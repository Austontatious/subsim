"""Build renderer-facing parameter exports from hydrophone analysis artifacts."""

from __future__ import annotations

import csv
import datetime as dt
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any


REQUIRED_RENDER_FAMILIES = [
    "ambient_soundscape",
    "marine_mammal_whale",
    "marine_mammal_other",
    "surface_vessel",
    "intermittent_machinery_archetype",
]


FAMILY_CONFIG: dict[str, dict[str, Any]] = {
    "ambient_soundscape": {
        "source_categories": ["ambient_soundscape"],
        "synthesis_mode": "ambient_bed",
        "acoustic_contract_hook": "foundation.ambient",
        "default_duration_s": 10.0,
        "seed_mix": 0.18,
    },
    "marine_mammal_whale": {
        "source_categories": ["marine_mammal_whale"],
        "synthesis_mode": "hybrid",
        "acoustic_contract_hook": "contacts.biologic_large",
        "default_duration_s": 7.5,
        "seed_mix": 0.12,
    },
    "marine_mammal_other": {
        "source_categories": ["marine_mammal_other"],
        "synthesis_mode": "hybrid",
        "acoustic_contract_hook": "contacts.biologic_other",
        "default_duration_s": 6.0,
        "seed_mix": 0.10,
    },
    "surface_vessel": {
        "source_categories": ["surface_vessel"],
        "synthesis_mode": "hybrid",
        "acoustic_contract_hook": "contacts.surface_vessel",
        "default_duration_s": 8.0,
        "seed_mix": 0.15,
    },
    "intermittent_machinery_archetype": {
        "source_categories": ["surface_vessel"],
        "safe_archetype_filter": "intermittent_machinery_archetype",
        "synthesis_mode": "procedural",
        "acoustic_contract_hook": "contacts.unknown_contact_like",
        "default_duration_s": 8.0,
        "seed_mix": 0.06,
    },
}


FEATURE_KEYS = [
    "dominant_freq_hz",
    "spectral_centroid_hz",
    "spectral_bandwidth_hz",
    "spectral_rolloff_hz",
    "spectral_flatness",
    "narrowband_index",
    "harmonicity",
    "dominant_mod_hz",
    "inter_event_interval_s",
    "transient_density",
    "roughness",
    "envelope_std",
    "duration_s",
]


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:  # noqa: BLE001
        return default


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    values = sorted(values)
    x = (len(values) - 1) * p
    lo = int(math.floor(x))
    hi = int(math.ceil(x))
    if lo == hi:
        return values[lo]
    frac = x - lo
    return values[lo] * (1.0 - frac) + values[hi] * frac


def _feature_summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {
            "min": 0.0,
            "max": 0.0,
            "mean": 0.0,
            "std": 0.0,
            "p10": 0.0,
            "p50": 0.0,
            "p90": 0.0,
        }

    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return {
        "min": min(values),
        "max": max(values),
        "mean": mean,
        "std": math.sqrt(variance),
        "p10": _percentile(values, 0.10),
        "p50": _percentile(values, 0.50),
        "p90": _percentile(values, 0.90),
    }


def _read_feature_rows(features_csv_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with features_csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            casted: dict[str, Any] = dict(row)
            for key in FEATURE_KEYS:
                casted[key] = _to_float(row.get(key), 0.0)
            casted["category_label"] = str(row.get("category_label") or "")
            casted["safe_archetype_tag"] = str(row.get("safe_archetype_tag") or "")
            rows.append(casted)
    return rows


def _select_rows_for_family(rows: list[dict[str, Any]], family: str) -> list[dict[str, Any]]:
    config = FAMILY_CONFIG[family]
    source_categories = set(config.get("source_categories", []))
    filtered = [r for r in rows if r.get("category_label") in source_categories]

    archetype = config.get("safe_archetype_filter")
    if archetype:
        arche_rows = [r for r in filtered if r.get("safe_archetype_tag") == archetype]
        if arche_rows:
            return arche_rows
    return filtered


def _build_seed_exemplars(
    *,
    family: str,
    family_rows: list[dict[str, Any]],
    exemplar_categories: dict[str, Any],
) -> list[dict[str, Any]]:
    seeds: list[dict[str, Any]] = []

    # category-level representative/outlier seeds
    for category in FAMILY_CONFIG[family].get("source_categories", []):
        exemplar = exemplar_categories.get(category)
        if not exemplar:
            continue
        rep_path = exemplar.get("representative_file_path")
        out_path = exemplar.get("outlier_file_path")
        if rep_path:
            seeds.append(
                {
                    "role": "representative",
                    "sample_id": exemplar.get("representative_sample_id"),
                    "file_path": rep_path,
                }
            )
        if out_path:
            seeds.append(
                {
                    "role": "outlier_texture",
                    "sample_id": exemplar.get("outlier_sample_id"),
                    "file_path": out_path,
                }
            )

    # add additional seed candidates from current family rows
    if family_rows:
        sorted_rows = sorted(
            family_rows,
            key=lambda r: (abs(_to_float(r.get("spectral_flatness"), 0.0) - 0.2), -_to_float(r.get("narrowband_index"), 0.0)),
        )
        for row in sorted_rows[:2]:
            seeds.append(
                {
                    "role": "auto_candidate",
                    "sample_id": row.get("sample_id"),
                    "file_path": row.get("file_path"),
                }
            )

    # dedupe by path
    deduped: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for seed in seeds:
        path = str(seed.get("file_path") or "")
        if not path or path in seen_paths:
            continue
        seen_paths.add(path)
        deduped.append(seed)
    return deduped[:4]


def _derived_family_parameters(feature_ranges: dict[str, dict[str, float]], family: str) -> dict[str, Any]:
    dominant = feature_ranges["dominant_freq_hz"]
    bandwidth = feature_ranges["spectral_bandwidth_hz"]
    cadence = feature_ranges["inter_event_interval_s"]
    modulation = feature_ranges["dominant_mod_hz"]
    flatness = feature_ranges["spectral_flatness"]
    narrowband = feature_ranges["narrowband_index"]

    band_low = max(20.0, dominant["p10"] * 0.8)
    band_mid = max(20.0, dominant["p50"])
    band_high = max(band_low + 10.0, dominant["p90"] * 1.2)

    if family == "ambient_soundscape":
        event_cadence = max(0.8, cadence["p50"] * 16.0)
    elif family in {"marine_mammal_whale", "marine_mammal_other"}:
        event_cadence = max(0.25, cadence["p50"] * 10.0)
    elif family == "surface_vessel":
        event_cadence = max(0.2, cadence["p50"] * 6.0)
    else:
        event_cadence = max(0.5, cadence["p50"] * 18.0)

    modulation_mid = max(0.05, modulation["p50"])

    freq_jitter_pct = min(0.45, max(0.03, (dominant["p90"] - dominant["p10"]) / max(40.0, dominant["p50"])))
    modulation_jitter_pct = min(0.75, max(0.1, (modulation["p90"] - modulation["p10"]) / max(0.05, modulation_mid)))

    return {
        "dominant_band_hz": {
            "low": round(band_low, 3),
            "mid": round(band_mid, 3),
            "high": round(band_high, 3),
        },
        "bandwidth_tendency_hz": {
            "median": round(bandwidth["p50"], 3),
            "upper": round(bandwidth["p90"], 3),
        },
        "tonality_tendency": {
            "spectral_flatness_median": round(flatness["p50"], 6),
            "narrowband_index_median": round(narrowband["p50"], 6),
        },
        "event_cadence_s": {
            "median": round(event_cadence, 4),
            "fast": round(max(0.08, event_cadence * 0.65), 4),
            "slow": round(event_cadence * 1.6, 4),
        },
        "modulation_hz": {
            "median": round(modulation_mid, 4),
            "low": round(max(0.05, modulation["p10"]), 4),
            "high": round(max(0.1, modulation["p90"]), 4),
        },
        "variability_knobs": {
            "frequency_jitter_pct": round(freq_jitter_pct, 4),
            "modulation_jitter_pct": round(modulation_jitter_pct, 4),
            "timing_jitter_pct": 0.18 if family == "intermittent_machinery_archetype" else 0.12,
            "roughness_jitter_pct": 0.2,
        },
    }


def build_renderer_params_v1(
    *,
    hydro_root: Path,
    output_json_path: Path,
    output_md_path: Path | None = None,
) -> dict[str, Any]:
    analysis_path = hydro_root / "reports" / "hydrophone_category_analysis_report.json"
    gap_path = hydro_root / "reports" / "hydrophone_dataset_gap_report.json"
    exemplars_path = hydro_root / "analysis" / "hydrophone_category_exemplars.json"
    features_csv_path = hydro_root / "features" / "hydrophone_features.csv"

    analysis = _read_json(analysis_path)
    gaps = _read_json(gap_path)
    exemplars = _read_json(exemplars_path)
    feature_rows = _read_feature_rows(features_csv_path)
    exemplar_categories = exemplars.get("categories", {})

    families: dict[str, Any] = {}

    for family in REQUIRED_RENDER_FAMILIES:
        rows = _select_rows_for_family(feature_rows, family)
        sample_count = len(rows)

        label_quality_counts = Counter(str(r.get("label_quality") or "unknown") for r in rows)
        source_counts = Counter(str(r.get("source_id") or "unknown") for r in rows)

        feature_ranges: dict[str, dict[str, float]] = {}
        for key in FEATURE_KEYS:
            vals = [_to_float(r.get(key), 0.0) for r in rows]
            feature_ranges[key] = _feature_summary(vals)

        derived = _derived_family_parameters(feature_ranges, family)
        seeds = _build_seed_exemplars(
            family=family,
            family_rows=rows,
            exemplar_categories=exemplar_categories,
        )

        families[family] = {
            "family": family,
            "synthesis_mode": FAMILY_CONFIG[family]["synthesis_mode"],
            "acoustic_contract_hook": FAMILY_CONFIG[family]["acoustic_contract_hook"],
            "default_duration_s": FAMILY_CONFIG[family]["default_duration_s"],
            "seed_mix": FAMILY_CONFIG[family]["seed_mix"],
            "analysis_basis": {
                "sample_count": sample_count,
                "source_categories": FAMILY_CONFIG[family].get("source_categories", []),
                "safe_archetype_filter": FAMILY_CONFIG[family].get("safe_archetype_filter"),
                "source_counts": dict(sorted(source_counts.items())),
                "label_quality_counts": dict(sorted(label_quality_counts.items())),
            },
            "feature_ranges": feature_ranges,
            "derived_parameters": derived,
            "seed_exemplars": seeds,
        }

    payload: dict[str, Any] = {
        "renderer_params_version": "renderer_params_v1",
        "generated_utc": _utc_now_iso(),
        "source_analysis": {
            "analysis_report_path": str(analysis_path),
            "gap_report_path": str(gap_path),
            "exemplar_path": str(exemplars_path),
            "features_csv_path": str(features_csv_path),
            "analysis_report_version": analysis.get("report_version"),
            "analysis_sample_count": analysis.get("sample_count"),
        },
        "global": {
            "safe_contact_policy": (
                "Contact-like rendering uses abstract archetypes only and never nation/class-specific military signatures."
            ),
            "supported_families": REQUIRED_RENDER_FAMILIES,
            "acoustic_contract_schema_version": "acoustic-substrate.v1",
            "default_sample_rate_hz": 44100,
        },
        "families": families,
        "coverage_snapshot": gaps.get("category_gaps", {}),
    }

    _write_json(output_json_path, payload)

    if output_md_path is not None:
        _write_renderer_params_markdown(output_md_path, payload)

    return payload


def _write_renderer_params_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append("# Renderer Params v1")
    lines.append("")
    lines.append(f"Generated: {payload.get('generated_utc')}")
    lines.append("")
    lines.append("## Scope")
    lines.append("")
    lines.append(
        "Renderer-facing parameter export derived from hydrophone analyzer outputs for first hybrid family generation in Subsim."
    )
    lines.append("")

    families = payload.get("families", {})
    for family in REQUIRED_RENDER_FAMILIES:
        detail = families.get(family, {})
        basis = detail.get("analysis_basis", {})
        derived = detail.get("derived_parameters", {})
        lines.append(f"## {family}")
        lines.append("")
        lines.append(f"- Synthesis mode: `{detail.get('synthesis_mode', 'unknown')}`")
        lines.append(f"- Acoustic contract hook: `{detail.get('acoustic_contract_hook', 'unknown')}`")
        lines.append(f"- Source sample count: {basis.get('sample_count', 0)}")
        lines.append(f"- Seed exemplars: {len(detail.get('seed_exemplars', []))}")
        band = derived.get("dominant_band_hz", {})
        lines.append(
            f"- Dominant band (Hz): low={band.get('low', 0)}, mid={band.get('mid', 0)}, high={band.get('high', 0)}"
        )
        cadence = derived.get("event_cadence_s", {})
        lines.append(
            f"- Cadence (s): fast={cadence.get('fast', 0)}, median={cadence.get('median', 0)}, slow={cadence.get('slow', 0)}"
        )
        lines.append("")

    lines.append("## Safety")
    lines.append("")
    lines.append(
        "All contact-like families remain abstract gameplay archetypes and do not attempt real-world military platform signature emulation."
    )
    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


__all__ = [
    "REQUIRED_RENDER_FAMILIES",
    "build_renderer_params_v1",
]
