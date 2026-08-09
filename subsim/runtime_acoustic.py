"""Runtime integration utilities for Hybrid Acoustic Renderer v1."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

from .acoustic_contract import AcousticFoundationState
from .config import AUDIO_SAMPLE_RATE, PACKAGE_ROOT
from .renderer_v1 import HybridAcousticRendererV1


REPO_ROOT = PACKAGE_ROOT.parent
DEFAULT_PRESET_PATH = PACKAGE_ROOT / "runtime_acoustic_presets_v1.json"
DEFAULT_RENDERER_PARAMS_PATH = REPO_ROOT / "dataset" / "hydrophone" / "renderer_params_v1.json"
DEFAULT_RENDERER_PARAMS_MD = REPO_ROOT / "dataset" / "hydrophone" / "renderer_params_v1.md"
DEFAULT_RENDER_CACHE_DIR = REPO_ROOT / "build" / "runtime_acoustic_cache"
DEFAULT_HYDRO_ROOT = REPO_ROOT / "dataset" / "hydrophone"

RUNTIME_FAMILIES = (
    "ambient_soundscape",
    "marine_mammal_whale",
    "marine_mammal_other",
    "surface_vessel",
    "intermittent_machinery_archetype",
)


FALLBACK_PRESET_PACK: dict[str, Any] = {
    "preset_pack_version": "runtime_acoustic_presets_v1",
    "default_preset": "medium_clutter",
    "presets": {
        "low_clutter": {
            "description": "Sparse ocean bed with lower clutter density for readability.",
            "global_mix_gain": 0.85,
            "foundation": {
                "ambient_multiplier": 0.9,
                "self_noise_multiplier": 0.88,
                "player_hum_multiplier": 0.9,
                "self_noise_masking_pressure": 0.8,
            },
            "families": {
                "ambient_soundscape": {"enabled": True, "intensity": 0.75, "variability": 0.24, "density": 0.7, "duration_s": 11.0},
                "marine_mammal_whale": {"enabled": True, "intensity": 0.62, "variability": 0.26, "density": 0.45, "duration_s": 8.0},
                "marine_mammal_other": {"enabled": True, "intensity": 0.58, "variability": 0.25, "density": 0.42, "duration_s": 6.5},
                "surface_vessel": {"enabled": True, "intensity": 0.65, "variability": 0.23, "density": 0.5, "duration_s": 8.0},
                "intermittent_machinery_archetype": {"enabled": True, "intensity": 0.48, "variability": 0.28, "density": 0.35, "duration_s": 8.0},
            },
        },
        "medium_clutter": {
            "description": "Balanced default clutter for normal tactical play.",
            "global_mix_gain": 1.0,
            "foundation": {
                "ambient_multiplier": 1.0,
                "self_noise_multiplier": 1.0,
                "player_hum_multiplier": 1.0,
                "self_noise_masking_pressure": 1.0,
            },
            "families": {
                "ambient_soundscape": {"enabled": True, "intensity": 0.95, "variability": 0.34, "density": 0.95, "duration_s": 10.0},
                "marine_mammal_whale": {"enabled": True, "intensity": 0.85, "variability": 0.33, "density": 0.75, "duration_s": 7.5},
                "marine_mammal_other": {"enabled": True, "intensity": 0.9, "variability": 0.35, "density": 0.82, "duration_s": 6.0},
                "surface_vessel": {"enabled": True, "intensity": 1.0, "variability": 0.31, "density": 0.92, "duration_s": 8.0},
                "intermittent_machinery_archetype": {"enabled": True, "intensity": 0.78, "variability": 0.36, "density": 0.72, "duration_s": 8.0},
            },
        },
        "high_clutter": {
            "description": "Dense and noisy field for stress tests and clutter-heavy scenarios.",
            "global_mix_gain": 1.14,
            "foundation": {
                "ambient_multiplier": 1.12,
                "self_noise_multiplier": 1.12,
                "player_hum_multiplier": 1.05,
                "self_noise_masking_pressure": 1.2,
            },
            "families": {
                "ambient_soundscape": {"enabled": True, "intensity": 1.1, "variability": 0.46, "density": 1.2, "duration_s": 10.0},
                "marine_mammal_whale": {"enabled": True, "intensity": 1.0, "variability": 0.45, "density": 1.02, "duration_s": 8.0},
                "marine_mammal_other": {"enabled": True, "intensity": 1.08, "variability": 0.52, "density": 1.16, "duration_s": 6.5},
                "surface_vessel": {"enabled": True, "intensity": 1.16, "variability": 0.48, "density": 1.26, "duration_s": 8.0},
                "intermittent_machinery_archetype": {"enabled": True, "intensity": 1.0, "variability": 0.55, "density": 1.15, "duration_s": 8.0},
            },
        },
    },
}


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def load_runtime_acoustic_preset_pack(path: Path = DEFAULT_PRESET_PATH) -> dict[str, Any]:
    if path.exists():
        try:
            payload = _read_json(path)
            if isinstance(payload, dict) and isinstance(payload.get("presets"), dict):
                return payload
        except Exception:  # noqa: BLE001
            pass
    return FALLBACK_PRESET_PACK


def list_runtime_acoustic_presets(path: Path = DEFAULT_PRESET_PATH) -> list[str]:
    pack = load_runtime_acoustic_preset_pack(path)
    presets = pack.get("presets", {})
    return sorted(str(name) for name in presets.keys())


def resolve_runtime_acoustic_preset(
    preset_name: str | None,
    *,
    preset_path: Path = DEFAULT_PRESET_PATH,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    pack = load_runtime_acoustic_preset_pack(preset_path)
    presets = dict(pack.get("presets", {}))
    if not presets:
        presets = dict(FALLBACK_PRESET_PACK["presets"])
    default_name = str(pack.get("default_preset") or "medium_clutter")

    selected = str(preset_name or default_name)
    if selected not in presets:
        selected = default_name if default_name in presets else sorted(presets.keys())[0]
    return selected, dict(presets[selected]), pack


def _ensure_renderer_params(params_path: Path) -> bool:
    if params_path.exists():
        return True

    hydro_root = DEFAULT_HYDRO_ROOT
    if not hydro_root.exists():
        return False

    try:
        from .renderer_params_v1 import build_renderer_params_v1

        build_renderer_params_v1(
            hydro_root=hydro_root,
            output_json_path=params_path,
            output_md_path=DEFAULT_RENDERER_PARAMS_MD,
        )
        return params_path.exists()
    except Exception:  # noqa: BLE001
        return False


class RuntimeHybridLayerV1:
    """Manages renderer-backed runtime layers and preset-driven gain shaping."""

    def __init__(
        self,
        *,
        preset_name: str = "medium_clutter",
        runtime_seed: int = 0,
        sample_rate_hz: int = AUDIO_SAMPLE_RATE,
        preset_path: Path = DEFAULT_PRESET_PATH,
        params_path: Path = DEFAULT_RENDERER_PARAMS_PATH,
        cache_dir: Path = DEFAULT_RENDER_CACHE_DIR,
    ) -> None:
        self.runtime_seed = int(runtime_seed)
        self.sample_rate_hz = int(sample_rate_hz)
        self.preset_path = preset_path
        self.params_path = params_path
        self.cache_dir = cache_dir

        self.preset_name, self.preset, self.pack = resolve_runtime_acoustic_preset(
            preset_name,
            preset_path=preset_path,
        )
        self.enabled = False
        self.init_error = ""
        self.layer_specs: dict[str, dict[str, Any]] = {}
        self.last_layer_gains: dict[str, float] = {}
        self.last_foundation_profile: dict[str, float] = {}

        self.renderer: HybridAcousticRendererV1 | None = None
        self._initialize_renderer()

    def _initialize_renderer(self) -> None:
        if not _ensure_renderer_params(self.params_path):
            self.init_error = f"renderer params missing: {self.params_path}"
            return

        try:
            self.renderer = HybridAcousticRendererV1.from_json(
                self.params_path,
                sample_rate=self.sample_rate_hz,
            )
        except Exception as exc:  # noqa: BLE001
            self.init_error = f"renderer init failed: {type(exc).__name__}: {exc}"
            self.renderer = None
            return

        try:
            self._prepare_layer_specs()
        except Exception as exc:  # noqa: BLE001
            self.init_error = f"layer prep failed: {type(exc).__name__}: {exc}"
            self.layer_specs = {}
            self.enabled = False
            return

        self.enabled = bool(self.layer_specs)

    def _prepare_layer_specs(self) -> None:
        assert self.renderer is not None
        self.layer_specs = {}
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        family_preset_cfg = dict(self.preset.get("families", {}))
        params_families = set(self.renderer.supported_families())

        for idx, family in enumerate(RUNTIME_FAMILIES):
            if family not in params_families:
                continue

            cfg = dict(family_preset_cfg.get(family, {}))
            if not bool(cfg.get("enabled", True)):
                continue

            variability = _clamp(float(cfg.get("variability", 0.35)), 0.0, 1.0)
            intensity = _clamp(float(cfg.get("intensity", 1.0)), 0.2, 1.8)
            density = _clamp(float(cfg.get("density", 1.0)), 0.05, 2.0)
            duration_s = _clamp(float(cfg.get("duration_s", 8.0)), 1.0, 20.0)
            seed_offset = int(cfg.get("seed_offset", 0))
            render_seed = self.runtime_seed + ((idx + 1) * 1009) + seed_offset

            render_spec = {
                "family": family,
                "preset": self.preset_name,
                "render_seed": render_seed,
                "duration_s": round(duration_s, 6),
                "variability": round(variability, 6),
                "intensity": round(intensity, 6),
                "sample_rate_hz": self.sample_rate_hz,
                "params_mtime_ns": self.params_path.stat().st_mtime_ns,
            }
            digest = hashlib.sha1(json.dumps(render_spec, sort_keys=True).encode("utf-8")).hexdigest()[:12]
            out_dir = self.cache_dir / self.preset_name
            out_dir.mkdir(parents=True, exist_ok=True)
            wav_path = out_dir / f"{family}_{digest}.wav"

            if not wav_path.exists() or wav_path.stat().st_size <= 128:
                self.renderer.render_family_to_wav(
                    wav_path,
                    family,
                    duration_s=duration_s,
                    seed=render_seed,
                    variability=variability,
                    intensity=intensity,
                    include_seed=True,
                )

            layer_key = f"__hybrid_{family}__"
            self.layer_specs[layer_key] = {
                "family": family,
                "loop_key": layer_key,
                "wav_path": str(wav_path.resolve()),
                "density": density,
                "intensity": intensity,
                "variability": variability,
                "duration_s": duration_s,
                "seed": render_seed,
                "contract_hook": self.renderer.families.get(family, {}).get("acoustic_contract_hook", "unknown"),
                "synthesis_mode": self.renderer.families.get(family, {}).get("synthesis_mode", "unknown"),
            }

    def apply_foundation_profile(self, foundation: AcousticFoundationState) -> dict[str, float]:
        foundation_cfg = dict(self.preset.get("foundation", {}))
        ambient_mult = float(foundation_cfg.get("ambient_multiplier", 1.0))
        self_noise_mult = float(foundation_cfg.get("self_noise_multiplier", 1.0))
        hum_mult = float(foundation_cfg.get("player_hum_multiplier", 1.0))
        masking_pressure = float(foundation_cfg.get("self_noise_masking_pressure", 1.0))

        ambient_gain = _clamp(foundation.ambient_level * ambient_mult, 0.0, 1.0)
        self_noise_gain = _clamp(foundation.self_noise_level * 0.38 * self_noise_mult * masking_pressure, 0.0, 1.0)
        hum_gain = _clamp(foundation.player_hum_level * hum_mult, 0.0, 1.0)

        profile = {
            "ambient_gain": ambient_gain,
            "self_noise_gain": self_noise_gain,
            "hum_gain": hum_gain,
        }
        self.last_foundation_profile = profile
        return profile

    def compute_layer_gains(
        self,
        foundation: AcousticFoundationState,
        *,
        contact_count: int,
        active_ping_count: int = 0,
    ) -> dict[str, float]:
        if not self.enabled:
            self.last_layer_gains = {}
            return {}

        contact_norm = _clamp(contact_count / 4.0, 0.0, 1.0)
        active_ping_norm = _clamp(active_ping_count / 3.0, 0.0, 1.0)
        own_noise = _clamp(foundation.own_noise, 0.0, 1.0)
        global_mix_gain = _clamp(float(self.preset.get("global_mix_gain", 1.0)), 0.2, 2.0)

        gains: dict[str, float] = {}
        for layer_key, spec in self.layer_specs.items():
            family = str(spec.get("family"))
            density = _clamp(float(spec.get("density", 1.0)), 0.0, 2.0)
            intensity = _clamp(float(spec.get("intensity", 1.0)), 0.0, 2.0)

            if family == "ambient_soundscape":
                gain = 0.17 * foundation.ambient_level * density * intensity
            elif family == "marine_mammal_whale":
                gain = 0.10 * density * intensity * (1.0 - 0.45 * own_noise) * (0.85 - 0.2 * contact_norm)
            elif family == "marine_mammal_other":
                gain = 0.11 * density * intensity * (1.0 - 0.35 * own_noise) * (0.8 + 0.2 * (1.0 - contact_norm))
            elif family == "surface_vessel":
                gain = 0.13 * density * intensity * (0.25 + 0.75 * max(contact_norm, 0.2))
            elif family == "intermittent_machinery_archetype":
                gain = 0.10 * density * intensity * (0.2 + 0.8 * own_noise) * (0.75 + 0.25 * active_ping_norm)
            else:
                gain = 0.0

            if foundation.ping_active and family in {"ambient_soundscape", "marine_mammal_whale", "marine_mammal_other"}:
                gain *= 0.9

            gain = _clamp(gain * global_mix_gain, 0.0, 0.40)
            gains[layer_key] = gain

        self.last_layer_gains = gains
        return gains

    def state_snapshot(self) -> dict[str, Any]:
        layers: dict[str, Any] = {}
        for layer_key, spec in self.layer_specs.items():
            layers[layer_key] = {
                "family": spec.get("family"),
                "contract_hook": spec.get("contract_hook"),
                "synthesis_mode": spec.get("synthesis_mode"),
                "wav_path": spec.get("wav_path"),
                "gain": self.last_layer_gains.get(layer_key, 0.0),
                "density": spec.get("density"),
                "intensity": spec.get("intensity"),
                "variability": spec.get("variability"),
            }

        return {
            "schema_version": "runtime-acoustic.v1",
            "generated_utc": _utc_now_iso(),
            "enabled": self.enabled,
            "preset_name": self.preset_name,
            "init_error": self.init_error,
            "families": layers,
        }


__all__ = [
    "DEFAULT_PRESET_PATH",
    "DEFAULT_RENDERER_PARAMS_PATH",
    "RUNTIME_FAMILIES",
    "RuntimeHybridLayerV1",
    "list_runtime_acoustic_presets",
    "load_runtime_acoustic_preset_pack",
    "resolve_runtime_acoustic_preset",
]
