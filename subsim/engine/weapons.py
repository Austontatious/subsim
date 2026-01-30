"""Weapons models for SubSim."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from .contacts import Contact
from .world import Vec3, World, clamp


@dataclass
class WeaponEvent:
    kind: str
    position: Vec3
    contact_id: Optional[str]
    timestamp: float


@dataclass
class Mine:
    position: Vec3
    arm_delay: float = 2.5
    trigger_radius: float = 200.0
    trigger_speed: float = 1.2
    timer: float = 0.0
    armed: bool = False
    detonated: bool = False

    def update(self, dt: float, contacts: Sequence[Contact], now: float) -> Optional[WeaponEvent]:
        if self.detonated:
            return None
        self.timer += dt
        if not self.armed and self.timer >= self.arm_delay:
            self.armed = True

        if not self.armed:
            return None

        for contact in contacts:
            distance = World.distance(self.position, contact.position)
            if distance <= self.trigger_radius and contact.speed_mps >= self.trigger_speed:
                self.detonated = True
                return WeaponEvent("mine-detonation", self.position, contact.ident, now)
        return None


@dataclass
class Torpedo:
    position: Vec3
    heading_deg: float
    target_id: Optional[str] = None
    speed_mps: float = 18.0
    run_up: float = 1.0
    fuse_range: float = 40.0
    timer: float = 0.0
    detonated: bool = False

    def update(
        self,
        dt: float,
        contacts: Sequence[Contact],
        now: float,
    ) -> Optional[WeaponEvent]:
        if self.detonated:
            return None

        self.timer += dt
        if self.timer >= self.run_up:
            solution = self._seek_target(contacts)
            if solution is not None:
                desired_heading = solution
                error = (desired_heading - self.heading_deg + 540.0) % 360.0 - 180.0
                turn = clamp(error * 0.9, -35.0 * dt, 35.0 * dt)
                self.heading_deg = (self.heading_deg + turn) % 360.0

        x, y, z = self.position
        rad = math.radians(self.heading_deg)
        x += math.cos(rad) * self.speed_mps * dt
        y += math.sin(rad) * self.speed_mps * dt
        self.position = (x, y, z)

        for contact in contacts:
            if self.target_id and contact.ident != self.target_id:
                continue
            distance = World.distance(self.position, contact.position)
            if distance <= self.fuse_range:
                self.detonated = True
                return WeaponEvent("torpedo-detonation", self.position, contact.ident, now)
        return None

    def _seek_target(self, contacts: Sequence[Contact]) -> Optional[float]:
        if self.target_id:
            for contact in contacts:
                if contact.ident == self.target_id:
                    return math.degrees(
                        math.atan2(contact.position[1] - self.position[1], contact.position[0] - self.position[0])
                    )
            return None
        if not contacts:
            return None
        nearest = min(contacts, key=lambda c: World.distance(self.position, c.position))
        return math.degrees(
            math.atan2(nearest.position[1] - self.position[1], nearest.position[0] - self.position[0])
        )


@dataclass
class WeaponManager:
    mines: List[Mine] = field(default_factory=list)
    torpedoes: List[Torpedo] = field(default_factory=list)

    def drop_mine(self, position: Vec3) -> None:
        self.mines.append(Mine(position=position))

    def launch_torpedo(self, position: Vec3, heading_deg: float, target_id: Optional[str]) -> None:
        self.torpedoes.append(Torpedo(position=position, heading_deg=heading_deg, target_id=target_id))

    def update(
        self,
        dt: float,
        now: float,
        contacts: Sequence[Contact],
    ) -> List[WeaponEvent]:
        events: List[WeaponEvent] = []
        for mine in list(self.mines):
            evt = mine.update(dt, contacts, now)
            if evt:
                events.append(evt)
            if mine.detonated:
                self.mines.remove(mine)
        for torpedo in list(self.torpedoes):
            evt = torpedo.update(dt, contacts, now)
            if evt:
                events.append(evt)
            if torpedo.detonated or torpedo.timer > 200.0:
                self.torpedoes.remove(torpedo)
        return events


__all__ = ["WeaponManager", "Mine", "Torpedo", "WeaponEvent"]
