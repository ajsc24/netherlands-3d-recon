"""Select sharp, temporally spaced keyframes from extracted equirect frames."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from paths import (
    ensure_work_dirs,
    frames_key_dir,
    frames_raw_dir,
    load_config,
    write_status,
)

try:
    import cv2
    import numpy as np
except ImportError as exc:
    raise SystemExit("opencv-python required") from exc


def laplacian_sharpness(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def score_frame(path: Path, downscale: int = 8) -> float:
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0.0
    if downscale > 1:
        h, w = img.shape
        img = cv2.resize(img, (w // downscale, h // downscale), interpolation=cv2.INTER_AREA)
    return laplacian_sharpness(img)


def select_indices(scores: list[float], target: int, min_gap: int) -> list[int]:
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

    # Fill gaps for coverage if sharpness greedy left holes
    if len(picked) < target:
        step = max(1, n // target)
        for i in range(0, n, step):
            if all(abs(i - p) >= min_gap for p in picked):
                picked.append(i)
            if len(picked) >= target:
                break

    return sorted(picked[:target])


def select_keyframes(cfg_path: Path | None = None) -> int:
    cfg = load_config(cfg_path)
    work = ensure_work_dirs(cfg)
    kf = cfg.get("keyframes", {})
    if not kf.get("enabled", True):
        print("keyframes.enabled is false — copying all raw frames")
        raw = frames_raw_dir(work)
        dst = frames_key_dir(cfg, work)
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(raw, dst)
        n = len(list(dst.glob("frame_*.jpg")))
        write_status(work, "keyframes", True, {"exported": n, "mode": "all"})
        return 0

    raw = frames_raw_dir(work)
    frames = sorted(raw.glob("frame_*.jpg"))
    if not frames:
        print(f"No frames in {raw}", file=sys.stderr)
        return 1

    target = int(kf.get("target", 320))
    min_gap = int(kf.get("min_frame_gap", 2))
    print(f"Scoring {len(frames)} frames (target={target}, min_gap={min_gap})...", flush=True)
    scores = [score_frame(p) for p in frames]
    indices = select_indices(scores, target, min_gap)

    dst = frames_key_dir(cfg, work)
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)

    for out_i, src_i in enumerate(indices):
        shutil.copy2(frames[src_i], dst / f"frame_{out_i:06d}.jpg")

    meta = {
        "source_frames": len(frames),
        "exported": len(indices),
        "indices": indices,
        "mean_sharpness": float(sum(scores[i] for i in indices) / max(1, len(indices))),
        "all_mean_sharpness": float(sum(scores) / max(1, len(scores))),
    }
    (work / "qa" / "keyframes.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Selected {len(indices)} keyframes -> {dst}")
    write_status(work, "keyframes", True, meta)
    return 0


def main() -> int:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=None)
    args = p.parse_args()
    return select_keyframes(args.config)


if __name__ == "__main__":
    raise SystemExit(main())
