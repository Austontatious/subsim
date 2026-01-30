"""Non-player behaviours for demo contacts."""
from __future__ import annotations

import math
from dataclasses import dataclass

from .contacts import ContactManager
from .world import World


@dataclass
class AiController:
    manager: ContactManager
    aggression: float = 1.0
    last_ping_time: float = -1e9

    def notify_ping(self, world_time: float) -> None:
        self.last_ping_time = world_time

    def update(self, world: World, dt: float) -> None:
        player_pos = world.player.position
        for contact in self.manager:
            if contact.kind == "merchant":
                contact.heading_deg = (contact.heading_deg + 0.1 * dt) % 360.0
            elif contact.kind == "hunter":
                self._update_hunter(contact, player_pos, world.time, dt)

    def _update_hunter(self, contact, player_pos, world_time: float, dt: float) -> None:
        heading = contact.heading_deg
        if world_time - self.last_ping_time < 20.0:
            # steer toward player after ping
            desired = math.degrees(math.atan2(player_pos[1] - contact.position[1], player_pos[0] - contact.position[0]))
            error = (desired - heading + 540.0) % 360.0 - 180.0
            turn_rate = 25.0 * self.aggression
            heading = (heading + max(-turn_rate * dt, min(turn_rate * dt, error * 0.5))) % 360.0
        else:
            # search pattern
            heading = (heading + 12.0 * self.aggression * dt) % 360.0
        contact.heading_deg = heading


__all__ = ["AiController"]
