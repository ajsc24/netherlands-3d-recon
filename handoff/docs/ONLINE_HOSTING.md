# Online hosting — showcase website + code repository

## What you get

| Item | URL (after publish) |
|------|---------------------|
| **Public showcase website** | `https://YOUR_GITHUB_USERNAME.github.io/netherlands-3d-recon/` |
| **Source code (GitHub)** | `https://github.com/YOUR_GITHUB_USERNAME/netherlands-3d-recon` |

The website lives in `handoff/showcase/` — interactive 3D viewer, pipeline stats, and link to the repo.

---

## One-time setup

1. Install GitHub CLI:
   ```powershell
   winget install GitHub.cli
   ```

2. Log in (opens browser):
   ```powershell
   gh auth login
   ```

---

## Publish everything (code + website)

From the project root:

```powershell
.\handoff\scripts\Publish-Online.ps1
```

This will:
- Create a git repo (if needed)
- Push code + docs + handoff package to a **public** GitHub repo
- Enable **GitHub Pages** from `handoff/showcase/`
- Write `repo-url.txt` so the site links to your repo

Custom repo name:
```powershell
.\handoff\scripts\Publish-Online.ps1 -RepoName my-netherlands-3d
```

---

## Add the 3D model to the website

After `mesh_best.ply` exists:

```powershell
.\handoff\scripts\Export-WebModel.ps1
git add handoff/showcase/assets/model.ply
git commit -m "Add web 3D model"
git push
```

The site auto-loads `assets/model.ply` or `assets/model.glb`.

---

## Preview locally (before publish)

Open in a browser (needs a local server for ES modules):

```powershell
cd handoff\showcase
python -m http.server 8080
# visit http://localhost:8080
```

Or double-click `index.html` — preview image works; full 3D may need the server above.

---

## Update the live site later

```powershell
git add -A
git commit -m "Update showcase"
git push
```

GitHub Pages redeploys in ~1 minute.

---

## Note on Cursor repos

Cursor-hosted repos (`origin.cursor.com`) are **private** and not suitable for showing the public website. Use GitHub for the showcase; Cursor repo is optional for private backup only (requires WSL on Windows for the origin CLI).
