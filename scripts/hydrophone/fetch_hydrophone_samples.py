#!/usr/bin/env python3
"""Bounded hydrophone sample fetcher.

The default mode is dry-run: it writes dataset status/report metadata but does
not download or copy audio. Use --download to materialize a tiny sample set.
"""

from __future__ import annotations

import argparse
import io
import shutil
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hydrophone_common import (  # noqa: E402
    DEFAULT_DATA_ROOT,
    DEFAULT_REPORT_ROOT,
    REPO_ROOT,
    conservative_normalize,
    ensure_dir,
    ensure_hydrophone_layout,
    read_jsonl,
    read_wav_info,
    repo_relative,
    write_jsonl,
    write_text,
    write_wav,
    utc_now_iso,
)


@dataclass(frozen=True)
class DatasetSpec:
    dataset_id: str
    name: str
    source_url: str
    license: str
    default_access_method: str
    default_label: str
    default_sub_label: str
    notes: str


DATASETS: dict[str, DatasetSpec] = {
    "shipsear": DatasetSpec(
        dataset_id="shipsear",
        name="ShipsEar",
        source_url="https://huggingface.co/datasets/peng7554/DS3500",
        license="cc-by-4.0_on_hf_mirror_verify_original_terms",
        default_access_method="direct_download",
        default_label="surface_vessel",
        default_sub_label="ship_radiated_noise",
        notes="ShipsEar component is exposed through a Hugging Face DS3500 mirror as a ZIP archive; bounded sampler prefers a local archive cache to avoid large archive downloads.",
    ),
    "deepship": DatasetSpec(
        dataset_id="deepship",
        name="DeepShip",
        source_url="https://github.com/irfankamboh/DeepShip",
        license="unknown_or_documented",
        default_access_method="manual",
        default_label="surface_vessel",
        default_sub_label="ship",
        notes="Useful surface-vessel corpus, but packaging is manual-heavy for a tiny automated first slice.",
    ),
    "oceanship": DatasetSpec(
        dataset_id="oceanship",
        name="OceanShip",
        source_url="https://github.com/irfankamboh/OceanShip",
        license="unknown_or_documented",
        default_access_method="manual",
        default_label="surface_vessel",
        default_sub_label="ship",
        notes="Candidate surface-vessel dataset; direct small-file access is not assumed by this first-pass fetcher.",
    ),
    "watkins": DatasetSpec(
        dataset_id="watkins",
        name="Watkins Marine Mammal Sound Database",
        source_url="https://huggingface.co/datasets/qdskipper/wmms-parquet",
        license="personal_or_academic_noncommercial_verify_before_distribution",
        default_access_method="direct_download",
        default_label="biologic_mammal",
        default_sub_label="marine_mammal",
        notes="Uses a parquet mirror when available locally or by direct URL; keep license caveats visible.",
    ),
    "fishsounds": DatasetSpec(
        dataset_id="fishsounds",
        name="FishSounds / fish sound references",
        source_url="https://fishsounds.net",
        license="unknown_or_documented",
        default_access_method="manual",
        default_label="biologic_fish",
        default_sub_label="fish",
        notes="Manual next step: select a FishSounds record, follow the linked source dataset, verify that source's terms, then register the direct audio URL and citation metadata before pulling.",
    ),
    "noaa_fish_sounds": DatasetSpec(
        dataset_id="noaa_fish_sounds",
        name="NOAA Fisheries Sounds in the Ocean: Fish and Invertebrates",
        source_url="https://www.fisheries.noaa.gov/national/science-data/sounds-ocean-fish-and-invertebrates",
        license="noaa_public_information_with_citation_request",
        default_access_method="direct_download",
        default_label="biologic_fish",
        default_sub_label="fish",
        notes="Direct MP3 exemplar clips from NOAA Fisheries Passive Acoustics Group fish page; invertebrate clips are skipped for the biologic_fish class.",
    ),
    "zenodo_pacama_fish": DatasetSpec(
        dataset_id="zenodo_pacama_fish",
        name="Zenodo pacama catfish stridulation sounds",
        source_url="https://zenodo.org/records/14181832",
        license="cc-by-4.0",
        default_access_method="direct_download",
        default_label="biologic_fish",
        default_sub_label="pacama_catfish",
        notes="Three WAV files for pacama Lophiosilurus alexandri stridulation sounds; Zenodo record is CC BY 4.0.",
    ),
    "noaa": DatasetSpec(
        dataset_id="noaa",
        name="NOAA NCEI Passive Acoustic Data Archive",
        source_url="https://www.ncei.noaa.gov/products/passive-acoustic-data",
        license="varies_by_collection",
        default_access_method="manual",
        default_label="ambient_ocean",
        default_sub_label="ambient",
        notes="Archive is broad and heterogeneous; first slice records it as a manual expansion target.",
    ),
    "noaa_ocean_sounds": DatasetSpec(
        dataset_id="noaa_ocean_sounds",
        name="NOAA Fisheries Sounds in the Ocean: Environmental and Anthropogenic",
        source_url="https://www.fisheries.noaa.gov/national/science-data/sounds-ocean-environmental-and-anthropogenic",
        license="noaa_public_information_with_citation_request",
        default_access_method="direct_download",
        default_label="ambient_ocean",
        default_sub_label="environmental_sound",
        notes="Direct MP3 exemplar clips from NOAA Fisheries environmental sounds page; anthropogenic clips are skipped for ambient_ocean.",
    ),
    "mbari": DatasetSpec(
        dataset_id="mbari",
        name="MBARI Pacific Sound",
        source_url="https://docs.mbari.org/pacific-sound/",
        license="project_license_see_source",
        default_access_method="direct_download",
        default_label="ambient_ocean",
        default_sub_label="ambient",
        notes="Decimated 2 kHz archive supports small HTTP range samples from public AWS objects.",
    ),
    "wolfset": DatasetSpec(
        dataset_id="wolfset",
        name="Simulated passive sonar / contact simulation",
        source_url="local_synthetic_generator",
        license="repo_generated_synthetic",
        default_access_method="skipped",
        default_label="synthetic_submarine_like",
        default_sub_label="synthetic_narrowband",
        notes="No real submarine signature data is fetched; use generate_synthetic_waves.py for simulated contact-like examples.",
    ),
}

LICENSE_REVIEWS: dict[str, dict[str, Any]] = {
    "shipsear": {
        "redistribution": "allowed",
        "commercial_use": "allowed",
        "license_reviewed": True,
        "license_notes": "Hugging Face mirror declares CC BY 4.0; verify original ShipsEar terms before redistribution.",
    },
    "deepship": {
        "redistribution": "unclear",
        "commercial_use": "unclear",
        "license_reviewed": True,
        "license_notes": "Manual-heavy source; no sampled files in this slice.",
    },
    "oceanship": {
        "redistribution": "unclear",
        "commercial_use": "unclear",
        "license_reviewed": True,
        "license_notes": "Manual-heavy source; no sampled files in this slice.",
    },
    "watkins": {
        "redistribution": "not_allowed",
        "commercial_use": "not_allowed",
        "license_reviewed": True,
        "license_notes": "WMMS mirror/source terms are treated as personal or academic noncommercial; do not redistribute raw clips.",
    },
    "fishsounds": {
        "redistribution": "unclear",
        "commercial_use": "unclear",
        "license_reviewed": True,
        "license_notes": "FishSounds is an index/reference path; verify terms on each linked source before sampling.",
    },
    "noaa_fish_sounds": {
        "redistribution": "allowed",
        "commercial_use": "allowed",
        "license_reviewed": True,
        "license_notes": "NOAA Fisheries says website information may be distributed/copied unless noted; NOAA audio is generally not copyrighted, but attribution and non-endorsement caveats apply.",
    },
    "zenodo_pacama_fish": {
        "redistribution": "allowed",
        "commercial_use": "allowed",
        "license_reviewed": True,
        "license_notes": "Zenodo record declares Creative Commons Attribution 4.0 International.",
    },
    "noaa": {
        "redistribution": "unclear",
        "commercial_use": "unclear",
        "license_reviewed": True,
        "license_notes": "NCEI passive acoustic archive terms vary by collection; no direct samples pulled by this dataset id.",
    },
    "noaa_ocean_sounds": {
        "redistribution": "allowed",
        "commercial_use": "allowed",
        "license_reviewed": True,
        "license_notes": "NOAA Fisheries says website information may be distributed/copied unless noted; NOAA audio is generally not copyrighted, but attribution and non-endorsement caveats apply.",
    },
    "mbari": {
        "redistribution": "unclear",
        "commercial_use": "unclear",
        "license_reviewed": True,
        "license_notes": "MBARI Pacific Sound is open-access public data, but this slice keeps raw/derived audio untracked pending project-specific redistribution review.",
    },
    "wolfset": {
        "redistribution": "allowed",
        "commercial_use": "allowed",
        "license_reviewed": True,
        "license_notes": "Repo-generated synthetic fixtures; never represent synthetic submarine-like waves as real recordings.",
    },
}

LEGACY_ROOT = REPO_ROOT / "dataset" / "hydrophone"
SHIPSEAR_ZIP_URL = "https://huggingface.co/datasets/peng7554/DS3500/resolve/main/ShipsEar.zip"
WATKINS_PARQUET_URL = (
    "https://huggingface.co/datasets/qdskipper/wmms-parquet/resolve/main/data/test-00000-of-00001.parquet"
)
MBARI_KEYS = [
    "2020/01/MARS-20200101T000000Z-2kHz.wav",
    "2020/06/MARS-20200615T000000Z-2kHz.wav",
    "2021/09/MARS-20210921T000000Z-2kHz.wav",
]

NOAA_FISH_CLIPS = [
    {
        "common_name": "Atlantic cod",
        "species": "Gadus morhua",
        "url": "https://www.fisheries.noaa.gov/s3/2023-04/Gamo-grunt-NOAA-PAGroup-03-amplified-atlantic-cod-clip.mp3",
    },
    {
        "common_name": "black drum",
        "species": "Pogonias cromis",
        "url": "https://www.fisheries.noaa.gov/s3/2023-04/Pocr-drumming-Heyman-01-amplified-LPfilter500-black-drum-clip.mp3",
    },
    {
        "common_name": "black grouper",
        "species": "Mycteroperca bonaci",
        "url": "https://www.fisheries.noaa.gov/s3/2023-04/Mybo-pulses-UnivPR-Rowell-01-amplified-black-grouper-clip.mp3",
    },
    {
        "common_name": "haddock",
        "species": "Melanogrammus aeglefinus",
        "url": "https://www.fisheries.noaa.gov/s3/2023-04/Meae-knock-NOAA-PAGroup-01-haddock-clip.mp3",
    },
    {
        "common_name": "red grouper",
        "species": "Epinephelus morio",
        "url": "https://www.fisheries.noaa.gov/s3/2023-04/Epmo-pulses-NOAA-PAGroup-01-red-grouper-clip.mp3",
    },
    {
        "common_name": "silver perch",
        "species": "Bairdiella chrysoura",
        "url": "https://www.fisheries.noaa.gov/s3/2023-04/Bach-knocks-LGL-Heyman-01-silver-perch-clip.mp3",
    },
    {
        "common_name": "toadfish",
        "species": "Opsanus spp.",
        "url": "https://www.fisheries.noaa.gov/s3/2023-04/Opsp-tonal-NOAA-PAGroup-01-amplified-LPfilter500-toadfish-clip.mp3",
    },
]

NOAA_OCEAN_CLIPS = [
    {
        "sub_label": "earthquake",
        "url": "https://www.fisheries.noaa.gov/s3/2023-04/Quake-NOAA-Kline-01-amplified-LPfilter200-earthquake-clip.mp3",
    },
    {
        "sub_label": "ice_calving",
        "url": "https://www.fisheries.noaa.gov/s3/2023-04/Ice-Calving-AWI-Van-Opzeeland-03-ice-calving-clip.mp3",
    },
    {
        "sub_label": "ice_singing",
        "url": "https://www.fisheries.noaa.gov/s3/2023-04/Ice-singing-AWI-Van-Opzeeland-02-ice-singing-clip.mp3",
    },
    {
        "sub_label": "quiet_ocean",
        "url": "https://www.fisheries.noaa.gov/s3/2023-04/Quiet-AWI-Van-Opzeeland-02-quiet-ocean-clip.mp3",
    },
    {
        "sub_label": "rain",
        "url": "https://www.fisheries.noaa.gov/s3/2023-04/Rain-GRNMS-NOAA-PAGroup-02-rain-clip.mp3",
    },
    {
        "sub_label": "soundscape",
        "url": "https://www.fisheries.noaa.gov/s3/2023-04/Sdsc01-HourlySancSdCompiled-GRNMS-NOAA-PAGroup-26-amplified-soundscape-clip.mp3",
    },
    {
        "sub_label": "thunderstorm",
        "url": "https://www.fisheries.noaa.gov/s3/2023-04/Storm-Meno-Fish-Multisound-NOAA-PAGroup-01-amplified-thunderstorm-clip.mp3",
    },
]

ZENODO_PACAMA_FILES = [
    {
        "filename": "DR0000_0178.wav",
        "url": "https://zenodo.org/api/records/14181832/files/DR0000_0178.wav/content",
    },
    {
        "filename": "DR0000_0179.wav",
        "url": "https://zenodo.org/api/records/14181832/files/DR0000_0179.wav/content",
    },
    {
        "filename": "DR0000_0180.wav",
        "url": "https://zenodo.org/api/records/14181832/files/DR0000_0180.wav/content",
    },
]


def _dataset_record(spec: DatasetSpec, *, status: str, access_method: str, notes: str) -> dict[str, Any]:
    review = LICENSE_REVIEWS.get(spec.dataset_id, {})
    return {
        "dataset_id": spec.dataset_id,
        "name": spec.name,
        "source_url": spec.source_url,
        "license": spec.license,
        "redistribution": review.get("redistribution", "unclear"),
        "commercial_use": review.get("commercial_use", "unclear"),
        "license_reviewed": bool(review.get("license_reviewed", False)),
        "license_notes": str(review.get("license_notes", "")),
        "access_method": access_method,
        "status": status,
        "notes": notes,
    }


def _clip_record(
    *,
    clip_id: str,
    dataset_id: str,
    raw_path: Path,
    label: str,
    sub_label: str,
    sample_rate: int,
    duration_sec: float,
    license_text: str,
    source_url: str,
    downloaded_at: str,
    original_filename: str,
    group_id: str | None = None,
    provenance_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provenance = {
        "source_url": source_url,
        "downloaded_at": downloaded_at,
        "original_filename": original_filename,
    }
    if provenance_extra:
        provenance.update(provenance_extra)
    return {
        "clip_id": clip_id,
        "dataset_id": dataset_id,
        "source_path": repo_relative(raw_path),
        "normalized_path": f"data/hydrophone/normalized/{clip_id}.wav",
        "label": label,
        "sub_label": sub_label,
        "sample_rate_hz": int(sample_rate),
        "duration_sec": round(float(duration_sec), 6),
        "group_id": group_id or f"{dataset_id}:{original_filename}",
        "license": license_text,
        "provenance": provenance,
    }


def _copy_legacy_wavs(
    *,
    dataset_id: str,
    source_glob: str,
    raw_root: Path,
    max_files: int,
    spec: DatasetSpec,
    attempts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    source_paths = sorted(LEGACY_ROOT.glob(source_glob))[:max_files]
    if not source_paths:
        return []
    rows: list[dict[str, Any]] = []
    downloaded_at = utc_now_iso()
    target_dir = raw_root / dataset_id
    ensure_dir(target_dir)
    attempts.append(
        {
            "dataset_id": dataset_id,
            "url": f"local:{LEGACY_ROOT / source_glob}",
            "result": "sampled_from_local_cache",
            "detail": f"{len(source_paths)} files copied",
        }
    )
    for idx, src in enumerate(source_paths, start=1):
        suffix = src.suffix.lower() or ".wav"
        dst = target_dir / f"{dataset_id}_{idx:06d}{suffix}"
        shutil.copy2(src, dst)
        sample_rate, duration = read_wav_info(dst)
        sub_label = spec.default_sub_label
        if dataset_id == "watkins":
            sub_label = src.parent.name
        rows.append(
            _clip_record(
                clip_id=f"{dataset_id}_{idx:06d}",
                dataset_id=dataset_id,
                raw_path=dst,
                label=spec.default_label,
                sub_label=sub_label,
                sample_rate=sample_rate,
                duration_sec=duration,
                license_text=spec.license,
                source_url=spec.source_url,
                downloaded_at=downloaded_at,
                original_filename=src.name,
            )
        )
    return rows


def _sample_shipsear_zip(
    *,
    raw_root: Path,
    max_files: int,
    spec: DatasetSpec,
    attempts: list[dict[str, Any]],
    allow_archive_downloads: bool,
) -> list[dict[str, Any]]:
    zip_path = LEGACY_ROOT / "downloads" / "hf_shipsear" / "ShipsEar.zip"
    if not zip_path.exists() and allow_archive_downloads:
        zip_path = raw_root / "shipsear" / "ShipsEar.zip"
        _download_file(SHIPSEAR_ZIP_URL, zip_path, attempts, "shipsear", max_bytes=None)
    if not zip_path.exists():
        attempts.append(
            {
                "dataset_id": "shipsear",
                "url": SHIPSEAR_ZIP_URL,
                "result": "manual_required",
                "detail": "No local ShipsEar ZIP cache found; large archive download skipped by default.",
            }
        )
        return []

    target_dir = raw_root / "shipsear"
    ensure_dir(target_dir)
    rows: list[dict[str, Any]] = []
    downloaded_at = utc_now_iso()
    with zipfile.ZipFile(zip_path) as archive:
        names = sorted(name for name in archive.namelist() if name.lower().endswith(".wav"))
        for idx, name in enumerate(names[:max_files], start=1):
            raw_bytes = archive.read(name)
            dst = target_dir / f"shipsear_{idx:06d}.wav"
            dst.write_bytes(raw_bytes)
            sample_rate, duration = read_wav_info(dst)
            class_part = Path(name).parent.name.lower()
            label = "ambient_ocean" if "environment" in class_part or class_part == "4" else "surface_vessel"
            sub_label = "environmental_noise" if label == "ambient_ocean" else f"shipsear_class_{class_part}"
            rows.append(
                _clip_record(
                    clip_id=f"shipsear_{idx:06d}",
                    dataset_id="shipsear",
                    raw_path=dst,
                    label=label,
                    sub_label=sub_label,
                    sample_rate=sample_rate,
                    duration_sec=duration,
                    license_text=spec.license,
                    source_url=spec.source_url,
                    downloaded_at=downloaded_at,
                    original_filename=name,
                )
            )
    attempts.append(
        {
            "dataset_id": "shipsear",
            "url": f"local:{zip_path}",
            "result": "sampled_from_zip_cache",
            "detail": f"{len(rows)} files extracted",
        }
    )
    return rows


def _sample_watkins_parquet(
    *,
    raw_root: Path,
    max_files: int,
    spec: DatasetSpec,
    attempts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    parquet_path = LEGACY_ROOT / "downloads" / "hf_wmms_parquet" / "test-00000-of-00001.parquet"
    if not parquet_path.exists():
        parquet_path = raw_root / "watkins" / "test-00000-of-00001.parquet"
        try:
            _download_file(WATKINS_PARQUET_URL, parquet_path, attempts, "watkins", max_bytes=80_000_000)
        except Exception as exc:  # noqa: BLE001
            attempts.append(
                {
                    "dataset_id": "watkins",
                    "url": WATKINS_PARQUET_URL,
                    "result": "manual_required",
                    "detail": f"Parquet mirror download failed: {type(exc).__name__}: {exc}",
                }
            )
            return []

    try:
        import pyarrow.parquet as pq
    except Exception as exc:  # noqa: BLE001
        attempts.append(
            {
                "dataset_id": "watkins",
                "url": str(parquet_path),
                "result": "blocked",
                "detail": f"pyarrow unavailable: {type(exc).__name__}: {exc}",
            }
        )
        return []

    target_dir = raw_root / "watkins"
    ensure_dir(target_dir)
    table = pq.read_table(parquet_path, columns=["audio", "species", "label"])
    rows: list[dict[str, Any]] = []
    downloaded_at = utc_now_iso()
    for record in table.to_pylist():
        audio = record.get("audio") or {}
        audio_bytes = audio.get("bytes")
        if not audio_bytes:
            continue
        species = str(record.get("species") or "marine_mammal").lower().replace(" ", "_")
        idx = len(rows) + 1
        dst = target_dir / f"watkins_{idx:06d}.wav"
        dst.write_bytes(audio_bytes)
        sample_rate, duration = read_wav_info(dst)
        rows.append(
            _clip_record(
                clip_id=f"watkins_{idx:06d}",
                dataset_id="watkins",
                raw_path=dst,
                label="biologic_mammal",
                sub_label=species,
                sample_rate=sample_rate,
                duration_sec=duration,
                license_text=spec.license,
                source_url=spec.source_url,
                downloaded_at=downloaded_at,
                original_filename=str(audio.get("path") or dst.name),
            )
        )
        if len(rows) >= max_files:
            break
    attempts.append(
        {
            "dataset_id": "watkins",
            "url": str(parquet_path),
            "result": "sampled_from_parquet",
            "detail": f"{len(rows)} files decoded",
        }
    )
    return rows


def _sample_mbari_range(
    *,
    raw_root: Path,
    max_files: int,
    spec: DatasetSpec,
    attempts: list[dict[str, Any]],
    range_bytes: int,
) -> list[dict[str, Any]]:
    local_rows = _copy_legacy_wavs(
        dataset_id="mbari",
        source_glob="raw/mbari_pacific_sound_2khz/*.wav",
        raw_root=raw_root,
        max_files=max_files,
        spec=spec,
        attempts=attempts,
    )
    if local_rows:
        return local_rows

    try:
        import soundfile as sf
    except Exception as exc:  # noqa: BLE001
        attempts.append(
            {
                "dataset_id": "mbari",
                "url": spec.source_url,
                "result": "blocked",
                "detail": f"soundfile unavailable for range decode: {type(exc).__name__}: {exc}",
            }
        )
        return []

    rows: list[dict[str, Any]] = []
    target_dir = raw_root / "mbari"
    ensure_dir(target_dir)
    downloaded_at = utc_now_iso()
    for key in MBARI_KEYS:
        if len(rows) >= max_files:
            break
        url = f"https://pacific-sound-2khz.s3.amazonaws.com/{key}"
        try:
            content = _download_range(url, range_bytes, attempts, "mbari")
            data, sample_rate = sf.read(io.BytesIO(content), dtype="float32", always_2d=False)
            if data.ndim > 1:
                data = data.mean(axis=1)
            clip_len = max(1, int(sample_rate * 12))
            data = conservative_normalize(data[:clip_len])
            idx = len(rows) + 1
            dst = target_dir / f"mbari_{idx:06d}.wav"
            write_wav(dst, data, int(sample_rate))
            _, duration = read_wav_info(dst)
            rows.append(
                _clip_record(
                    clip_id=f"mbari_{idx:06d}",
                    dataset_id="mbari",
                    raw_path=dst,
                    label="ambient_ocean",
                    sub_label="ambient",
                    sample_rate=sample_rate,
                    duration_sec=duration,
                    license_text=spec.license,
                    source_url=url,
                    downloaded_at=downloaded_at,
                    original_filename=Path(key).name,
                )
            )
        except Exception as exc:  # noqa: BLE001
            attempts.append(
                {
                    "dataset_id": "mbari",
                    "url": url,
                    "result": "manual_required",
                    "detail": f"Range sample failed: {type(exc).__name__}: {exc}",
                }
            )
    return rows


def _sample_noaa_fish_sounds(
    *,
    raw_root: Path,
    max_files: int,
    spec: DatasetSpec,
    attempts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    target_dir = raw_root / "noaa_fish_sounds"
    ensure_dir(target_dir)
    rows: list[dict[str, Any]] = []
    downloaded_at = utc_now_iso()
    for item in NOAA_FISH_CLIPS[:max_files]:
        idx = len(rows) + 1
        original_filename = Path(item["url"]).name
        dst = target_dir / f"noaa_fish_sounds_{idx:06d}.mp3"
        try:
            _download_file(item["url"], dst, attempts, "noaa_fish_sounds", max_bytes=8_000_000)
            sample_rate, duration = read_wav_info(dst)
            rows.append(
                _clip_record(
                    clip_id=f"noaa_fish_sounds_{idx:06d}",
                    dataset_id="noaa_fish_sounds",
                    raw_path=dst,
                    label="biologic_fish",
                    sub_label=str(item["common_name"]).lower().replace(" ", "_"),
                    sample_rate=sample_rate,
                    duration_sec=duration,
                    license_text=spec.license,
                    source_url=item["url"],
                    downloaded_at=downloaded_at,
                    original_filename=original_filename,
                    group_id=f"noaa_fish_sounds:{original_filename}",
                    provenance_extra={
                        "species": item["species"],
                        "site": "NOAA Fisheries Sounds in the Ocean fish page",
                        "deployment": "noaa_web_exemplar",
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            attempts.append(
                {
                    "dataset_id": "noaa_fish_sounds",
                    "url": item["url"],
                    "result": "manual_required",
                    "detail": f"NOAA fish clip failed: {type(exc).__name__}: {exc}",
                }
            )
    return rows


def _sample_noaa_ocean_sounds(
    *,
    raw_root: Path,
    max_files: int,
    spec: DatasetSpec,
    attempts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    target_dir = raw_root / "noaa_ocean_sounds"
    ensure_dir(target_dir)
    rows: list[dict[str, Any]] = []
    downloaded_at = utc_now_iso()
    for item in NOAA_OCEAN_CLIPS[:max_files]:
        idx = len(rows) + 1
        original_filename = Path(item["url"]).name
        dst = target_dir / f"noaa_ocean_sounds_{idx:06d}.mp3"
        try:
            _download_file(item["url"], dst, attempts, "noaa_ocean_sounds", max_bytes=8_000_000)
            sample_rate, duration = read_wav_info(dst)
            rows.append(
                _clip_record(
                    clip_id=f"noaa_ocean_sounds_{idx:06d}",
                    dataset_id="noaa_ocean_sounds",
                    raw_path=dst,
                    label="ambient_ocean",
                    sub_label=str(item["sub_label"]),
                    sample_rate=sample_rate,
                    duration_sec=duration,
                    license_text=spec.license,
                    source_url=item["url"],
                    downloaded_at=downloaded_at,
                    original_filename=original_filename,
                    group_id=f"noaa_ocean_sounds:{original_filename}",
                    provenance_extra={
                        "site": "NOAA Fisheries Sounds in the Ocean environmental page",
                        "deployment": "noaa_web_exemplar",
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            attempts.append(
                {
                    "dataset_id": "noaa_ocean_sounds",
                    "url": item["url"],
                    "result": "manual_required",
                    "detail": f"NOAA ocean clip failed: {type(exc).__name__}: {exc}",
                }
            )
    return rows


def _sample_zenodo_pacama_fish(
    *,
    raw_root: Path,
    max_files: int,
    spec: DatasetSpec,
    attempts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    target_dir = raw_root / "zenodo_pacama_fish"
    ensure_dir(target_dir)
    rows: list[dict[str, Any]] = []
    downloaded_at = utc_now_iso()
    for item in ZENODO_PACAMA_FILES[:max_files]:
        idx = len(rows) + 1
        original_filename = item["filename"]
        dst = target_dir / original_filename
        try:
            _download_file(item["url"], dst, attempts, "zenodo_pacama_fish", max_bytes=12_000_000)
            sample_rate, duration = read_wav_info(dst)
            rows.append(
                _clip_record(
                    clip_id=f"zenodo_pacama_fish_{idx:06d}",
                    dataset_id="zenodo_pacama_fish",
                    raw_path=dst,
                    label="biologic_fish",
                    sub_label="pacama_catfish",
                    sample_rate=sample_rate,
                    duration_sec=duration,
                    license_text=spec.license,
                    source_url=item["url"],
                    downloaded_at=downloaded_at,
                    original_filename=original_filename,
                    group_id=f"zenodo_pacama_fish:{original_filename}",
                    provenance_extra={
                        "species": "Lophiosilurus alexandri",
                        "site": "Zenodo record 14181832",
                        "deployment": "zenodo_dataset_file",
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            attempts.append(
                {
                    "dataset_id": "zenodo_pacama_fish",
                    "url": item["url"],
                    "result": "manual_required",
                    "detail": f"Zenodo pacama file failed: {type(exc).__name__}: {exc}",
                }
            )
    return rows


def _download_file(
    url: str,
    dest: Path,
    attempts: list[dict[str, Any]],
    dataset_id: str,
    *,
    max_bytes: int | None,
) -> None:
    import requests

    ensure_dir(dest.parent)
    if dest.exists() and dest.stat().st_size > 0:
        attempts.append(
            {
                "dataset_id": dataset_id,
                "url": url,
                "result": "cached",
                "detail": f"{dest.stat().st_size} bytes",
            }
        )
        return
    attempts.append({"dataset_id": dataset_id, "url": url, "result": "attempted", "detail": "download"})
    with requests.get(url, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length") or 0)
        if max_bytes is not None and total and total > max_bytes:
            raise RuntimeError(f"remote object is {total} bytes, above cap {max_bytes}")
        written = 0
        tmp = dest.with_suffix(dest.suffix + ".part")
        with tmp.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                written += len(chunk)
                if max_bytes is not None and written > max_bytes:
                    raise RuntimeError(f"download exceeded cap {max_bytes}")
                fh.write(chunk)
        tmp.replace(dest)
    attempts.append({"dataset_id": dataset_id, "url": url, "result": "downloaded", "detail": f"{dest.stat().st_size} bytes"})


def _download_range(
    url: str,
    range_bytes: int,
    attempts: list[dict[str, Any]],
    dataset_id: str,
) -> bytes:
    import requests

    attempts.append({"dataset_id": dataset_id, "url": url, "result": "attempted", "detail": f"bytes=0-{range_bytes - 1}"})
    headers = {"Range": f"bytes=0-{range_bytes - 1}"}
    with requests.get(url, headers=headers, stream=True, timeout=90) as resp:
        resp.raise_for_status()
        chunks: list[bytes] = []
        total = 0
        for chunk in resp.iter_content(chunk_size=256 * 1024):
            if not chunk:
                continue
            remaining = range_bytes - total
            chunks.append(chunk[:remaining])
            total += min(len(chunk), remaining)
            if total >= range_bytes:
                break
    return b"".join(chunks)


def _split_dataset_args(values: list[str] | None) -> list[str]:
    if not values:
        return list(DATASETS)
    selected: list[str] = []
    for value in values:
        for part in value.split(","):
            part = part.strip().lower()
            if part:
                selected.append(part)
    unknown = sorted(set(selected) - set(DATASETS))
    if unknown:
        raise SystemExit(f"Unknown dataset id(s): {', '.join(unknown)}")
    return selected


def _merge_clip_manifest(path: Path, selected: set[str], sampled: list[dict[str, Any]], *, dry_run: bool) -> None:
    if dry_run:
        if not path.exists():
            write_jsonl(path, [])
        return
    existing = read_jsonl(path)
    retained = [row for row in existing if str(row.get("dataset_id")) not in selected]
    write_jsonl(path, retained + sampled)


def _write_readmes(data_root: Path) -> None:
    write_text(
        data_root / "raw_samples" / "README.md",
        """# Raw Hydrophone Samples

This directory is for tiny local samples pulled by `scripts/hydrophone/fetch_hydrophone_samples.py --download`.

Raw audio files are intentionally ignored by git. Track provenance in `data/hydrophone/manifests/*.jsonl` instead.
""",
    )
    write_text(
        data_root / "normalized" / "README.md",
        """# Normalized Hydrophone Clips

This directory stores mono WAV clips produced by `normalize_hydrophone_audio.py`.

Normalized audio files are ignored by git because they are derived dataset artifacts.
""",
    )


def _write_sampling_report(
    *,
    path: Path,
    dataset_rows: list[dict[str, Any]],
    clip_rows: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    dry_run: bool,
) -> None:
    sampled = [row for row in dataset_rows if row["status"] == "sampled"]
    manual = [row for row in dataset_rows if row["status"] in {"manual_required", "blocked"}]
    total_duration = sum(float(row.get("duration_sec") or 0.0) for row in clip_rows)
    counts: dict[str, int] = {}
    for row in clip_rows:
        counts[row["dataset_id"]] = counts.get(row["dataset_id"], 0) + 1

    lines = [
        "# Hydrophone Dataset Sampling Report",
        "",
        f"Generated: {utc_now_iso()}",
        f"Mode: {'dry-run' if dry_run else 'download'}",
        "",
        "## Datasets attempted",
        "",
        "| Dataset | Status | Access | Notes |",
        "|---|---:|---|---|",
    ]
    for row in dataset_rows:
        lines.append(
            f"| {row['name']} (`{row['dataset_id']}`) | {row['status']} | {row['access_method']} | {row['notes']} |"
        )

    lines.extend(["", "## Datasets successfully sampled", ""])
    if sampled:
        for row in sampled:
            lines.append(f"- `{row['dataset_id']}`: {counts.get(row['dataset_id'], 0)} clips.")
    else:
        lines.append("- None in this run.")

    lines.extend(["", "## Datasets requiring manual download", ""])
    if manual:
        for row in manual:
            lines.append(f"- `{row['dataset_id']}`: {row['notes']}")
    else:
        lines.append("- None marked manual/blocked in this run.")

    lines.extend(["", "## License/usage notes found", ""])
    for row in dataset_rows:
        lines.append(f"- `{row['dataset_id']}`: {row['license']}")

    lines.extend(["", "## Attempt log", ""])
    if attempts:
        lines.extend(["| Dataset | URL | Result | Detail |", "|---|---|---:|---|"])
        for attempt in attempts:
            lines.append(
                f"| {attempt['dataset_id']} | {attempt['url']} | {attempt['result']} | {attempt.get('detail', '')} |"
            )
    else:
        lines.append("- No network or local-cache attempts were made.")

    lines.extend(
        [
            "",
            "## File counts",
            "",
            f"- Clip records produced this run: {len(clip_rows)}",
            f"- Total sampled duration: {total_duration:.2f} seconds",
        ]
    )
    for dataset_id, count in sorted(counts.items()):
        lines.append(f"- `{dataset_id}`: {count}")

    lines.extend(
        [
            "",
            "## Recommended next expansion",
            "",
            "- Prefer one source per class with machine-readable license notes before scaling volume.",
            "- Expand MBARI/NOAA ambient clips by deployment group before using broad NOAA archive pulls.",
            "- Add FishSounds/GLUBS records only after choosing specific downloadable references and recording source-level terms.",
            "- Keep submarine-like examples synthetic/simulated and labeled as such.",
        ]
    )
    write_text(path, "\n".join(lines))


def _write_license_review(path: Path, dataset_rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Hydrophone Dataset License Review",
        "",
        f"Generated: {utc_now_iso()}",
        "",
        "This is a conservative engineering review, not legal advice. Raw audio remains untracked by repo policy even when a source appears redistributable.",
        "",
    ]
    for row in dataset_rows:
        lines.extend(
            [
                f"## {row['name']}",
                "",
                f"- Dataset ID: `{row['dataset_id']}`",
                f"- Source URL: {row['source_url']}",
                f"- Access status: {row['status']}",
                f"- License / terms found: {row['license']}",
                f"- Redistribution allowed? {row.get('redistribution', 'unclear')}",
                f"- Commercial use allowed? {row.get('commercial_use', 'unclear')}",
                "- Can raw clips be committed? no",
                f"- Can derived features be committed? {row.get('redistribution', 'unclear')}",
                f"- Notes: {row.get('license_notes') or row.get('notes', '')}",
                "",
            ]
        )
    write_text(path, "\n".join(lines))


def fetch_samples(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    data_root = Path(args.data_root)
    report_root = Path(args.report_root)
    ensure_hydrophone_layout(data_root, report_root)
    _write_readmes(data_root)

    selected = _split_dataset_args(args.datasets)
    dry_run = bool(args.dry_run or not args.download)
    raw_root = data_root / "raw_samples"
    datasets_path = data_root / "manifests" / "datasets.jsonl"
    clips_path = data_root / "manifests" / "clips.jsonl"
    attempts: list[dict[str, Any]] = []
    dataset_rows: list[dict[str, Any]] = []
    clip_rows: list[dict[str, Any]] = []

    for dataset_id in selected:
        spec = DATASETS[dataset_id]
        if dry_run:
            note = f"Dry-run only. {spec.notes}"
            status = "skipped"
            access = "skipped"
            if spec.default_access_method == "manual":
                status = "manual_required"
                access = "manual"
            dataset_rows.append(_dataset_record(spec, status=status, access_method=access, notes=note))
            continue

        rows: list[dict[str, Any]] = []
        if dataset_id == "shipsear":
            rows = _sample_shipsear_zip(
                raw_root=raw_root,
                max_files=args.max_files_per_dataset,
                spec=spec,
                attempts=attempts,
                allow_archive_downloads=args.allow_archive_downloads,
            )
        elif dataset_id == "watkins":
            rows = _copy_legacy_wavs(
                dataset_id="watkins",
                source_glob="raw/hf_wmms_parquet/**/*.wav",
                raw_root=raw_root,
                max_files=args.max_files_per_dataset,
                spec=spec,
                attempts=attempts,
            )
            if not rows:
                rows = _sample_watkins_parquet(
                    raw_root=raw_root,
                    max_files=args.max_files_per_dataset,
                    spec=spec,
                    attempts=attempts,
                )
        elif dataset_id == "mbari":
            rows = _sample_mbari_range(
                raw_root=raw_root,
                max_files=args.max_files_per_dataset,
                spec=spec,
                attempts=attempts,
                range_bytes=args.mbari_range_bytes,
            )
        elif dataset_id == "noaa_fish_sounds":
            rows = _sample_noaa_fish_sounds(
                raw_root=raw_root,
                max_files=args.max_files_per_dataset,
                spec=spec,
                attempts=attempts,
            )
        elif dataset_id == "noaa_ocean_sounds":
            rows = _sample_noaa_ocean_sounds(
                raw_root=raw_root,
                max_files=args.max_files_per_dataset,
                spec=spec,
                attempts=attempts,
            )
        elif dataset_id == "zenodo_pacama_fish":
            rows = _sample_zenodo_pacama_fish(
                raw_root=raw_root,
                max_files=args.max_files_per_dataset,
                spec=spec,
                attempts=attempts,
            )
        elif dataset_id == "wolfset":
            attempts.append(
                {
                    "dataset_id": "wolfset",
                    "url": "scripts/hydrophone/generate_synthetic_waves.py",
                    "result": "skipped",
                    "detail": "Synthetic contacts are generated in the synthetic stage, not fetched as real data.",
                }
            )
        else:
            attempts.append(
                {
                    "dataset_id": dataset_id,
                    "url": spec.source_url,
                    "result": "manual_required",
                    "detail": spec.notes,
                }
            )

        status = "sampled" if rows else ("skipped" if dataset_id == "wolfset" else "manual_required")
        access = spec.default_access_method if rows else ("skipped" if dataset_id == "wolfset" else "manual")
        note = f"Sampled {len(rows)} clips. {spec.notes}" if rows else spec.notes
        dataset_rows.append(_dataset_record(spec, status=status, access_method=access, notes=note))
        clip_rows.extend(rows)

    if dry_run and datasets_path.exists():
        # Dry-runs should report what would be attempted without erasing the last materialized dataset review.
        pass
    else:
        write_jsonl(datasets_path, dataset_rows)
    _merge_clip_manifest(clips_path, set(selected), clip_rows, dry_run=dry_run)
    _write_sampling_report(
        path=report_root / "hydrophone_dataset_sampling_report.md",
        dataset_rows=dataset_rows,
        clip_rows=clip_rows,
        attempts=attempts,
        dry_run=dry_run,
    )
    _write_license_review(report_root / "license_review.md", dataset_rows)
    return dataset_rows, clip_rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch tiny public hydrophone samples into local manifests.")
    parser.add_argument("--download", action="store_true", help="Actually copy/download sample audio. Defaults to dry-run.")
    parser.add_argument("--dry-run", action="store_true", help="Force dry-run even if --download is present.")
    parser.add_argument("--max-files-per-dataset", type=int, default=5)
    parser.add_argument(
        "--datasets",
        nargs="*",
        help="Dataset ids to attempt. Supports comma-separated values. Known: "
        + ", ".join(sorted(DATASETS)),
    )
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--report-root", default=str(DEFAULT_REPORT_ROOT))
    parser.add_argument("--mbari-range-bytes", type=int, default=1_500_000)
    parser.add_argument(
        "--allow-archive-downloads",
        action="store_true",
        help="Permit archive-sized direct downloads such as ShipsEar.zip. Off by default.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.max_files_per_dataset < 0:
        parser.error("--max-files-per-dataset must be non-negative")
    dataset_rows, clip_rows = fetch_samples(args)
    sampled = sum(1 for row in dataset_rows if row["status"] == "sampled")
    print(
        f"hydrophone fetch complete: datasets={len(dataset_rows)} sampled_datasets={sampled} "
        f"clip_records={len(clip_rows)} mode={'dry-run' if (args.dry_run or not args.download) else 'download'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
