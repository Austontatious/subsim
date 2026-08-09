#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"${ROOT}/.venv/bin/python" - <<'PY'
from subsim.assets import ensure_assets
ensure_assets()
print("Ensured desktop acoustic assets in assets/sfx")
PY

mkdir -p "${ROOT}/godot/audio/sfx"
for base in ambient player_hum merchant hunter ping torpedo mine; do
  for variant in clean lp1 lp2 lp3; do
    cp -f "${ROOT}/assets/sfx/${base}_${variant}.wav" "${ROOT}/godot/audio/sfx/${base}_${variant}.wav"
  done
done
cp -f "${ROOT}/subsim/runtime_acoustic_presets_v1.json" "${ROOT}/godot/audio/runtime_acoustic_presets_v1.json"

echo "Synced assets into godot/audio/sfx and runtime preset pack"
