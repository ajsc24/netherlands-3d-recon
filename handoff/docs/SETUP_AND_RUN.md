# Setup & Run Guide

## Prerequisites

- Windows 10/11, NVIDIA GPU 8+ GB VRAM, 16+ GB RAM, **100+ GB free disk**
- Python 3.10+ (project uses 3.13)
- PowerShell 5.1+

```powershell
nvidia-smi   # verify GPU
```

If scripts are blocked:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

---

## One-time install (from project root)

```powershell
cd C:\Users\oskar\Downloads\gpu_handoff_netherlands

.\Install-Windows.ps1      # COLMAP CUDA + ffmpeg + Python venv + PyMeshLab
.\Install-OpenMVS.ps1      # OpenMVS 2.4 binaries → tools/openmvs/
.\Install-360GS.ps1        # optional: 360 Gaussian Splatting
```

---

## Pipeline entry points

### Full pipeline from video (~many hours)

```powershell
.\QUICKSTART_GPU.ps1
```

Steps: video check → extract → mask → dewarp → COLMAP (sparse + dense + mesh).

Resume from a step:
```powershell
.\QUICKSTART_GPU.ps1 -FromStep extract   # check|extract|mask|dewarp|colmap
.\QUICKSTART_GPU.ps1 -DenseOnly            # dense only if sparse exists
```

### Best-quality on existing COLMAP data

```powershell
.\Run-Best.ps1
```

Runs: wall re-fusion → mesh_wall.ply → OpenMVS → pick best → 360-GS export.

Flags:
```powershell
.\Run-Best.ps1 -SkipRefusion    # skip COLMAP re-fusion
.\Run-Best.ps1 -SkipOpenMVS     # COLMAP meshes only
.\Run-Best.ps1 -OpenMVSOnly     # OpenMVS + pick only
```

### Resume after crash

```powershell
.\Run-Resume-Best.ps1
# equivalent: python pipeline\run_best.py --config config_netherlands_best.yaml --skip-refusion
```

### Re-run with fixed masks

```powershell
.\Run-Handoff-Remask.ps1
```

### Pro keyframe pipeline (fewer images)

```powershell
.\Run-ProQuality.ps1
.\Run-ProQuality.ps1 -Config config_netherlands_pro1view.yaml
```

### Dense only

```powershell
.\pipeline\Run-Dense.ps1
```

### OpenMVS texture only (after densify + reconstruct)

```powershell
pipeline\.venv\Scripts\python.exe pipeline\run_openmvs.py --config config_netherlands_best.yaml --from-step texture
```

---

## Monitor long runs

```powershell
Get-Content workspace_netherlands\best_resume.log -Tail 20 -Wait
Get-Content workspace_netherlands\best_pipeline.log -Tail 20 -Wait
```

OpenMVS logs: `workspace_netherlands\colmap\openmvs\TextureMesh-*.log`

---

## View results

| Output | Viewer |
|--------|--------|
| `mesh_best.ply`, `mesh_final.ply` | MeshLab (R = reset view), Blender |
| `scene_refine.obj` + `.mtl` + `.jpg` | MeshLab — File → Import Mesh |

---

## Environment

| Component | Path |
|-----------|------|
| Python venv | `pipeline\.venv\` |
| COLMAP | `tools\bin\colmap.exe` |
| OpenMVS | `tools\openmvs\*.exe` |
| Work data | `workspace_netherlands\` |
| Source video | `input\NetherlandsBottomLevel.mp4` |
