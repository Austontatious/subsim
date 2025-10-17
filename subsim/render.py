"""Rendering helpers using pyglet when available."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional, Sequence

from .contacts import Contact
from .world import World

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

        if pyglet:
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

    def draw(self, world: World, contacts: Sequence[Contact]) -> None:
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

    def close(self) -> None:
        if self.window:
            self.window.close()


__all__ = ["Renderer"]
