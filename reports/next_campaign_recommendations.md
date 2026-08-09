# Next Campaign Recommendations

Generated: 2026-05-07T14:36:23Z

## Campaign 001

Proceed with sonar contact readability under clutter.

Primary evidence:

- `clutter_false_positive` fails scenario expectation under ReadyPlayer1 `belief_baseline`.
- False-positive rate is `0.5`, above the `0.35` threshold.
- Full ReadyPlayer1 suite golden regression still passes, so the loop is stable enough for a bounded patch.

Recommended implementation focus:

- Tune SubSim perceived sonar ambiguity/continuity under clutter.
- Preserve truth/perceived separation.
- Add deterministic tests before touching thresholds or ReadyPlayer1 evaluation expectations.

## Campaign 002 Candidates

After Campaign 001 has before/after evidence:

- Scenario feedback clarity: improve report surfacing for why a scenario failed and which metric drove rejection.
- Replay/metrics determinism: make SubSim trace writing create parent directories or emit a clearer failure, because the first preflight trace failed when `reports/` did not exist.
- Torpedo/fire-control loop: evaluate only after clutter readability is stable, because current clutter false positives could confound engagement metrics.
- Mobile controls parity: defer until the closed-loop desktop/replay gate can separate control-surface issues from sonar perception issues.

## Do Not Advance Yet

- Do not promote learned/shadow lanes.
- Do not change ReadyPlayer1 golden thresholds to make Campaign 001 pass.
- Do not delete preflight run artifacts.
- Do not start Campaign 002 before Campaign 001 has an after suite and a promotion/rejection decision.
