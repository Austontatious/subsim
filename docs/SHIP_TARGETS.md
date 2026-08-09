# Ship Targets

> Status: HISTORICAL. This file records the original Campaign 001 ship target. See `PROJECT_MEMORY.md` for the current campaign ledger and remaining risks.

Updated: 2026-05-07

## Closed-Loop Target

Build a bounded autonomous product lab:

1. Codex proposes and patches a small SubSim campaign change.
2. ReadyPlayer1 evaluates the same scenario ids and seeds before and after.
3. Contract artifacts gate promotion.
4. Reports preserve metrics, taxonomy, traces, and rollback evidence.
5. Campaigns advance only when deterministic gates pass.

## Non-Negotiable Gates

- No SubSim gameplay promotion without before/after ReadyPlayer1 metrics.
- No learned/shadow-only promotion.
- No replacement of deterministic tests with model-judged tests.
- No direct ReadyPlayer1 edits to SubSim gameplay.
- No deletion of run artifacts unless clearly obsolete and documented.
- Baseline evaluator lanes stay runnable.

## Current Ship Target

Campaign 001 targets sonar contact readability under clutter.

Evidence:

- Full `belief_baseline` suite passed golden regression.
- `clutter_false_positive` failed scenario expectations.
- Current false-positive rate is `0.5`, above the scenario threshold of `0.35`.
- Failure taxonomy points at clutter/binding readability rather than raw determinism failure.

## Next Promotion Shape

Campaign 001 may be promoted only if:

- SubSim tests pass.
- ReadyPlayer1 focused evaluation tests pass.
- Full seed 7 `belief_baseline` suite passes golden regression.
- `clutter_false_positive` improves on false positives without protected scenario regressions.
- Shadow/learned lanes are reported as advisory, not decisive.
