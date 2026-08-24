#Requires -Version 5.1
<#
.SYNOPSIS
  Export a web-friendly GLB for the showcase site from the best available mesh.

.DESCRIPTION
  Looks for mesh_best.ply, mesh_final.ply, or scene_refine.obj and writes
  handoff/showcase/assets/model.glb (decimated for web).
#>
param(
    [string]$Root = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent),
    [int]$TargetFaces = 150000
)

$ErrorActionPreference = "Stop"
$OutGlb = Join-Path $Root "handoff\showcase\assets\model.glb"
$OutPly = Join-Path $Root "handoff\showcase\assets\model.ply"
    $Candidates = @(
    (Join-Path $Root "workspace_v2\colmap\dense\mesh_best.ply"),
    (Join-Path $Root "workspace_v2\colmap\dense\mesh_final.ply"),
    (Join-Path $Root "workspace_netherlands\colmap\dense\mesh_best.ply"),
    (Join-Path $Root "workspace_v2\openmvs\scene_refine.obj"),
    (Join-Path $Root "workspace_netherlands\colmap\openmvs\scene_refine.obj")
)

# Also refresh sparse preview for walk mode when no mesh yet
$Colmap = Join-Path $Root "tools\bin\colmap.exe"
$Sparse = Join-Path $Root "workspace_v2\colmap\sparse\1"
$SparseOut = Join-Path $Root "handoff\showcase\assets\sparse_preview.ply"
if ((Test-Path $Colmap) -and (Test-Path $Sparse)) {
    & $Colmap model_converter --input_path $Sparse --output_path $SparseOut --output_type PLY 2>$null
    Copy-Item $SparseOut (Join-Path $Root "docs\assets\sparse_preview.ply") -Force -ErrorAction SilentlyContinue
}

$Mesh = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Mesh) {
    Write-Host "No mesh found. Run the pipeline first, then re-run this script." -ForegroundColor Yellow
    exit 1
}

Write-Host "Source: $Mesh" -ForegroundColor Cyan

$Py = Join-Path $Root "recon_v2\.venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = Join-Path $Root "pipeline\.venv\Scripts\python.exe" }
if (-not (Test-Path $Py)) { $Py = "python" }

$Script = @"
import sys
from pathlib import Path
import pymeshlab

src = Path(r"$Mesh")
out_ply = Path(r"$OutPly")
target = $TargetFaces

ms = pymeshlab.MeshSet()
ms.load_new_mesh(str(src))
if ms.current_mesh().face_number() > target:
    ms.meshing_decimation_quadric_edge_collapse(targetfacenum=target)
    print(f"Decimated to {ms.current_mesh().face_number():,} faces")

ms.save_current_mesh(str(out_ply))
print(f"Wrote {out_ply} ({out_ply.stat().st_size / 1e6:.1f} MB)")
print("For GLB: import model.ply in Blender -> Export glTF")
"@

$Tmp = Join-Path $env:TEMP "export_web_model.py"
$Script | Set-Content -Path $Tmp -Encoding UTF8
& $Py $Tmp
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Done: $OutPly" -ForegroundColor Green
Write-Host "Re-run Publish-Online.ps1 to update the live site." -ForegroundColor Cyan
