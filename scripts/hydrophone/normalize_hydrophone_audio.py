#!/usr/bin/env python3
"""Normalize raw hydrophone samples into mono fixed-rate WAV clips."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hydrophone_common import (  # noqa: E402
    ALLOWED_LABELS,
    DEFAULT_DATA_ROOT,
    DEFAULT_REPORT_ROOT,
    SUPPORTED_AUDIO_SUFFIXES,
    conservative_normalize,
    ensure_hydrophone_layout,
    infer_dataset_id_from_path,
    read_audio,
    read_jsonl,
    repo_relative,
    resolve_repo_path,
    resample_audio,
    segment_audio,
    write_jsonl,
    write_wav,
)


SEGMENT_SUFFIX_RE = re.compile(r"_seg\d{3}$")


def _backfill_group_id(row: dict[str, Any]) -> str:
    if row.get("group_id"):
        return str(row["group_id"])
    provenance = row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
    original = provenance.get("original_filename") or row.get("source_path") or row.get("clip_id") or "unknown"
    return f"{row.get('dataset_id', 'unknown')}:{original}"


def _records_from_raw_scan(raw_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, path in enumerate(sorted(raw_root.rglob("*")), start=1):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_AUDIO_SUFFIXES:
            continue
        dataset_id = infer_dataset_id_from_path(path, raw_root)
        clip_id = f"{dataset_id}_{idx:06d}"
        rows.append(
            {
                "clip_id": clip_id,
                "dataset_id": dataset_id,
                "source_path": repo_relative(path),
                "normalized_path": f"data/hydrophone/normalized/{clip_id}.wav",
                "label": "unknown_or_noise",
                "sub_label": "unknown",
                "sample_rate_hz": 0,
                "duration_sec": 0.0,
                "group_id": f"{dataset_id}:{path.name}",
                "license": "unknown_or_documented",
                "provenance": {
                    "source_url": "local_raw_scan",
                    "downloaded_at": "",
                    "original_filename": path.name,
                },
            }
        )
    return rows


def normalize_audio_manifest(
    *,
    clips_manifest: Path,
    raw_root: Path,
    normalized_root: Path,
    sample_rate: int,
    window_sec: float,
    max_segments_per_file: int,
) -> list[dict[str, Any]]:
    records = read_jsonl(clips_manifest)
    raw_records = [row for row in records if row.get("source_path")]
    if not raw_records:
        raw_records = _records_from_raw_scan(raw_root)
    else:
        deduped: dict[tuple[str, str], dict[str, Any]] = {}
        for row in raw_records:
            key = (str(row.get("dataset_id", "")), str(row.get("source_path", "")))
            if key not in deduped:
                collapsed = dict(row)
                collapsed["clip_id"] = SEGMENT_SUFFIX_RE.sub("", str(collapsed.get("clip_id") or ""))
                deduped[key] = collapsed
        raw_records = list(deduped.values())

    normalized_rows: list[dict[str, Any]] = []
    for row in raw_records:
        source_path = resolve_repo_path(str(row["source_path"]))
        if not source_path.exists():
            continue
        if source_path.suffix.lower() not in SUPPORTED_AUDIO_SUFFIXES:
            continue
        label = str(row.get("label") or "unknown_or_noise")
        if label not in ALLOWED_LABELS:
            label = "unknown_or_noise"

        samples, source_rate = read_audio(source_path)
        samples = resample_audio(samples, source_rate, sample_rate)
        samples = conservative_normalize(samples)
        segments = segment_audio(
            samples,
            sample_rate,
            window_sec=window_sec,
            max_segments=max_segments_per_file,
            pad_short=True,
        )
        base_clip_id = SEGMENT_SUFFIX_RE.sub("", str(row.get("clip_id") or source_path.stem))
        for seg_idx, segment in enumerate(segments):
            clip_id = base_clip_id if len(segments) == 1 else f"{base_clip_id}_seg{seg_idx:03d}"
            normalized_path = normalized_root / f"{clip_id}.wav"
            write_wav(normalized_path, segment, sample_rate)
            out = dict(row)
            out.update(
                {
                    "clip_id": clip_id,
                    "normalized_path": repo_relative(normalized_path),
                    "label": label,
                    "sample_rate_hz": int(sample_rate),
                    "duration_sec": round(len(segment) / float(sample_rate), 6),
                    "group_id": _backfill_group_id(row),
                }
            )
            provenance = dict(out.get("provenance") or {})
            provenance.setdefault("original_filename", source_path.name)
            out["provenance"] = provenance
            normalized_rows.append(out)

    write_jsonl(clips_manifest, normalized_rows)
    return normalized_rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Normalize hydrophone audio to mono WAV clips.")
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--report-root", default=str(DEFAULT_REPORT_ROOT))
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--window-sec", type=float, default=10.0)
    parser.add_argument("--max-segments-per-file", type=int, default=3)
    parser.add_argument("--clips-manifest", default=None)
    parser.add_argument("--raw-root", default=None)
    parser.add_argument("--normalized-root", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.sample_rate <= 0:
        parser.error("--sample-rate must be positive")
    if args.window_sec <= 0:
        parser.error("--window-sec must be positive")
    if args.max_segments_per_file <= 0:
        parser.error("--max-segments-per-file must be positive")

    data_root = Path(args.data_root)
    report_root = Path(args.report_root)
    ensure_hydrophone_layout(data_root, report_root)
    clips_manifest = Path(args.clips_manifest) if args.clips_manifest else data_root / "manifests" / "clips.jsonl"
    raw_root = Path(args.raw_root) if args.raw_root else data_root / "raw_samples"
    normalized_root = Path(args.normalized_root) if args.normalized_root else data_root / "normalized"

    rows = normalize_audio_manifest(
        clips_manifest=clips_manifest,
        raw_root=raw_root,
        normalized_root=normalized_root,
        sample_rate=args.sample_rate,
        window_sec=args.window_sec,
        max_segments_per_file=args.max_segments_per_file,
    )
    print(f"hydrophone normalize complete: normalized_clips={len(rows)} sample_rate={args.sample_rate}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
