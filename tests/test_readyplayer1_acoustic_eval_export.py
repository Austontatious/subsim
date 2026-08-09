from __future__ import annotations

import json
from pathlib import Path

from scripts.hydrophone.export_readyplayer1_acoustic_eval_cases import export_readyplayer1_cases
from scripts.hydrophone.hydrophone_common import read_jsonl


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _clip(label: str, clip_id: str) -> dict:
    return {
        "clip_id": clip_id,
        "dataset_id": "fixture",
        "normalized_path": f"norm/{clip_id}.wav",
        "label": label,
        "sub_label": label,
        "duration_sec": 1.0,
        "sample_rate_hz": 16000,
        "group_id": f"group_{clip_id}",
        "license": "fixture_license",
    }


def test_readyplayer1_eval_export_expected_behaviors_and_real_only_default(tmp_path: Path) -> None:
    clips = tmp_path / "clips.jsonl"
    datasets = tmp_path / "datasets.jsonl"
    split_dir = tmp_path / "splits"
    synthetic = tmp_path / "synthetic.jsonl"
    out = tmp_path / "cases.jsonl"
    clip_rows = [
        _clip("surface_vessel", "surface_001"),
        _clip("biologic_fish", "fish_001"),
        _clip("ambient_ocean", "ambient_001"),
    ]
    _write_jsonl(clips, clip_rows)
    _write_jsonl(datasets, [{"dataset_id": "fixture", "commercial_use": "allowed", "license": "fixture"}])
    _write_jsonl(split_dir / "train.jsonl", [clip_rows[0]])
    _write_jsonl(split_dir / "validation.jsonl", [clip_rows[1]])
    _write_jsonl(split_dir / "heldout_source_eval.jsonl", [clip_rows[2]])
    _write_jsonl(synthetic, [{"synthetic_id": "syn_sub_like_000001", "path": "synthetic.wav", "label": "synthetic_submarine_like"}])

    cases = export_readyplayer1_cases(
        clips_manifest=clips,
        datasets_manifest=datasets,
        split_dir=split_dir,
        synthetic_manifest=synthetic,
        output_path=out,
        report_path=tmp_path / "report.md",
    )

    assert len(cases) == 3
    by_label = {case["expected"]["broad_class"]: case for case in read_jsonl(out)}
    assert by_label["surface_vessel"]["expected"]["should_track"]
    assert by_label["surface_vessel"]["expected"]["should_confirm"]
    assert by_label["biologic_fish"]["expected"]["should_reject_as_clutter"]
    assert by_label["ambient_ocean"]["expected"]["should_reject_as_clutter"]
    assert "synthetic_submarine_like" not in by_label


def test_readyplayer1_eval_export_can_include_synthetic_explicitly(tmp_path: Path) -> None:
    clips = tmp_path / "clips.jsonl"
    datasets = tmp_path / "datasets.jsonl"
    split_dir = tmp_path / "splits"
    synthetic = tmp_path / "synthetic.jsonl"
    out = tmp_path / "cases.jsonl"
    _write_jsonl(clips, [_clip("ambient_ocean", "ambient_001")])
    _write_jsonl(datasets, [])
    _write_jsonl(split_dir / "train.jsonl", [])
    _write_jsonl(split_dir / "validation.jsonl", [])
    _write_jsonl(split_dir / "heldout_source_eval.jsonl", [])
    _write_jsonl(synthetic, [{"synthetic_id": "syn_sub_like_000001", "path": "synthetic.wav", "label": "synthetic_submarine_like"}])

    cases = export_readyplayer1_cases(
        clips_manifest=clips,
        datasets_manifest=datasets,
        split_dir=split_dir,
        synthetic_manifest=synthetic,
        output_path=out,
        report_path=tmp_path / "report.md",
        include_synthetic=True,
    )

    synthetic_cases = [case for case in cases if case["expected"]["broad_class"] == "synthetic_submarine_like"]
    assert synthetic_cases
    assert synthetic_cases[0]["split"] == "synthetic"
    assert synthetic_cases[0]["expected"]["should_track"]
