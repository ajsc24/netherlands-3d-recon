# Install 360 Gaussian Splatting (optional — for full-room immersive view).
# Requires Python 3.10/3.11 + CUDA PyTorch. Run after Run-Best.ps1 exports keyframes.
#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Tools = Join-Path $Root "tools\360gs"
$Repo = "https://github.com/inuex35/360-gaussian-splatting.git"

Write-Host "=== 360 Gaussian Splatting setup ===" -ForegroundColor Cyan
if (Test-Path (Join-Path $Tools "train.py")) {
    Write-Host "[OK] Already cloned at $Tools"
} else {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Host "Install git first." -ForegroundColor Red
        exit 1
    }
    git clone --depth 1 $Repo $Tools
}

$Dataset = Join-Path $Root "exports\360gs_dataset\images"
if (-not (Test-Path $Dataset)) {
    Write-Host "Run .\Run-Best.ps1 first to export keyframes." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Next steps (manual — needs Python 3.11 + CUDA torch):"
Write-Host "  1. Install Python 3.11: winget install Python.Python.3.11"
Write-Host "  2. OpenSfM spherical reconstruction on $Dataset"
Write-Host "  3. cd tools\360gs && pip install -r requirements.txt"
Write-Host "  4. python train.py -s $Root\exports\360gs_dataset --panorama"
Write-Host ""
Write-Host "See: https://github.com/inuex35/360-gaussian-splatting"
