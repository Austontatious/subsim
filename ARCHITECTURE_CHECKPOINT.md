# Architecture Checkpoint

Last updated: 2026-04-24

Current-state architecture map for SubSim.

## System purpose
SubSim is an audio-first deterministic submarine simulation with a desktop Python runtime, a Godot Android frontend, and replayable QA/playtester instrumentation.

## Current runtime architecture
- Simulation core: `subsim/engine/`
- Runtime loop and mode control: `subsim/game.py`, `subsim/__main__.py`
- Audio/event systems: `subsim/audio.py`, `subsim/events.py`, `subsim/assets.py`
- Hybrid runtime acoustic layer: `subsim/runtime_acoustic.py`, `subsim/runtime_acoustic_presets_v1.json`
- Hybrid family renderer: `subsim/renderer_v1.py`, `dataset/hydrophone/renderer_params_v1.json`
- Canonical acoustic contract: `subsim/acoustic_contract.py`, `docs/ACOUSTIC_CONTRACT.md`
- Godot acoustic playback path: `godot/scripts/audio/acoustic_mixer.gd`, `godot/scripts/engine_port/engine.gd`, `godot/main/Main.tscn`
- Godot preset parity hook: `godot/audio/runtime_acoustic_presets_v1.json`
- Replay and determinism surfaces: `subsim/replay.py`
- Machine-readable sonar console: `subsim/testing/sonar_console/`

## Data/behavior invariants
- Fixed-step deterministic tick model.
- Core control interface stays centered on the `Action` schema in `subsim/input.py`.

## Architecture-defining files
- `subsim/engine/world.py`
- `subsim/engine/sensors.py`
- `subsim/engine/contacts.py`
- `subsim/engine/weapons.py`
- `subsim/engine/ai.py`
- `subsim/game.py`
- `subsim/replay.py`
- `subsim/input.py`
- `subsim/acoustic_contract.py`
- `subsim/runtime_acoustic.py`
- `subsim/renderer_v1.py`
- `godot/scripts/audio/acoustic_mixer.gd`
- `subsim/testing/sonar_console/console.py`

## Known limitations
- Audio-first UX is runtime-sensitive and can vary by host audio stack.
- Godot parity currently applies shared runtime preset multipliers but does not yet consume desktop-generated HybridAcousticRendererV1 wav caches directly.

## When to update this document
- Any change to deterministic tick/replay contracts.
- Any change to engine module ownership or control interfaces.
- Any change to runtime entrypoint or scenario/replay behavior boundaries.
- Any change to acoustic contract schema or cross-surface cue taxonomy.
