# Accuracy-first 3D reconstruction (recon_v2)

Clean rebuild of the Netherlands bottom-floor pipeline from the Insta360 X2 video.

## Deliverables

| Output | Path |
|--------|------|
| Best untextured mesh | `workspace_v2/colmap/dense/mesh_best.ply` |
| Textured mesh | `workspace_v2/openmvs/scene_refine.obj` (+ JPG atlases) |
| Quality report | `workspace_v2/QUALITY_REPORT.md` |
| 360-GS keyframes | `exports_v2/360gs_dataset/` |

## Setup (once)

From the **project root** (`gpu_handoff_netherlands`):

```powershell
# COLMAP + OpenMVS if not already installed
.\Install-Windows.ps1
.\Install-OpenMVS.ps1

# recon_v2 Python venv
.\recon_v2\scripts\Setup.ps1
```

Legacy workspaces were archived by:

```powershell
.\recon_v2\scripts\Archive-Legacy.ps1
```

## Run (full accuracy pipeline — many hours / days)

```powershell
.\recon_v2\scripts\Run-Accurate.ps1
```

Resume from a stage:

```powershell
.\recon_v2\scripts\Run-Accurate.ps1 -FromStep sfm
.\recon_v2\scripts\Run-Accurate.ps1 -FromStep mvs -ToStep pick
```

Stages: `extract` → `keyframes` → `mask` → `dewarp` → `sfm` → `mvs` → `mesh_post` → `openmvs` → `pick` → `export_360gs`

## Design notes

- Hard QA gates stop the run before dense if sparse registration is below 85%.
- Dual fusion: strict + wall-friendly clouds; primary mesh uses wall-friendly coverage.
- OpenMVS 2.4 uses `-i scene_dense.mvs -m scene_mesh.ply` (no fake `scene_mesh.mvs`).
- Flat painted walls will still have holes in classical MVS; use the 360-GS export for visual fill-in.
