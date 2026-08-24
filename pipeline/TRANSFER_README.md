# Drone recon — Linux portable package

Self-contained folder to copy to a Linux machine and run the Insta360 → 3D mesh pipeline.

## What is in this folder

| Item | Purpose |
|------|---------|
| `*.py` | Full pipeline (extract, mask, dewarp, COLMAP) |
| `config.yaml` | Paths and settings (edit before run) |
| `requirements.txt` | Python dependencies |
| `install_linux.sh` | Install ffmpeg, COLMAP, Python venv |
| `run.sh` | Run full pipeline |
| `resume_colmap.sh` | Skip to COLMAP only |
| `input/` | Put your `.mp4` here as `video.mp4` |

**Not included** (too large — copy separately if needed):

- Your source video (copy into `input/video.mp4`)
- Partial `workspace/` from Windows (optional, to resume COLMAP)

## Quick start on Linux

```bash
# 1) Copy this entire folder to the Linux PC, e.g. ~/drone_recon_linux
cd ~/drone_recon_linux

# 2) Copy your video
cp /path/to/your_clip.mp4 input/video.mp4

# 3) Install (Ubuntu/Debian)
chmod +x install_linux.sh run.sh resume_colmap.sh
./install_linux.sh

# 4) Run (hours for 600 frames + COLMAP)
./run.sh
```

Resume after interrupt:

```bash
./run.sh --from-step colmap
# or only patch match onward if sparse model exists — see workspace/colmap/
```

## Outputs

- `workspace/images/` — frames for COLMAP  
- `workspace/colmap/dense/fused.ply` — point cloud  
- `workspace/colmap/dense/meshed-poisson.ply` — mesh  

Open in MeshLab or Blender.

## Requirements

- **OS:** Ubuntu 22.04+ or similar (Debian works with `apt`)
- **GPU:** NVIDIA + CUDA strongly recommended for COLMAP
- **RAM:** 16 GB+ recommended for 600 images
- **Disk:** ~20–50 GB free for workspace

### If apt COLMAP is too old

Build from https://colmap.github.io/install.html or use a newer binary, then set in `config.yaml`:

```yaml
colmap:
  colmap_exe: "/path/to/colmap"
```

COLMAP 4.x uses these flags (already set in `run_colmap.py`):

- `--FeatureExtraction.max_image_size`
- `--FeatureExtraction.use_gpu`
- `--FeatureMatching.use_gpu`

## Copy from Windows (optional resume)

To continue COLMAP on Linux without re-extracting frames:

1. Copy this folder **without** a huge `workspace/` first, OR copy only:
   - `workspace/images/`
   - `workspace/masks/`
   - `workspace/colmap/database.db` (if feature extract + match finished)
2. On Linux: `./install_linux.sh` then `./resume_colmap.sh`

## Zip on Windows before transfer

From PowerShell on the PC that has this folder:

```powershell
Compress-Archive -Path "C:\Users\aaron\Downloads\drone_recon_linux" -DestinationPath "C:\Users\aaron\Downloads\drone_recon_linux.zip"
```

Then `scp` or USB the `.zip` + your `.mp4` to Linux.

```bash
unzip drone_recon_linux.zip
cd drone_recon_linux
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `colmap not found` | Run `sudo apt install colmap` or set `colmap_exe` |
| `moov atom not found` | Video corrupt; repair in Insta360 Studio first |
| Mapper registers few images | Need more camera motion in the video |
| Patch match very slow | Normal; 600 views can take many hours |
