# =============================================================================
# HANDOFF ANNOTATION — mask_drone.py
# =============================================================================
# PURPOSE: Mask bottom of equirect frames (drone + operator hands at nadir)
# CRITICAL: COLMAP masks use 0=IGNORE, 255=VALID — scene is white, drone is black
# INPUT:   frames_raw/ equirect JPEGs
# OUTPUT:  masks_equirect/frame_*.png
# CONFIG:  drone_mask.polygon — normalized [x,y], default y >= 0.58
# BUG FIX: Earlier version had inverted mask (only 4% pixels usable)
# SEE:     handoff/docs/KNOWN_ISSUES.md #1
# =============================================================================

"""Build equirectangular masks (drone region) before perspective dewarp."""

from __future__ import annotations

import json
from pathlib import Path

from config_paths import frame_source_dir, load_config, masks_equirect_dir

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:
    Image = None


def polygon_mask_cv(shape: tuple[int, int], polygon_norm: list[list[float]], dilate_px: int):
    h, w = shape[:2]
    pts = np.array([[int(x * w), int(y * h)] for x, y in polygon_norm], dtype=np.int32)
    # COLMAP: 0 = ignore, >0 = valid. Mask out the drone polygon only.
    mask = np.full((h, w), 255, dtype=np.uint8)
    cv2.fillPoly(mask, [pts], 0)
    if dilate_px > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_px * 2 + 1, dilate_px * 2 + 1))
        mask = cv2.dilate(mask, k)
    return mask


def polygon_mask_pil(shape: tuple[int, int], polygon_norm: list[list[float]], dilate_px: int):
    if Image is None:
        raise RuntimeError("Need opencv-python or Pillow for mask generation")
    h, w = shape[:2]
    pts = [(int(x * w), int(y * h)) for x, y in polygon_norm]
    mask = Image.new("L", (w, h), 255)
    ImageDraw.Draw(mask).polygon(pts, fill=0)
    # Full-resolution morphological dilate is very slow on 5K+ equirect frames.
    if dilate_px > 0 and max(w, h) <= 2400:
        mask = mask.filter(ImageFilter.MaxFilter(dilate_px * 2 + 1))
    return mask


def polygon_mask(shape: tuple[int, int], polygon_norm: list[list[float]], dilate_px: int):
    if cv2 is not None:
        return polygon_mask_cv(shape, polygon_norm, dilate_px)
    return polygon_mask_pil(shape, polygon_norm, dilate_px)


def save_mask(path: Path, mask) -> None:
    if cv2 is not None and hasattr(mask, "dtype"):
        cv2.imwrite(str(path), mask)
    else:
        mask.save(path)


def read_image_shape(path: Path) -> tuple[int, int, int] | tuple[int, int]:
    if cv2 is not None:
        img = cv2.imread(str(path))
        if img is None:
            raise RuntimeError(f"Cannot read {path}")
        return img.shape
    if Image is None:
        raise RuntimeError("Need opencv-python or Pillow to read images")
    with Image.open(path) as img:
        w, h = img.size
    return (h, w, 3)


def apply_inpaint(path: Path, mask) -> None:
    if cv2 is None:
        return
    img = cv2.imread(str(path))
    if img is None:
        return
    if hasattr(mask, "save"):
        mask = np.array(mask)
    cv2.imwrite(str(path), cv2.inpaint(img, mask, inpaintRadius=5, flags=cv2.INPAINT_TELEA))


def process_equirect_masks(
    frames_dir: Path,
    masks_dir: Path,
    polygon_norm: list[list[float]],
    dilate_px: int,
    inpaint: bool,
) -> None:
    masks_dir.mkdir(parents=True, exist_ok=True)
    paths = sorted(frames_dir.glob("frame_*.jpg"))
    meta = {"count": 0, "polygon": polygon_norm, "dilate_px": dilate_px, "inpaint": inpaint}
    for path in paths:
        shape = read_image_shape(path)
        mask = polygon_mask(shape, polygon_norm, dilate_px)
        save_mask(masks_dir / f"{path.stem}.png", mask)
        if inpaint:
            apply_inpaint(path, mask)
        meta["count"] += 1
    (masks_dir / "mask_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def main(cfg_path: Path | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    cfg = load_config(args.config or cfg_path or (root / "config.yaml"))
    work = Path(cfg["work_dir"])
    dm = cfg.get("drone_mask", {})
    if not dm.get("enabled", True):
        print("drone_mask.enabled is false — skipping")
        return
    process_equirect_masks(
        frame_source_dir(cfg, work),
        masks_equirect_dir(cfg, work),
        dm["polygon"],
        int(dm.get("dilate_px", 12)),
        bool(dm.get("inpaint", False)),
    )
    print(f"Wrote equirect masks to {work / 'masks_equirect'} (dewarp copies them to workspace/masks)")


if __name__ == "__main__":
    main()
