# HANDOFF: Equirect → N perspective pinhole views for COLMAP (views_per_frame=8).
# Copies masks to colmap/masks/. See handoff/docs/CODE_ANNOTATIONS.md

"""Convert equirectangular Insta360 frames to perspective views for COLMAP."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from config_paths import frame_source_dir, load_config

try:
    import cv2
    import numpy as np
    import py360convert as p360
except ImportError:
    cv2 = None
    np = None
    p360 = None

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None


def yaw_pitch_grid(n_views: int) -> list[tuple[float, float]]:
    if n_views <= 4:
        return [(0, 0), (90, 0), (180, 0), (-90, 0)][:n_views]
    yaws = np.linspace(-180, 180, n_views, endpoint=False) if np is not None else [
        -180 + (360 / n_views) * i for i in range(n_views)
    ]
    pitches = [0.0] * (n_views // 2) + [15.0] * (n_views - n_views // 2)
    return [(float(y), float(pitches[i % len(pitches)])) for i, y in enumerate(yaws)]


def equirect_to_perspective(
    equirect_bgr,
    fov_deg: float,
    out_size: int,
    yaw_deg: float,
    pitch_deg: float,
):
    rgb = cv2.cvtColor(equirect_bgr, cv2.COLOR_BGR2RGB)
    out = p360.e2p(
        rgb,
        fov_deg=fov_deg,
        u_deg=yaw_deg,
        v_deg=pitch_deg,
        out_hw=(out_size, out_size),
    )
    return cv2.cvtColor(out, cv2.COLOR_RGB2BGR)


def warp_mask_equirect_to_perspective(
    mask_gray,
    fov_deg: float,
    out_size: int,
    yaw_deg: float,
    pitch_deg: float,
):
    mask_rgb = cv2.cvtColor(mask_gray, cv2.COLOR_GRAY2RGB)
    warped = p360.e2p(
        mask_rgb,
        fov_deg=fov_deg,
        u_deg=yaw_deg,
        v_deg=pitch_deg,
        out_hw=(out_size, out_size),
    )
    out = cv2.cvtColor(warped, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(out, 127, 255, cv2.THRESH_BINARY)
    return binary


def v360_filter(yaw: float, pitch: float, fov: float, size: int) -> str:
    return (
        f"v360=input=equirect:output=rectilinear:yaw={yaw}:pitch={pitch}:roll=0:"
        f"d_fov={fov}:w={size}:h={size}"
    )


def dewarp_file_ffmpeg(
    src: Path,
    dst: Path,
    yaw: float,
    pitch: float,
    fov: float,
    size: int,
) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found")
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(src),
        "-vf",
        v360_filter(yaw, pitch, fov, size),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(dst),
    ]
    subprocess.run(cmd, check=True)


def main(cfg_path: Path | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    cfg_path = args.config or cfg_path or root / "config.yaml"
    cfg = load_config(cfg_path)
    work = Path(cfg["work_dir"])
    raw_dir = frame_source_dir(cfg, work)
    images_dir = work / "images"
    masks_dir = work / "masks"
    masks_equirect = work / "masks_equirect"
    images_dir.mkdir(parents=True, exist_ok=True)
    masks_dir.mkdir(parents=True, exist_ok=True)

    projection = cfg.get("projection", "equirect")
    n_views = int(cfg.get("views_per_frame", 8))
    fov = float(cfg.get("perspective_fov_deg", 90))
    size = int(cfg.get("perspective_size", 1024))
    use_masks = cfg.get("drone_mask", {}).get("enabled", True)
    directions = yaw_pitch_grid(n_views)
    use_ffmpeg = p360 is None or cv2 is None

    frames = sorted(raw_dir.glob("frame_*.jpg"))
    if not frames:
        raise FileNotFoundError(f"No frames in {raw_dir}. Run extract_frames.py first.")

    iterator = tqdm(frames, desc="dewarp") if tqdm else frames
    count = 0
    for frame_path in iterator:
        stem = frame_path.stem
        eq_mask_path = masks_equirect / f"{stem}.png"

        if projection == "raw":
            name = f"{stem}_v00"
            out_path = images_dir / f"{name}.jpg"
            if use_ffmpeg:
                dewarp_file_ffmpeg(frame_path, out_path, 0, 0, fov, size)
            else:
                img = cv2.imread(str(frame_path))
                if img is None:
                    continue
                if not out_path.exists() or out_path.stat().st_size == 0:
                    cv2.imwrite(str(out_path), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
            if use_masks and eq_mask_path.is_file():
                mask_out = masks_dir / f"{name}.png"
                if use_ffmpeg:
                    dewarp_file_ffmpeg(eq_mask_path, mask_out, 0, 0, fov, size)
                else:
                    eq_mask = cv2.imread(str(eq_mask_path), cv2.IMREAD_GRAYSCALE)
                    cv2.imwrite(str(mask_out), eq_mask)
            count += 1
            continue

        for vi, (yaw, pitch) in enumerate(directions):
            name = f"{stem}_v{vi:02d}"
            out_path = images_dir / f"{name}.jpg"
            if use_ffmpeg:
                dewarp_file_ffmpeg(frame_path, out_path, yaw, pitch, fov, size)
                if use_masks and eq_mask_path.is_file():
                    dewarp_file_ffmpeg(
                        eq_mask_path,
                        masks_dir / f"{name}.png",
                        yaw,
                        pitch,
                        fov,
                        size,
                    )
            else:
                img = cv2.imread(str(frame_path))
                if img is None:
                    continue
                persp = equirect_to_perspective(img, fov, size, yaw, pitch)
                cv2.imwrite(str(out_path), persp, [cv2.IMWRITE_JPEG_QUALITY, 92])
                if use_masks and eq_mask_path.is_file():
                    eq_mask = cv2.imread(str(eq_mask_path), cv2.IMREAD_GRAYSCALE)
                    pm = warp_mask_equirect_to_perspective(eq_mask, fov, size, yaw, pitch)
                    cv2.imwrite(str(masks_dir / f"{name}.png"), pm)
            count += 1

    print(f"Wrote {count} perspective images to {images_dir}")
    if use_ffmpeg:
        print("Used ffmpeg v360 for equirect -> rectilinear conversion")
    if use_masks and masks_equirect.is_dir():
        print(f"Wrote COLMAP masks to {masks_dir}")


if __name__ == "__main__":
    main()
