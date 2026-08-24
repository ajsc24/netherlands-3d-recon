"""COLMAP structure-from-motion (feature extract, match, mapper) + sparse QA gate."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from paths import ensure_work_dirs, load_config, write_status
from qa import QAError, gate_sparse, write_qa_json


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def resolve_colmap(colmap_cfg: dict) -> str | None:
    colmap = colmap_cfg.get("colmap_exe", "colmap")
    path = Path(colmap)
    if path.is_file():
        return str(path.resolve())
    return shutil.which(colmap)


def _pick_option(help_text: str, candidates: list[str]) -> str:
    for name in candidates:
        if f"--{name} " in help_text or f"--{name} arg" in help_text or f"--{name}\n" in help_text:
            return name
    return candidates[-1]


def colmap_cli_options(colmap: str) -> dict[str, str]:
    extract_help = ""
    match_help = ""
    try:
        er = subprocess.run([colmap, "feature_extractor", "-h"], capture_output=True, text=True)
        extract_help = (er.stdout or "") + (er.stderr or "")
        mr = subprocess.run([colmap, "sequential_matcher", "-h"], capture_output=True, text=True)
        match_help = (mr.stdout or "") + (mr.stderr or "")
    except OSError:
        pass
    return {
        "max_image_size": _pick_option(
            extract_help,
            ["SiftExtraction.max_image_size", "FeatureExtraction.max_image_size"],
        ),
        "max_num_features": _pick_option(
            extract_help,
            ["SiftExtraction.max_num_features", "FeatureExtraction.max_num_features"],
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


def has_masks(masks_dir: Path, images_dir: Path) -> bool:
    if not masks_dir.is_dir():
        return False
    masks = list(masks_dir.glob("*.png"))
    images = list(images_dir.glob("*.jpg"))
    return len(masks) > 0 and len(masks) >= len(images) // 2


def pick_best_sparse_model(colmap: str, sparse: Path) -> Path | None:
    best: Path | None = None
    best_images = -1
    if not sparse.is_dir():
        return None
    for sub in sorted(sparse.iterdir(), key=lambda p: p.name):
        if not sub.is_dir() or not (sub / "images.bin").is_file():
            continue
        text = subprocess.run(
            [colmap, "model_analyzer", "--path", str(sub)],
            capture_output=True,
            text=True,
            check=False,
        )
        out = (text.stdout or "") + (text.stderr or "")
        for line in out.splitlines():
            if "Registered images:" in line:
                count = int(line.rsplit(":", 1)[-1].strip())
                if count > best_images:
                    best_images = count
                    best = sub
                break
    if best:
        print(f"Selected sparse/{best.name} ({best_images} registered images)")
    return best


def run_sfm(cfg_path: Path | None = None, from_step: str = "extract") -> int:
    cfg = load_config(cfg_path)
    work = ensure_work_dirs(cfg)
    colmap_cfg = cfg.get("colmap", {})
    colmap = resolve_colmap(colmap_cfg)
    if not colmap:
        print("COLMAP not found. Run project Install-Windows.ps1", file=sys.stderr)
        return 1

    images = work / "images"
    masks = work / "masks"
    database = work / "colmap" / "database.db"
    sparse = work / "colmap" / "sparse"
    sparse.mkdir(parents=True, exist_ok=True)

    if not list(images.glob("*.jpg")):
        print(f"No images in {images}", file=sys.stderr)
        return 1

    gpu_flag = "1" if colmap_cfg.get("use_gpu", True) else "0"
    max_size = int(colmap_cfg.get("max_image_size", 2000))
    max_feat = int(colmap_cfg.get("max_num_features", 8192))
    single_camera = "1" if colmap_cfg.get("single_camera", True) else "0"
    use_masks = colmap_cfg.get("use_masks_in_colmap", True) and has_masks(masks, images)
    cli = colmap_cli_options(colmap)

    steps = ["extract", "match", "mapper"]
    if from_step not in steps:
        print(f"Unknown from_step: {from_step}", file=sys.stderr)
        return 1
    start = steps.index(from_step)

    if start <= steps.index("extract"):
        if database.is_file():
            database.unlink()
        # Clear prior sparse models so mapper starts clean
        if sparse.is_dir():
            for child in list(sparse.iterdir()):
                if child.is_dir():
                    shutil.rmtree(child)
        cmd = [
            colmap,
            "feature_extractor",
            "--database_path", str(database),
            "--image_path", str(images),
            "--ImageReader.single_camera", single_camera,
            f"--{cli['max_image_size']}", str(max_size),
            f"--{cli['max_num_features']}", str(max_feat),
            f"--{cli['extract_gpu']}", gpu_flag,
        ]
        if use_masks:
            cmd += ["--ImageReader.mask_path", str(masks)]
            print(f"Using masks from {masks}")
        run(cmd)

    if start <= steps.index("match"):
        matcher = colmap_cfg.get("matcher", "pairs")
        if matcher == "pairs":
            from build_match_pairs import write_pairs_file

            write_pairs_file(cfg_path)
            pairs_path = work / "colmap" / "match_pairs.txt"
            if not pairs_path.is_file():
                print(f"Missing pairs file {pairs_path}", file=sys.stderr)
                return 1
            run([
                colmap,
                "matches_importer",
                "--database_path", str(database),
                "--match_list_path", str(pairs_path),
                "--match_type", "pairs",
                f"--{cli['match_gpu']}", gpu_flag,
                "--TwoViewGeometry.min_num_inliers",
                str(int(colmap_cfg.get("min_num_matches", 8))),
            ])
        elif matcher == "sequential":
            run([
                colmap,
                "sequential_matcher",
                "--database_path", str(database),
                f"--{cli['match_gpu']}", gpu_flag,
                "--SequentialMatching.overlap",
                str(int(colmap_cfg.get("sequential_overlap", 80))),
                "--SequentialMatching.quadratic_overlap", "1",
            ])
        else:
            run([
                colmap,
                "exhaustive_matcher",
                "--database_path", str(database),
                f"--{cli['match_gpu']}", gpu_flag,
            ])

    if start <= steps.index("mapper"):
        # Fresh sparse output
        for child in list(sparse.iterdir()):
            if child.is_dir():
                shutil.rmtree(child)
        mapper_cmd = [
            colmap,
            "mapper",
            "--database_path", str(database),
            "--image_path", str(images),
            "--output_path", str(sparse),
            "--Mapper.init_min_num_inliers",
            str(int(colmap_cfg.get("init_min_num_inliers", 15))),
            "--Mapper.abs_pose_min_num_inliers",
            str(int(colmap_cfg.get("abs_pose_min_num_inliers", 10))),
            "--Mapper.min_num_matches",
            str(int(colmap_cfg.get("min_num_matches", 8))),
            "--Mapper.num_threads", "-1",
        ]
        if colmap_cfg.get("ba_use_gpu", True) and gpu_flag == "1":
            mapper_cmd += ["--Mapper.ba_use_gpu", "1"]
        run(mapper_cmd)

    model_dir = pick_best_sparse_model(colmap, sparse)
    if model_dir is None:
        write_status(work, "sfm", False, {"error": "no sparse model"})
        print("Mapper produced no usable sparse model", file=sys.stderr)
        return 2

    # Persist selected model path for dense stage
    selected = work / "colmap" / "selected_sparse.txt"
    selected.write_text(str(model_dir), encoding="utf-8")

    qa_cfg = cfg.get("qa", {})
    try:
        report = gate_sparse(
            colmap,
            model_dir,
            images,
            min_ratio=float(qa_cfg.get("min_registered_ratio", 0.85)),
            min_track=float(qa_cfg.get("min_mean_track_length", 3.0)),
        )
    except QAError as exc:
        print(f"SPARSE QA FAILED: {exc}", file=sys.stderr)
        write_qa_json(work / "qa" / "sparse_qa.json", {"ok": False, "error": str(exc)})
        write_status(work, "sfm", False, {"error": str(exc)})
        return 3

    write_qa_json(work / "qa" / "sparse_qa.json", report)
    print(
        f"Sparse QA OK: {report['registered_images']}/{report['total_images']} "
        f"({report['registered_ratio']:.1%}), track={report['mean_track_length']:.2f}"
    )
    write_status(work, "sfm", True, report)
    return 0


def main() -> int:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=None)
    p.add_argument("--from-step", choices=["extract", "match", "mapper"], default="extract")
    args = p.parse_args()
    return run_sfm(args.config, args.from_step)


if __name__ == "__main__":
    raise SystemExit(main())
