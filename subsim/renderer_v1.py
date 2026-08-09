"""First-pass hybrid acoustic renderer driven by renderer_params_v1."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import random
import struct
import wave
from array import array
from pathlib import Path
from typing import Any

from .config import AUDIO_SAMPLE_RATE


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _normalize(signal: list[float], peak: float = 0.95) -> list[float]:
    if not signal:
        return signal
    m = max(abs(v) for v in signal)
    if m <= 1e-9:
        return signal
    if m <= peak:
        return signal
    scale = peak / m
    return [v * scale for v in signal]


def _mix_in(dst: list[float], src: list[float], gain: float = 1.0, offset: int = 0) -> None:
    if gain == 0.0:
        return
    start = max(0, offset)
    for i, v in enumerate(src):
        j = start + i
        if j >= len(dst):
            break
        dst[j] += gain * v


def _one_pole_low_pass(samples: list[float], cutoff_hz: float, sr: int) -> list[float]:
    if not samples:
        return []
    cutoff_hz = _clamp(cutoff_hz, 5.0, sr * 0.48)
    dt = 1.0 / sr
    rc = 1.0 / (2.0 * math.pi * cutoff_hz)
    alpha = dt / (rc + dt)
    out = [0.0] * len(samples)
    prev = samples[0]
    for i, x in enumerate(samples):
        prev = prev + alpha * (x - prev)
        out[i] = prev
    return out


def _one_pole_high_pass(samples: list[float], cutoff_hz: float, sr: int) -> list[float]:
    if not samples:
        return []
    cutoff_hz = _clamp(cutoff_hz, 5.0, sr * 0.48)
    dt = 1.0 / sr
    rc = 1.0 / (2.0 * math.pi * cutoff_hz)
    alpha = rc / (rc + dt)
    out = [0.0] * len(samples)
    prev_y = 0.0
    prev_x = samples[0]
    for i, x in enumerate(samples):
        y = alpha * (prev_y + x - prev_x)
        out[i] = y
        prev_y = y
        prev_x = x
    return out


def _write_wav_mono(path: Path, samples: list[float], sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = [max(-1.0, min(1.0, v)) for v in samples]
    pcm = array("h", (int(v * 32767) for v in clipped))
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())


def pcm16_sha1(samples: list[float]) -> str:
    pcm = array("h", (int(max(-1.0, min(1.0, v)) * 32767) for v in samples))
    return hashlib.sha1(pcm.tobytes()).hexdigest()


class HybridAcousticRendererV1:
    """Renderer for first-pass high-value underwater acoustic families."""

    def __init__(self, params: dict[str, Any], sample_rate: int | None = None) -> None:
        self.params = params
        self.families: dict[str, Any] = dict(params.get("families", {}))
        configured_sr = int(params.get("global", {}).get("default_sample_rate_hz", AUDIO_SAMPLE_RATE))
        self.sample_rate = int(sample_rate or configured_sr)

    @classmethod
    def from_json(cls, path: Path | str, *, sample_rate: int | None = None) -> "HybridAcousticRendererV1":
        p = Path(path)
        params = json.loads(p.read_text(encoding="utf-8"))
        return cls(params=params, sample_rate=sample_rate)

    def supported_families(self) -> list[str]:
        return sorted(self.families.keys())

    def render_family(
        self,
        family: str,
        *,
        duration_s: float | None = None,
        seed: int = 0,
        variability: float = 0.35,
        intensity: float = 1.0,
        include_seed: bool = True,
        overrides: dict[str, float] | None = None,
    ) -> tuple[list[float], dict[str, Any]]:
        if family not in self.families:
            raise ValueError(f"Unsupported family: {family}")

        family_cfg = self.families[family]
        derived = dict(family_cfg.get("derived_parameters", {}))
        if overrides:
            for key, value in overrides.items():
                derived[key] = value

        duration = float(duration_s or family_cfg.get("default_duration_s", 6.0))
        duration = _clamp(duration, 0.6, 20.0)
        variability = _clamp(variability, 0.0, 1.0)
        intensity = _clamp(intensity, 0.2, 1.6)

        rng = random.Random(int(seed))

        if family == "ambient_soundscape":
            samples, render_params = self._render_ambient_soundscape(duration, rng, variability, intensity, derived)
        elif family == "marine_mammal_whale":
            samples, render_params = self._render_marine_mammal_whale(duration, rng, variability, intensity, derived)
        elif family == "marine_mammal_other":
            samples, render_params = self._render_marine_mammal_other(duration, rng, variability, intensity, derived)
        elif family == "surface_vessel":
            samples, render_params = self._render_surface_vessel(duration, rng, variability, intensity, derived)
        elif family == "intermittent_machinery_archetype":
            samples, render_params = self._render_intermittent_machinery(duration, rng, variability, intensity, derived)
        else:
            raise ValueError(f"No render implementation for family: {family}")

        used_seed_path = ""
        if include_seed:
            seed_mix = float(family_cfg.get("seed_mix", 0.0))
            if seed_mix > 0.0:
                seed_path = self._pick_seed_path(family_cfg, rng)
                if seed_path:
                    seed_signal = self._load_seed_wave(Path(seed_path), target_sr=self.sample_rate)
                    if seed_signal:
                        self._blend_seed(samples, seed_signal, seed_mix, rng)
                        used_seed_path = seed_path

        samples = _normalize(samples, peak=0.96)
        meta = {
            "renderer_version": "hybrid_renderer_v1",
            "generated_utc": _utc_now_iso(),
            "family": family,
            "synthesis_mode": family_cfg.get("synthesis_mode", "unknown"),
            "acoustic_contract_hook": family_cfg.get("acoustic_contract_hook", "unknown"),
            "duration_s": duration,
            "sample_rate_hz": self.sample_rate,
            "seed": int(seed),
            "variability": variability,
            "intensity": intensity,
            "seed_exemplar_used": used_seed_path,
            "render_params": render_params,
            "pcm_sha1": pcm16_sha1(samples),
        }
        return samples, meta

    def render_family_to_wav(
        self,
        output_path: Path | str,
        family: str,
        *,
        duration_s: float | None = None,
        seed: int = 0,
        variability: float = 0.35,
        intensity: float = 1.0,
        include_seed: bool = True,
        overrides: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        path = Path(output_path)
        samples, meta = self.render_family(
            family,
            duration_s=duration_s,
            seed=seed,
            variability=variability,
            intensity=intensity,
            include_seed=include_seed,
            overrides=overrides,
        )
        _write_wav_mono(path, samples, self.sample_rate)
        meta["output_path"] = str(path.resolve())
        meta["output_size_bytes"] = path.stat().st_size
        return meta

    # -------------------------------------------------------------
    # Family renderers
    # -------------------------------------------------------------
    def _render_ambient_soundscape(
        self,
        duration_s: float,
        rng: random.Random,
        variability: float,
        intensity: float,
        params: dict[str, Any],
    ) -> tuple[list[float], dict[str, Any]]:
        n = int(duration_s * self.sample_rate)
        raw_noise = [rng.uniform(-1.0, 1.0) for _ in range(n)]

        centroid = float(params.get("bandwidth_tendency_hz", {}).get("median", 1200.0))
        cutoff = _clamp(centroid * (0.75 + 0.35 * variability), 180.0, 3200.0)
        low_noise = _one_pole_low_pass(raw_noise, cutoff, self.sample_rate)
        shimmer = _one_pole_high_pass(low_noise, _clamp(cutoff * 0.35, 40.0, 900.0), self.sample_rate)

        dominant = params.get("dominant_band_hz", {})
        base_freq = _clamp(float(dominant.get("mid", 70.0)), 35.0, 220.0)
        drift_freq = _clamp(base_freq * (1.6 + 0.4 * variability), 70.0, 420.0)

        out = [0.0] * n
        phase_a = rng.uniform(0.0, math.tau)
        phase_b = rng.uniform(0.0, math.tau)
        slow_mod_hz = _clamp(float(params.get("modulation_hz", {}).get("low", 0.06)), 0.02, 0.45)

        for i in range(n):
            t = i / self.sample_rate
            swell = 0.68 + 0.32 * math.sin(math.tau * slow_mod_hz * t + phase_a)
            tone = 0.16 * math.sin(math.tau * base_freq * t + phase_a)
            tone += 0.09 * math.sin(math.tau * drift_freq * t + phase_b)
            out[i] = (0.60 * low_noise[i] + 0.24 * shimmer[i] + tone) * swell * intensity

        return out, {
            "cutoff_hz": cutoff,
            "base_freq_hz": base_freq,
            "drift_freq_hz": drift_freq,
            "slow_mod_hz": slow_mod_hz,
        }

    def _render_marine_mammal_whale(
        self,
        duration_s: float,
        rng: random.Random,
        variability: float,
        intensity: float,
        params: dict[str, Any],
    ) -> tuple[list[float], dict[str, Any]]:
        n = int(duration_s * self.sample_rate)
        out = [0.0] * n

        dominant = params.get("dominant_band_hz", {})
        f_mid = _clamp(float(dominant.get("mid", 180.0)), 70.0, 450.0)
        cadence = params.get("event_cadence_s", {})
        phrase_interval = _clamp(float(cadence.get("slow", 1.6)), 0.8, 3.2)

        events = 0
        t0 = rng.uniform(0.0, 0.35)
        while t0 < duration_s:
            call_dur = _clamp(rng.uniform(0.35, 1.1) * (1.0 + 0.2 * variability), 0.25, 1.4)
            start_hz = _clamp(f_mid * rng.uniform(0.72, 1.28), 60.0, 560.0)
            end_hz = _clamp(start_hz * rng.uniform(0.65, 1.35), 50.0, 620.0)
            amp = 0.34 * intensity * rng.uniform(0.85, 1.15)

            i_start = int(t0 * self.sample_rate)
            i_end = min(n, i_start + int(call_dur * self.sample_rate))
            phase = rng.uniform(0.0, math.tau)
            for i in range(i_start, i_end):
                x = (i - i_start) / max(1, (i_end - i_start - 1))
                env = math.sin(math.pi * x) ** 1.6
                f = _lerp(start_hz, end_hz, x)
                phase += math.tau * f / self.sample_rate
                sample = math.sin(phase)
                sample += 0.25 * math.sin(phase * 1.98)
                sample += 0.10 * math.sin(phase * 2.95)
                out[i] += amp * env * sample

            events += 1
            t0 += phrase_interval * rng.uniform(0.72, 1.25)

        return out, {
            "call_events": events,
            "center_freq_hz": f_mid,
            "phrase_interval_s": phrase_interval,
        }

    def _render_marine_mammal_other(
        self,
        duration_s: float,
        rng: random.Random,
        variability: float,
        intensity: float,
        params: dict[str, Any],
    ) -> tuple[list[float], dict[str, Any]]:
        n = int(duration_s * self.sample_rate)
        out = [0.0] * n

        dominant = params.get("dominant_band_hz", {})
        f_mid = _clamp(float(dominant.get("mid", 3200.0)), 250.0, 11000.0)
        cadence = params.get("event_cadence_s", {})
        burst_interval = _clamp(float(cadence.get("median", 0.45)), 0.18, 1.1)

        bursts = 0
        cursor = rng.uniform(0.0, 0.22)
        while cursor < duration_s:
            click_count = int(rng.uniform(3, 9) * (1.0 + 0.45 * variability))
            click_count = max(2, min(14, click_count))
            intra_gap = rng.uniform(0.018, 0.075)
            base_amp = 0.35 * intensity * rng.uniform(0.85, 1.25)

            for click_idx in range(click_count):
                t_event = cursor + click_idx * intra_gap
                if t_event >= duration_s:
                    break
                freq = _clamp(f_mid * rng.uniform(0.45, 1.65), 500.0, 12000.0)
                dur = rng.uniform(0.010, 0.055)
                i_start = int(t_event * self.sample_rate)
                i_end = min(n, i_start + int(dur * self.sample_rate))
                phase = rng.uniform(0.0, math.tau)
                for i in range(i_start, i_end):
                    x = (i - i_start) / max(1, (i_end - i_start - 1))
                    env = math.exp(-5.5 * x)
                    phase += math.tau * freq / self.sample_rate
                    out[i] += base_amp * env * math.sin(phase)

            bursts += 1
            cursor += burst_interval * rng.uniform(0.75, 1.35)

        return out, {
            "burst_events": bursts,
            "center_freq_hz": f_mid,
            "burst_interval_s": burst_interval,
        }

    def _render_surface_vessel(
        self,
        duration_s: float,
        rng: random.Random,
        variability: float,
        intensity: float,
        params: dict[str, Any],
    ) -> tuple[list[float], dict[str, Any]]:
        n = int(duration_s * self.sample_rate)
        out = [0.0] * n

        dominant = params.get("dominant_band_hz", {})
        fundamental = _clamp(float(dominant.get("mid", 175.0)), 35.0, 420.0)
        mod = params.get("modulation_hz", {})
        wobble_hz = _clamp(float(mod.get("median", 2.2)), 0.2, 9.0)

        phase = rng.uniform(0.0, math.tau)
        for i in range(n):
            t = i / self.sample_rate
            wobble = 1.0 + (0.06 + 0.15 * variability) * math.sin(math.tau * wobble_hz * t)
            f = fundamental * wobble
            phase += math.tau * f / self.sample_rate
            base = math.sin(phase)
            harmonics = 0.52 * math.sin(phase * 2.0) + 0.23 * math.sin(phase * 3.0)
            out[i] = (0.42 * base + 0.20 * harmonics) * intensity

        white = [rng.uniform(-1.0, 1.0) for _ in range(n)]
        cavitation = _one_pole_high_pass(_one_pole_low_pass(white, 5200.0, self.sample_rate), 280.0, self.sample_rate)
        cav_gain = 0.08 + 0.16 * variability
        for i in range(n):
            out[i] += cavitation[i] * cav_gain

        return out, {
            "fundamental_hz": fundamental,
            "wobble_hz": wobble_hz,
            "cavitation_mix": cav_gain,
        }

    def _render_intermittent_machinery(
        self,
        duration_s: float,
        rng: random.Random,
        variability: float,
        intensity: float,
        params: dict[str, Any],
    ) -> tuple[list[float], dict[str, Any]]:
        n = int(duration_s * self.sample_rate)
        out = [0.0] * n

        dominant = params.get("dominant_band_hz", {})
        base_hz = _clamp(float(dominant.get("mid", 140.0)), 45.0, 360.0)

        # quiet floor hum
        phase = rng.uniform(0.0, math.tau)
        for i in range(n):
            phase += math.tau * base_hz / self.sample_rate
            out[i] += 0.12 * intensity * math.sin(phase)

        # sparse intermittent events
        cadence = params.get("event_cadence_s", {})
        interval = _clamp(float(cadence.get("slow", 1.3)), 0.5, 3.5)
        cursor = rng.uniform(0.15, 0.75)
        events = 0
        while cursor < duration_s:
            event_dur = rng.uniform(0.09, 0.55)
            i_start = int(cursor * self.sample_rate)
            i_end = min(n, i_start + int(event_dur * self.sample_rate))
            freq = _clamp(base_hz * rng.uniform(0.75, 2.6), 55.0, 900.0)
            phase = rng.uniform(0.0, math.tau)
            for i in range(i_start, i_end):
                x = (i - i_start) / max(1, (i_end - i_start))
                env = math.exp(-3.0 * x)
                phase += math.tau * freq / self.sample_rate
                out[i] += 0.35 * intensity * env * math.sin(phase)

            # transient tap/noise accent
            burst_len = int(self.sample_rate * rng.uniform(0.01, 0.04))
            b0 = max(0, i_start - burst_len // 3)
            for i in range(b0, min(n, b0 + burst_len)):
                x = (i - b0) / max(1, burst_len)
                out[i] += rng.uniform(-1.0, 1.0) * (0.12 * (1.0 - x))

            events += 1
            cursor += interval * rng.uniform(0.7, 1.5)

        return out, {
            "base_hz": base_hz,
            "event_interval_s": interval,
            "events": events,
        }

    # -------------------------------------------------------------
    # Seed handling
    # -------------------------------------------------------------
    def _pick_seed_path(self, family_cfg: dict[str, Any], rng: random.Random) -> str:
        seeds = list(family_cfg.get("seed_exemplars", []))
        if not seeds:
            return ""
        candidates = [s for s in seeds if Path(str(s.get("file_path", ""))).exists()]
        if not candidates:
            return ""
        pick = rng.choice(candidates)
        return str(pick.get("file_path") or "")

    def _blend_seed(self, signal: list[float], seed_signal: list[float], seed_mix: float, rng: random.Random) -> None:
        if not signal or not seed_signal:
            return
        seed_mix = _clamp(seed_mix, 0.01, 0.45)

        if len(seed_signal) > len(signal):
            start = rng.randint(0, len(seed_signal) - len(signal))
            seed_crop = seed_signal[start : start + len(signal)]
        elif len(seed_signal) < len(signal):
            repeats = (len(signal) // len(seed_signal)) + 1
            seed_crop = (seed_signal * repeats)[: len(signal)]
        else:
            seed_crop = seed_signal

        for i in range(len(signal)):
            signal[i] = (1.0 - seed_mix) * signal[i] + seed_mix * seed_crop[i]

    def _load_seed_wave(self, path: Path, *, target_sr: int) -> list[float]:
        if not path.exists():
            return []

        try:
            with wave.open(str(path), "rb") as wf:
                channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                src_sr = wf.getframerate()
                nframes = wf.getnframes()
                raw = wf.readframes(nframes)
        except Exception:  # noqa: BLE001
            return []

        decoded = self._decode_pcm(raw, sampwidth)
        if channels > 1:
            mono: list[float] = []
            for i in range(0, len(decoded), channels):
                frame = decoded[i : i + channels]
                if frame:
                    mono.append(sum(frame) / len(frame))
            decoded = mono

        if src_sr != target_sr and decoded:
            decoded = self._resample_linear(decoded, src_sr=src_sr, dst_sr=target_sr)

        max_samples = target_sr * 12
        if len(decoded) > max_samples:
            decoded = decoded[:max_samples]

        return decoded

    def _decode_pcm(self, raw: bytes, sampwidth: int) -> list[float]:
        if sampwidth == 1:
            return [((b - 128) / 128.0) for b in raw]

        out: list[float] = []
        if sampwidth == 2:
            for i in range(0, len(raw), 2):
                if i + 2 > len(raw):
                    break
                v = struct.unpack_from("<h", raw, i)[0]
                out.append(v / 32768.0)
            return out

        if sampwidth == 3:
            for i in range(0, len(raw), 3):
                if i + 3 > len(raw):
                    break
                b0, b1, b2 = raw[i], raw[i + 1], raw[i + 2]
                val = b0 | (b1 << 8) | (b2 << 16)
                if val & 0x800000:
                    val -= 1 << 24
                out.append(val / 8388608.0)
            return out

        if sampwidth == 4:
            for i in range(0, len(raw), 4):
                if i + 4 > len(raw):
                    break
                val = struct.unpack_from("<i", raw, i)[0]
                out.append(val / 2147483648.0)
            return out

        return []

    def _resample_linear(self, samples: list[float], *, src_sr: int, dst_sr: int) -> list[float]:
        if src_sr <= 0 or dst_sr <= 0 or not samples:
            return samples
        if src_sr == dst_sr:
            return samples

        new_len = max(1, int(round(len(samples) * dst_sr / src_sr)))
        out = [0.0] * new_len
        for i in range(new_len):
            pos = i * src_sr / dst_sr
            j0 = int(pos)
            j1 = min(j0 + 1, len(samples) - 1)
            frac = pos - j0
            out[i] = samples[j0] * (1.0 - frac) + samples[j1] * frac
        return out


__all__ = [
    "HybridAcousticRendererV1",
    "pcm16_sha1",
]
