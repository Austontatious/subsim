#!/usr/bin/env python3
"""Train a deliberately simple baseline classifier for sampled hydrophone clips."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
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
    utc_now_iso,
    write_text,
)


NON_FEATURE_COLUMNS = {
    "clip_id",
    "dataset_id",
    "label",
    "group_id",
    "source_path",
    "normalized_path",
}
SPLIT_NAMES = ("train", "validation", "heldout_source_eval")


def _load_features(path: Path):
    try:
        import pandas as pd
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"pandas unavailable: {type(exc).__name__}: {exc}") from exc

    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _default_features_path(data_root: Path) -> Path:
    parquet = data_root / "features" / "features.parquet"
    if parquet.exists():
        return parquet
    return data_root / "features" / "features.csv"


def _is_synthetic_df(df):
    synthetic_mask = df["label"].astype(str).eq("synthetic_submarine_like")
    if "dataset_id" in df.columns:
        synthetic_mask = synthetic_mask | df["dataset_id"].astype(str).str.startswith("synthetic")
    return synthetic_mask


def filter_real_rows(df, *, include_synthetic: bool = False):
    if include_synthetic:
        return df.copy()
    return df[~_is_synthetic_df(df)].copy()


def _choose_group_column(df) -> str | None:
    if "group_id" in df.columns and df["group_id"].fillna("").astype(str).str.len().gt(0).any():
        return "group_id"
    if "source_path" in df.columns and df["source_path"].fillna("").astype(str).str.len().gt(0).any():
        return "source_path"
    return None


def _numeric_feature_columns(df) -> list[str]:
    return [
        col
        for col in df.columns
        if col not in NON_FEATURE_COLUMNS and str(df[col].dtype).lower() not in {"object", "string"}
    ]


def _class_counts(df) -> dict[str, int]:
    if df.empty or "label" not in df.columns:
        return {}
    return {str(k): int(v) for k, v in sorted(df["label"].astype(str).value_counts().to_dict().items())}


def _group_counts(df, group_col: str | None) -> dict[str, int]:
    if df.empty or not group_col or group_col not in df.columns:
        return {str(label): 0 for label in sorted(df.get("label", []).astype(str).unique())} if "label" in df.columns else {}
    out: dict[str, int] = {}
    for label, sub in df.groupby("label"):
        out[str(label)] = int(sub[group_col].astype(str).nunique())
    return dict(sorted(out.items()))


def _stable_group_split(df, *, group_col: str, label_col: str = "label", test_fraction: float = 0.35):
    groups_by_label: dict[str, list[str]] = {}
    for group, sub in df.groupby(group_col):
        group_value = str(group)
        if not group_value:
            continue
        label = str(sub[label_col].astype(str).value_counts().idxmax())
        groups_by_label.setdefault(label, []).append(group_value)

    test_groups: set[str] = set()
    for label, groups in groups_by_label.items():
        del label
        unique_groups = sorted(set(groups), key=lambda value: hashlib.sha1(value.encode("utf-8")).hexdigest())
        if len(unique_groups) <= 1:
            continue
        test_count = max(1, int(round(len(unique_groups) * test_fraction)))
        test_count = min(test_count, len(unique_groups) - 1)
        test_groups.update(unique_groups[:test_count])

    if not test_groups:
        return None
    mask = df[group_col].astype(str).isin(test_groups).to_numpy()
    train_idx = [idx for idx, is_test in enumerate(mask) if not is_test]
    test_idx = [idx for idx, is_test in enumerate(mask) if is_test]
    if not train_idx or not test_idx:
        return None
    return train_idx, test_idx


def _write_confusion_csv(path: Path, labels: list[str], matrix) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["actual\\predicted"] + labels)
        for label, values in zip(labels, matrix):
            writer.writerow([label] + [int(v) for v in values])


def _write_skip_report(
    report_path: Path,
    reason: str,
    details: list[str] | None = None,
    *,
    total_clips: int = 0,
    classes: dict[str, int] | None = None,
    groups: int = 0,
    split_strategy: str = "not_run",
    include_synthetic: bool = False,
) -> None:
    classes = classes or {}
    classes_below_10 = sorted(label for label, count in classes.items() if count < 10)
    lines = [
        "# Hydrophone Classifier Baseline Report",
        "",
        f"Generated: {utc_now_iso()}",
        "",
        "## Status",
        "",
        f"Skipped: {reason}",
    ]
    if details:
        lines.extend(["", "## Details", ""])
        lines.extend(f"- {detail}" for detail in details)
    lines.extend(
        [
            "",
            "## Eval Reliability",
            "",
            f"- Total clips: {total_clips}",
            f"- Classes: {', '.join(f'{k}={v}' for k, v in sorted(classes.items())) or 'none'}",
            f"- Groups: {groups}",
            f"- Split strategy: {split_strategy}",
            f"- Classes below 10 clips: {', '.join(classes_below_10) or 'none'}",
            "- Known leakage risks: classifier did not run",
            "- Should metrics be trusted? no",
            f"- Synthetic included: {'yes' if include_synthetic else 'no'}",
        ]
    )
    write_text(report_path, "\n".join(lines))


def _load_model_tools():
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import classification_report, confusion_matrix
        from sklearn.model_selection import train_test_split
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"scikit-learn unavailable: {type(exc).__name__}: {exc}") from exc
    return RandomForestClassifier, classification_report, confusion_matrix, train_test_split


def _evaluate_model(model, df, numeric_cols: list[str], labels: list[str], *, classification_report, confusion_matrix):
    if df.empty:
        return {"rows": 0, "report_text": "No rows.", "matrix": None, "class_counts": {}}
    X = df[numeric_cols].fillna(0.0).to_numpy(dtype=float)
    y = df["label"].astype(str).to_numpy()
    predicted = model.predict(X)
    return {
        "rows": int(len(df)),
        "report_text": classification_report(y, predicted, labels=labels, zero_division=0),
        "matrix": confusion_matrix(y, predicted, labels=labels),
        "class_counts": _class_counts(df),
    }


def _read_split_rows(split_dir: Path, *, include_synthetic: bool) -> dict[str, list[dict[str, Any]]]:
    rows_by_split: dict[str, list[dict[str, Any]]] = {}
    for split in SPLIT_NAMES:
        rows = read_jsonl(split_dir / f"{split}.jsonl")
        if not include_synthetic:
            rows = [
                row
                for row in rows
                if str(row.get("label")) != "synthetic_submarine_like"
                and not str(row.get("dataset_id", "")).startswith("synthetic")
            ]
        rows_by_split[split] = rows
    return rows_by_split


def _select_df_for_split(df, split_rows: list[dict[str, Any]]):
    clip_ids = [str(row.get("clip_id", "")) for row in split_rows if row.get("clip_id")]
    return df[df["clip_id"].astype(str).isin(set(clip_ids))].copy(), clip_ids


def _train_fixed_split_classifier(
    *,
    df,
    features_path: Path,
    split_dir: Path,
    report_root: Path,
    random_state: int,
    include_synthetic: bool,
) -> dict[str, Any]:
    RandomForestClassifier, classification_report, confusion_matrix, _ = _load_model_tools()
    report_path = report_root / "classifier_baseline_report.md"
    split_metadata_path = report_root / "classifier_split_metadata.json"
    rows_by_split = _read_split_rows(split_dir, include_synthetic=include_synthetic)
    df = filter_real_rows(df, include_synthetic=include_synthetic)
    df = df[df["label"].notna() & (df["label"].astype(str) != "")]

    train_df, train_ids = _select_df_for_split(df, rows_by_split["train"])
    validation_df, validation_ids = _select_df_for_split(df, rows_by_split["validation"])
    heldout_df, heldout_ids = _select_df_for_split(df, rows_by_split["heldout_source_eval"])
    numeric_cols = _numeric_feature_columns(df)
    group_col = _choose_group_column(df)

    if train_df.empty or len(_class_counts(train_df)) < 2:
        _write_skip_report(
            report_path,
            "fixed split train set has fewer than 2 classes",
            total_clips=len(df),
            classes=_class_counts(df),
            groups=int(df[group_col].astype(str).nunique()) if group_col else 0,
            split_strategy="fixed_split",
            include_synthetic=include_synthetic,
        )
        return {"status": "skipped", "reason": "fixed_train_too_small"}
    if not numeric_cols:
        _write_skip_report(report_path, "no numeric feature columns found", include_synthetic=include_synthetic)
        return {"status": "skipped", "reason": "no_numeric_features"}

    X_train = train_df[numeric_cols].fillna(0.0).to_numpy(dtype=float)
    y_train = train_df["label"].astype(str).to_numpy()
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=8,
        random_state=random_state,
        class_weight="balanced",
    )
    model.fit(X_train, y_train)

    labels = sorted(_class_counts(df))
    validation_eval = _evaluate_model(
        model,
        validation_df,
        numeric_cols,
        labels,
        classification_report=classification_report,
        confusion_matrix=confusion_matrix,
    )
    heldout_eval = _evaluate_model(
        model,
        heldout_df,
        numeric_cols,
        labels,
        classification_report=classification_report,
        confusion_matrix=confusion_matrix,
    )
    if validation_eval["matrix"] is not None:
        _write_confusion_csv(report_root / "classifier_confusion_matrix_validation.csv", labels, validation_eval["matrix"])
    if heldout_eval["matrix"] is not None:
        _write_confusion_csv(report_root / "classifier_confusion_matrix_heldout_source_eval.csv", labels, heldout_eval["matrix"])

    split_groups = {
        split: {str(row.get("group_id", "")) for row in rows if row.get("group_id")}
        for split, rows in rows_by_split.items()
    }
    leakage: list[str] = []
    for idx, left in enumerate(SPLIT_NAMES):
        for right in SPLIT_NAMES[idx + 1 :]:
            overlap = sorted(split_groups[left] & split_groups[right])
            if overlap:
                leakage.append(f"{left}/{right}: {len(overlap)} overlapping groups")

    class_counts = _class_counts(df)
    group_counts = _group_counts(df, group_col)
    classes_below_10 = sorted(label for label, count in class_counts.items() if count < 10)
    reliability_risks = []
    if leakage:
        reliability_risks.extend(leakage)
    if classes_below_10:
        reliability_risks.append("some classes have fewer than 10 clips")
    if len(df) < 100:
        reliability_risks.append("corpus is still small")
    trust = "limited" if not leakage else "no"

    missing_by_split = {
        "train": sorted(set(train_ids) - set(train_df["clip_id"].astype(str))),
        "validation": sorted(set(validation_ids) - set(validation_df["clip_id"].astype(str))),
        "heldout_source_eval": sorted(set(heldout_ids) - set(heldout_df["clip_id"].astype(str))),
    }
    metadata = {
        "generated": utc_now_iso(),
        "features_path": str(features_path),
        "split_dir": str(split_dir),
        "include_synthetic": bool(include_synthetic),
        "split_strategy": "fixed_split_manifest",
        "group_column": group_col,
        "class_counts": class_counts,
        "group_counts": group_counts,
        "train_rows": int(len(train_df)),
        "validation_rows": int(len(validation_df)),
        "heldout_source_eval_rows": int(len(heldout_df)),
        "missing_feature_clip_ids": missing_by_split,
        "known_leakage_risks": reliability_risks,
        "should_metrics_be_trusted": trust,
    }
    split_metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Hydrophone Classifier Baseline Report",
        "",
        f"Generated: {utc_now_iso()}",
        "",
        "## Status",
        "",
        "Ran RandomForestClassifier baseline using fixed split manifests.",
        "",
        "## Fixed Split Evaluation",
        "",
        "### Train",
        "",
        f"- Rows: {len(train_df)}",
        f"- Classes: {', '.join(f'{k}={v}' for k, v in sorted(_class_counts(train_df).items()))}",
        f"- Groups: {train_df[group_col].astype(str).nunique() if group_col else 0}",
        "",
        "### Validation",
        "",
        f"- Rows: {len(validation_df)}",
        f"- Classes: {', '.join(f'{k}={v}' for k, v in sorted(_class_counts(validation_df).items())) or 'none'}",
        f"- Groups: {validation_df[group_col].astype(str).nunique() if group_col and not validation_df.empty else 0}",
        "",
        "```text",
        validation_eval["report_text"].rstrip(),
        "```",
        "",
        "### Heldout Source Eval",
        "",
        "This is the main smoke signal because source groups were held out from training.",
        "",
        f"- Rows: {len(heldout_df)}",
        f"- Classes: {', '.join(f'{k}={v}' for k, v in sorted(_class_counts(heldout_df).items())) or 'none'}",
        f"- Groups: {heldout_df[group_col].astype(str).nunique() if group_col and not heldout_df.empty else 0}",
        "",
        "```text",
        heldout_eval["report_text"].rstrip(),
        "```",
        "",
        "### Reliability Warning",
        "",
        f"- Total real clips used: {len(df)}",
        f"- Split strategy: fixed_split_manifest",
        f"- Synthetic included: {'yes' if include_synthetic else 'no'}",
        f"- Classes below 10 clips: {', '.join(classes_below_10) or 'none'}",
        f"- Known leakage risks: {', '.join(reliability_risks) or 'none'}",
        f"- Should metrics be trusted? {trust}",
        "",
        "## Confusion Matrices",
        "",
        "- Validation CSV: `reports/hydrophone/classifier_confusion_matrix_validation.csv`",
        "- Heldout CSV: `reports/hydrophone/classifier_confusion_matrix_heldout_source_eval.csv`",
        "",
        "## Split Metadata",
        "",
        "- JSON: `reports/hydrophone/classifier_split_metadata.json`",
    ]
    write_text(report_path, "\n".join(lines))
    return {
        "status": "ran",
        "mode": "fixed_split",
        "class_counts": class_counts,
        "group_counts": group_counts,
        "validation": validation_eval,
        "heldout": heldout_eval,
        "split_metadata": metadata,
    }


def _train_random_split_classifier(
    *,
    df,
    features_path: Path,
    report_root: Path,
    random_state: int,
    include_synthetic: bool,
) -> dict[str, Any]:
    RandomForestClassifier, classification_report, confusion_matrix, train_test_split = _load_model_tools()
    report_path = report_root / "classifier_baseline_report.md"
    confusion_csv_path = report_root / "classifier_confusion_matrix.csv"
    split_metadata_path = report_root / "classifier_split_metadata.json"

    raw_rows = len(df)
    df = filter_real_rows(df, include_synthetic=include_synthetic)
    df = df[df["label"].notna() & (df["label"].astype(str) != "")]
    class_counts = _class_counts(df)
    group_col = _choose_group_column(df)
    total_groups = int(df[group_col].astype(str).nunique()) if group_col else 0
    if len(class_counts) < 2:
        _write_skip_report(
            report_path,
            "fewer than 2 classes available",
            [f"{label}: {count}" for label, count in sorted(class_counts.items())],
            total_clips=len(df),
            classes=class_counts,
            groups=total_groups,
            include_synthetic=include_synthetic,
        )
        return {"status": "skipped", "reason": "too_few_classes", "class_counts": class_counts}
    if len(df) < 4:
        _write_skip_report(
            report_path,
            "too few clips for a meaningful train/test split",
            total_clips=len(df),
            classes=class_counts,
            groups=total_groups,
            include_synthetic=include_synthetic,
        )
        return {"status": "skipped", "reason": "too_few_rows", "class_counts": class_counts}

    numeric_cols = _numeric_feature_columns(df)
    if not numeric_cols:
        _write_skip_report(report_path, "no numeric feature columns found", include_synthetic=include_synthetic)
        return {"status": "skipped", "reason": "no_numeric_features"}

    X = df[numeric_cols].fillna(0.0).to_numpy(dtype=float)
    y = df["label"].astype(str).to_numpy()
    split_policy = f"stable_grouped_by_{group_col}" if group_col else "sklearn_train_test_split"
    split = _stable_group_split(df, group_col=group_col) if group_col else None
    train_groups: list[str] = []
    test_groups: list[str] = []
    if split is not None:
        train_idx, test_idx = split
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        train_groups = sorted(set(df.iloc[train_idx][group_col].astype(str))) if group_col else []
        test_groups = sorted(set(df.iloc[test_idx][group_col].astype(str))) if group_col else []
    else:
        split_policy = "sklearn_train_test_split"
        indices = list(range(len(df)))
        stratify = y if min(class_counts.values()) >= 2 else None
        try:
            train_idx, test_idx = train_test_split(indices, y, test_size=0.35, random_state=random_state, stratify=stratify)
        except ValueError:
            train_idx, test_idx = train_test_split(indices, y, test_size=0.35, random_state=random_state, stratify=None)
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        if group_col:
            train_groups = sorted(set(df.iloc[train_idx][group_col].astype(str)))
            test_groups = sorted(set(df.iloc[test_idx][group_col].astype(str)))

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=8,
        random_state=random_state,
        class_weight="balanced",
    )
    model.fit(X_train, y_train)
    labels = sorted(class_counts)
    predicted = model.predict(X_test)
    report_text = classification_report(y_test, predicted, labels=labels, zero_division=0)
    matrix = confusion_matrix(y_test, predicted, labels=labels)
    _write_confusion_csv(confusion_csv_path, labels, matrix)

    group_counts = _group_counts(df, group_col)
    classes_below_10 = sorted(label for label, count in class_counts.items() if count < 10)
    leakage_risks: list[str] = []
    if split_policy == "sklearn_train_test_split":
        leakage_risks.append("fallback split is not group-safe")
    if classes_below_10:
        leakage_risks.append("some classes have fewer than 10 clips")
    if len(df) < 100:
        leakage_risks.append("corpus is still small")
    trust = "no" if split_policy == "sklearn_train_test_split" else "limited"

    split_metadata = {
        "generated": utc_now_iso(),
        "features_path": str(features_path),
        "raw_feature_rows": int(raw_rows),
        "training_rows": int(len(df)),
        "include_synthetic": bool(include_synthetic),
        "split_strategy": split_policy,
        "group_column": group_col,
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "train_groups": train_groups,
        "test_groups": test_groups,
        "class_counts": class_counts,
        "group_counts": group_counts,
        "classes_below_10": classes_below_10,
        "known_leakage_risks": leakage_risks,
        "should_metrics_be_trusted": trust,
    }
    split_metadata_path.write_text(json.dumps(split_metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Hydrophone Classifier Baseline Report",
        "",
        f"Generated: {utc_now_iso()}",
        "",
        "## Status",
        "",
        "Ran RandomForestClassifier baseline.",
        "",
        "## Corpus",
        "",
        f"- Rows: {len(df)}",
        f"- Raw feature rows loaded: {raw_rows}",
        f"- Train rows: {len(X_train)}",
        f"- Test rows: {len(X_test)}",
        f"- Numeric features: {len(numeric_cols)}",
        f"- Split policy: {split_policy}",
        f"- Synthetic included: {'yes' if include_synthetic else 'no'}",
        "",
        "## Class Counts",
        "",
    ]
    for label, count in sorted(class_counts.items()):
        lines.append(f"- `{label}`: {count}")
    lines.extend(["", "## Group Counts", ""])
    for label, count in sorted(group_counts.items()):
        lines.append(f"- `{label}`: {count}")
    lines.extend(
        [
            "",
            "## Eval Reliability",
            "",
            f"- Total clips: {len(df)}",
            f"- Classes: {', '.join(f'{k}={v}' for k, v in sorted(class_counts.items()))}",
            f"- Groups: {total_groups}",
            f"- Split strategy: {split_policy}",
            f"- Classes below 10 clips: {', '.join(classes_below_10) or 'none'}",
            f"- Known leakage risks: {', '.join(leakage_risks) or 'none'}",
            f"- Should metrics be trusted? {trust}",
            "",
            "## Precision / Recall / F1",
            "",
            "```text",
            report_text.rstrip(),
            "```",
            "",
            "## Confusion Matrix",
            "",
            f"CSV: `{confusion_csv_path.relative_to(report_root.parent.parent).as_posix()}`",
            "",
            "## Split Metadata",
            "",
            f"JSON: `{split_metadata_path.relative_to(report_root.parent.parent).as_posix()}`",
        ]
    )
    write_text(report_path, "\n".join(lines))
    return {
        "status": "ran",
        "mode": "random_split",
        "rows": len(df),
        "class_counts": class_counts,
        "group_counts": group_counts,
        "report": report_text,
        "split_metadata": split_metadata,
    }


def train_classifier(
    *,
    features_path: Path,
    report_root: Path,
    random_state: int = 7,
    include_synthetic: bool = False,
    split_dir: Path | None = None,
) -> dict[str, Any]:
    ensure_dir(report_root)
    report_path = report_root / "classifier_baseline_report.md"
    try:
        df = _load_features(features_path)
    except Exception as exc:  # noqa: BLE001
        _write_skip_report(report_path, f"feature table unavailable: {type(exc).__name__}: {exc}", include_synthetic=include_synthetic)
        return {"status": "skipped", "reason": "feature_table_unavailable"}

    if df.empty:
        _write_skip_report(report_path, "feature table has no rows", include_synthetic=include_synthetic)
        return {"status": "skipped", "reason": "no_rows"}
    if "label" not in df.columns or "clip_id" not in df.columns:
        _write_skip_report(report_path, "feature table must include label and clip_id columns", include_synthetic=include_synthetic)
        return {"status": "skipped", "reason": "missing_required_columns"}

    if split_dir is not None:
        required = [split_dir / f"{split}.jsonl" for split in SPLIT_NAMES]
        if all(path.exists() for path in required):
            return _train_fixed_split_classifier(
                df=df,
                features_path=features_path,
                split_dir=split_dir,
                report_root=report_root,
                random_state=random_state,
                include_synthetic=include_synthetic,
            )
        _write_skip_report(
            report_path,
            f"split directory is missing required files: {split_dir}",
            include_synthetic=include_synthetic,
        )
        return {"status": "skipped", "reason": "missing_split_files"}

    return _train_random_split_classifier(
        df=df,
        features_path=features_path,
        report_root=report_root,
        random_state=random_state,
        include_synthetic=include_synthetic,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train a baseline hydrophone classifier.")
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--report-root", default=str(DEFAULT_REPORT_ROOT))
    parser.add_argument("--features-path", default=None)
    parser.add_argument("--split-dir", default=None)
    parser.add_argument("--random-state", type=int, default=7)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--real-only", action="store_true", help="Exclude synthetic rows. This is the default.")
    mode.add_argument("--include-synthetic", action="store_true", help="Include synthetic rows if present in the feature table.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    data_root = Path(args.data_root)
    report_root = Path(args.report_root)
    ensure_hydrophone_layout(data_root, report_root)
    features_path = Path(args.features_path) if args.features_path else _default_features_path(data_root)
    split_dir = Path(args.split_dir) if args.split_dir else None
    result = train_classifier(
        features_path=features_path,
        report_root=report_root,
        random_state=args.random_state,
        include_synthetic=bool(args.include_synthetic),
        split_dir=split_dir,
    )
    print(f"hydrophone classifier complete: status={result['status']} reason={result.get('reason', '')}")
    if result.get("class_counts"):
        counts = ", ".join(f"{label}={count}" for label, count in sorted(result["class_counts"].items()))
        print(f"class counts: {counts}")
    metadata = result.get("split_metadata") or {}
    for label in metadata.get("classes_below_10", []):
        print(f"WARNING: class below 10 clips: {label}")
    if metadata.get("known_leakage_risks"):
        print("WARNING: eval reliability is limited: " + "; ".join(metadata["known_leakage_risks"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
