# Hydrophone Category Analysis Report

Generated: 2026-04-24T00:36:08+00:00

## Scope

This report summarizes the v1 Subsim hydrophone ingestion/analyzer pass over a bounded subset of open/public underwater-acoustic sources.

## Corpus Summary

- Samples analyzed: 434
- Source datasets: 3
- Categories present: 5
- Cluster count (k-means): 8
- Silhouette score: 0.18953277324491113

## Category Findings

### ambient_soundscape

- Count: 54
- Source mix: {"hf_shipsear": 45, "mbari_pacific_sound_2khz": 9}
- Label quality: {"exact": 45, "inferred": 9}
- Suggested render mode: texture_bed_synthesis_with_spectral_controls
- Parameter hints: {"centroid_hint_hz": 1570.9, "modulation_hint_hz": 1.981, "spectral_flatness_hint": 0.281}

### marine_mammal_orca

- Count: 14
- Source mix: {"hf_wmms_parquet": 14}
- Label quality: {"exact": 14}
- Suggested render mode: hybrid_procedural_with_exemplar_grains
- Parameter hints: {"cadence_hint_s": 0.066, "carrier_band_hint_hz": 3580.0, "modulation_hint_hz": 1.0, "tonality_hint": 0.933}

### marine_mammal_other

- Count: 113
- Source mix: {"hf_wmms_parquet": 113}
- Label quality: {"exact": 113}
- Suggested render mode: hybrid_procedural_with_exemplar_grains
- Parameter hints: {"cadence_hint_s": 0.065, "carrier_band_hint_hz": 330.0, "modulation_hint_hz": 1.0, "tonality_hint": 0.941}

### marine_mammal_whale

- Count: 73
- Source mix: {"hf_wmms_parquet": 73}
- Label quality: {"exact": 73}
- Suggested render mode: hybrid_procedural_with_exemplar_grains
- Parameter hints: {"cadence_hint_s": 0.065, "carrier_band_hint_hz": 210.0, "modulation_hint_hz": 0.704, "tonality_hint": 0.962}

### surface_vessel

- Count: 180
- Source mix: {"hf_shipsear": 180}
- Label quality: {"coarse": 180}
- Suggested render mode: parametric_machinery_and_cavitation_layers
- Parameter hints: {"low_band_ratio_hint": 0.299, "roughness_hint": 0.0, "transient_density_hint": 14.614}

## Overlap / Confusion Risk

Closest category centroids (higher overlap risk):
- marine_mammal_orca vs marine_mammal_other: centroid distance 1.8274
- marine_mammal_whale vs surface_vessel: centroid distance 2.1003
- marine_mammal_other vs marine_mammal_whale: centroid distance 2.4557
- marine_mammal_orca vs marine_mammal_whale: centroid distance 3.1277
- marine_mammal_other vs surface_vessel: centroid distance 3.1947
- ambient_soundscape vs surface_vessel: centroid distance 3.2927
- marine_mammal_orca vs surface_vessel: centroid distance 3.9015
- ambient_soundscape vs marine_mammal_whale: centroid distance 4.0426

## Safe Contact-Like Archetypes

The analyzer emits only abstract archetype tags (for example `quiet_contact_archetype`, `intermittent_machinery_archetype`) and does not build nation/class-specific military signature labels.
- Distribution: {"intermittent_machinery_archetype": 180}

## Practical Takeaways For Renderer Design

- Marine mammal categories are suitable for hybrid procedural generation anchored by exemplar fragments.
- Surface vessel classes are suitable for parametric low-band machinery/cavitation style rendering.
- Ambient beds are suitable for layered texture synthesis with spectral and modulation controls.
- Sparse categories should remain synthetic or deferred until additional curated data is pulled.
