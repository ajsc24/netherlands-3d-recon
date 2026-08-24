# Setup status (this machine)

Updated 2026-06-05 after full COLMAP run.

## Done

| Step | Status |
|------|--------|
| Video at `input/video.mp4` | Yes (from `VID_20260529_195535_10_017.mp4`, 452 MB) |
| `config.yaml` `use_gpu` | Set to `false` (no NVIDIA driver detected here) |
| Frame extraction (2 fps) | **215** frames in `workspace/frames_raw/` |
| Drone masks + COLMAP images | **215** pairs in `workspace/images/` and `workspace/masks/` |
| Workspace size so far | ~142 MB |

## Video note

Your clip is **1920×1080**, **~108 seconds** (~1.8 min), not the README’s 2560×1440 / ~11 min sample. At 2 fps you get 215 frames (under the 600 cap). Quality depends on camera motion and overlap; a longer/higher-res source would help if you have it.

## COLMAP result (2026-06-05)

| Output | Path | Notes |
|--------|------|-------|
| Sparse point cloud | `workspace/colmap/dense/fused.ply` | **74 points** (13/215 images registered) |
| Poisson mesh | `workspace/colmap/dense/meshed-poisson.ply` | Generated from sparse cloud (~1.3 KB) |

**Why the model is tiny:**

1. **Short clip, little motion** — ~108 s at 1920×1080; mapper only aligned **13** frames.
2. **No CUDA** — `patch_match_stereo` fails with *"Dense stereo reconstruction requires CUDA"*, so no full dense cloud.
3. **CPU COLMAP 3.7** — feature/match/mapper ran on CPU; a zombie mapper from an earlier run could not be killed (permission denied) and competed for `sparse/`.

For a usable environment mesh you need: **flight/orbit footage** (or the full ~11 min source), **NVIDIA + CUDA COLMAP**, and ideally the longer `2560×1440` video from the README.

## Next steps (GPU Linux box)

On a normal Ubuntu 22.04+ machine with sudo, NVIDIA + CUDA, and ~50+ GB free disk:

```bash
cd /path/to/drone_recon_linux
chmod +x install_linux.sh run.sh resume_colmap.sh run_colmap_docker.sh

# If workspace/ is already copied from this machine, skip full pipeline:
./install_linux.sh   # apt: ffmpeg, colmap; creates .venv

# Edit config if you have CUDA:
#   colmap.use_gpu: true

./resume_colmap.sh
# or: ./run.sh --from-step colmap
```

**Docker alternative** (if apt colmap is unavailable but Docker works):

```bash
./run_colmap_docker.sh
```

**Deliverable when finished:**

- `workspace/colmap/dense/fused.ply`
- `workspace/colmap/dense/meshed-poisson.ply`

Expect **many hours** for `patch_match_stereo` on 215 images (longer on CPU).
