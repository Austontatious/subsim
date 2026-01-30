# Project Memory

Date: 2026-01-30

## Current state
- Desktop Python game runs with `pygame` audio + `pyglet` rendering and a fixed-step sim loop.
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
- Audio layering beyond core earcons is minimal (no advanced per-contact loops yet).

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
- 2026-01-30: Added desktop-focused docs, CI workflow, and release build script.
- 2026-01-30: Added mode system, objective loop, event bus with audio ducking, scenario generator, and replay tracing.
- 2026-01-30: Added headless QA flags, tuning pass, HUD/help/pause overlays, replay golden refresh, and packaging fixes.
- 2026-01-30: Refactored to engine/ layout, two-dial Action input, agent harness, fire-control MVP, and replay trace format.
- 2026-01-30: Canonical CODEX sheet added, replay/golden tests updated, and UI now shows dial values, torpedo state, ping cooldown, and contact confidence.
- 2026-01-30: Updated documentation and QA runbook to match two-dial controls and headless flags.
