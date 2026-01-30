# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project adheres to Semantic Versioning.

## [Unreleased]
### Added
- Mode system with Menu/Tutorial/Skirmish/Debrief.
- Objective loop (Locate → Classify → Engage/Evade → Extract) and scenario generator with difficulty presets.
- Audio event bus with panning + priority ducking and fire-solution events.
- Headless trace/replay harness with golden test support.
- Baseline agent harness and headless QA flags.
- HUD overlays for contact list, objectives, dials, ping cooldown, and torpedo state.

### Changed
- Canonical two-dial Action input throughout the runtime.
- Refactored sim modules into `subsim/engine/`.

## [0.1.0] - 2026-01-30
### Added
- Desktop prototype with world, sensors, contacts, weapons, and AI.
- Procedural audio asset generation and pygame mixer playback.
- Simple pyglet renderer and keyboard input.
- Pytest coverage for core sim logic.
