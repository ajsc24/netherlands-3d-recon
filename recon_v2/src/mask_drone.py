"""Build equirectangular drone masks (COLMAP polarity: 0=ignore, 255=valid)."""

from __future__ import annotations

import sys
from pathlib import Path

from paths import (
    ensure_work_dirs,
    equirect_source_dir,
    load_config,
    write_status,
)
from qa import QAError, assert_mask_valid_fraction, write_qa_json

try:
    import cv2
    import numpy as np
except ImportError as exc:
    raise SystemExit("opencv-python required") from exc


def polygon_mask(
    shape: tuple[int, int],
    polygon_norm: list[list[float]],
    dilate_px: int,
) -> np.ndarray:
    h, w = shape[:2]
    pts = np.array([[int(x * w), int(y * h)] for x, y in polygon_norm], dtype=np.int32)
    mask = np.full((h, w), 255, dtype=np.uint8)
    cv2.fillPoly(mask, [pts], 0)
    if dilate_px > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_px * 2 + 1, dilate_px * 2 + 1))
        # Dilate the ignored (0) region by eroding the valid region
        mask = cv2.erode(mask, k)
    return mask


def write_qa_overlay(frame_bgr: np.ndarray, mask: np.ndarray, out_path: Path) -> None:
    overlay = frame_bgr.copy()
    ignored = mask < 128
    overlay[ignored] = (overlay[ignored] * 0.35 + np.array([0, 0, 180]) * 0.65).astype(np.uint8)
    cv2.imwrite(str(out_path), overlay)


def build_masks(cfg_path: Path | None = None) -> int:
    cfg = load_config(cfg_path)
    work = ensure_work_dirs(cfg)
    dm = cfg.get("drone_mask", {})
    if not dm.get("enabled", True):
        print("drone_mask.enabled is false — skipping")
        write_status(work, "mask", True, {"skipped": True})
        return 0

    frames_dir = equirect_source_dir(cfg, work)
    frames = sorted(frames_dir.glob("frame_*.jpg"))
    if not frames:
        print(f"No frames in {frames_dir}", file=sys.stderr)
        return 1

    masks_dir = work / "masks_equirect"
    if masks_dir.exists():
        for old in masks_dir.glob("*.png"):
            old.unlink()
    masks_dir.mkdir(parents=True, exist_ok=True)
    qa_dir = work / "qa" / "mask_overlays"
    qa_dir.mkdir(parents=True, exist_ok=True)

    polygon = dm.get("polygon") or [[0.0, 0.58], [1.0, 0.58], [1.0, 1.0], [0.0, 1.0]]
    dilate = int(dm.get("dilate_px", 10))
    min_valid = float(dm.get("min_valid_fraction", 0.55))

    first = cv2.imread(str(frames[0]))
    if first is None:
        print(f"Cannot read {frames[0]}", file=sys.stderr)
        return 1
    template = polygon_mask(first.shape, polygon, dilate)

    written: list[Path] = []
    for i, frame_path in enumerate(frames):
        out = masks_dir / f"{frame_path.stem}.png"
        cv2.imwrite(str(out), template)
        written.append(out)
        if i < 8 or i % 40 == 0:
            img = cv2.imread(str(frame_path))
            if img is not None:
                write_qa_overlay(img, template, qa_dir / f"{frame_path.stem}_overlay.jpg")

    print(f"Wrote {len(written)} equirect masks -> {masks_dir}")
    print(f"QA overlays -> {qa_dir}")

    try:
        report = assert_mask_valid_fraction(written, min_valid)
    except QAError as exc:
        print(f"MASK QA FAILED: {exc}", file=sys.stderr)
        write_status(work, "mask", False, {"error": str(exc)})
        return 3

    write_qa_json(work / "qa" / "mask_qa.json", report)
    print(f"Mask QA OK: mean valid = {report['mean_valid_fraction']:.1%}")
    write_status(work, "mask", True, report)
    return 0


def main() -> int:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=None)
    args = p.parse_args()
    return build_masks(args.config)


if __name__ == "__main__":
    raise SystemExit(main())
