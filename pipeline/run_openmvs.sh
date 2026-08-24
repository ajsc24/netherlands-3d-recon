#!/usr/bin/env bash
# Dense reconstruction via OpenMVS from existing COLMAP sparse + undistorted images.
# Works on CPU (OpenMP). GPU optional if OpenMVS CUDA build is used.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

CFG="${1:-config_netherlands.yaml}"
WORK_REL=$(python3 -c "import yaml; print(yaml.safe_load(open('$CFG'))['work_dir'])")
WORK="$ROOT/$WORK_REL"
COLMAP="$WORK/colmap"
DENSE="$COLMAP/dense"
MVS="$COLMAP/openmvs"
OPENMVS="${OPENMVS_BIN:-$ROOT/tools/openmvs}"

if [[ ! -x "$OPENMVS/InterfaceCOLMAP" ]]; then
  echo "OpenMVS not found. Run: ./install_openmvs.sh"
  exit 1
fi

if [[ ! -d "$DENSE/sparse" ]] || [[ ! -d "$DENSE/images" ]]; then
  echo "Missing undistorted COLMAP dense workspace: $DENSE"
  echo "Run first:"
  echo "  colmap image_undistorter --image_path $WORK/images \\"
  echo "    --input_path $COLMAP/sparse/0 --output_path $DENSE --output_type COLMAP"
  exit 1
fi

mkdir -p "$MVS"
export LD_LIBRARY_PATH="${OPENMVS}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

echo "=== OpenMVS: import COLMAP ==="
"$OPENMVS/InterfaceCOLMAP" \
  --working-folder "$MVS" \
  -i "$DENSE" \
  -o "$MVS/scene.mvs" \
  --image-folder "$DENSE/images"

echo ""
echo "=== OpenMVS: densify (CPU — expect many hours on 2410 images) ==="
# resolution-level 1 = half res (faster, less RAM). Use 0 for full quality.
"$OPENMVS/DensifyPointCloud" \
  --working-folder "$MVS" \
  -i "$MVS/scene.mvs" \
  -o "$MVS/scene_dense.mvs" \
  --resolution-level 1 \
  --number-views 8 \
  --number-views-fuse 3

echo ""
echo "=== OpenMVS: reconstruct mesh ==="
"$OPENMVS/ReconstructMesh" \
  --working-folder "$MVS" \
  -i "$MVS/scene_dense.mvs" \
  -o "$MVS/scene_mesh.mvs"

echo ""
echo "=== OpenMVS: refine mesh ==="
"$OPENMVS/RefineMesh" \
  --working-folder "$MVS" \
  -i "$MVS/scene_mesh.mvs" \
  -o "$MVS/scene_refine.mvs" \
  --resolution-level 1

echo ""
echo "=== OpenMVS: texture + export OBJ ==="
"$OPENMVS/TextureMesh" \
  --working-folder "$MVS" \
  -i "$MVS/scene_refine.mvs" \
  --export-type obj

echo ""
echo "Done."
echo "  OpenMVS project: $MVS/"
echo "  Textured mesh:     $MVS/scene_refine_texture.obj (+ .mtl + images)"
echo ""
echo "Open in MeshLab: File → Import Mesh → scene_refine_texture.obj"
echo "Or convert to PLY in MeshLab: Filters → Remeshing → … → export PLY"
