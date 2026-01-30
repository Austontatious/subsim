# QA Runbook (10-minute smoke test)

Date: 2026-01-30

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
