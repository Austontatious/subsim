#!/usr/bin/env python3
"""Run the bounded hydrophone ingestion pipeline stages in order."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hydrophone_common import DEFAULT_DATA_ROOT, DEFAULT_REPORT_ROOT, ensure_hydrophone_layout  # noqa: E402


def _run(cmd: list[str]) -> int:
    print("+ " + " ".join(cmd))
    completed = subprocess.run(cmd, check=False)
    return int(completed.returncode)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the bounded hydrophone corpus pipeline.")
    parser.add_argument("--dry-run", action="store_true", help="Do not fetch audio or generate synthetic WAVs.")
    parser.add_argument("--download", action="store_true", help="Fetch/copy tiny real dataset samples.")
    parser.add_argument("--max-files-per-dataset", type=int, default=5)
    parser.add_argument("--datasets", nargs="*", default=None)
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--window-sec", type=float, default=10.0)
    parser.add_argument("--synthetic-count", type=int, default=50)
    parser.add_argument("--synthetic-duration-sec", type=float, default=10.0)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--split-seed", type=int, default=1337)
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--report-root", default=str(DEFAULT_REPORT_ROOT))
    parser.add_argument("--skip-synthetic", action="store_true")
    parser.add_argument("--build-fixed-splits", action="store_true")
    parser.add_argument("--export-fixtures", action="store_true")
    parser.add_argument("--include-synthetic-fixtures", action="store_true")
    classifier_mode = parser.add_mutually_exclusive_group()
    classifier_mode.add_argument("--real-only", action="store_true", help="Exclude synthetic clips from classifier training. Default.")
    classifier_mode.add_argument("--include-synthetic", action="store_true", help="Include synthetic rows in classifier training if feature table contains them.")
    parser.add_argument(
        "--generate-in-dry-run",
        action="store_true",
        help="Allow synthetic generation even when --dry-run is set.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    data_root = Path(args.data_root)
    report_root = Path(args.report_root)
    ensure_hydrophone_layout(data_root, report_root)

    dry_run = bool(args.dry_run or not args.download)
    commands: list[list[str]] = []

    fetch_cmd = [
        sys.executable,
        str(SCRIPT_DIR / "fetch_hydrophone_samples.py"),
        "--max-files-per-dataset",
        str(args.max_files_per_dataset),
        "--data-root",
        str(data_root),
        "--report-root",
        str(report_root),
    ]
    if dry_run:
        fetch_cmd.append("--dry-run")
    else:
        fetch_cmd.append("--download")
    if args.datasets:
        fetch_cmd.append("--datasets")
        fetch_cmd.extend(args.datasets)
    commands.append(fetch_cmd)

    commands.append(
        [
            sys.executable,
            str(SCRIPT_DIR / "normalize_hydrophone_audio.py"),
            "--window-sec",
            str(args.window_sec),
            "--sample-rate",
            str(args.sample_rate),
            "--data-root",
            str(data_root),
            "--report-root",
            str(report_root),
        ]
    )
    commands.append(
        [
            sys.executable,
            str(SCRIPT_DIR / "extract_hydrophone_features.py"),
            "--data-root",
            str(data_root),
            "--report-root",
            str(report_root),
        ]
    )
    if args.build_fixed_splits:
        commands.append(
            [
                sys.executable,
                str(SCRIPT_DIR / "build_fixed_eval_splits.py"),
                "--seed",
                str(args.split_seed),
                "--data-root",
                str(data_root),
                "--report-root",
                str(report_root),
            ]
        )
    classifier_cmd = [
        sys.executable,
        str(SCRIPT_DIR / "train_hydrophone_classifier.py"),
        "--data-root",
        str(data_root),
        "--report-root",
        str(report_root),
        "--random-state",
        str(args.seed),
    ]
    if args.build_fixed_splits:
        classifier_cmd.extend(["--split-dir", str(data_root / "manifests" / "splits")])
    classifier_cmd.append("--include-synthetic" if args.include_synthetic else "--real-only")
    commands.append(classifier_cmd)
    if not args.skip_synthetic and (not dry_run or args.generate_in_dry_run):
        commands.append(
            [
                sys.executable,
                str(SCRIPT_DIR / "generate_synthetic_waves.py"),
                "--count",
                str(args.synthetic_count),
                "--sample-rate",
                str(args.sample_rate),
                "--duration-sec",
                str(args.synthetic_duration_sec),
                "--seed",
                str(args.seed),
                "--data-root",
                str(data_root),
                "--report-root",
                str(report_root),
            ]
        )
    if args.export_fixtures:
        fixture_flag = ["--include-synthetic"] if args.include_synthetic_fixtures else []
        commands.append(
            [
                sys.executable,
                str(SCRIPT_DIR / "export_subsim_acoustic_fixtures.py"),
                "--data-root",
                str(data_root),
                "--report-root",
                str(report_root),
                *fixture_flag,
            ]
        )
        commands.append(
            [
                sys.executable,
                str(SCRIPT_DIR / "export_readyplayer1_acoustic_eval_cases.py"),
                "--data-root",
                str(data_root),
                "--report-root",
                str(report_root),
                "--split-dir",
                str(data_root / "manifests" / "splits"),
                *fixture_flag,
            ]
        )

    for cmd in commands:
        rc = _run(cmd)
        if rc != 0:
            print(f"hydrophone pipeline failed: rc={rc} command={' '.join(cmd)}", file=sys.stderr)
            return rc

    print(f"hydrophone pipeline complete: mode={'dry-run' if dry_run else 'download'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
