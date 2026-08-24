# Configuration Guide

All paths in YAML are **relative to the project root** (`gpu_handoff_netherlands/`). `config_paths.py` resolves them to absolute paths at load time.

---

## config_netherlands_handoff.yaml — Full production run

Primary config for the complete pipeline from video.

```yaml
video_path: "input/NetherlandsBottomLevel.mp4"   # Source Insta360 walkthrough
work_dir: "workspace_netherlands"                 # All outputs go here

extract_fps: 2.0          # ~314 frames from 2:37 video
max_frames: 320           # Cap extraction count
views_per_frame: 8        # Equirect → 8 perspective crops per frame → ~2500 images
perspective_fov_deg: 90   # Each crop FOV
perspective_size: 1024    # Crop resolution

drone_mask:
  polygon:                # Normalized [x,y] 0–1; bottom 42% of frame
    - [0.0, 0.58]         # COLMAP: white=valid, black=ignored
  use_masks_in_colmap: true

colmap:
  max_image_size: 1600    # SIFT extraction limit
  dense_max_image_size: 1200   # Stereo resolution (VRAM tradeoff)
  fusion_*:               # Strict fusion defaults for first pass
```

---

## config_netherlands_best.yaml — OpenMVS + wall mesh

Used by `Run-Best.ps1`. Does **not** re-extract frames; operates on existing COLMAP workspace.

```yaml
refusion:
  fusion_max_reproj_error: 3.0    # Looser than handoff → more wall points
  fusion_min_num_pixels: 3        # Accept thinner surfaces

openmvs:
  resolution_level: 1             # Image scale for densify (0=full, higher=smaller)
  refine_mesh: false              # Skip on 8 GB GPU
  texture_resolution_level: 2     # Downscale images for texturing
  decimate: 0.5                   # Halve faces before TextureMesh
  max_texture_size: 4096          # Atlas size (8192 OOM'd)
  import_sparse_only: true        # Don't load 22M fused.ply into OpenMVS

postprocess:
  max_poisson_points: 3000000     # Subsample before Poisson
  poisson_depth: 12               # Higher = more detail, more RAM
```

---

## config_netherlands_pro.yaml / pro1view.yaml

Keyframe-based reduced image count for faster iteration.

- `keyframes.enabled: true` — uses `select_keyframes.py` output
- `pro`: 4 views per keyframe (~45 keyframes)
- `pro1view`: 1 view per keyframe, longer baseline

---

## config_netherlands_fast.yaml / maxgpu.yaml

Tuning variants for speed vs quality experiments (see files in `code/configs/`).

---

## Key COLMAP fusion parameters

| Parameter | Strict (handoff) | Loose (best/refusion) | Effect |
|-----------|------------------|----------------------|--------|
| `fusion_max_reproj_error` | 1.5 | 3.0 | More points on walls |
| `fusion_max_depth_error` | 0.008 | 0.02 | Thicker depth consistency |
| `fusion_min_num_pixels` | 5 | 3 | Smaller patches accepted |

---

## OpenMVS resolution_level

| Level | Meaning |
|-------|---------|
| 0 | Full resolution images |
| 1 | Half resolution (densify default) |
| 2 | Quarter (texture default in best config) |

Higher = faster, less detail, less VRAM.
