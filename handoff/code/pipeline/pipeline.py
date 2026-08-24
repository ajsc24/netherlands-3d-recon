# =============================================================================
# HANDOFF ANNOTATION — pipeline.py
# =============================================================================
# PURPOSE: Main orchestrator — video → frames → masks → dewarp → COLMAP mesh
# STEPS:   check → extract → mask → dewarp → colmap (resume via --from-step)
# ENTRY:   QUICKSTART_GPU.ps1 calls this
# SEE:     handoff/docs/CODE_ANNOTATIONS.md
# =============================================================================

"""End-to-end: repair check -> frames -> dewarp -> drone mask -> COLMAP mesh."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from config_paths import load_config
from dewarp_views import main as dewarp_main
from extract_frames import main as extract_main
from mask_drone import main as mask_main
from repair_video import main as repair_main
from run_colmap import main as colmap_main


def run_repair_check(cfg: dict) -> int:
    import subprocess

    video = Path(cfg["video_path"])
    ref = cfg.get("reference_video_path")
    cmd = [sys.executable, str(Path(__file__).parent / "repair_video.py"), str(video)]
    if ref:
        cmd += ["--reference", str(ref)]
    return subprocess.call(cmd)


def log_step(name: str) -> None:
    print(f"\n{'=' * 60}\n  STEP: {name}\n{'=' * 60}\n", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Drone video -> 3D model (no drone)")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).parent / "config.yaml",
    )
    parser.add_argument(
        "--from-step",
        choices=["check", "extract", "mask", "dewarp", "colmap"],
        default="check",
        help="Start at this step (skip earlier steps)",
    )
    args = parser.parse_args()
    cfg = load_config(args.config)
    steps = ["check", "extract", "mask", "dewarp", "colmap"]
    start = steps.index(args.from_step)

    if start <= steps.index("check"):
        log_step("1/5 Video check (ffprobe)")
        code = run_repair_check(cfg)
        if code != 0:
            print("\nStop: fix the video file before continuing (see messages above).")
            return code
        print("Video OK — continuing to frame extraction.\n", flush=True)

    if start <= steps.index("extract"):
        log_step("2/5 Extract frames")
        extract_main(args.config)

    if start <= steps.index("mask"):
        log_step("3/5 Build drone masks")
        mask_main(args.config)

    if start <= steps.index("dewarp"):
        log_step("4/5 Prepare images for COLMAP")
        dewarp_main(args.config)

    if start <= steps.index("colmap"):
        log_step("5/5 COLMAP reconstruction")
        code = colmap_main(args.config)
        if code != 0:
            print(
                "\nCOLMAP is required for the 3D model step.\n"
                "Windows: ..\\Install-Windows.ps1 then ..\\QUICKSTART_GPU.ps1 -FromStep colmap\n"
                "Linux: https://colmap.github.io/install.html\n"
                "Or set colmap.colmap_exe in config.yaml.\n"
            )
        return code

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
