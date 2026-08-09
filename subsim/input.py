"""Input mapping for the two-dial + two-button action interface."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

try:  # pragma: no cover - optional dependency
    import pyglet
    from pyglet.window import key

    _HAVE_PYGLET = True
except Exception:  # pragma: no cover
    pyglet = None  # type: ignore
    key = None  # type: ignore
    _HAVE_PYGLET = False


@dataclass
class Action:
    heading_deg: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    ping: bool = False
    torpedo: bool = False

    def normalized(self) -> "Action":
        heading = self.heading_deg % 360.0
        pitch = max(-1.0, min(1.0, self.pitch))
        roll = max(-1.0, min(1.0, self.roll))
        return Action(heading_deg=heading, pitch=pitch, roll=roll, ping=self.ping, torpedo=self.torpedo)


@dataclass
class InputFrame:
    action: Action
    cycle_contact: bool = False
    lock_contact: bool = False
    menu_choice: Optional[int] = None
    confirm: bool = False
    toggle_help: bool = False
    toggle_pause: bool = False
    quit: bool = False


class TwoDialInput:
    def __init__(self, renderer, initial_heading: float = 0.0) -> None:
        self.headless = renderer.headless if renderer else True
        self._handler = None
        self._heading = initial_heading
        self._pitch = 0.0
        self._roll = 0.0
        self._ping_latch = False
        self._torpedo_latch = False
        self._cycle_latch = False
        self._lock_latch = False
        self._menu_choice: Optional[int] = None
        self._confirm_latch = False
        self._help_latch = False
        self._pause_latch = False
        self._quit_flag = False
        if not self.headless and _HAVE_PYGLET and renderer.window:
            self._handler = key.KeyStateHandler()
            renderer.window.push_handlers(self._handler)
            renderer.window.push_handlers(on_key_press=self._on_key_press)

    def _on_key_press(self, symbol, modifiers):  # pragma: no cover - pyglet only
        if symbol in (key.SPACE, key.P):
            self._ping_latch = True
        elif symbol in (key.T,):
            self._torpedo_latch = True
        elif symbol in (key.TAB,):
            self._cycle_latch = True
        elif symbol in (key.ENTER, key.NUM_ENTER):
            self._lock_latch = True
            self._confirm_latch = True
        elif symbol in (key._1, key.NUM_1):
            self._menu_choice = 1
        elif symbol in (key._2, key.NUM_2):
            self._menu_choice = 2
        elif symbol in (key._3, key.NUM_3):
            self._menu_choice = 3
        elif symbol in (key._4, key.NUM_4):
            self._menu_choice = 4
        elif symbol in (key.H,):
            self._help_latch = True
        elif symbol in (key.ESCAPE,):
            self._pause_latch = True
        elif symbol in (key.X,):
            self._quit_flag = True

    def collect(self) -> InputFrame:
        if self.headless or not self._handler:
            action = Action(heading_deg=self._heading, pitch=self._pitch, roll=self._roll)
        else:
            # Heading dial
            coarse = 4.0
            fine = 1.0
            if self._handler[key.LEFT] or self._handler[key.A]:
                self._heading -= coarse
            if self._handler[key.RIGHT] or self._handler[key.D]:
                self._heading += coarse
            if self._handler[key.Q]:
                self._heading -= fine
            if self._handler[key.E]:
                self._heading += fine

            # Pitch dial
            step = 0.08
            if self._handler[key.W]:
                self._pitch += step
            if self._handler[key.S]:
                self._pitch -= step
            # Roll dial (optional)
            if self._handler[key.Z]:
                self._roll -= 0.05
            if self._handler[key.C]:
                self._roll += 0.05

            self._pitch = max(-1.0, min(1.0, self._pitch))
            self._roll = max(-1.0, min(1.0, self._roll))

            action = Action(
                heading_deg=self._heading,
                pitch=self._pitch,
                roll=self._roll,
                ping=self._consume_latch("ping"),
                torpedo=self._consume_latch("torpedo"),
            )

        frame = InputFrame(
            action=action.normalized(),
            cycle_contact=self._consume_latch("cycle"),
            lock_contact=self._consume_latch("lock"),
            menu_choice=self._consume_menu_choice(),
            confirm=self._consume_confirm(),
            toggle_help=self._consume_help(),
            toggle_pause=self._consume_pause(),
            quit=self._quit_flag,
        )
        return frame

    def _consume_latch(self, which: str) -> bool:
        if which == "ping":
            flag = self._ping_latch
            self._ping_latch = False
            return flag
        if which == "torpedo":
            flag = self._torpedo_latch
            self._torpedo_latch = False
            return flag
        if which == "cycle":
            flag = self._cycle_latch
            self._cycle_latch = False
            return flag
        if which == "lock":
            flag = self._lock_latch
            self._lock_latch = False
            return flag
        return False

    def _consume_menu_choice(self) -> Optional[int]:
        choice = self._menu_choice
        self._menu_choice = None
        return choice

    def _consume_confirm(self) -> bool:
        flag = self._confirm_latch
        self._confirm_latch = False
        return flag

    def _consume_help(self) -> bool:
        flag = self._help_latch
        self._help_latch = False
        return flag

    def _consume_pause(self) -> bool:
        flag = self._pause_latch
        self._pause_latch = False
        return flag


__all__ = ["Action", "InputFrame", "TwoDialInput"]
