import json
from pathlib import Path

from subsim.renderer_params_v1 import build_renderer_params_v1
from subsim.renderer_preview_v1 import build_renderer_preview_report, generate_renderer_previews
from subsim.renderer_v1 import HybridAcousticRendererV1


REPO_ROOT = Path(__file__).resolve().parent.parent
HYDRO_ROOT = REPO_ROOT / "dataset" / "hydrophone"


def test_preview_manifest_and_report_generation(tmp_path: Path) -> None:
    params_path = tmp_path / "renderer_params_v1.json"
    build_renderer_params_v1(
        hydro_root=HYDRO_ROOT,
        output_json_path=params_path,
        output_md_path=tmp_path / "renderer_params_v1.md",
    )

    renderer = HybridAcousticRendererV1.from_json(params_path)
    preview_root = tmp_path / "renderer_previews"
    manifest = generate_renderer_previews(
        renderer,
        output_root=preview_root,
        variants_per_family=1,
        base_seed=77,
        include_plots=False,
        duration_override_s=0.9,
    )

    manifest_path = preview_root / "renderer_preview_manifest.json"
    assert manifest_path.exists()
    assert manifest["entry_count"] == len(renderer.supported_families())

    for entry in manifest["entries"]:
        wav = Path(entry["audio_path"])
        assert wav.exists()
        assert wav.stat().st_size > 200

    params = json.loads(params_path.read_text(encoding="utf-8"))
    gap_report = json.loads((HYDRO_ROOT / "reports" / "hydrophone_dataset_gap_report.json").read_text(encoding="utf-8"))
    report_json = tmp_path / "renderer_preview_report.json"
    report_md = tmp_path / "renderer_preview_report.md"

    report = build_renderer_preview_report(
        renderer_params=params,
        preview_manifest=manifest,
        gap_report=gap_report,
        output_json_path=report_json,
        output_md_path=report_md,
    )

    assert report_json.exists()
    assert report_md.exists()
    assert report["report_version"] == "renderer_preview_report.v1"
    assert len(report["families_assessed"]) == len(renderer.supported_families())
