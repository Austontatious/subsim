# SubSim – Godot Android Frontend (android branch)

This is a Godot 4 frontend that drives a stub engine at a fixed 30 FPS and now
includes a real acoustic playback layer. It remains a parity surface for
Android/mobile validation while the desktop Python runtime stays canonical.

Quick start
- Open `godot/` in Godot 4.2+.
- Run the scene (`Main.tscn`). You should see a sonar battlespace with two semi-transparent control dials.
- Physics tick is fixed to 30 FPS and calls `engine.step(1/30)` each frame.

Acoustic playback (current)
- `Main.tscn` includes `AcousticMixer`.
- `AcousticMixer` renders:
  - foundational beds (ambient + self-noise + player hum)
  - passive contact loops (`mix_contact`)
  - ping / fire / return cues (`sfx_ping`, `sfx_fire`, `sfx_return`)
- Audio content is placeholder/procedural and synced from desktop generation:
  - `../scripts/sync_godot_audio_assets.sh`

Mobile UX (current)
- Background: full-screen sonar battlespace (player centered, contacts as simple glyphs).
- Left dial: Attitude (pitch/roll). Drag vertical for pitch, horizontal for roll.
- Right dial: Heading. Drag to set target heading. Center readout shows target, small readout shows current.
- Bottom strip: always-visible mobile controls + status with larger touch targets.
  - `PING` button: active ping (same path as gesture/keyboard ping).
  - `FIRE` button: launches a simple heading-based torpedo in Godot runtime (ammo/cooldown/active count shown).
- Pinch: zoom battlespace.
- Two-finger tap: ping shortcut (optional), no longer required for discoverability.

Structure
- `main/Main.tscn` – root scene with `main.gd`, `Engine` and `Renderer` nodes.
- `scripts/engine_port/engine.gd` – engine API and early logic.
- `scripts/audio/acoustic_mixer.gd` – Godot playback layer for substrate cues.
- `scripts/renderer.gd` – minimal 2D visualization placeholder.
- `scripts/ui/` – dial + overlay UI controls.
- `shaders/` – sonar sweep + contact glyph shaders.

Next steps
- Continue parity work against desktop event taxonomy and occlusion semantics.
- Port more core logic from Python as needed.
