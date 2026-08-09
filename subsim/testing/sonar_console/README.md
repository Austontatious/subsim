# Sonar Console (Testing Instrumentation)

This module provides a machine-readable sonar console for AI playtesting.
It is instrumentation for test harnesses and replay tooling, not a player UI surface.

## Scope

- Produces a **perceived stream** (`SonarConsoleFrame`) for agent consumption.
- Produces a separate **ground-truth stream** (`GroundTruthFrame`) for offline scoring/debug.
- Writes replayable JSONL logs and supports deterministic replay.
- Includes scoring utilities and a ReadyPlayer1-style consumer stub.

## Boundaries

- Does not depend on rendering code or player-facing HUD.
- Does not expose hidden truth fields in perceived frames.
- Keeps truth mapping (`matched_track_id`) in truth-only outputs.

## Primary Contracts

- `SonarConsoleFrame`
- `PerceivedTrack`
- `OwnshipSensorContext`
- `SonarEvent`
- `GroundTruthFrame`
- `TruthEntity`
- `TrackTruthAlignment`

All contracts are defined in [`contracts.py`](./contracts.py).

## Quick Usage

```python
from pathlib import Path
from subsim.testing.sonar_console import SonarConsole, write_jsonl, score_run

console = SonarConsole()
fixture = console.load_fixture("subsim/testing/sonar_console/fixtures/skirmish_seed_7.json")
run = console.run_fixture(fixture)

log_path = write_jsonl(
    path=Path("tests/tmp/sonar_console_run.jsonl"),
    perceived_frames=run.perceived_frames,
    truth_frames=run.truth_frames,
    actions=run.actions,
)

summary, rows = score_run(
    perceived_frames=run.perceived_frames,
    truth_frames=run.truth_frames,
)
print(log_path, summary.to_dict(), len(rows))
```

## Playtester Stub

`playtester_stub.py` contains `run_stub_playtester`, a tiny consumer that reads perceived frames and keeps a belief state.
This is a handoff example for future ReadyPlayer1 integration.
