# Re-run handoff pipeline with FIXED masks (scene=white, drone=black).
# Uses existing frames_raw; re-dewarps, re-matches, re-denses (~many hours).
#Requires -Version 5.1
param(
    [ValidateSet("mask", "dewarp", "colmap")]
    [string]$FromStep = "mask",
    [switch]$DenseOnly
)

$Root = $PSScriptRoot
$Cfg = Join-Path $Root "config_netherlands_handoff.yaml"
$Pipeline = Join-Path $Root "pipeline"
$Venv = Join-Path $Pipeline ".venv\Scripts\python.exe"

if (-not (Test-Path $Venv)) { Write-Host "Run Install-Windows.ps1 first"; exit 1 }

$work = Join-Path $Root "workspace_netherlands"
if (-not (Test-Path (Join-Path $work "frames_raw"))) {
    Write-Host "No frames_raw - run QUICKSTART_GPU.ps1 first"; exit 1
}

Write-Host "=== Handoff re-run with corrected COLMAP masks ===" -ForegroundColor Cyan
Write-Host "This re-processes all 314 frames x 8 views. Expect many hours."
Write-Host ""

if ($DenseOnly) {
    & (Join-Path $Pipeline "Run-Dense.ps1") -Config $Cfg -Full
    exit $LASTEXITCODE
}

# Wipe stale features/masks; keep dense backups (fused_full.ply etc.)
$colmapDir = Join-Path $work "colmap"
$denseDir = Join-Path $colmapDir "dense"
$backupDir = Join-Path $work "dense_backup"
if ($FromStep -in @("mask", "dewarp") -and (Test-Path $denseDir)) {
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    Get-ChildItem $denseDir -Filter "*.ply" | Copy-Item -Destination $backupDir -Force
    Write-Host "Backed up dense PLY files to $backupDir" -ForegroundColor Yellow
}
if ($FromStep -in @("mask", "dewarp")) {
    Remove-Item -Recurse -Force (Join-Path $work "images"), (Join-Path $work "masks") -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force (Join-Path $work "masks_equirect") -ErrorAction SilentlyContinue
    Remove-Item -Force (Join-Path $colmapDir "database.db") -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force (Join-Path $colmapDir "sparse") -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $denseDir -ErrorAction SilentlyContinue
}

Push-Location $Root
try {
    if ($FromStep -eq "mask") {
        & $Venv (Join-Path $Pipeline "mask_drone.py") --config $Cfg
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        $FromStep = "dewarp"
    }
    if ($FromStep -eq "dewarp") {
        & $Venv (Join-Path $Pipeline "dewarp_views.py") --config $Cfg
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        $FromStep = "colmap"
    }
    if ($FromStep -eq "colmap") {
        & $Venv (Join-Path $Pipeline "run_colmap.py") --config $Cfg --from-step extract
        exit $LASTEXITCODE
    }
} finally { Pop-Location }
