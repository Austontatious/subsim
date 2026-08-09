# SubSim

Audio-first submarine skirmish prototype with a deterministic **desktop Python runtime** and a **Godot Android frontend**. Audio is the primary UI: contacts are heard before they are seen.

## Features (current)
- Deterministic sim loop (30 FPS fixed-step) with replayable traces.
- Passive + active sonar model with contact uncertainty.
- Audio event bus with panning + ducking (audio-first UI).
- Foundational acoustic bed (ambient + self-noise + player hum) and passive contact timbre variants.
- HybridAcousticRendererV1 is integrated into desktop runtime mix for five families (`ambient_soundscape`, `marine_mammal_whale`, `marine_mammal_other`, `surface_vessel`, `intermittent_machinery_archetype`).
- Runtime acoustic preset pack (`low_clutter`, `medium_clutter`, `high_clutter`, plus environment-flavored presets) controls clutter density and masking character.
- Canonical acoustic contract shared across desktop runtime, Godot frontend, and sonar-console playtester instrumentation.
- Two-dial control scheme (heading + pitch) + ping/torpedo buttons.
- Menu / Tutorial / Skirmish / Debrief modes.
- Objective loop: Locate → Classify → Engage/Evade → Extract.
- Scenario generator with difficulty presets (easy/normal/hard).
- Headless runs + baseline agent harness for replay/QA.

## Controls (two dials + two buttons)
| Action | Key |
| --- | --- |
| Heading dial | A / D or Left / Right |
| Fine heading | Q / E |
| Pitch dial (dive/climb) | W / S |
| Roll dial (optional) | Z / C |
| Active ping | Space |
| Torpedo (two-step) | T |
| Cycle contact | Tab |
| Lock contact | Enter |
| Help overlay | H |
| Pause | Esc |
| Quit | X |

## How to play (audio-first)
- **Listen** first: contact hums pan left/right based on bearing.
- **Move** to reduce own-noise and improve detection.
- **Ping** (Space) to improve classification but increase risk.
- **Engage** with torpedoes using the two-step solution window (press T to start, T again when ready).
- **Extract** once objectives advance to the exit phase.

## Install & run (venv)
```
python -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python -m subsim
```

One-liner run:
```
python -m venv .venv && .venv/bin/pip install -e . && .venv/bin/python -m subsim
```

Headless smoke test:
```
SDL_AUDIODRIVER=dummy PYGLET_HEADLESS=true .venv/bin/python -m subsim --headless --duration 3
```

List runtime acoustic presets:
```
.venv/bin/python -m subsim --list-acoustic-presets
```

Run with a clutter preset:
```
.venv/bin/python -m subsim --acoustic-preset high_clutter
```

Headless trace (golden generation):
```
SDL_AUDIODRIVER=dummy PYGLET_HEADLESS=true .venv/bin/python -m subsim --scenario skirmish --seed 7 --difficulty normal --ticks 180 --trace tests/golden/skirmish_seed_7.json
```

Soak test (30 min, baseline agent):
```
SDL_AUDIODRIVER=dummy PYGLET_HEADLESS=true .venv/bin/python -m subsim --soak --health-check
```

Agent baseline (headless):
```
SDL_AUDIODRIVER=dummy PYGLET_HEADLESS=true .venv/bin/python -m subsim --agent baseline --headless --ticks 300
```

## Canonical acoustic contract
- Contract doc: `docs/ACOUSTIC_CONTRACT.md`
- Completion report: `docs/acoustic_substrate_completion_report.md`
- Asset gap report: `docs/ACOUSTIC_ASSET_GAP_REPORT.md`
- Hydrophone-derived renderer params + previews: `python3 tools/renderer_v1_pipeline.py run-all`
- Runtime renderer integration report: `docs/runtime_acoustic_integration_report.md`
- Runtime preset pack:
  - Desktop source: `subsim/runtime_acoustic_presets_v1.json`
  - Godot parity copy: `godot/audio/runtime_acoustic_presets_v1.json`

`Game.build_observation()` now exposes an `acoustic` envelope (`schema_version`, `foundation`, `contacts`, `runtime_renderer`) so agent consumers and playtester tooling use the same substrate semantics as player-facing audio.

## Build a release zip (Linux, experimental)
This produces a single-file executable with bundled assets.
```
./scripts/build_release.sh
```
Output:
- `dist/subsim-<version>-linux-x86_64.zip`

## Godot / Android acoustic path
1. Sync desktop-generated acoustic assets into Godot project resources:
   - `./scripts/sync_godot_audio_assets.sh`
2. Export Android debug APK (example):
   - `cd godot`
   - `godot --headless --path . --export-debug Android build/subsim-android.apk`
3. APK output:
   - `godot/build/subsim-android.apk`

## Troubleshooting
- **No audio device**: run with `SDL_AUDIODRIVER=dummy` to silence audio errors.
- **Mixer init fails**: ensure no exclusive audio device is blocking pygame.
- **Headless runs**: set `PYGLET_HEADLESS=true` if display errors occur.
- **Low FPS**: close other GPU-heavy apps; pyglet is lightweight but not vsync capped.
- **Godot frontend is silent**: verify `godot/audio/sfx/*.wav` exists and scene contains `AcousticMixer` node (`godot/main/Main.tscn`).

## Repo layout
```
subsim/        # Python package (sim + audio + render)
assets/sfx/    # Generated audio assets
godot/         # Android frontend path (includes acoustic playback layer)
tests/         # pytest suite
```

## License
Software and original documentation: MIT. See `LICENSE`.

Third-party hydrophone data and source-derived outputs retain their source terms and are not relicensed under MIT. See `THIRD_PARTY_DATA.md`.
