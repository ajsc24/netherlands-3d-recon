#!/usr/bin/env bash
# Full Netherlands interior pipeline on a GPU Linux box.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CFG="$ROOT/config_netherlands_handoff.yaml"
VIDEO="$ROOT/input/NetherlandsBottomLevel.mp4"

echo "=== Netherlands interior — GPU pipeline ==="
echo ""

if ! nvidia-smi >/dev/null 2>&1; then
  echo "WARNING: nvidia-smi failed. Dense step will need GPU — fix drivers."
fi

if [[ ! -f "$VIDEO" ]]; then
  echo "ERROR: Video not found:"
  echo "  $VIDEO"
  echo ""
  echo "Copy your Insta360 MP4 there, then re-run:"
  echo "  cp /path/to/NetherlandsBottomLevel.mp4 input/"
  exit 1
fi

if ! command -v colmap >/dev/null; then
  echo "Install COLMAP: sudo apt install colmap ffmpeg python3-yaml"
  exit 1
fi

chmod +x "$ROOT/pipeline/"*.sh 2>/dev/null || true

echo "Step 1/2: Extract, mask, dewarp, COLMAP sparse..."
cd "$ROOT/pipeline"
python3 pipeline.py --config "$CFG"

echo ""
echo "Step 2/2: Dense mesh on GPU (Docker)..."
if docker info >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
  ./run_dense_docker.sh "$CFG"
else
  echo "Docker/GPU not ready — sparse done. Run dense later:"
  echo "  cd pipeline && ./run_dense_docker.sh $CFG"
fi

echo ""
echo "Done. Mesh:"
echo "  $ROOT/workspace_netherlands/colmap/dense/meshed-poisson.ply"
