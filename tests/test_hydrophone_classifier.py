from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.hydrophone.train_hydrophone_classifier import train_classifier


def _feature_row(idx: int, label: str, group_id: str, value: float, *, dataset_id: str = "fixture") -> dict:
    return {
        "clip_id": f"clip_{idx:03d}",
        "dataset_id": dataset_id,
        "label": label,
        "group_id": group_id,
        "source_path": f"raw/{group_id}.wav",
        "normalized_path": f"norm/clip_{idx:03d}.wav",
        "duration_sec": 1.0,
        "sample_rate_hz": 16000,
        "rms_energy": value,
        "zero_crossing_rate": value / 10.0,
        "spectral_centroid_hz": value * 100.0,
        "spectral_bandwidth_hz": value * 10.0,
        "spectral_rolloff_hz": value * 120.0,
        "dominant_frequency_hz": value * 80.0,
        "spectral_flatness": value / 20.0,
        "mel_mean": value,
        "mel_std": value / 3.0,
    }


def test_classifier_gracefully_skips_too_small_dataset(tmp_path: Path) -> None:
    features_path = tmp_path / "features.csv"
    pd.DataFrame([_feature_row(1, "ambient_ocean", "g1", 0.1)]).to_csv(features_path, index=False)

    result = train_classifier(features_path=features_path, report_root=tmp_path)

    assert result["status"] == "skipped"
    assert result["reason"] == "too_few_classes"
    assert "Skipped" in (tmp_path / "classifier_baseline_report.md").read_text(encoding="utf-8")


def test_grouped_split_does_not_overlap_groups_when_possible(tmp_path: Path) -> None:
    rows = []
    idx = 0
    for label, offset in [("ambient_ocean", 1.0), ("surface_vessel", 4.0)]:
        for group_num in range(4):
            group_id = f"{label}_group_{group_num}"
            for _ in range(2):
                idx += 1
                rows.append(_feature_row(idx, label, group_id, offset + group_num))
    features_path = tmp_path / "features.csv"
    pd.DataFrame(rows).to_csv(features_path, index=False)

    result = train_classifier(features_path=features_path, report_root=tmp_path)
    metadata = json.loads((tmp_path / "classifier_split_metadata.json").read_text(encoding="utf-8"))

    assert result["status"] == "ran"
    assert metadata["split_strategy"] == "stable_grouped_by_group_id"
    assert set(metadata["train_groups"]).isdisjoint(metadata["test_groups"])


def test_synthetic_rows_are_excluded_by_default(tmp_path: Path) -> None:
    rows = [
        _feature_row(1, "ambient_ocean", "ambient_a", 0.1),
        _feature_row(2, "ambient_ocean", "ambient_b", 0.2),
        _feature_row(3, "surface_vessel", "surface_a", 2.0),
        _feature_row(4, "surface_vessel", "surface_b", 2.1),
        _feature_row(
            5,
            "synthetic_submarine_like",
            "synthetic_a",
            8.0,
            dataset_id="synthetic_generator",
        ),
    ]
    features_path = tmp_path / "features.csv"
    pd.DataFrame(rows).to_csv(features_path, index=False)

    result = train_classifier(features_path=features_path, report_root=tmp_path)
    metadata = json.loads((tmp_path / "classifier_split_metadata.json").read_text(encoding="utf-8"))

    assert result["status"] == "ran"
    assert not metadata["include_synthetic"]
    assert "synthetic_submarine_like" not in metadata["class_counts"]
    assert metadata["raw_feature_rows"] == 5
    assert metadata["training_rows"] == 4


def test_classifier_can_run_from_fixed_split_files_without_group_leakage(tmp_path: Path) -> None:
    rows = [
        _feature_row(1, "ambient_ocean", "ambient_train", 0.1),
        _feature_row(2, "surface_vessel", "surface_train", 2.0),
        _feature_row(3, "ambient_ocean", "ambient_validation", 0.2),
        _feature_row(4, "surface_vessel", "surface_validation", 2.1),
        _feature_row(5, "ambient_ocean", "ambient_heldout", 0.3),
        _feature_row(6, "surface_vessel", "surface_heldout", 2.2),
    ]
    features_path = tmp_path / "features.csv"
    split_dir = tmp_path / "splits"
    pd.DataFrame(rows).to_csv(features_path, index=False)
    split_dir.mkdir()
    for split, split_rows in {
        "train": rows[:2],
        "validation": rows[2:4],
        "heldout_source_eval": rows[4:6],
    }.items():
        (split_dir / f"{split}.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in split_rows),
            encoding="utf-8",
        )

    result = train_classifier(features_path=features_path, report_root=tmp_path, split_dir=split_dir)
    metadata = json.loads((tmp_path / "classifier_split_metadata.json").read_text(encoding="utf-8"))

    assert result["status"] == "ran"
    assert metadata["split_strategy"] == "fixed_split_manifest"
    train_groups = {row["group_id"] for row in rows[:2]}
    validation_groups = {row["group_id"] for row in rows[2:4]}
    heldout_groups = {row["group_id"] for row in rows[4:6]}
    assert train_groups.isdisjoint(validation_groups)
    assert train_groups.isdisjoint(heldout_groups)
    assert validation_groups.isdisjoint(heldout_groups)
    assert (tmp_path / "classifier_confusion_matrix_validation.csv").exists()
    assert (tmp_path / "classifier_confusion_matrix_heldout_source_eval.csv").exists()
