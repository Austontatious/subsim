# ADR: Hybrid Runtime Acoustic Integration v1 (Desktop-first + Preset Pack)

Date: 2026-04-24
Status: Accepted

## Problem
SubSim had a working offline hybrid renderer preview pipeline, but live runtime playback still depended mostly on foundational beds and deterministic contact loops. This created a gap between analyzed hydrophone-derived synthesis capability and in-game acoustic world richness.

A second gap existed across surfaces:
- Desktop runtime could host renderer-driven families now.
- Godot/APK path needed parity progress without blocking desktop integration.

## Options Considered

1. Keep renderer isolated as an offline preview tool and continue dataset pulls first.
2. Fully replace runtime audio paths with renderer output in one pass across desktop and Godot.
3. Integrate renderer into desktop runtime first, preserve tactical cue channels, and add a compact shared preset pack with a first Godot parity hook.

## Decision
Choose option 3.

- Integrate `RuntimeHybridLayerV1` into desktop `Game._update_audio_mix()` and `AudioEngine`.
- Activate five high-value runtime families:
  - `ambient_soundscape`
  - `marine_mammal_whale`
  - `marine_mammal_other`
  - `surface_vessel`
  - `intermittent_machinery_archetype`
- Keep tactical/event cues explicit and renderer-independent.
- Add `runtime_acoustic_presets_v1.json` for clutter density/style control.
- Add CLI/runtime control path (`--acoustic-preset`, `--list-acoustic-presets`).
- Expose runtime renderer state in observation contract (`acoustic.runtime_renderer`).
- Add first Godot parity hook by consuming shared preset multipliers (`godot/audio/runtime_acoustic_presets_v1.json`) in `AcousticMixer`.

## Rationale
- Desktop-first integration delivers immediate gameplay value with lowest validation friction.
- Presets provide reproducible scene tuning for QA, balancing, and scenario setup.
- Preserving explicit tactical cues avoids regressing clarity in core gameplay loops.
- Godot parity is advanced with a shared configuration surface now, while deferring full renderer-loop parity to a follow-on pass.

## Consequences
Positive:
- Runtime world is materially richer using analyzed renderer families.
- Clutter density and masking character are now controllable via compact presets.
- Observation surfaces now expose renderer runtime state for machine-facing consumers.

Tradeoffs:
- Godot uses preset-based shaping but does not yet consume desktop renderer loop assets directly.
- Perceptual quality evaluation remains primarily listening-based in v1.

## Explicit Deferrals
- No nation/class-specific submarine signature rendering.
- No full Godot waveform parity with desktop renderer loop cache in this pass.
- No complete replacement of all existing deterministic/tactical cues.
