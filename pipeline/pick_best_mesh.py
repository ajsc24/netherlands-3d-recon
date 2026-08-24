"""Score candidate meshes and copy the best to mesh_best.ply."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

try:
    import pymeshlab
except ImportError:
    pymeshlab = None


def mesh_stats(path: Path) -> dict | None:
    if pymeshlab is None or not path.is_file() or path.stat().st_size < 1000:
        return None
    if path.stat().st_size > 400 * 1024 * 1024:
        print(f"  {path.name}: skipped (>{400}MB — too large to score quickly)")
        return None
    try:
        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(str(path))
        m = ms.current_mesh()
        v = m.vertex_number()
        f = m.face_number()
        if v < 100 or f < 100:
            return None
        bbox = m.bounding_box()
        diag = ((bbox.max()[0] - bbox.min()[0]) ** 2 +
                (bbox.max()[1] - bbox.min()[1]) ** 2 +
                (bbox.max()[2] - bbox.min()[2]) ** 2) ** 0.5
        return {"path": path, "verts": v, "faces": f, "bbox_diag": float(diag)}
    except Exception:
        return None


def score(s: dict) -> float:
    # Prefer large spatial extent and rich geometry.
    return s["bbox_diag"] * (s["faces"] ** 0.5)


def pick_best(dense: Path, openmvs: Path | None = None) -> Path | None:
    candidates = [
        dense / "mesh_final.ply",
        dense / "mesh_wall.ply",
        dense / "meshed-poisson_colmap.ply",
    ]
    if openmvs:
        candidates += [
            openmvs / "scene_refine_texture.ply",
            openmvs / "scene_mesh.ply",
            openmvs / "mesh_openmvs.ply",
        ]
        for obj in openmvs.glob("*_texture.obj"):
            ply = openmvs / "mesh_openmvs.ply"
            if pymeshlab and not ply.is_file():
                ms = pymeshlab.MeshSet()
                ms.load_new_mesh(str(obj))
                ms.save_current_mesh(str(ply))
                candidates.append(ply)

    ranked: list[tuple[float, dict]] = []
    for p in candidates:
        st = mesh_stats(p)
        if st:
            ranked.append((score(st), st))
            print(f"  {p.name}: {st['verts']:,} verts, diag={st['bbox_diag']:.2f}m, score={score(st):.0f}")

    if not ranked:
        print("No valid candidate meshes found.")
        return None

    ranked.sort(key=lambda x: x[0], reverse=True)
    best = ranked[0][1]["path"]
    out = dense / "mesh_best.ply"
    shutil.copy2(best, out)
    print(f"\nBest mesh: {best.name} -> {out}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dense", type=Path, required=True)
    parser.add_argument("--openmvs", type=Path, default=None)
    args = parser.parse_args()
    result = pick_best(args.dense, args.openmvs)
    return 0 if result else 1


if __name__ == "__main__":
    raise SystemExit(main())
