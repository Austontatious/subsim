# Project Memory

## 2026-05-07 — SubSim x ReadyPlayer1 Campaign Ledger Checkpoint

### Current closed-loop architecture
- Codex changes SubSim only through bounded, reviewable patches.
- ReadyPlayer1 evaluates with deterministic SubSim sonar-console replay/live harnesses.
- Promotion requires contract evidence: scenario id, seed, SubSim revision/worktree marker, ReadyPlayer1 revision/worktree marker, evaluator lane, metrics, replay/run artifacts, failure taxonomy, and explicit promote/hold/reject decision.
- Baseline evaluator lanes remain authoritative; learned/shadow lanes are not promotion authority.

### Promoted campaigns
- Preflight: established the gated SubSim x ReadyPlayer1 evaluation loop. Validation included SubSim full tests, ReadyPlayer1 focused SubSim evaluation tests, standards tests in both repos, live preflight ready, golden regression pass, and initial scenario expectations at `6 pass / 1 fail`.
- Campaign 001: `CAMPAIGN_001_PROMOTED`. Weak passive-only clutter now has damped displayed confidence/contact quality, `possible_contact` / `suspect_contact` labels, clutter rejection for persistent unconfirmed weak contacts, and rejected clutter dropped from later policy observations.
- Campaign 002A: `CAMPAIGN_002A_PROMOTED`. Sonar contacts now emit explicit lifecycle states: `possible`, `suspect`, `tracking`, `confirmed`, `rejected`, and `lost`.
- Campaign 003: `CAMPAIGN_003_PROMOTED`. ReadyPlayer1 now separates raw weak contact detections from primary-track candidates, preventing weak clutter from becoming the tactical primary while preserving raw false-positive visibility.
- Campaign 003 acoustic clutter integration: promoted as an evidence expansion using SubSim hydrophone fixture exports. ReadyPlayer1 scores heldout acoustic clutter binding while using fixture labels only for fixture construction/scoring, not policy truth.
- Campaign 004A: `CAMPAIGN_004A_PROMOTED`. ReadyPlayer1 improved the torpedo/fire-control feedback loop by adding explicit fire-control decision rationale, duplicate same-primary torpedo suppression, and deterministic fire-control metrics. No SubSim gameplay or torpedo physics code changed.

### Current trusted metrics
- Campaign 001 moved `clutter_false_positive` under `belief_baseline`, seed `7`: `sonar_false_positive_rate 0.5 -> 0.2857142857142857`, `sonar_clutter_false_positive_persistence_s 1.0 -> 0.4`, `sonar_clutter_overconfident_weak_contact_rate 1.0 -> 0.0`, scenario suite `6 pass / 1 fail -> 7 pass / 0 fail`, golden regression stayed pass.
- Campaign 002A preserved Campaign 001 gains and moved `sonar_binding_ambiguity_abandonment_rate 1.0 -> 0.0`; new lifecycle metrics include `sonar_uncertain_contact_decay_s=0.39999999999999997` and `sonar_stale_track_clearance_s=0.20000000000000007`.
- Campaign 003 preserved Campaign 001/002A gains and moved `sonar_clutter_wrong_binding_rate 0.2 -> 0.0`, `sonar_binding_wrong_contact_step_rate 0.2 -> 0.0`, and `sonar_action_thrash 4 -> 2` on `clutter_false_positive`.
- Campaign 003 acoustic heldout gate moved `acoustic_clutter_wrong_binding_rate 1.0 -> 0.0`, `acoustic_biologic_wrong_primary_rate 1.0 -> 0.0`, `acoustic_ambient_wrong_primary_rate 1.0 -> 0.0`, and preserved `acoustic_surface_contact_missed_track_rate=0.0`.
- Campaign 004A preserved sonar gains and moved `clean_single_contact_tracking` fire-control behavior: `torpedo_count 2 -> 1`, `torpedo_duplicate_same_track_count 1 -> 0`, and `torpedo_wasted_shot_rate 0.5 -> 0.0`. `clutter_false_positive` stayed at `sonar_clutter_wrong_binding_rate=0.0`, `sonar_clutter_raw_confidence_wrong_binding_rate=0.2`, and `sonar_action_thrash=2`.
- Latest Campaign 004A refresh validation: SubSim full suite `65 passed`; ReadyPlayer1 full suite pass with one skipped marker; ReadyPlayer1 focused fire-control/acoustic tests `20 passed`; scenario suite `7 pass / 0 fail`; golden regression pass; acoustic heldout regression `acoustic_clutter_wrong_binding_rate=0.0`; standards tests `9 passed` in each repo; JSON/JSONL validation pass; `git diff --check` pass in both repos.

### Current evaluator lanes
- Random/baseline lane: preserved for baseline coverage.
- Scripted tactical baseline lane: `belief_baseline` is the current promotion lane.
- Belief-state lane: active through ReadyPlayer1 SubSim sonar evaluation.
- Learned/shadow lane: present for comparison/research, not allowed as sole promotion signal.

### Remaining risks
- Raw first-frame clutter can still briefly outrank a true contact by confidence alone: `sonar_clutter_raw_confidence_wrong_binding_rate=0.2`.
- Primary binding is fixed for the target clutter scenario, but `sonar_true_contact_primary_ratio=0.6` shows the policy still spends time in search/uncertain states before commitment.
- Other suite taxonomy still exposes `timidity_indecision`, `belief_drift`, and `reacquisition_failure`.
- SubSim's live `FireControl` state exists, but ReadyPlayer1 sonar replay observations do not yet normalize that state.

### Recommended next campaign
- Campaign 005A: normalize fire-control readiness/solution state into SubSim sonar observations and ReadyPlayer1 replay/live adapters.
- Goal: expose solution lifecycle and post-shot feedback without changing torpedo physics or reducing tactical uncertainty.

### Inspect first on resume
- `/mnt/data/ReadyPlayer1/reports/campaign_001_comparison.json`
- `/mnt/data/ReadyPlayer1/reports/campaign_002a_comparison.json`
- `/mnt/data/ReadyPlayer1/reports/campaign_002a_promotion_decision.md`
- `/mnt/data/ReadyPlayer1/reports/campaign_003_plan.md`
- `/mnt/data/ReadyPlayer1/reports/campaign_003_comparison.json`
- `/mnt/data/ReadyPlayer1/reports/campaign_003_promotion_decision.md`
- `/mnt/data/ReadyPlayer1/reports/campaign_003_acoustic_clutter/campaign_003_acoustic_clutter_comparison.json`
- `/mnt/data/ReadyPlayer1/reports/campaign_004a_plan.md`
- `/mnt/data/ReadyPlayer1/reports/campaign_004a_comparison.json`
- `/mnt/data/ReadyPlayer1/reports/campaign_004a_promotion_decision.md`
- `/mnt/data/subsim/subsim/testing/sonar_console/perception.py`
- `/mnt/data/subsim/subsim/testing/sonar_console/contracts.py`
- `/mnt/data/ReadyPlayer1/readyplayer1/harness/subsim/sonar_adapter.py`
- `/mnt/data/ReadyPlayer1/readyplayer1/agents/policies/belief_baseline.py`
- `/mnt/data/ReadyPlayer1/readyplayer1/eval/metrics.py`
- `/mnt/data/ReadyPlayer1/readyplayer1/eval/scenarios/subsim/scenario_pack.json`

Date: 2026-01-30

## Current state
- Desktop Python game runs with `pygame` audio + `pyglet` rendering and a fixed-step sim loop.
- Godot Android frontend includes acoustic playback infrastructure (`AcousticMixer`) with passive contact mix, foundational beds, and ping/fire/return earcons.
- Mode system exists (Menu / Tutorial / Skirmish / Debrief) with deterministic headless replay support.
- Engine is isolated in `subsim/engine/` with scenario generator + difficulty presets.
- Objective loop implemented: Locate → Classify → Engage/Evade → Extract.
- Audio event bus provides panning + priority ducking; UI HUD shows contact list, objectives, dials, ping cooldown, and torpedo state.
- Two-dial Action input is canonical; baseline agent harness and golden replay tests exist.

## Key decisions
- Units are meters/seconds; fixed-step sim at 30 FPS (`FRAME_DT`).
- Depth is negative downward; surface clamp near `-5.0`.
- Headings use degrees with 0 deg on +X axis; bearings derived via `atan2(dy, dx)`.
- Audio assets are procedural and referenced by `ASSET_NAMES` and `ASSET_VARIANTS`.
- Canonical input is the two-dial `Action` (heading/pitch + ping/torpedo).

## Known issues / tech debt
- Tutorial and menu flows are functional but need UX polish and stronger audio-guided onboarding.
- HUD layout is functional but still sparse; typography/spacing needs a polish pass.
- Settings/keybind remap and audio sliders are not implemented yet.
- Release packaging is Linux-only and still experimental; Windows/mac not verified.
- Acoustic substrate is still placeholder/procedural for many channels; richer content packs are deferred.

## Roadmap (post-ship)
- Add optional biologics and thermal layer mechanics.
- Add replay export (Captain's Log) and sharing.
- Consider deeper AI behaviors and additional objectives.

## How to resume
- Polish tutorial flow with tighter success gates and more audio cues.
- Improve HUD layout/visual hierarchy and add settings screen.
- Expand audio layering (contact loops, threat warnings) and tune mix.
- Harden packaging/release script and verify on a clean machine.
- Keep golden traces updated when mechanics change.

## Recent changes
- 2026-05-07: Added fixed hydrophone eval manifests and gameplay fixture exports:
  - Added deterministic group-safe split builder under `scripts/hydrophone/build_fixed_eval_splits.py` producing train/validation/heldout source eval JSONL plus split summary/report.
  - Updated classifier training to consume fixed split manifests and report validation vs heldout-source metrics separately.
  - Added SubSim contact fixtures and ReadyPlayer1 acoustic eval case exports under `data/hydrophone/fixtures/`, defaulting to real-only with explicit opt-in synthetic inclusion.
- 2026-05-07: Expanded the bounded hydrophone corpus slice:
  - Added direct small biologic fish sources (`noaa_fish_sounds`, `zenodo_pacama_fish`) and direct NOAA environmental exemplar clips while keeping FishSounds/DeepShip/OceanShip/NOAA NCEI as documented manual paths.
  - Backfilled `group_id` into clip manifests/features and changed classifier evaluation to grouped splitting on `group_id` with reliability warnings and split metadata.
  - Added `reports/hydrophone/license_review.md` and dataset manifest fields for redistribution/commercial-use/license-review status.
- 2026-05-07: Added bounded hydrophone ingestion slice under `data/hydrophone/` and `scripts/hydrophone/`:
  - Introduced dry-run-first dataset sampling manifests for ShipsEar, Watkins, MBARI, NOAA, FishSounds, DeepShip/OceanShip, and synthetic simulation.
  - Added normalization, baseline feature extraction, RandomForest classifier reporting, and safe synthetic wave generation with explicit synthetic-not-real-submarine disclaimers.
  - Added gitignore protections so raw/normalized/features/generated WAV artifacts stay out of git while manifests and reports remain trackable.
- 2026-05-07: Implemented Campaign 001 sonar contact readability under clutter:
  - Added weak passive-only confirmation logic in `subsim/testing/sonar_console/perception.py`.
  - Passive-only contacts now progress through possible/suspect ambiguity with damped displayed confidence, then are rejected as clutter if they fail sustained evidence before confirmation.
  - Added focused sonar-console perception tests for weak clutter rejection, strengthening-contact preservation, and active-ping confirmation.
- 2026-05-07: Documented the SubSim x ReadyPlayer1 closed-loop preflight without gameplay changes:
  - Added `SUBSIM_PROJECT_STATE.md`, closed-loop ship targets, evaluation contract, Campaign 001 plan, and preflight reports.
  - Validated SubSim full tests (`48 passed`) and deterministic seed 7 skirmish trace export under `reports/preflight_subsim_skirmish_seed7_trace.json`.
  - Recorded Campaign 001 before evidence from ReadyPlayer1: `clutter_false_positive` under `belief_baseline` has `sonar_false_positive_rate=0.5` and clutter/binding failure labels.
- 2026-04-24: Fixed Godot mobile control surfaces for discoverable/usable gameplay controls:
  - Increased bottom control-strip touch target sizing (mobile strip now 96..140 px with larger buttons).
  - Added explicit on-screen `PING` button in `ContextStrip` and wired it through `main.gd` to `engine.cmd_ping()`.
  - Updated `FIRE` behavior from SFX-only to real Godot gameplay action by adding a bounded torpedo state model in `godot/scripts/engine_port/engine.gd` (ammo, cooldown, active torpedoes, heading-based launch, simple movement/expiry/contact-hit removal).
  - Added torpedo status reporting in player pose and context strip (`ammo`, `active`, cooldown-driven button state).
  - Added optional torpedo marker rendering in `godot/scripts/battlespace3d.gd` and mobile-control regression tests in `tests/test_godot_mobile_controls.py`.
- 2026-04-24: Integrated HybridAcousticRendererV1 into live desktop runtime with preset-pack control:
  - Added desktop runtime bridge `subsim/runtime_acoustic.py` + preset pack `subsim/runtime_acoustic_presets_v1.json`.
  - Wired `Game._update_audio_mix()` to drive renderer-backed runtime layers and expose `acoustic.runtime_renderer` in observations.
  - Extended `AudioEngine` with external loop playback support for renderer-generated wav caches.
  - Added CLI/runtime controls: `--acoustic-preset` and `--list-acoustic-presets`.
  - Added compact runtime preset pack entries (`low_clutter`, `medium_clutter`, `high_clutter`, `open_ocean_quiet`, `coastal_busy`, `biologics_heavy`).
  - Added first Godot parity hook: `AcousticMixer` now consumes `godot/audio/runtime_acoustic_presets_v1.json` multipliers for foundation/contact shaping.
  - Added runtime integration tests (`tests/test_runtime_acoustic_integration.py`) and updated acoustic observation/Godot wiring tests for runtime fields/preset assets.
- 2026-04-24: Added Renderer Params v1 + first Hybrid Acoustic Renderer v1:
  - Added `subsim/renderer_params_v1.py` to derive renderer-facing family parameters from hydrophone analysis outputs.
  - Added `subsim/renderer_v1.py` first hybrid family generators for `ambient_soundscape`, `marine_mammal_whale`, `marine_mammal_other`, `surface_vessel`, and `intermittent_machinery_archetype`.
  - Added `subsim/renderer_preview_v1.py` preview manifest/report generation and optional waveform/spectrogram preview plotting.
  - Added `tools/renderer_v1_pipeline.py` with `build-params`, `render-previews`, `report`, `validate`, and `run-all`.
  - Generated `dataset/hydrophone/renderer_params_v1.json` (+ `.md`), preview renders in `artifacts/renderer_v1_previews/`, and evaluation reports in `docs/renderer_preview_report.md|json`.
  - Added targeted renderer tests (`tests/test_renderer_params_v1.py`, `tests/test_renderer_v1.py`, `tests/test_renderer_preview_v1.py`) and lazy-imported `subsim.__init__.py` main entrypoint to avoid package-import side effects during tooling runs.
- 2026-04-24: Added `dataset/hydrophone/` Hydrophone Dataset Pull + Acoustic Category Analyzer v1:
  - Added source manifest (`hydrophone_sources_manifest.json`) with bounded subset pulls for WMMS (marine mammals), ShipsEar (ship noise), and MBARI range-sliced soundscape clips, plus metadata-only DCLDE/NOAA references.
  - Implemented one-shot orchestrator `tools/hydrophone_pipeline.py` with stages: `pull`, `normalize`, `features`, `analyze`, `report`, `validate`, `run-all`.
  - Generated normalized index (`hydrophone_dataset_index.jsonl`) with cross-source taxonomy mapping, label quality flags (`exact/coarse/inferred`), and safety buckets.
  - Generated feature tables and clustering artifacts (`features/`, `analysis/`) with renderer-oriented spectral/envelope/cadence traits and abstract safe contact-like archetype tags.
  - Generated renderer-facing reports: `reports/hydrophone_category_analysis_report.md|json` and `reports/hydrophone_dataset_gap_report.md|json`.
  - Added `dataset/hydrophone/README.md`, dependency pin file (`requirements.txt`), and git ignores for large local pull blobs (`raw/`, `downloads/`, `staging/`).
- 2026-04-23: Completed Acoustic Substrate v1 pass:
  - Added canonical cross-surface contract module `subsim/acoustic_contract.py` and docs in `docs/ACOUSTIC_CONTRACT.md`.
  - Expanded desktop substrate with foundational channels (ambient/self-noise/player-hum) and passive timbre variant selection.
  - Fixed desktop passive loop lifecycle so stale/removed contacts are stopped explicitly (prevents phantom contact audio).
  - Wired Godot frontend playback layer via `godot/scripts/audio/acoustic_mixer.gd` and `Main.tscn` node integration; added active return cue signal in `godot/scripts/engine_port/engine.gd`.
  - Aligned Godot passive variant selection to contract inputs (confidence + own-noise + inferred occlusion) instead of gain-only buckets.
  - Added integrity tests for Godot playback wiring/assets and contract-doc synchronization.
  - Synced acoustic assets into `godot/audio/sfx/` and added `scripts/sync_godot_audio_assets.sh`.
  - Updated observations and sonar-console alignment to consume shared acoustic semantics.
  - Added validation tests: `tests/test_acoustic_contract.py`, `tests/test_game_acoustic_observation.py`, `tests/test_godot_acoustic_wiring.py`, `tests/test_acoustic_contract_docs_sync.py`.
- 2026-04-19: Added `subsim/testing/sonar_console` machine-readable instrumentation module with typed perceived/truth contracts, deterministic fixture runner, JSONL replay, scoring metrics, and a ReadyPlayer1-style consumer stub; added ADR at `docs/decisions/2026-04-19-sonar-console-instrumentation.md`.
- 2026-04-19: Fixed packaging discovery to include `subsim.*` so non-editable installs run without `ModuleNotFoundError`; updated quit key to `X` to remove conflict with fine heading `Q`; added regression test for keymap overlap.
- 2026-01-30: Added desktop-focused docs, CI workflow, and release build script.
- 2026-01-30: Added mode system, objective loop, event bus with audio ducking, scenario generator, and replay tracing.
- 2026-01-30: Added headless QA flags, tuning pass, HUD/help/pause overlays, replay golden refresh, and packaging fixes.
- 2026-01-30: Refactored to engine/ layout, two-dial Action input, agent harness, fire-control MVP, and replay trace format.
- 2026-01-30: Canonical CODEX sheet added, replay/golden tests updated, and UI now shows dial values, torpedo state, ping cooldown, and contact confidence.
- 2026-01-30: Updated documentation and QA runbook to match two-dial controls and headless flags.
