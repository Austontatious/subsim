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
EXTRACT_RADIUS_M = 1000.0
EVADE_DISTANCE_M = 900.0
EVADE_TIME_S = 4.0
LOCATE_CONFIDENCE = 0.2
AUDIO_MAX_DISTANCE_M = 2000.0
CLASSIFY_CONFIDENCE = 0.55
PING_COOLDOWN_S = 4.0
PITCH_RATE_MPS = 20.0
FIRE_SOLUTION_READY_S = 0.8
FIRE_SOLUTION_WINDOW_S = 1.6

TELEGRAPH_SPEEDS: Dict[str, float] = {
    "STOP": 0.0,
    "1/4": 2.0,
    "1/2": 4.0,
    "FULL": 7.0,
    "FLANK": 11.0,
}
CRUISE_TELEGRAPH = "1/2"

KEYMAP = {
    "heading_left": "LEFT/A",
    "heading_right": "RIGHT/D",
    "heading_fine_left": "Q",
    "heading_fine_right": "E",
    "pitch_up": "W",
    "pitch_down": "S",
    "roll_left": "Z",
    "roll_right": "C",
    "ping": "SPACE",
    "fire_torpedo": "T",
    "cycle_contact": "TAB",
    "lock_contact": "ENTER",
    "help": "H",
    "pause": "ESC",
    "quit": "Q",
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
