# Create recon_v2 Python venv and install dependencies.
#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$Recon = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Venv = Join-Path $Recon ".venv"
$Py = Join-Path $Venv "Scripts\python.exe"
$Req = Join-Path $Recon "requirements.txt"

Write-Host "=== recon_v2 Setup ===" -ForegroundColor Cyan
Write-Host "  $Recon"

if (-not (Test-Path $Py)) {
    Write-Host "Creating venv..."
    python -m venv $Venv
}
& $Py -m pip install --upgrade pip
& $Py -m pip install -r $Req

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Run: .\recon_v2\scripts\Run-Accurate.ps1"
