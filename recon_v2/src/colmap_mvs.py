"""COLMAP dense stereo + dual fusion (strict + wall-friendly)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from colmap_sfm import pick_best_sparse_model, resolve_colmap
from paths import ensure_work_dirs, load_config, write_status


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def selected_sparse(work: Path, colmap: str) -> Path | None:
    marker = work / "colmap" / "selected_sparse.txt"
    if marker.is_file():
        p = Path(marker.read_text(encoding="utf-8").strip())
        if p.is_dir() and (p / "images.bin").is_file():
            return p
    return pick_best_sparse_model(colmap, work / "colmap" / "sparse")


def fusion_cmd(
    colmap: str,
    dense: Path,
    out_ply: Path,
    params: dict,
    colmap_cfg: dict,
) -> list[str]:
    cmd = [
        colmap,
        "stereo_fusion",
        "--workspace_path", str(dense),
        "--workspace_format", "COLMAP",
        "--input_type", "geometric",
        "--output_path", str(out_ply),
        "--StereoFusion.num_threads",
        str(int(colmap_cfg.get("fusion_num_threads", -1))),
    ]
    if colmap_cfg.get("fusion_use_cache", True):
        cmd += ["--StereoFusion.use_cache", "1"]
    if "fusion_cache_size" in colmap_cfg:
        cmd += ["--StereoFusion.cache_size", str(int(colmap_cfg["fusion_cache_size"]))]
    mapping = [
        ("max_reproj_error", "--StereoFusion.max_reproj_error"),
        ("max_depth_error", "--StereoFusion.max_depth_error"),
        ("max_normal_error", "--StereoFusion.max_normal_error"),
        ("min_num_pixels", "--StereoFusion.min_num_pixels"),
        ("check_num_images", "--StereoFusion.check_num_images"),
    ]
    for key, flag in mapping:
        if key in params:
            cmd += [flag, str(params[key])]
    return cmd


def run_mvs(cfg_path: Path | None = None, from_step: str = "undistort") -> int:
    cfg = load_config(cfg_path)
    work = ensure_work_dirs(cfg)
    colmap_cfg = cfg.get("colmap", {})
    colmap = resolve_colmap(colmap_cfg)
    if not colmap:
        print("COLMAP not found", file=sys.stderr)
        return 1

    images = work / "images"
    dense = work / "colmap" / "dense"
    dense.mkdir(parents=True, exist_ok=True)
    model_dir = selected_sparse(work, colmap)
    if model_dir is None:
        print("No sparse model — run sfm first", file=sys.stderr)
        return 2

    steps = ["undistort", "stereo", "fusion"]
    if from_step not in steps:
        print(f"Unknown from_step: {from_step}", file=sys.stderr)
        return 1
    start = steps.index(from_step)

    if start <= steps.index("undistort"):
        print("\n=== Dense: undistort ===", flush=True)
        run([
            colmap,
            "image_undistorter",
            "--image_path", str(images),
            "--input_path", str(model_dir),
            "--output_path", str(dense),
            "--output_type", "COLMAP",
        ])

    if start <= steps.index("stereo"):
        print("\n=== Dense: patch_match_stereo (long) ===", flush=True)
        patch = [
            colmap,
            "patch_match_stereo",
            "--workspace_path", str(dense),
            "--workspace_format", "COLMAP",
            "--PatchMatchStereo.geom_consistency",
            "true" if colmap_cfg.get("dense_geom_consistency", True) else "false",
            "--PatchMatchStereo.max_image_size",
            str(int(colmap_cfg.get("dense_max_image_size", 1400))),
            "--PatchMatchStereo.gpu_index",
            str(int(colmap_cfg.get("dense_gpu_index", 0))),
            "--PatchMatchStereo.cache_size",
            str(int(colmap_cfg.get("dense_cache_size", 48))),
        ]
        run(patch)

    if start <= steps.index("fusion"):
        print("\n=== Dense: dual fusion (strict + wall) ===", flush=True)
        strict = cfg.get("fusion_strict", {})
        wall = cfg.get("fusion_wall", {})
        strict_out = dense / strict.get("output_name", "fused_strict.ply")
        wall_out = dense / wall.get("output_name", "fused_wall.ply")

        try:
            run(fusion_cmd(colmap, dense, strict_out, strict, colmap_cfg))
        except subprocess.CalledProcessError as exc:
            print(f"Strict fusion failed: {exc}", file=sys.stderr)

        try:
            run(fusion_cmd(colmap, dense, wall_out, wall, colmap_cfg))
        except subprocess.CalledProcessError as exc:
            print(f"Wall fusion failed: {exc}", file=sys.stderr)
            write_status(work, "mvs", False, {"error": "wall fusion failed"})
            return 4

        primary = cfg.get("fusion_primary", "wall")
        src = wall_out if primary == "wall" else strict_out
        if not src.is_file():
            src = wall_out if wall_out.is_file() else strict_out
        if not src.is_file():
            print("No fused cloud produced", file=sys.stderr)
            write_status(work, "mvs", False, {"error": "no fused ply"})
            return 4

        fused = dense / "fused.ply"
        shutil.copy2(src, fused)
        print(f"Primary fused.ply <- {src.name}")

    detail = {
        "dense": str(dense),
        "fused_strict": (dense / "fused_strict.ply").is_file(),
        "fused_wall": (dense / "fused_wall.ply").is_file(),
        "fused": (dense / "fused.ply").is_file(),
    }
    write_status(work, "mvs", True, detail)
    print("Dense MVS stage done.")
    return 0


def main() -> int:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=None)
    p.add_argument("--from-step", choices=["undistort", "stereo", "fusion"], default="undistort")
    args = p.parse_args()
    return run_mvs(args.config, args.from_step)


if __name__ == "__main__":
    raise SystemExit(main())
