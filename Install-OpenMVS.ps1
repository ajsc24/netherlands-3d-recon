# Download OpenMVS Windows binaries (CPU build; works without 7-Zip).
# Run: .\Install-OpenMVS.ps1
#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Dest = Join-Path $Root "tools\openmvs"
$Zip = Join-Path $Root "tools\OpenMVS_Windows_x64.zip"
$Url = "https://github.com/cdcseacave/openMVS/releases/download/v2.4.0/OpenMVS_Windows_x64.zip"

if (Test-Path (Join-Path $Dest "InterfaceCOLMAP.exe")) {
    Write-Host "[OK] OpenMVS already installed at $Dest" -ForegroundColor Green
    exit 0
}

Write-Host "Downloading OpenMVS v2.4.0 Windows x64..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path (Split-Path $Dest) | Out-Null
Invoke-WebRequest -Uri $Url -OutFile $Zip -UseBasicParsing
if (Test-Path $Dest) { Remove-Item -Recurse -Force $Dest }
Expand-Archive -Path $Zip -DestinationPath (Join-Path $Root "tools") -Force
Remove-Item $Zip -Force

# Zip may extract to tools/OpenMVS or flat; normalize to tools/openmvs
$candidates = @(
    (Join-Path $Root "tools\OpenMVS"),
    (Join-Path $Root "tools\openMVS"),
    (Join-Path $Root "tools\openmvs")
)
$found = $null
foreach ($c in $candidates) {
    if (Test-Path (Join-Path $c "InterfaceCOLMAP.exe")) { $found = $c; break }
}
if (-not $found) {
  Get-ChildItem (Join-Path $Root "tools") -Recurse -Filter "InterfaceCOLMAP.exe" | Select-Object -First 1 | ForEach-Object {
    $found = $_.DirectoryName
  }
}
if (-not $found) {
    Write-Host "ERROR: InterfaceCOLMAP.exe not found after extract." -ForegroundColor Red
    exit 1
}
if ($found -ne $Dest) {
    if (Test-Path $Dest) { Remove-Item -Recurse -Force $Dest }
    Move-Item $found $Dest
}
Write-Host "[OK] OpenMVS installed: $Dest" -ForegroundColor Green
Get-ChildItem $Dest -Filter "*.exe" | Select-Object Name
