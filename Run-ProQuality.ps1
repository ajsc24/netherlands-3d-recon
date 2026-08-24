# Pro-quality run: keyframe selection + fewer/higher-res views + fresh COLMAP.
# Run from PowerShell:  .\Run-ProQuality.ps1
#Requires -Version 5.1
param(
    [string]$Config = "config_netherlands_pro.yaml",
    [ValidateSet("check", "extract", "keyframes", "mask", "dewarp", "colmap")]
    [string]$FromStep = "keyframes",
    [switch]$DenseOnly
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Pipeline = Join-Path $Root "pipeline"
$Cfg = if ([System.IO.Path]::IsPathRooted($Config)) { $Config } else { Join-Path $Root $Config }
$VenvPython = Join-Path $Pipeline ".venv\Scripts\python.exe"
$ColmapExe = Join-Path $Root "tools\bin\colmap.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Run .\Install-Windows.ps1 first." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $ColmapExe)) {
    Write-Host "COLMAP missing. Run .\Install-Windows.ps1" -ForegroundColor Red
    exit 1
}

$rawFrames = Join-Path $Root "workspace_netherlands\frames_raw"
if ($FromStep -eq "keyframes" -and -not (Test-Path $rawFrames)) {
    Write-Host "No frames in workspace_netherlands\frames_raw - starting from extract." -ForegroundColor Yellow
    $FromStep = "extract"
}

$cfgYaml = Get-Content $Cfg -Raw
if ($cfgYaml -match 'work_dir:\s*"?([^"\r\n]+)"?') { $WorkDir = $Matches[1].Trim() } else { $WorkDir = "workspace_netherlands_pro" }
if ($cfgYaml -match 'views_per_frame:\s*(\d+)') { $ViewsPerFrame = [int]$Matches[1] } else { $ViewsPerFrame = 4 }

Write-Host "=== Netherlands PRO quality pipeline ===" -ForegroundColor Cyan
Write-Host "Config: $(Split-Path $Cfg -Leaf)"
Write-Host "  Workspace: $WorkDir"
Write-Host "  Keyframes x $ViewsPerFrame views"
Write-Host ""

if ($DenseOnly) {
    & (Join-Path $Pipeline "Run-Dense.ps1") -Config $Cfg
    exit $LASTEXITCODE
}

$steps = @("check", "extract", "keyframes", "mask", "dewarp", "colmap")
$start = [array]::IndexOf($steps, $FromStep)
if ($start -lt 0) { $start = 0 }

Push-Location $Root
try {
    if ($start -le 0) {
        Write-Host "STEP: video check" -ForegroundColor Green
        & $VenvPython (Join-Path $Pipeline "repair_video.py") (Join-Path $Root "input\NetherlandsBottomLevel.mp4")
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    if ($start -le 1) {
        Write-Host "STEP: extract frames" -ForegroundColor Green
        & $VenvPython (Join-Path $Pipeline "extract_frames.py") --config $Cfg
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    if ($start -le 2) {
        $wsRaw = Join-Path $Root "$WorkDir\frames_raw"
        $wsKey = Join-Path $Root "$WorkDir\frames_key"
        $donorKey = Join-Path $Root "workspace_netherlands_pro\frames_key"
        if (-not (Test-Path $wsKey) -and (Test-Path $donorKey) -and $WorkDir -ne "workspace_netherlands_pro") {
            Write-Host "Reusing keyframes from workspace_netherlands_pro\frames_key" -ForegroundColor Yellow
            New-Item -ItemType Directory -Force -Path (Join-Path $Root $WorkDir) | Out-Null
            Copy-Item -Recurse $donorKey $wsKey
        } elseif (-not (Test-Path $wsRaw) -and (Test-Path $rawFrames)) {
            Write-Host "Reusing frames from workspace_netherlands\frames_raw" -ForegroundColor Yellow
            New-Item -ItemType Directory -Force -Path (Join-Path $Root $WorkDir) | Out-Null
            Copy-Item -Recurse $rawFrames $wsRaw
            Write-Host "STEP: select keyframes" -ForegroundColor Green
            & $VenvPython (Join-Path $Pipeline "select_keyframes.py") --config $Cfg
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        } elseif (-not (Test-Path $wsKey)) {
            Write-Host "STEP: select keyframes" -ForegroundColor Green
            & $VenvPython (Join-Path $Pipeline "select_keyframes.py") --config $Cfg
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        } else {
            Write-Host "STEP: keyframes already present - skipping selection" -ForegroundColor Yellow
        }
    }
    if ($start -le 3) {
        Write-Host "STEP: drone masks" -ForegroundColor Green
        & $VenvPython (Join-Path $Pipeline "mask_drone.py") --config $Cfg
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    if ($start -le 4) {
        Write-Host "STEP: dewarp - $ViewsPerFrame view(s) per keyframe" -ForegroundColor Green
        & $VenvPython (Join-Path $Pipeline "dewarp_views.py") --config $Cfg
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    if ($start -le 5) {
        Write-Host "STEP: COLMAP sparse + dense + mesh" -ForegroundColor Green
        & $VenvPython (Join-Path $Pipeline "run_colmap.py") --config $Cfg --from-step extract
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}
