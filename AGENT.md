# SubSim Agent Guide

## Project intent (source of truth)
Ship a playable, polished **Python desktop** submarine game. Audio is primary UI. Godot/Android is out of scope.

## Source-of-truth modules
- Core sim + rules: `subsim/engine/world.py`, `subsim/engine/sensors.py`, `subsim/engine/contacts.py`, `subsim/engine/weapons.py`, `subsim/engine/ai.py`
- Audio system: `subsim/audio.py`, `subsim/assets.py`, `subsim/events.py`
- Runtime loop: `subsim/game.py`, `subsim/__main__.py`
- Tunables/constants: `subsim/config.py`
- Replay: `subsim/replay.py`
- Agents: `subsim/agents/`
- Tests: `tests/`

## Conventions and invariants
- Units are **meters** and **seconds**. Speeds are m/s.
- **Depth is negative downward** (surface near `-5.0`, max depth `MAX_DEPTH_M` is negative).
- Headings are degrees; bearing uses `atan2(dy, dx)` (0 deg on +X axis, CCW positive).
- `FRAME_RATE` and `FRAME_DT` are 30 FPS fixed-step.
- Audio asset names/variants are defined in `ASSET_NAMES`/`ASSET_VARIANTS`; tests depend on them.
- Canonical control interface is the two-dial `Action` in `subsim/input.py`.

## Run / test / validate
- Install: `python -m venv .venv && .venv/bin/pip install -e .`
- Run: `.venv/bin/python -m subsim`
- Headless smoke: `SDL_AUDIODRIVER=dummy PYGLET_HEADLESS=true .venv/bin/python -m subsim --headless --duration 3`
- Tests: `.venv/bin/python -m pytest -q`
- Golden replay: `SDL_AUDIODRIVER=dummy PYGLET_HEADLESS=true .venv/bin/python -m subsim --scenario skirmish --seed 7 --difficulty normal --ticks 180 --trace tests/golden/skirmish_seed_7.json`
- Replay compare: `SDL_AUDIODRIVER=dummy PYGLET_HEADLESS=true .venv/bin/python -m subsim --replay tests/golden/skirmish_seed_7.json`
- Agent baseline: `SDL_AUDIODRIVER=dummy PYGLET_HEADLESS=true .venv/bin/python -m subsim --agent baseline --headless --ticks 300`
- Repo guard: `.venv/bin/python validate.py`

## Dont-touch warnings
- Do not change depth sign or world coordinate conventions without updating tests and docs.
- Do not rename audio assets or variants without updating `tests/test_synthesis.py`.
- Keep simulation deterministic under a seed; avoid introducing randoms without seeded RNGs.

## Definition of done (ship checklist)
- Fresh clone -> install -> `python -m subsim` works.
- Tutorial completable; skirmish replayable.
- Audio panning + alerts work and are not obnoxious.
- Controls are standard and responsive.
- 30-minute soak test without crash.
- CI green; tests pass.
- `CHANGELOG.md` + `LICENSE` present.
- A release zip exists with run instructions.

## Stateful memory
When making a significant change or decision, append a dated entry to `PROJECT_MEMORY.md`.
