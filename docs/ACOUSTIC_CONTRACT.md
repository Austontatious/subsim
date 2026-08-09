# SubSim Acoustic Contract

Version: `acoustic-substrate.v1`
Last updated: 2026-04-24

## Purpose
Define one canonical acoustic substrate across:
- Desktop runtime mix (`subsim/audio.py`)
- Godot/APK frontend playback (`godot/scripts/audio/acoustic_mixer.gd`)
- Machine-facing consumers (`Game.build_observation()`, `subsim/testing/sonar_console`)

This contract separates:
- Sim truth (physics/sensor state)
- Perception abstraction (agent/playtester-facing)
- Presentation/mix behavior (desktop and Godot playback)

## Canonical schema
Python contract source of truth:
- `subsim/acoustic_contract.py`
- `SCHEMA_VERSION = "acoustic-substrate.v1"`

Core structures:
- `AcousticFoundationState`
  - `ambient_level`
  - `self_noise_level`
  - `player_hum_level`
  - `own_noise`
  - `own_noise_bucket` (`low|medium|high`)
  - `sensor_noise`
  - `ping_active`
  - `masking`
- `AcousticContactState`
  - `contact_id`
  - `kind`
  - `bearing_deg`
  - `distance_m`
  - `confidence`
  - `gain`
  - `occlusion_layers`
  - `own_noise`
  - `variant` (`clean|lp1|lp2|lp3`)
  - `source_channels`

Event cue taxonomy:
- `PING`
- `RETURN`
- `CONTACT_NEW`
- `FIRE_SOLUTION_START`
- `FIRE_SOLUTION_READY`
- `FIRE_SOLUTION_MISS`
- `TORP_LAUNCH`
- `TORP_IN_WATER`
- `TORP_HIT`
- `DETONATION`
- `UI_CONFIRM`
- `UI_ALERT`
- `OBJECTIVE_STAGE_ADVANCE`
- `OBJECTIVE_COMPLETE`
- `OBJECTIVE_FAIL`
- `MODE_CHANGE`

Runtime renderer envelope (desktop-first integration):
- `acoustic.runtime_renderer.schema_version` (`runtime-acoustic.v1`)
- `acoustic.runtime_renderer.preset_name`
- `acoustic.runtime_renderer.enabled`
- `acoustic.runtime_renderer.desktop_runtime_active`
- `acoustic.runtime_renderer.foundation_profile`
- `acoustic.runtime_renderer.layer_gains`
- `acoustic.runtime_renderer.families`

## Update cadence
- Sim tick cadence: fixed-step `30 FPS`.
- Passive/contact acoustic state: recomputed every sim step.
- Foundation state: recomputed every sim step.
- Event cues: emitted on action/objective/weapon transitions and consumed in the same runtime tick path.

## Surface mappings

### Desktop runtime
- Source:
  - `subsim/game.py` builds foundation/contact acoustic state.
  - `subsim/runtime_acoustic.py` resolves runtime preset pack + HybridAcousticRendererV1 family layers.
  - `subsim/audio.py` renders:
    - ambient bed
    - self-noise bed
    - player hum bed
    - per-contact passive loops
    - HybridAcousticRendererV1 runtime family loops (cached wav layers)
    - event earcons (ping/return/fire/weapon/UI cues)
- Contact variant selection:
  - `pick_contact_variant(confidence, occlusion_layers, own_noise)`

### Godot/APK frontend
- Source:
  - `godot/scripts/engine_port/engine.gd` emits:
    - `mix_contact(id, pan_l, pan_r, gain)`
    - `sfx_ping()`
    - `sfx_fire()`
    - `sfx_return(id, bearing_deg, distance_m, strength)`
  - `godot/scripts/audio/acoustic_mixer.gd` renders:
    - foundational beds
    - passive contact loops
    - contract-aligned passive variant selection from confidence + own-noise + inferred occlusion
    - first parity hook for runtime preset multipliers from `res://audio/runtime_acoustic_presets_v1.json`
    - ping/fire/return cues
- Scene integration:
  - `godot/main/Main.tscn` contains `AcousticMixer`.

### RL/playtester surfaces
- `Game.build_observation()` now includes:
  - `acoustic.schema_version`
  - `acoustic.foundation`
  - `acoustic.contacts`
  - `acoustic.runtime_renderer`
- Sonar console alignment:
  - `subsim/testing/sonar_console/console.py` uses `build_foundation_state` for `OwnshipSensorContext` bucket/masking semantics.
- Note:
  - RL/playtester consumes abstract acoustic/perception state, not literal waveform buffers.

## Parity expectations
- Required parity:
  - passive contact emission semantics
  - foundation channel semantics
  - ping/fire/return cue families
  - contact variant families (`clean/lp1/lp2/lp3`)
- Allowed differences:
  - exact mixer implementation details
  - exact gain curve tuning per surface
  - device-dependent playback characteristics

## Known parity gaps (v1)
- Desktop has richer event taxonomy (`TORP_HIT`, `DETONATION`, objective/UI cues) than current Godot engine stub.
- Desktop runtime uses full HybridAcousticRendererV1 layer rendering; Godot currently consumes only shared preset multipliers (not full family synthesis output) as the first parity hook.
- Godot mobile now has explicit on-screen `PING`/`FIRE` controls, and `FIRE` launches a simplified heading-based torpedo model with ammo/cooldown tracking; it still does not implement desktop fire-control solution windows/locking semantics.
- Godot contact mix currently derives from frontend engine stub, not full desktop world contacts/weapon systems.
- Godot frontend infers coarse occlusion from weak/uncertain signals because the engine stub does not emit explicit occlusion layers.
- RL/playtester still consumes abstracted tracks; no waveform-level policy input in v1.

## Change discipline
- Any schema field rename/removal requires:
  - contract doc update
  - tests update
  - compatibility note in `PROJECT_MEMORY.md`
- New event cue types should be appended (not silently repurposed) and reflected in all relevant surfaces.
