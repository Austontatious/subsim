"""Rendering helpers using pyglet when available."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional, Sequence

from .engine.contacts import Contact
from .engine.world import World
from . import ui

try:  # pragma: no cover - optional dependency
    import pyglet
    from pyglet import shapes

    _HAVE_PYGLET = True
except Exception:  # pragma: no cover - running headless
    pyglet = None  # type: ignore
    shapes = None  # type: ignore
    _HAVE_PYGLET = False


@dataclass
class Renderer:
    headless: bool = False
    window: Optional["pyglet.window.Window"] = field(init=False, default=None)
    batch: Optional["pyglet.graphics.Batch"] = field(init=False, default=None)
    _thermocline: Optional["pyglet.shapes.Line"] = field(init=False, default=None)

    def __post_init__(self) -> None:
        if not _HAVE_PYGLET:
            self.headless = True

        if self.headless or not os.environ.get("DISPLAY"):
            if pyglet:
                pyglet.options["headless"] = True

        if pyglet and not pyglet.options.get("headless", False):
            try:
                self.window = pyglet.window.Window(800, 600, caption="SubSim")
            except Exception:
                pyglet.options["headless"] = True
                self.window = None
        else:
            self.window = None

        if pyglet and not pyglet.options.get("headless", False):
            self.batch = pyglet.graphics.Batch()
            self._thermocline = shapes.Line(0, 300, 800, 300, color=(80, 150, 220), batch=self.batch)
            if hasattr(self._thermocline, "width"):
                try:
                    self._thermocline.width = 2
                except Exception:
                    pass
        else:
            self.batch = None
            self._thermocline = None

    def draw(self, world: World, contacts: Sequence[Contact], hud: Optional[dict] = None) -> None:
        if not pyglet or not self.window or not self.batch:
            return
        self.window.switch_to()
        self.window.dispatch_events()
        self.window.clear()

        # convert positions to screen space (top-down)
        cx, cy = world.player.position[:2]
        scale = 0.15
        glyphs = [
            shapes.Circle(400 + cx * scale, 300 + cy * scale, 8, color=(120, 220, 255), batch=self.batch)
        ]
        for contact in contacts:
            x, y, _ = contact.position
            glyphs.append(shapes.Circle(400 + x * scale, 300 + y * scale, 6, color=(255, 180, 90), batch=self.batch))
        self.batch.draw()
        for glyph in glyphs:
            glyph.delete()

        if hud:
            labels = self._build_labels(hud)
            for label in labels:
                label.draw()

    def close(self) -> None:
        if self.window:
            self.window.close()

    def _build_labels(self, hud: dict) -> list["pyglet.text.Label"]:
        labels: list["pyglet.text.Label"] = []
        font = "Courier"
        color = (210, 220, 235, 255)
        accent = (120, 200, 255, 255)
        w = self.window.width
        h = self.window.height

        mode = hud.get("mode", "skirmish")
        paused = hud.get("paused", False)
        help_on = hud.get("help", False)

        if mode == "menu":
            labels.append(
                pyglet.text.Label(
                    "SubSim",
                    font_name=font,
                    font_size=26,
                    x=w // 2,
                    y=h // 2 + 120,
                    anchor_x="center",
                    anchor_y="center",
                    color=accent,
                )
            )
            menu_lines = ui.menu_lines()
            for idx, line in enumerate(menu_lines):
                labels.append(
                    pyglet.text.Label(
                        line,
                        font_name=font,
                        font_size=14,
                        x=w // 2,
                        y=h // 2 + 40 - idx * 22,
                        anchor_x="center",
                        anchor_y="center",
                        color=color,
                    )
                )
            return labels

        if mode == "debrief":
            outcome = hud.get("debrief", {}).get("outcome", "Debrief")
            labels.append(
                pyglet.text.Label(
                    f"Debrief: {outcome}",
                    font_name=font,
                    font_size=18,
                    x=w // 2,
                    y=h // 2 + 80,
                    anchor_x="center",
                    anchor_y="center",
                    color=accent,
                )
            )
            stats = hud.get("debrief", {})
            lines = [
                f"Pings: {stats.get('pings', 0)}",
                f"Torpedoes: {stats.get('torpedoes', 0)}",
                f"Hits: {stats.get('hits', 0)}",
                "Press 1 or Enter to return",
            ]
            for idx, line in enumerate(lines):
                labels.append(
                    pyglet.text.Label(
                        line,
                        font_name=font,
                        font_size=14,
                        x=w // 2,
                        y=h // 2 + 40 - idx * 22,
                        anchor_x="center",
                        anchor_y="center",
                        color=color,
                    )
                )
            return labels

        # Top status bar
        labels.append(
            pyglet.text.Label(
                f"TIME {hud.get('time', 0.0):6.1f}s",
                font_name=font,
                font_size=12,
                x=14,
                y=h - 18,
                color=color,
            )
        )
        labels.append(
            pyglet.text.Label(
                f"HDG {hud.get('heading', 0.0):05.1f}  SPD {hud.get('speed', 0.0):04.1f}  DEPTH {hud.get('depth', 0.0):06.1f}",
                font_name=font,
                font_size=12,
                x=140,
                y=h - 18,
                color=color,
            )
        )
        labels.append(
            pyglet.text.Label(
                f"DIAL HDG {hud.get('heading_dial', 0.0):05.1f}  PITCH {hud.get('pitch', 0.0):+.2f}  ROLL {hud.get('roll', 0.0):+.2f}",
                font_name=font,
                font_size=11,
                x=14,
                y=h - 36,
                color=color,
            )
        )

        message = hud.get("message")
        if message:
            labels.append(
                pyglet.text.Label(
                    message,
                    font_name=font,
                    font_size=14,
                    x=w // 2,
                    y=h - 40,
                    anchor_x="center",
                    anchor_y="center",
                    color=accent,
                )
            )

        # Bottom bar
        ping_cd = hud.get("ping_cooldown", 0.0)
        torp_state = hud.get("torpedo_state", "idle")
        labels.append(
            pyglet.text.Label(
                f"PING CD {ping_cd:4.1f}s  TORP {torp_state.upper()}",
                font_name=font,
                font_size=12,
                x=14,
                y=18,
                color=color,
            )
        )

        # Left contact list
        labels.append(
            pyglet.text.Label(
                "CONTACTS",
                font_name=font,
                font_size=12,
                x=14,
                y=h - 44,
                color=accent,
            )
        )
        tracks = hud.get("tracks", [])
        for idx, track in enumerate(tracks[:8]):
            marker = "*" if track.get("locked") else " "
            line = (
                f"{marker}{track['id']:<8} brg {track['bearing']:5.1f}  "
                f"rng {track['distance']:6.0f}  conf {track['confidence']:.2f}  "
                f"cls {track.get('classify', 0.0):.2f}"
            )
            labels.append(
                pyglet.text.Label(
                    line,
                    font_name=font,
                    font_size=10,
                    x=14,
                    y=h - 64 - idx * 14,
                    color=color,
                )
            )

        # Right objective
        objective = hud.get("objective", "")
        if objective:
            labels.append(
                pyglet.text.Label(
                    f"OBJECTIVE: {objective}",
                    font_name=font,
                    font_size=12,
                    x=w - 14,
                    y=h - 44,
                    anchor_x="right",
                    color=accent,
                )
            )

        if paused:
            labels.append(
                pyglet.text.Label(
                    "PAUSED",
                    font_name=font,
                    font_size=22,
                    x=w // 2,
                    y=h // 2,
                    anchor_x="center",
                    anchor_y="center",
                    color=accent,
                )
            )
            labels.append(
                pyglet.text.Label(
                    "Esc to resume, Q to quit",
                    font_name=font,
                    font_size=12,
                    x=w // 2,
                    y=h // 2 - 30,
                    anchor_x="center",
                    anchor_y="center",
                    color=color,
                )
            )

        if help_on:
            help_lines = ui.help_lines()
            for idx, line in enumerate(help_lines):
                labels.append(
                    pyglet.text.Label(
                        line,
                        font_name=font,
                        font_size=12,
                        x=w - 14,
                        y=120 + idx * 16,
                        anchor_x="right",
                        color=color,
                    )
                )

        return labels


__all__ = ["Renderer"]
