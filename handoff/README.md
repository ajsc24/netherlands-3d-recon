# Netherlands 3D Reconstruction — Handoff Package

**Created:** June 2026  
**Project root:** `gpu_handoff_netherlands/` (parent of this folder)  
**Goal:** Dense textured 3D mesh of a Netherlands house bottom floor from an Insta360 X2 walkthrough video.

This `handoff/` folder is a **self-contained snapshot** of code, configs, scripts, and documentation for the next person (or machine) continuing the work.

---

## Start here

| Document | Contents |
|----------|----------|
| [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) | What was built, final deliverables, reconstruction stats |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | End-to-end pipeline diagram and tool chain |
| [docs/SETUP_AND_RUN.md](docs/SETUP_AND_RUN.md) | Install, run, resume commands |
| [docs/CONFIG_GUIDE.md](docs/CONFIG_GUIDE.md) | Every YAML config explained |
| [docs/CODE_ANNOTATIONS.md](docs/CODE_ANNOTATIONS.md) | File-by-file annotated walkthrough of all Python |
| [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) | Bugs fixed, limitations, OpenMVS quirks |

---

## Folder layout

```
handoff/
├── README.md                 ← you are here
├── docs/                     ← human-readable documentation
├── code/
│   ├── pipeline/             ← annotated Python modules (mirror of ../pipeline/)
│   ├── scripts/              ← PowerShell entry points
│   └── configs/              ← YAML configs for each pipeline variant
```

**Not copied here (too large):**
- `input/NetherlandsBottomLevel.mp4` — source video (~GB)
- `workspace_netherlands/` — reconstruction outputs (fused.ply, meshes, depth maps)
- `tools/bin/colmap.exe` — download via `Install-Windows.ps1`
- `tools/openmvs/` — download via `Install-OpenMVS.ps1`
- `pipeline/.venv/` — Python virtualenv

Run pipelines from the **project root** (`gpu_handoff_netherlands/`), not from `handoff/code/`. The copies here are for reading and handoff; live scripts live one level up.

---

## Quick commands (from project root)

```powershell
# One-time setup
.\Install-Windows.ps1
.\Install-OpenMVS.ps1

# Full pipeline from video (many hours)
.\QUICKSTART_GPU.ps1

# Best-quality on existing COLMAP data (OpenMVS + mesh pick)
.\Run-Best.ps1

# Resume after crash (skip re-fusion)
.\Run-Resume-Best.ps1
```

## Public showcase website + online code

```powershell
# Publish to GitHub (public repo + website anyone can visit)
.\handoff\scripts\Publish-Online.ps1

# Add 3D model to the site after mesh is ready
.\handoff\scripts\Export-WebModel.ps1
git add handoff/showcase/assets/model.ply && git commit -m "Add web model" && git push
```

See **[docs/ONLINE_HOSTING.md](docs/ONLINE_HOSTING.md)** for full instructions.

Local preview: `cd handoff\showcase && python -m http.server 8080`

---

## Best deliverables (as of handoff)

| File | Description |
|------|-------------|
| `workspace_netherlands\colmap\dense\mesh_best.ply` | Auto-picked best untextured mesh (copy of `mesh_final.ply`) |
| `workspace_netherlands\colmap\dense\mesh_final.ply` | COLMAP Poisson mesh, ~2.8M verts, best room coverage |
| `workspace_netherlands\colmap\openmvs\scene_refine.obj` | **Textured** OpenMVS mesh (~413k verts after decimation) |
| `workspace_netherlands\colmap\openmvs\scene_refine_material_*_map_Kd.jpg` | 4096px texture atlases |

Open textured mesh in **MeshLab** (import OBJ + MTL; textures load automatically).

---

## Hardware used

- Windows 11, RTX 3050 8 GB, i7-13700F, 32 GB RAM
- COLMAP 3.13 CUDA build
- OpenMVS 2.4.0
- Python 3.13 venv with PyMeshLab

---

## Contact / context

Interior walkthrough filmed on Insta360 X2 (5760×2880 equirect, ~2:37). Camera held under a drone; bottom ~42% of each frame is masked to exclude drone body and operator hands before photogrammetry.
