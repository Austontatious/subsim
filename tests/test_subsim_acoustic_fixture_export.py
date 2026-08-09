from __future__ import annotations

import json
from pathlib import Path

from scripts.hydrophone.export_subsim_acoustic_fixtures import export_subsim_fixtures
from scripts.hydrophone.hydrophone_common import read_jsonl


VALID_ROLES = {"true_contact", "biologic_clutter", "ambient_clutter", "surface_contact", "unknown_noise"}
REQUIRED = {
    "fixture_id",
    "source_clip_id",
    "label",
    "sub_label",
    "normalized_path",
    "duration_sec",
    "sample_rate_hz",
    "group_id",
    "license",
    "redistribution",
    "commercial_use",
    "gameplay_role",
    "suggested_contact_confidence",
    "suggested_bearing_noise_deg",
    "suggested_range_noise_m",
    "notes",
}


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


def test_subsim_fixture_export_defaults_to_real_only_and_valid_roles(tmp_path: Path) -> None:
    clips = tmp_path / "clips.jsonl"
    datasets = tmp_path / "datasets.jsonl"
    synthetic = tmp_path / "synthetic.jsonl"
    out = tmp_path / "fixtures.jsonl"
    _write_jsonl(clips, [_clip("surface_vessel", "surface_001"), _clip("ambient_ocean", "ambient_001")])
    _write_jsonl(
        datasets,
        [{"dataset_id": "fixture", "license": "fixture_license", "redistribution": "allowed", "commercial_use": "allowed"}],
    )
    _write_jsonl(
        synthetic,
        [{"synthetic_id": "syn_sub_like_000001", "path": "synthetic.wav", "label": "synthetic_submarine_like"}],
    )

    rows = export_subsim_fixtures(
        clips_manifest=clips,
        datasets_manifest=datasets,
        synthetic_manifest=synthetic,
        output_path=out,
        report_path=tmp_path / "report.md",
    )

    assert len(rows) == 2
    for row in read_jsonl(out):
        assert REQUIRED <= set(row)
        assert row["gameplay_role"] in VALID_ROLES
        assert row["label"] != "synthetic_submarine_like"


def test_subsim_fixture_export_can_include_synthetic_explicitly(tmp_path: Path) -> None:
    clips = tmp_path / "clips.jsonl"
    datasets = tmp_path / "datasets.jsonl"
    synthetic = tmp_path / "synthetic.jsonl"
    out = tmp_path / "fixtures.jsonl"
    _write_jsonl(clips, [_clip("ambient_ocean", "ambient_001")])
    _write_jsonl(datasets, [])
    _write_jsonl(
        synthetic,
        [{"synthetic_id": "syn_sub_like_000001", "path": "synthetic.wav", "label": "synthetic_submarine_like"}],
    )

    rows = export_subsim_fixtures(
        clips_manifest=clips,
        datasets_manifest=datasets,
        synthetic_manifest=synthetic,
        output_path=out,
        report_path=tmp_path / "report.md",
        include_synthetic=True,
    )

    assert any(row["label"] == "synthetic_submarine_like" and row["gameplay_role"] == "true_contact" for row in rows)
