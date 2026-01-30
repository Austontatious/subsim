# SubSim

Audio-first submarine skirmish prototype for **desktop Python**. The simulation core is deterministic and built for fast iteration on sonar gameplay. Audio is the primary UI: contacts are heard before they are seen.

## Features (current)
- Deterministic sim loop (30 FPS fixed-step) with replayable traces.
- Passive + active sonar model with contact uncertainty.
- Audio event bus with panning + ducking (audio-first UI).
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
| Quit | Q |

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

## Build a release zip (Linux, experimental)
This produces a single-file executable with bundled assets.
```
./scripts/build_release.sh
```
Output:
- `dist/subsim-<version>-linux-x86_64.zip`

## Troubleshooting
- **No audio device**: run with `SDL_AUDIODRIVER=dummy` to silence audio errors.
- **Mixer init fails**: ensure no exclusive audio device is blocking pygame.
- **Headless runs**: set `PYGLET_HEADLESS=true` if display errors occur.
- **Low FPS**: close other GPU-heavy apps; pyglet is lightweight but not vsync capped.

## Repo layout
```
subsim/        # Python package (sim + audio + render)
assets/sfx/    # Generated audio assets
tests/         # pytest suite
```

## License
MIT. See `LICENSE`.
