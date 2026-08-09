# Hydrophone Dataset Sampling Report

Generated: 2026-05-07T16:12:23+00:00
Mode: dry-run

## Datasets attempted

| Dataset | Status | Access | Notes |
|---|---:|---|---|
| ShipsEar (`shipsear`) | skipped | skipped | Dry-run only. ShipsEar component is exposed through a Hugging Face DS3500 mirror as a ZIP archive; bounded sampler prefers a local archive cache to avoid large archive downloads. |
| DeepShip (`deepship`) | manual_required | manual | Dry-run only. Useful surface-vessel corpus, but packaging is manual-heavy for a tiny automated first slice. |
| OceanShip (`oceanship`) | manual_required | manual | Dry-run only. Candidate surface-vessel dataset; direct small-file access is not assumed by this first-pass fetcher. |
| Watkins Marine Mammal Sound Database (`watkins`) | skipped | skipped | Dry-run only. Uses a parquet mirror when available locally or by direct URL; keep license caveats visible. |
| FishSounds / fish sound references (`fishsounds`) | manual_required | manual | Dry-run only. Manual next step: select a FishSounds record, follow the linked source dataset, verify that source's terms, then register the direct audio URL and citation metadata before pulling. |
| NOAA Fisheries Sounds in the Ocean: Fish and Invertebrates (`noaa_fish_sounds`) | skipped | skipped | Dry-run only. Direct MP3 exemplar clips from NOAA Fisheries Passive Acoustics Group fish page; invertebrate clips are skipped for the biologic_fish class. |
| Zenodo pacama catfish stridulation sounds (`zenodo_pacama_fish`) | skipped | skipped | Dry-run only. Three WAV files for pacama Lophiosilurus alexandri stridulation sounds; Zenodo record is CC BY 4.0. |
| NOAA NCEI Passive Acoustic Data Archive (`noaa`) | manual_required | manual | Dry-run only. Archive is broad and heterogeneous; first slice records it as a manual expansion target. |
| NOAA Fisheries Sounds in the Ocean: Environmental and Anthropogenic (`noaa_ocean_sounds`) | skipped | skipped | Dry-run only. Direct MP3 exemplar clips from NOAA Fisheries environmental sounds page; anthropogenic clips are skipped for ambient_ocean. |
| MBARI Pacific Sound (`mbari`) | skipped | skipped | Dry-run only. Decimated 2 kHz archive supports small HTTP range samples from public AWS objects. |
| Simulated passive sonar / contact simulation (`wolfset`) | skipped | skipped | Dry-run only. No real submarine signature data is fetched; use generate_synthetic_waves.py for simulated contact-like examples. |

## Datasets successfully sampled

- None in this run.

## Datasets requiring manual download

- `deepship`: Dry-run only. Useful surface-vessel corpus, but packaging is manual-heavy for a tiny automated first slice.
- `oceanship`: Dry-run only. Candidate surface-vessel dataset; direct small-file access is not assumed by this first-pass fetcher.
- `fishsounds`: Dry-run only. Manual next step: select a FishSounds record, follow the linked source dataset, verify that source's terms, then register the direct audio URL and citation metadata before pulling.
- `noaa`: Dry-run only. Archive is broad and heterogeneous; first slice records it as a manual expansion target.

## License/usage notes found

- `shipsear`: cc-by-4.0_on_hf_mirror_verify_original_terms
- `deepship`: unknown_or_documented
- `oceanship`: unknown_or_documented
- `watkins`: personal_or_academic_noncommercial_verify_before_distribution
- `fishsounds`: unknown_or_documented
- `noaa_fish_sounds`: noaa_public_information_with_citation_request
- `zenodo_pacama_fish`: cc-by-4.0
- `noaa`: varies_by_collection
- `noaa_ocean_sounds`: noaa_public_information_with_citation_request
- `mbari`: project_license_see_source
- `wolfset`: repo_generated_synthetic

## Attempt log

- No network or local-cache attempts were made.

## File counts

- Clip records produced this run: 0
- Total sampled duration: 0.00 seconds

## Recommended next expansion

- Prefer one source per class with machine-readable license notes before scaling volume.
- Expand MBARI/NOAA ambient clips by deployment group before using broad NOAA archive pulls.
- Add FishSounds/GLUBS records only after choosing specific downloadable references and recording source-level terms.
- Keep submarine-like examples synthetic/simulated and labeled as such.
