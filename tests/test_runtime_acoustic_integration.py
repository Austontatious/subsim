import json
from pathlib import Path

from subsim.acoustic_contract import build_foundation_state
from subsim.game import parse_args
from subsim.runtime_acoustic import RUNTIME_FAMILIES, RuntimeHybridLayerV1, resolve_runtime_acoustic_preset


REPO_ROOT = Path(__file__).resolve().parent.parent
PARAMS_PATH = REPO_ROOT / "dataset" / "hydrophone" / "renderer_params_v1.json"


def _write_test_preset(path: Path) -> None:
    payload = {
        "default_preset": "test_dense",
        "presets": {
            "test_dense": {
                "global_mix_gain": 1.0,
                "foundation": {
                    "ambient_multiplier": 1.0,
                    "self_noise_multiplier": 1.0,
                    "player_hum_multiplier": 1.0,
                    "self_noise_masking_pressure": 1.0,
                },
                "families": {
                    "ambient_soundscape": {"enabled": True, "intensity": 0.9, "variability": 0.2, "density": 0.8, "duration_s": 1.0},
                    "marine_mammal_whale": {"enabled": True, "intensity": 0.9, "variability": 0.2, "density": 0.8, "duration_s": 1.0},
                    "marine_mammal_other": {"enabled": True, "intensity": 0.9, "variability": 0.2, "density": 0.8, "duration_s": 1.0},
                    "surface_vessel": {"enabled": True, "intensity": 0.9, "variability": 0.2, "density": 0.8, "duration_s": 1.0},
                    "intermittent_machinery_archetype": {
                        "enabled": True,
                        "intensity": 0.9,
                        "variability": 0.2,
                        "density": 0.8,
                        "duration_s": 1.0,
                    },
                },
            }
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_resolve_runtime_preset_falls_back_to_default() -> None:
    selected, _, pack = resolve_runtime_acoustic_preset("not_a_real_preset")
    assert "presets" in pack
    assert selected in pack["presets"]


def test_runtime_hybrid_layer_prepares_cached_layers(tmp_path: Path) -> None:
    assert PARAMS_PATH.exists()
    preset_path = tmp_path / "runtime_preset.json"
    _write_test_preset(preset_path)

    runtime = RuntimeHybridLayerV1(
        preset_name="test_dense",
        runtime_seed=77,
        params_path=PARAMS_PATH,
        preset_path=preset_path,
        cache_dir=tmp_path / "cache",
    )
    assert runtime.enabled, runtime.init_error
    assert runtime.layer_specs
    rendered_families = {str(spec.get("family")) for spec in runtime.layer_specs.values()}
    assert rendered_families.issubset(set(RUNTIME_FAMILIES))
    for spec in runtime.layer_specs.values():
        wav_path = Path(str(spec.get("wav_path")))
        assert wav_path.exists()
        assert wav_path.stat().st_size > 256

    foundation = build_foundation_state(own_noise=0.35, sensor_noise=0.2, ping_active=False)
    foundation_profile = runtime.apply_foundation_profile(foundation)
    gains = runtime.compute_layer_gains(foundation, contact_count=2, active_ping_count=1)
    assert set(gains.keys()) == set(runtime.layer_specs.keys())
    assert {"ambient_gain", "self_noise_gain", "hum_gain"} <= set(foundation_profile.keys())


def test_parse_args_supports_runtime_acoustic_preset() -> None:
    args = parse_args(["--headless", "--ticks", "1", "--acoustic-preset", "high_clutter"])
    assert args.acoustic_preset == "high_clutter"
