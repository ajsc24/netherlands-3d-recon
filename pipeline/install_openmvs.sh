#!/usr/bin/env bash
# Download prebuilt OpenMVS 2.4.0 for Ubuntu x64.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/tools/openmvs"
ZIP="$DEST/OpenMVS_Ubuntu_x64.zip"
URL="https://github.com/cdcseacave/openMVS/releases/download/v2.4.0/OpenMVS_Ubuntu_x64.zip"

mkdir -p "$DEST"
cd "$DEST"

if [[ -x "$DEST/InterfaceCOLMAP" ]]; then
  echo "OpenMVS already installed at $DEST"
  exit 0
fi

echo "Downloading OpenMVS (~158 MB)..."
if command -v wget >/dev/null; then
  wget -c -O "$ZIP" "$URL"
elif command -v curl >/dev/null; then
  curl -L -o "$ZIP" "$URL"
else
  echo "Install wget or curl first."
  exit 1
fi

if [[ ! -s "$ZIP" ]]; then
  echo "Download failed (empty file)."
  exit 1
fi

echo "Extracting..."
unzip -o "$ZIP"
chmod +x InterfaceCOLMAP DensifyPointCloud ReconstructMesh RefineMesh TextureMesh 2>/dev/null || true

echo ""
echo "OpenMVS ready:"
ls -1 "$DEST"/InterfaceCOLMAP "$DEST"/DensifyPointCloud "$DEST"/ReconstructMesh 2>/dev/null
echo ""
echo "Next: ./run_openmvs.sh"
