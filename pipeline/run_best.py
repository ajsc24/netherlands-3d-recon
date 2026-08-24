"""Best-quality orchestrator: wall-friendly re-fusion, multi-mesh postprocess, OpenMVS, pick best."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from config_paths import load_config
from pick_best_mesh import pick_best
from postprocess_mesh import postprocess_dense_workspace
from prepare_360gs import export_dataset
from run_openmvs import run_openmvs


def refusion_and_post(cfg_path: Path) -> int:
    cfg = load_config(cfg_path)
    ref = cfg.get("refusion", {})
    if not ref.get("enabled", True):
        return 0

    work = Path(cfg["work_dir"])
    dense = work / "colmap" / "dense"
    if not (dense / "stereo" / "depth_maps").is_dir():
        print("No depth maps — skip re-fusion")
        return 0

    handoff_path = cfg_path.parent / "config_netherlands_handoff.yaml"
    base = load_config(handoff_path) if handoff_path.is_file() else cfg
    merged = {**base, **cfg}
    colmap_cfg = merged.setdefault("colmap", {})
    for k in (
        "fusion_max_reproj_error",
        "fusion_max_depth_error",
        "fusion_max_normal_error",
        "fusion_min_num_pixels",
        "fusion_check_num_images",
    ):
        if k in ref:
            colmap_cfg[k] = ref[k]

    tmp_cfg = dense.parent / "best_refusion_cfg.yaml"
    tmp_cfg.write_text(yaml.dump(merged, default_flow_style=False), encoding="utf-8")

    print("\n=== Step 1/4: Wall-friendly COLMAP re-fusion ===")
    py = Path(__file__).parent / ".venv" / "Scripts" / "python.exe"
    if not py.is_file():
        py = Path(sys.executable)
    r = subprocess.run(
        [str(py), str(Path(__file__).parent / "redo_dense.py"), "--config", str(tmp_cfg), "--from-step", "fusion"],
        check=False,
    )
    if r.returncode != 0:
        print("Re-fusion failed — continuing with existing fused.ply", file=sys.stderr)
        return 0

    fused = dense / "fused.ply"
    if not fused.is_file():
        return 0

    backup = dense / "fused_before_wall.ply"
    if not backup.is_file():
        shutil.copy2(fused, backup)

    print("\n=== Step 2/4: Wall-friendly mesh variants ===")
    post_cfg = cfg.get("postprocess", {})
    colmap_exe = colmap_cfg.get("colmap_exe")
    postprocess_dense_workspace(
        dense,
        post_cfg,
        colmap_exe,
        mesh_name="mesh_wall.ply",
        filtered_name="fused_wall_filtered.ply",
    )
    return 0


def convert_openmvs_obj(work: Path) -> None:
    mvs = work / "colmap" / "openmvs"
    if not mvs.is_dir():
        return
    try:
        import pymeshlab
    except ImportError:
        return
    for obj in sorted(mvs.glob("*_texture.obj")):
        ply = mvs / "mesh_openmvs.ply"
        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(str(obj))
        ms.save_current_mesh(str(ply))
        print(f"  converted {obj.name} -> {ply.name}")
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="Best-quality multi-tool mesh pipeline")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--skip-openmvs", action="store_true")
    parser.add_argument("--skip-refusion", action="store_true")
    parser.add_argument("--openmvs-only", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    cfg_path = args.config or (root / "config_netherlands_best.yaml")

    if not args.openmvs_only and not args.skip_refusion:
        refusion_and_post(cfg_path)
    elif args.skip_refusion:
        # Postprocess existing fused.ply without re-fusion (fast mesh variant).
        cfg = load_config(cfg_path)
        work = Path(cfg["work_dir"])
        dense = work / "colmap" / "dense"
        wall = dense / "mesh_wall.ply"
        if dense.joinpath("fused.ply").is_file() and not wall.is_file():
            print("\n=== Step 2/4: Mesh from existing fused.ply (no re-fusion) ===")
            colmap_exe = cfg.get("colmap", {}).get("colmap_exe")
            postprocess_dense_workspace(
                dense,
                cfg.get("postprocess", {}),
                colmap_exe,
                mesh_name="mesh_wall.ply",
                filtered_name="fused_wall_filtered.ply",
            )

    if not args.skip_openmvs:
        print("\n=== Step 3/4: OpenMVS dense + mesh + texture ===")
        code = run_openmvs(cfg_path)
        if code != 0:
            print("OpenMVS failed — continuing with COLMAP meshes only", file=sys.stderr)

    cfg = load_config(cfg_path)
    work = Path(cfg["work_dir"])
    convert_openmvs_obj(work)

    print("\n=== Step 4/4: Pick best mesh ===")
    dense = work / "colmap" / "dense"
    mvs = work / "colmap" / "openmvs"
    pick_best(dense, mvs if mvs.is_dir() else None)

    if cfg.get("gaussian_splat", {}).get("enabled", True) and not args.openmvs_only:
        print("\n=== Bonus: 360-GS dataset export ===")
        export_dataset(cfg_path)

    print("\n=== BEST PIPELINE DONE ===")
    print(f"  Primary mesh: {dense / 'mesh_best.ply'}")
    if (mvs / "scene_refine_texture.obj").is_file():
        print(f"  OpenMVS OBJ:  {mvs / 'scene_refine_texture.obj'}")
    gs_out = root / "exports" / "360gs_dataset"
    if gs_out.is_dir():
        print(f"  360-GS data:  {gs_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
