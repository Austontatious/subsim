"""UI helpers for keyboard-driven controls."""
from __future__ import annotations

from dataclasses import dataclass

try:  # pragma: no cover - optional dependency
    import pyglet
    from pyglet.window import key

    _HAVE_PYGLET = True
except Exception:  # pragma: no cover
    pyglet = None  # type: ignore
    key = None  # type: ignore
    _HAVE_PYGLET = False


@dataclass
class ControlState:
    turn: float = 0.0
    speed_delta: int = 0
    depth_delta: float = 0.0
    ping: bool = False
    fire_torpedo: bool = False
    drop_mine: bool = False
    quit: bool = False


class InputController:
    def __init__(self, renderer) -> None:
        self.headless = renderer.headless if renderer else True
        self._handler = None
        self._ping_latch = False
        self._torpedo_latch = False
        self._mine_latch = False
        self._quit_flag = False
        if not self.headless and _HAVE_PYGLET and renderer.window:
            self._handler = key.KeyStateHandler()
            renderer.window.push_handlers(self._handler)
            renderer.window.push_handlers(on_key_press=self._on_key_press)

    def _on_key_press(self, symbol, modifiers):  # pragma: no cover - pyglet only
        if symbol in (key.P, key.p):
            self._ping_latch = True
        elif symbol in (key.T, key.t):
            self._torpedo_latch = True
        elif symbol in (key.M, key.m):
            self._mine_latch = True
        elif symbol in (key.Q, key.ESCAPE):
            self._quit_flag = True

    def collect(self) -> ControlState:
        if self.headless or not self._handler:
            state = ControlState()
        else:
            state = ControlState()
            if self._handler[key.LEFT]:
                state.turn -= 1.0
            if self._handler[key.RIGHT]:
                state.turn += 1.0
            if self._handler[key.UP]:
                state.speed_delta += 1
            if self._handler[key.DOWN]:
                state.speed_delta -= 1
            if self._handler[key.W]:
                state.depth_delta -= 5.0
            if self._handler[key.S]:
                state.depth_delta += 5.0
        state.ping = self._consume_latch("ping")
        state.fire_torpedo = self._consume_latch("torpedo")
        state.drop_mine = self._consume_latch("mine")
        state.quit = self._quit_flag
        return state

    def _consume_latch(self, which: str) -> bool:
        if which == "ping":
            flag = self._ping_latch
            self._ping_latch = False
            return flag
        if which == "torpedo":
            flag = self._torpedo_latch
            self._torpedo_latch = False
            return flag
        if which == "mine":
            flag = self._mine_latch
            self._mine_latch = False
            return flag
        return False


__all__ = ["ControlState", "InputController"]
