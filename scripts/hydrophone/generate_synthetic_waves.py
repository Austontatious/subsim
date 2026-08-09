#!/usr/bin/env python3
"""Generate synthetic hydrophone/contact-like WAVs for safe SubSim experimentation."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any, Callable

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hydrophone_common import (  # noqa: E402
    DEFAULT_DATA_ROOT,
    DEFAULT_REPORT_ROOT,
    conservative_normalize,
    count_by,
    ensure_hydrophone_layout,
    repo_relative,
    write_jsonl,
    write_text,
    write_wav,
    utc_now_iso,
)


GeneratorFn = Callable[[np.random.Generator, int, float], tuple[np.ndarray, dict[str, Any]]]
SUBLIKE_DISCLAIMER = "Synthetic/simulated contact-like signal, not a real submarine recording."


def _timebase(sample_rate: int, duration_sec: float) -> np.ndarray:
    return np.arange(int(round(sample_rate * duration_sec)), dtype=np.float32) / float(sample_rate)


def _sine_with_drift(t: np.ndarray, base_hz: float, drift_hz: float, phase: float = 0.0) -> np.ndarray:
    duration = max(float(t[-1]) if len(t) > 1 else 1.0, 1e-6)
    instantaneous = base_hz + drift_hz * np.sin(2.0 * np.pi * t / duration)
    phase_acc = 2.0 * np.pi * np.cumsum(instantaneous) / (len(t) / duration)
    return np.sin(phase_acc + phase)


def _lowpass_noise(rng: np.random.Generator, n: int, strength: float = 0.98) -> np.ndarray:
    white = rng.normal(0.0, 1.0, n).astype(np.float32)
    out = np.zeros(n, dtype=np.float32)
    prev = 0.0
    for i, value in enumerate(white):
        prev = strength * prev + (1.0 - strength) * float(value)
        out[i] = prev
    return out


def _band_texture(rng: np.random.Generator, n: int) -> np.ndarray:
    low = _lowpass_noise(rng, n, strength=0.992)
    mid = rng.normal(0.0, 0.18, n).astype(np.float32)
    return low + mid


def _harmonic_stack(rng: np.random.Generator, sample_rate: int, duration_sec: float) -> tuple[np.ndarray, dict[str, Any]]:
    t = _timebase(sample_rate, duration_sec)
    base = float(rng.uniform(45.0, 95.0))
    drift = float(rng.uniform(0.2, 2.0))
    harmonics = [1, 2, 3, 4]
    samples = np.zeros_like(t)
    for idx, harmonic in enumerate(harmonics):
        amp = 0.28 / (idx + 1)
        samples += amp * _sine_with_drift(t, base * harmonic, drift * (idx + 1), rng.uniform(0, 2 * np.pi))
    noise_level = float(rng.uniform(0.015, 0.05))
    samples += noise_level * _band_texture(rng, len(t))
    return samples, {
        "base_frequency_hz": round(base, 3),
        "harmonics": harmonics,
        "drift_hz": round(drift, 3),
        "noise_level": round(noise_level, 4),
    }


def _slow_drifting_tonal(rng: np.random.Generator, sample_rate: int, duration_sec: float) -> tuple[np.ndarray, dict[str, Any]]:
    t = _timebase(sample_rate, duration_sec)
    base = float(rng.uniform(80.0, 180.0))
    drift = float(rng.uniform(2.0, 8.0))
    envelope = 0.45 + 0.15 * np.sin(2.0 * np.pi * t / max(duration_sec, 1e-6))
    samples = envelope * _sine_with_drift(t, base, drift, rng.uniform(0, 2 * np.pi))
    samples += 0.04 * _band_texture(rng, len(t))
    return samples, {"base_frequency_hz": round(base, 3), "drift_hz": round(drift, 3), "noise_level": 0.04}


def _weak_intermittent_tonal(rng: np.random.Generator, sample_rate: int, duration_sec: float) -> tuple[np.ndarray, dict[str, Any]]:
    t = _timebase(sample_rate, duration_sec)
    base = float(rng.uniform(55.0, 140.0))
    pulse_rate = float(rng.uniform(0.3, 0.8))
    gate = (np.sin(2.0 * np.pi * pulse_rate * t) > rng.uniform(0.1, 0.45)).astype(np.float32)
    smooth_gate = np.convolve(gate, np.ones(max(8, sample_rate // 80)) / max(8, sample_rate // 80), mode="same")
    samples = 0.28 * smooth_gate * _sine_with_drift(t, base, rng.uniform(0.2, 1.2), rng.uniform(0, 2 * np.pi))
    samples += 0.035 * _band_texture(rng, len(t))
    return samples, {"base_frequency_hz": round(base, 3), "pulse_rate_hz": round(pulse_rate, 3), "noise_level": 0.035}


def _low_frequency_rumble(rng: np.random.Generator, sample_rate: int, duration_sec: float) -> tuple[np.ndarray, dict[str, Any]]:
    t = _timebase(sample_rate, duration_sec)
    base = float(rng.uniform(18.0, 45.0))
    samples = 0.35 * np.sin(2.0 * np.pi * base * t + rng.uniform(0, 2 * np.pi))
    samples += 0.18 * np.sin(2.0 * np.pi * (base * 1.7) * t)
    samples += 0.12 * _lowpass_noise(rng, len(t), strength=0.997)
    return samples, {"base_frequency_hz": round(base, 3), "harmonics": [1, 1.7], "noise_level": 0.12}


def _surface_vessel_track(rng: np.random.Generator, sample_rate: int, duration_sec: float) -> tuple[np.ndarray, dict[str, Any]]:
    t = _timebase(sample_rate, duration_sec)
    base = float(rng.uniform(70.0, 160.0))
    drift = float(rng.uniform(-10.0, 10.0))
    approach = np.sin(np.pi * t / max(duration_sec, 1e-6)) ** 0.8
    samples = np.zeros_like(t)
    for harmonic in [1, 2, 3, 5]:
        freq = base * harmonic + drift * (t / max(duration_sec, 1e-6))
        phase = 2.0 * np.pi * np.cumsum(freq) / sample_rate
        samples += (0.22 / harmonic) * np.sin(phase + rng.uniform(0, 2 * np.pi))
    samples *= 0.25 + 0.75 * approach
    samples += 0.09 * _band_texture(rng, len(t))
    return samples, {
        "base_frequency_hz": round(base, 3),
        "harmonics": [1, 2, 3, 5],
        "dopplerish_drift_hz": round(drift, 3),
        "noise_level": 0.09,
    }


def _filtered_noise_bed(rng: np.random.Generator, sample_rate: int, duration_sec: float) -> tuple[np.ndarray, dict[str, Any]]:
    n = int(round(duration_sec * sample_rate))
    texture = _band_texture(rng, n)
    swell = 0.55 + 0.2 * np.sin(np.linspace(0, 2 * np.pi, n, dtype=np.float32) + rng.uniform(0, 2 * np.pi))
    samples = 0.15 * texture * swell
    return samples, {"broadband_texture": "lowpass_plus_white", "noise_level": 0.15}


def _chirp_train(rng: np.random.Generator, sample_rate: int, duration_sec: float) -> tuple[np.ndarray, dict[str, Any]]:
    t = _timebase(sample_rate, duration_sec)
    samples = np.zeros_like(t)
    calls = int(rng.integers(3, 8))
    for _ in range(calls):
        start = float(rng.uniform(0.0, max(0.1, duration_sec - 0.8)))
        length = float(rng.uniform(0.18, 0.75))
        f0 = float(rng.uniform(250.0, 900.0))
        f1 = float(rng.uniform(900.0, 2600.0))
        idx = (t >= start) & (t < start + length)
        local = t[idx] - start
        if len(local) == 0:
            continue
        k = (f1 - f0) / max(length, 1e-6)
        phase = 2.0 * np.pi * (f0 * local + 0.5 * k * local * local)
        envelope = np.sin(np.pi * local / max(length, 1e-6))
        samples[idx] += 0.35 * envelope * np.sin(phase)
    samples += 0.025 * rng.normal(0.0, 1.0, len(t))
    return samples, {"call_count": calls, "frequency_sweep_hz": "250-2600", "noise_level": 0.025}


def _fish_pulse_train(rng: np.random.Generator, sample_rate: int, duration_sec: float) -> tuple[np.ndarray, dict[str, Any]]:
    t = _timebase(sample_rate, duration_sec)
    samples = np.zeros_like(t)
    pulse_count = int(rng.integers(8, 25))
    for _ in range(pulse_count):
        center = float(rng.uniform(0.1, max(0.2, duration_sec - 0.1)))
        width = float(rng.uniform(0.015, 0.06))
        freq = float(rng.uniform(90.0, 450.0))
        envelope = np.exp(-0.5 * ((t - center) / width) ** 2)
        samples += 0.18 * envelope * np.sin(2.0 * np.pi * freq * t + rng.uniform(0, 2 * np.pi))
    samples += 0.02 * _band_texture(rng, len(t))
    return samples, {"pulse_count": pulse_count, "pulse_band_hz": "90-450", "noise_level": 0.02}


def _unknown_click_burst(rng: np.random.Generator, sample_rate: int, duration_sec: float) -> tuple[np.ndarray, dict[str, Any]]:
    t = _timebase(sample_rate, duration_sec)
    samples = 0.04 * rng.normal(0.0, 1.0, len(t))
    burst_count = int(rng.integers(2, 6))
    for _ in range(burst_count):
        center = float(rng.uniform(0.0, duration_sec))
        width = float(rng.uniform(0.003, 0.02))
        samples += 0.35 * np.exp(-0.5 * ((t - center) / width) ** 2) * rng.choice([-1.0, 1.0])
    return samples, {"burst_count": burst_count, "noise_level": 0.04}


GENERATOR_SPECS: list[dict[str, Any]] = [
    {"label": "synthetic_submarine_like", "generation_type": "narrowband_harmonic_stack", "fn": _harmonic_stack},
    {"label": "synthetic_submarine_like", "generation_type": "slowly_drifting_tonal", "fn": _slow_drifting_tonal},
    {"label": "synthetic_submarine_like", "generation_type": "weak_intermittent_tonal", "fn": _weak_intermittent_tonal},
    {"label": "synthetic_submarine_like", "generation_type": "low_frequency_rumble", "fn": _low_frequency_rumble},
    {"label": "surface_vessel", "generation_type": "surface_vessel_doppler_track", "fn": _surface_vessel_track},
    {"label": "ambient_ocean", "generation_type": "filtered_noise_bed", "fn": _filtered_noise_bed},
    {"label": "biologic_mammal", "generation_type": "chirp_train", "fn": _chirp_train},
    {"label": "biologic_fish", "generation_type": "pulse_train", "fn": _fish_pulse_train},
    {"label": "unknown_or_noise", "generation_type": "irregular_click_burst", "fn": _unknown_click_burst},
]


def _synthetic_id(label: str, idx: int) -> str:
    prefixes = {
        "synthetic_submarine_like": "syn_sub_like",
        "surface_vessel": "syn_surface",
        "ambient_ocean": "syn_ambient",
        "biologic_mammal": "syn_mammal",
        "biologic_fish": "syn_fish",
        "unknown_or_noise": "syn_noise",
    }
    return f"{prefixes.get(label, 'syn')}_{idx:06d}"


def generate_synthetic_dataset(
    *,
    count: int,
    sample_rate: int,
    duration_sec: float,
    waves_dir: Path,
    manifest_path: Path,
    report_path: Path,
    seed: int = 7,
) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed)
    waves_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for idx in range(1, count + 1):
        spec = GENERATOR_SPECS[(idx - 1) % len(GENERATOR_SPECS)]
        samples, params = spec["fn"](rng, sample_rate, duration_sec)
        samples = conservative_normalize(samples)
        synthetic_id = _synthetic_id(str(spec["label"]), idx)
        path = waves_dir / f"{synthetic_id}.wav"
        write_wav(path, samples, sample_rate)
        disclaimer = (
            SUBLIKE_DISCLAIMER
            if spec["label"] == "synthetic_submarine_like"
            else "Synthetic/simulated training or distractor signal, not a field recording."
        )
        rows.append(
            {
                "synthetic_id": synthetic_id,
                "path": repo_relative(path),
                "label": spec["label"],
                "generation_type": spec["generation_type"],
                "sample_rate_hz": int(sample_rate),
                "duration_sec": round(float(duration_sec), 6),
                "parameters": params,
                "disclaimer": disclaimer,
            }
        )

    write_jsonl(manifest_path, rows)
    _write_report(report_path, rows)
    return rows


def _write_report(report_path: Path, rows: list[dict[str, Any]]) -> None:
    label_counts = count_by(rows, "label")
    type_counts = count_by(rows, "generation_type")
    lines = [
        "# Hydrophone Synthetic Wave Report",
        "",
        f"Generated: {utc_now_iso()}",
        "",
        "## Safety Note",
        "",
        f"- {SUBLIKE_DISCLAIMER}",
        "- These files are procedural fixtures for SubSim development and should not be described as real platform signatures.",
        "",
        "## Counts by label",
        "",
    ]
    for label, count in label_counts.items():
        lines.append(f"- `{label}`: {count}")
    lines.extend(["", "## Counts by generation type", ""])
    for generation_type, count in type_counts.items():
        lines.append(f"- `{generation_type}`: {count}")
    lines.extend(
        [
            "",
            "## Output",
            "",
            "- Waves: `data/hydrophone/synthetic/waves/`",
            "- Manifest: `data/hydrophone/synthetic/manifest.jsonl`",
        ]
    )
    write_text(report_path, "\n".join(lines))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate synthetic hydrophone/contact-like WAV files.")
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--report-root", default=str(DEFAULT_REPORT_ROOT))
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--duration-sec", type=float, default=10.0)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--waves-dir", default=None)
    parser.add_argument("--manifest-path", default=None)
    parser.add_argument("--report-path", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.count < 0:
        parser.error("--count must be non-negative")
    if args.sample_rate <= 0:
        parser.error("--sample-rate must be positive")
    if args.duration_sec <= 0:
        parser.error("--duration-sec must be positive")

    data_root = Path(args.data_root)
    report_root = Path(args.report_root)
    ensure_hydrophone_layout(data_root, report_root)
    waves_dir = Path(args.waves_dir) if args.waves_dir else data_root / "synthetic" / "waves"
    manifest_path = Path(args.manifest_path) if args.manifest_path else data_root / "synthetic" / "manifest.jsonl"
    report_path = Path(args.report_path) if args.report_path else report_root / "synthetic_wave_report.md"

    rows = generate_synthetic_dataset(
        count=args.count,
        sample_rate=args.sample_rate,
        duration_sec=args.duration_sec,
        waves_dir=waves_dir,
        manifest_path=manifest_path,
        report_path=report_path,
        seed=args.seed,
    )
    print(f"hydrophone synthetic generation complete: waves={len(rows)} manifest={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
