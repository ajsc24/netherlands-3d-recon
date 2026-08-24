"""Accuracy-first orchestrator with hard QA gates between stages."""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

# Ensure src/ is on path when run as script
SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paths import default_config_path, ensure_work_dirs, load_config, write_status  # noqa: E402

STAGES = [
    "extract",
    "keyframes",
    "mask",
    "dewarp",
    "sfm",
    "mvs",
    "mesh_post",
    "openmvs",
    "pick",
    "export_360gs",
]


def run_stage(name: str, cfg_path: Path) -> int:
    if name == "extract":
        from extract_frames import extract_frames

        return extract_frames(cfg_path)
    if name == "keyframes":
        from select_keyframes import select_keyframes

        return select_keyframes(cfg_path)
    if name == "mask":
        from mask_drone import build_masks

        return build_masks(cfg_path)
    if name == "dewarp":
        from dewarp_views import dewarp_views

        return dewarp_views(cfg_path)
    if name == "sfm":
        from colmap_sfm import run_sfm

        return run_sfm(cfg_path)
    if name == "mvs":
        from colmap_mvs import run_mvs

        return run_mvs(cfg_path)
    if name == "mesh_post":
        from mesh_post import run_mesh_post

        return run_mesh_post(cfg_path)
    if name == "openmvs":
        from openmvs_run import run_openmvs

        return run_openmvs(cfg_path)
    if name == "pick":
        from pick_best import pick_and_report

        return pick_and_report(cfg_path)
    if name == "export_360gs":
        from export_360gs import export_360gs

        return export_360gs(cfg_path)
    raise ValueError(f"Unknown stage: {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Accurate Netherlands 3D rebuild orchestrator")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--from-step", choices=STAGES, default="extract")
    parser.add_argument("--to-step", choices=STAGES, default="export_360gs")
    parser.add_argument(
        "--list-stages",
        action="store_true",
        help="Print stage names and exit",
    )
    args = parser.parse_args()

    if args.list_stages:
        print("\n".join(STAGES))
        return 0

    cfg_path = (args.config or default_config_path()).resolve()
    cfg = load_config(cfg_path)
    work = ensure_work_dirs(cfg)

    start = STAGES.index(args.from_step)
    end = STAGES.index(args.to_step)
    if end < start:
        print("--to-step must be after --from-step", file=sys.stderr)
        return 1

    print("=" * 60)
    print("ACCURATE RECONSTRUCTION PIPELINE")
    print(f"  config : {cfg_path}")
    print(f"  work   : {work}")
    print(f"  stages : {STAGES[start]} .. {STAGES[end]}")
    print("=" * 60)

    log_dir = work / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    for stage in STAGES[start : end + 1]:
        print(f"\n######## STAGE: {stage} ########\n", flush=True)
        try:
            code = run_stage(stage, cfg_path)
        except Exception as exc:
            traceback.print_exc()
            write_status(work, stage, False, {"error": str(exc)})
            print(f"\nHARD STOP at stage '{stage}': {exc}", file=sys.stderr)
            return 10
        if code != 0:
            print(f"\nHARD STOP at stage '{stage}' (exit {code})", file=sys.stderr)
            return code
        print(f"\n######## STAGE OK: {stage} ########\n", flush=True)

    print("\n=== PIPELINE COMPLETE ===")
    print(f"  Workspace: {work}")
    print(f"  Best mesh: {work / 'colmap' / 'dense' / 'mesh_best.ply'}")
    print(f"  Report:    {work / 'QUALITY_REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
