# SubSim Hydrophone Fixture Export Report

Generated: 2026-05-07T16:28:21+00:00

- Fixture rows: 78
- Synthetic included: no

## Counts by Gameplay Role

- `ambient_clutter`: 40
- `biologic_clutter`: 28
- `surface_contact`: 10

## Counts by Source Dataset

- `mbari`: 27
- `noaa_fish_sounds`: 10
- `noaa_ocean_sounds`: 13
- `shipsear`: 10
- `watkins`: 10
- `zenodo_pacama_fish`: 8

## License / Commercial Caveats

- cc-by-4.0 / redistribution=allowed / commercial=allowed
- cc-by-4.0_on_hf_mirror_verify_original_terms / redistribution=allowed / commercial=allowed
- noaa_public_information_with_citation_request / redistribution=allowed / commercial=allowed
- personal_or_academic_noncommercial_verify_before_distribution / redistribution=not_allowed / commercial=not_allowed
- project_license_see_source / redistribution=unclear / commercial=unclear

## Recommended SubSim Integration Path

- Use `subsim_acoustic_contacts.jsonl` as gameplay fixture metadata, not acoustic truth labels.
- Feed heldout-source ReadyPlayer1 cases into the Campaign 003 clutter-binding and primary-track selection loop first.
- Keep audio artifacts ignored; fixtures should reference local normalized paths that can be regenerated.
