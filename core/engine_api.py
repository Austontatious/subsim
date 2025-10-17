from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Tuple, List, Optional


@dataclass
class PlayerState:
    heading_deg: float
    speed_mps: float
    depth_m: float


@dataclass
class Contact:
    id: int
    kind: str
    position_m: Tuple[float, float, float]
    velocity_mps: Tuple[float, float, float]
    confidence: float


@dataclass
class WorldSnapshot:
    t: float
    player: PlayerState
    contacts: List[Contact]
    last_ping_age_s: Optional[float]


class AbstractAudio(Protocol):
    def play_event(self, name: str, volume: float = 1.0, pan: float = 0.0) -> None: ...
    def loop_contact(self, contact_id: int, name: str, volume: float, pan: float) -> None: ...
    def stop_contact(self, contact_id: int) -> None: ...
    def set_paused(self, paused: bool) -> None: ...


class AbstractRenderer(Protocol):
    def update(self, snapshot: WorldSnapshot) -> None: ...
    def set_waterfall(self, enabled: bool) -> None: ...


class EngineAPI(Protocol):
    def step(self, dt: float) -> WorldSnapshot: ...
    def set_heading(self, heading_deg: float) -> None: ...
    def set_telegraph(self, speed_mps: float) -> None: ...
    def set_depth(self, depth_m: float) -> None: ...
    def ping(self) -> None: ...
    def fire_torpedo(self) -> None: ...
    def drop_mine(self) -> None: ...

