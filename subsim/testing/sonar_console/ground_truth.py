"""Ground-truth frame export for offline scoring and replay diagnostics."""
from __future__ import annotations

from typing import Mapping, Sequence

from ...engine.contacts import Contact
from ...engine.world import World
from .contracts import GroundTruthFrame, TruthEntity


def build_ground_truth_frame(
    *,
    tick: int,
    t: float,
    world: World,
    contacts: Sequence[Contact],
    source_to_track: Mapping[str, str],
) -> GroundTruthFrame:
    entities: list[TruthEntity] = []
    for contact in sorted(contacts, key=lambda item: item.ident):
        bearing = World.bearing(world.player.position, contact.position)
        range_m = World.distance(world.player.position, contact.position)
        occlusion = World.thermocline_layers(world.player.position[2], contact.depth_m)
        detectability = _detectability(
            contact_noise=contact.noise,
            own_noise=world.player.own_noise,
            range_m=range_m,
            occlusion_layers=occlusion,
        )
        entities.append(
            TruthEntity(
                entity_id=contact.ident,
                kind=contact.kind,
                bearing_deg_true=bearing,
                range_m_true=range_m,
                course_deg_true=contact.heading_deg,
                speed_mps_true=contact.speed_mps,
                depth_m_true=contact.depth_m,
                detectability=detectability,
                occlusion_layers=occlusion,
                matched_track_id=source_to_track.get(contact.ident),
            )
        )
    return GroundTruthFrame(tick=tick, t=t, entities=entities)


def _detectability(*, contact_noise: float, own_noise: float, range_m: float, occlusion_layers: int) -> float:
    range_term = max(0.0, min(1.0, 1.0 - (range_m / 2200.0)))
    noise_term = max(0.0, min(1.0, contact_noise - (own_noise * 0.4)))
    occlusion_term = 0.7**max(0, occlusion_layers)
    return max(0.0, min(1.0, range_term * noise_term * occlusion_term))


__all__ = ["build_ground_truth_frame"]
