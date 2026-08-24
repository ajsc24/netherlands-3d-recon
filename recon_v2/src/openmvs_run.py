"""OpenMVS densify + mesh + texture (OpenMVS 2.4 correct .mvs/.ply handling)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from paths import ensure_work_dirs, load_config, write_status


def exe(openmvs_dir: Path, name: str) -> str:
    path = openmvs_dir / f"{name}.exe"
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}")
    return str(path)


def run(cmd: list[str], env: dict | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, env=env)


def run_openmvs(cfg_path: Path | None = None, from_step: str = "import") -> int:
    cfg = load_config(cfg_path)
    ocfg = cfg.get("openmvs", {})
    if not ocfg.get("enabled", True):
        print("openmvs.enabled is false — skipping")
        return 0

    work = ensure_work_dirs(cfg)
    # Prefer workspace_v2/openmvs; also support colmap/openmvs layout
    dense = work / "colmap" / "dense"
    mvs = work / "openmvs"
    mvs.mkdir(parents=True, exist_ok=True)

    openmvs_dir = Path(ocfg.get("openmvs_dir", "tools/openmvs"))
    if not (openmvs_dir / "InterfaceCOLMAP.exe").is_file():
        print(f"OpenMVS not found at {openmvs_dir}. Run Install-OpenMVS.ps1", file=sys.stderr)
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
    scene_mesh_ply = mvs / "scene_mesh.ply"

    steps = ["import", "densify", "mesh", "refine", "texture"]
    start = steps.index(from_step)

    if start <= steps.index("import"):
        print("\n=== OpenMVS: import COLMAP ===", flush=True)
        fused = dense / "fused.ply"
        fused_vis = dense / "fused.ply.vis"
        fused_bak = dense / "fused.ply.openmvs_bak"
        vis_bak = dense / "fused.ply.vis.openmvs_bak"
        restored = False
        if ocfg.get("import_sparse_only") and fused.is_file():
            print("  hiding fused.ply for sparse-only import")
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
        print("\n=== OpenMVS: densify ===", flush=True)
        run(
            [
                exe(openmvs_dir, "DensifyPointCloud"),
                "--working-folder", str(mvs),
                "-i", str(scene),
                "-o", str(scene_dense),
                "--resolution-level", str(int(ocfg.get("resolution_level", 1))),
                "--number-views", str(int(ocfg.get("number_views", 10))),
                "--number-views-fuse", str(int(ocfg.get("number_views_fuse", 4))),
            ],
            env=env,
        )

    if start <= steps.index("mesh"):
        print("\n=== OpenMVS: reconstruct mesh ===", flush=True)
        run(
            [
                exe(openmvs_dir, "ReconstructMesh"),
                "--working-folder", str(mvs),
                "-i", str(scene_dense),
                "-o", str(scene_mesh),
            ],
            env=env,
        )

    texture_mesh_ply = scene_mesh_ply
    if start <= steps.index("refine") and ocfg.get("refine_mesh", False):
        if not scene_mesh_ply.is_file():
            print(f"Missing {scene_mesh_ply}", file=sys.stderr)
            return 1
        print("\n=== OpenMVS: refine mesh ===", flush=True)
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
            refine_ply = mvs / "scene_refine.ply"
            if refine_ply.is_file():
                texture_mesh_ply = refine_ply
        except subprocess.CalledProcessError:
            print("  RefineMesh failed — using ReconstructMesh ply", file=sys.stderr)

    if start <= steps.index("texture") and ocfg.get("texture_mesh", True):
        if not scene_dense.is_file() or not texture_mesh_ply.is_file():
            print("Missing scene_dense.mvs or mesh ply for texturing", file=sys.stderr)
            return 1
        print("\n=== OpenMVS: texture mesh ===", flush=True)
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
        # CRITICAL: use float — int(0.5) == 0 would disable decimation
        dec = float(ocfg.get("decimate", 0))
        if 0 < dec < 1:
            tex_cmd += ["--decimate", str(dec)]
        run(tex_cmd, env=env)

    obj = mvs / "scene_refine.obj"
    if not obj.is_file():
        obj = next(mvs.glob("*_texture.obj"), None) or next(mvs.glob("*.obj"), None)
    detail = {"mvs_dir": str(mvs), "obj": str(obj) if obj else None, "mesh_ply": str(scene_mesh_ply)}
    write_status(work, "openmvs", True, detail)
    print(f"OpenMVS done. Textured: {obj}")
    return 0


def main() -> int:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=None)
    p.add_argument(
        "--from-step",
        choices=["import", "densify", "mesh", "refine", "texture"],
        default="import",
    )
    args = p.parse_args()
    return run_openmvs(args.config, args.from_step)


if __name__ == "__main__":
    raise SystemExit(main())
