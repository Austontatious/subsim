# SubSim – Godot Android Frontend (android branch)

This is a minimal Godot 4 project that drives a stub engine at a fixed 30 FPS.
It’s the starting point for a native Android frontend that will replace the
current desktop (pyglet/pygame) UI while sharing engine logic at the feature level.

Quick start
- Open `godot/` in Godot 4.2+.
- Run the scene (`Main.tscn`). You should see a HUD and a simple player triangle.
- Physics tick is fixed to 30 FPS and calls `engine.step(1/30)` each frame.

Structure
- `main/Main.tscn` – root scene with `main.gd`, `Engine` and `Renderer` nodes.
- `scripts/engine_port/engine.gd` – engine API and early logic.
- `scripts/renderer.gd` – minimal 2D visualization placeholder.

Next steps
- Wire audio mixer and touch UI.
- Port more core logic from Python as needed.
