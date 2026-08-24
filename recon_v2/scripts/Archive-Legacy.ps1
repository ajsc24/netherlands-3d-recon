# Archive legacy reconstruction workspaces to free a clean slate for workspace_v2.
#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not (Test-Path (Join-Path $ProjectRoot "input"))) {
    $ProjectRoot = Split-Path $PSScriptRoot -Parent
    $ProjectRoot = Split-Path $ProjectRoot -Parent
}
# scripts -> recon_v2 -> project root
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Arch = Join-Path $ProjectRoot "archive\legacy_$stamp"
New-Item -ItemType Directory -Force -Path $Arch | Out-Null
Write-Host "Archive: $Arch" -ForegroundColor Cyan
Write-Host ("Free GB before: {0:N1}" -f ((Get-PSDrive C).Free / 1GB))

$toMove = @(
    "workspace_netherlands",
    "workspace_netherlands_pro",
    "workspace_netherlands_pro1view"
)
foreach ($d in $toMove) {
    $src = Join-Path $ProjectRoot $d
    if (Test-Path $src) {
        Write-Host "Moving $d ..."
        Move-Item -LiteralPath $src -Destination $Arch -Force
    } else {
        Write-Host "Skip missing $d"
    }
}

Write-Host ("Free GB after move: {0:N1}" -f ((Get-PSDrive C).Free / 1GB))
Write-Host "Done. Old data is under archive\ (not deleted)." -ForegroundColor Green
