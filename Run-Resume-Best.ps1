# Resume after crash: skip re-fusion, run OpenMVS + pick best mesh.
#Requires -Version 5.1
$ErrorActionPreference = "Continue"
$Root = $PSScriptRoot
$Venv = Join-Path $Root "pipeline\.venv\Scripts\python.exe"
$Cfg = Join-Path $Root "config_netherlands_best.yaml"
$Log = Join-Path $Root "workspace_netherlands\best_resume.log"

Write-Host "=== Resume BEST pipeline (skip refusion) ===" -ForegroundColor Cyan
Write-Host "Log: $Log"
Write-Host ""

if (-not (Test-Path $Venv)) { Write-Host "Run Install-Windows.ps1"; exit 1 }
& (Join-Path $Root "Install-OpenMVS.ps1") | Out-Null

$env:PYTHONUNBUFFERED = "1"
Push-Location $Root
try {
    & $Venv (Join-Path $Root "pipeline\run_best.py") --config $Cfg --skip-refusion *>&1 |
        Tee-Object -FilePath $Log
    exit $LASTEXITCODE
} finally { Pop-Location }
