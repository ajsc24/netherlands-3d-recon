"""Re-run dense fusion + mesh post-process using existing depth maps."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from config_paths import load_config
from postprocess_mesh import postprocess_dense_workspace
from run_colmap import colmap_has_cuda, pick_best_sparse_model, resolve_colmap, run


def main() -> int:
    parser = argparse.ArgumentParser(description="Redo COLMAP fusion + Open3D mesh")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--from-step",
        choices=["undistort", "fusion", "postprocess"],
        default="fusion",
        help="undistort: rebuild dense workspace from best sparse; fusion: reuse depth maps",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    colmap_cfg = cfg.get("colmap", {})
    colmap = resolve_colmap(colmap_cfg)
    if not colmap:
        print("COLMAP not found", file=sys.stderr)
        return 1

    work = Path(cfg["work_dir"])
    images = work / "images"
    sparse = work / "colmap" / "sparse"
    dense = work / "colmap" / "dense"
    model_dir = pick_best_sparse_model(colmap, sparse)
    if model_dir is None:
        print("No sparse model found", file=sys.stderr)
        return 2

    steps = ["undistort", "fusion", "postprocess"]
    start = steps.index(args.from_step)

    if start <= steps.index("undistort"):
        if dense.is_dir():
            print(f"Clearing old dense workspace: {dense}")
            shutil.rmtree(dense)
        dense.mkdir(parents=True, exist_ok=True)
        run(
            [
                colmap,
                "image_undistorter",
                "--image_path",
                str(images),
                "--input_path",
                str(model_dir),
                "--output_path",
                str(dense),
                "--output_type",
                "COLMAP",
            ]
        )
        if not colmap_has_cuda(colmap):
            print("COLMAP CUDA not available for patch_match", file=sys.stderr)
            return 3
        patch_match = [
            colmap,
            "patch_match_stereo",
            "--workspace_path",
            str(dense),
            "--workspace_format",
            "COLMAP",
            "--PatchMatchStereo.geom_consistency",
            "true" if colmap_cfg.get("dense_geom_consistency", False) else "false",
        ]
        if "dense_max_image_size" in colmap_cfg:
            patch_match += [
                "--PatchMatchStereo.max_image_size",
                str(int(colmap_cfg["dense_max_image_size"])),
            ]
        if "dense_gpu_index" in colmap_cfg:
            patch_match += ["--PatchMatchStereo.gpu_index", str(int(colmap_cfg["dense_gpu_index"]))]
        print("=== Patch match stereo (many hours) ===")
        run(patch_match)

    if start <= steps.index("fusion"):
        fusion = [
            colmap,
            "stereo_fusion",
            "--workspace_path",
            str(dense),
            "--workspace_format",
            "COLMAP",
            "--input_type",
            "geometric",
            "--output_path",
            str(dense / "fused.ply"),
            "--StereoFusion.num_threads",
            str(int(colmap_cfg.get("fusion_num_threads", -1))),
        ]
        defaults = {
            "fusion_max_reproj_error": 1.5,
            "fusion_max_depth_error": 0.008,
            "fusion_max_normal_error": 8,
            "fusion_min_num_pixels": 5,
            "fusion_check_num_images": 35,
        }
        for key, val in defaults.items():
            fusion += [
                {
                    "fusion_max_reproj_error": "--StereoFusion.max_reproj_error",
                    "fusion_max_depth_error": "--StereoFusion.max_depth_error",
                    "fusion_max_normal_error": "--StereoFusion.max_normal_error",
                    "fusion_min_num_pixels": "--StereoFusion.min_num_pixels",
                    "fusion_check_num_images": "--StereoFusion.check_num_images",
                }[key],
                str(colmap_cfg.get(key, val)),
            ]
        if colmap_cfg.get("fusion_use_cache", True):
            fusion += ["--StereoFusion.use_cache", "1"]
        if "fusion_cache_size" in colmap_cfg:
            fusion += ["--StereoFusion.cache_size", str(int(colmap_cfg["fusion_cache_size"]))]
        print("=== Stereo fusion ===")
        run(fusion)

    if start <= steps.index("postprocess"):
        outputs = postprocess_dense_workspace(dense, cfg.get("postprocess", {}), colmap)
        print("\n=== Deliverables ===")
        for name, path in outputs.items():
            print(f"  {name}: {path}")
        print("\nOpen in MeshLab: mesh_final.ply")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
