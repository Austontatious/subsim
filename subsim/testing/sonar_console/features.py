"""Derived trend features for perceived sonar tracks."""
from __future__ import annotations

import math
from typing import Sequence


def circular_delta_deg(current: float, previous: float) -> float:
    """Return signed angular difference in degrees on [-180, 180]."""
    return (current - previous + 540.0) % 360.0 - 180.0


def bearing_rate_deg_per_min(history: Sequence[tuple[float, float, float]]) -> float:
    """Estimate bearing trend from recent (t, bearing_deg, strength) history."""
    if len(history) < 2:
        return 0.0
    dt = max(1e-6, history[-1][0] - history[0][0])
    accum = 0.0
    for idx in range(1, len(history)):
        accum += circular_delta_deg(history[idx][1], history[idx - 1][1])
    return accum / dt * 60.0


def signal_strength_trend(history: Sequence[tuple[float, float, float]]) -> float:
    """Linearized trend from first/last signal sample."""
    if len(history) < 2:
        return 0.0
    dt = max(1e-6, history[-1][0] - history[0][0])
    return (history[-1][2] - history[0][2]) / dt


def doppler_estimate(history: Sequence[tuple[float, float, float]]) -> float:
    """Proxy for closing/opening dynamics from bearing churn and strength trend."""
    if len(history) < 2:
        return 0.0
    br = abs(bearing_rate_deg_per_min(history))
    ss = signal_strength_trend(history)
    return (ss * 12.0) - (br / 180.0)


def history_window_summary(history: Sequence[tuple[float, float, float]]) -> dict[str, float]:
    if not history:
        return {
            "window_samples": 0.0,
            "window_duration_s": 0.0,
            "bearing_span_deg": 0.0,
            "strength_mean": 0.0,
            "strength_min": 0.0,
            "strength_max": 0.0,
        }
    bearings = [sample[1] for sample in history]
    strengths = [sample[2] for sample in history]
    duration = history[-1][0] - history[0][0] if len(history) > 1 else 0.0
    span = 0.0
    for idx in range(1, len(bearings)):
        span += abs(circular_delta_deg(bearings[idx], bearings[idx - 1]))
    return {
        "window_samples": float(len(history)),
        "window_duration_s": float(max(0.0, duration)),
        "bearing_span_deg": float(span),
        "strength_mean": float(sum(strengths) / len(strengths)),
        "strength_min": float(min(strengths)),
        "strength_max": float(max(strengths)),
    }


def normalize_label_probs(raw: dict[str, float]) -> dict[str, float]:
    clipped = {label: max(0.0, min(1.0, value)) for label, value in raw.items()}
    total = sum(clipped.values())
    if total <= 1e-9:
        return {label: 0.0 for label in clipped}
    return {label: value / total for label, value in clipped.items()}


def top_label(prob_map: dict[str, float]) -> str | None:
    if not prob_map:
        return None
    return max(prob_map.items(), key=lambda item: item[1])[0]


def mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def finite(value: float) -> float:
    if math.isfinite(value):
        return value
    return 0.0


__all__ = [
    "bearing_rate_deg_per_min",
    "signal_strength_trend",
    "doppler_estimate",
    "history_window_summary",
    "normalize_label_probs",
    "top_label",
    "circular_delta_deg",
    "mean",
    "finite",
]
