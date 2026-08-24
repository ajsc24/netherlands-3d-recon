#!/usr/bin/env bash
# Resume only COLMAP (skip extract/mask/dewarp). Use after copying workspace from Windows.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
if command -v colmap >/dev/null 2>&1; then
  FROM="${COLMAP_FROM_STEP:-match}"
  exec python3 run_colmap.py --from-step "$FROM" "$@"
fi
exec python3 pipeline.py --from-step colmap "$@"
