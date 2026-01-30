# CODEX_SHEET_SUBSIM — Desktop Python SubSim (Ship + Agent Harness)

## 0) Purpose + Non-Negotiables

Shipping target: Desktop Python version only. Godot folder is ignored for now.

Goal: A shippable, fun, audio-forward submarine tactics game with:

- Modes: Menu / Tutorial / Skirmish / Debrief
- Objective loop: Locate → Classify → Engage/Evade → Extract
- Two “dials” control scheme + two buttons (Ping, Torpedo)
- Deterministic headless runs with trace output + golden replay tests
- Audio event bus (panning + ducking) as the primary UI layer

Important: The repo may not be structured exactly like this today. If it diverges, refactor to match this sheet. This sheet is the source of truth.

## 1) Canonical Architecture (Make It So)

### 1.1 Source of Truth Layout

Use this structure (names can vary slightly if already established, but semantics must match):

```
subsim/
  __main__.py
  game.py              # orchestration: modes, tick loop, emits events, consumes input/actions
  config.py            # tunables + defaults
  scenario.py          # scenario generation + difficulty presets
  objectives.py        # objective state machine + progress evaluation
  replay.py            # trace writer + golden replay loader/runner
  events.py            # event schema + event bus
  audio.py             # consumes events: ducking, panning, earcons, contact loops
  ui.py                # menu/tutorial overlays, HUD widgets, help, keybind hints
  render.py            # 2D tactical display; must support headless mode (no GL resources)
  input.py             # optional: maps keyboard to the “two dials” + buttons abstraction
  engine/              # (optional) sim core, if you want to isolate it
    world.py
    sensors.py
    contacts.py
    weapons.py
    ai.py

tests/
  test_replay.py
  golden/
    skirmish_seed_7.json
```

If files already exist with different names, migrate them into this conceptual layout:

- Don’t break imports without updating all call sites.
- Leave compatibility shims only if unavoidable, but prefer direct refactor.

## 2) Game Loop + Modes (Canonical Behavior)

### 2.1 game.py Responsibilities

game.py must be the single orchestration layer:

- Creates initial world + scenario
- Owns the mode machine: MenuMode, TutorialMode, SkirmishMode, DebriefMode
- Per tick:
  - collect inputs (keyboard or agent)
  - convert to canonical Action (two dials + buttons)
  - step sim
  - update objectives
  - emit events (contacts/ping/weapons/objective/UI)
  - render (unless headless)
  - update audio (event consumer)

### 2.2 Canonical Action Interface (“Two Dials + Two Buttons”)

Define a single action object used everywhere (UI, agents, replay):

```python
@dataclass
class Action:
    heading_deg: float        # 0..360 dial
    pitch: float              # -1..+1 dial (maps to dive planes/depth rate)
    roll: float               # -1..+1 dial (optional; if unused, keep but ignore)
    ping: bool                # button
    torpedo: bool             # button
```

Rules:

- Heading wraps 0..360
- Pitch/roll clamped -1..+1
- ping and torpedo are edge-triggered (press events) unless explicitly held

If the sim currently uses throttle/rudder/depth directly, adapt:

- keep internal physics inputs, but expose canonical Action at the outer boundary.

## 3) Fire Control MVP (Two-Step Torpedo, Cheap + Fun)

Implement the two-step torpedo process (MVP), fire-and-forget:

### 3.1 Behavior

First torpedo press: Compute/enter solution mode for the currently locked contact (or best contact).

Game emits FIRE_SOLUTION_START event and begins an audio cadence indicating the “window.”

Second torpedo press within the time window: launches torpedo.

Accuracy is a function of:

- contact solution quality (belief/confidence)
- timing error vs the cue

### 3.2 Events

Add events (names can vary but must be stable):

- FIRE_SOLUTION_START
- FIRE_SOLUTION_READY
- FIRE_SOLUTION_MISS (early/late)
- TORP_LAUNCH
- TORP_IN_WATER
- TORP_HIT / DETONATION

## 4) Audio Event Bus Contract (Non-Negotiable)

### 4.1 events.py Schema

Define a minimal stable event schema:

```python
@dataclass
class GameEvent:
    t: float                 # sim time
    type: str                # enum-like strings
    bearing_deg: float | None
    distance_norm: float | None
    priority: int            # 0..100 (ducking)
    payload: dict            # freeform details
```

### 4.2 audio.py

Must:

- Apply panning based on bearing
- Apply ducking based on priority (alerts duck ambience)
- Implement UI earcons
- Implement per-contact loops (optional MVP: just earcons + ping returns + threat tone)

### 4.3 Headless Mode

When --headless:

- Audio should not hard-fail if device missing
- Should still “consume” events (no exceptions) and optionally log mix decisions

## 5) Deterministic Replay + Golden Tests (Must Exist)

### 5.1 Trace Format

Trace contains:

- seed, difficulty, tick rate
- per tick: action + key game events + minimal sim state (positions, contacts summary, objectives)

### 5.2 replay.py

Must support:

- --trace out.json --ticks N --seed S --difficulty D
- --replay golden.json to reproduce
- A “golden compare” that tolerates tiny float drift but catches logic regressions

### 5.3 Tests

tests/test_replay.py must:

- run headless for seed=7 for N ticks
- compare to tests/golden/skirmish_seed_7.json
- fail with a readable diff summary if mismatch

If goldens need regeneration, add:

```
python -m subsim --headless --seed 7 --difficulty normal --ticks N --trace tests/golden/skirmish_seed_7.json
```

and document it in PROJECT_MEMORY.md.

## 6) UI/UX Requirements (Desktop Polish)

### 6.1 Controls (Keyboard)

Provide standard bindings (overrideable later):

- Heading dial: A/D or left/right adjusts heading; Q/E fine adjust
- Pitch dial: W/S adjust pitch (dive/climb); optional roll on Z/C
- Ping: Space
- Torpedo: T
- Cycle/lock contact: Tab / Enter
- Help overlay: H
- Pause/menu: Esc

UI must display:

- heading dial value
- pitch/roll dial values
- ping cooldown
- torpedo state (idle / solution-mode / ready / fired)
- objective progress
- contact list with confidence values

### 6.2 Headless Renderer Guard

render.py must not create GL/pygame window resources when headless.

## 7) Scenario Generator + Objective Loop (Replayable Fun)

### 7.1 scenario.py

Must:

- accept seed
- produce initial world state (player + contacts + environment)
- difficulty presets: easy/normal/hard
- guarantee at least 1 meaningful objective path

### 7.2 objectives.py

Implements Locate→Classify→Engage/Evade→Extract:

- Locate: detect contact above threshold
- Classify: classification confidence threshold
- Engage/Evade: either destroy target OR remain undetected for X time while reaching extraction zone
- Extract: reach exit region

Emit objective events:

- OBJECTIVE_STAGE_ADVANCE
- OBJECTIVE_COMPLETE
- OBJECTIVE_FAIL

## 8) Agent Harness (Foundation for “Playtest SaaS”)

Implement an in-process agent interface (no vision required):

### 8.1 agents/base.py

```python
class Agent:
    def reset(self, obs: dict) -> None: ...
    def act(self, obs: dict) -> Action: ...
```

### 8.2 agents/baseline.py

A competent baseline:

- keep speed moderate (stealth)
- if no contact: slow patrol + periodic ping
- if contact detected but low confidence: ping when safe
- if hostile classified: enter fire-solution loop and shoot
- if torp detected: decoy + evade + silent running

### 8.3 CLI Integration

Add:

- --agent baseline to run the agent in place of keyboard input
- Agent runs in headless mode by default unless --render is set

This becomes the backbone of SaaS playtesting later.

## 9) Docs + Release Hygiene (Already Started — Ensure Consistency)

Repo root must include:

- AGENT.md — operational rules + how to run tests/build + architecture summary
- README.md — user-facing instructions + controls
- PROJECT_MEMORY.md — append-only decisions and state
- QA_RUNBOOK.md — manual smoke checklist
- LICENSE — MIT
- CHANGELOG.md

## 10) Acceptance Criteria (Ship Gate)

A “ship candidate” satisfies:

- python -m subsim launches menu, tutorial works end-to-end, skirmish playable
- Audio panning + ducking works; game is playable by sound
- Headless: python -m subsim --headless --seed 7 --ticks 300 --trace out.json succeeds
- pytest -q passes, including golden replay test
- Release script produces a runnable zip
- No crashes in a 30-minute soak run (agent baseline ok)

## 11) If Current Code Differs (Refactor Rules)

If existing code:

- doesn’t have Action as defined → create adapters, then migrate call sites
- emits ad-hoc audio calls → route through event bus
- mixes rendering with sim step → separate concerns in game.py
- lacks deterministic seeding → thread seed through scenario/world/sensors/AI
- headless breaks due to graphics init → guard early and ensure tests run headless

This sheet overrides prior design; align implementation to match.

## 12) Execution Order (Do It In This Sequence)

- Normalize structure + imports + canonical Action interface
- Ensure modes run (Menu/Tutorial/Skirmish/Debrief)
- Event bus is the only audio UI path
- Implement two-step fire control MVP
- Deterministic replay trace + golden test pass
- Baseline agent harness + CLI integration
- UI polish + help overlay
- Packaging + release zip + QA runbook update
- CI: pytest + golden tests in headless
