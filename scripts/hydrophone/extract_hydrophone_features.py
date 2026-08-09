#!/usr/bin/env python3
"""Extract simple baseline acoustic features for normalized hydrophone clips."""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hydrophone_common import (  # noqa: E402
    DEFAULT_DATA_ROOT,
    DEFAULT_REPORT_ROOT,
    ensure_dir,
    ensure_hydrophone_layout,
    read_audio,
    read_jsonl,
    resolve_repo_path,
)


N_FFT = 1024
HOP_LENGTH = 512
N_MELS = 32
N_MFCC = 13


def feature_columns() -> list[str]:
    cols = [
        "clip_id",
        "dataset_id",
        "label",
        "group_id",
        "source_path",
        "normalized_path",
        "duration_sec",
        "sample_rate_hz",
        "rms_energy",
        "zero_crossing_rate",
        "spectral_centroid_hz",
        "spectral_bandwidth_hz",
        "spectral_rolloff_hz",
        "dominant_frequency_hz",
        "spectral_flatness",
        "mel_mean",
        "mel_std",
        "mel_min",
        "mel_max",
    ]
    for i in range(1, N_MFCC + 1):
        cols.append(f"mfcc_{i:02d}_mean")
        cols.append(f"mfcc_{i:02d}_std")
    return cols


def _frames(samples: np.ndarray, frame_size: int = N_FFT, hop: int = HOP_LENGTH) -> np.ndarray:
    samples = np.asarray(samples, dtype=np.float32)
    if len(samples) < frame_size:
        padded = np.zeros(frame_size, dtype=np.float32)
        padded[: len(samples)] = samples
        return padded.reshape(1, frame_size)
    starts = range(0, len(samples) - frame_size + 1, hop)
    return np.stack([samples[start : start + frame_size] for start in starts]).astype(np.float32)


def _hz_to_mel(freq_hz: np.ndarray) -> np.ndarray:
    return 2595.0 * np.log10(1.0 + freq_hz / 700.0)


def _mel_to_hz(mels: np.ndarray) -> np.ndarray:
    return 700.0 * (10.0 ** (mels / 2595.0) - 1.0)


def _mel_filterbank(sample_rate: int, n_fft: int = N_FFT, n_mels: int = N_MELS) -> np.ndarray:
    max_freq = sample_rate / 2.0
    mel_points = np.linspace(_hz_to_mel(np.array([0.0]))[0], _hz_to_mel(np.array([max_freq]))[0], n_mels + 2)
    hz_points = _mel_to_hz(mel_points)
    bins = np.floor((n_fft + 1) * hz_points / sample_rate).astype(int)
    bins = np.clip(bins, 0, n_fft // 2)
    filters = np.zeros((n_mels, n_fft // 2 + 1), dtype=np.float32)
    for i in range(1, n_mels + 1):
        left, center, right = int(bins[i - 1]), int(bins[i]), int(bins[i + 1])
        if center <= left:
            center = min(left + 1, filters.shape[1] - 1)
        if right <= center:
            right = min(center + 1, filters.shape[1])
        for j in range(left, center):
            filters[i - 1, j] = (j - left) / max(1, center - left)
        for j in range(center, right):
            filters[i - 1, j] = (right - j) / max(1, right - center)
    return filters


def _dct_type_ii(values: np.ndarray, n_coeffs: int) -> np.ndarray:
    try:
        from scipy.fftpack import dct

        return dct(values, type=2, axis=1, norm="ortho")[:, :n_coeffs]
    except Exception:
        n = values.shape[1]
        k = np.arange(n_coeffs).reshape(1, -1)
        idx = np.arange(n).reshape(-1, 1)
        basis = np.cos(math.pi / n * (idx + 0.5) @ k)
        return values @ basis


def extract_feature_row(samples: np.ndarray, sample_rate: int, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    metadata = metadata or {}
    samples = np.asarray(samples, dtype=np.float32)
    samples = np.nan_to_num(samples, copy=False)
    if len(samples) == 0:
        samples = np.zeros(1, dtype=np.float32)

    rms = float(np.sqrt(np.mean(samples * samples)))
    signs = np.signbit(samples)
    zcr = float(np.mean(signs[1:] != signs[:-1])) if len(samples) > 1 else 0.0

    frames = _frames(samples)
    window = np.hanning(frames.shape[1]).astype(np.float32)
    spectra = np.fft.rfft(frames * window, axis=1)
    power = np.abs(spectra) ** 2
    mag = np.sqrt(power + 1e-12)
    mean_mag = np.mean(mag, axis=0)
    freqs = np.fft.rfftfreq(N_FFT, d=1.0 / float(sample_rate))
    weight_sum = float(np.sum(mean_mag)) + 1e-12

    centroid = float(np.sum(freqs * mean_mag) / weight_sum)
    bandwidth = float(np.sqrt(np.sum(((freqs - centroid) ** 2) * mean_mag) / weight_sum))
    cumulative = np.cumsum(mean_mag)
    rolloff_idx = int(np.searchsorted(cumulative, cumulative[-1] * 0.85)) if cumulative[-1] > 0 else 0
    rolloff = float(freqs[min(rolloff_idx, len(freqs) - 1)])
    if len(mean_mag) > 1:
        dominant_idx = int(np.argmax(mean_mag[1:]) + 1)
    else:
        dominant_idx = 0
    dominant = float(freqs[dominant_idx])
    flatness = float(np.exp(np.mean(np.log(mean_mag + 1e-12))) / (np.mean(mean_mag) + 1e-12))

    filters = _mel_filterbank(sample_rate)
    mel = power @ filters.T
    log_mel = np.log(mel + 1e-9)
    mfcc = _dct_type_ii(log_mel, N_MFCC)

    row: dict[str, Any] = {
        "clip_id": metadata.get("clip_id", ""),
        "dataset_id": metadata.get("dataset_id", ""),
        "label": metadata.get("label", ""),
        "group_id": metadata.get("group_id", ""),
        "source_path": metadata.get("source_path", ""),
        "normalized_path": metadata.get("normalized_path", ""),
        "duration_sec": float(metadata.get("duration_sec") or len(samples) / float(sample_rate)),
        "sample_rate_hz": int(metadata.get("sample_rate_hz") or sample_rate),
        "rms_energy": rms,
        "zero_crossing_rate": zcr,
        "spectral_centroid_hz": centroid,
        "spectral_bandwidth_hz": bandwidth,
        "spectral_rolloff_hz": rolloff,
        "dominant_frequency_hz": dominant,
        "spectral_flatness": flatness,
        "mel_mean": float(np.mean(log_mel)),
        "mel_std": float(np.std(log_mel)),
        "mel_min": float(np.min(log_mel)),
        "mel_max": float(np.max(log_mel)),
    }
    mfcc_mean = np.mean(mfcc, axis=0)
    mfcc_std = np.std(mfcc, axis=0)
    for i in range(N_MFCC):
        row[f"mfcc_{i + 1:02d}_mean"] = float(mfcc_mean[i])
        row[f"mfcc_{i + 1:02d}_std"] = float(mfcc_std[i])

    for key, value in list(row.items()):
        if isinstance(value, float) and not math.isfinite(value):
            row[key] = 0.0
    return row


def extract_features_from_manifest(clips_manifest: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for clip in read_jsonl(clips_manifest):
        normalized = str(clip.get("normalized_path") or "")
        if not normalized:
            continue
        path = resolve_repo_path(normalized)
        if not path.exists():
            continue
        samples, sample_rate = read_audio(path)
        rows.append(extract_feature_row(samples, sample_rate, clip))
    return rows


def write_features(rows: list[dict[str, Any]], features_dir: Path, output_format: str = "auto") -> Path:
    ensure_dir(features_dir)
    columns = feature_columns()
    normalized_rows = [{col: row.get(col, "") for col in columns} for row in rows]

    if output_format in {"auto", "parquet"}:
        try:
            import pandas as pd

            df = pd.DataFrame(normalized_rows, columns=columns)
            out = features_dir / "features.parquet"
            df.to_parquet(out, index=False)
            return out
        except Exception:
            if output_format == "parquet":
                raise

    out = features_dir / "features.csv"
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(normalized_rows)
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract baseline hydrophone acoustic features.")
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--report-root", default=str(DEFAULT_REPORT_ROOT))
    parser.add_argument("--clips-manifest", default=None)
    parser.add_argument("--features-dir", default=None)
    parser.add_argument("--output-format", choices=["auto", "parquet", "csv"], default="auto")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    data_root = Path(args.data_root)
    report_root = Path(args.report_root)
    ensure_hydrophone_layout(data_root, report_root)
    clips_manifest = Path(args.clips_manifest) if args.clips_manifest else data_root / "manifests" / "clips.jsonl"
    features_dir = Path(args.features_dir) if args.features_dir else data_root / "features"

    rows = extract_features_from_manifest(clips_manifest)
    out = write_features(rows, features_dir, args.output_format)
    print(f"hydrophone features complete: rows={len(rows)} output={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
