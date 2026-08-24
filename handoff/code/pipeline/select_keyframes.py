# HANDOFF: Select ~45 sharp keyframes for pro pipeline (fewer images, faster).
# Used with config_netherlands_pro.yaml. See Run-ProQuality.ps1

"""Pick sharp, well-spaced keyframes from extracted video frames (pro-style ~30-50 photos)."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from config_paths import load_config

try:
    import cv2
    import numpy as np
except ImportError as exc:
    raise SystemExit("opencv-python required") from exc


def laplacian_sharpness(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def score_frame(path: Path, downscale: int) -> float:
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0.0
    if downscale > 1:
        h, w = img.shape
        img = cv2.resize(img, (w // downscale, h // downscale), interpolation=cv2.INTER_AREA)
    return laplacian_sharpness(img)


def select_indices(
    scores: list[float],
    target: int,
    min_gap: int,
) -> list[int]:
    n = len(scores)
    if n <= target:
        return list(range(n))

    order = sorted(range(n), key=lambda i: scores[i], reverse=True)
    picked: list[int] = []
    for idx in order:
        if all(abs(idx - p) >= min_gap for p in picked):
            picked.append(idx)
        if len(picked) >= target:
            break

    if len(picked) < target:
        step = max(1, n // target)
        for i in range(0, n, step):
            if i not in picked:
                picked.append(i)
            if len(picked) >= target:
                break

    return sorted(picked[:target])


def copy_selected(
    src_dir: Path,
    dst_dir: Path,
    indices: list[int],
    frames: list[Path],
    mask_src: Path | None,
    mask_dst: Path | None,
) -> None:
    if dst_dir.exists():
        shutil.rmtree(dst_dir)
    dst_dir.mkdir(parents=True)
    if mask_dst:
        if mask_dst.exists():
            shutil.rmtree(mask_dst)
        mask_dst.mkdir(parents=True)

    for out_i, src_i in enumerate(indices):
        src = frames[src_i]
        dst = dst_dir / f"frame_{out_i:06d}.jpg"
        shutil.copy2(src, dst)
        if mask_src and mask_dst and mask_src.is_dir():
            m = mask_src / f"{src.stem}.png"
            if m.is_file():
                shutil.copy2(m, mask_dst / f"{dst.stem}.png")


def main(cfg_path: Path | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    cfg = load_config(args.config or cfg_path or (root / "config.yaml"))
    kf = cfg.get("keyframes", {})
    if not kf.get("enabled", False):
        print("keyframes.enabled is false — skipping")
        return

    work = Path(cfg["work_dir"])
    raw = work / "frames_raw"
    frames = sorted(raw.glob("frame_*.jpg"))
    if not frames:
        raise FileNotFoundError(f"No frames in {raw}")

    target = int(kf.get("target_count", 45))
    min_gap = int(kf.get("min_frame_gap", 4))
    downscale = int(kf.get("sharpness_downscale", 8))

    scores = [score_frame(p, downscale) for p in frames]
    indices = select_indices(scores, target, min_gap)

    out_dir = work / kf.get("output_dir", "frames_key")
    mask_out = work / "masks_equirect_key" if cfg.get("drone_mask", {}).get("enabled") else None
    copy_selected(
        raw,
        out_dir,
        indices,
        frames,
        work / "masks_equirect" if (work / "masks_equirect").is_dir() else None,
        mask_out,
    )

    meta = {
        "source_frames": len(frames),
        "selected": len(indices),
        "indices": indices,
        "scores": [scores[i] for i in indices],
        "min_gap": min_gap,
        "target": target,
    }
    (out_dir / "keyframes_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Selected {len(indices)} keyframes -> {out_dir}")


if __name__ == "__main__":
    main()
