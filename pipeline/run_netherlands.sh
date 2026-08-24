#!/usr/bin/env bash
# Full pipeline for Insta360 X2 equirect interior capture.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
CFG="${1:-config_netherlands.yaml}"

if [[ ! -f "$CFG" ]]; then
  echo "Missing $CFG"
  exit 1
fi

VIDEO=$(python3 -c "import yaml; c=yaml.safe_load(open('$CFG')); print(c['video_path'])")
if [[ ! -f "$VIDEO" ]]; then
  echo "Video not found: $VIDEO"
  exit 1
fi

echo "=== Netherlands interior pipeline ==="
echo "Config: $CFG"
echo "Video:  $VIDEO"
python3 pipeline.py --config "$CFG" "$@"
