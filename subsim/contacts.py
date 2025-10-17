"""Contact definitions and management."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, Iterable, List

from .config import MAX_WORLD_EXTENT_M
from .world import Vec3, clamp


@dataclass
class Contact:
    ident: str
    kind: str
    position: Vec3
    heading_deg: float
    speed_mps: float
    depth_m: float
    noise: float
    active: bool = True

    def update(self, dt: float) -> None:
        if not self.active:
            return
        x, y, _ = self.position
        rad = math.radians(self.heading_deg)
        x += math.cos(rad) * self.speed_mps * dt
        y += math.sin(rad) * self.speed_mps * dt
        x = clamp(x, -MAX_WORLD_EXTENT_M, MAX_WORLD_EXTENT_M)
        y = clamp(y, -MAX_WORLD_EXTENT_M, MAX_WORLD_EXTENT_M)
        self.position = (x, y, self.depth_m)


@dataclass
class ContactManager:
    seed: int = 0
    contacts: Dict[str, Contact] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def spawn_demo_contacts(self) -> None:
        merchant = Contact(
            ident="merchant",
            kind="merchant",
            position=(400.0, -1200.0, -90.0),
            heading_deg=12.0,
            speed_mps=2.5,
            depth_m=-90.0,
            noise=0.35,
        )
        hunter = Contact(
            ident="hunter",
            kind="hunter",
            position=(-900.0, 600.0, -180.0),
            heading_deg=180.0,
            speed_mps=3.5,
            depth_m=-180.0,
            noise=0.45,
        )
        self.contacts = {merchant.ident: merchant, hunter.ident: hunter}

    def update(self, dt: float) -> None:
        for contact in self.contacts.values():
            contact.update(dt)
            if contact.kind == "hunter":
                contact.heading_deg = (contact.heading_deg + self._rng.uniform(-2.0, 2.0)) % 360.0

    def __iter__(self) -> Iterable[Contact]:
        return iter(self.contacts.values())

    def as_list(self) -> List[Contact]:
        return list(self.contacts.values())


__all__ = ["Contact", "ContactManager"]
