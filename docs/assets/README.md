# Web model assets

Place **`model.glb`** here for the interactive 3D viewer on the showcase site.

## Generate from your mesh

From the project root, after `mesh_best.ply` or `scene_refine.obj` exists:

```powershell
.\handoff\scripts\Export-WebModel.ps1
```

Target size: under ~25 MB for fast GitHub Pages loading.

If `model.glb` is missing, the site shows `preview.jpg` instead.
