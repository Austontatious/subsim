"""Perception logic for machine-readable sonar track estimation."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Mapping, Sequence

from ...engine.sensors import PassiveContact, PingReturn
from .contracts import OwnshipSensorContext, PerceivedTrack, SonarEvent
from .features import (
    bearing_rate_deg_per_min,
    circular_delta_deg,
    doppler_estimate,
    finite,
    history_window_summary,
    normalize_label_probs,
    signal_strength_trend,
)


_WEAK_PASSIVE_CONFIDENCE = 0.55
_WEAK_PASSIVE_SIGNAL = 0.35
_WEAK_PASSIVE_CLASSIFICATION = 0.60
_PASSIVE_SUSPECT_TICKS = 2
_PASSIVE_CLUTTER_TICKS = 3


@dataclass
class _TrackState:
    source_id: str
    track_id: str
    first_seen_at: float
    last_updated_at: float
    last_bearing_deg: float
    last_confidence: float
    last_signal_strength: float
    occlusion_layers: int
    classification_confidence: float = 0.0
    missed_ticks: int = 0
    reacquires: int = 0
    unconfirmed_weak_ticks: int = 0
    history: deque[tuple[float, float, float]] = field(default_factory=deque)


class PerceptionEngine:
    """Stateful estimator that transforms raw sensor tracks into AI-facing perceptions."""

    def __init__(
        self,
        *,
        history_window: int = 12,
        detection_threshold: float = 0.12,
        fade_after_ticks: int = 2,
        drop_after_ticks: int = 8,
    ) -> None:
        self.history_window = max(3, history_window)
        self.detection_threshold = max(0.0, min(1.0, detection_threshold))
        self.fade_after_ticks = max(1, fade_after_ticks)
        self.drop_after_ticks = max(self.fade_after_ticks + 1, drop_after_ticks)
        self._purge_after_ticks = self.drop_after_ticks + self.history_window
        self._states: Dict[str, _TrackState] = {}
        self._next_track_num = 1

    def update(
        self,
        *,
        tick: int,
        t: float,
        passive_tracks: Sequence[PassiveContact],
        ping_returns: Sequence[PingReturn],
        ownship: OwnshipSensorContext,
        classification_scores: Mapping[str, float],
    ) -> tuple[list[PerceivedTrack], list[SonarEvent], dict[str, str]]:
        events: list[SonarEvent] = []
        ping_contact_ids = {ret.contact_id for ret in ping_returns}
        visible_sources: set[str] = set()

        if ownship.self_noise_bucket == "high":
            events.append(
                SonarEvent(
                    event_type="high_self_noise",
                    tick=tick,
                    t=t,
                    track_id=None,
                    severity="warn",
                    details={"self_noise": ownship.self_noise},
                )
            )

        for raw in sorted(passive_tracks, key=lambda item: item.contact_id):
            source_id = raw.contact_id
            signal = max(0.0, min(1.0, raw.gain))
            confidence = max(0.0, min(1.0, raw.confidence))
            detectable = confidence >= self.detection_threshold or source_id in ping_contact_ids

            if not detectable:
                continue
            visible_sources.add(source_id)
            state = self._states.get(source_id)
            if state is None:
                state = _TrackState(
                    source_id=source_id,
                    track_id=self._next_track_id(),
                    first_seen_at=t,
                    last_updated_at=t,
                    last_bearing_deg=raw.azimuth_deg,
                    last_confidence=confidence,
                    last_signal_strength=signal,
                    occlusion_layers=raw.occlusion_layers,
                )
                state.history = deque(maxlen=self.history_window)
                self._states[source_id] = state
                events.append(
                    SonarEvent(
                        event_type="contact_detected",
                        tick=tick,
                        t=t,
                        track_id=state.track_id,
                        severity="info",
                        details={"source_channels": ["passive"]},
                    )
                )
            elif state.missed_ticks >= self.fade_after_ticks:
                state.reacquires += 1
                events.append(
                    SonarEvent(
                        event_type="contact_reacquired",
                        tick=tick,
                        t=t,
                        track_id=state.track_id,
                        severity="info",
                        details={"missed_ticks": state.missed_ticks},
                    )
                )

            bearing_delta = abs(circular_delta_deg(raw.azimuth_deg, state.last_bearing_deg))
            if bearing_delta >= 20.0:
                events.append(
                    SonarEvent(
                        event_type="bearing_shifted",
                        tick=tick,
                        t=t,
                        track_id=state.track_id,
                        severity="info",
                        details={"delta_deg": bearing_delta},
                    )
                )

            if signal > (state.last_signal_strength + 0.12):
                events.append(
                    SonarEvent(
                        event_type="contact_strengthened",
                        tick=tick,
                        t=t,
                        track_id=state.track_id,
                        severity="info",
                        details={"signal_strength": signal},
                    )
                )

            prior_class = state.classification_confidence
            classify = max(prior_class * 0.92, float(classification_scores.get(source_id, 0.0)))
            classify = max(0.0, min(1.0, classify))
            if abs(classify - prior_class) >= 0.2:
                events.append(
                    SonarEvent(
                        event_type="classification_changed",
                        tick=tick,
                        t=t,
                        track_id=state.track_id,
                        severity="info",
                        details={"previous": prior_class, "current": classify},
                    )
                )

            state.last_updated_at = t
            state.last_bearing_deg = raw.azimuth_deg
            state.last_confidence = confidence
            state.last_signal_strength = signal
            state.occlusion_layers = raw.occlusion_layers
            state.classification_confidence = classify
            state.missed_ticks = 0
            passive_only = source_id not in ping_contact_ids
            if self._weak_passive_candidate(
                passive_only=passive_only,
                confidence=confidence,
                signal=signal,
                classification_confidence=classify,
            ):
                state.unconfirmed_weak_ticks += 1
            else:
                state.unconfirmed_weak_ticks = 0
            if state.unconfirmed_weak_ticks == _PASSIVE_CLUTTER_TICKS:
                events.append(
                    SonarEvent(
                        event_type="clutter_rejected",
                        tick=tick,
                        t=t,
                        track_id=state.track_id,
                        severity="warn",
                        details={
                            "reason": "unconfirmed_passive_clutter",
                            "confidence": confidence,
                            "signal_strength": signal,
                        },
                    )
                )
            state.history.append((t, raw.azimuth_deg, signal))

        for source_id, state in self._states.items():
            if source_id in visible_sources:
                continue
            state.missed_ticks += 1
            if state.missed_ticks == self.fade_after_ticks:
                events.append(
                    SonarEvent(
                        event_type="contact_faded",
                        tick=tick,
                        t=t,
                        track_id=state.track_id,
                        severity="warn",
                        details={"missed_ticks": state.missed_ticks},
                    )
                )
            if state.missed_ticks == self.drop_after_ticks:
                events.append(
                    SonarEvent(
                        event_type="contact_lost",
                        tick=tick,
                        t=t,
                        track_id=state.track_id,
                        severity="warn",
                        details={"missed_ticks": state.missed_ticks},
                    )
                )

        tracks: list[PerceivedTrack] = []
        stale_sources: list[str] = []
        for source_id, state in sorted(self._states.items(), key=lambda item: item[1].track_id):
            if state.missed_ticks > self._purge_after_ticks:
                stale_sources.append(source_id)
                continue
            if state.unconfirmed_weak_ticks > _PASSIVE_CLUTTER_TICKS:
                continue

            if state.missed_ticks == 0:
                confidence = state.last_confidence
                signal = state.last_signal_strength
            else:
                decay = max(0.0, 1.0 - (state.missed_ticks / max(1, self.drop_after_ticks)))
                confidence = state.last_confidence * decay
                signal = state.last_signal_strength * decay

            faded = state.missed_ticks >= self.fade_after_ticks and state.missed_ticks < self.drop_after_ticks
            channels = ["passive"]
            if source_id in ping_contact_ids:
                channels.append("active_ping")
            passive_only = "active_ping" not in channels
            unconfirmed_weak_ticks = state.unconfirmed_weak_ticks if passive_only else 0
            passive_clutter_lost = unconfirmed_weak_ticks >= _PASSIVE_CLUTTER_TICKS
            faded = faded or (
                _PASSIVE_SUSPECT_TICKS <= unconfirmed_weak_ticks < _PASSIVE_CLUTTER_TICKS
            )
            lost = state.missed_ticks >= self.drop_after_ticks or passive_clutter_lost
            intermittent = (
                state.reacquires > 0
                or state.missed_ticks > 0
                or unconfirmed_weak_ticks >= _PASSIVE_SUSPECT_TICKS
            )
            readable_confidence = self._readability_confidence(
                confidence=confidence,
                signal=signal,
                classification_confidence=state.classification_confidence,
                passive_only=passive_only,
                unconfirmed_weak_ticks=unconfirmed_weak_ticks,
            )

            ambiguity_flags = self._ambiguity_flags(
                ownship=ownship,
                confidence=readable_confidence,
                signal=signal,
                classification_confidence=state.classification_confidence,
                occlusion_layers=state.occlusion_layers,
                missed_ticks=state.missed_ticks,
                passive_only=passive_only,
                unconfirmed_weak_ticks=unconfirmed_weak_ticks,
            )
            if any(flag in ambiguity_flags for flag in {"low_confidence", "possible_contact", "suspect_contact", "clutter"}):
                events.append(
                    SonarEvent(
                        event_type="ambiguous_contact",
                        tick=tick,
                        t=t,
                        track_id=state.track_id,
                        severity="warn",
                        details={
                            "confidence": readable_confidence,
                            "signal_strength": signal,
                            "ambiguity_flags": list(ambiguity_flags),
                        },
                    )
                )

            class_probs = self._classification_probs(state.classification_confidence)
            contact_quality = self._contact_quality(
                confidence=readable_confidence,
                signal=signal,
                classification_confidence=state.classification_confidence,
                ownship=ownship,
                passive_only=passive_only,
                unconfirmed_weak_ticks=unconfirmed_weak_ticks,
            )
            history = list(state.history)
            track = PerceivedTrack(
                track_id=state.track_id,
                first_seen_at=state.first_seen_at,
                last_updated_at=state.last_updated_at,
                bearing_deg_estimate=state.last_bearing_deg,
                bearing_confidence=finite(readable_confidence),
                bearing_rate_deg_per_min=finite(bearing_rate_deg_per_min(history)),
                signal_strength=finite(signal),
                signal_strength_trend=finite(signal_strength_trend(history)),
                doppler_estimate=finite(doppler_estimate(history)),
                classification_probs=class_probs,
                contact_quality=contact_quality,
                intermittent=intermittent,
                faded=faded,
                lost=lost,
                ambiguity_flags=ambiguity_flags,
                source_channels=channels,
                history_window_summary=history_window_summary(history),
                lifecycle_state=self._lifecycle_state(
                    lost=lost,
                    faded=faded,
                    ambiguity_flags=ambiguity_flags,
                    source_channels=channels,
                    confidence=readable_confidence,
                    classification_confidence=state.classification_confidence,
                    contact_quality=contact_quality,
                    passive_clutter_lost=passive_clutter_lost,
                ),
            )
            tracks.append(track)

        for source_id in stale_sources:
            del self._states[source_id]

        source_to_track = {source_id: state.track_id for source_id, state in self._states.items()}
        return tracks, events, source_to_track

    def _classification_probs(self, classification_confidence: float) -> dict[str, float]:
        hunter = max(0.0, min(1.0, classification_confidence))
        merchant = max(0.0, (1.0 - hunter) * 0.35)
        unknown = max(0.0, 1.0 - hunter - merchant)
        return normalize_label_probs(
            {
                "hunter": hunter,
                "merchant": merchant,
                "unknown": unknown,
            }
        )

    def _readability_confidence(
        self,
        *,
        confidence: float,
        signal: float,
        classification_confidence: float,
        passive_only: bool,
        unconfirmed_weak_ticks: int,
    ) -> float:
        readable = confidence
        if self._weak_passive_candidate(
            passive_only=passive_only,
            confidence=confidence,
            signal=signal,
            classification_confidence=classification_confidence,
        ):
            if unconfirmed_weak_ticks >= _PASSIVE_CLUTTER_TICKS:
                readable *= 0.45
            elif unconfirmed_weak_ticks >= _PASSIVE_SUSPECT_TICKS:
                readable *= 0.70
            else:
                readable *= 0.85
        return max(0.0, min(1.0, readable))

    def _contact_quality(
        self,
        *,
        confidence: float,
        signal: float,
        classification_confidence: float,
        ownship: OwnshipSensorContext,
        passive_only: bool,
        unconfirmed_weak_ticks: int,
    ) -> float:
        quality = (confidence + signal + (1.0 - ownship.self_noise)) / 3.0
        if ownship.masking:
            quality *= 0.85
        if self._weak_passive_candidate(
            passive_only=passive_only,
            confidence=confidence,
            signal=signal,
            classification_confidence=classification_confidence,
        ):
            if unconfirmed_weak_ticks >= _PASSIVE_CLUTTER_TICKS:
                quality *= 0.45
            elif unconfirmed_weak_ticks >= _PASSIVE_SUSPECT_TICKS:
                quality *= 0.65
            else:
                quality *= 0.82
        return max(0.0, min(1.0, quality))

    def _ambiguity_flags(
        self,
        *,
        ownship: OwnshipSensorContext,
        confidence: float,
        signal: float,
        classification_confidence: float,
        occlusion_layers: int,
        missed_ticks: int,
        passive_only: bool,
        unconfirmed_weak_ticks: int,
    ) -> list[str]:
        flags: list[str] = []
        if confidence < 0.25:
            flags.append("low_confidence")
        if signal < 0.15:
            flags.append("weak_signal")
        if occlusion_layers > 0:
            flags.append("thermocline_occlusion")
        if ownship.masking:
            flags.append("self_noise_masking")
        if missed_ticks > 0:
            flags.append("intermittent_update")
        if self._weak_passive_candidate(
            passive_only=passive_only,
            confidence=confidence,
            signal=signal,
            classification_confidence=classification_confidence,
        ):
            if unconfirmed_weak_ticks >= _PASSIVE_CLUTTER_TICKS:
                flags.extend(["clutter", "unconfirmed_contact"])
            elif unconfirmed_weak_ticks >= _PASSIVE_SUSPECT_TICKS:
                flags.append("suspect_contact")
            else:
                flags.append("possible_contact")
        return flags

    def _weak_passive_candidate(
        self,
        *,
        passive_only: bool,
        confidence: float,
        signal: float,
        classification_confidence: float,
    ) -> bool:
        return (
            passive_only
            and confidence < _WEAK_PASSIVE_CONFIDENCE
            and signal < _WEAK_PASSIVE_SIGNAL
            and classification_confidence < _WEAK_PASSIVE_CLASSIFICATION
        )

    def _lifecycle_state(
        self,
        *,
        lost: bool,
        faded: bool,
        ambiguity_flags: Sequence[str],
        source_channels: Sequence[str],
        confidence: float,
        classification_confidence: float,
        contact_quality: float,
        passive_clutter_lost: bool,
    ) -> str:
        flags = {str(flag) for flag in ambiguity_flags}
        channels = {str(channel) for channel in source_channels}
        if passive_clutter_lost or "clutter" in flags or "unconfirmed_contact" in flags:
            return "rejected"
        if lost:
            return "lost"
        if "suspect_contact" in flags:
            return "suspect"
        if "possible_contact" in flags:
            return "possible"
        if faded or "intermittent_update" in flags:
            return "fading"
        if "active_ping" in channels or (
            confidence >= 0.68
            and classification_confidence >= 0.65
            and contact_quality >= 0.62
        ):
            return "confirmed"
        return "tracking"

    def _next_track_id(self) -> str:
        track_id = f"T{self._next_track_num:03d}"
        self._next_track_num += 1
        return track_id


__all__ = ["PerceptionEngine"]
