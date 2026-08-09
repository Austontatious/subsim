from __future__ import annotations

import json
from pathlib import Path

from scripts.hydrophone.build_fixed_eval_splits import build_fixed_splits
from scripts.hydrophone.hydrophone_common import read_jsonl


ALLOWED_LABELS = {
    "surface_vessel",
    "biologic_mammal",
    "biologic_fish",
    "ambient_ocean",
    "synthetic_submarine_like",
    "unknown_or_noise",
}


def _clip(idx: int, label: str, group_id: str) -> dict:
    return {
        "clip_id": f"{label}_{idx:03d}",
        "dataset_id": "fixture",
        "source_path": f"raw/{group_id}.wav",
        "normalized_path": f"norm/{label}_{idx:03d}.wav",
        "label": label,
        "sub_label": label,
        "sample_rate_hz": 16000,
        "duration_sec": 1.0,
        "group_id": group_id,
        "license": "fixture",
        "provenance": {"source_url": "fixture", "downloaded_at": "", "original_filename": f"{group_id}.wav"},
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_fixed_split_files_are_valid_and_group_disjoint(tmp_path: Path) -> None:
    rows = []
    idx = 0
    for label in ["ambient_ocean", "biologic_fish", "surface_vessel"]:
        for group in range(5):
            idx += 1
            rows.append(_clip(idx, label, f"{label}_group_{group}"))
    clips_manifest = tmp_path / "clips.jsonl"
    split_dir = tmp_path / "splits"
    _write_jsonl(clips_manifest, rows)

    summary = build_fixed_splits(
        clips_manifest=clips_manifest,
        output_dir=split_dir,
        report_path=tmp_path / "report.md",
        seed=1337,
    )

    assert (split_dir / "split_summary.json").exists()
    assert summary["group_leakage_prevented"]
    group_to_split = {}
    for split in ["train", "validation", "heldout_source_eval"]:
        split_rows = read_jsonl(split_dir / f"{split}.jsonl")
        assert split_rows
        for row in split_rows:
            assert row["label"] in ALLOWED_LABELS
            group = row["group_id"]
            assert group not in group_to_split
            group_to_split[group] = split


def test_split_builder_handles_tiny_fixture_data_gracefully(tmp_path: Path) -> None:
    clips_manifest = tmp_path / "clips.jsonl"
    split_dir = tmp_path / "splits"
    _write_jsonl(
        clips_manifest,
        [_clip(1, "ambient_ocean", "ambient_only"), _clip(2, "surface_vessel", "surface_only")],
    )

    summary = build_fixed_splits(
        clips_manifest=clips_manifest,
        output_dir=split_dir,
        report_path=tmp_path / "report.md",
        seed=99,
    )

    assert summary["total_clips"] == 2
    assert summary["group_leakage_prevented"]
    assert summary["degradation_notes"]
