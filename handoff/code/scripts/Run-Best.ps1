# =============================================================================
# HANDOFF ANNOTATION — Run-Best.ps1
# =============================================================================
# PURPOSE: Entry point for best-quality pipeline (OpenMVS + re-fusion + mesh pick)
# CALLS:   pipeline/run_best.py --config config_netherlands_best.yaml
# LOG:     workspace_netherlands/best_pipeline.log
# NOTE:    $ErrorActionPreference = Continue around Python (COLMAP stderr)
# =============================================================================

# Best-quality mesh: OpenMVS + wall-friendly re-fusion + multi-mesh pick + 360-GS export.
# Uses existing COLMAP sparse/dense (no full 20h re-run).
#Requires -Version 5.1
param(
    [switch]$SkipOpenMVS,
    [switch]$SkipRefusion,
    [switch]$OpenMVSOnly,
    [switch]$InstallOnly
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Pipeline = Join-Path $Root "pipeline"
$Cfg = Join-Path $Root "config_netherlands_best.yaml"
$Venv = Join-Path $Pipeline ".venv\Scripts\python.exe"

if (-not (Test-Path $Venv)) {
    Write-Host "Run .\Install-Windows.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host "=== BEST quality pipeline ===" -ForegroundColor Cyan
Write-Host "  OpenMVS mesh + wall re-fusion + mesh pick + 360-GS export"
Write-Host ""

& (Join-Path $Root "Install-OpenMVS.ps1")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if ($InstallOnly) { exit 0 }

$args = @(
    (Join-Path $Pipeline "run_best.py"),
    "--config", $Cfg
)
if ($SkipOpenMVS) { $args += "--skip-openmvs" }
if ($SkipRefusion) { $args += "--skip-refusion" }
if ($OpenMVSOnly) { $args += "--openmvs-only" }

Push-Location $Root
try {
    $log = Join-Path $Root "workspace_netherlands\best_pipeline.log"
    $env:PYTHONUNBUFFERED = "1"
    # COLMAP logs to stderr; don't let PowerShell treat that as a fatal error.
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $Venv @args *>&1 | Tee-Object -FilePath $log
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prevEap
    exit $code
} finally {
    Pop-Location
}
