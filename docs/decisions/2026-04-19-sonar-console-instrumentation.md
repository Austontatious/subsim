# ADR: Sonar Console Instrumentation Surface

Date: 2026-04-19

## Problem

SubSim lacked a machine-readable perception surface for AI playtesting.
Existing outputs were player-facing (audio/HUD) or mixed traces that did not cleanly separate perceived state from hidden world truth.

## Options Considered

1. Extend game HUD/UI payloads directly for machine consumers.
2. Emit only ground-truth state for playtesting and skip perception modeling.
3. Add a separate testing module with typed contracts for perceived and truth streams.

## Decision

Choose option 3:

- Add `subsim/testing/sonar_console/` as a dedicated testing/instrumentation module.
- Define explicit typed contracts for:
  - perceived frames/tracks/events
  - ownship sensor context
  - ground-truth frames/entities
  - offline track-truth alignment rows
- Keep perceived and truth outputs separate end-to-end (runtime, replay logs, scoring).
- Provide deterministic fixture execution, JSONL replay, scoring helpers, and a playtester consumer stub.

## Rationale

- Preserves gameplay/UI boundaries while enabling AI instrumentation.
- Avoids truth leakage into live machine-perceived inputs.
- Supports deterministic replay and offline analysis from the first implementation.
- Gives ReadyPlayer1 a stable, explicit integration contract with low coupling to game internals.

## Consequences

- New internal interface surface now requires contract stability discipline.
- Additional tests are needed to enforce determinism and stream separation.
- Module currently uses lightweight derived features and should evolve as sensing complexity increases.

## Explicit Deferrals

- No RL training stack integration in this pass.
- No player-facing sonar UI changes in this pass.
- No cross-repo ReadyPlayer1 runtime binding in this pass (stub consumer only).
