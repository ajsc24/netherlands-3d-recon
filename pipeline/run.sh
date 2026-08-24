#!/usr/bin/env bash
# Run the full pipeline (or resume with --from-step colmap).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  echo "No .venv — run ./install_linux.sh first"
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if [[ ! -f config.yaml ]]; then
  echo "Missing config.yaml"
  exit 1
fi

VIDEO=$(python3 -c "import yaml; c=yaml.safe_load(open('config.yaml')); print(c['video_path'])")
if [[ ! -f "$VIDEO" ]]; then
  echo "Video not found: $VIDEO"
  echo "Copy your MP4 to input/video.mp4 (or edit video_path in config.yaml)"
  exit 1
fi

echo "=== Starting pipeline ==="
python3 pipeline.py "$@"
