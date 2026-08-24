"""PyMeshLab post-process: outlier cleanup + Screened Poisson mesh."""

from __future__ import annotations

import re
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np

from paths import ensure_work_dirs, load_config, write_status

try:
    import pymeshlab
except ImportError:
    pymeshlab = None


def _cfg(post_cfg: dict, key: str, default):
    return post_cfg.get(key, default)


def read_colmap_fused(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    data = path.read_bytes()
    m = re.search(br"end_header\r?\n", data)
    if not m:
        raise ValueError(f"Invalid PLY: {path}")
    header = data[: m.start()].decode()
    rest = data[m.end() :]
    n = int(next(l.split()[2] for l in header.splitlines() if l.startswith("element vertex")))
    has_normals = "property float nx" in header
    pts = np.empty((n, 3), dtype=np.float64)
    norms = np.zeros((n, 3), dtype=np.float64)
    cols = np.empty((n, 3), dtype=np.uint8)
    off = 0
    for i in range(n):
        x, y, z = struct.unpack_from("<fff", rest, off)
        off += 12
        if has_normals:
            nx, ny, nz = struct.unpack_from("<fff", rest, off)
            off += 12
            norms[i] = (nx, ny, nz)
        r, g, b = struct.unpack_from("<BBB", rest, off)
        off += 3
        pts[i] = (x, y, z)
        cols[i] = (r, g, b)
    return pts, norms, cols


def write_colmap_fused(path: Path, pts: np.ndarray, norms: np.ndarray, cols: np.ndarray) -> None:
    with path.open("wb") as f:
        f.write(
            (
                f"ply\nformat binary_little_endian 1.0\n"
                f"element vertex {len(pts)}\n"
                f"property float x\nproperty float y\nproperty float z\n"
                f"property float nx\nproperty float ny\nproperty float nz\n"
                f"property uchar red\nproperty uchar green\nproperty uchar blue\n"
                f"end_header\n"
            ).encode()
        )
        for i in range(len(pts)):
            x, y, z = pts[i]
            nx, ny, nz = norms[i]
            r, g, b = cols[i]
            f.write(
                struct.pack(
                    "<ffffffBBB",
                    float(x), float(y), float(z),
                    float(nx), float(ny), float(nz),
                    int(r), int(g), int(b),
                )
            )


def numpy_prefilter(pts, norms, cols, post_cfg):
    finite = np.isfinite(pts).all(axis=1)
    max_coord = float(_cfg(post_cfg, "max_coord", 120.0))
    bounded = np.abs(pts).max(axis=1) < max_coord
    mask = finite & bounded
    pts, norms, cols = pts[mask], norms[mask], cols[mask]
    print(f"  numeric filter: {mask.sum():,} / {len(finite):,} kept")

    core_pct = _cfg(post_cfg, "core_percentile", 99.8)
    if core_pct and len(pts) > 0:
        med = np.median(pts, axis=0)
        dist = np.linalg.norm(pts - med, axis=1)
        cutoff = np.percentile(dist, float(core_pct))
        core = dist <= cutoff
        pts, norms, cols = pts[core], norms[core], cols[core]
        span = pts.max(0) - pts.min(0)
        print(f"  core p{core_pct}: {len(pts):,} pts, span {span.round(2)}")
    return pts, norms, cols


def pymeshlab_mesh_from_cloud(work_ply: Path, post_cfg: dict):
    if pymeshlab is None:
        raise RuntimeError("pymeshlab not installed")
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(str(work_ply))
    print(f"  PyMeshLab loaded: {ms.current_mesh().vertex_number():,} vertices")
    ms.compute_selection_point_cloud_outliers(
        knearest=int(_cfg(post_cfg, "outlier_k", 48)),
        propthreshold=float(_cfg(post_cfg, "outlier_threshold", 0.85)),
    )
    ms.meshing_remove_selected_vertices()
    print(f"  after outlier removal: {ms.current_mesh().vertex_number():,} vertices")
    ms.compute_normal_for_point_clouds(
        k=int(_cfg(post_cfg, "normal_k", 30)),
        smoothiter=int(_cfg(post_cfg, "normal_smooth", 3)),
        flipflag=False,
    )
    ms.generate_surface_reconstruction_screened_poisson(
        depth=int(_cfg(post_cfg, "poisson_depth", 12)),
        fulldepth=int(_cfg(post_cfg, "poisson_fulldepth", 7)),
        samplespernode=float(_cfg(post_cfg, "poisson_samples_per_node", 2.0)),
        pointweight=float(_cfg(post_cfg, "poisson_point_weight", 3.0)),
        iters=int(_cfg(post_cfg, "poisson_iters", 10)),
        preclean=bool(_cfg(post_cfg, "poisson_preclean", True)),
        threads=int(_cfg(post_cfg, "poisson_threads", 20)),
    )
    print(
        f"  Poisson mesh: {ms.current_mesh().vertex_number():,} verts, "
        f"{ms.current_mesh().face_number():,} faces"
    )
    min_pct = float(_cfg(post_cfg, "min_component_percent", 1.0))
    if min_pct > 0:
        ms.meshing_remove_connected_component_by_diameter(
            mincomponentdiag=pymeshlab.PercentageValue(min_pct)
        )
    ms.meshing_remove_duplicate_vertices()
    ms.meshing_remove_unreferenced_vertices()
    return ms


def run_colmap_poisson(colmap_exe: str, fused: Path, out_mesh: Path, depth: int, trim: float) -> bool:
    cmd = [
        colmap_exe, "poisson_mesher",
        "--input_path", str(fused),
        "--output_path", str(out_mesh),
        "--PoissonMeshing.depth", str(depth),
        "--PoissonMeshing.trim", str(trim),
    ]
    print("+", " ".join(cmd), flush=True)
    try:
        subprocess.run(cmd, check=True)
        return out_mesh.is_file() and out_mesh.stat().st_size > 1000
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"  COLMAP Poisson failed: {exc}", file=sys.stderr)
        return False


def postprocess_cloud(
    dense: Path,
    fused_name: str,
    mesh_name: str,
    filtered_name: str,
    post_cfg: dict,
    colmap_exe: str | None,
) -> dict[str, Path]:
    fused = dense / fused_name
    if not fused.is_file():
        raise FileNotFoundError(f"Missing {fused}")
    print(f"\n=== Post-process {fused_name} -> {mesh_name} ===")
    pts, norms, cols = read_colmap_fused(fused)
    print(f"  raw fused: {len(pts):,} points")
    pts, norms, cols = numpy_prefilter(pts, norms, cols, post_cfg)
    max_pts = int(_cfg(post_cfg, "max_poisson_points", 4_000_000))
    if len(pts) > max_pts:
        step = max(1, len(pts) // max_pts)
        idx = np.arange(0, len(pts), step)
        pts, norms, cols = pts[idx], norms[idx], cols[idx]
        print(f"  subsampled for Poisson: {len(pts):,} (step={step})")
    filtered = dense / filtered_name
    write_colmap_fused(filtered, pts, norms, cols)
    ms = pymeshlab_mesh_from_cloud(filtered, post_cfg)
    mesh = dense / mesh_name
    ms.save_current_mesh(str(mesh))
    print(f"  wrote {mesh}")
    outputs = {"point_cloud": filtered, "mesh": mesh}
    if colmap_exe and _cfg(post_cfg, "colmap_poisson_fallback", True):
        colmap_mesh = dense / mesh_name.replace(".ply", "_colmap.ply")
        if run_colmap_poisson(
            colmap_exe,
            filtered,
            colmap_mesh,
            depth=int(_cfg(post_cfg, "colmap_poisson_depth", 12)),
            trim=float(_cfg(post_cfg, "colmap_poisson_trim", 6.0)),
        ):
            outputs["mesh_colmap"] = colmap_mesh
    return outputs


def run_mesh_post(cfg_path: Path | None = None) -> int:
    if pymeshlab is None:
        print("pymeshlab required", file=sys.stderr)
        return 1
    cfg = load_config(cfg_path)
    work = ensure_work_dirs(cfg)
    post_cfg = cfg.get("postprocess", {})
    if not post_cfg.get("enabled", True):
        write_status(work, "mesh_post", True, {"skipped": True})
        return 0

    dense = work / "colmap" / "dense"
    colmap_exe = cfg.get("colmap", {}).get("colmap_exe")
    results = {}
    try:
        if (dense / "fused_wall.ply").is_file():
            results["wall"] = postprocess_cloud(
                dense, "fused_wall.ply", "mesh_wall.ply",
                "fused_wall_filtered.ply", post_cfg, colmap_exe,
            )
        if (dense / "fused_strict.ply").is_file():
            results["strict"] = postprocess_cloud(
                dense, "fused_strict.ply", "mesh_strict.ply",
                "fused_strict_filtered.ply", post_cfg, colmap_exe,
            )
        # Primary mesh_final from fused.ply
        if (dense / "fused.ply").is_file():
            results["final"] = postprocess_cloud(
                dense, "fused.ply", "mesh_final.ply",
                "fused_filtered.ply", post_cfg, colmap_exe,
            )
    except Exception as exc:
        print(f"Mesh post failed: {exc}", file=sys.stderr)
        write_status(work, "mesh_post", False, {"error": str(exc)})
        return 1

    write_status(
        work,
        "mesh_post",
        True,
        {k: {nk: str(nv) for nk, nv in v.items()} for k, v in results.items()},
    )
    return 0


def main() -> int:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=None)
    args = p.parse_args()
    return run_mesh_post(args.config)


if __name__ == "__main__":
    raise SystemExit(main())
