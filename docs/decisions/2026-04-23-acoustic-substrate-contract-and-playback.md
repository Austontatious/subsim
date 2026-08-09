# ADR: Acoustic Substrate Contract and Godot Playback Layer

Date: 2026-04-23
Status: Accepted

## Problem
SubSim had an asymmetric acoustic state:
- Desktop runtime generated passive/contact acoustic state and played audio.
- Godot/APK frontend emitted acoustic-like signals but had no actual playback layer.
- RL/playtester path consumed abstract sonar features that could drift from player-facing semantics.

This made "audio-first" true in desktop intent, but inconsistent across surfaces.

## Decision
Adopt a shared acoustic contract and implement a real Godot playback layer in the same pass.

### 1) Canonical contract
- Add `subsim/acoustic_contract.py` as the typed source of truth for:
  - foundation state
  - contact acoustic state
  - variant selection rules
  - event taxonomy
- Add `docs/ACOUSTIC_CONTRACT.md` as the human-readable contract surface.

### 2) Desktop substrate expansion
- Extend desktop mix with foundational channels:
  - ambient bed
  - self-noise bed
  - player hum bed
- Keep passive contact loops and add contract-driven variant selection (`clean/lp1/lp2/lp3`).

### 3) Godot/APK playback implementation
- Add `godot/scripts/audio/acoustic_mixer.gd` and scene integration in `godot/main/Main.tscn`.
- Route `mix_contact`, `sfx_ping`, `sfx_fire`, and `sfx_return` into actual playback nodes.
- Add active return cue signal in `godot/scripts/engine_port/engine.gd`.

### 4) RL/playtester alignment
- Use shared foundation semantics in sonar console (`build_foundation_state`).
- Expose `acoustic` envelope in `Game.build_observation()`.

## Consequences
Positive:
- Frontend APK path is no longer structurally silent.
- Desktop, Godot, and playtester paths align to one acoustic model.
- Contract drift risk is reduced and testable.

Tradeoffs:
- Godot frontend still uses a stub simulation engine and procedural/placeholder assets.
- Full cue parity with desktop objective/weapon richness is not yet complete.

## Explicit deferrals
- No waveform-level RL policy input in this pass.
- No premium content pack requirement in this pass.
- No full clutter/biologics acoustic redesign in this pass.
