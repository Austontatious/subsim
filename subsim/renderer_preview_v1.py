"""Preview rendering and report helpers for Hybrid Acoustic Renderer v1."""

from __future__ import annotations

import datetime as dt
import json
import math
import wave
from pathlib import Path
from typing import Any

from .renderer_v1 import HybridAcousticRendererV1

try:  # pragma: no cover - optional
    import matplotlib.pyplot as plt

    _HAVE_MPL = True
except Exception:  # pragma: no cover
    plt = None  # type: ignore
    _HAVE_MPL = False


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def generate_renderer_previews(
    renderer: HybridAcousticRendererV1,
    *,
    output_root: Path,
    variants_per_family: int = 4,
    base_seed: int = 20260424,
    include_plots: bool = True,
    duration_override_s: float | None = None,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    audio_dir = output_root / "audio"
    plots_dir = output_root / "plots"
    audio_dir.mkdir(parents=True, exist_ok=True)
    if include_plots:
        plots_dir.mkdir(parents=True, exist_ok=True)

    entries: list[dict[str, Any]] = []
    families = renderer.supported_families()

    for fam_idx, family in enumerate(families):
        for variant_idx in range(variants_per_family):
            seed = base_seed + fam_idx * 1000 + variant_idx * 37
            variability = min(0.95, 0.22 + 0.18 * variant_idx)
            intensity = 0.9 + 0.12 * (variant_idx % 3)
            file_name = f"{family}_v{variant_idx + 1}_s{seed}.wav"
            wav_path = audio_dir / file_name

            meta = renderer.render_family_to_wav(
                wav_path,
                family,
                duration_s=duration_override_s,
                seed=seed,
                variability=variability,
                intensity=intensity,
                include_seed=True,
            )

            entry = {
                "preview_id": f"{family}:v{variant_idx + 1}:s{seed}",
                "family": family,
                "variant_index": variant_idx + 1,
                "seed": seed,
                "variability": variability,
                "intensity": intensity,
                "duration_s": meta.get("duration_s"),
                "sample_rate_hz": meta.get("sample_rate_hz"),
                "synthesis_mode": meta.get("synthesis_mode"),
                "acoustic_contract_hook": meta.get("acoustic_contract_hook"),
                "seed_exemplar_used": meta.get("seed_exemplar_used"),
                "pcm_sha1": meta.get("pcm_sha1"),
                "audio_path": str(wav_path.resolve()),
                "render_params": meta.get("render_params", {}),
            }
            entries.append(entry)

            if include_plots and variant_idx == 0:
                _write_preview_plot(wav_path, plots_dir / f"{family}_preview.png", title=f"{family} preview")

    manifest = {
        "manifest_version": "renderer_preview_manifest.v1",
        "generated_utc": _utc_now_iso(),
        "renderer_version": "hybrid_renderer_v1",
        "variants_per_family": variants_per_family,
        "base_seed": base_seed,
        "families": families,
        "entry_count": len(entries),
        "audio_dir": str(audio_dir.resolve()),
        "entries": entries,
    }
    _write_json(output_root / "renderer_preview_manifest.json", manifest)
    return manifest


def _read_wav_float(path: Path) -> tuple[list[float], int]:
    with wave.open(str(path), "rb") as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        sr = wf.getframerate()
        raw = wf.readframes(wf.getnframes())

    if sampwidth != 2:
        return [], sr

    samples: list[float] = []
    for i in range(0, len(raw), 2 * channels):
        frame_vals = []
        for ch in range(channels):
            j = i + ch * 2
            if j + 2 > len(raw):
                continue
            v = int.from_bytes(raw[j : j + 2], byteorder="little", signed=True)
            frame_vals.append(v / 32768.0)
        if frame_vals:
            samples.append(sum(frame_vals) / len(frame_vals))
    return samples, sr


def _write_preview_plot(wav_path: Path, out_png: Path, *, title: str) -> None:
    if not _HAVE_MPL:
        return
    samples, sr = _read_wav_float(wav_path)
    if not samples:
        return

    duration = len(samples) / max(1, sr)
    t = [i / sr for i in range(len(samples))]

    fig = plt.figure(figsize=(10, 6))
    ax1 = fig.add_subplot(2, 1, 1)
    ax1.plot(t, samples, linewidth=0.6)
    ax1.set_title(title)
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Amplitude")

    ax2 = fig.add_subplot(2, 1, 2)
    ax2.specgram(samples, NFFT=512, Fs=sr, noverlap=256)
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Frequency (Hz)")
    ax2.set_ylim(0, min(12000, sr / 2))

    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=140)
    plt.close(fig)


def build_renderer_preview_report(
    *,
    renderer_params: dict[str, Any],
    preview_manifest: dict[str, Any],
    gap_report: dict[str, Any],
    output_json_path: Path,
    output_md_path: Path,
) -> dict[str, Any]:
    families = renderer_params.get("families", {})
    entries = preview_manifest.get("entries", [])

    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        grouped.setdefault(str(entry.get("family")), []).append(entry)

    family_assessments: list[dict[str, Any]] = []
    for family, family_cfg in families.items():
        family_entries = grouped.get(family, [])
        sample_count = int(family_cfg.get("analysis_basis", {}).get("sample_count", 0))
        synthesis_mode = str(family_cfg.get("synthesis_mode", "unknown"))

        if sample_count >= 50 and len(family_entries) >= 3:
            readiness = "plausible_for_first_integration"
        elif sample_count >= 12 and len(family_entries) >= 2:
            readiness = "prototype_quality_needs_tuning"
        else:
            readiness = "experimental_sparse"

        common_risks: list[str] = []
        if family in {"surface_vessel", "intermittent_machinery_archetype"}:
            common_risks.append("Can become rhythmically repetitive without wider timing perturbations.")
        if family in {"marine_mammal_whale", "marine_mammal_other"}:
            common_risks.append("Biologic phrase realism still depends on richer phrase-level envelopes and optional exemplar curation.")
        if family == "ambient_soundscape":
            common_risks.append("Weather/geophony texture coverage is currently thin and may sound overly stationary.")

        family_assessments.append(
            {
                "family": family,
                "synthesis_mode": synthesis_mode,
                "analysis_sample_count": sample_count,
                "preview_count": len(family_entries),
                "integration_readiness": readiness,
                "acoustic_contract_hook": family_cfg.get("acoustic_contract_hook"),
                "common_risks": common_risks,
                "next_steps": _family_next_steps(family),
            }
        )

    missing_categories = [
        cat
        for cat, detail in gap_report.get("category_gaps", {}).items()
        if detail.get("coverage_status") == "missing"
    ]

    report = {
        "report_version": "renderer_preview_report.v1",
        "generated_utc": _utc_now_iso(),
        "renderer_params_version": renderer_params.get("renderer_params_version"),
        "preview_manifest_path": preview_manifest.get("audio_dir"),
        "families_assessed": family_assessments,
        "known_missing_categories": missing_categories,
        "overall_recommendations": [
            "Integrate ambient, whale, marine_mammal_other, and surface_vessel as first playable hybrid families.",
            "Keep intermittent machinery archetype as ambiguous contact-like clutter, not platform-specific signature rendering.",
            "Prioritize second-wave source pulls for weather_geophony and anthropogenic_non_vessel to enrich world-bed diversity.",
        ],
        "validation_scope": {
            "structural": "Preview generation and manifest/report consistency are validated automatically.",
            "subjective": "Perceptual quality remains listening-based and should be reviewed by design/audio iteration.",
        },
    }

    _write_json(output_json_path, report)
    _write_renderer_preview_markdown(output_md_path, report)
    return report


def _family_next_steps(family: str) -> list[str]:
    if family == "ambient_soundscape":
        return [
            "Add weather layers (rain/storm impulse textures) and low-frequency swell controls.",
            "Add dynamic depth/occlusion hooks for scenario-driven ambient changes.",
        ]
    if family == "marine_mammal_whale":
        return [
            "Expand phrase templates (upsweeps/downsweeps) and inter-phrase spacing variation.",
            "Curate 3-6 high-quality exemplar snippets for phrase-tail realism.",
        ]
    if family == "marine_mammal_other":
        return [
            "Add richer click-train grammars (burst packetization and chirp arcs).",
            "Differentiate dolphin-like vs seal-like textures through modulation presets.",
        ]
    if family == "surface_vessel":
        return [
            "Add explicit cavitation state controls tied to speed/load abstractions.",
            "Blend low-engine harmonics with sparse mechanical transients for class variation.",
        ]
    if family == "intermittent_machinery_archetype":
        return [
            "Increase ambiguity controls (event sparsity, narrowband drift, transient smear).",
            "Keep labels abstract (quiet/noisy/unknown contact-like) and avoid real platform mapping.",
        ]
    return ["Tune category-specific generator controls."]


def _write_renderer_preview_markdown(path: Path, report: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append("# Renderer Preview Report (v1)")
    lines.append("")
    lines.append(f"Generated: {report.get('generated_utc')}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("This report evaluates the first hybrid renderer preview pass generated from hydrophone-derived renderer params.")
    lines.append("")

    lines.append("## Family Assessments")
    lines.append("")
    for fam in report.get("families_assessed", []):
        lines.append(f"### {fam.get('family')}")
        lines.append("")
        lines.append(f"- Synthesis mode: `{fam.get('synthesis_mode')}`")
        lines.append(f"- Analysis sample count: {fam.get('analysis_sample_count')}")
        lines.append(f"- Preview renders: {fam.get('preview_count')}")
        lines.append(f"- Integration readiness: `{fam.get('integration_readiness')}`")
        lines.append(f"- Contract hook: `{fam.get('acoustic_contract_hook')}`")
        risks = fam.get("common_risks", [])
        if risks:
            for risk in risks:
                lines.append(f"- Risk: {risk}")
        for step in fam.get("next_steps", []):
            lines.append(f"- Next: {step}")
        lines.append("")

    missing = report.get("known_missing_categories", [])
    lines.append("## Data Gaps Still Affecting Renderer")
    lines.append("")
    if missing:
        for cat in missing:
            lines.append(f"- {cat}")
    else:
        lines.append("- No missing categories flagged in current gap report.")
    lines.append("")

    lines.append("## Validation Notes")
    lines.append("")
    scope = report.get("validation_scope", {})
    lines.append(f"- Structural: {scope.get('structural', '')}")
    lines.append(f"- Subjective: {scope.get('subjective', '')}")
    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


__all__ = [
    "build_renderer_preview_report",
    "generate_renderer_previews",
]
