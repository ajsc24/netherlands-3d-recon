# Project Status & Results

## Objective

Produce the best possible **3D interior mesh** of a Netherlands house bottom floor from a single 360° walkthrough video, using open-source tools on a Windows GPU workstation.

---

## Pipeline variants run

| Variant | Config | Images | Registered | Notes |
|---------|--------|--------|------------|-------|
| **Full handoff** | `config_netherlands_handoff.yaml` | 2512 (314×8 views) | 2445/2512 | Primary production run |
| **Pro 4-view** | `config_netherlands_pro.yaml` | ~180 | 40 | Faster keyframe test |
| **Pro 1-view** | `config_netherlands_pro1view.yaml` | 45 | 34 | Longer camera span (~17 m) |
| **Best integrated** | `config_netherlands_best.yaml` | uses full handoff sparse | 2445 | OpenMVS + re-fusion + pick |

---

## Full handoff results (COLMAP)

| Artifact | Path | Stats |
|----------|------|-------|
| Sparse model | `workspace_netherlands/colmap/sparse/1/` | 51,410 points, **2445 images** |
| Depth maps | `workspace_netherlands/colmap/dense/stereo/depth_maps/` | 4,890 files |
| Fused cloud | `workspace_netherlands/colmap/dense/fused.ply` | ~22.8M points |
| Final mesh | `workspace_netherlands/colmap/dense/mesh_final.ply` | ~2.8M verts, 168 MB |
| Wall mesh | `workspace_netherlands/colmap/dense/mesh_wall.ply` | ~25.6M verts (Poisson on full cloud) |

**User feedback:** Better than early runs — couch and piano visible, but ~80% of room still missing (typical photogrammetry limitation on flat walls and uniform surfaces).

---

## OpenMVS results

| Step | Status | Output |
|------|--------|--------|
| InterfaceCOLMAP | ✓ | `scene.mvs` |
| DensifyPointCloud | ✓ (~1.5 h) | `scene_dense.mvs`, 4M points |
| ReconstructMesh | ✓ | `scene_mesh.ply`, 826k verts |
| RefineMesh | ✗ skipped/failed | GPU/memory on 8 GB |
| TextureMesh | ✓ (~50 min) | `scene_refine.obj` + 2×4096 JPG atlases |

Texture settings that worked: `max_texture_size: 4096`, `texture_resolution_level: 2`, `decimate: 0.5`.

---

## mesh_best.ply selection

Automated scoring (`pick_best_mesh.py`) prefers **spatial extent × face count**:

1. `mesh_final.ply` — **winner** (largest bbox diagonal ~30.5 m)
2. `scene_mesh.ply` — OpenMVS untextured (~22.5 m diagonal)
3. `mesh_wall.ply` — skipped in scoring (>400 MB)

For **textured** viewing, use `scene_refine.obj` regardless of `mesh_best.ply`.

---

## Optional next steps

1. **360 Gaussian Splatting** — `exports/360gs_dataset/` + `Install-360GS.ps1` for immersive quality
2. **Fewer images** — pro keyframe configs for faster iteration
3. **Meshroom / hloc** — alternative SfM+MVS not yet integrated
4. **Higher texture quality** — retry TextureMesh with more RAM or fewer images
