"""Simple world model and kinematics helpers."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Tuple

from ..config import (
    FRAME_DT,
    MAX_DEPTH_M,
    MAX_WORLD_EXTENT_M,
    TELEGRAPH_SPEEDS,
    THERMOCLINE_DEPTH_M,
)

Vec3 = Tuple[float, float, float]


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


@dataclass
class Player:
    position: Vec3 = (0.0, 0.0, -120.0)
    heading_deg: float = 0.0
    speed_mps: float = 0.0
    target_depth: float = -120.0
    telegraph: str = "STOP"
    own_noise: float = 0.0

    def change_heading(self, delta_deg: float) -> None:
        self.heading_deg = (self.heading_deg + delta_deg) % 360.0

    def change_depth(self, delta: float) -> None:
        self.target_depth = clamp(self.target_depth + delta, MAX_DEPTH_M, -5.0)

    def telegraph_step(self, faster: bool) -> None:
        orders = list(TELEGRAPH_SPEEDS.keys())
        idx = orders.index(self.telegraph)
        if faster and idx < len(orders) - 1:
            idx += 1
        elif not faster and idx > 0:
            idx -= 1
        self.telegraph = orders[idx]

    def update(self, dt: float) -> None:
        target_speed = TELEGRAPH_SPEEDS[self.telegraph]
        accel = 2.5
        if self.speed_mps < target_speed:
            self.speed_mps = min(target_speed, self.speed_mps + accel * dt)
        else:
            self.speed_mps = max(target_speed, self.speed_mps - accel * dt)

        x, y, z = self.position
        rad = math.radians(self.heading_deg)
        x += math.cos(rad) * self.speed_mps * dt
        y += math.sin(rad) * self.speed_mps * dt
        x = clamp(x, -MAX_WORLD_EXTENT_M, MAX_WORLD_EXTENT_M)
        y = clamp(y, -MAX_WORLD_EXTENT_M, MAX_WORLD_EXTENT_M)
        depth_rate = 1.0 * (self.target_depth - z)
        z += depth_rate * dt
        z = clamp(z, MAX_DEPTH_M, -5.0)
        self.position = (x, y, z)
        self.own_noise = clamp(abs(self.speed_mps) * 0.06, 0.0, 0.9)


@dataclass
class World:
    seed: int = 0
    player: Player = field(default_factory=Player)
    time: float = 0.0

    def update(self, dt: float = FRAME_DT) -> None:
        self.time += dt
        self.player.update(dt)

    @staticmethod
    def distance(a: Vec3, b: Vec3) -> float:
        dx = a[0] - b[0]
        dy = a[1] - b[1]
        dz = a[2] - b[2]
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    @staticmethod
    def bearing(from_pos: Vec3, to_pos: Vec3) -> float:
        dx = to_pos[0] - from_pos[0]
        dy = to_pos[1] - from_pos[1]
        ang = math.degrees(math.atan2(dy, dx))
        return (ang + 360.0) % 360.0

    @staticmethod
    def thermocline_layers(z0: float, z1: float) -> int:
        delta0 = z0 - THERMOCLINE_DEPTH_M
        delta1 = z1 - THERMOCLINE_DEPTH_M
        return 1 if delta0 * delta1 < 0 else 0


__all__ = ["World", "Player", "Vec3", "clamp"]
