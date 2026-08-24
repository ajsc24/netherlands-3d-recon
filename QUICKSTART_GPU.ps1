# Full Netherlands interior pipeline on Windows + NVIDIA GPU.
# Run from PowerShell:  .\QUICKSTART_GPU.ps1
#Requires -Version 5.1
param(
    [ValidateSet("check", "extract", "mask", "dewarp", "colmap")]
    [string]$FromStep = "check",
    [switch]$DenseOnly
)

$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
$Pipeline = Join-Path $Root "pipeline"
$Cfg = Join-Path $Root "config_netherlands_handoff.yaml"
$Video = Join-Path $Root "input\NetherlandsBottomLevel.mp4"
$ColmapExe = Join-Path $Root "tools\bin\colmap.exe"
$VenvPython = Join-Path $Pipeline ".venv\Scripts\python.exe"

function Test-Command($Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

Write-Host "=== Netherlands interior - Windows GPU pipeline ===" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $VenvPython)) {
    Write-Host "Python venv not found. Run setup first:" -ForegroundColor Red
    Write-Host "  .\Install-Windows.ps1"
    exit 1
}

if (-not (Test-Path $ColmapExe)) {
    Write-Host "COLMAP not found at $ColmapExe" -ForegroundColor Red
    Write-Host "Run:  .\Install-Windows.ps1"
    exit 1
}

if (Test-Command nvidia-smi) {
    Write-Host "GPU:" -ForegroundColor Green
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
} else {
    Write-Host "WARNING: nvidia-smi failed - dense reconstruction needs an NVIDIA GPU." -ForegroundColor Yellow
}

if (-not (Test-Path $Video)) {
    Write-Host "ERROR: Video not found:" -ForegroundColor Red
    Write-Host "  $Video"
    Write-Host ""
    Write-Host "Copy your Insta360 MP4 there, then re-run this script."
    exit 1
}

if (-not (Test-Command ffmpeg)) {
    Write-Host "WARNING: ffmpeg not on PATH - frame extraction may use OpenCV fallback." -ForegroundColor Yellow
}

$drive = (Get-Location).Drive.Name
$freeGb = [math]::Round((Get-PSDrive $drive).Free / 1GB, 1)
Write-Host "Free disk on current drive: ${freeGb} GB (need about 100 GB for full dense run)"
Write-Host ""

if ($DenseOnly) {
    Write-Host "Dense-only mode..."
    & (Join-Path $Pipeline "Run-Dense.ps1") -Config $Cfg
    exit $LASTEXITCODE
}

$pipelineArgs = @(
    (Join-Path $Pipeline "pipeline.py"),
    "--config", $Cfg,
    "--from-step", $FromStep
)

Write-Host "Running pipeline from step: $FromStep"
Write-Host ""

Push-Location $Root
try {
    & $VenvPython @pipelineArgs
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        exit $code
    }
} finally {
    Pop-Location
}

$mesh = Join-Path $Root "workspace_netherlands\colmap\dense\mesh_final.ply"
if (-not (Test-Path $mesh)) {
    Write-Host ""
    Write-Host "Sparse steps finished. Run dense + mesh:"
    Write-Host "  .\pipeline\Run-Dense.ps1"
    Write-Host "  or:  .\QUICKSTART_GPU.ps1 -DenseOnly"
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "  Point cloud: $Root\workspace_netherlands\colmap\dense\fused_filtered.ply"
Write-Host "  Mesh:        $mesh"
Write-Host ""
Write-Host "Open mesh_final.ply in MeshLab (press R to reset view)."
