"""Global configuration and shared constants for SubSim."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict


PACKAGE_ROOT = Path(__file__).resolve().parent
ASSET_DIR = PACKAGE_ROOT.parent / "assets" / "sfx"

AUDIO_SAMPLE_RATE = 44100
FRAME_RATE = 30
FRAME_DT = 1.0 / FRAME_RATE
SPEED_OF_SOUND = 1482.0  # metres per second
THERMOCLINE_DEPTH_M = -150.0
THERMOCLINE_ATTEN_DB = 12.0
MAX_WORLD_EXTENT_M = 1500.0
MAX_DEPTH_M = -450.0

TELEGRAPH_SPEEDS: Dict[str, float] = {
    "STOP": 0.0,
    "1/4": 2.0,
    "1/2": 4.0,
    "FULL": 7.0,
    "FLANK": 11.0,
}

KEYMAP = {
    "turn_left": "LEFT",
    "turn_right": "RIGHT",
    "speed_up": "UP",
    "speed_down": "DOWN",
    "depth_up": "r",
    "depth_down": "s",
    "ping": "p",
    "fire_torpedo": "t",
    "drop_mine": "m",
    "toggle_waterfall": "W",
    "quit": "q",
}


@dataclass(frozen=True)
class Colors:
    background: tuple[int, int, int] = (6, 10, 24)
    foreground: tuple[int, int, int] = (210, 220, 235)
    accent: tuple[int, int, int] = (104, 182, 255)
    warning: tuple[int, int, int] = (255, 98, 98)


HUD_FONT = "Courier"
ASSET_VARIANTS = ("clean", "lp1", "lp2", "lp3")
ASSET_NAMES = {
    "player_hum": {"freq": 86.0, "duration": 2.5},
    "merchant": {"freq": 138.0, "duration": 2.5},
    "hunter": {"freq": 192.0, "duration": 2.5},
    "ping": {"freq": 820.0, "duration": 0.35},
    "torpedo": {"freq": 420.0, "duration": 1.0},
    "mine": {"freq": 90.0, "duration": 1.0},
}
