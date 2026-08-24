"""Export equirect keyframes for 360 Gaussian Splatting training."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from paths import (
    ensure_work_dirs,
    frames_raw_dir,
    load_config,
    write_status,
)
from select_keyframes import score_frame, select_indices


def export_360gs(cfg_path: Path | None = None) -> int:
    cfg = load_config(cfg_path)
    gs = cfg.get("gaussian_splat", {})
    if not gs.get("enabled", True):
        print("gaussian_splat.enabled is false — skipping")
        return 0

    work = ensure_work_dirs(cfg)
    raw = frames_raw_dir(work)
    if not raw.is_dir() or not list(raw.glob("frame_*.jpg")):
        print(f"No raw frames in {raw} — run extract first", file=sys.stderr)
        return 1

    out = Path(gs.get("output_dir"))
    img_dir = out / "images"
    if img_dir.exists():
        shutil.rmtree(img_dir)
    img_dir.mkdir(parents=True)

    frames = sorted(raw.glob("frame_*.jpg"))
    target = int(gs.get("target_keyframes", 100))
    min_gap = int(gs.get("min_frame_gap", 3))
    print(f"Scoring {len(frames)} frames for 360GS export (target={target})...")
    scores = [score_frame(p, 8) for p in frames]
    indices = select_indices(scores, target, min_gap)

    for out_i, src_i in enumerate(indices):
        shutil.copy2(frames[src_i], img_dir / f"frame_{out_i:06d}.jpg")

    meta = {
        "source_frames": len(frames),
        "exported": len(indices),
        "indices": indices,
        "camera": "equirectangular / spherical",
        "source_video": cfg.get("video_path"),
    }
    (out / "dataset_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    readme = out / "README_TRAIN.md"
    readme.write_text(
        "\n".join(
            [
                "# 360 Gaussian Splatting — train these keyframes",
                "",
                "Dataset: equirectangular (spherical) JPEG keyframes from the Insta360 walkthrough.",
                "",
                "## Requirements",
                "",
                "- Python 3.10 or 3.11 (not 3.13)",
                "- CUDA PyTorch matching your GPU driver",
                "- git",
                "",
                "## Steps",
                "",
                "```powershell",
                "# From project root",
                ".\\Install-360GS.ps1",
                "",
                "# Then (example — see https://github.com/inuex35/360-gaussian-splatting ):",
                "# 1) OpenSfM spherical reconstruction on this folder",
                "# 2) cd tools\\360gs",
                "# 3) python train.py -s <path-to-this-dataset> --panorama",
                "```",
                "",
                f"Images: `{img_dir}` ({len(indices)} frames)",
                "",
                "Use this splat for visual completeness where the COLMAP/OpenMVS mesh",
                "has holes on flat painted walls.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(f"Exported {len(indices)} equirect keyframes -> {out}")
    write_status(work, "export_360gs", True, {"exported": len(indices), "out": str(out)})
    return 0


def main() -> int:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=None)
    args = p.parse_args()
    return export_360gs(args.config)


if __name__ == "__main__":
    raise SystemExit(main())
