# Dense reconstruction: best sparse model -> fusion -> Open3D mesh.
# Usage:
#   .\Run-Dense.ps1                    # re-fuse + mesh (fast if depth maps exist)
#   .\Run-Dense.ps1 -Full              # wipe dense + patch_match + fuse + mesh (hours)
#   .\Run-Dense.ps1 -PostprocessOnly   # mesh only from existing fused.ply
#Requires -Version 5.1
param(
    [string]$Config = (Join-Path (Split-Path $PSScriptRoot -Parent) "config_netherlands_handoff.yaml"),
    [switch]$Full,
    [switch]$PostprocessOnly
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $Config -Parent
$Pipeline = $PSScriptRoot
$VenvPython = Join-Path $Pipeline ".venv\Scripts\python.exe"
$Colmap = Join-Path $Root "tools\bin\colmap.exe"
$cfgYaml = Get-Content $Config -Raw
if ($cfgYaml -match 'work_dir:\s*"?([^"\r\n]+)"?') {
    $WorkDir = $Matches[1].Trim()
} else {
    $WorkDir = "workspace_netherlands"
}
$Dense = Join-Path $Root "$WorkDir\colmap\dense"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Run ..\Install-Windows.ps1 first." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $Colmap)) {
    Write-Host "COLMAP not found." -ForegroundColor Red
    exit 1
}

$step = "fusion"
if ($Full) { $step = "undistort" }
if ($PostprocessOnly) { $step = "postprocess" }

if ($step -eq "fusion" -and -not (Test-Path "$Dense\stereo\depth_maps")) {
    Write-Host "No depth maps — use -Full for full dense reconstruction." -ForegroundColor Red
    exit 1
}
if ($step -eq "postprocess" -and -not (Test-Path "$Dense\fused.ply")) {
    Write-Host "No fused.ply — run without -PostprocessOnly first." -ForegroundColor Red
    exit 1
}

Push-Location $Root
try {
    & $VenvPython (Join-Path $Pipeline "redo_dense.py") --config $Config --from-step $step
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
