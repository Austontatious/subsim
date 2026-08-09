# SubSim Acoustic Substrate Completion Report (v1)

Date: 2026-04-23
Contract version: `acoustic-substrate.v1`
Status: `complete_with_known_gaps`

## Scope
Single integrated pass to:
1. Implement real Godot/APK playback.
2. Improve desktop/Godot acoustic parity.
3. Add ambient/self-noise/player-hum foundational channels.
4. Define canonical cross-surface acoustic contract.
5. Audit RL/playtester alignment to the same substrate.
6. Document asset gaps and validation evidence.

## Executive outcome
- Desktop sim continues to generate passive/contact acoustic state and event cues.
- Godot/APK path now has a real playback layer (`AcousticMixer`) and is no longer structurally silent.
- Foundational acoustic bed is implemented (ambient + self-noise + player hum).
- A canonical acoustic contract now exists and is wired across desktop, Godot, and machine-facing observation surfaces.
- RL/playtester still consumes abstract acoustic state (not waveforms), but that state is now explicitly aligned to the same contract.

## Required question answers

### 1) Is audio generation actually happening?
Yes.
- Desktop sim emits passive contact mix and event cues through `subsim/game.py` and `subsim/audio.py`.
- Runtime observation now exposes acoustic state in `Game.build_observation()`:
  - `acoustic.schema_version`
  - `acoustic.foundation`
  - `acoustic.contacts`

Evidence:
- Runtime sanity output on seed 7 after 300 ticks showed:
  - `schema = acoustic-substrate.v1`
  - non-empty `foundation`
  - `contacts_total = 3`, `acoustic_contacts = 3`
  - representative contact with `gain`, `variant`, `occlusion_layers`, `source_channels`.

### 2) Was Android playback broken specifically?
Previously yes due missing playback layer; now addressed.
- Godot engine signals now include and emit:
  - `mix_contact`
  - `sfx_ping`
  - `sfx_fire`
  - `sfx_return`
- `godot/scripts/audio/acoustic_mixer.gd` connects and renders these cues through `AudioStreamPlayer`/`AudioStreamPlayer2D`.
- `godot/main/Main.tscn` now includes `AcousticMixer`.

APK artifact:
- `godot/build/subsim-android.apk`
- size: `28,390,598` bytes
- sha256: `f22f25110371a83704c423c2b538abcba50dc4a3304d50d5157b8cf21b7f69fb`
- rebuilt in this pass (`2026-04-23 14:55:01 -0700`)

Note:
- Physical handset audibility still requires manual device validation.

### 3) Is game logic emitting the right sound cues?
Partially implemented, substantially improved.

Implemented now:
- Passive contact loops with per-contact gain/pan and contract-driven variant semantics (`clean/lp1/lp2/lp3`).
- Desktop contact-loop lifecycle now stops stale/removed contact loops to avoid phantom passive audio.
- Godot passive variant selection now uses contract inputs (confidence + own-noise + inferred occlusion) instead of gain-only buckets.
- Active ping cue and lightweight active return cue in Godot.
- Weapon/UI cue families (desktop richer than Godot stub).
- Foundational acoustic bed:
  - ambient noise floor
  - self-noise layer
  - player hum layer
  - quiet vs elevated own-noise behavior.

Still thin:
- Contact class richness remains coarse.
- Ambient family diversity is limited.
- Many cues are procedural placeholders.
- Full clutter/biologics richness is deferred.

### 4) Is RL/playtester consuming the intended signal?
Yes at abstract-state level; no waveform consumption.
- `Game.build_observation()` now includes canonical acoustic envelope.
- Sonar console ownship context now derives from shared `build_foundation_state`.
- RL/playtester consumes contract-aligned abstractions, not PCM audio buffers.

## Implemented deliverables

### Godot playback layer
- Added: `godot/scripts/audio/acoustic_mixer.gd`
- Updated: `godot/scripts/engine_port/engine.gd` (`sfx_return` + active return scheduling/emission)
- Updated: `godot/main/Main.tscn` (adds `AcousticMixer` node)

### Desktop/Godot parity substrate
- Added canonical contract module: `subsim/acoustic_contract.py`
- Updated desktop audio mixer: `subsim/audio.py`
- Updated game acoustic state build + observation exposure: `subsim/game.py`
- Added/used shared variants and ambient assets: `subsim/config.py`, `subsim/assets.py`

### RL/playtester alignment
- Updated sonar console context semantics:
  - `subsim/testing/sonar_console/console.py`
- Added tests validating contract semantics and observation envelope.

### Contract and strategy docs
- `docs/ACOUSTIC_CONTRACT.md`
- `docs/ACOUSTIC_ASSET_GAP_REPORT.md`
- ADR:
  - `docs/decisions/2026-04-23-acoustic-substrate-contract-and-playback.md`

## Validation performed

Programmatic:
- `pytest -q` -> `38 passed`.
- Wiring checks confirm signal emission/connection and scene node presence.
- Runtime sanity probe confirms non-empty and changing acoustic observation state.
- APK export command completed successfully (debug build).
- Added automated integrity checks for:
  - Godot scene/mixer signal wiring and required asset presence (`tests/test_godot_acoustic_wiring.py`)
  - acoustic contract doc-to-schema/taxonomy synchronization (`tests/test_acoustic_contract_docs_sync.py`)

Manual (required, not executed by CI here):
- Install APK on handset and verify audible:
  - ambient bed
  - passive contact loops
  - ping/fire cues
  - return cues

## Known parity gaps and deferrals
- Godot frontend engine remains a simplified/stub simulation path vs full desktop world model.
- Desktop event taxonomy is richer than current Godot event routing.
- Godot frontend still infers coarse occlusion because the engine stub does not emit explicit occlusion layers.
- No waveform-level RL policy input in this pass.
- No premium content library requirement in this pass.

## Next-step recommendations
1. Add ambient biome diversity packs and propulsion regime layers.
2. Expand contact signature subclasses beyond merchant/hunter coarse classes.
3. Add on-device APK acoustic regression checklist to release QA.
