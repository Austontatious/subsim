# Hydrophone Fixed Eval Manifest Report

Generated: 2026-05-07T16:26:28+00:00

## Summary

- Total clips: 78
- Total groups: 46
- Synthetic included: no
- Group leakage prevented: yes
- Reliability caveat: this is a stable smoke/eval asset, not proof of model quality.

## Split Counts

| Split | Clips | Groups |
|---|---:|---:|
| train | 47 | 28 |
| validation | 16 | 9 |
| heldout_source_eval | 15 | 9 |

## Split Counts by Class

| Class | Train | Validation | Heldout |
|---|---:|---:|---:|
| ambient_ocean | 25 | 9 | 6 |
| biologic_fish | 10 | 3 | 5 |
| biologic_mammal | 6 | 2 | 2 |
| surface_vessel | 6 | 2 | 2 |

## Split Counts by Dataset

| Dataset | Train | Validation | Heldout |
|---|---:|---:|---:|
| mbari | 18 | 6 | 3 |
| noaa_fish_sounds | 4 | 3 | 3 |
| noaa_ocean_sounds | 7 | 3 | 3 |
| shipsear | 6 | 2 | 2 |
| watkins | 6 | 2 | 2 |
| zenodo_pacama_fish | 6 | 0 | 2 |

## Imbalance / Degradation Notes

- No class had to drop validation or heldout groups.
