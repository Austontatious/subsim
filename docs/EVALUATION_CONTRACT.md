# SubSim x ReadyPlayer1 Evaluation Contract

Contract version: `subsim-rp1-eval-contract.v1`

Owner: ReadyPlayer1 owns evaluator execution and artifact emission. SubSim owns gameplay/runtime behavior being evaluated. Codex may patch SubSim after this contract is satisfied; ReadyPlayer1 must not directly edit SubSim gameplay.

## Required Record

Every campaign evaluation record must include:

```json
{
  "contract_version": "subsim-rp1-eval-contract.v1",
  "scenario_id": "clutter_false_positive",
  "seed": 7,
  "subsim_commit": "5f12fe898965bf9758731e5036f24cc7af588b2b",
  "readyplayer1_commit": "e8d5ee9252a532b9f8f49cac64a77e01782f0b10",
  "evaluator_lane": "belief_baseline",
  "metrics_emitted": {
    "sonar_false_positive_rate": 0.5,
    "sonar_track_persistence_ratio": 1.0,
    "sonar_action_thrash": 4
  },
  "replay_artifact_path": "readyplayer1/eval/scenarios/subsim/replays/clutter_false_positive.jsonl",
  "run_artifact_path": "reports/campaign_001_runs/<suite_run_id>/scenario_runs/<run_id>",
  "failure_taxonomy_output": {
    "primary": "clutter_binding_error",
    "labels": []
  },
  "promotion_decision": "reject|promote|hold",
  "decision_reason": "Before-only preflight; no SubSim gameplay patch promoted."
}
```

## Required Metrics

The suite must preserve these metric families when available:

- Core run metrics: `total_steps`, `duration`, `ping_count`, `torpedo_count`, `objective_complete`, `survived`
- Sonar metrics: `sonar_detection_latency_s`, `sonar_false_positive_rate`, `sonar_track_persistence_ratio`, `sonar_classification_convergence_s`, `sonar_low_confidence_indecision_s`, `sonar_action_thrash`, `sonar_contact_loss_events`, `sonar_reacquisition_events`, `sonar_contact_loss_reacquisition_rate`
- Binding/clutter diagnostics: `sonar_clutter_wrong_binding_rate`, `sonar_clutter_false_positive_persistence_s`, `sonar_clutter_overconfident_weak_contact_rate`, `sonar_clutter_ambiguity_discipline_violations`, `sonar_binding_wrong_contact_persistence_s`, `sonar_binding_weak_contact_overconfidence_rate`, `sonar_binding_ambiguity_abandonment_rate`, `sonar_binding_competing_hypothesis_collapse_rate`

## Evaluator Lanes

- `baseline`: implemented in ReadyPlayer1 as a deterministic baseline policy. It is a low-skill baseline lane and must be preserved.
- `belief_baseline`: implemented in ReadyPlayer1 as the tactical scripted baseline and current primary promotion gate.
- `belief_baseline_contact_binding_v2`: implemented in ReadyPlayer1 as a contact-centric belief-state variant. It can provide comparative evidence but is not the only gate.
- `sequence_stub`: deterministic shadow-lane plumbing. It is advisory only.
- `sequence_model` and `qwen_structured`: learned/model shadow lanes. They require configured model endpoints or explicit fallback behavior and are advisory only.
- `rssm_v2` governed lanes: model-lane operations exist in ReadyPlayer1, but learned/model results cannot be the only promotion signal.

## Promotion Rules

- Promotion requires before and after metrics for the same scenario id, seed, SubSim commit lineage, ReadyPlayer1 commit, lane, and tick budget.
- `belief_baseline` or another preserved non-learned baseline lane must pass regression gates.
- A learned/shadow lane may support a decision but must not be the sole promotion signal.
- A change is rejected if deterministic tests fail, golden regression fails, truth leaks into perceived observations, or failure taxonomy worsens in protected scenarios.
- ReadyPlayer1 artifacts prove; Codex patches; SubSim remains the only gameplay change surface.

## Current Preflight Status

Current preflight contract status is recorded in `reports/evaluation_contract_status.json`. Campaign 001 is before-only and therefore records `promotion_decision: hold` until an after-run exists.
