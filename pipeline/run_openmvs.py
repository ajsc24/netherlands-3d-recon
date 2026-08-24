"""OpenMVS dense mesh + texture from existing COLMAP undistorted workspace."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from config_paths import load_config


def exe(openmvs_dir: Path, name: str) -> str:
    path = openmvs_dir / f"{name}.exe"
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}")
    return str(path)


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True, env=env)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--from-step", choices=["import", "densify", "mesh", "refine", "texture"], default="import")
    args = parser.parse_args()
    return run_openmvs(args.config, args.from_step)


def ply_for_mvs(mvs_path: Path) -> Path:
    """OpenMVS 2.4 writes geometry to a sibling .ply; cameras stay in the input .mvs."""
    return mvs_path.with_suffix(".ply")


def run_openmvs(cfg_path: Path, from_step: str = "import") -> int:
    cfg = load_config(cfg_path)
    ocfg = cfg.get("openmvs", {})
    if not ocfg.get("enabled", True):
        print("openmvs.enabled is false — skipping")
        return 0

    root = Path(__file__).resolve().parent.parent
    work = Path(cfg["work_dir"])
    dense = work / "colmap" / "dense"
    mvs = work / "colmap" / "openmvs"
    mvs.mkdir(parents=True, exist_ok=True)

    openmvs_dir = Path(ocfg.get("openmvs_dir", "tools/openmvs"))
    if not openmvs_dir.is_absolute():
        openmvs_dir = (root / openmvs_dir).resolve()
    if not (openmvs_dir / "InterfaceCOLMAP.exe").is_file():
        print(f"OpenMVS not found at {openmvs_dir}. Run ..\\Install-OpenMVS.ps1", file=sys.stderr)
        return 1

    if not (dense / "images").is_dir() or not (dense / "sparse").is_dir():
        print(f"Missing COLMAP dense workspace: {dense}", file=sys.stderr)
        return 1

    env = os.environ.copy()
    env["PATH"] = str(openmvs_dir) + os.pathsep + env.get("PATH", "")

    scene = mvs / "scene.mvs"
    scene_dense = mvs / "scene_dense.mvs"
    scene_mesh = mvs / "scene_mesh.mvs"
    scene_refine = mvs / "scene_refine.mvs"

    steps = ["import", "densify", "mesh", "refine", "texture"]
    start = steps.index(from_step)

    if start <= steps.index("import"):
        print("\n=== OpenMVS: import COLMAP ===")
        fused = dense / "fused.ply"
        fused_vis = dense / "fused.ply.vis"
        fused_bak = dense / "fused.ply.openmvs_bak"
        vis_bak = dense / "fused.ply.vis.openmvs_bak"
        restored = False
        if ocfg.get("import_sparse_only") and fused.is_file():
            print("  (hiding fused.ply — import sparse model only; OpenMVS will densify)")
            if fused_bak.is_file():
                fused_bak.unlink()
            shutil.move(fused, fused_bak)
            if fused_vis.is_file():
                shutil.move(fused_vis, vis_bak)
            restored = True
        try:
            run(
                [
                    exe(openmvs_dir, "InterfaceCOLMAP"),
                    "--working-folder", str(mvs),
                    "-i", str(dense),
                    "-o", str(scene),
                    "--image-folder", str(dense / "images"),
                ],
                env=env,
            )
        finally:
            if restored:
                if fused_bak.is_file():
                    shutil.move(fused_bak, fused)
                if vis_bak.is_file():
                    shutil.move(vis_bak, fused_vis)

    if start <= steps.index("densify"):
        print("\n=== OpenMVS: densify (CPU/GPU — many hours on 2400+ images) ===")
        cmd = [
            exe(openmvs_dir, "DensifyPointCloud"),
            "--working-folder", str(mvs),
            "-i", str(scene),
            "-o", str(scene_dense),
            "--resolution-level", str(int(ocfg.get("resolution_level", 1))),
            "--number-views", str(int(ocfg.get("number_views", 10))),
            "--number-views-fuse", str(int(ocfg.get("number_views_fuse", 4))),
        ]
        run(cmd, env=env)

    if start <= steps.index("mesh"):
        print("\n=== OpenMVS: reconstruct mesh ===")
        run(
            [
                exe(openmvs_dir, "ReconstructMesh"),
                "--working-folder", str(mvs),
                "-i", str(scene_dense),
                "-o", str(scene_mesh),
            ],
            env=env,
        )

    scene_mesh_ply = mvs / "scene_mesh.ply"
    scene_refine_ply = mvs / "scene_refine.ply"
    texture_mesh_ply = scene_mesh_ply

    if start <= steps.index("refine") and ocfg.get("refine_mesh", True):
        if not scene_mesh_ply.is_file():
            print(f"Missing {scene_mesh_ply} — run reconstruct first", file=sys.stderr)
            return 1
        print("\n=== OpenMVS: refine mesh ===")
        try:
            run(
                [
                    exe(openmvs_dir, "RefineMesh"),
                    "--working-folder", str(mvs),
                    "-i", str(scene_dense),
                    "-m", str(scene_mesh_ply),
                    "-o", str(scene_refine),
                    "--resolution-level", str(int(ocfg.get("resolution_level", 1))),
                ],
                env=env,
            )
            if scene_refine_ply.is_file():
                texture_mesh_ply = scene_refine_ply
        except subprocess.CalledProcessError:
            print("  RefineMesh failed — using coarse mesh for texturing", file=sys.stderr)

    if start <= steps.index("texture") and ocfg.get("texture_mesh", True):
        if not scene_dense.is_file():
            print(f"Missing {scene_dense}", file=sys.stderr)
            return 1
        if not texture_mesh_ply.is_file():
            print(f"Missing mesh {texture_mesh_ply}", file=sys.stderr)
            return 1
        print("\n=== OpenMVS: texture mesh ===")
        tex_cmd = [
            exe(openmvs_dir, "TextureMesh"),
            "--working-folder", str(mvs),
            "-i", str(scene_dense),
            "-m", str(texture_mesh_ply),
            "-o", str(scene_refine),
            "--export-type", "obj",
        ]
        if ocfg.get("max_texture_size"):
            tex_cmd += ["--max-texture-size", str(int(ocfg["max_texture_size"]))]
        tex_res = int(ocfg.get("texture_resolution_level", 0))
        if tex_res > 0:
            tex_cmd += ["--resolution-level", str(tex_res)]
        dec = float(ocfg.get("decimate", 0))
        if 0 < dec < 1:
            tex_cmd += ["--decimate", str(dec)]
        run(tex_cmd, env=env)

    obj = mvs / "scene_refine_texture.obj"
    if not obj.is_file():
        obj = mvs / "scene_mesh_texture.obj"
    if not obj.is_file():
        obj = next(mvs.glob("*_texture.obj"), obj)
    print(f"\nOpenMVS done.\n  Project: {mvs}\n  Textured mesh: {obj}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
