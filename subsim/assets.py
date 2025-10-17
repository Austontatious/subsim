"""Procedural asset synthesis and management."""
from __future__ import annotations

import math
import random
import wave
from array import array
from pathlib import Path
from typing import Dict

from .config import ASSET_DIR, ASSET_NAMES, ASSET_VARIANTS, AUDIO_SAMPLE_RATE

_RNG = random.Random(0xC0FFEE)


def _sine(freq: float, duration: float, amp: float = 0.4) -> array:
    samples = int(duration * AUDIO_SAMPLE_RATE)
    buf = array("f")
    step = 1.0 / AUDIO_SAMPLE_RATE
    phase = 0.0
    for _ in range(samples):
        buf.append(amp * math.sin(phase))
        phase += 2.0 * math.pi * freq * step
    return buf


def _motor(freq: float, duration: float, wobble: float = 0.15) -> array:
    samples = int(duration * AUDIO_SAMPLE_RATE)
    buf = array("f")
    step = 1.0 / AUDIO_SAMPLE_RATE
    phase = 0.0
    wobble_phase = 0.0
    wobble_speed = 2.0 * math.pi * 1.1
    for _ in range(samples):
        modulation = 1.0 + wobble * math.sin(wobble_phase)
        buf.append(0.35 * math.sin(phase) * modulation)
        phase += 2.0 * math.pi * freq * step
        wobble_phase += wobble_speed * step
    return buf


def _noise(duration: float) -> array:
    samples = int(duration * AUDIO_SAMPLE_RATE)
    buf = array("f")
    for _ in range(samples):
        buf.append(_RNG.uniform(-0.5, 0.5))
    return buf


def _low_pass(data: array, cutoff: float) -> array:
    if cutoff <= 0.0:
        return array("f", [0.0] * len(data))
    dt = 1.0 / AUDIO_SAMPLE_RATE
    rc = 1.0 / (2.0 * math.pi * cutoff)
    alpha = dt / (rc + dt)
    out = array("f", data)
    prev = out[0] if out else 0.0
    for i in range(len(out)):
        prev = prev + alpha * (out[i] - prev)
        out[i] = prev
    return out


def _write_wav(path: Path, data: array) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = array("h", (int(max(-1.0, min(1.0, sample)) * 32767) for sample in data))
    with wave.open(path.as_posix(), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(AUDIO_SAMPLE_RATE)
        wav_file.writeframes(pcm.tobytes())


def _synth_asset(name: str) -> array:
    meta = ASSET_NAMES[name]
    freq = meta["freq"]
    duration = meta["duration"]
    if name in {"player_hum", "merchant", "hunter"}:
        return _motor(freq, duration)
    if name == "ping":
        return _sine(freq, duration, amp=0.7)
    if name in {"torpedo", "mine"}:
        base = _sine(freq, duration, amp=0.5)
        noise = _noise(duration)
        return array("f", (0.7 * b + 0.3 * n for b, n in zip(base, noise)))
    return _sine(freq, duration)


def ensure_assets(path: Path | str | None = None) -> Dict[str, Dict[str, Path]]:
    asset_dir = Path(path) if path is not None else ASSET_DIR
    asset_dir.mkdir(parents=True, exist_ok=True)
    outputs: Dict[str, Dict[str, Path]] = {}

    cutoff_hz = {
        "clean": 20000.0,
        "lp1": 2400.0,
        "lp2": 1200.0,
        "lp3": 600.0,
    }

    for name in ASSET_NAMES:
        base_data = _synth_asset(name)
        variants: Dict[str, Path] = {}
        for variant in ASSET_VARIANTS:
            filename = asset_dir / f"{name}_{variant}.wav"
            if not filename.exists() or filename.stat().st_size == 0:
                data = base_data if variant == "clean" else _low_pass(base_data, cutoff_hz[variant])
                _write_wav(filename, data)
            variants[variant] = filename
        outputs[name] = variants
    return outputs


__all__ = ["ensure_assets"]
