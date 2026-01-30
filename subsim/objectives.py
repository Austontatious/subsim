"""Objective tracking for Locate -> Classify -> Engage/Evade -> Extract."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence

from .config import CLASSIFY_CONFIDENCE, EVADE_DISTANCE_M, EVADE_TIME_S, EXTRACT_RADIUS_M, LOCATE_CONFIDENCE
from .engine.contacts import Contact
from .engine.sensors import SensorTick
from .engine.world import World


@dataclass
class ObjectiveUpdate:
    stage: str
    message: str


@dataclass
class ObjectiveTracker:
    branch: str = "engage"  # "engage" or "evade"
    stage: str = "LOCATE"
    located: bool = False
    classified: bool = False
    engaged: bool = False
    evaded: bool = False
    extracted: bool = False
    completed: bool = False
    failed: bool = False
    time_to_locate: float | None = None
    time_to_classify: float | None = None
    _evade_timer: float = 0.0
    _timeline: List[ObjectiveUpdate] = field(default_factory=list)
    _classification: Dict[str, float] = field(default_factory=dict)

    def updates(self) -> List[ObjectiveUpdate]:
        updates = list(self._timeline)
        self._timeline.clear()
        return updates

    def status_line(self) -> str:
        if self.failed:
            return "OBJECTIVE FAILED"
        if self.completed:
            return "OBJECTIVE COMPLETE"
        if self.stage == "LOCATE":
            return "Locate a contact"
        if self.stage == "CLASSIFY":
            return "Classify contact"
        if self.stage == "ENGAGE":
            return "Engage target"
        if self.stage == "EVADE":
            return "Evade and break contact"
        if self.stage == "EXTRACT":
            return "Extract to safe waters"
        return "Objective"

    def classification_for(self, contact_id: str) -> float:
        return self._classification.get(contact_id, 0.0)

    def update(
        self,
        world: World,
        sensor_tick: SensorTick,
        contacts: Sequence[Contact],
        *,
        dt: float,
        ping_used: bool,
        torpedo_fired: bool,
        torpedo_hit: bool,
    ) -> None:
        if self.completed or self.failed:
            return

        # Update classification confidence from ping returns.
        for ret in sensor_tick.ping_returns:
            cur = self._classification.get(ret.contact_id, 0.0)
            self._classification[ret.contact_id] = min(1.0, cur + 0.4)

        # Passive confidence can also gently raise classification.
        for track in sensor_tick.passive_tracks:
            cur = self._classification.get(track.contact_id, 0.0)
            self._classification[track.contact_id] = max(cur, track.confidence * 0.5)

        if not self.located:
            for track in sensor_tick.passive_tracks:
                if track.confidence >= LOCATE_CONFIDENCE:
                    self.located = True
                    self.stage = "CLASSIFY"
                    if self.time_to_locate is None:
                        self.time_to_locate = world.time
                    self._timeline.append(ObjectiveUpdate("LOCATE", "Contact located"))
                    break

        if self.located and not self.classified:
            for track in sensor_tick.passive_tracks:
                if self._classification.get(track.contact_id, 0.0) >= CLASSIFY_CONFIDENCE:
                    self.classified = True
                    self.stage = "ENGAGE" if self.branch == "engage" else "EVADE"
                    if self.time_to_classify is None:
                        self.time_to_classify = world.time
                    self._timeline.append(ObjectiveUpdate("CLASSIFY", "Contact classified"))
                    break

        if self.stage == "ENGAGE" and not self.engaged:
            if torpedo_fired or torpedo_hit:
                self.engaged = True
                self.stage = "EXTRACT"
                self._timeline.append(ObjectiveUpdate("ENGAGE", "Target engaged"))

        if self.stage == "EVADE" and not self.evaded:
            nearest = _nearest_enemy_distance(world, contacts)
            if nearest is None:
                self.evaded = True
            elif nearest >= EVADE_DISTANCE_M:
                self._evade_timer += dt
                if self._evade_timer >= EVADE_TIME_S:
                    self.evaded = True
            else:
                self._evade_timer = 0.0
            if self.evaded:
                self.stage = "EXTRACT"
                self._timeline.append(ObjectiveUpdate("EVADE", "Contact evaded"))

        if self.stage == "EXTRACT" and not self.extracted:
            if _is_extracted(world):
                self.extracted = True
                self.completed = True
                self.stage = "COMPLETE"
                self._timeline.append(ObjectiveUpdate("EXTRACT", "Extraction complete"))


def _nearest_enemy_distance(world: World, contacts: Sequence[Contact]) -> float | None:
    if not contacts:
        return None
    distances = [World.distance(world.player.position, c.position) for c in contacts if c.kind == "hunter"]
    if not distances:
        return None
    return min(distances)


def _is_extracted(world: World) -> bool:
    x, y, _ = world.player.position
    return (x * x + y * y) ** 0.5 >= EXTRACT_RADIUS_M


__all__ = ["ObjectiveTracker", "ObjectiveUpdate"]
