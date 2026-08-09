# Hydrophone Dataset Gap Report

Generated: 2026-04-24T00:36:08+00:00

## Coverage Snapshot

- marine_mammal_whale: 87 inclusive samples (primary=73, status=well_covered)
- marine_mammal_orca: 14 inclusive samples (primary=14, status=thin)
- marine_mammal_other: 113 inclusive samples (primary=113, status=well_covered)
- marine_life_other: 0 inclusive samples (primary=0, status=missing)
- surface_vessel: 180 inclusive samples (primary=180, status=well_covered)
- ambient_soundscape: 54 inclusive samples (primary=54, status=well_covered)
- weather_geophony: 0 inclusive samples (primary=0, status=missing)
- anthropogenic_non_vessel: 0 inclusive samples (primary=0, status=missing)
- machinery_noise: 180 inclusive samples (primary=0, status=well_covered)
- unknown_contact_like: 9 inclusive samples (primary=0, status=thin)
- submarine_like_archetype_inspiration: 0 inclusive samples (primary=0, status=missing)

## Gaps That Matter For Subsim

- `weather_geophony` remains thin/missing in this v1 subset and needs dedicated source pulls.
- `anthropogenic_non_vessel` remains thin/missing and needs explicit harbor/industrial/noise-event sets.
- `submarine_like_archetype_inspiration` is intentionally not sourced from real military signatures; derive this only as abstract procedural archetypes.

## Metadata-Only Sources Pending Manual Follow-Up

### dclde_reference

- Select specific DCLDE years/species aligned with Subsim goals.
- Acquire downloads according to challenge-specific terms.
- Register local paths into this manifest before re-run.

### noaa_passive_acoustics_reference

- Identify concrete NOAA collection endpoints with stable machine access.
- Define source-specific subset strategy for manageable pulls.

## Recommended Next Pulls

- Add a weather/geophony-focused hydrophone subset (storms, rain, seismic/ice where available).
- Add a curated anthropogenic non-vessel subset (fixed machinery, offshore infrastructure, harbor clutter).
- Keep contact-like categories abstract and game-oriented instead of platform-specific.
