# Annotated Code Walkthrough

Every Python module in `code/pipeline/` with purpose, inputs/outputs, and key logic explained.

Paths below refer to `handoff/code/pipeline/` (mirror of live `pipeline/`).

---

## config_paths.py

**Purpose:** Load YAML configs and resolve relative paths to absolute paths from the project root.

```python
def load_config(cfg_path):
    # Resolves video_path, work_dir, colmap_exe, openmvs_dir relative to config file parent
```

**Why it exists:** Configs use portable relative paths (`tools/bin/colmap.exe`) so the project folder can move between drives.

**Helpers:**
- `frame_source_dir()` — `frames_raw/` or `frames_key/` if keyframes enabled
- `masks_equirect_dir()` — `workspace/masks_equirect/`

---

## pipeline.py

**Purpose:** Main 5-step orchestrator for full video → mesh pipeline.

| Step | Module | What it does |
|------|--------|-------------|
| 1 check | repair_video.py | ffprobe validation |
| 2 extract | extract_frames.py | ffmpeg → `frames_raw/frame_*.jpg` |
| 3 mask | mask_drone.py | Drone polygon masks on equirect |
| 4 dewarp | dewarp_views.py | 8 perspective views + mask copies |
| 5 colmap | run_colmap.py | Full COLMAP sparse + dense |

**CLI:** `--from-step extract` skips earlier steps for resume.

---

## extract_frames.py

**Purpose:** Extract JPEG frames from walkthrough video at configured FPS.

- Reads `extract_fps`, `max_frames` from config
- Output: `{work_dir}/frames_raw/frame_000001.jpg`, ...
- Uses ffmpeg subprocess

---

## mask_drone.py

**Purpose:** Create COLMAP-compatible masks excluding drone body and operator hands.

**Critical logic:**
```python
# COLMAP: 0 = ignore, >0 = valid
mask = np.full((h, w), 255, dtype=np.uint8)   # scene = valid (white)
cv2.fillPoly(mask, [pts], 0)                   # drone polygon = ignore (black)
```

**Input:** `frames_raw/` equirect JPEGs  
**Output:** `masks_equirect/frame_*.png`  
**Config:** `drone_mask.polygon` — normalized coordinates, bottom 42% default

---

## dewarp_views.py

**Purpose:** Convert each equirect frame into N perspective pinhole images for COLMAP.

- Samples viewing directions around the sphere (`views_per_frame`, typically 8)
- Writes to `colmap/images/` with naming like `frame_000001_view_00.jpg`
- Copies/resizes masks to `colmap/masks/` matching image names
- COLMAP `single_camera: true` because all crops share identical intrinsics

---

## run_colmap.py

**Purpose:** Full COLMAP reconstruction — sparse SfM through dense mesh.

**Major stages:**
1. `feature_extractor` — SIFT on GPU
2. `sequential_matcher` — match consecutive frames (walkthrough order)
3. `mapper` — bundle adjustment, sparse point cloud
4. `pick_best_sparse_model()` — choose best `sparse/N/` folder
5. `image_undistorter` — prepare dense workspace
6. `patch_match_stereo` — CUDA depth maps
7. `stereo_fusion` → `fused.ply`
8. `poisson_mesher` → `meshed-poisson.ply`
9. Optional `postprocess_mesh.py` → `mesh_final.ply`

**Mask integration:** If masks exist, passes `--ImageReader.mask_path` and uses masked features.

**CLI compatibility:** `colmap_cli_options()` probes `-h` output because COLMAP 3.x vs 3.13 use different flag names (`SiftExtraction` vs `FeatureExtraction`).

---

## redo_dense.py

**Purpose:** Re-run dense fusion + mesh without repeating sparse SfM.

Used by `run_best.py` for wall-friendly re-fusion with looser parameters.

**CLI:** `--from-step fusion` starts at stereo fusion.

---

## postprocess_mesh.py

**Purpose:** Clean fused point cloud and build higher-quality Poisson mesh.

**Pipeline inside:**
1. Read `fused.ply` (binary COLMAP format)
2. NumPy prefilter — remove outliers by coordinate bounds + percentile core
3. Optional subsample to `max_poisson_points` (OOM guard)
4. PyMeshLab — statistical outlier removal, normal estimation, Screened Poisson
5. Remove small disconnected components
6. Fallback: COLMAP `poisson_mesher` if PyMeshLab fails

**Outputs:** `fused_wall_filtered.ply`, `mesh_wall.ply` (or `mesh_final.ply`)

---

## run_best.py

**Purpose:** Best-quality orchestrator combining COLMAP re-fusion, OpenMVS, and mesh selection.

```
Step 1: refusion_and_post()     → wall-friendly fused.ply + mesh_wall.ply
Step 2: (skip if --skip-refusion) postprocess on existing fused
Step 3: run_openmvs()           → OpenMVS densify/mesh/texture
Step 4: pick_best()             → mesh_best.ply
Bonus: export_dataset()          → 360-GS keyframes
```

**Flags:** `--skip-refusion`, `--skip-openmvs`, `--openmvs-only`

---

## run_openmvs.py

**Purpose:** OpenMVS dense reconstruction and texturing from COLMAP undistorted workspace.

**Steps:** import → densify → reconstruct → (optional refine) → texture

**OpenMVS 2.4 pattern (important):**
```python
# After ReconstructMesh — only scene_mesh.ply exists, NOT scene_mesh.mvs
TextureMesh -i scene_dense.mvs -m scene_mesh.ply -o scene_refine.mvs
```

**import_sparse_only:** Temporarily renames `fused.ply` so InterfaceCOLMAP doesn't load 22M points.

**decimate fix:** Uses `float()` not `int()` for fractional decimation values.

---

## pick_best_mesh.py

**Purpose:** Score mesh candidates and copy winner to `mesh_best.ply`.

**Scoring:** `bbox_diagonal × sqrt(face_count)` — prefers large spatial extent and rich geometry.

**Candidates:**
- `mesh_final.ply`, `mesh_wall.ply`, `meshed-poisson_colmap.ply`
- OpenMVS: `scene_mesh.ply`, textured OBJ converted to PLY

**Guard:** Skips files >400 MB (mesh_wall.ply) to avoid PyMeshLab OOM during scoring.

---

## select_keyframes.py

**Purpose:** Pick sparse temporal subset of frames for pro-quality pipeline.

Uses motion / sharpness heuristics to select ~45 keyframes instead of 314.

---

## prepare_360gs.py

**Purpose:** Export camera poses + images for 360 Gaussian Splatting training.

Output: `exports/360gs_dataset/` with COLMAP-format data compatible with `inuex35/360-gaussian-splatting`.

---

## repair_video.py

**Purpose:** Validate video with ffprobe before spending hours on pipeline.

Checks resolution, codec, duration; compares to reference if provided.

---

## PowerShell scripts (code/scripts/)

| Script | Purpose |
|--------|---------|
| `Install-Windows.ps1` | Download COLMAP CUDA, create venv, install pip packages |
| `Install-OpenMVS.ps1` | Download OpenMVS 2.4.0 binaries |
| `QUICKSTART_GPU.ps1` | Full pipeline wrapper |
| `Run-Best.ps1` | Calls `run_best.py`, tees log to `best_pipeline.log` |
| `Run-Resume-Best.ps1` | Resume with `--skip-refusion` |
| `Run-Handoff-Remask.ps1` | Re-run full handoff after mask fix |
| `Run-ProQuality.ps1` | Keyframe + reduced view pipeline |
| `Run-Dense.ps1` | COLMAP dense only |

**PowerShell note:** `$ErrorActionPreference = "Continue"` around Python calls because COLMAP logs to stderr.

---

## Adding annotations to live code

The copies in `handoff/code/pipeline/` include `# HANDOFF:` header blocks at the top of each file linking back to this document. When modifying live code in `../pipeline/`, update both if behavior changes.
