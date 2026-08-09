from pathlib import Path

from subsim.renderer_params_v1 import REQUIRED_RENDER_FAMILIES, build_renderer_params_v1
from subsim.renderer_v1 import HybridAcousticRendererV1


REPO_ROOT = Path(__file__).resolve().parent.parent
HYDRO_ROOT = REPO_ROOT / "dataset" / "hydrophone"


def _build_params(tmp_path: Path) -> Path:
    params_path = tmp_path / "renderer_params_v1.json"
    build_renderer_params_v1(
        hydro_root=HYDRO_ROOT,
        output_json_path=params_path,
        output_md_path=tmp_path / "renderer_params_v1.md",
    )
    return params_path


def test_renderer_v1_deterministic_with_fixed_seed(tmp_path: Path) -> None:
    params_path = _build_params(tmp_path)
    renderer = HybridAcousticRendererV1.from_json(params_path)

    samples_a, meta_a = renderer.render_family(
        "surface_vessel",
        duration_s=1.25,
        seed=1337,
        variability=0.33,
        intensity=1.0,
        include_seed=False,
    )
    samples_b, meta_b = renderer.render_family(
        "surface_vessel",
        duration_s=1.25,
        seed=1337,
        variability=0.33,
        intensity=1.0,
        include_seed=False,
    )

    assert samples_a == samples_b
    assert meta_a["pcm_sha1"] == meta_b["pcm_sha1"]

    _, meta_c = renderer.render_family(
        "surface_vessel",
        duration_s=1.25,
        seed=1441,
        variability=0.33,
        intensity=1.0,
        include_seed=False,
    )
    assert meta_c["pcm_sha1"] != meta_a["pcm_sha1"]


def test_renderer_v1_supports_required_families(tmp_path: Path) -> None:
    params_path = _build_params(tmp_path)
    renderer = HybridAcousticRendererV1.from_json(params_path)

    supported = set(renderer.supported_families())
    assert set(REQUIRED_RENDER_FAMILIES).issubset(supported)

    for family in REQUIRED_RENDER_FAMILIES:
        wav_path = tmp_path / f"{family}.wav"
        meta = renderer.render_family_to_wav(
            wav_path,
            family,
            duration_s=1.0,
            seed=2026,
            variability=0.2,
            intensity=0.95,
            include_seed=True,
        )
        assert wav_path.exists()
        assert wav_path.stat().st_size > 256
        assert meta["family"] == family
        assert meta["sample_rate_hz"] == renderer.sample_rate
