"""Event bus for audio-first HUD + replay traces."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


EVENT_PING = "PING"
EVENT_RETURN = "RETURN"
EVENT_CONTACT_NEW = "CONTACT_NEW"
EVENT_CONTACT_UPDATE = "CONTACT_UPDATE"
EVENT_FIRE_SOLUTION_START = "FIRE_SOLUTION_START"
EVENT_FIRE_SOLUTION_READY = "FIRE_SOLUTION_READY"
EVENT_FIRE_SOLUTION_MISS = "FIRE_SOLUTION_MISS"
EVENT_TORP_LAUNCH = "TORP_LAUNCH"
EVENT_TORP_IN_WATER = "TORP_IN_WATER"
EVENT_TORP_HIT = "TORP_HIT"
EVENT_DETONATION = "DETONATION"
EVENT_UI_CONFIRM = "UI_CONFIRM"
EVENT_UI_ALERT = "UI_ALERT"
EVENT_OBJECTIVE_STAGE = "OBJECTIVE_STAGE_ADVANCE"
EVENT_OBJECTIVE_COMPLETE = "OBJECTIVE_COMPLETE"
EVENT_OBJECTIVE_FAIL = "OBJECTIVE_FAIL"
EVENT_MODE_CHANGE = "MODE_CHANGE"


@dataclass
class GameEvent:
    t: float
    type: str
    bearing_deg: Optional[float] = None
    distance_norm: Optional[float] = None
    priority: int = 0
    payload: Dict[str, Any] = field(default_factory=dict)


class EventBus:
    def __init__(self) -> None:
        self._events: List[GameEvent] = []

    def emit(
        self,
        event_type: str,
        *,
        t: float,
        bearing_deg: Optional[float] = None,
        distance_norm: Optional[float] = None,
        priority: int = 0,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._events.append(
            GameEvent(
                t=t,
                type=event_type,
                bearing_deg=bearing_deg,
                distance_norm=distance_norm,
                priority=priority,
                payload=dict(payload) if payload else {},
            )
        )

    def flush(self) -> List[GameEvent]:
        events = self._events
        self._events = []
        return events

    def peek(self) -> List[GameEvent]:
        return list(self._events)


def events_to_trace(events: Iterable[GameEvent]) -> List[Dict[str, Any]]:
    return [
        {
            "t": e.t,
            "type": e.type,
            "bearing": e.bearing_deg,
            "distance": e.distance_norm,
            "priority": e.priority,
            "payload": e.payload,
        }
        for e in events
    ]


__all__ = [
    "EventBus",
    "GameEvent",
    "events_to_trace",
    "EVENT_PING",
    "EVENT_RETURN",
    "EVENT_CONTACT_NEW",
    "EVENT_CONTACT_UPDATE",
    "EVENT_FIRE_SOLUTION_START",
    "EVENT_FIRE_SOLUTION_READY",
    "EVENT_FIRE_SOLUTION_MISS",
    "EVENT_TORP_LAUNCH",
    "EVENT_TORP_IN_WATER",
    "EVENT_TORP_HIT",
    "EVENT_DETONATION",
    "EVENT_UI_CONFIRM",
    "EVENT_UI_ALERT",
    "EVENT_OBJECTIVE_STAGE",
    "EVENT_OBJECTIVE_COMPLETE",
    "EVENT_OBJECTIVE_FAIL",
    "EVENT_MODE_CHANGE",
]
