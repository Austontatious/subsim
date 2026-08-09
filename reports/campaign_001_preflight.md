# Campaign 001 Preflight

Generated: 2026-05-07T14:36:23Z

Status: `READY_FOR_CAMPAIGN_001_IMPLEMENTATION`

No SubSim gameplay changes were made during this preflight.

## Scope

- SubSim repo: `/mnt/data/subsim`
- ReadyPlayer1 repo: `/mnt/data/ReadyPlayer1`
- SubSim HEAD: `5f12fe898965bf9758731e5036f24cc7af588b2b`
- ReadyPlayer1 HEAD: `e8d5ee9252a532b9f8f49cac64a77e01782f0b10`
- Worktree note: both repos were dirty before this pass.

## Confirmed SubSim Paths

- Tests: `PYTHONPATH=/mnt/data/subsim SDL_AUDIODRIVER=dummy PYGLET_HEADLESS=true python3 -m pytest -q`
- Eval scaffolding: `PYTHONPATH=/mnt/data/subsim SDL_AUDIODRIVER=dummy PYGLET_HEADLESS=true python3 evals/runner.py --check`
- Deterministic trace: `PYTHONPATH=/mnt/data/subsim SDL_AUDIODRIVER=dummy PYGLET_HEADLESS=true python3 -m subsim --scenario skirmish --seed 7 --difficulty normal --ticks 180 --trace reports/preflight_subsim_skirmish_seed7_trace.json --health-check`
- Trace artifact: `reports/preflight_subsim_skirmish_seed7_trace.json`

## Cross-Repo Evaluation Evidence

Canonical ReadyPlayer1 evidence:

- Live preflight: `/mnt/data/ReadyPlayer1/reports/preflight_runs/20260507T143101Z-subsim_live_preflight-fbc26b/subsim_live_harness_preflight_summary.json`
- Full before suite: `/mnt/data/ReadyPlayer1/reports/campaign_001_runs/20260507T143115Z-subsim_suite-677aa9/suite_summary.json`
- Baseline plus shadow smoke: `/mnt/data/ReadyPlayer1/reports/campaign_001_runs/20260507T143139Z-subsim_suite-bf7d4f/suite_summary.json`
- Belief-state variant smoke: `/mnt/data/ReadyPlayer1/reports/campaign_001_runs/20260507T143139Z-subsim_suite-d47f7f/suite_summary.json`

## Before Metrics

Campaign target scenario:

- Scenario: `clutter_false_positive`
- Lane: `belief_baseline`
- Seed: `7`
- Expectation status: `fail`
- `sonar_false_positive_rate`: `0.5`
- `sonar_track_persistence_ratio`: `1.0`
- `sonar_action_thrash`: `4`
- Failure labels: `clutter_binding_error`, `false_positive_persistence`, `overconfident_weak_contact_continuity`, `binding_ambiguity_abandonment`

## Decision

The evaluation loop is working for a bounded first campaign. Campaign 001 may proceed to implementation, but promotion remains `hold` until after metrics exist and the contract gate passes.

Final status: `READY_FOR_CAMPAIGN_001_IMPLEMENTATION`
