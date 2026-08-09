"""Canonical acoustic contract shared across desktop, Godot, and playtester paths."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Tuple


SCHEMA_VERSION = "acoustic-substrate.v1"
CONTACT_VARIANTS: Tuple[str, ...] = ("clean", "lp1", "lp2", "lp3")

# Canonical event cue taxonomy across surfaces. Not every surface renders all cues.
EVENT_CUE_TYPES: Tuple[str, ...] = (
    "PING",
    "RETURN",
    "CONTACT_NEW",
    "FIRE_SOLUTION_START",
    "FIRE_SOLUTION_READY",
    "FIRE_SOLUTION_MISS",
    "TORP_LAUNCH",
    "TORP_IN_WATER",
    "TORP_HIT",
    "DETONATION",
    "UI_CONFIRM",
    "UI_ALERT",
    "OBJECTIVE_STAGE_ADVANCE",
    "OBJECTIVE_COMPLETE",
    "OBJECTIVE_FAIL",
    "MODE_CHANGE",
)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def own_noise_bucket(own_noise: float) -> str:
    """Canonical own-noise bucket boundaries shared by game + sonar console."""
    own_noise = _clamp01(own_noise)
    if own_noise < 0.25:
        return "low"
    if own_noise < 0.55:
        return "medium"
    return "high"


def pick_contact_variant(*, confidence: float, occlusion_layers: int, own_noise: float) -> str:
    """Choose an acoustic variant for passive contacts from the canonical contract."""
    confidence = _clamp01(confidence)
    own_noise = _clamp01(own_noise)
    score = (max(0, int(occlusion_layers)) * 0.45) + ((1.0 - confidence) * 0.55) + (own_noise * 0.35)
    if score >= 1.20:
        return "lp3"
    if score >= 0.80:
        return "lp2"
    if score >= 0.35:
        return "lp1"
    return "clean"


@dataclass(frozen=True)
class AcousticFoundationState:
    ambient_level: float
    self_noise_level: float
    player_hum_level: float
    own_noise: float
    own_noise_bucket: str
    sensor_noise: float
    ping_active: bool
    masking: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ambient_level": self.ambient_level,
            "self_noise_level": self.self_noise_level,
            "player_hum_level": self.player_hum_level,
            "own_noise": self.own_noise,
            "own_noise_bucket": self.own_noise_bucket,
            "sensor_noise": self.sensor_noise,
            "ping_active": self.ping_active,
            "masking": self.masking,
        }


@dataclass(frozen=True)
class AcousticContactState:
    contact_id: str
    kind: str
    bearing_deg: float
    distance_m: float
    confidence: float
    gain: float
    occlusion_layers: int
    own_noise: float
    variant: str
    source_channels: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contact_id": self.contact_id,
            "kind": self.kind,
            "bearing_deg": self.bearing_deg,
            "distance_m": self.distance_m,
            "confidence": self.confidence,
            "gain": self.gain,
            "occlusion_layers": self.occlusion_layers,
            "own_noise": self.own_noise,
            "variant": self.variant,
            "source_channels": list(self.source_channels),
        }


def build_foundation_state(*, own_noise: float, sensor_noise: float, ping_active: bool) -> AcousticFoundationState:
    """Canonical foundation channels used by desktop and Godot playback surfaces."""
    own_noise = _clamp01(own_noise)
    sensor_noise = _clamp01(sensor_noise)
    ambient_level = _clamp01(0.20 + (sensor_noise * 0.32) - (0.06 if ping_active else 0.0))
    self_noise_level = _clamp01(0.08 + (own_noise * 0.72))
    player_hum_level = _clamp01(0.12 + (own_noise * 0.60))
    masking = bool(ping_active or own_noise > 0.55)
    return AcousticFoundationState(
        ambient_level=ambient_level,
        self_noise_level=self_noise_level,
        player_hum_level=player_hum_level,
        own_noise=own_noise,
        own_noise_bucket=own_noise_bucket(own_noise),
        sensor_noise=sensor_noise,
        ping_active=bool(ping_active),
        masking=masking,
    )


def build_contact_state(
    *,
    contact_id: str,
    kind: str,
    bearing_deg: float,
    distance_m: float,
    confidence: float,
    gain: float,
    occlusion_layers: int,
    own_noise: float,
    source_channels: Iterable[str] = ("passive",),
) -> AcousticContactState:
    variant = pick_contact_variant(
        confidence=confidence,
        occlusion_layers=occlusion_layers,
        own_noise=own_noise,
    )
    return AcousticContactState(
        contact_id=str(contact_id),
        kind=str(kind),
        bearing_deg=float(bearing_deg),
        distance_m=float(distance_m),
        confidence=_clamp01(confidence),
        gain=_clamp01(gain),
        occlusion_layers=max(0, int(occlusion_layers)),
        own_noise=_clamp01(own_noise),
        variant=variant,
        source_channels=tuple(str(ch) for ch in source_channels),
    )


__all__ = [
    "SCHEMA_VERSION",
    "CONTACT_VARIANTS",
    "EVENT_CUE_TYPES",
    "AcousticFoundationState",
    "AcousticContactState",
    "own_noise_bucket",
    "pick_contact_variant",
    "build_foundation_state",
    "build_contact_state",
]
