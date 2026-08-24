#Requires -Version 5.1
<#
.SYNOPSIS
  Publish project code + showcase website to GitHub (public repo + GitHub Pages).

.DESCRIPTION
  1. Creates/updates a git repo (excludes large binaries, video, workspaces)
  2. Creates a public GitHub repository via gh CLI
  3. Enables GitHub Pages from handoff/showcase/
  4. Writes repo-url.txt for the showcase site

  Prerequisites:
    winget install GitHub.cli
    gh auth login

.EXAMPLE
  .\handoff\scripts\Publish-Online.ps1
  .\handoff\scripts\Publish-Online.ps1 -RepoName my-netherlands-3d
#>
param(
    [string]$RepoName = "netherlands-3d-recon",
    [switch]$SkipPages
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $Root

function Require-Gh {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        Write-Host "GitHub CLI (gh) not found. Install: winget install GitHub.cli" -ForegroundColor Red
        exit 1
    }
    gh auth status 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Not logged into GitHub. Run: gh auth login" -ForegroundColor Yellow
        gh auth login
    }
}

Require-Gh

if (-not (Test-Path ".git")) {
    Write-Host "Initializing git repository..." -ForegroundColor Cyan
    git init -b main
}

Write-Host "Staging project files..." -ForegroundColor Cyan
git add -A
$Status = git status --porcelain
if ($Status) {
    git commit -m "Add handoff package, showcase website, and reconstruction pipeline"
} else {
    Write-Host "Nothing new to commit." -ForegroundColor Gray
}

Write-Host "Syncing showcase -> docs/ (GitHub Pages requires /docs)..." -ForegroundColor Cyan
$Docs = Join-Path $Root "docs"
$Showcase = Join-Path $Root "handoff\showcase"
New-Item -ItemType Directory -Force $Docs | Out-Null
Copy-Item (Join-Path $Showcase "*") $Docs -Recurse -Force

$RemoteUrl = $null
try {
    $RemoteUrl = git remote get-url origin 2>$null
} catch {
    $RemoteUrl = $null
}
if (-not $RemoteUrl) {
    Write-Host "Creating public GitHub repo: $RepoName" -ForegroundColor Cyan
    gh repo create $RepoName --public --source=. --remote=origin --push
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Repo create failed (name taken?). Try: -RepoName another-name" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "Pushing to existing remote: $RemoteUrl" -ForegroundColor Cyan
    git push -u origin main
}

$Owner = (gh api user -q .login)
$RepoUrl = "https://github.com/$Owner/$RepoName"
$PagesUrl = "https://$Owner.github.io/$RepoName/"

if (-not $SkipPages) {
    Write-Host "Enabling GitHub Pages from /docs ..." -ForegroundColor Cyan
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    gh api -X POST "repos/$Owner/$RepoName/pages" `
        -f build_type=legacy `
        -f "source[branch]=main" `
        -f "source[path]=/docs" 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        gh api -X PUT "repos/$Owner/$RepoName/pages" `
            -f build_type=legacy `
            -f "source[branch]=main" `
            -f "source[path]=/docs" 2>$null | Out-Null
    }
    $ErrorActionPreference = $prev
}

$RepoUrl | Set-Content -Path (Join-Path $Docs "repo-url.txt") -Encoding UTF8 -NoNewline
$RepoUrl | Set-Content -Path (Join-Path $Showcase "repo-url.txt") -Encoding UTF8 -NoNewline
git add docs handoff/showcase/repo-url.txt handoff/scripts/Publish-Online.ps1
$prev = $ErrorActionPreference
$ErrorActionPreference = "Continue"
git commit -m "Set showcase repo URL" 2>$null | Out-Null
git push 2>&1 | Out-Null
$ErrorActionPreference = $prev

Write-Host ""
Write-Host "=== Published ===" -ForegroundColor Green
Write-Host "  Code:     $RepoUrl"
Write-Host "  Website:  $PagesUrl"
Write-Host "  (Pages may take 1-2 minutes to go live on first publish)"
Write-Host ""
Write-Host "Open locally:  start handoff\showcase\index.html"
Write-Host "Update site:   edit handoff/showcase, then git push"
