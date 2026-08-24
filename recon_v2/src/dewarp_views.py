"""Equirectangular frames → overlapping perspective views for COLMAP."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from paths import (
    ensure_work_dirs,
    equirect_source_dir,
    load_config,
    write_status,
)

try:
    import cv2
    import numpy as np
    import py360convert as p360
except ImportError as exc:
    raise SystemExit(f"Need opencv + py360convert: {exc}") from exc

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None


def yaw_pitch_grid(n_views: int, pitch_cycle: list[float]) -> list[tuple[float, float]]:
    yaws = list(np.linspace(-180.0, 180.0, n_views, endpoint=False))
    pitches = [float(pitch_cycle[i % len(pitch_cycle)]) for i in range(n_views)]
    return list(zip(yaws, pitches))


def e2p_bgr(equirect_bgr, fov_deg: float, out_size: int, yaw: float, pitch: float):
    rgb = cv2.cvtColor(equirect_bgr, cv2.COLOR_BGR2RGB)
    out = p360.e2p(
        rgb,
        fov_deg=fov_deg,
        u_deg=yaw,
        v_deg=pitch,
        out_hw=(out_size, out_size),
    )
    return cv2.cvtColor(out, cv2.COLOR_RGB2BGR)


def e2p_mask(mask_gray, fov_deg: float, out_size: int, yaw: float, pitch: float):
    mask_rgb = cv2.cvtColor(mask_gray, cv2.COLOR_GRAY2RGB)
    warped = p360.e2p(
        mask_rgb,
        fov_deg=fov_deg,
        u_deg=yaw,
        v_deg=pitch,
        out_hw=(out_size, out_size),
    )
    gray = cv2.cvtColor(warped, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
    return binary


def dewarp_views(cfg_path: Path | None = None) -> int:
    cfg = load_config(cfg_path)
    work = ensure_work_dirs(cfg)
    dw = cfg.get("dewarp", {})
    n_views = int(dw.get("views_per_frame", 12))
    fov = float(dw.get("perspective_fov_deg", 85))
    size = int(dw.get("perspective_size", 1536))
    pitch_cycle = [float(x) for x in dw.get("pitch_cycle", [0.0, 0.0, 0.0, 8.0])]
    views = yaw_pitch_grid(n_views, pitch_cycle)

    frames_dir = equirect_source_dir(cfg, work)
    frames = sorted(frames_dir.glob("frame_*.jpg"))
    if not frames:
        print(f"No frames in {frames_dir}", file=sys.stderr)
        return 1

    masks_eq = work / "masks_equirect"
    use_masks = cfg.get("drone_mask", {}).get("enabled", True) and masks_eq.is_dir()

    images = work / "images"
    masks = work / "masks"
    for d in (images, masks):
        if d.exists():
            for old in d.glob("*"):
                if old.is_file():
                    old.unlink()
        d.mkdir(parents=True, exist_ok=True)

    print(
        f"Dewarping {len(frames)} frames × {n_views} views "
        f"(fov={fov}, size={size}) -> {images}",
        flush=True,
    )
    iterator = frames
    if tqdm is not None:
        iterator = tqdm(frames, desc="dewarp")

    written = 0
    for frame_path in iterator:
        img = cv2.imread(str(frame_path))
        if img is None:
            continue
        mask_eq = None
        if use_masks:
            mp = masks_eq / f"{frame_path.stem}.png"
            if mp.is_file():
                mask_eq = cv2.imread(str(mp), cv2.IMREAD_GRAYSCALE)

        for vi, (yaw, pitch) in enumerate(views):
            name = f"{frame_path.stem}_v{vi:02d}.jpg"
            view = e2p_bgr(img, fov, size, yaw, pitch)
            cv2.imwrite(str(images / name), view, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            if mask_eq is not None:
                # COLMAP expects mask named <image_name>.png alongside image stem
                mview = e2p_mask(mask_eq, fov, size, yaw, pitch)
                cv2.imwrite(str(masks / f"{Path(name).stem}.png"), mview)
            written += 1

    qa_dir = work / "qa" / "dewarp_samples"
    qa_dir.mkdir(parents=True, exist_ok=True)
    for s in sorted(images.glob("frame_000000_v*.jpg"))[:4]:
        shutil.copy2(s, qa_dir / s.name)

    n_img = len(list(images.glob("*.jpg")))
    n_msk = len(list(masks.glob("*.png")))
    detail = {
        "images": n_img,
        "masks": n_msk,
        "views_per_frame": n_views,
        "fov": fov,
        "size": size,
        "written_ops": written,
    }
    print(f"Dewarp done: {n_img} images, {n_msk} masks")
    if n_img < 100:
        print("WARNING: unexpectedly few dewarped images", file=sys.stderr)
        write_status(work, "dewarp", False, detail)
        return 2

    write_status(work, "dewarp", True, detail)
    return 0


def main() -> int:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=None)
    args = p.parse_args()
    return dewarp_views(args.config)


if __name__ == "__main__":
    raise SystemExit(main())
