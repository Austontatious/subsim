# AGENTS.md

This repo follows:
- `/mnt/data/GLOBAL_STANDARDS.md`
- `/mnt/data/AGENTS_CORE.md`
Repo-specific overrides and invariants below.

## Repo-Specific Invariants
# SubSim Agent Guide

## Project intent (source of truth)
Ship a playable, polished submarine game with:
- canonical deterministic **Python desktop** simulation/runtime
- a supported **Godot/Android frontend playback surface** for acoustic parity and mobile playtesting
Audio is primary UI across both surfaces.

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

## Plan and Task Document Authority
- `AGENTS.md`, `ARCHITECTURE_CHECKPOINT.md`, and `PROJECT_MEMORY.md` outrank older plans and task sheets.
- Files under `docs/tasks/` or named `PLAN.md`, `PLANS.md`, or `TODO.md` are historical unless they carry an explicit current status and agree with current architecture and validation evidence.
- Superseded plans belong under `docs/tasks/archive/` with a clear status header.

## Drift, Deleted Files, and Commit Hygiene
- Classify dirty files before staging as intended work, generated leftovers, unrelated drift, or needing human review.
- Do not stage unrelated drift or review-needed material without explicit approval.
- Deleted tracked files require explicit classification; default unclear deletions to human review.
- Keep runtime, data/licensing, generated evidence, and governance changes in coherent commits where practical.
- Before committing, inspect `git status --short`, both staged and unstaged diffs, `git diff --check`, and the staged name/status list.

## Generated Artifact Policy
- Runtime caches, device captures, raw source audio, downloads, staging data, and large renderer previews stay untracked.
- Commit generated reports only when they are useful audit evidence and do not contain restricted source material or secrets.
- Raw or derived hydrophone material must follow `reports/hydrophone/license_review.md` before publication.

## Stateful memory
When making a significant change or decision, append a dated entry to `PROJECT_MEMORY.md`.

## Architecture and Operations Source of Truth
- Architecture truth: `ARCHITECTURE_CHECKPOINT.md`
- Operational procedures: `RUNBOOK.md` and `QA_RUNBOOK.md`

## Overrides
- GIT_POLICY: conservative
- Rationale: Default safety baseline; no local git-policy relaxation is required for routine work.
