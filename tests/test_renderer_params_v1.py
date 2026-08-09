from pathlib import Path

from subsim.renderer_params_v1 import REQUIRED_RENDER_FAMILIES, build_renderer_params_v1


REPO_ROOT = Path(__file__).resolve().parent.parent
HYDRO_ROOT = REPO_ROOT / "dataset" / "hydrophone"


def test_build_renderer_params_v1_from_hydrophone_outputs(tmp_path: Path) -> None:
    out_json = tmp_path / "renderer_params_v1.json"
    out_md = tmp_path / "renderer_params_v1.md"

    payload = build_renderer_params_v1(
        hydro_root=HYDRO_ROOT,
        output_json_path=out_json,
        output_md_path=out_md,
    )

    assert out_json.exists()
    assert out_md.exists()
    assert payload["renderer_params_version"] == "renderer_params_v1"

    families = payload.get("families", {})
    for family in REQUIRED_RENDER_FAMILIES:
        assert family in families
        f = families[family]
        assert f.get("synthesis_mode") in {"ambient_bed", "hybrid", "procedural", "sample_backed"}
        assert f.get("analysis_basis", {}).get("sample_count", 0) > 0
        assert "dominant_freq_hz" in f.get("feature_ranges", {})
        assert "derived_parameters" in f
        assert "seed_exemplars" in f

    intermittent = families["intermittent_machinery_archetype"]
    assert intermittent["analysis_basis"].get("safe_archetype_filter") == "intermittent_machinery_archetype"
