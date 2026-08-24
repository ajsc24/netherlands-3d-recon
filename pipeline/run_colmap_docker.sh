#!/usr/bin/env bash
# Run COLMAP in the official Docker image when colmap is not installed on the host.
# Requires: Docker daemon running, NVIDIA optional (CPU works but is slow).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

IMAGE="${COLMAP_IMAGE:-colmap/colmap:latest}"
WORK="$ROOT/workspace"

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not running. Start Docker, or install COLMAP: sudo apt install colmap"
  exit 1
fi

if [[ ! -d "$WORK/images" ]] || [[ -z "$(ls -A "$WORK/images"/*.jpg 2>/dev/null)" ]]; then
  echo "Missing $WORK/images — run frame extraction first (./run.sh or steps 1–4)."
  exit 1
fi

docker pull "$IMAGE"

# GPU: add --gpus all when NVIDIA Container Toolkit is installed
GPU_ARGS=()
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
  GPU_ARGS=(--gpus all)
fi

docker run --rm -it "${GPU_ARGS[@]}" \
  -v "$ROOT:/data" \
  -w /data \
  "$IMAGE" \
  bash -lc 'python3 run_colmap.py --config /data/config.yaml'
