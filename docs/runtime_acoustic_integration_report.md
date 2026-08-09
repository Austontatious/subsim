# Runtime Acoustic Integration Report

Generated: 2026-04-24T02:07:41Z
Report version: `runtime_acoustic_integration_report.v1`

## Summary

HybridAcousticRendererV1 is now live in the desktop runtime acoustic path. The runtime mixer layers renderer-generated families under existing tactical/event cues and drives them through a compact preset pack (`runtime_acoustic_presets_v1`).

Desktop runtime is the primary validated target in this pass. Godot has a first parity hook for shared preset behavior, but not full renderer-loop playback parity yet.

## Desktop Runtime Integration Status

Active integration points:
- `subsim/game.py::_update_audio_mix`
- `subsim/audio.py::play_external_loop`
- `subsim/runtime_acoustic.py::RuntimeHybridLayerV1`

Active runtime families:
- `ambient_soundscape`
- `marine_mammal_whale`
- `marine_mammal_other`
- `surface_vessel`
- `intermittent_machinery_archetype`

Observation surface now includes:
- `acoustic.runtime_renderer`

Default runtime preset:
- `medium_clutter`

## Preset Pack v1

Preset pack files:
- Desktop source: `subsim/runtime_acoustic_presets_v1.json`
- Godot parity copy: `godot/audio/runtime_acoustic_presets_v1.json`

Available presets:
- `low_clutter`
- `medium_clutter`
- `high_clutter`
- `open_ocean_quiet`
- `coastal_busy`
- `biologics_heavy`

Control axes per preset:
- foundation multipliers (ambient/self-noise/player-hum + masking pressure)
- family-level `enabled/intensity/variability/density/duration_s`
- global mix gain

Runtime selection path:
- `.venv/bin/python -m subsim --acoustic-preset <name>`
- `.venv/bin/python -m subsim --list-acoustic-presets`

## Contract Mapping

Contract truth remains in:
- `subsim/acoustic_contract.py`

Renderer/presentation layer is:
- `subsim/runtime_acoustic.py`

Family hook mapping:
- `ambient_soundscape -> foundation.ambient`
- `marine_mammal_whale -> contacts.biologic_large`
- `marine_mammal_other -> contacts.biologic_other`
- `surface_vessel -> contacts.surface_vessel`
- `intermittent_machinery_archetype -> contacts.unknown_contact_like`

## Godot Parity Status

Status: **partial_hook**

Shared now:
- shared runtime preset pack JSON consumption
- foundation multiplier shaping in `AcousticMixer`
- surface-vessel/intermittent-machinery weighting in contact gain path

Desktop-only now:
- direct playback of desktop-generated runtime hybrid family loops
- full runtime family layer graph

Next parity step:
- route desktop runtime layer metadata/audio proxies into the Godot mixer for full family parity.

## Tactical Cue Preservation

Explicit tactical/event cues remain directly driven (not replaced by atmospheric renderer layers), including:
- `PING`, `RETURN`
- fire-control cues (`FIRE_SOLUTION_START/READY/MISS`)
- weapon cues (`TORP_LAUNCH`, `TORP_IN_WATER`, `TORP_HIT`, `DETONATION`)
- UI cues (`UI_CONFIRM`, `UI_ALERT`)

## Validation

Automated tests:
- Command: `.venv/bin/python -m pytest -q tests/test_runtime_acoustic_integration.py tests/test_game_acoustic_observation.py tests/test_godot_acoustic_wiring.py tests/test_acoustic_contract_docs_sync.py`
- Result: `10 passed in 32.34s`

Headless runtime smokes:
- `SDL_AUDIODRIVER=dummy PYGLET_HEADLESS=true .venv/bin/python -m subsim --headless --ticks 60 --acoustic-preset low_clutter` (pass)
- `SDL_AUDIODRIVER=dummy PYGLET_HEADLESS=true .venv/bin/python -m subsim --headless --ticks 60 --acoustic-preset high_clutter` (pass)

## Remaining Gaps

- Godot currently consumes preset multipliers, but does not yet consume full desktop renderer loop outputs.
- Audio plausibility remains listening-validated; no objective timbre quality gate exists yet.
- Report generation is static in this pass (not CI-regenerated).
