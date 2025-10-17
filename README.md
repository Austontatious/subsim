# SubSim

Audio-first submarine skirmish prototype. Desktop baseline uses pygame/pyglet; the Android branch adds a Godot 4 frontend while sharing the core simulation model.

- Repo root contains the Python package and tests (`subsim/`, `tests/`).
- `godot/` contains a Godot 4 project for the Android/mobile frontend (also runs on desktop).

## Branches

- `main`: desktop prototype (pygame/pyglet).
- `android`: Godot 4 mobile frontend in `godot/` (work-in-progress).
- `android-sync`: temporary sync branch mirroring `android` at a stable point to avoid local merge conflicts.

## Run (Godot frontend)

Requirements: Godot 4.5.x

1) Checkout `android` (or `android-sync`):

```
git fetch origin
git switch android
# if you have local edits you want to discard
# git reset --hard origin/android
```

2) Open `godot/` in Godot and run `Main.tscn`.

Controls:
- Right compass dial: drag to set target heading; outer ring shows current heading.
- Left telegraph slider: detents −5..5 (REV FULL..AHEAD FULL). A label shows the current detent.
- Near-left depth area: drag vertically to set target depth (0–1000 m).
- Ping: press PING button or Enter/Space.

## Implemented (Android/Godot branch)

- Engine stub (GDScript):
  - Fixed-step kinematics (30 FPS), target depth, bounded turn rate.
  - Telegraph detents mapped to 35 kts Full (−5..5 = Rev/Ahead Full with 1/8, 1/4, 1/2, 3/4).
  - Demo contacts array (moving targets) and passive mix signal plumbing.
  - Active ping event (signal) for earcon/visuals.
- Godot UI/visuals:
  - Compass dial (inner = target, outer = current), mouse + touch support.
  - Telegraph VSlider with label text (REV/AHEAD detents).
  - Depth drag area (simple control; half-dial UI pending).
  - 3D battlespace: translucent cube, blue background, gridlines, pinch/scroll zoom.
  - Sonar ping visuals: expanding translucent spheres with fade-out.

## Not Yet Implemented

- Audio in Godot: per-contact loops, equal-power pan, rolloff, earcons.
- Contact visualization in 3D (billboards, labels, colors by type).
- Engine parity features: occlusion/thermocline, returns, weapons (torpedo/mine), AI behaviors.
- Touch-first depth half-dial with ticks and labels.
- World scale mapping to ~12.8 km cube and scaled ping propagation (speed of sound).
- Android export configuration (SDK/keystore), packaging and device smoke tests.
- Automated tests for the engine logic (pytest for Python still runs on desktop).

## File Layout (Godot)

```
godot/
  project.godot
  default_env.tres           # Blue background clear color
  main/
    Main.tscn
    main.gd                  # Wires UI to engine and 3D
  scripts/
    engine_port/engine.gd    # GDScript engine stub + kinematics
    battlespace3d.gd         # Camera + zoom + ping waves
    gridlines.gd             # Grid/cube edges (ImmediateMesh)
    renderer.gd              # 2D placeholder (TODO expand)
    ui/compass_dial.gd       # Compass dial control (mouse + touch)
  space/
    Battlespace3D.tscn       # Cube + camera + grid instance
```

## Troubleshooting

- Parse error: "Could not find type CompassDial" or missing scenes.
  - Pull latest `android` and restart Godot. If needed, clear the cache: `rm -rf godot/.godot`.
- Parse error: "Variable typed as Variant" (warnings treated as errors).
  - Ensure you have the latest `godot/scripts/battlespace3d.gd` (explicitly typed vars) and `main.gd`.
- Local changes block pulling:
  - Discard local edits: `git reset --hard origin/android` (or use `android-sync`).
  - Keep edits: `git stash -u && git pull --rebase && git stash pop`.
- Android export warning (build-tools): harmless until export is configured.
- Theme warning at startup: benign; UI draws fine.

## Roadmap (next)

- Map world units to ~12.8 km cube and ping speed to scaled sound speed.
- Add 3D contact billboards and HUD readouts for contacts.
- Implement audio mixer in Godot (loops, pan, rolloff, earcons).
- Depth half-dial UI with ticks; polish visuals.
- Android export preset + keystore + device smoke tests.

## License

TBD.
