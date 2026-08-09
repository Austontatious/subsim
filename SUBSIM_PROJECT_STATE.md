# SubSim Project State

Updated: 2026-05-07

## Scope

SubSim is the gameplay producer in the SubSim x ReadyPlayer1 closed-loop rig. ReadyPlayer1 may evaluate SubSim but must not directly edit SubSim gameplay. Codex patches SubSim only after a documented before/after campaign gate.

Current SubSim HEAD: `5f12fe898965bf9758731e5036f24cc7af588b2b`.

Worktree note: the repo was already dirty before this preflight. This document records executable surfaces and evaluation evidence without reverting or deleting existing artifacts.

## Executable Paths

- Full tests: `PYTHONPATH=/mnt/data/subsim SDL_AUDIODRIVER=dummy PYGLET_HEADLESS=true python3 -m pytest -q`
- Standards eval check: `PYTHONPATH=/mnt/data/subsim SDL_AUDIODRIVER=dummy PYGLET_HEADLESS=true python3 evals/runner.py --check`
- Headless smoke: `SDL_AUDIODRIVER=dummy .venv/bin/python -m subsim --headless --duration 3`
- Deterministic trace run: `PYTHONPATH=/mnt/data/subsim SDL_AUDIODRIVER=dummy PYGLET_HEADLESS=true python3 -m subsim --scenario skirmish --seed 7 --difficulty normal --ticks 180 --trace reports/preflight_subsim_skirmish_seed7_trace.json --health-check`
- Replay compare: `SDL_AUDIODRIVER=dummy PYGLET_HEADLESS=true .venv/bin/python -m subsim --replay tests/golden/skirmish_seed_7.json`
- Baseline agent run: `SDL_AUDIODRIVER=dummy PYGLET_HEADLESS=true .venv/bin/python -m subsim --agent baseline --headless --ticks 300`
- Sonar console instrumentation: `subsim/testing/sonar_console/`

## Current Evaluation Boundary

- SubSim emits deterministic gameplay traces and sonar-console perceived/truth streams.
- ReadyPlayer1 consumes replay/live sonar-console observations through `readyplayer1/harness/adapters/subsim.py`.
- Truth is allowed in evaluation artifacts and scoring only; truth must not be exposed inside perceived frames.
- Campaign promotion requires ReadyPlayer1 before/after evidence. Learned or shadow lanes are advisory only.

## Preflight Evidence

- SubSim full tests: `48 passed in 45.41s`.
- SubSim eval scaffolding: pass, 1 case file.
- Deterministic trace: `reports/preflight_subsim_skirmish_seed7_trace.json`, 180 frames, seed 7, 6 seconds.
- Initial deterministic trace attempt failed only because `reports/` was absent; rerun passed after creating the directory.
- ReadyPlayer1 live preflight reported SubSim harness status `ready`.
- ReadyPlayer1 full belief baseline suite on seed 7 passed golden regression but showed one scenario expectation failure: `clutter_false_positive`.

## Campaign 001 Candidate

Smallest high-leverage target: sonar contact readability under clutter.

Before metric anchor from ReadyPlayer1:

- Scenario: `clutter_false_positive`
- Lane: `belief_baseline`
- `sonar_false_positive_rate`: `0.5`
- `sonar_track_persistence_ratio`: `1.0`
- `sonar_action_thrash`: `4`
- Failure labels: `clutter_binding_error`, `false_positive_persistence`, `overconfident_weak_contact_continuity`, `binding_ambiguity_abandonment`

No gameplay change has been applied in this preflight.
