# QA Runbook (10-minute smoke test)

Date: 2026-04-24

## Setup
1) `python -m venv .venv && .venv/bin/pip install -e .`
2) Run: `.venv/bin/python -m subsim`

## Smoke checklist (10 minutes)
- Launch: game window appears in < 3 seconds, no exceptions in console.
- Menu: start Tutorial, complete at least one step, then return to Menu.
- Skirmish: start a run and confirm objective stages advance (Locate → Classify → Engage/Evade → Extract).
- Audio: you hear contact hums; panning changes as you turn.
- Controls: heading dial (A/D or arrows), pitch dial (W/S), ping (Space), torpedo two-step (T twice).
- Pause/help: Esc pauses mid-run; H help overlay shows controls.

## Audio focus
- Left/right panning is obvious with headphones.
- No clipping or distortion at default volume.
- Ping/torpedo earcons are clear and not fatiguing.

## Acoustic substrate v1 checks (desktop + Godot/APK)
- Contract tests pass:
  - `.venv/bin/python -m pytest -q tests/test_acoustic_contract.py tests/test_game_acoustic_observation.py tests/test_acoustic_contract_docs_sync.py`
- Godot wiring/asset checks pass:
  - `.venv/bin/python -m pytest -q tests/test_godot_acoustic_wiring.py`
- Runtime renderer preset checks pass:
  - `.venv/bin/python -m pytest -q tests/test_runtime_acoustic_integration.py`
- Acoustic observation envelope present (`schema_version`, `foundation`, `contacts`) in `Game.build_observation()`.
- Runtime observation envelope present (`acoustic.runtime_renderer`) with `preset_name`, `families`, and per-layer gain output.
- Preset switching behaves materially differently:
  - `.venv/bin/python -m subsim --headless --ticks 60 --acoustic-preset low_clutter`
  - `.venv/bin/python -m subsim --headless --ticks 60 --acoustic-preset high_clutter`
- Godot playback wiring exists:
  - `AcousticMixer` node in `godot/main/Main.tscn`
  - signal handlers connected in `godot/scripts/audio/acoustic_mixer.gd`
  - engine emits `mix_contact`, `sfx_ping`, `sfx_fire`, `sfx_return` in `godot/scripts/engine_port/engine.gd`
- Godot audio assets synced:
  - `./scripts/sync_godot_audio_assets.sh`
  - verify `godot/audio/sfx/*.wav` exists
  - verify `godot/audio/runtime_acoustic_presets_v1.json` exists
- APK export:
  - `cd godot`
  - `godot --headless --path . --export-debug Android build/subsim-android.apk`
- On-device manual verification:
  - Launch APK and confirm audible ambient bed, passive contact loops, and ping/fire cues.
  - Confirm bottom strip controls are visibly tappable on handset (not tiny labels only).
  - Confirm `PING` button triggers the same ping pulse/audio behavior as keyboard/gesture ping.
  - Confirm `FIRE` button changes gameplay state (torpedo ammo/active count and heading-based launch), not only SFX.
  - Note: CI cannot assert physical handset audibility; this is manual validation only.

## Window focus/resume
- Alt-tab away and back; input still works.
- Resize window (if supported) without crash.

## Notes
- Log any crashes with stack trace and repro steps.
- Capture any audio artifacts (pops, clicks) and list their triggers.

## Headless QA
- Golden trace: `SDL_AUDIODRIVER=dummy PYGLET_HEADLESS=true python -m subsim --scenario skirmish --seed 7 --difficulty normal --ticks 180 --trace tests/golden/skirmish_seed_7.json`
- Replay compare: `SDL_AUDIODRIVER=dummy PYGLET_HEADLESS=true python -m subsim --replay tests/golden/skirmish_seed_7.json`
- Soak (30 min): `SDL_AUDIODRIVER=dummy PYGLET_HEADLESS=true python -m subsim --soak --health-check`
- Agent baseline (headless): `SDL_AUDIODRIVER=dummy PYGLET_HEADLESS=true python -m subsim --agent baseline --headless --ticks 300`
