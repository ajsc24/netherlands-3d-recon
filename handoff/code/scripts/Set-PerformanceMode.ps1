# Tune Windows for long COLMAP GPU runs. Run as Administrator for best results.
#Requires -Version 5.1
$ErrorActionPreference = "SilentlyContinue"

Write-Host "=== Performance mode for COLMAP ===" -ForegroundColor Cyan

# High performance power plan
$highPerf = powercfg -list | Select-String "High performance|Ultimate Performance|Hoogste prestaties"
if ($highPerf) {
    $guid = ($highPerf -split "\s+")[3]
    powercfg -setactive $guid | Out-Null
    Write-Host "[OK] Power plan: high performance" -ForegroundColor Green
} else {
    Write-Host "[TIP] Enable High performance in Settings > System > Power" -ForegroundColor Yellow
}

# Prevent sleep while plugged in
powercfg -change -standby-timeout-ac 0 | Out-Null
powercfg -change -hibernate-timeout-ac 0 | Out-Null
powercfg -change -disk-timeout-ac 0 | Out-Null
Write-Host "[OK] Sleep/hibernate disabled on AC power" -ForegroundColor Green

# NVIDIA persistence / status
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv
    Write-Host "[TIP] NVIDIA Control Panel > Manage 3D settings > Power management: Prefer maximum performance" -ForegroundColor Yellow
}

$work = Join-Path $PSScriptRoot "workspace_netherlands"
if (Test-Path $work) {
    Write-Host "[TIP] Add Defender exclusion (Admin PowerShell):" -ForegroundColor Yellow
    Write-Host "  Add-MpPreference -ExclusionPath '$work'" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Before dense run:" -ForegroundColor Cyan
Write-Host "  - Close Chrome, Slack, games (free VRAM for RTX 3050)"
Write-Host "  - Run: .\pipeline\Run-Dense.ps1 -Config .\config_netherlands_maxgpu.yaml"
Write-Host ""
