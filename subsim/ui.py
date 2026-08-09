"""UI helpers (menus, overlays, HUD labels)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MenuItem:
    key: str
    label: str


MAIN_MENU = [
    MenuItem("1", "Start Skirmish"),
    MenuItem("2", "Tutorial"),
    MenuItem("4", "Quit"),
]

HELP_LINES = [
    "HELP (H to toggle)",
    "Heading dial: A/D or Left/Right (Q/E fine)",
    "Pitch dial: W/S",
    "Roll dial: Z/C",
    "Ping: Space",
    "Torpedo: T",
    "Cycle contact: Tab",
    "Lock contact: Enter",
    "Pause: Esc",
    "Quit: X",
]


def menu_lines() -> list[str]:
    return [f"{item.key}  {item.label}" for item in MAIN_MENU]


def help_lines() -> list[str]:
    return list(HELP_LINES)


__all__ = ["menu_lines", "help_lines", "MenuItem"]
