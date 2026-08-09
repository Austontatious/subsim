# Campaign 001 Plan

> Status: SUPERSEDED. Campaign 001 was promoted and followed by later campaigns; retain this document as the original preflight plan. See `PROJECT_MEMORY.md` for the latest campaign ledger.

Status: preflight documented, implementation not started

## Problem Statement

The current evaluation loop is runnable and the strongest before signal is clutter readability. The seed 7 ReadyPlayer1 `belief_baseline` suite passes golden regression overall, but `clutter_false_positive` fails its scenario expectation with a `sonar_false_positive_rate` of `0.5`.

The target is not to make the evaluator easier. The target is to make SubSim's sonar contact surface more legible under clutter while preserving deterministic traces and truth/perceived separation.

## Target Files

Likely SubSim files:

- `subsim/testing/sonar_console/perception.py`
- `subsim/testing/sonar_console/contracts.py`
- `subsim/testing/sonar_console/scoring.py`
- `subsim/testing/sonar_console/tests/test_replay_scoring.py`
- `tests/test_game_acoustic_observation.py`

ReadyPlayer1 files should remain evaluation-only unless a contract/reporting bug is found:

- `readyplayer1/eval/subsim_suite.py`
- `readyplayer1/eval/failure_taxonomy.py`
- `tests/test_subsim_suite_runner.py`
- `tests/test_subsim_failure_taxonomy.py`

## Before Metrics

Source: `ReadyPlayer1/reports/campaign_001_runs/20260507T143115Z-subsim_suite-677aa9/suite_summary.json`

- Scenario: `clutter_false_positive`
- Seed: `7`
- Lane: `belief_baseline`
- Expectation status: `fail`
- `sonar_false_positive_rate`: `0.5`
- `sonar_track_persistence_ratio`: `1.0`
- `sonar_action_thrash`: `4`
- Failure labels: `clutter_binding_error`, `false_positive_persistence`, `overconfident_weak_contact_continuity`, `binding_ambiguity_abandonment`

Control evidence:

- Full suite expectation counts: `6 pass / 1 fail`
- Golden regression status: `pass`
- Baseline plus shadow smoke: `sequence_stub` was classified `hurt`, proving shadow evidence is advisory and not promotional.

## Patch Plan

1. Add or tune clutter ambiguity handling in the SubSim sonar-console perception path without exposing truth fields in perceived frames.
2. Preserve deterministic seed behavior and JSON-compatible schema output.
3. Add focused tests for clutter ambiguity, false-positive persistence, and no truth leakage.
4. Re-run the exact before suite command with the after SubSim commit.
5. Compare before/after metrics in the campaign report before any promotion decision.

## Expected After Metrics

Minimum target:

- `clutter_false_positive.sonar_false_positive_rate <= 0.35`
- `clutter_false_positive.sonar_action_thrash <= 6`
- `clutter_false_positive.sonar_track_persistence_ratio >= 0.7`
- No new high-severity taxonomy labels in clean, crossing, self-noise, or pressure scenarios.
- Full `belief_baseline` suite golden regression remains `pass`.

Stretch target:

- Remove `overconfident_weak_contact_continuity` from the clutter failure labels.
- Reduce `sonar_clutter_wrong_binding_rate` below `0.2` without increasing missed entities.

## Rollback Plan

- Revert only Campaign 001 SubSim edits.
- Keep generated before/after ReadyPlayer1 reports.
- Re-run SubSim full tests and ReadyPlayer1 seed 7 suite to confirm restoration to pre-campaign metrics.

## Acceptance Criteria

- No deterministic test failures in SubSim.
- ReadyPlayer1 focused SubSim evaluation tests pass.
- ReadyPlayer1 live preflight remains `ready`.
- Before and after suite summaries are linked in `reports/campaign_001_preflight.md` or a campaign implementation report.
- Promotion decision is not based on learned/shadow lanes alone.
- Final status remains blocked from promotion if no after metrics exist.
