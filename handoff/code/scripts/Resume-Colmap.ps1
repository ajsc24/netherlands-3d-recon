# Resume COLMAP from feature matching (skip frame extract / mask / dewarp).
#Requires -Version 5.1
param(
    [string]$Config = (Join-Path (Split-Path $PSScriptRoot -Parent) "config_netherlands_handoff.yaml"),
    [ValidateSet("match", "mapper", "dense")]
    [string]$FromStep = "match"
)

$Root = Split-Path $Config -Parent
$VenvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Run ..\Install-Windows.ps1 first." -ForegroundColor Red
    exit 1
}

Push-Location $Root
try {
    & $VenvPython (Join-Path $PSScriptRoot "run_colmap.py") --config $Config --from-step $FromStep
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
