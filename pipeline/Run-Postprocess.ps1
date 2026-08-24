# Rebuild mesh from existing fused.ply (Open3D cleanup + Poisson). ~5-15 min.
#Requires -Version 5.1
& (Join-Path $PSScriptRoot "Run-Dense.ps1") -PostprocessOnly @args
