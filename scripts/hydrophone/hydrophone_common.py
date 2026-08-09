#!/usr/bin/env python3
"""Shared helpers for the bounded SubSim hydrophone pipeline."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import wave
from pathlib import Path
from typing import Any, Iterable

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_ROOT = REPO_ROOT / "data" / "hydrophone"
DEFAULT_REPORT_ROOT = REPO_ROOT / "reports" / "hydrophone"

ALLOWED_LABELS = {
    "surface_vessel",
    "biologic_mammal",
    "biologic_fish",
    "ambient_ocean",
    "synthetic_submarine_like",
    "unknown_or_noise",
}

SUPPORTED_AUDIO_SUFFIXES = {".wav", ".flac", ".ogg", ".aiff", ".aif", ".mp3"}


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def ensure_hydrophone_layout(data_root: Path = DEFAULT_DATA_ROOT, report_root: Path = DEFAULT_REPORT_ROOT) -> None:
    for rel in [
        "raw_samples",
        "normalized",
        "manifests",
        "features",
        "synthetic/waves",
    ]:
        ensure_dir(data_root / rel)
    ensure_dir(report_root)


def repo_relative(path: Path) -> str:
    path = path.resolve()
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_repo_path(path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def stable_id(prefix: str, *parts: object, n: int = 12) -> str:
    payload = "||".join(str(part) for part in parts)
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:n]
    return f"{prefix}_{digest}"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSONL row: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{lineno}: expected JSON object")
            rows.append(row)
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=False))
            fh.write("\n")
    tmp.replace(path)


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def read_audio(path: Path) -> tuple[np.ndarray, int]:
    """Read supported audio into mono float32 samples in [-1, 1] where possible."""
    try:
        import soundfile as sf

        samples, sample_rate = sf.read(path, dtype="float32", always_2d=False)
    except Exception as sf_exc:  # noqa: BLE001
        if path.suffix.lower() != ".wav":
            raise RuntimeError(f"Could not read {path} with soundfile: {sf_exc}") from sf_exc
        try:
            with wave.open(str(path), "rb") as wav:
                sample_rate = wav.getframerate()
                channels = wav.getnchannels()
                width = wav.getsampwidth()
                frames = wav.readframes(wav.getnframes())
        except Exception as wav_exc:  # noqa: BLE001
            raise RuntimeError(f"Could not read WAV {path}: {wav_exc}") from wav_exc

        if width == 1:
            data = np.frombuffer(frames, dtype=np.uint8).astype(np.float32)
            samples = (data - 128.0) / 128.0
        elif width == 2:
            samples = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
        elif width == 4:
            samples = np.frombuffer(frames, dtype="<i4").astype(np.float32) / 2147483648.0
        else:
            raise RuntimeError(f"Unsupported WAV sample width {width} for {path}")
        if channels > 1:
            samples = samples.reshape(-1, channels).mean(axis=1)

    samples = np.asarray(samples, dtype=np.float32)
    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    samples = np.nan_to_num(samples, copy=False)
    return samples.astype(np.float32, copy=False), int(sample_rate)


def write_wav(path: Path, samples: np.ndarray, sample_rate: int) -> None:
    ensure_dir(path.parent)
    samples = np.asarray(samples, dtype=np.float32)
    samples = np.nan_to_num(samples, copy=False)
    samples = np.clip(samples, -1.0, 1.0)
    try:
        import soundfile as sf

        sf.write(path, samples, sample_rate, subtype="PCM_16")
        return
    except Exception:
        pass

    pcm = (samples * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())


def read_wav_info(path: Path) -> tuple[int, float]:
    try:
        import soundfile as sf

        info = sf.info(path)
        return int(info.samplerate), float(info.frames) / float(info.samplerate)
    except Exception:
        with wave.open(str(path), "rb") as wav:
            sr = wav.getframerate()
            return int(sr), float(wav.getnframes()) / float(sr)


def resample_audio(samples: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate == target_rate:
        return samples.astype(np.float32, copy=False)
    if len(samples) == 0:
        return samples.astype(np.float32, copy=False)
    try:
        from scipy import signal

        gcd = math.gcd(int(source_rate), int(target_rate))
        up = int(target_rate) // gcd
        down = int(source_rate) // gcd
        return signal.resample_poly(samples, up, down).astype(np.float32)
    except Exception:
        old_x = np.linspace(0.0, 1.0, num=len(samples), endpoint=False)
        new_len = max(1, int(round(len(samples) * target_rate / source_rate)))
        new_x = np.linspace(0.0, 1.0, num=new_len, endpoint=False)
        return np.interp(new_x, old_x, samples).astype(np.float32)


def conservative_normalize(samples: np.ndarray) -> np.ndarray:
    samples = np.asarray(samples, dtype=np.float32)
    if len(samples) == 0:
        return samples
    samples = np.nan_to_num(samples, copy=False)
    samples = samples - float(np.mean(samples))
    peak = float(np.max(np.abs(samples))) if len(samples) else 0.0
    if peak < 1e-9:
        return np.zeros_like(samples, dtype=np.float32)
    if peak > 0.8:
        samples = samples * (0.8 / peak)
    elif peak < 0.05:
        samples = samples * min(4.0, 0.2 / peak)
    return np.clip(samples, -0.95, 0.95).astype(np.float32)


def segment_audio(
    samples: np.ndarray,
    sample_rate: int,
    *,
    window_sec: float,
    max_segments: int | None = None,
    pad_short: bool = True,
) -> list[np.ndarray]:
    if window_sec <= 0:
        raise ValueError("window_sec must be positive")
    window = max(1, int(round(window_sec * sample_rate)))
    if len(samples) <= window:
        if pad_short and len(samples) < window:
            padded = np.zeros(window, dtype=np.float32)
            padded[: len(samples)] = samples
            return [padded]
        return [samples.astype(np.float32, copy=False)]

    segments: list[np.ndarray] = []
    for start in range(0, len(samples) - window + 1, window):
        segments.append(samples[start : start + window].astype(np.float32, copy=False))
        if max_segments is not None and len(segments) >= max_segments:
            break
    return segments


def infer_dataset_id_from_path(path: Path, raw_root: Path) -> str:
    try:
        return path.relative_to(raw_root).parts[0]
    except Exception:
        return "unknown"


def count_by(rows: Iterable[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))
