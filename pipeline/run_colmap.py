"""Run COLMAP SfM + MVS with optional image masks (drone excluded)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from config_paths import load_config


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def has_masks(masks_dir: Path, images_dir: Path) -> bool:
    if not masks_dir.is_dir():
        return False
    masks = list(masks_dir.glob("*.png"))
    return len(masks) > 0 and len(masks) >= len(list(images_dir.glob("*.jpg"))) // 2


def resolve_colmap(colmap_cfg: dict) -> str | None:
    colmap = colmap_cfg.get("colmap_exe", "colmap")
    colmap_path = Path(colmap)
    if colmap_path.is_file():
        return str(colmap_path.resolve())
    return shutil.which(colmap)


def _pick_option(help_text: str, candidates: list[str]) -> str:
    for name in candidates:
        if f"--{name} " in help_text or f"--{name} arg" in help_text:
            return name
    return candidates[-1]


def colmap_cli_options(colmap: str) -> dict[str, str]:
    """Resolve COLMAP CLI option names (they differ across 3.x / 3.13 / 4.x builds)."""
    extract_help = ""
    match_help = ""
    try:
        extract_run = subprocess.run(
            [colmap, "feature_extractor", "-h"],
            capture_output=True,
            text=True,
            check=False,
        )
        extract_help = extract_run.stdout + extract_run.stderr
        match_run = subprocess.run(
            [colmap, "sequential_matcher", "-h"],
            capture_output=True,
            text=True,
            check=False,
        )
        match_help = match_run.stdout + match_run.stderr
    except OSError:
        pass

    return {
        "max_image_size": _pick_option(
            extract_help,
            ["SiftExtraction.max_image_size", "FeatureExtraction.max_image_size"],
        ),
        "extract_gpu": _pick_option(
            extract_help,
            ["FeatureExtraction.use_gpu", "SiftExtraction.use_gpu"],
        ),
        "match_gpu": _pick_option(
            match_help,
            ["FeatureMatching.use_gpu", "SiftMatching.use_gpu"],
        ),
    }


def pick_best_sparse_model(colmap: str, sparse: Path) -> Path | None:
    """COLMAP mapper can write multiple sparse/N folders; pick the largest reconstruction."""
    best: Path | None = None
    best_images = -1
    for sub in sorted(sparse.iterdir(), key=lambda p: p.name):
        if not sub.is_dir() or not (sub / "images.bin").is_file():
            continue
        try:
            result = subprocess.run(
                [colmap, "model_analyzer", "--path", str(sub)],
                capture_output=True,
                text=True,
                check=False,
            )
            text = result.stdout + result.stderr
        except OSError:
            continue
        for line in text.splitlines():
            if "Registered images:" in line:
                count = int(line.rsplit(":", 1)[-1].strip())
                if count > best_images:
                    best_images = count
                    best = sub
                break
    if best:
        print(f"Selected sparse/{best.name} ({best_images} registered images)")
    return best


def colmap_has_cuda(colmap: str) -> bool:
    try:
        run = subprocess.run([colmap, "-h"], capture_output=True, text=True, check=False)
        out = run.stdout + run.stderr
    except OSError:
        return False
    return "without CUDA" not in out


def export_sparse_ply(colmap: str, model_dir: Path, ply_path: Path) -> None:
    run(
        [
            colmap,
            "model_converter",
            "--input_path",
            str(model_dir),
            "--output_path",
            str(ply_path),
            "--output_type",
            "PLY",
        ]
    )


def ply_add_normals(src: Path, dst: Path) -> int:
    import struct

    data = src.read_bytes()
    header, rest = data.split(b"end_header\n", 1)
    lines = header.decode().splitlines()
    vertex_count = int(next(line.split()[2] for line in lines if line.startswith("element vertex")))
    off = 0
    with dst.open("w", encoding="utf-8") as f:
        f.write("ply\nformat ascii 1.0\n")
        f.write(f"element vertex {vertex_count}\n")
        for prop in "x y z nx ny nz red green blue".split():
            f.write(f"property float {prop}\n")
        f.write("end_header\n")
        for _ in range(vertex_count):
            x, y, z = struct.unpack_from("<fff", rest, off)
            off += 12
            r, g, b = struct.unpack_from("<BBB", rest, off)
            off += 3
            f.write(f"{x} {y} {z} 0 0 1 {r} {g} {b}\n")
    return vertex_count


def run_sparse_poisson_mesh(colmap: str, model_dir: Path, dense: Path) -> None:
    fused = dense / "fused.ply"
    fused_normals = dense / "fused-normals.ply"
    meshed = dense / "meshed-poisson.ply"
    export_sparse_ply(colmap, model_dir, fused)
    count = ply_add_normals(fused, fused_normals)
    print(f"Sparse point cloud: {fused} ({count} points)")
    print("CUDA dense stereo unavailable — building Poisson mesh from sparse cloud (CPU).")
    run(
        [
            colmap,
            "poisson_mesher",
            "--input_path",
            str(fused_normals),
            "--output_path",
            str(meshed),
        ]
    )


def main(cfg_path: Path | None = None, from_step: str = "extract") -> int:
    root = Path(__file__).resolve().parent
    cfg = load_config(cfg_path or (root / "config.yaml"))
    colmap_cfg = cfg.get("colmap", {})
    if not colmap_cfg.get("enabled", True):
        print("colmap.enabled is false — skipping")
        return 0

    colmap = resolve_colmap(colmap_cfg)
    if not colmap:
        print(
            "COLMAP not found. Windows: run ..\\Install-Windows.ps1\n"
            "Linux: sudo apt install colmap\n"
            "Or set colmap.colmap_exe in config.yaml.",
            file=sys.stderr,
        )
        return 1

    work = Path(cfg["work_dir"])
    images = work / "images"
    masks = work / "masks"
    database = work / "colmap" / "database.db"
    sparse = work / "colmap" / "sparse"
    dense = work / "colmap" / "dense"
    database.parent.mkdir(parents=True, exist_ok=True)
    sparse.mkdir(parents=True, exist_ok=True)
    dense.mkdir(parents=True, exist_ok=True)

    if not sorted(images.glob("*.jpg")):
        print(f"No images in {images}", file=sys.stderr)
        return 1

    gpu = colmap_cfg.get("use_gpu", True)
    gpu_flag = "1" if gpu else "0"
    max_size = int(colmap_cfg.get("max_image_size", 1600))
    single_camera = "1" if colmap_cfg.get("single_camera", True) else "0"
    dm = cfg.get("drone_mask", {})
    use_masks = (
        colmap_cfg.get("use_masks_in_colmap", dm.get("enabled", True))
        and has_masks(masks, images)
    )
    cli = colmap_cli_options(colmap)

    steps = ["extract", "match", "mapper", "dense"]
    if from_step not in steps:
        print(f"Unknown from_step: {from_step}", file=sys.stderr)
        return 1
    start = steps.index(from_step)

    reader = [
        colmap,
        "feature_extractor",
        "--database_path",
        str(database),
        "--image_path",
        str(images),
        "--ImageReader.single_camera",
        single_camera,
        f"--{cli['max_image_size']}",
        str(max_size),
        f"--{cli['extract_gpu']}",
        gpu_flag,
    ]
    if use_masks:
        reader += ["--ImageReader.mask_path", str(masks)]
    if "extract_num_threads" in colmap_cfg:
        reader += [
            "--FeatureExtraction.num_threads",
            str(int(colmap_cfg["extract_num_threads"])),
        ]
    if start <= steps.index("extract"):
        run(reader)

    matcher = colmap_cfg.get("matcher", "sequential")
    if start <= steps.index("match"):
        if matcher == "sequential":
            run(
            [
                colmap,
                "sequential_matcher",
                "--database_path",
                str(database),
                f"--{cli['match_gpu']}",
                gpu_flag,
                "--SequentialMatching.overlap",
                str(int(colmap_cfg.get("sequential_overlap", 30))),
            ]
            )
        else:
            run(
                [
                    colmap,
                    "exhaustive_matcher",
                    "--database_path",
                    str(database),
                    f"--{cli['match_gpu']}",
                    gpu_flag,
                ]
            )

    if start <= steps.index("mapper"):
        mapper_cmd = [
            colmap,
            "mapper",
            "--database_path",
            str(database),
            "--image_path",
            str(images),
            "--output_path",
            str(sparse),
            "--Mapper.init_min_num_inliers",
            str(int(colmap_cfg.get("init_min_num_inliers", 30))),
            "--Mapper.abs_pose_min_num_inliers",
            str(int(colmap_cfg.get("abs_pose_min_num_inliers", 15))),
            "--Mapper.min_num_matches",
            str(int(colmap_cfg.get("min_num_matches", 10))),
        ]
        if "mapper_num_threads" in colmap_cfg:
            mapper_cmd += [
                "--Mapper.num_threads",
                str(int(colmap_cfg["mapper_num_threads"])),
            ]
        if colmap_cfg.get("ba_use_gpu", False) and gpu:
            mapper_cmd += ["--Mapper.ba_use_gpu", "1"]
            if "ba_gpu_index" in colmap_cfg:
                mapper_cmd += [
                    "--Mapper.ba_gpu_index",
                    str(int(colmap_cfg["ba_gpu_index"])),
                ]
        if "mapper_num_threads" not in colmap_cfg:
            mapper_cmd += ["--Mapper.num_threads", "-1"]
        if "ba_global_max_num_iterations" in colmap_cfg:
            mapper_cmd += [
                "--Mapper.ba_global_max_num_iterations",
                str(int(colmap_cfg["ba_global_max_num_iterations"])),
            ]
        run(mapper_cmd)

    model_dir = pick_best_sparse_model(colmap, sparse)
    if model_dir is None:
        print("Mapper produced no usable sparse model — check overlap and masks.", file=sys.stderr)
        return 2

    if start > steps.index("dense"):
        print(f"\nDone.\n  Point cloud: {dense / 'fused.ply'}\n  Mesh:        {dense / 'meshed-poisson.ply'}")
        return 0

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

    dense_mode = colmap_cfg.get("dense_mode", "auto")
    use_cuda_dense = dense_mode == "cuda" or (dense_mode == "auto" and colmap_has_cuda(colmap))

    if use_cuda_dense:
        try:
            patch_match = [
                colmap,
                "patch_match_stereo",
                "--workspace_path",
                str(dense),
                "--workspace_format",
                "COLMAP",
                "--PatchMatchStereo.geom_consistency",
                "true" if colmap_cfg.get("dense_geom_consistency", True) else "false",
            ]
            if "dense_max_image_size" in colmap_cfg:
                patch_match += [
                    "--PatchMatchStereo.max_image_size",
                    str(int(colmap_cfg["dense_max_image_size"])),
                ]
            if "dense_gpu_index" in colmap_cfg:
                patch_match += [
                    "--PatchMatchStereo.gpu_index",
                    str(int(colmap_cfg["dense_gpu_index"])),
                ]
            if "dense_cache_size" in colmap_cfg:
                patch_match += [
                    "--PatchMatchStereo.cache_size",
                    str(int(colmap_cfg["dense_cache_size"])),
                ]
            if "dense_num_iterations" in colmap_cfg:
                patch_match += [
                    "--PatchMatchStereo.num_iterations",
                    str(int(colmap_cfg["dense_num_iterations"])),
                ]
            run(patch_match)
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
            ]
            if "fusion_num_threads" in colmap_cfg:
                fusion += [
                    "--StereoFusion.num_threads",
                    str(int(colmap_cfg["fusion_num_threads"])),
                ]
            elif "mapper_num_threads" in colmap_cfg:
                fusion += [
                    "--StereoFusion.num_threads",
                    str(int(colmap_cfg["mapper_num_threads"])),
                ]
            else:
                fusion += ["--StereoFusion.num_threads", "-1"]
            if "fusion_cache_size" in colmap_cfg:
                fusion += [
                    "--StereoFusion.cache_size",
                    str(int(colmap_cfg["fusion_cache_size"])),
                ]
            if colmap_cfg.get("fusion_use_cache", False):
                fusion += ["--StereoFusion.use_cache", "1"]
            if "fusion_max_image_size" in colmap_cfg:
                fusion += [
                    "--StereoFusion.max_image_size",
                    str(int(colmap_cfg["fusion_max_image_size"])),
                ]
            for key, flag in [
                ("fusion_max_reproj_error", "--StereoFusion.max_reproj_error"),
                ("fusion_max_depth_error", "--StereoFusion.max_depth_error"),
                ("fusion_max_normal_error", "--StereoFusion.max_normal_error"),
                ("fusion_min_num_pixels", "--StereoFusion.min_num_pixels"),
                ("fusion_check_num_images", "--StereoFusion.check_num_images"),
            ]:
                if key in colmap_cfg:
                    fusion += [flag, str(colmap_cfg[key])]
            run(fusion)
            post_cfg = cfg.get("postprocess", {"enabled": True})
            if post_cfg.get("enabled", True):
                from postprocess_mesh import postprocess_dense_workspace

                postprocess_dense_workspace(dense, post_cfg, colmap)
            else:
                run(
                    [
                        colmap,
                        "poisson_mesher",
                        "--input_path",
                        str(dense / "fused.ply"),
                        "--output_path",
                        str(dense / "meshed-poisson.ply"),
                    ]
                )
        except subprocess.CalledProcessError as exc:
            print(
                f"\nDense stereo failed ({exc.cmd[1] if len(exc.cmd) > 1 else exc.cmd}). "
                "Falling back to sparse Poisson mesh.",
                file=sys.stderr,
            )
            run_sparse_poisson_mesh(colmap, model_dir, dense)
    else:
        run_sparse_poisson_mesh(colmap, model_dir, dense)

    mesh_final = dense / "mesh_final.ply"
    mesh_line = mesh_final if mesh_final.is_file() else dense / "meshed-poisson.ply"
    filtered = dense / "fused_filtered.ply"
    cloud_line = filtered if filtered.is_file() else dense / "fused.ply"
    print(f"\nDone.\n  Point cloud: {cloud_line}\n  Mesh:        {mesh_line}")
    return 0


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=None)
    p.add_argument(
        "--from-step",
        choices=["extract", "match", "mapper", "dense"],
        default="extract",
    )
    args = p.parse_args()
    raise SystemExit(main(args.config, args.from_step))
