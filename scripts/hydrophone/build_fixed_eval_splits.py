#!/usr/bin/env python3
"""Build deterministic group-safe hydrophone train/validation/heldout splits."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hydrophone_common import (  # noqa: E402
    ALLOWED_LABELS,
    DEFAULT_DATA_ROOT,
    DEFAULT_REPORT_ROOT,
    ensure_dir,
    ensure_hydrophone_layout,
    read_jsonl,
    write_jsonl,
    write_text,
    utc_now_iso,
)


SPLIT_NAMES = ("train", "validation", "heldout_source_eval")


def _is_synthetic(row: dict[str, Any]) -> bool:
    return str(row.get("label")) == "synthetic_submarine_like" or str(row.get("dataset_id", "")).startswith("synthetic")


def _backfill_group_id(row: dict[str, Any]) -> str:
    if row.get("group_id"):
        return str(row["group_id"])
    provenance = row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
    original = provenance.get("original_filename") or row.get("source_path") or row.get("clip_id") or "unknown"
    return f"{row.get('dataset_id', 'unknown')}:{original}"


def _stable_group_order(groups: list[str], *, label: str, seed: int) -> list[str]:
    return sorted(
        groups,
        key=lambda group: hashlib.sha1(f"{seed}|{label}|{group}".encode("utf-8")).hexdigest(),
    )


def _target_counts(n_groups: int, *, train_frac: float, validation_frac: float, heldout_frac: float) -> dict[str, int]:
    if n_groups <= 0:
        return {name: 0 for name in SPLIT_NAMES}
    if n_groups == 1:
        return {"train": 1, "validation": 0, "heldout_source_eval": 0}
    if n_groups == 2:
        return {"train": 1, "validation": 0, "heldout_source_eval": 1}

    validation = max(1, int(round(n_groups * validation_frac)))
    heldout = max(1, int(round(n_groups * heldout_frac)))
    if validation + heldout >= n_groups:
        overflow = validation + heldout - (n_groups - 1)
        while overflow > 0 and validation >= heldout and validation > 1:
            validation -= 1
            overflow -= 1
        while overflow > 0 and heldout > 1:
            heldout -= 1
            overflow -= 1
    train = n_groups - validation - heldout
    if train <= 0:
        train = 1
        if validation >= heldout and validation > 1:
            validation -= 1
        elif heldout > 1:
            heldout -= 1
    return {"train": train, "validation": validation, "heldout_source_eval": heldout}


def _counts_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key, "unknown")) for row in rows).items()))


def _counts_by_split(rows_by_split: dict[str, list[dict[str, Any]]], key: str) -> dict[str, dict[str, int]]:
    values: set[str] = set()
    for rows in rows_by_split.values():
        values.update(str(row.get(key, "unknown")) for row in rows)
    out: dict[str, dict[str, int]] = {}
    for value in sorted(values):
        out[value] = {split: sum(1 for row in rows_by_split[split] if str(row.get(key, "unknown")) == value) for split in SPLIT_NAMES}
    return out


def _group_counts_by_split(rows_by_split: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    return {
        split: len({str(row.get("group_id", "")) for row in rows if row.get("group_id")})
        for split, rows in rows_by_split.items()
    }


def _load_split_input(clips_manifest: Path, *, include_synthetic: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in read_jsonl(clips_manifest):
        if str(row.get("label")) not in ALLOWED_LABELS:
            continue
        if not include_synthetic and _is_synthetic(row):
            continue
        out = dict(row)
        out["group_id"] = _backfill_group_id(out)
        rows.append(out)
    return rows


def build_fixed_splits(
    *,
    clips_manifest: Path,
    output_dir: Path,
    report_path: Path,
    seed: int = 1337,
    train_frac: float = 0.60,
    validation_frac: float = 0.20,
    heldout_frac: float = 0.20,
    include_synthetic: bool = False,
) -> dict[str, Any]:
    ensure_dir(output_dir)
    rows = _load_split_input(clips_manifest, include_synthetic=include_synthetic)

    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_group[str(row["group_id"])].append(row)

    label_groups: dict[str, list[str]] = defaultdict(list)
    group_label: dict[str, str] = {}
    for group_id, group_rows in by_group.items():
        labels = Counter(str(row["label"]) for row in group_rows)
        label = sorted(labels.items(), key=lambda item: (-item[1], item[0]))[0][0]
        label_groups[label].append(group_id)
        group_label[group_id] = label

    group_split: dict[str, str] = {}
    degradation_notes: list[str] = []
    for label, groups in sorted(label_groups.items()):
        ordered = _stable_group_order(groups, label=label, seed=seed)
        targets = _target_counts(
            len(ordered),
            train_frac=train_frac,
            validation_frac=validation_frac,
            heldout_frac=heldout_frac,
        )
        if targets["validation"] == 0 or targets["heldout_source_eval"] == 0:
            degradation_notes.append(
                f"`{label}` has only {len(ordered)} groups; one or more eval splits are empty for that class."
            )
        cursor = 0
        for split in SPLIT_NAMES:
            for group_id in ordered[cursor : cursor + targets[split]]:
                group_split[group_id] = split
            cursor += targets[split]

    rows_by_split = {split: [] for split in SPLIT_NAMES}
    for row in rows:
        split = group_split.get(str(row["group_id"]), "train")
        out = dict(row)
        out["split"] = split
        rows_by_split[split].append(out)

    for split in SPLIT_NAMES:
        rows_by_split[split].sort(key=lambda row: (str(row.get("label")), str(row.get("dataset_id")), str(row.get("clip_id"))))
        write_jsonl(output_dir / f"{split}.jsonl", rows_by_split[split])

    group_sets = {split: {str(row["group_id"]) for row in rows_by_split[split]} for split in SPLIT_NAMES}
    leakage_pairs = []
    for idx, left in enumerate(SPLIT_NAMES):
        for right in SPLIT_NAMES[idx + 1 :]:
            overlap = sorted(group_sets[left] & group_sets[right])
            if overlap:
                leakage_pairs.append({"left": left, "right": right, "groups": overlap})

    summary = {
        "generated": utc_now_iso(),
        "seed": seed,
        "include_synthetic": include_synthetic,
        "input_manifest": str(clips_manifest),
        "split_fracs": {
            "train": train_frac,
            "validation": validation_frac,
            "heldout_source_eval": heldout_frac,
        },
        "total_clips": len(rows),
        "total_groups": len(by_group),
        "split_clip_counts": {split: len(rows_by_split[split]) for split in SPLIT_NAMES},
        "split_group_counts": _group_counts_by_split(rows_by_split),
        "class_counts_by_split": _counts_by_split(rows_by_split, "label"),
        "dataset_counts_by_split": _counts_by_split(rows_by_split, "dataset_id"),
        "group_leakage_prevented": not leakage_pairs,
        "group_leakage": leakage_pairs,
        "degradation_notes": degradation_notes,
    }
    (output_dir / "split_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(report_path, summary)
    return summary


def _write_report(report_path: Path, summary: dict[str, Any]) -> None:
    class_counts = summary["class_counts_by_split"]
    dataset_counts = summary["dataset_counts_by_split"]
    lines = [
        "# Hydrophone Fixed Eval Manifest Report",
        "",
        f"Generated: {summary['generated']}",
        "",
        "## Summary",
        "",
        f"- Total clips: {summary['total_clips']}",
        f"- Total groups: {summary['total_groups']}",
        f"- Synthetic included: {'yes' if summary['include_synthetic'] else 'no'}",
        f"- Group leakage prevented: {'yes' if summary['group_leakage_prevented'] else 'no'}",
        "- Reliability caveat: this is a stable smoke/eval asset, not proof of model quality.",
        "",
        "## Split Counts",
        "",
        "| Split | Clips | Groups |",
        "|---|---:|---:|",
    ]
    for split in SPLIT_NAMES:
        lines.append(
            f"| {split} | {summary['split_clip_counts'].get(split, 0)} | {summary['split_group_counts'].get(split, 0)} |"
        )

    lines.extend(["", "## Split Counts by Class", "", "| Class | Train | Validation | Heldout |", "|---|---:|---:|---:|"])
    for label, counts in sorted(class_counts.items()):
        lines.append(
            f"| {label} | {counts.get('train', 0)} | {counts.get('validation', 0)} | {counts.get('heldout_source_eval', 0)} |"
        )

    lines.extend(["", "## Split Counts by Dataset", "", "| Dataset | Train | Validation | Heldout |", "|---|---:|---:|---:|"])
    for dataset_id, counts in sorted(dataset_counts.items()):
        lines.append(
            f"| {dataset_id} | {counts.get('train', 0)} | {counts.get('validation', 0)} | {counts.get('heldout_source_eval', 0)} |"
        )

    lines.extend(["", "## Imbalance / Degradation Notes", ""])
    if summary["degradation_notes"]:
        lines.extend(f"- {note}" for note in summary["degradation_notes"])
    else:
        lines.append("- No class had to drop validation or heldout groups.")
    write_text(report_path, "\n".join(lines))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build deterministic group-safe hydrophone eval splits.")
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--report-root", default=str(DEFAULT_REPORT_ROOT))
    parser.add_argument("--clips-manifest", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--train-frac", type=float, default=0.60)
    parser.add_argument("--validation-frac", type=float, default=0.20)
    parser.add_argument("--heldout-frac", type=float, default=0.20)
    parser.add_argument("--include-synthetic", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    total = args.train_frac + args.validation_frac + args.heldout_frac
    if total <= 0:
        raise SystemExit("split fractions must sum to a positive value")
    data_root = Path(args.data_root)
    report_root = Path(args.report_root)
    ensure_hydrophone_layout(data_root, report_root)
    clips_manifest = Path(args.clips_manifest) if args.clips_manifest else data_root / "manifests" / "clips.jsonl"
    output_dir = Path(args.output_dir) if args.output_dir else data_root / "manifests" / "splits"
    summary = build_fixed_splits(
        clips_manifest=clips_manifest,
        output_dir=output_dir,
        report_path=report_root / "fixed_eval_manifest_report.md",
        seed=args.seed,
        train_frac=args.train_frac / total,
        validation_frac=args.validation_frac / total,
        heldout_frac=args.heldout_frac / total,
        include_synthetic=args.include_synthetic,
    )
    print(
        "hydrophone fixed splits complete: "
        f"clips={summary['total_clips']} groups={summary['total_groups']} "
        f"train={summary['split_clip_counts'].get('train', 0)} "
        f"validation={summary['split_clip_counts'].get('validation', 0)} "
        f"heldout={summary['split_clip_counts'].get('heldout_source_eval', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
