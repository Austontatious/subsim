from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_ROOT = REPO_ROOT / "data" / "hydrophone" / "manifests"
ALLOWED_LABELS = {
    "surface_vessel",
    "biologic_mammal",
    "biologic_fish",
    "ambient_ocean",
    "synthetic_submarine_like",
    "unknown_or_noise",
}
DATASET_REQUIRED = {
    "dataset_id",
    "name",
    "source_url",
    "license",
    "redistribution",
    "commercial_use",
    "license_reviewed",
    "license_notes",
    "access_method",
    "status",
    "notes",
}
CLIP_REQUIRED = {
    "clip_id",
    "dataset_id",
    "source_path",
    "normalized_path",
    "label",
    "sub_label",
    "sample_rate_hz",
    "duration_sec",
    "group_id",
    "license",
    "provenance",
}


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def test_dataset_manifest_jsonl_is_parseable_and_complete() -> None:
    path = MANIFEST_ROOT / "datasets.jsonl"
    assert path.exists()
    rows = _read_jsonl(path)
    assert rows
    for row in rows:
        assert DATASET_REQUIRED <= set(row)
        assert row["status"] in {"sampled", "skipped", "blocked", "manual_required"}
        assert row["access_method"] in {"direct_download", "manual", "api", "skipped"}
        assert row["redistribution"] in {"allowed", "not_allowed", "unclear"}
        assert row["commercial_use"] in {"allowed", "not_allowed", "unclear"}
        assert isinstance(row["license_reviewed"], bool)
        assert isinstance(row["license_notes"], str)


def test_clip_manifest_jsonl_rows_use_allowed_schema_and_labels() -> None:
    path = MANIFEST_ROOT / "clips.jsonl"
    assert path.exists()
    for row in _read_jsonl(path):
        assert CLIP_REQUIRED <= set(row)
        assert row["label"] in ALLOWED_LABELS
        assert row["group_id"]
        assert isinstance(row["provenance"], dict)
        assert {"source_url", "downloaded_at", "original_filename"} <= set(row["provenance"])
