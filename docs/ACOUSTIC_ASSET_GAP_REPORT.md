# Acoustic Asset Gap Report

Date: 2026-04-23
Scope: SubSim Acoustic Substrate v1

## Current asset classes (available)
Procedural assets generated in `assets/sfx/` and synced to `godot/audio/sfx/`:
- `ambient`
- `player_hum`
- `merchant`
- `hunter`
- `ping`
- `torpedo`
- `mine`

Per-asset variants:
- `clean`
- `lp1`
- `lp2`
- `lp3`

## What is now covered
- Foundational channels:
  - ambient bed
  - self-noise bed (derived from ambient/own-noise semantics)
  - player hum bed
- Passive contacts:
  - merchant/hunter loop families
  - variant selection by confidence/occlusion/own-noise
- Cue events:
  - ping/return
  - fire/torpedo/mine cue families
  - UI/alert families via ping-derived earcons

## Known thin/placeholder areas
- Many cues are procedural and intentionally synthetic, not recorded marine/library-grade content.
- Ambient class is still a single family (limited biome/environment differentiation).
- Contact classes are coarse (`merchant` vs `hunter`) and do not yet include finer vessel signatures.
- No dedicated cavitation/transient library by throttle regime.
- No layered underwater impulse response / reverberation model.
- No stochastic machinery fault/anomaly signatures.

## Asset strategy (non-blocking progression)
Short-term (keep velocity):
- Continue procedural base + variant mapping for deterministic development.
- Keep desktop/Godot parity through shared asset names and variant semantics.
- Use `scripts/sync_godot_audio_assets.sh` as canonical sync step before export.

Medium-term (high leverage additions):
1. Add 3-5 ambient beds (open ocean, littoral, storm, harbor, thermal inversion heavy).
2. Add vessel-subclass signatures (diesel cargo, fast patrol, submarine classes).
3. Add propulsion regime layers (idle, cruise, flank) keyed to own-noise/telegraph.
4. Add torpedo/mine transient packs with range-filtered variants.
5. Add UX cue packs for objective/alert states to reduce ping overloading.

## Priority recommendation
Highest immediate realism gain per effort:
1. Ambient bed diversity.
2. Propulsion/self-noise regime layers.
3. Contact signature subclass expansion.
