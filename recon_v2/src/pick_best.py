"""Score mesh candidates and write mesh_best.ply + QUALITY_REPORT.md."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from paths import ensure_work_dirs, load_config, write_status

try:
    import pymeshlab
except ImportError:
    pymeshlab = None


def mesh_stats(path: Path) -> dict | None:
    if pymeshlab is None or not path.is_file() or path.stat().st_size < 1000:
        return None
    if path.stat().st_size > 400 * 1024 * 1024:
        print(f"  {path.name}: skipped (>400MB)")
        return {"path": str(path), "skipped": True, "reason": "too_large", "bytes": path.stat().st_size}
    try:
        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(str(path))
        m = ms.current_mesh()
        v = m.vertex_number()
        f = m.face_number()
        if v < 100 or f < 100:
            return None
        bbox = m.bounding_box()
        diag = (
            (bbox.max()[0] - bbox.min()[0]) ** 2
            + (bbox.max()[1] - bbox.min()[1]) ** 2
            + (bbox.max()[2] - bbox.min()[2]) ** 2
        ) ** 0.5
        return {
            "path": str(path),
            "name": path.name,
            "verts": v,
            "faces": f,
            "bbox_diag": float(diag),
            "bytes": path.stat().st_size,
        }
    except Exception as exc:
        print(f"  {path.name}: score failed ({exc})")
        return None


def score(s: dict) -> float:
    if s.get("skipped"):
        return -1.0
    return float(s["bbox_diag"]) * (float(s["faces"]) ** 0.5)


def pick_and_report(cfg_path: Path | None = None) -> int:
    cfg = load_config(cfg_path)
    work = ensure_work_dirs(cfg)
    dense = work / "colmap" / "dense"
    openmvs = work / "openmvs"

    candidates = [
        dense / "mesh_final.ply",
        dense / "mesh_wall.ply",
        dense / "mesh_strict.ply",
        dense / "mesh_final_colmap.ply",
        dense / "mesh_wall_colmap.ply",
        openmvs / "scene_mesh.ply",
        openmvs / "scene_refine.ply",
    ]
    # Convert textured OBJ to PLY for scoring if needed
    if pymeshlab and openmvs.is_dir():
        for obj in list(openmvs.glob("*_texture.obj")) + list(openmvs.glob("scene_refine.obj")):
            ply = openmvs / "mesh_openmvs_textured.ply"
            if obj.is_file() and not ply.is_file():
                try:
                    ms = pymeshlab.MeshSet()
                    ms.load_new_mesh(str(obj))
                    ms.save_current_mesh(str(ply))
                    candidates.append(ply)
                except Exception:
                    pass
            elif ply.is_file():
                candidates.append(ply)

    ranked: list[tuple[float, dict]] = []
    all_stats: list[dict] = []
    for p in candidates:
        st = mesh_stats(p)
        if not st:
            continue
        all_stats.append(st)
        if not st.get("skipped"):
            sc = score(st)
            ranked.append((sc, st))
            print(f"  {st['name']}: {st['verts']:,} verts, diag={st['bbox_diag']:.2f}, score={sc:.0f}")

    best_path = None
    if ranked:
        ranked.sort(key=lambda x: x[0], reverse=True)
        best = ranked[0][1]
        best_path = Path(best["path"])
        out = dense / "mesh_best.ply"
        shutil.copy2(best_path, out)
        print(f"\nBest mesh: {best_path.name} -> {out}")
    else:
        print("No scorable meshes found", file=sys.stderr)

    # QUALITY_REPORT.md
    sparse_qa = {}
    sq = work / "qa" / "sparse_qa.json"
    if sq.is_file():
        sparse_qa = json.loads(sq.read_text(encoding="utf-8"))

    status = {}
    sp = work / "status.json"
    if sp.is_file():
        status = json.loads(sp.read_text(encoding="utf-8"))

    textured = None
    for cand in [
        openmvs / "scene_refine.obj",
        openmvs / "scene_refine_texture.obj",
    ]:
        if cand.is_file():
            textured = cand
            break
    if textured is None and openmvs.is_dir():
        textured = next(openmvs.glob("*.obj"), None)

    gs_dir = Path(cfg.get("gaussian_splat", {}).get("output_dir", "exports_v2/360gs_dataset"))
    report_path = work / "QUALITY_REPORT.md"
    lines = [
        "# Reconstruction Quality Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Sparse SfM",
        "",
        f"- Registered: {sparse_qa.get('registered_images', '?')} / {sparse_qa.get('total_images', '?')}",
        f"- Ratio: {sparse_qa.get('registered_ratio', '?')}",
        f"- Mean track length: {sparse_qa.get('mean_track_length', '?')}",
        f"- Points: {sparse_qa.get('points', '?')}",
        "",
        "## Mesh candidates",
        "",
        "| Mesh | Verts | Faces | BBox diag | Score |",
        "|------|------:|------:|----------:|------:|",
    ]
    for sc, st in ranked:
        lines.append(
            f"| {st['name']} | {st['verts']:,} | {st['faces']:,} | {st['bbox_diag']:.2f} | {sc:.0f} |"
        )
    lines += [
        "",
        f"**Selected best:** `{best_path.name if best_path else 'none'}` → `colmap/dense/mesh_best.ply`",
        "",
        "## Textured mesh",
        "",
        f"- OpenMVS OBJ: `{textured}`" if textured else "- OpenMVS OBJ: not found",
        "",
        "## 360 Gaussian Splat",
        "",
        f"- Dataset: `{gs_dir}`",
        "- Flat painted walls will still have holes in classical MVS meshes;",
        "  train 360-GS on the exported equirect keyframes for visual completeness.",
        "",
        "## Stage status",
        "",
        "```json",
        json.dumps(status.get("stages", {}), indent=2),
        "```",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {report_path}")

    write_status(
        work,
        "pick",
        best_path is not None,
        {
            "best": str(best_path) if best_path else None,
            "candidates": len(ranked),
            "report": str(report_path),
            "textured_obj": str(textured) if textured else None,
        },
    )
    return 0 if best_path else 1


def main() -> int:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=None)
    args = p.parse_args()
    if pymeshlab is None:
        print("pymeshlab required", file=sys.stderr)
        return 1
    return pick_and_report(args.config)


if __name__ == "__main__":
    raise SystemExit(main())
