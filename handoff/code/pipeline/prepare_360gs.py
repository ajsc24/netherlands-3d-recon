# HANDOFF: Export keyframes + poses for 360 Gaussian Splatting training.
# Output: exports/360gs_dataset/. Requires Install-360GS.ps1 for training.

"""Export equirect keyframes for 360-gaussian-splatting / OpenSfM."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from config_paths import load_config
from select_keyframes import score_frame, select_indices


def export_dataset(cfg_path: Path) -> int:
    cfg = load_config(cfg_path)
    gs = cfg.get("gaussian_splat", {})
    if not gs.get("enabled", True):
        print("gaussian_splat.enabled is false — skipping")
        return 0

    root = Path(__file__).resolve().parent.parent
    work = Path(cfg["work_dir"])
    raw = work / "frames_raw"
    if not raw.is_dir():
        print(f"No {raw} — run frame extraction first", flush=True)
        return 1

    out_rel = gs.get("output_dir", "exports/360gs_dataset")
    out = (root / out_rel).resolve() if not Path(out_rel).is_absolute() else Path(out_rel)
    img_dir = out / "images"
    if img_dir.exists():
        shutil.rmtree(img_dir)
    img_dir.mkdir(parents=True)

    frames = sorted(raw.glob("frame_*.jpg"))
    target = int(gs.get("target_keyframes", 80))
    min_gap = int(gs.get("min_frame_gap", 4))
    scores = [score_frame(p, 8) for p in frames]
    indices = select_indices(scores, target, min_gap)

    for out_i, src_i in enumerate(indices):
        shutil.copy2(frames[src_i], img_dir / f"frame_{out_i:06d}.jpg")

    meta = {
        "source_frames": len(frames),
        "exported": len(indices),
        "indices": indices,
        "readme": (
            "Train with 360-gaussian-splatting (github.com/inuex35/360-gaussian-splatting):\n"
            "  1. OpenSfM reconstruct with spherical camera model\n"
            "  2. python train.py -s <this_folder> --panorama\n"
            "Or use Nerfstudio on cubemap exports (see README-BEST.md)."
        ),
    }
    (out / "dataset_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Exported {len(indices)} equirect keyframes to {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    return export_dataset(args.config)


if __name__ == "__main__":
    raise SystemExit(main())
