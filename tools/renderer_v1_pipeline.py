#!/usr/bin/env python3
"""Renderer Params v1 + Hybrid Renderer preview pipeline for Subsim."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from subsim.renderer_params_v1 import build_renderer_params_v1
from subsim.renderer_preview_v1 import build_renderer_preview_report, generate_renderer_previews
from subsim.renderer_v1 import HybridAcousticRendererV1


DEFAULT_HYDRO_ROOT = REPO_ROOT / "dataset" / "hydrophone"
DEFAULT_PARAMS_JSON = DEFAULT_HYDRO_ROOT / "renderer_params_v1.json"
DEFAULT_PARAMS_MD = DEFAULT_HYDRO_ROOT / "renderer_params_v1.md"
DEFAULT_PREVIEW_ROOT = REPO_ROOT / "artifacts" / "renderer_v1_previews"
DEFAULT_PREVIEW_MANIFEST = DEFAULT_PREVIEW_ROOT / "renderer_preview_manifest.json"
DEFAULT_REPORT_JSON = REPO_ROOT / "docs" / "renderer_preview_report.json"
DEFAULT_REPORT_MD = REPO_ROOT / "docs" / "renderer_preview_report.md"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def cmd_build_params(args: argparse.Namespace) -> dict[str, Any]:
    payload = build_renderer_params_v1(
        hydro_root=args.hydro_root,
        output_json_path=args.params_json,
        output_md_path=args.params_md,
    )
    return {
        "stage": "build_params",
        "params_json": str(args.params_json),
        "params_md": str(args.params_md),
        "families": sorted(payload.get("families", {}).keys()),
    }


def cmd_render_previews(args: argparse.Namespace) -> dict[str, Any]:
    if not args.params_json.exists():
        raise RuntimeError(f"Renderer params missing: {args.params_json}")

    renderer = HybridAcousticRendererV1.from_json(args.params_json)
    manifest = generate_renderer_previews(
        renderer,
        output_root=args.preview_root,
        variants_per_family=args.variants_per_family,
        base_seed=args.seed,
        include_plots=not args.no_plots,
        duration_override_s=args.duration_override_s,
    )
    return {
        "stage": "render_previews",
        "preview_manifest": str(args.preview_manifest),
        "entry_count": manifest.get("entry_count"),
        "families": manifest.get("families"),
    }


def cmd_report(args: argparse.Namespace) -> dict[str, Any]:
    if not args.params_json.exists():
        raise RuntimeError(f"Renderer params missing: {args.params_json}")
    if not args.preview_manifest.exists():
        raise RuntimeError(f"Preview manifest missing: {args.preview_manifest}")

    params = _read_json(args.params_json)
    manifest = _read_json(args.preview_manifest)
    gap_report = _read_json(args.hydro_root / "reports" / "hydrophone_dataset_gap_report.json")

    report = build_renderer_preview_report(
        renderer_params=params,
        preview_manifest=manifest,
        gap_report=gap_report,
        output_json_path=args.report_json,
        output_md_path=args.report_md,
    )
    return {
        "stage": "report",
        "report_json": str(args.report_json),
        "report_md": str(args.report_md),
        "families_assessed": len(report.get("families_assessed", [])),
    }


def cmd_validate(args: argparse.Namespace) -> dict[str, Any]:
    checks = {
        "params_json_exists": args.params_json.exists(),
        "params_md_exists": args.params_md.exists(),
        "preview_manifest_exists": args.preview_manifest.exists(),
        "report_json_exists": args.report_json.exists(),
        "report_md_exists": args.report_md.exists(),
    }

    missing = [k for k, ok in checks.items() if not ok]
    if missing:
        raise RuntimeError(f"Missing required artifacts: {', '.join(missing)}")

    params = _read_json(args.params_json)
    manifest = _read_json(args.preview_manifest)
    report = _read_json(args.report_json)

    entries = manifest.get("entries", [])
    if not isinstance(entries, list) or not entries:
        raise RuntimeError("Preview manifest has no entries")

    missing_audio = [e.get("audio_path") for e in entries if not Path(str(e.get("audio_path"))).exists()]
    if missing_audio:
        raise RuntimeError(f"Missing preview audio files: {missing_audio[:3]}")

    renderer = HybridAcousticRendererV1.from_json(args.params_json)
    first = entries[0]
    regen_samples, regen_meta = renderer.render_family(
        first["family"],
        duration_s=float(first.get("duration_s") or 0),
        seed=int(first.get("seed") or 0),
        variability=float(first.get("variability") or 0.0),
        intensity=float(first.get("intensity") or 1.0),
        include_seed=True,
    )
    _ = regen_samples
    if regen_meta.get("pcm_sha1") != first.get("pcm_sha1"):
        raise RuntimeError(
            "Reproducibility check failed: regenerated first preview hash does not match manifest."
        )

    report_families = {f.get("family") for f in report.get("families_assessed", [])}
    param_families = set(params.get("families", {}).keys())
    if report_families != param_families:
        raise RuntimeError(
            f"Report families do not match renderer params families: report={sorted(report_families)} params={sorted(param_families)}"
        )

    return {
        "stage": "validate",
        "checks": checks,
        "entry_count": len(entries),
        "family_count": len(param_families),
        "reproducibility_ok": True,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Subsim Renderer v1 pipeline")
    parser.add_argument(
        "command",
        choices=["build-params", "render-previews", "report", "validate", "run-all"],
    )
    parser.add_argument("--hydro-root", type=Path, default=DEFAULT_HYDRO_ROOT)
    parser.add_argument("--params-json", type=Path, default=DEFAULT_PARAMS_JSON)
    parser.add_argument("--params-md", type=Path, default=DEFAULT_PARAMS_MD)
    parser.add_argument("--preview-root", type=Path, default=DEFAULT_PREVIEW_ROOT)
    parser.add_argument("--preview-manifest", type=Path, default=DEFAULT_PREVIEW_MANIFEST)
    parser.add_argument("--report-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--report-md", type=Path, default=DEFAULT_REPORT_MD)
    parser.add_argument("--variants-per-family", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20260424)
    parser.add_argument("--duration-override-s", type=float, default=None)
    parser.add_argument("--no-plots", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.command == "build-params":
        payload = cmd_build_params(args)
    elif args.command == "render-previews":
        payload = cmd_render_previews(args)
    elif args.command == "report":
        payload = cmd_report(args)
    elif args.command == "validate":
        payload = cmd_validate(args)
    elif args.command == "run-all":
        build_payload = cmd_build_params(args)
        render_payload = cmd_render_previews(args)
        report_payload = cmd_report(args)
        validate_payload = cmd_validate(args)
        payload = {
            "pipeline": "renderer_v1",
            "build_params": build_payload,
            "render_previews": render_payload,
            "report": report_payload,
            "validate": validate_payload,
        }
        _write_json(args.preview_root / "run_all_summary.json", payload)
    else:
        raise RuntimeError(f"Unknown command: {args.command}")

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
