# Run the accuracy-first reconstruction pipeline.
#Requires -Version 5.1
param(
    [ValidateSet(
        "extract", "keyframes", "mask", "dewarp", "sfm",
        "mvs", "mesh_post", "openmvs", "pick", "export_360gs"
    )]
    [string]$FromStep = "extract",
    [ValidateSet(
        "extract", "keyframes", "mask", "dewarp", "sfm",
        "mvs", "mesh_post", "openmvs", "pick", "export_360gs"
    )]
    [string]$ToStep = "export_360gs",
    [string]$Config = ""
)

$ErrorActionPreference = "Continue"
$Recon = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ProjectRoot = (Resolve-Path (Join-Path $Recon "..")).Path
$VenvPy = Join-Path $Recon ".venv\Scripts\python.exe"
$Orch = Join-Path $Recon "src\orchestrate.py"

if (-not $Config) {
    $Config = Join-Path $Recon "config_accurate.yaml"
}

if (-not (Test-Path $VenvPy)) {
    Write-Host "Run .\recon_v2\scripts\Setup.ps1 first." -ForegroundColor Red
    exit 1
}

$Work = Join-Path $ProjectRoot "workspace_v2"
New-Item -ItemType Directory -Force -Path (Join-Path $Work "logs") | Out-Null
$Log = Join-Path $Work "logs\pipeline.log"

Write-Host "=== ACCURATE pipeline ===" -ForegroundColor Cyan
Write-Host "  From: $FromStep  To: $ToStep"
Write-Host "  Log:  $Log"
Write-Host ""

$env:PYTHONUNBUFFERED = "1"
Push-Location $ProjectRoot
try {
    & $VenvPy $Orch --config $Config --from-step $FromStep --to-step $ToStep *>&1 |
        Tee-Object -FilePath $Log -Append
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
