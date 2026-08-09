#!/usr/bin/env python3
"""Export hydrophone clip metadata as SubSim gameplay acoustic fixtures."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hydrophone_common import (  # noqa: E402
    DEFAULT_DATA_ROOT,
    DEFAULT_REPORT_ROOT,
    ensure_dir,
    ensure_hydrophone_layout,
    read_jsonl,
    write_jsonl,
    write_text,
    utc_now_iso,
)


GAMEPLAY_ROLE_BY_LABEL = {
    "surface_vessel": "surface_contact",
    "biologic_mammal": "biologic_clutter",
    "biologic_fish": "biologic_clutter",
    "ambient_ocean": "ambient_clutter",
    "synthetic_submarine_like": "true_contact",
    "unknown_or_noise": "unknown_noise",
}

CONFIDENCE_BY_LABEL = {
    "surface_vessel": 0.65,
    "biologic_mammal": 0.35,
    "biologic_fish": 0.25,
    "ambient_ocean": 0.10,
    "synthetic_submarine_like": 0.70,
    "unknown_or_noise": 0.05,
}


def _is_synthetic(row: dict[str, Any]) -> bool:
    return str(row.get("label")) == "synthetic_submarine_like" or str(row.get("dataset_id", "")).startswith("synthetic")


def _load_dataset_license_rows(datasets_manifest: Path) -> dict[str, dict[str, Any]]:
    return {str(row["dataset_id"]): row for row in read_jsonl(datasets_manifest) if row.get("dataset_id")}


def _real_fixture_id(label: str, idx: int) -> str:
    return f"hydro_{label}_{idx:06d}"


def _synthetic_clip_rows(synthetic_manifest: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in read_jsonl(synthetic_manifest):
        synthetic_id = str(row.get("synthetic_id", "synthetic"))
        rows.append(
            {
                "clip_id": synthetic_id,
                "dataset_id": "synthetic_generator",
                "source_path": row.get("path", ""),
                "normalized_path": row.get("path", ""),
                "label": row.get("label", "synthetic_submarine_like"),
                "sub_label": row.get("generation_type", "synthetic"),
                "sample_rate_hz": row.get("sample_rate_hz", 16000),
                "duration_sec": row.get("duration_sec", 0.0),
                "group_id": f"synthetic:{synthetic_id}",
                "license": "repo_generated_synthetic",
                "provenance": {
                    "source_url": "scripts/hydrophone/generate_synthetic_waves.py",
                    "downloaded_at": "",
                    "original_filename": Path(str(row.get("path", synthetic_id))).name,
                },
                "synthetic_disclaimer": row.get("disclaimer", ""),
            }
        )
    return rows


def _fixture_row(
    source: dict[str, Any],
    *,
    fixture_id: str,
    dataset_license: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    label = str(source.get("label", "unknown_or_noise"))
    dataset_id = str(source.get("dataset_id", "unknown"))
    license_row = dataset_license.get(dataset_id, {})
    role = GAMEPLAY_ROLE_BY_LABEL.get(label, "unknown_noise")
    notes = "Gameplay fixture metadata; not a claim of real-world acoustic truth."
    if label == "synthetic_submarine_like":
        notes = "Synthetic/simulated contact-like fixture, not a real submarine recording."
    return {
        "fixture_id": fixture_id,
        "source_clip_id": source.get("clip_id", ""),
        "dataset_id": dataset_id,
        "label": label,
        "sub_label": source.get("sub_label", "unknown"),
        "normalized_path": source.get("normalized_path", ""),
        "duration_sec": float(source.get("duration_sec") or 0.0),
        "sample_rate_hz": int(source.get("sample_rate_hz") or 0),
        "group_id": source.get("group_id", ""),
        "license": source.get("license") or license_row.get("license", "unknown_or_documented"),
        "redistribution": license_row.get("redistribution", "allowed" if dataset_id == "synthetic_generator" else "unclear"),
        "commercial_use": license_row.get("commercial_use", "allowed" if dataset_id == "synthetic_generator" else "unclear"),
        "gameplay_role": role,
        "suggested_contact_confidence": CONFIDENCE_BY_LABEL.get(label, 0.05),
        "suggested_bearing_noise_deg": 0.0,
        "suggested_range_noise_m": 0.0,
        "notes": notes,
    }


def export_subsim_fixtures(
    *,
    clips_manifest: Path,
    datasets_manifest: Path,
    output_path: Path,
    report_path: Path,
    synthetic_manifest: Path | None = None,
    include_synthetic: bool = False,
) -> list[dict[str, Any]]:
    dataset_license = _load_dataset_license_rows(datasets_manifest)
    source_rows = [dict(row) for row in read_jsonl(clips_manifest)]
    if not include_synthetic:
        source_rows = [row for row in source_rows if not _is_synthetic(row)]
    elif synthetic_manifest is not None:
        source_rows.extend(_synthetic_clip_rows(synthetic_manifest))

    label_counts: Counter[str] = Counter()
    fixtures: list[dict[str, Any]] = []
    for source in source_rows:
        label = str(source.get("label", "unknown_or_noise"))
        label_counts[label] += 1
        fixtures.append(
            _fixture_row(
                source,
                fixture_id=_real_fixture_id(label, label_counts[label]),
                dataset_license=dataset_license,
            )
        )

    write_jsonl(output_path, fixtures)
    _write_report(report_path, fixtures, include_synthetic=include_synthetic)
    return fixtures


def _write_report(report_path: Path, fixtures: list[dict[str, Any]], *, include_synthetic: bool) -> None:
    role_counts = Counter(str(row.get("gameplay_role", "unknown")) for row in fixtures)
    dataset_counts = Counter(str(row.get("dataset_id", "unknown")) for row in fixtures)
    caveats = sorted(
        {
            f"{row['license']} / redistribution={row['redistribution']} / commercial={row['commercial_use']}"
            for row in fixtures
        }
    )
    lines = [
        "# SubSim Hydrophone Fixture Export Report",
        "",
        f"Generated: {utc_now_iso()}",
        "",
        f"- Fixture rows: {len(fixtures)}",
        f"- Synthetic included: {'yes' if include_synthetic else 'no'}",
        "",
        "## Counts by Gameplay Role",
        "",
    ]
    for role, count in sorted(role_counts.items()):
        lines.append(f"- `{role}`: {count}")
    lines.extend(["", "## Counts by Source Dataset", ""])
    for dataset_id, count in sorted(dataset_counts.items()):
        lines.append(f"- `{dataset_id}`: {count}")
    lines.extend(["", "## License / Commercial Caveats", ""])
    lines.extend(f"- {caveat}" for caveat in caveats)
    lines.extend(
        [
            "",
            "## Recommended SubSim Integration Path",
            "",
            "- Use `subsim_acoustic_contacts.jsonl` as gameplay fixture metadata, not acoustic truth labels.",
            "- Feed heldout-source ReadyPlayer1 cases into the Campaign 003 clutter-binding and primary-track selection loop first.",
            "- Keep audio artifacts ignored; fixtures should reference local normalized paths that can be regenerated.",
        ]
    )
    write_text(report_path, "\n".join(lines))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export SubSim acoustic contact fixtures from hydrophone manifests.")
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--report-root", default=str(DEFAULT_REPORT_ROOT))
    parser.add_argument("--clips-manifest", default=None)
    parser.add_argument("--datasets-manifest", default=None)
    parser.add_argument("--synthetic-manifest", default=None)
    parser.add_argument("--output-path", default=None)
    parser.add_argument("--include-synthetic", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    data_root = Path(args.data_root)
    report_root = Path(args.report_root)
    ensure_hydrophone_layout(data_root, report_root)
    ensure_dir(data_root / "fixtures")
    clips_manifest = Path(args.clips_manifest) if args.clips_manifest else data_root / "manifests" / "clips.jsonl"
    datasets_manifest = Path(args.datasets_manifest) if args.datasets_manifest else data_root / "manifests" / "datasets.jsonl"
    synthetic_manifest = Path(args.synthetic_manifest) if args.synthetic_manifest else data_root / "synthetic" / "manifest.jsonl"
    output_path = Path(args.output_path) if args.output_path else data_root / "fixtures" / "subsim_acoustic_contacts.jsonl"
    fixtures = export_subsim_fixtures(
        clips_manifest=clips_manifest,
        datasets_manifest=datasets_manifest,
        output_path=output_path,
        report_path=report_root / "subsim_fixture_export_report.md",
        synthetic_manifest=synthetic_manifest,
        include_synthetic=args.include_synthetic,
    )
    print(f"subsim acoustic fixture export complete: fixtures={len(fixtures)} output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
