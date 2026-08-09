# Subsim Hydrophone Dataset Pipeline (v1)

This folder contains a repeatable pull + normalization + feature + analysis pipeline for building a practical underwater-acoustic substrate for Subsim.

## Pipeline entrypoint

- Script: `tools/hydrophone_pipeline.py`
- Root output dir (default): `dataset/hydrophone/`

## One-shot run

```bash
cd /path/to/subsim
python3 tools/hydrophone_pipeline.py run-all
```

## Stage-by-stage

```bash
python3 tools/hydrophone_pipeline.py pull
python3 tools/hydrophone_pipeline.py normalize
python3 tools/hydrophone_pipeline.py features
python3 tools/hydrophone_pipeline.py analyze
python3 tools/hydrophone_pipeline.py report
python3 tools/hydrophone_pipeline.py validate
```

## Core artifacts

- Source manifest: `dataset/hydrophone/hydrophone_sources_manifest.json`
- Taxonomy map: `dataset/hydrophone/hydrophone_taxonomy.json`
- Normalized index: `dataset/hydrophone/hydrophone_dataset_index.jsonl`
- Feature table: `dataset/hydrophone/features/hydrophone_features.csv`
- Clusters + PCA: `dataset/hydrophone/analysis/`
- Category report: `dataset/hydrophone/reports/hydrophone_category_analysis_report.md`
- Gap report: `dataset/hydrophone/reports/hydrophone_dataset_gap_report.md`

## Renderer v1 follow-on

Build renderer params + first hybrid preview artifacts:

```bash
cd /path/to/subsim
python3 tools/renderer_v1_pipeline.py run-all
```

Generated outputs include:

- `dataset/hydrophone/renderer_params_v1.json`
- `dataset/hydrophone/renderer_params_v1.md`
- `artifacts/renderer_v1_previews/renderer_preview_manifest.json`
- `docs/renderer_preview_report.md`
- `docs/renderer_preview_report.json`

## Dependencies

Baseline package versions for this pipeline are listed in `dataset/hydrophone/requirements.txt`.

## Safety boundary

This pipeline is intentionally constrained to open/public sources and uses abstract contact-like archetype tags only. It does not build nation/class-specific military signature labels.
