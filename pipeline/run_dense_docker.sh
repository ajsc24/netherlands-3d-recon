#!/usr/bin/env bash
# Dense COLMAP (patch_match + fusion + mesh) in official CUDA Docker image.
# Requires: Docker, nvidia-container-toolkit, working nvidia-smi.
set -euo pipefail

PIPELINE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PIPELINE_ROOT"

CFG="${1:-config_netherlands.yaml}"
IMAGE="${COLMAP_IMAGE:-colmap/colmap:latest}"

# Resolve config and handoff root (config may live in parent folder)
if [[ "$CFG" = /* ]]; then
  CFG_ABS="$CFG"
else
  CFG_ABS="$(cd "$PIPELINE_ROOT" && realpath "$CFG" 2>/dev/null || echo "$PIPELINE_ROOT/$CFG")"
fi
HANDOFF_ROOT="$(dirname "$CFG_ABS")"

WORK_REL=$(python3 -c "import yaml; print(yaml.safe_load(open('$CFG_ABS'))['work_dir'])")
if [[ "$WORK_REL" = /* ]]; then
  WORK_ABS="$WORK_REL"
else
  WORK_ABS="$(cd "$HANDOFF_ROOT/$WORK_REL" && pwd)"
fi
DENSE="$WORK_ABS/colmap/dense"
SPARSE="$WORK_ABS/colmap/sparse/0"
IMAGES="$WORK_ABS/images"

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not running. Start Docker first."
  exit 1
fi

if ! nvidia-smi >/dev/null 2>&1; then
  echo "nvidia-smi failed — fix NVIDIA drivers before dense reconstruction."
  exit 1
fi

if [[ ! -d "$SPARSE" ]]; then
  echo "Missing sparse model: $SPARSE"
  echo "Run sparse COLMAP first: python3 run_colmap.py --config $CFG_ABS --from-step match"
  exit 1
fi

if [[ ! -d "$DENSE/stereo" ]] && [[ ! -f "$DENSE/sparse/cameras.bin" ]]; then
  echo "Dense workspace not prepared — running image_undistorter on host..."
  colmap image_undistorter \
    --image_path "$IMAGES" \
    --input_path "$SPARSE" \
    --output_path "$DENSE" \
    --output_type COLMAP
fi

echo "=== Pulling $IMAGE (first time only) ==="
docker pull "$IMAGE"

WORK_IN_DATA="${WORK_ABS#$HANDOFF_ROOT/}"
echo "=== Dense stereo on GPU — expect many hours ==="
docker run --rm --gpus all \
  -v "$HANDOFF_ROOT:/data" \
  -w "/data/$WORK_IN_DATA/colmap/dense" \
  "$IMAGE" \
  colmap patch_match_stereo \
    --workspace_path . \
    --workspace_format COLMAP \
    --PatchMatchStereo.geom_consistency true

echo "=== Stereo fusion ==="
docker run --rm --gpus all \
  -v "$HANDOFF_ROOT:/data" \
  -w "/data/$WORK_IN_DATA/colmap/dense" \
  "$IMAGE" \
  colmap stereo_fusion \
    --workspace_path . \
    --workspace_format COLMAP \
    --input_type geometric \
    --output_path fused.ply

echo "=== Poisson mesh ==="
docker run --rm \
  -v "$HANDOFF_ROOT:/data" \
  -w "/data/$WORK_IN_DATA/colmap/dense" \
  "$IMAGE" \
  colmap poisson_mesher \
    --input_path fused.ply \
    --output_path meshed-poisson.ply

echo ""
echo "Done."
echo "  Point cloud: $DENSE/fused.ply"
echo "  Mesh:        $DENSE/meshed-poisson.ply"
