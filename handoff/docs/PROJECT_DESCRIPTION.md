# Netherlands Interior 3D Model — Windows GPU

**Goal:** Dense 3D mesh of the bottom floor of a house from an Insta360 X2 360° walkthrough, with drone and operator masked out.

**Platform:** Native Windows + NVIDIA GPU (tested for RTX 3050 8 GB). No WSL, no Linux, no Docker required.

### Best-quality run (OpenMVS + multi-mesh)

```powershell
.\Run-Best.ps1
```

Uses existing COLMAP sparse/dense, then: wall-friendly re-fusion, OpenMVS textured mesh, picks best -> `mesh_best.ply`. Log: `workspace_netherlands\best_pipeline.log`

Optional immersive 360 view: `.\Install-360GS.ps1` after Run-Best exports keyframes.

---

## What you need

| Item | Requirement |
|------|-------------|
| OS | Windows 10/11 |
| GPU | NVIDIA, 8+ GB VRAM |
| RAM | 16 GB+ |
| Disk | **100+ GB free** on the drive you run from |
| Software | Python 3.10+, PowerShell 5.1+ |

Verify GPU:

```powershell
nvidia-smi
```

---

## Quick start (3 commands)

Open **PowerShell** in this folder (`gpu_handoff_netherlands`):

```powershell
# 1) One-time setup (~250 MB COLMAP download + Python packages)
.\Install-Windows.ps1

# 2) Confirm video is here (already included in this package):
#    input\NetherlandsBottomLevel.mp4

# 3) Run full pipeline (many hours)
.\QUICKSTART_GPU.ps1
```

That is it. **Do not use `chmod`** — that is Linux only.

---

## Video

| Property | Value |
|----------|--------|
| Path | `input\NetherlandsBottomLevel.mp4` |
| Camera | Insta360 X2 |
| Format | HEVC, **5760×2880** equirect (2:1) |
| Duration | ~2:37 |
| Content | Interior walkthrough, camera held under drone |

---

## What the pipeline does

```
NetherlandsBottomLevel.mp4 (5760×2880 equirect)
    → extract frames (2 fps, ~314 frames)
    → mask bottom 42% (drone + hands at nadir)
    → dewarp to 8 perspective views per frame (~2500 images)
    → COLMAP sparse (structure-from-motion, GPU)
    → COLMAP dense on GPU (patch_match_stereo → fusion → Poisson mesh)
```

---

## Deliverables

| File | Description |
|------|-------------|
| `workspace_netherlands\colmap\dense\fused.ply` | Dense point cloud |
| `workspace_netherlands\colmap\dense\meshed-poisson.ply` | **Final mesh** |

Open in [MeshLab](https://www.meshlab.net/) (press **R** to reset view) or Blender.

---

## Resume / partial runs

```powershell
# Skip video check, restart from frame extraction
.\QUICKSTART_GPU.ps1 -FromStep extract

# Only re-run masks (after editing mask line in config)
.\QUICKSTART_GPU.ps1 -FromStep mask

# Sparse COLMAP only (if frames already exist)
.\QUICKSTART_GPU.ps1 -FromStep colmap

# Dense mesh only (if sparse model already exists)
.\pipeline\Run-Dense.ps1
# or
.\QUICKSTART_GPU.ps1 -DenseOnly

# Resume COLMAP from matching step
.\pipeline\Resume-Colmap.ps1 -FromStep match
```

---

## Configuration

Edit `config_netherlands_handoff.yaml`:

```yaml
video_path: "input/NetherlandsBottomLevel.mp4"
work_dir: "workspace_netherlands"
projection: equirect
views_per_frame: 8
drone_mask:
  polygon: bottom 42% of frame  # y >= 0.58
colmap:
  colmap_exe: "tools/bin/colmap.exe"
  use_gpu: true
  dense_mode: cuda
```

If drone/hands still appear in the mesh, lower the mask line (`0.58` → `0.52`) and re-run from mask:

```powershell
.\QUICKSTART_GPU.ps1 -FromStep mask
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `chmod` not recognized | You are on Windows — use `.\QUICKSTART_GPU.ps1` instead |
| `Running scripts is disabled` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| COLMAP not found | Run `.\Install-Windows.ps1` again |
| `Dense stereo requires CUDA` | Reinstall COLMAP via Install script (CUDA build, not nocuda) |
| ffmpeg not found | Reopen PowerShell after Install, or `winget install Gyan.FFmpeg` |
| Out of disk | Need ~100 GB under `workspace_netherlands\` |
| Sparse mesh looks tiny | Normal until dense step finishes |
| 8 GB VRAM OOM during dense | Close other GPU apps; reduce `max_image_size` to 1200 in config |

---

## File map

```
gpu_handoff_netherlands/
├── PROJECT_DESCRIPTION.md          ← this file
├── Install-Windows.ps1             ← one-time setup
├── QUICKSTART_GPU.ps1              ← run full pipeline
├── config_netherlands_handoff.yaml
├── input/
│   └── NetherlandsBottomLevel.mp4
├── tools/
│   └── bin/colmap.exe              ← created by Install-Windows.ps1
└── pipeline/
    ├── pipeline.py
    ├── Run-Dense.ps1               ← GPU dense only
    ├── Resume-Colmap.ps1
    └── …
```

---

## Linux (optional)

Original bash scripts (`QUICKSTART_GPU.sh`, Docker dense) are still in `pipeline/` if you later move to Ubuntu.
