# One-time setup: ffmpeg, COLMAP (CUDA), Python venv for Netherlands interior pipeline.
# Run from PowerShell:  .\Install-Windows.ps1
#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
$Pipeline = Join-Path $Root "pipeline"
$Tools = Join-Path $Root "tools"
$ColmapExe = Join-Path $Tools "bin\colmap.exe"
$Venv = Join-Path $Pipeline ".venv"
$ColmapVersion = "3.13.0"
$ColmapZip = "colmap-x64-windows-cuda.zip"
$ColmapUrl = "https://github.com/colmap/colmap/releases/download/$ColmapVersion/$ColmapZip"

Write-Host "=== Netherlands interior - Windows GPU setup ===" -ForegroundColor Cyan
Write-Host ""

function Test-Command($Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

if (Test-Command nvidia-smi) {
    Write-Host "[OK] NVIDIA driver:" -ForegroundColor Green
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
} else {
    Write-Host "[WARN] nvidia-smi not found. Install NVIDIA drivers for GPU dense reconstruction." -ForegroundColor Yellow
}

if (-not (Test-Command ffmpeg)) {
    Write-Host "Installing ffmpeg via winget..."
    if (Test-Command winget) {
        winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
        $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
        $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
        $env:Path = $machinePath + ";" + $userPath
    } else {
        Write-Host "winget not found. Install ffmpeg manually: https://ffmpeg.org/download.html" -ForegroundColor Yellow
    }
}

if (Test-Command ffmpeg) {
    $ffver = ffmpeg -version 2>&1 | Select-Object -First 1
    Write-Host "[OK] ffmpeg: $ffver" -ForegroundColor Green
} else {
    Write-Host "[WARN] ffmpeg still not on PATH - reopen PowerShell after install." -ForegroundColor Yellow
}

if (-not (Test-Path $ColmapExe)) {
    New-Item -ItemType Directory -Force -Path $Tools | Out-Null
    $ZipPath = Join-Path $Tools $ColmapZip
    Write-Host "Downloading COLMAP $ColmapVersion CUDA build about 250 MB..."
    Invoke-WebRequest -Uri $ColmapUrl -OutFile $ZipPath -UseBasicParsing
    Write-Host "Extracting COLMAP..."
    Expand-Archive -Path $ZipPath -DestinationPath $Tools -Force
    Remove-Item $ZipPath -Force
}

if (Test-Path $ColmapExe) {
    Write-Host "[OK] COLMAP: $ColmapExe" -ForegroundColor Green
    & $ColmapExe -h 2>&1 | Select-Object -First 3
} else {
    Write-Host "[ERROR] COLMAP install failed. Download manually:" -ForegroundColor Red
    Write-Host "  $ColmapUrl"
    Write-Host "  Extract zip contents into: $Tools"
    exit 1
}

if (-not (Test-Command python)) {
    Write-Host "[ERROR] Python not found. Install Python 3.10+ from https://python.org" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Python: $(python --version)" -ForegroundColor Green

if (-not (Test-Path (Join-Path $Venv "Scripts\python.exe"))) {
    Write-Host "Creating Python venv at pipeline\.venv ..."
    python -m venv $Venv
}

$VenvPython = Join-Path $Venv "Scripts\python.exe"
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r (Join-Path $Pipeline "requirements.txt")
Write-Host "[OK] PyMeshLab (MeshLab filters) installed for mesh post-processing" -ForegroundColor Green

$InputDir = Join-Path $Root "input"
New-Item -ItemType Directory -Force -Path $InputDir | Out-Null

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1) Video should be at:  $InputDir\NetherlandsBottomLevel.mp4"
Write-Host "  2) Run full pipeline:   .\QUICKSTART_GPU.ps1"
Write-Host ""
Write-Host "Resume after interrupt:"
Write-Host "  .\QUICKSTART_GPU.ps1 -FromStep colmap"
Write-Host "  .\pipeline\Run-Dense.ps1"
Write-Host ""
