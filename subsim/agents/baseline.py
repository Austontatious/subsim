"""Baseline agent for deterministic headless runs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from ..config import CLASSIFY_CONFIDENCE
from ..input import Action
from .base import Agent


@dataclass
class BaselineAgent(Agent):
    heading: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    last_ping_time: float = -999.0

    def reset(self, obs: Dict) -> None:
        self.heading = obs.get("player", {}).get("heading", 0.0)
        self.pitch = 0.0
        self.roll = 0.0
        self.last_ping_time = -999.0

    def act(self, obs: Dict) -> Action:
        t = obs.get("t", 0.0)
        contacts = obs.get("contacts", [])
        ping_cooldown = obs.get("ping_cooldown", 0.0)
        torp_state = obs.get("torpedo_state", "idle")

        ping = False
        torpedo = False

        if not contacts:
            # Patrol loop.
            self.heading = (self.heading + 2.5) % 360.0
            if ping_cooldown <= 0.0 and (t - self.last_ping_time) > 12.0:
                ping = True
                self.last_ping_time = t
        else:
            # Focus on best contact.
            best = max(contacts, key=lambda c: c.get("confidence", 0.0))
            bearing = best.get("bearing", 0.0)
            classify = best.get("classify", 0.0)
            distance = best.get("distance", 9999.0)
            self.heading = bearing

            if classify < CLASSIFY_CONFIDENCE and ping_cooldown <= 0.0 and (t - self.last_ping_time) > 6.0:
                ping = True
                self.last_ping_time = t

            if torp_state == "idle" and classify >= CLASSIFY_CONFIDENCE:
                torpedo = True
            elif torp_state == "ready":
                torpedo = True

            # Evasive pitch if close.
            if distance < 400.0:
                self.pitch = -0.6
            else:
                self.pitch *= 0.8

        return Action(heading_deg=self.heading, pitch=self.pitch, roll=self.roll, ping=ping, torpedo=torpedo)


__all__ = ["BaselineAgent"]
