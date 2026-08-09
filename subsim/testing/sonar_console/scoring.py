"""Offline alignment and scoring metrics for sonar console runs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Sequence

from .contracts import GroundTruthFrame, PerceivedTrack, SonarConsoleFrame, TrackTruthAlignment
from .features import circular_delta_deg, mean, top_label


@dataclass(frozen=True)
class ScoreSummary:
    detection_latency_s: float
    track_persistence: float
    false_positive_rate: float
    classification_convergence_s: float | None
    mean_bearing_error_deg: float
    aligned_samples: int

    def to_dict(self) -> dict[str, float | int | None]:
        return {
            "detection_latency_s": self.detection_latency_s,
            "track_persistence": self.track_persistence,
            "false_positive_rate": self.false_positive_rate,
            "classification_convergence_s": self.classification_convergence_s,
            "mean_bearing_error_deg": self.mean_bearing_error_deg,
            "aligned_samples": self.aligned_samples,
        }


def align_frame(
    *,
    perceived: SonarConsoleFrame,
    truth: GroundTruthFrame,
) -> list[TrackTruthAlignment]:
    track_by_id: Dict[str, PerceivedTrack] = {track.track_id: track for track in perceived.tracks}
    alignments: list[TrackTruthAlignment] = []
    matched_track_ids: set[str] = set()

    for entity in truth.entities:
        track_id = entity.matched_track_id
        if track_id is None or track_id not in track_by_id:
            alignments.append(
                TrackTruthAlignment(
                    tick=truth.tick,
                    t=truth.t,
                    track_id=None,
                    entity_id=entity.entity_id,
                    status="missed",
                    bearing_error_deg=None,
                    range_error_m=None,
                    confidence=0.0,
                    predicted_label=None,
                    true_label=entity.kind,
                )
            )
            continue
        track = track_by_id[track_id]
        matched_track_ids.add(track_id)
        range_estimate = _range_estimate_from_signal(track.signal_strength)
        alignments.append(
            TrackTruthAlignment(
                tick=truth.tick,
                t=truth.t,
                track_id=track_id,
                entity_id=entity.entity_id,
                status="matched",
                bearing_error_deg=abs(circular_delta_deg(track.bearing_deg_estimate, entity.bearing_deg_true)),
                range_error_m=abs(range_estimate - entity.range_m_true),
                confidence=track.bearing_confidence,
                predicted_label=top_label(track.classification_probs),
                true_label=entity.kind,
            )
        )

    for track in perceived.tracks:
        if track.track_id in matched_track_ids:
            continue
        if track.lost:
            continue
        alignments.append(
            TrackTruthAlignment(
                tick=perceived.tick,
                t=perceived.t,
                track_id=track.track_id,
                entity_id=None,
                status="false_positive",
                bearing_error_deg=None,
                range_error_m=None,
                confidence=track.bearing_confidence,
                predicted_label=top_label(track.classification_probs),
                true_label=None,
            )
        )
    return alignments


def align_streams(
    *,
    perceived_frames: Sequence[SonarConsoleFrame],
    truth_frames: Sequence[GroundTruthFrame],
) -> list[TrackTruthAlignment]:
    if len(perceived_frames) != len(truth_frames):
        raise ValueError("Perceived and truth frame counts must match")
    rows: list[TrackTruthAlignment] = []
    for perceived, truth in zip(perceived_frames, truth_frames):
        rows.extend(align_frame(perceived=perceived, truth=truth))
    return rows


def score_alignment(rows: Iterable[TrackTruthAlignment]) -> ScoreSummary:
    alignments = list(rows)
    if not alignments:
        return ScoreSummary(
            detection_latency_s=0.0,
            track_persistence=0.0,
            false_positive_rate=0.0,
            classification_convergence_s=None,
            mean_bearing_error_deg=0.0,
            aligned_samples=0,
        )

    matched = [row for row in alignments if row.status == "matched"]
    missed = [row for row in alignments if row.status == "missed"]
    false_pos = [row for row in alignments if row.status == "false_positive"]

    detection_by_entity: dict[str, float] = {}
    first_truth_by_entity: dict[str, float] = {}
    convergence_by_entity: dict[str, float] = {}
    for row in alignments:
        if row.entity_id is None:
            continue
        first_truth_by_entity.setdefault(row.entity_id, row.t)
        if row.status == "matched":
            detection_by_entity.setdefault(row.entity_id, row.t)
            if row.predicted_label == row.true_label and row.confidence >= 0.55:
                convergence_by_entity.setdefault(row.entity_id, row.t)

    detection_latencies: list[float] = []
    for entity_id, truth_t in first_truth_by_entity.items():
        detection_t = detection_by_entity.get(entity_id)
        if detection_t is None:
            continue
        detection_latencies.append(max(0.0, detection_t - truth_t))

    persistence_den = len(matched) + len(missed)
    track_persistence = (len(matched) / persistence_den) if persistence_den else 0.0

    convergence_latencies: list[float] = []
    for entity_id, truth_t in first_truth_by_entity.items():
        conv_t = convergence_by_entity.get(entity_id)
        if conv_t is None:
            continue
        convergence_latencies.append(max(0.0, conv_t - truth_t))

    bearing_errors = [row.bearing_error_deg for row in matched if row.bearing_error_deg is not None]
    false_positive_rate = len(false_pos) / max(1, len(matched) + len(false_pos))
    return ScoreSummary(
        detection_latency_s=mean(detection_latencies),
        track_persistence=track_persistence,
        false_positive_rate=false_positive_rate,
        classification_convergence_s=mean(convergence_latencies) if convergence_latencies else None,
        mean_bearing_error_deg=mean(bearing_errors),
        aligned_samples=len(matched),
    )


def score_run(
    *,
    perceived_frames: Sequence[SonarConsoleFrame],
    truth_frames: Sequence[GroundTruthFrame],
) -> tuple[ScoreSummary, list[TrackTruthAlignment]]:
    rows = align_streams(perceived_frames=perceived_frames, truth_frames=truth_frames)
    summary = score_alignment(rows)
    return summary, rows


def _range_estimate_from_signal(signal_strength: float) -> float:
    signal = max(0.0, min(1.0, signal_strength))
    return (1.0 - signal) * 2000.0


__all__ = ["ScoreSummary", "align_frame", "align_streams", "score_alignment", "score_run"]
