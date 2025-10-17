"""Sensor models for passive contacts and active sonar."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List

from .config import SPEED_OF_SOUND
from .contacts import Contact
from .world import Vec3, World


@dataclass
class PassiveContact:
    contact_id: str
    azimuth_deg: float
    distance_m: float
    confidence: float
    gain: float
    occlusion_layers: int


@dataclass
class PingOut:
    strength: float = 1.0


@dataclass
class PingReturn:
    contact_id: str
    delay_s: float
    range_m: float
    bearing_deg: float
    atten: float


@dataclass
class BearingDetection:
    contact_id: str
    bearing_deg: float
    confidence: float


@dataclass
class SensorTick:
    passive_tracks: List[PassiveContact] = field(default_factory=list)
    ping_returns: List[PingReturn] = field(default_factory=list)
    bearing_events: List[BearingDetection] = field(default_factory=list)
    ping_emitted: bool = False


class SensorSuite:
    """Combines passive audio model and active sonar pings."""

    def __init__(self) -> None:
        self.last_ping_time: float = -1e9

    def sample_passive(self, world: World, contacts: Iterable[Contact]) -> List[PassiveContact]:
        tracks: List[PassiveContact] = []
        player_pos = world.player.position
        own_noise = world.player.own_noise
        for contact in contacts:
            distance = World.distance(player_pos, contact.position)
            bearing = World.bearing(player_pos, contact.position)
            confidence = max(0.05, min(1.0, 1.0 - distance / 2000.0))
            occlusion = World.thermocline_layers(player_pos[2], contact.depth_m)
            rolloff = 1.0 / (1.0 + (distance / 500.0) ** 2)
            gain = rolloff * confidence * max(0.2, 1.0 - own_noise) * (0.5 ** occlusion)
            tracks.append(
                PassiveContact(
                    contact_id=contact.ident,
                    azimuth_deg=bearing,
                    distance_m=distance,
                    confidence=confidence,
                    gain=gain,
                    occlusion_layers=occlusion,
                )
            )
        return tracks

    def emit_ping(self, world_time: float) -> None:
        self.last_ping_time = world_time

    def process_active(
        self,
        world: World,
        contacts: Iterable[Contact],
        ping_requested: bool,
    ) -> List[PingReturn]:
        returns: List[PingReturn] = []
        if ping_requested:
            self.emit_ping(world.time)
        if self.last_ping_time < 0.0:
            return returns

        player_pos = world.player.position
        for contact in contacts:
            distance = World.distance(player_pos, contact.position)
            delay = 2.0 * distance / SPEED_OF_SOUND
            bearing = World.bearing(player_pos, contact.position)
            occlusion = World.thermocline_layers(player_pos[2], contact.depth_m)
            atten = 1.0 / (distance * distance + 1.0)
            atten *= 0.6**occlusion
            returns.append(
                PingReturn(
                    contact_id=contact.ident,
                    delay_s=delay,
                    range_m=distance,
                    bearing_deg=bearing,
                    atten=atten,
                )
            )
        return returns

    def step(
        self,
        world: World,
        contacts: Iterable[Contact],
        ping: bool = False,
    ) -> SensorTick:
        passive = self.sample_passive(world, contacts)
        ping_returns = self.process_active(world, contacts, ping_requested=ping)
        bearings = [
            BearingDetection(
                contact_id=p.contact_id,
                bearing_deg=p.azimuth_deg,
                confidence=p.confidence,
            )
            for p in passive
        ]
        return SensorTick(
            passive_tracks=passive,
            ping_returns=ping_returns,
            bearing_events=bearings,
            ping_emitted=ping,
        )


__all__ = [
    "SensorSuite",
    "PassiveContact",
    "PingReturn",
    "PingOut",
    "BearingDetection",
    "SensorTick",
]
