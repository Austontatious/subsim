# Public Readiness Report

## Overall assessment

SubSim presents as a credible active prototype: the repository contains a deterministic playable desktop simulation, a Godot/Android parity surface, an acoustic evaluation pipeline, tests, architecture records, and honest limitation reporting. It is suitable for technical review once the accumulated local work is committed and visible on GitHub.

## First-screen assessment

The README quickly identifies the project as an audio-first submarine skirmish prototype, lists current capabilities, and provides runnable desktop, headless, acoustic, release, and Android paths. The project is clearly a working prototype rather than a production-ready game.

## Credibility concerns

- Godot remains a simplified mobile playback/playtest surface rather than a complete port of the Python simulation.
- Acoustic content is still partly procedural and listening quality lacks an objective CI gate.
- Generated renderer previews and Android device captures remain local under ignored `artifacts/`; durable summaries remain under `docs/` and `reports/`.
- Hydrophone source licensing is tracked in `reports/hydrophone/license_review.md`; raw source audio remains excluded from Git.
- Watkins/WMMS-derived feature tables and renderer parameters were approved by the project owner for publication as personal/research assets. `THIRD_PARTY_DATA.md` excludes them from the software's MIT grant, records required attribution, and does not grant commercial reuse.
- Historical Campaign 001 planning documents are retained with explicit status headers because later campaigns superseded them.

## Branch/public visibility check

The accumulated work is on the local `android` branch, tracking `origin/android`. GitHub's default branch is `main`, so visitors will not see this work on the repository landing page until it is merged or the default branch is changed.

## Suggested next improvements

1. Review and merge the published `android` branch into the public default branch.
2. Run a clean-clone CI install using the `dev` and `hydrophone` extras.
3. Complete physical-device acoustic/touch QA and rebuild release artifacts from the published revision.
4. Reconcile the current Campaign 005 fire-control work with ReadyPlayer1 evaluation evidence.

## Cleanup and validation record

- Ignored local generated preview/device artifacts without deleting them.
- Removed a machine-specific Android debug-keystore path from the export preset.
- Added a hydrophone dependency extra and installed it in the full CI test job.
- Replaced machine-specific Godot executable paths in public run instructions.
- Clean dependency install: `.venv/bin/pip install -e '.[dev,hydrophone]'` passed.
- Repository guard and full `.venv` suite: `65 passed`; headless smoke, asset checks, AST parsing, and banned-phrase checks passed.
- Standards tests: `9 passed`.
- Eval scaffold, Godot editor load, staged JSON/JSONL validation, staged secret-pattern scan, agent-policy lint, and `git diff --check`: passed.
