# Known Issues & Fixes

Issues encountered during this project and how they were resolved.

---

## 1. Inverted COLMAP masks (~4% usable pixels)

**Symptom:** Sparse reconstruction registered almost no images; mesh was tiny sliver.

**Cause:** `mask_drone.py` originally set the scene to black and drone to white — opposite of COLMAP convention (0=ignore, 255=valid).

**Fix:** Mask now fills scene with 255, drone polygon with 0. Re-run from mask step.

---

## 2. Wrong sparse model folder

**Symptom:** Dense step used `sparse/0` with fewer images while `sparse/1` had 2445.

**Fix:** `pick_best_sparse_model()` in `run_colmap.py` selects the sparse subfolder with most registered images.

---

## 3. PowerShell treats COLMAP stderr as fatal

**Symptom:** `Run-Best.ps1` exited early though COLMAP was still running.

**Fix:** Set `$ErrorActionPreference = "Continue"` around Python subprocess calls in PowerShell scripts.

---

## 4. OpenMVS import crash on 22M-point fused.ply

**Symptom:** `InterfaceCOLMAP` hung or crashed loading huge COLMAP fusion.

**Fix:** `import_sparse_only: true` in config — temporarily hides `fused.ply` during import; OpenMVS densifies fresh.

---

## 5. OpenMVS 2.4 does not write scene_mesh.mvs

**Symptom:** `RefineMesh` / `TextureMesh` failed: "unable to open scene_mesh.mvs".

**Cause:** OpenMVS 2.4 only exports `scene_mesh.ply` from ReconstructMesh; camera data stays in `scene_dense.mvs`.

**Fix:** Use `-i scene_dense.mvs -m scene_mesh.ply` for refine and texture. See `run_openmvs.py`.

---

## 6. Poisson OOM on 22M points

**Symptom:** `postprocess_mesh.py` crashed during Poisson on full fused cloud.

**Fix:** `max_poisson_points: 3000000` subsamples before Poisson in `config_netherlands_best.yaml`.

---

## 7. TextureMesh OOM / crash

**Symptom:** TextureMesh killed after ~18 min with 2445 images at 8192px.

**Fix:** Reduced settings: `max_texture_size: 4096`, `texture_resolution_level: 2`, `decimate: 0.5`, `refine_mesh: false`.

**Bug fixed:** `decimate: 0.5` was ignored because code used `int(0.5) == 0`. Now uses `float`.

---

## 8. Concurrent pipeline runs

**Symptom:** Log file locks, duplicate fusion processes, corrupted PLY.

**Fix:** Use single log file; `Run-Resume-Best.ps1` for clean restarts; don't run multiple pipelines in parallel.

---

## Limitations (not bugs)

- **Flat walls / uniform paint** — photogrammetry struggles; expect missing geometry (~80% room in user feedback).
- **8 GB VRAM** — dense stereo and OpenMVS texture are memory-bound; close other GPU apps.
- **2445 images** — OpenMVS densify takes 1–2+ hours; texture ~50 min with reduced settings.
- **Open3D unavailable** on Python 3.13 — PyMeshLab used instead.
- **Textured OBJ** has atlas textures, not per-vertex color.

---

## Exit codes seen

| Code | Meaning |
|------|---------|
| `3221225477` | Windows access violation (COLMAP Poisson crash) |
| `1073807364` | Process terminated externally (OOM / kill) |
| `4294967295` | -1 unsigned (OpenMVS generic failure) |
