from __future__ import annotations

import math

import numpy as np

from scripts.hydrophone.extract_hydrophone_features import extract_feature_row, feature_columns


CORE_FEATURES = [
    "rms_energy",
    "zero_crossing_rate",
    "spectral_centroid_hz",
    "spectral_bandwidth_hz",
    "spectral_rolloff_hz",
    "dominant_frequency_hz",
    "spectral_flatness",
    "mel_mean",
    "mel_std",
]


def test_feature_extraction_on_tiny_sine_noise_fixture_has_no_nans() -> None:
    sample_rate = 16000
    t = np.arange(sample_rate, dtype=np.float32) / sample_rate
    rng = np.random.default_rng(123)
    samples = 0.4 * np.sin(2.0 * np.pi * 440.0 * t) + 0.02 * rng.normal(0.0, 1.0, len(t))

    row = extract_feature_row(
        samples.astype(np.float32),
        sample_rate,
        {
            "clip_id": "fixture_001",
            "dataset_id": "fixture",
            "label": "unknown_or_noise",
            "group_id": "fixture_source_a",
        },
    )

    assert row["clip_id"] == "fixture_001"
    assert row["group_id"] == "fixture_source_a"
    assert "group_id" in feature_columns()
    assert row["sample_rate_hz"] == sample_rate
    for feature in CORE_FEATURES:
        assert feature in row
        assert math.isfinite(float(row[feature]))
    assert abs(float(row["dominant_frequency_hz"]) - 440.0) < 20.0
    for idx in range(1, 14):
        assert math.isfinite(float(row[f"mfcc_{idx:02d}_mean"]))
        assert math.isfinite(float(row[f"mfcc_{idx:02d}_std"]))
