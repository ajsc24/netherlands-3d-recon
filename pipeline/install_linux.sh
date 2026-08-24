#!/usr/bin/env bash
# Install system deps + Python venv for drone_recon on Ubuntu/Debian.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "=== Drone recon — Linux setup ==="

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found. Install Python 3.10+ first."
  exit 1
fi

# System packages (sudo)
if command -v apt-get >/dev/null 2>&1; then
  echo "Installing ffmpeg and COLMAP via apt (needs sudo)..."
  sudo apt-get update
  sudo apt-get install -y ffmpeg colmap
else
  echo "apt-get not found — install ffmpeg and colmap manually, then re-run."
  echo "  https://colmap.github.io/install.html"
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "WARNING: ffmpeg not on PATH"
fi

if ! command -v colmap >/dev/null 2>&1; then
  echo "WARNING: colmap not on PATH — set colmap.colmap_exe in config.yaml"
else
  colmap -h | head -3 || true
fi

# Python venv
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

mkdir -p input workspace

echo ""
echo "Setup done."
echo "  1) Copy your MP4 to:  $ROOT/input/video.mp4"
echo "  2) Edit config.yaml if paths differ"
echo "  3) Run:  ./run.sh"
echo ""
