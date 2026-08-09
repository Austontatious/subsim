#!/usr/bin/env python3
"""Export ReadyPlayer1-style acoustic eval cases from hydrophone manifests."""

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
from export_subsim_acoustic_fixtures import GAMEPLAY_ROLE_BY_LABEL, _load_dataset_license_rows, _synthetic_clip_rows  # noqa: E402


CONTACT_LABELS = {"surface_vessel", "synthetic_submarine_like"}


def _is_synthetic(row: dict[str, Any]) -> bool:
    return str(row.get("label")) == "synthetic_submarine_like" or str(row.get("dataset_id", "")).startswith("synthetic")


def _load_split_assignments(split_dir: Path) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for split in ("train", "validation", "heldout_source_eval"):
        path = split_dir / f"{split}.jsonl"
        if not path.exists():
            continue
        for row in read_jsonl(path):
            clip_id = str(row.get("clip_id", ""))
            if clip_id:
                assignments[clip_id] = split
    return assignments


def _expected_for_label(label: str) -> dict[str, Any]:
    should_contact = label in CONTACT_LABELS
    return {
        "broad_class": label,
        "gameplay_role": GAMEPLAY_ROLE_BY_LABEL.get(label, "unknown_noise"),
        "should_track": should_contact,
        "should_confirm": should_contact,
        "should_reject_as_clutter": not should_contact,
    }


def _case_row(
    source: dict[str, Any],
    *,
    case_id: str,
    split: str,
    dataset_license: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    label = str(source.get("label", "unknown_or_noise"))
    dataset_id = str(source.get("dataset_id", ""))
    license_row = dataset_license.get(dataset_id, {})
    return {
        "case_id": case_id,
        "source_clip_id": source.get("clip_id", ""),
        "split": split,
        "input": {
            "normalized_path": source.get("normalized_path", ""),
            "duration_sec": float(source.get("duration_sec") or 0.0),
            "sample_rate_hz": int(source.get("sample_rate_hz") or 0),
        },
        "expected": _expected_for_label(label),
        "metadata": {
            "dataset_id": dataset_id,
            "group_id": source.get("group_id", ""),
            "license": source.get("license") or license_row.get("license", "unknown_or_documented"),
            "commercial_use": license_row.get("commercial_use", "allowed" if dataset_id == "synthetic_generator" else "unclear"),
            "notes": "Gameplay/eval behavior fixture; not a claim of real acoustic truth.",
        },
    }


def export_readyplayer1_cases(
    *,
    clips_manifest: Path,
    datasets_manifest: Path,
    split_dir: Path,
    output_path: Path,
    report_path: Path,
    synthetic_manifest: Path | None = None,
    include_synthetic: bool = False,
) -> list[dict[str, Any]]:
    dataset_license = _load_dataset_license_rows(datasets_manifest)
    split_assignments = _load_split_assignments(split_dir)
    source_rows = [dict(row) for row in read_jsonl(clips_manifest)]
    if not include_synthetic:
        source_rows = [row for row in source_rows if not _is_synthetic(row)]
    elif synthetic_manifest is not None:
        source_rows.extend(_synthetic_clip_rows(synthetic_manifest))

    cases: list[dict[str, Any]] = []
    for idx, row in enumerate(source_rows, start=1):
        split = "synthetic" if _is_synthetic(row) else split_assignments.get(str(row.get("clip_id", "")), "heldout_source_eval")
        cases.append(_case_row(row, case_id=f"rp1_acoustic_{idx:06d}", split=split, dataset_license=dataset_license))

    write_jsonl(output_path, cases)
    _write_report(report_path, cases, include_synthetic=include_synthetic)
    return cases


def _write_report(report_path: Path, cases: list[dict[str, Any]], *, include_synthetic: bool) -> None:
    split_counts = Counter(str(row.get("split", "unknown")) for row in cases)
    role_counts = Counter(str(row.get("expected", {}).get("gameplay_role", "unknown")) for row in cases)
    dataset_counts = Counter(str(row.get("metadata", {}).get("dataset_id", "unknown")) for row in cases)
    lines = [
        "# ReadyPlayer1 Acoustic Eval Case Export",
        "",
        f"Generated: {utc_now_iso()}",
        "",
        f"- Eval cases: {len(cases)}",
        f"- Synthetic included: {'yes' if include_synthetic else 'no'}",
        "",
        "## Counts by Split",
        "",
    ]
    for split, count in sorted(split_counts.items()):
        lines.append(f"- `{split}`: {count}")
    lines.extend(["", "## Counts by Gameplay Role", ""])
    for role, count in sorted(role_counts.items()):
        lines.append(f"- `{role}`: {count}")
    lines.extend(["", "## Counts by Source Dataset", ""])
    for dataset_id, count in sorted(dataset_counts.items()):
        lines.append(f"- `{dataset_id}`: {count}")
    write_text(report_path, "\n".join(lines))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export ReadyPlayer1 acoustic eval cases from hydrophone manifests.")
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--report-root", default=str(DEFAULT_REPORT_ROOT))
    parser.add_argument("--clips-manifest", default=None)
    parser.add_argument("--datasets-manifest", default=None)
    parser.add_argument("--split-dir", default=None)
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
    split_dir = Path(args.split_dir) if args.split_dir else data_root / "manifests" / "splits"
    synthetic_manifest = Path(args.synthetic_manifest) if args.synthetic_manifest else data_root / "synthetic" / "manifest.jsonl"
    output_path = Path(args.output_path) if args.output_path else data_root / "fixtures" / "readyplayer1_acoustic_eval_cases.jsonl"
    cases = export_readyplayer1_cases(
        clips_manifest=clips_manifest,
        datasets_manifest=datasets_manifest,
        split_dir=split_dir,
        output_path=output_path,
        report_path=report_root / "readyplayer1_acoustic_eval_case_report.md",
        synthetic_manifest=synthetic_manifest,
        include_synthetic=args.include_synthetic,
    )
    print(f"readyplayer1 acoustic eval export complete: cases={len(cases)} output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
