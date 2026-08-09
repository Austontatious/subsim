"""Typed contract surfaces for machine-readable sonar console streams."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


SCHEMA_VERSION = "sonar-console.v1"


@dataclass(frozen=True)
class OwnshipSensorContext:
    heading_deg: float
    speed_mps: float
    depth_m: float
    pitch: float
    roll: float
    self_noise: float
    self_noise_bucket: str
    sensor_noise: float
    ping_cooldown_s: float
    ping_active: bool
    thermocline_side: str
    masking: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "heading_deg": self.heading_deg,
            "speed_mps": self.speed_mps,
            "depth_m": self.depth_m,
            "pitch": self.pitch,
            "roll": self.roll,
            "self_noise": self.self_noise,
            "self_noise_bucket": self.self_noise_bucket,
            "sensor_noise": self.sensor_noise,
            "ping_cooldown_s": self.ping_cooldown_s,
            "ping_active": self.ping_active,
            "thermocline_side": self.thermocline_side,
            "masking": self.masking,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "OwnshipSensorContext":
        return cls(
            heading_deg=float(payload["heading_deg"]),
            speed_mps=float(payload["speed_mps"]),
            depth_m=float(payload["depth_m"]),
            pitch=float(payload["pitch"]),
            roll=float(payload["roll"]),
            self_noise=float(payload["self_noise"]),
            self_noise_bucket=str(payload["self_noise_bucket"]),
            sensor_noise=float(payload["sensor_noise"]),
            ping_cooldown_s=float(payload["ping_cooldown_s"]),
            ping_active=bool(payload["ping_active"]),
            thermocline_side=str(payload["thermocline_side"]),
            masking=bool(payload["masking"]),
        )


@dataclass(frozen=True)
class PerceivedTrack:
    track_id: str
    first_seen_at: float
    last_updated_at: float
    bearing_deg_estimate: float
    bearing_confidence: float
    bearing_rate_deg_per_min: float
    signal_strength: float
    signal_strength_trend: float
    doppler_estimate: float
    classification_probs: Dict[str, float]
    contact_quality: float
    intermittent: bool
    faded: bool
    lost: bool
    ambiguity_flags: List[str]
    source_channels: List[str]
    history_window_summary: Dict[str, float]
    lifecycle_state: str = "tracking"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "track_id": self.track_id,
            "first_seen_at": self.first_seen_at,
            "last_updated_at": self.last_updated_at,
            "bearing_deg_estimate": self.bearing_deg_estimate,
            "bearing_confidence": self.bearing_confidence,
            "bearing_rate_deg_per_min": self.bearing_rate_deg_per_min,
            "signal_strength": self.signal_strength,
            "signal_strength_trend": self.signal_strength_trend,
            "doppler_estimate": self.doppler_estimate,
            "classification_probs": dict(self.classification_probs),
            "contact_quality": self.contact_quality,
            "intermittent": self.intermittent,
            "faded": self.faded,
            "lost": self.lost,
            "ambiguity_flags": list(self.ambiguity_flags),
            "source_channels": list(self.source_channels),
            "history_window_summary": dict(self.history_window_summary),
            "lifecycle_state": self.lifecycle_state,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "PerceivedTrack":
        return cls(
            track_id=str(payload["track_id"]),
            first_seen_at=float(payload["first_seen_at"]),
            last_updated_at=float(payload["last_updated_at"]),
            bearing_deg_estimate=float(payload["bearing_deg_estimate"]),
            bearing_confidence=float(payload["bearing_confidence"]),
            bearing_rate_deg_per_min=float(payload["bearing_rate_deg_per_min"]),
            signal_strength=float(payload["signal_strength"]),
            signal_strength_trend=float(payload["signal_strength_trend"]),
            doppler_estimate=float(payload["doppler_estimate"]),
            classification_probs={str(k): float(v) for k, v in payload["classification_probs"].items()},
            contact_quality=float(payload["contact_quality"]),
            intermittent=bool(payload["intermittent"]),
            faded=bool(payload["faded"]),
            lost=bool(payload["lost"]),
            ambiguity_flags=[str(v) for v in payload["ambiguity_flags"]],
            source_channels=[str(v) for v in payload["source_channels"]],
            history_window_summary={str(k): float(v) for k, v in payload["history_window_summary"].items()},
            lifecycle_state=str(payload.get("lifecycle_state", "tracking")),
        )


@dataclass(frozen=True)
class SonarEvent:
    event_type: str
    tick: int
    t: float
    track_id: str | None
    severity: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "tick": self.tick,
            "t": self.t,
            "track_id": self.track_id,
            "severity": self.severity,
            "details": dict(self.details),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "SonarEvent":
        return cls(
            event_type=str(payload["event_type"]),
            tick=int(payload["tick"]),
            t=float(payload["t"]),
            track_id=str(payload["track_id"]) if payload.get("track_id") is not None else None,
            severity=str(payload["severity"]),
            details=dict(payload.get("details", {})),
        )


@dataclass(frozen=True)
class SonarConsoleFrame:
    tick: int
    t: float
    ownship: OwnshipSensorContext
    tracks: List[PerceivedTrack]
    events: List[SonarEvent]
    fire_control: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "tick": self.tick,
            "t": self.t,
            "ownship": self.ownship.to_dict(),
            "tracks": [track.to_dict() for track in self.tracks],
            "events": [event.to_dict() for event in self.events],
            "fire_control": dict(self.fire_control),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "SonarConsoleFrame":
        return cls(
            schema_version=str(payload.get("schema_version", SCHEMA_VERSION)),
            tick=int(payload["tick"]),
            t=float(payload["t"]),
            ownship=OwnshipSensorContext.from_dict(payload["ownship"]),
            tracks=[PerceivedTrack.from_dict(item) for item in payload.get("tracks", [])],
            events=[SonarEvent.from_dict(item) for item in payload.get("events", [])],
            fire_control=dict(payload["fire_control"]) if isinstance(payload.get("fire_control"), dict) else {},
        )


@dataclass(frozen=True)
class TruthEntity:
    entity_id: str
    kind: str
    bearing_deg_true: float
    range_m_true: float
    course_deg_true: float
    speed_mps_true: float
    depth_m_true: float
    detectability: float
    occlusion_layers: int
    matched_track_id: str | None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "kind": self.kind,
            "bearing_deg_true": self.bearing_deg_true,
            "range_m_true": self.range_m_true,
            "course_deg_true": self.course_deg_true,
            "speed_mps_true": self.speed_mps_true,
            "depth_m_true": self.depth_m_true,
            "detectability": self.detectability,
            "occlusion_layers": self.occlusion_layers,
            "matched_track_id": self.matched_track_id,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "TruthEntity":
        return cls(
            entity_id=str(payload["entity_id"]),
            kind=str(payload["kind"]),
            bearing_deg_true=float(payload["bearing_deg_true"]),
            range_m_true=float(payload["range_m_true"]),
            course_deg_true=float(payload["course_deg_true"]),
            speed_mps_true=float(payload["speed_mps_true"]),
            depth_m_true=float(payload["depth_m_true"]),
            detectability=float(payload["detectability"]),
            occlusion_layers=int(payload["occlusion_layers"]),
            matched_track_id=str(payload["matched_track_id"]) if payload.get("matched_track_id") is not None else None,
        )


@dataclass(frozen=True)
class GroundTruthFrame:
    tick: int
    t: float
    entities: List[TruthEntity]
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "tick": self.tick,
            "t": self.t,
            "entities": [entity.to_dict() for entity in self.entities],
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "GroundTruthFrame":
        return cls(
            schema_version=str(payload.get("schema_version", SCHEMA_VERSION)),
            tick=int(payload["tick"]),
            t=float(payload["t"]),
            entities=[TruthEntity.from_dict(item) for item in payload.get("entities", [])],
        )


@dataclass(frozen=True)
class TrackTruthAlignment:
    tick: int
    t: float
    track_id: str | None
    entity_id: str | None
    status: str
    bearing_error_deg: float | None
    range_error_m: float | None
    confidence: float
    predicted_label: str | None
    true_label: str | None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tick": self.tick,
            "t": self.t,
            "track_id": self.track_id,
            "entity_id": self.entity_id,
            "status": self.status,
            "bearing_error_deg": self.bearing_error_deg,
            "range_error_m": self.range_error_m,
            "confidence": self.confidence,
            "predicted_label": self.predicted_label,
            "true_label": self.true_label,
        }


__all__ = [
    "SCHEMA_VERSION",
    "OwnshipSensorContext",
    "PerceivedTrack",
    "SonarEvent",
    "SonarConsoleFrame",
    "TruthEntity",
    "GroundTruthFrame",
    "TrackTruthAlignment",
]
