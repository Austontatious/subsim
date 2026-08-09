# Runbook

Primary QA/operator runbook lives in `QA_RUNBOOK.md`.

## Fast commands
- Install: `python -m venv .venv && .venv/bin/pip install -e .`
- Run: `.venv/bin/python -m subsim`
- Tests: `.venv/bin/python -m pytest -q`
- Headless smoke: `SDL_AUDIODRIVER=dummy PYGLET_HEADLESS=true .venv/bin/python -m subsim --headless --duration 3`
- Acoustic contract checks: `.venv/bin/python -m pytest -q tests/test_acoustic_contract.py tests/test_game_acoustic_observation.py tests/test_acoustic_contract_docs_sync.py`
- Runtime acoustic integration checks: `.venv/bin/python -m pytest -q tests/test_runtime_acoustic_integration.py tests/test_game_acoustic_observation.py`
- Godot acoustic wiring checks: `.venv/bin/python -m pytest -q tests/test_godot_acoustic_wiring.py`
- Godot mobile control checks: `.venv/bin/python -m pytest -q tests/test_godot_mobile_controls.py`
- List runtime presets: `.venv/bin/python -m subsim --list-acoustic-presets`
- Run with preset override: `.venv/bin/python -m subsim --acoustic-preset high_clutter`

## Godot / Android acoustic validation
- Sync assets into Godot project: `./scripts/sync_godot_audio_assets.sh`
- Export APK:
  - `cd godot`
  - `godot --headless --path . --export-debug Android build/subsim-android.apk`
- Verify acoustic wiring before export:
  - `rg -n "AcousticMixer|mix_contact|sfx_ping|sfx_fire|sfx_return" godot/main/Main.tscn godot/main/main.gd godot/scripts/audio/acoustic_mixer.gd godot/scripts/engine_port/engine.gd`
