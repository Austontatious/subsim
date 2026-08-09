#!/usr/bin/env python3
"""Hydrophone dataset pull + acoustic category analyzer for Subsim."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import math
import random
import re
import hashlib
import itertools
import sys
import wave
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import soundfile as sf
from scipy import signal
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = REPO_ROOT / "dataset" / "hydrophone"

TOP_LEVEL_CATEGORIES = [
    "marine_mammal_whale",
    "marine_mammal_orca",
    "marine_mammal_other",
    "marine_life_other",
    "surface_vessel",
    "ambient_soundscape",
    "weather_geophony",
    "anthropogenic_non_vessel",
    "machinery_noise",
    "unknown_contact_like",
    "submarine_like_archetype_inspiration",
]

SAFE_ARCHETYPES = [
    "quiet_contact_archetype",
    "intermittent_machinery_archetype",
    "low_observable_contact_like",
    "noisy_contact_like",
    "unknown_quiet_contact",
]


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_") or "unknown"


def stable_short_hash(*parts: str, n: int = 12) -> str:
    digest = hashlib.sha1("||".join(parts).encode("utf-8")).hexdigest()
    return digest[:n]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=False)
        f.write("\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=False))
            f.write("\n")


def download_file(url: str, dest: Path, *, force: bool = False, timeout: int = 120) -> dict[str, Any]:
    ensure_dir(dest.parent)
    if dest.exists() and not force:
        return {
            "status": "cached",
            "path": str(dest),
            "size_bytes": dest.stat().st_size,
        }

    tmp = dest.with_suffix(dest.suffix + ".part")
    if tmp.exists():
        tmp.unlink()

    with requests.get(url, stream=True, timeout=timeout) as resp:
        resp.raise_for_status()
        with tmp.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    fh.write(chunk)

    tmp.replace(dest)
    return {
        "status": "downloaded",
        "path": str(dest),
        "size_bytes": dest.stat().st_size,
    }


class HydrophonePipeline:
    def __init__(
        self,
        root: Path,
        manifest_path: Path,
        taxonomy_path: Path,
        *,
        force_download: bool = False,
        limit_per_source: int | None = None,
        verbose: bool = False,
    ) -> None:
        self.root = root
        self.manifest_path = manifest_path
        self.taxonomy_path = taxonomy_path
        self.force_download = force_download
        self.limit_per_source = limit_per_source
        self.verbose = verbose

        self.downloads_dir = root / "downloads"
        self.raw_dir = root / "raw"
        self.staging_dir = root / "staging"
        self.features_dir = root / "features"
        self.analysis_dir = root / "analysis"
        self.reports_dir = root / "reports"

        self.pull_records_path = self.staging_dir / "pulled_samples.jsonl"
        self.pull_status_path = self.root / "hydrophone_pull_status.json"
        self.index_path = self.root / "hydrophone_dataset_index.jsonl"
        self.features_csv_path = self.features_dir / "hydrophone_features.csv"
        self.features_jsonl_path = self.features_dir / "hydrophone_features.jsonl"
        self.cluster_csv_path = self.analysis_dir / "hydrophone_clusters.csv"
        self.exemplars_json_path = self.analysis_dir / "hydrophone_category_exemplars.json"
        self.analysis_json_path = self.reports_dir / "hydrophone_category_analysis_report.json"
        self.analysis_md_path = self.reports_dir / "hydrophone_category_analysis_report.md"
        self.gap_json_path = self.reports_dir / "hydrophone_dataset_gap_report.json"
        self.gap_md_path = self.reports_dir / "hydrophone_dataset_gap_report.md"

        ensure_dir(self.root)
        ensure_dir(self.downloads_dir)
        ensure_dir(self.raw_dir)
        ensure_dir(self.staging_dir)
        ensure_dir(self.features_dir)
        ensure_dir(self.analysis_dir)
        ensure_dir(self.reports_dir)

        self.manifest = read_json(self.manifest_path)
        self.taxonomy = read_json(self.taxonomy_path)

    def log(self, msg: str) -> None:
        print(msg)

    def debug(self, msg: str) -> None:
        if self.verbose:
            print(msg)

    # ------------------------------------------------------------------
    # Pull phase
    # ------------------------------------------------------------------
    def pull(self) -> dict[str, Any]:
        all_records: list[dict[str, Any]] = []
        source_status: list[dict[str, Any]] = []

        for source in self.manifest.get("sources", []):
            source_id = source.get("source_id", "unknown_source")
            enabled = bool(source.get("enabled", True))
            if not enabled:
                source_status.append(
                    {
                        "source_id": source_id,
                        "status": "skipped",
                        "reason": "disabled",
                        "pulled_count": 0,
                    }
                )
                continue

            adapter_name = source.get("adapter", "metadata_only")
            self.log(f"[pull] {source_id}: adapter={adapter_name}")
            start = dt.datetime.now(dt.timezone.utc)
            records: list[dict[str, Any]] = []
            status = "ok"
            error_text = ""

            try:
                if adapter_name == "hf_parquet_audio_bytes":
                    records = self._pull_hf_parquet_audio_bytes(source)
                elif adapter_name == "hf_zip_class_dirs":
                    records = self._pull_hf_zip_class_dirs(source)
                elif adapter_name == "http_wav_range_extract":
                    records = self._pull_http_wav_range_extract(source)
                elif adapter_name == "metadata_only":
                    records = []
                else:
                    raise ValueError(f"Unsupported adapter: {adapter_name}")
            except Exception as exc:  # noqa: BLE001
                status = "error"
                error_text = f"{type(exc).__name__}: {exc}"

            elapsed_s = (dt.datetime.now(dt.timezone.utc) - start).total_seconds()
            source_status.append(
                {
                    "source_id": source_id,
                    "name": source.get("name"),
                    "adapter": adapter_name,
                    "pull_mode": source.get("pull_mode"),
                    "status": status,
                    "error": error_text,
                    "pulled_count": len(records),
                    "elapsed_s": round(elapsed_s, 3),
                    "metadata_only": source.get("pull_mode") == "metadata_only",
                }
            )
            all_records.extend(records)
            self.log(f"[pull] {source_id}: status={status}, pulled={len(records)}")

        write_jsonl(self.pull_records_path, all_records)
        pull_status = {
            "pipeline_stage": "pull",
            "generated_utc": utc_now_iso(),
            "manifest_path": str(self.manifest_path),
            "pull_records_path": str(self.pull_records_path),
            "source_status": source_status,
            "pulled_total": len(all_records),
        }
        write_json(self.pull_status_path, pull_status)
        return pull_status

    def _apply_source_limit(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if self.limit_per_source is None:
            return rows
        return rows[: max(0, self.limit_per_source)]

    def _pull_hf_parquet_audio_bytes(self, source: dict[str, Any]) -> list[dict[str, Any]]:
        source_id = source["source_id"]
        repo = source["repository"]
        cfg = source.get("config", {})
        parquet_files = cfg.get("parquet_files", [])
        max_rows = int(cfg.get("max_rows", 100))
        rng = random.Random(int(cfg.get("shuffle_seed", 0)))

        records: list[dict[str, Any]] = []
        source_dl_dir = self.downloads_dir / source_id
        ensure_dir(source_dl_dir)

        rows_needed = max_rows
        for rel_path in parquet_files:
            if rows_needed <= 0:
                break
            filename = Path(rel_path).name
            url = f"https://huggingface.co/datasets/{repo}/resolve/main/{rel_path}"
            local_parquet = source_dl_dir / filename
            dl_info = download_file(url, local_parquet, force=self.force_download)
            self.debug(f"[pull:{source_id}] parquet={filename} {dl_info['status']} size={dl_info['size_bytes']}")

            frame = pd.read_parquet(local_parquet)
            idxs = list(range(len(frame)))
            rng.shuffle(idxs)

            for idx in idxs:
                if rows_needed <= 0:
                    break
                row = frame.iloc[idx]
                audio_blob = row.get("audio")
                if not isinstance(audio_blob, dict):
                    continue
                wav_bytes = audio_blob.get("bytes")
                original_name = str(audio_blob.get("path") or f"row_{idx}.wav")
                if wav_bytes is None:
                    continue
                species = str(row.get("species") or "unknown_species")
                label_id = int(row.get("label")) if row.get("label") is not None else None

                species_slug = slugify(species)
                base_stem = Path(original_name).stem or f"row_{idx}"
                sample_hash = stable_short_hash(source_id, rel_path, str(idx), original_name)
                out_name = f"{slugify(base_stem)}_{sample_hash}.wav"
                out_path = self.raw_dir / source_id / species_slug / out_name
                ensure_dir(out_path.parent)
                out_path.write_bytes(wav_bytes)

                sample_id = f"{source_id}_{sample_hash}"
                records.append(
                    {
                        "sample_id": sample_id,
                        "source_id": source_id,
                        "source_name": source.get("name"),
                        "source_dataset": repo,
                        "source_homepage": source.get("homepage_url"),
                        "source_license": source.get("license"),
                        "source_region": cfg.get("region"),
                        "local_audio_path": str(out_path.resolve()),
                        "original_label": species,
                        "original_label_id": label_id,
                        "original_label_type": "species",
                        "source_record_ref": f"{rel_path}#{idx}",
                        "source_audio_ref": original_name,
                        "collection_context": "marine_mammal_calls",
                        "ingested_utc": utc_now_iso(),
                    }
                )
                rows_needed -= 1

        return self._apply_source_limit(records)

    def _pull_hf_zip_class_dirs(self, source: dict[str, Any]) -> list[dict[str, Any]]:
        source_id = source["source_id"]
        cfg = source.get("config", {})
        zip_url = cfg["zip_url"]
        max_per_class = int(cfg.get("max_per_class", 20))
        class_label_map = cfg.get("class_label_map", {})
        rng = random.Random(int(cfg.get("shuffle_seed", 0)))

        local_zip = self.downloads_dir / source_id / Path(zip_url).name
        dl_info = download_file(zip_url, local_zip, force=self.force_download)
        self.debug(f"[pull:{source_id}] zip={local_zip.name} {dl_info['status']} size={dl_info['size_bytes']}")

        with zipfile.ZipFile(local_zip) as zf:
            wav_members = [m for m in zf.namelist() if m.lower().endswith(".wav")]
            by_class: dict[str, list[str]] = defaultdict(list)
            for member in wav_members:
                parts = Path(member).parts
                class_token = next((p for p in parts if p.isdigit()), None)
                if class_token is None:
                    continue
                by_class[class_token].append(member)

            records: list[dict[str, Any]] = []
            for class_id in sorted(by_class):
                members = by_class[class_id]
                rng.shuffle(members)
                picked = members[:max_per_class]
                class_slug = f"class_{class_id}"
                human_label = class_label_map.get(class_id, class_slug)

                for member in picked:
                    wav_bytes = zf.read(member)
                    sample_hash = stable_short_hash(source_id, member)
                    out_name = f"{Path(member).stem}_{sample_hash}.wav"
                    out_path = self.raw_dir / source_id / class_slug / out_name
                    ensure_dir(out_path.parent)
                    out_path.write_bytes(wav_bytes)

                    sample_id = f"{source_id}_{sample_hash}"
                    records.append(
                        {
                            "sample_id": sample_id,
                            "source_id": source_id,
                            "source_name": source.get("name"),
                            "source_dataset": source.get("repository"),
                            "source_homepage": source.get("homepage_url"),
                            "source_license": source.get("license"),
                            "source_region": cfg.get("region"),
                            "local_audio_path": str(out_path.resolve()),
                            "original_label": human_label,
                            "original_label_id": int(class_id),
                            "original_label_type": "shipsear_class",
                            "source_record_ref": member,
                            "source_audio_ref": member,
                            "collection_context": "ship_radiated_noise",
                            "ingested_utc": utc_now_iso(),
                        }
                    )

        return self._apply_source_limit(records)

    def _pull_http_wav_range_extract(self, source: dict[str, Any]) -> list[dict[str, Any]]:
        source_id = source["source_id"]
        cfg = source.get("config", {})
        bucket = cfg["bucket"]
        keys = cfg.get("keys", [])
        range_bytes = int(cfg.get("range_bytes", 4_000_000))
        clip_seconds = int(cfg.get("clip_seconds", 120))
        clips_per_file = int(cfg.get("clips_per_file", 2))

        records: list[dict[str, Any]] = []
        for key in keys:
            url = f"https://{bucket}.s3.amazonaws.com/{key}"
            headers = {"Range": f"bytes=0-{range_bytes - 1}"}
            resp = requests.get(url, headers=headers, timeout=120)
            resp.raise_for_status()
            blob = resp.content

            with wave.open(io.BytesIO(blob), "rb") as wf:
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                sample_rate = wf.getframerate()
                frames_per_clip = int(sample_rate * clip_seconds)

                for clip_idx in range(clips_per_file):
                    clip_frames = wf.readframes(frames_per_clip)
                    if len(clip_frames) < int(frames_per_clip * channels * sample_width * 0.75):
                        break
                    key_stem = Path(key).stem
                    sample_hash = stable_short_hash(source_id, key, str(clip_idx))
                    out_name = f"{slugify(key_stem)}_clip{clip_idx + 1}_{sample_hash}.wav"
                    out_path = self.raw_dir / source_id / out_name
                    ensure_dir(out_path.parent)

                    with wave.open(str(out_path), "wb") as out_wav:
                        out_wav.setnchannels(channels)
                        out_wav.setsampwidth(sample_width)
                        out_wav.setframerate(sample_rate)
                        out_wav.writeframes(clip_frames)

                    sample_id = f"{source_id}_{sample_hash}"
                    records.append(
                        {
                            "sample_id": sample_id,
                            "source_id": source_id,
                            "source_name": source.get("name"),
                            "source_dataset": source.get("name"),
                            "source_homepage": source.get("homepage_url"),
                            "source_license": source.get("license"),
                            "source_region": cfg.get("region"),
                            "local_audio_path": str(out_path.resolve()),
                            "original_label": "mbari_unlabeled_soundscape",
                            "original_label_id": None,
                            "original_label_type": "unlabeled",
                            "source_record_ref": key,
                            "source_audio_ref": f"{url}#clip={clip_idx + 1}",
                            "collection_context": "deep_ocean_soundscape",
                            "ingested_utc": utc_now_iso(),
                        }
                    )

        return self._apply_source_limit(records)

    # ------------------------------------------------------------------
    # Normalize phase
    # ------------------------------------------------------------------
    def normalize(self) -> dict[str, Any]:
        pulled_rows = read_jsonl(self.pull_records_path)
        if not pulled_rows:
            raise RuntimeError("No pulled samples found. Run pull first.")

        normalized_rows: list[dict[str, Any]] = []
        skipped_missing = 0

        for row in pulled_rows:
            audio_path = Path(row["local_audio_path"])
            if not audio_path.exists():
                skipped_missing += 1
                continue

            resolved_audio_path = audio_path.resolve()
            try:
                rel_audio_path = str(resolved_audio_path.relative_to(REPO_ROOT))
            except ValueError:
                rel_audio_path = str(resolved_audio_path)

            info = sf.info(str(audio_path))
            mapped = self._map_taxonomy(row)

            normalized_rows.append(
                {
                    "sample_id": row["sample_id"],
                    "source_id": row["source_id"],
                    "source_dataset": row.get("source_dataset"),
                    "source_name": row.get("source_name"),
                    "source_homepage": row.get("source_homepage"),
                    "source_license": row.get("source_license"),
                    "file_path": str(resolved_audio_path),
                    "file_path_relative": rel_audio_path,
                    "category_label": mapped["category_label"],
                    "category_labels": mapped["category_labels"],
                    "original_label": row.get("original_label"),
                    "original_label_id": row.get("original_label_id"),
                    "original_label_type": row.get("original_label_type"),
                    "label_quality": mapped["label_quality"],
                    "label_origin": mapped["label_origin"],
                    "duration_s": round(float(info.duration), 6),
                    "sample_rate_hz": int(info.samplerate),
                    "channel_count": int(info.channels),
                    "region": row.get("source_region"),
                    "collection_context": row.get("collection_context"),
                    "source_record_ref": row.get("source_record_ref"),
                    "source_audio_ref": row.get("source_audio_ref"),
                    "safety_bucket": mapped["safety_bucket"],
                    "ingested_utc": row.get("ingested_utc"),
                    "normalized_utc": utc_now_iso(),
                }
            )

        write_jsonl(self.index_path, normalized_rows)

        category_counts = Counter(r["category_label"] for r in normalized_rows)
        summary = {
            "pipeline_stage": "normalize",
            "generated_utc": utc_now_iso(),
            "input_pull_records": len(pulled_rows),
            "normalized_records": len(normalized_rows),
            "skipped_missing_files": skipped_missing,
            "category_counts": dict(sorted(category_counts.items())),
            "index_path": str(self.index_path),
        }
        self.log(
            f"[normalize] rows={summary['normalized_records']} skipped_missing={summary['skipped_missing_files']}"
        )
        return summary

    def _map_taxonomy(self, row: dict[str, Any]) -> dict[str, Any]:
        source_id = row.get("source_id", "")
        label = str(row.get("original_label") or "")
        label_l = label.lower()

        if source_id == "hf_wmms_parquet":
            if "killer_whale" in label_l or "orca" in label_l:
                return {
                    "category_label": "marine_mammal_orca",
                    "category_labels": ["marine_mammal_orca", "marine_mammal_whale"],
                    "label_quality": "exact",
                    "label_origin": "direct",
                    "safety_bucket": "non_contact_or_natural",
                }
            if "whale" in label_l:
                return {
                    "category_label": "marine_mammal_whale",
                    "category_labels": ["marine_mammal_whale"],
                    "label_quality": "exact",
                    "label_origin": "direct",
                    "safety_bucket": "non_contact_or_natural",
                }
            mammal_tokens = ["dolphin", "seal", "walrus", "beluga", "narwhal", "pilot"]
            if any(tok in label_l for tok in mammal_tokens):
                return {
                    "category_label": "marine_mammal_other",
                    "category_labels": ["marine_mammal_other"],
                    "label_quality": "exact",
                    "label_origin": "direct",
                    "safety_bucket": "non_contact_or_natural",
                }
            return {
                "category_label": "marine_life_other",
                "category_labels": ["marine_life_other"],
                "label_quality": "coarse",
                "label_origin": "inferred",
                "safety_bucket": "non_contact_or_natural",
            }

        if source_id == "hf_shipsear":
            class_id = str(row.get("original_label_id"))
            if class_id == "4":
                return {
                    "category_label": "ambient_soundscape",
                    "category_labels": ["ambient_soundscape"],
                    "label_quality": "exact",
                    "label_origin": "direct",
                    "safety_bucket": "non_contact_or_natural",
                }
            return {
                "category_label": "surface_vessel",
                "category_labels": ["surface_vessel", "machinery_noise"],
                "label_quality": "coarse",
                "label_origin": "direct",
                "safety_bucket": "contact_like_public_non_military",
            }

        if source_id == "mbari_pacific_sound_2khz":
            return {
                "category_label": "ambient_soundscape",
                "category_labels": ["ambient_soundscape", "unknown_contact_like"],
                "label_quality": "inferred",
                "label_origin": "inferred",
                "safety_bucket": "mixed_open_soundscape",
            }

        return {
            "category_label": "unknown_contact_like",
            "category_labels": ["unknown_contact_like"],
            "label_quality": "unknown",
            "label_origin": "unknown",
            "safety_bucket": "unknown",
        }

    # ------------------------------------------------------------------
    # Feature extraction phase
    # ------------------------------------------------------------------
    def extract_features(self) -> dict[str, Any]:
        rows = read_jsonl(self.index_path)
        if not rows:
            raise RuntimeError("No normalized index rows found. Run normalize first.")

        feature_rows: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []

        for idx, row in enumerate(rows, start=1):
            sample_id = row["sample_id"]
            path = Path(row["file_path"])
            try:
                feat = self._compute_features(path)
                feat_row = {
                    "sample_id": sample_id,
                    "source_id": row.get("source_id"),
                    "category_label": row.get("category_label"),
                    "label_quality": row.get("label_quality"),
                    "file_path": row.get("file_path"),
                    **feat,
                }
                feat_row["safe_archetype_tag"] = self._infer_safe_archetype(feat_row)
                feature_rows.append(feat_row)
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    {
                        "sample_id": sample_id,
                        "file_path": str(path),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            if idx % 50 == 0:
                self.log(f"[features] processed {idx}/{len(rows)}")

        if not feature_rows:
            raise RuntimeError("Feature extraction produced zero rows.")

        frame = pd.DataFrame(feature_rows)
        frame.to_csv(self.features_csv_path, index=False)
        write_jsonl(self.features_jsonl_path, feature_rows)

        summary = {
            "pipeline_stage": "features",
            "generated_utc": utc_now_iso(),
            "input_rows": len(rows),
            "feature_rows": len(feature_rows),
            "failure_rows": len(failures),
            "features_csv_path": str(self.features_csv_path),
            "features_jsonl_path": str(self.features_jsonl_path),
        }
        if failures:
            write_json(self.features_dir / "feature_failures.json", {"rows": failures})
        self.log(
            f"[features] extracted={summary['feature_rows']} failures={summary['failure_rows']}"
        )
        return summary

    def _compute_features(self, audio_path: Path) -> dict[str, Any]:
        y, sr = sf.read(str(audio_path), dtype="float32", always_2d=False)
        if isinstance(y, np.ndarray) and y.ndim == 2:
            y = np.mean(y, axis=1)
        if not isinstance(y, np.ndarray):
            y = np.asarray(y, dtype=np.float32)
        if y.size == 0:
            raise ValueError("empty audio")

        y = y.astype(np.float32)
        y = y - float(np.mean(y))

        full_duration = float(y.size / sr)
        max_seconds = 20.0
        max_samples = int(sr * max_seconds)
        if y.size > max_samples:
            y = y[:max_samples]

        duration = float(y.size / sr)
        eps = 1e-12

        rms = float(np.sqrt(np.mean(np.square(y)) + eps))
        zcr = float(np.mean(y[:-1] * y[1:] < 0)) if y.size > 1 else 0.0

        nperseg = max(128, min(2048, int(sr * 0.1)))
        noverlap = nperseg // 2
        freqs, _, spec_mag = signal.spectrogram(
            y,
            fs=sr,
            window="hann",
            nperseg=nperseg,
            noverlap=noverlap,
            mode="magnitude",
            scaling="spectrum",
        )

        power = np.square(spec_mag) + eps
        frame_energy = np.sum(power, axis=0) + eps

        centroids = np.sum(freqs[:, None] * power, axis=0) / frame_energy
        bandwidth = np.sqrt(np.sum(np.square(freqs[:, None] - centroids[None, :]) * power, axis=0) / frame_energy)

        cumsum = np.cumsum(power, axis=0)
        roll_thresh = 0.85 * frame_energy
        roll_idx = np.argmax(cumsum >= roll_thresh, axis=0)
        rolloff = freqs[roll_idx]

        flatness = np.exp(np.mean(np.log(power), axis=0)) / np.mean(power, axis=0)

        mean_psd = np.mean(power, axis=1)
        dominant_idx = int(np.argmax(mean_psd))
        dominant_freq_hz = float(freqs[dominant_idx])
        harmonicity = float(np.max(mean_psd) / (np.median(mean_psd) + eps))

        total_band = float(np.sum(mean_psd) + eps)
        low_ratio = float(np.sum(mean_psd[freqs < 200.0]) / total_band)
        mid_ratio = float(np.sum(mean_psd[(freqs >= 200.0) & (freqs < 1000.0)]) / total_band)
        high_ratio = float(np.sum(mean_psd[freqs >= 1000.0]) / total_band)

        if power.shape[1] > 1:
            flux = np.sqrt(np.sum(np.square(np.diff(power, axis=1).clip(min=0.0)), axis=0))
            spectral_flux = float(np.mean(flux))
        else:
            spectral_flux = 0.0

        env = np.abs(signal.hilbert(y))
        env_norm = env / (float(np.max(env)) + eps)
        env_mean = float(np.mean(env_norm))
        env_std = float(np.std(env_norm))

        mod_freqs, mod_psd = signal.welch(env_norm, fs=sr, nperseg=min(len(env_norm), max(256, int(sr * 2))))
        mod_mask = (mod_freqs >= 0.1) & (mod_freqs <= 20.0)
        if np.any(mod_mask):
            local_freqs = mod_freqs[mod_mask]
            local_psd = mod_psd[mod_mask]
            dominant_mod_hz = float(local_freqs[int(np.argmax(local_psd))])
        else:
            dominant_mod_hz = 0.0

        onset = np.diff(env_norm, prepend=env_norm[0])
        onset_pos = np.clip(onset, 0.0, None)
        threshold = float(np.mean(onset_pos) + 2.0 * np.std(onset_pos))
        min_distance = max(1, int(sr * 0.05))
        peaks, _ = signal.find_peaks(onset_pos, height=threshold, distance=min_distance)
        transient_density = float(len(peaks) / max(duration, eps))

        if len(peaks) >= 2:
            intervals = np.diff(peaks) / sr
            inter_event_interval_s = float(np.median(intervals))
        else:
            inter_event_interval_s = 0.0

        roughness = float(spectral_flux / (rms + eps))
        narrowband_index = float(max(0.0, min(1.0, 1.0 - float(np.mean(flatness)))))

        return {
            "duration_s": round(duration, 6),
            "full_duration_s": round(full_duration, 6),
            "sample_rate_hz": int(sr),
            "rms": rms,
            "zero_crossing_rate": zcr,
            "spectral_centroid_hz": float(np.mean(centroids)),
            "spectral_rolloff_hz": float(np.mean(rolloff)),
            "spectral_bandwidth_hz": float(np.mean(bandwidth)),
            "spectral_flatness": float(np.mean(flatness)),
            "dominant_freq_hz": dominant_freq_hz,
            "harmonicity": harmonicity,
            "low_band_ratio": low_ratio,
            "mid_band_ratio": mid_ratio,
            "high_band_ratio": high_ratio,
            "envelope_mean": env_mean,
            "envelope_std": env_std,
            "dominant_mod_hz": dominant_mod_hz,
            "transient_density": transient_density,
            "inter_event_interval_s": inter_event_interval_s,
            "spectral_flux": spectral_flux,
            "roughness": roughness,
            "narrowband_index": narrowband_index,
        }

    def _infer_safe_archetype(self, row: dict[str, Any]) -> str:
        category = row.get("category_label")
        if category not in {"surface_vessel", "machinery_noise", "unknown_contact_like"}:
            return ""

        dominant_freq = float(row.get("dominant_freq_hz", 0.0))
        flatness = float(row.get("spectral_flatness", 0.0))
        transient_density = float(row.get("transient_density", 0.0))
        low_ratio = float(row.get("low_band_ratio", 0.0))

        if dominant_freq < 180 and flatness < 0.25 and transient_density < 1.5:
            return "quiet_contact_archetype"
        if transient_density >= 3.5:
            return "intermittent_machinery_archetype"
        if low_ratio > 0.75 and flatness < 0.2:
            return "low_observable_contact_like"
        if dominant_freq > 500 or flatness > 0.35:
            return "noisy_contact_like"
        return "unknown_quiet_contact"

    # ------------------------------------------------------------------
    # Analysis phase
    # ------------------------------------------------------------------
    def analyze(self) -> dict[str, Any]:
        df = pd.read_csv(self.features_csv_path)
        if df.empty:
            raise RuntimeError("Feature CSV is empty. Run features first.")

        numeric_cols = [
            "rms",
            "zero_crossing_rate",
            "spectral_centroid_hz",
            "spectral_rolloff_hz",
            "spectral_bandwidth_hz",
            "spectral_flatness",
            "dominant_freq_hz",
            "harmonicity",
            "low_band_ratio",
            "mid_band_ratio",
            "high_band_ratio",
            "envelope_mean",
            "envelope_std",
            "dominant_mod_hz",
            "transient_density",
            "inter_event_interval_s",
            "spectral_flux",
            "roughness",
            "narrowband_index",
        ]
        for col in numeric_cols:
            if col not in df.columns:
                raise RuntimeError(f"Missing numeric feature column: {col}")

        X = df[numeric_cols].to_numpy(dtype=np.float64)
        scaler = StandardScaler()
        Xs = scaler.fit_transform(X)

        pca = PCA(n_components=2, random_state=7)
        pca_xy = pca.fit_transform(Xs)
        df["pca_x"] = pca_xy[:, 0]
        df["pca_y"] = pca_xy[:, 1]

        n = len(df)
        if n >= 6:
            k = min(8, max(2, int(round(math.sqrt(n / 2)))))
            if k >= n:
                k = max(2, n - 1)
            kmeans = KMeans(n_clusters=k, random_state=7, n_init=10)
            labels = kmeans.fit_predict(Xs)
            df["cluster_id"] = labels
            sil = float(silhouette_score(Xs, labels)) if len(set(labels)) > 1 else None
        else:
            k = 1
            df["cluster_id"] = 0
            sil = None

        df.to_csv(self.cluster_csv_path, index=False)

        exemplars = self._select_exemplars(df, numeric_cols)
        write_json(self.exemplars_json_path, exemplars)

        overlap = self._compute_category_overlap(df, numeric_cols)
        archetype_counts = Counter(tag for tag in df["safe_archetype_tag"].fillna("") if tag)

        category_stats = self._category_stats(df)
        renderer_recos = self._renderer_recommendations(df, category_stats)

        analysis_payload = {
            "report_version": "hydrophone_category_analysis.v1",
            "generated_utc": utc_now_iso(),
            "sample_count": int(len(df)),
            "source_count": int(df["source_id"].nunique()),
            "category_count": int(df["category_label"].nunique()),
            "cluster_count": int(k),
            "silhouette_score": sil,
            "pca_explained_variance_ratio": [float(v) for v in pca.explained_variance_ratio_],
            "category_stats": category_stats,
            "category_overlap": overlap,
            "safe_archetype_distribution": dict(sorted(archetype_counts.items())),
            "renderer_recommendations": renderer_recos,
            "exemplars_path": str(self.exemplars_json_path),
            "clusters_path": str(self.cluster_csv_path),
            "safety_note": "Contact-like archetypes are abstract acoustic buckets only, not real-world military signature identification classes.",
        }
        write_json(self.analysis_json_path, analysis_payload)

        self._write_pca_plot(df)

        self.log(
            f"[analyze] samples={analysis_payload['sample_count']} clusters={analysis_payload['cluster_count']}"
        )
        return analysis_payload

    def _write_pca_plot(self, df: pd.DataFrame) -> None:
        plt.figure(figsize=(10, 7))
        categories = sorted(df["category_label"].unique())
        cmap = plt.get_cmap("tab20", len(categories))
        for i, cat in enumerate(categories):
            sub = df[df["category_label"] == cat]
            plt.scatter(sub["pca_x"], sub["pca_y"], s=24, alpha=0.75, label=cat, color=cmap(i))
        plt.title("Hydrophone Feature PCA (v1)")
        plt.xlabel("PCA-1")
        plt.ylabel("PCA-2")
        plt.legend(loc="best", fontsize=8)
        plt.tight_layout()
        out = self.analysis_dir / "hydrophone_pca_scatter.png"
        plt.savefig(out, dpi=160)
        plt.close()

    def _select_exemplars(self, df: pd.DataFrame, numeric_cols: list[str]) -> dict[str, Any]:
        exemplars: dict[str, Any] = {
            "generated_utc": utc_now_iso(),
            "categories": {},
        }

        for cat in sorted(df["category_label"].unique()):
            sub = df[df["category_label"] == cat].copy()
            if sub.empty:
                continue
            X = sub[numeric_cols].to_numpy(dtype=np.float64)
            centroid = X.mean(axis=0)
            dists = np.linalg.norm(X - centroid[None, :], axis=1)
            nearest_idx = int(np.argmin(dists))
            farthest_idx = int(np.argmax(dists))
            nearest = sub.iloc[nearest_idx]
            farthest = sub.iloc[farthest_idx]

            exemplars["categories"][cat] = {
                "count": int(len(sub)),
                "representative_sample_id": nearest["sample_id"],
                "representative_file_path": nearest["file_path"],
                "outlier_sample_id": farthest["sample_id"],
                "outlier_file_path": farthest["file_path"],
            }

        return exemplars

    def _compute_category_overlap(self, df: pd.DataFrame, numeric_cols: list[str]) -> dict[str, Any]:
        cats = sorted(df["category_label"].unique())
        if len(cats) < 2:
            return {"pairs": [], "nearest_centroid_confusion": {}}

        scaler = StandardScaler()
        X = scaler.fit_transform(df[numeric_cols].to_numpy(dtype=np.float64))

        centroids: dict[str, np.ndarray] = {}
        for cat in cats:
            sub_idx = np.where(df["category_label"].to_numpy() == cat)[0]
            centroids[cat] = X[sub_idx].mean(axis=0)

        pairs = []
        for a, b in itertools.combinations(cats, 2):
            dist = float(np.linalg.norm(centroids[a] - centroids[b]))
            pairs.append({"category_a": a, "category_b": b, "centroid_distance": dist})
        pairs.sort(key=lambda x: x["centroid_distance"])

        predicted = []
        true_labels = df["category_label"].tolist()
        for row_vec in X:
            best_cat = min(cats, key=lambda c: float(np.linalg.norm(row_vec - centroids[c])))
            predicted.append(best_cat)

        confusion = defaultdict(lambda: defaultdict(int))
        for t, p in zip(true_labels, predicted):
            confusion[t][p] += 1

        confusion_summary: dict[str, Any] = {}
        for cat in cats:
            row = confusion[cat]
            total = sum(row.values())
            correct = row.get(cat, 0)
            confusion_summary[cat] = {
                "total": total,
                "correct": correct,
                "nearest_centroid_misclass_rate": float(1.0 - (correct / total)) if total else 0.0,
                "top_confusions": sorted(
                    [
                        {"predicted_category": k, "count": v}
                        for k, v in row.items()
                        if k != cat
                    ],
                    key=lambda r: r["count"],
                    reverse=True,
                )[:3],
            }

        return {
            "pairs": pairs[:12],
            "nearest_centroid_confusion": confusion_summary,
        }

    def _category_stats(self, df: pd.DataFrame) -> dict[str, Any]:
        stats: dict[str, Any] = {}
        feature_means = [
            "spectral_centroid_hz",
            "spectral_rolloff_hz",
            "spectral_flatness",
            "dominant_freq_hz",
            "dominant_mod_hz",
            "transient_density",
            "inter_event_interval_s",
            "low_band_ratio",
            "narrowband_index",
        ]

        for cat in sorted(df["category_label"].unique()):
            sub = df[df["category_label"] == cat]
            source_counts = Counter(sub["source_id"].tolist())
            quality_counts = Counter(sub["label_quality"].tolist())

            means = {k: float(sub[k].mean()) for k in feature_means if k in sub.columns}
            medians = {k: float(sub[k].median()) for k in feature_means if k in sub.columns}

            stats[cat] = {
                "count": int(len(sub)),
                "source_counts": dict(sorted(source_counts.items())),
                "label_quality_counts": dict(sorted(quality_counts.items())),
                "duration_median_s": float(sub["duration_s"].median()),
                "feature_means": means,
                "feature_medians": medians,
            }

        return stats

    def _renderer_recommendations(self, df: pd.DataFrame, stats: dict[str, Any]) -> dict[str, Any]:
        recommendations: dict[str, Any] = {}

        for category, detail in stats.items():
            count = detail["count"]
            means = detail["feature_means"]
            medians = detail["feature_medians"]

            if category in {"marine_mammal_whale", "marine_mammal_orca", "marine_mammal_other"}:
                mode = "hybrid_procedural_with_exemplar_grains"
                params = {
                    "carrier_band_hint_hz": round(medians.get("dominant_freq_hz", 0.0), 2),
                    "modulation_hint_hz": round(medians.get("dominant_mod_hz", 0.0), 3),
                    "cadence_hint_s": round(medians.get("inter_event_interval_s", 0.0), 3),
                    "tonality_hint": round(medians.get("narrowband_index", 0.0), 3),
                }
            elif category == "surface_vessel":
                mode = "parametric_machinery_and_cavitation_layers"
                params = {
                    "low_band_ratio_hint": round(means.get("low_band_ratio", 0.0), 3),
                    "roughness_hint": round(means.get("roughness", 0.0), 3),
                    "transient_density_hint": round(means.get("transient_density", 0.0), 3),
                }
            elif category in {"ambient_soundscape", "weather_geophony"}:
                mode = "texture_bed_synthesis_with_spectral_controls"
                params = {
                    "spectral_flatness_hint": round(means.get("spectral_flatness", 0.0), 3),
                    "centroid_hint_hz": round(means.get("spectral_centroid_hz", 0.0), 2),
                    "modulation_hint_hz": round(means.get("dominant_mod_hz", 0.0), 3),
                }
            elif category in {"anthropogenic_non_vessel", "machinery_noise", "unknown_contact_like"}:
                mode = "hybrid_noise_plus_event_templates"
                params = {
                    "transient_density_hint": round(means.get("transient_density", 0.0), 3),
                    "bandwidth_hint_hz": round(means.get("spectral_rolloff_hz", 0.0), 2),
                }
            else:
                mode = "sparse_or_unresolved"
                params = {}

            data_strength = "covered" if count >= 40 else "thin" if count >= 10 else "sparse"
            recommendations[category] = {
                "sample_count": count,
                "data_strength": data_strength,
                "suggested_render_mode": mode,
                "parameter_hints": params,
            }

        return recommendations

    # ------------------------------------------------------------------
    # Reporting phase
    # ------------------------------------------------------------------
    def report(self) -> dict[str, Any]:
        analysis = read_json(self.analysis_json_path)
        index_rows = read_jsonl(self.index_path)

        self._write_category_report_markdown(analysis)
        gap_payload = self._write_gap_reports(index_rows)

        summary = {
            "pipeline_stage": "report",
            "generated_utc": utc_now_iso(),
            "analysis_json_path": str(self.analysis_json_path),
            "analysis_md_path": str(self.analysis_md_path),
            "gap_json_path": str(self.gap_json_path),
            "gap_md_path": str(self.gap_md_path),
            "sample_count": len(index_rows),
            "covered_categories": [
                cat for cat, details in gap_payload["category_gaps"].items() if details["coverage_status"] != "missing"
            ],
        }
        self.log("[report] wrote category and gap reports")
        return summary

    def _write_category_report_markdown(self, analysis: dict[str, Any]) -> None:
        lines: list[str] = []
        lines.append("# Hydrophone Category Analysis Report")
        lines.append("")
        lines.append(f"Generated: {analysis.get('generated_utc')}")
        lines.append("")
        lines.append("## Scope")
        lines.append("")
        lines.append(
            "This report summarizes the v1 Subsim hydrophone ingestion/analyzer pass over a bounded subset of open/public underwater-acoustic sources."
        )
        lines.append("")
        lines.append("## Corpus Summary")
        lines.append("")
        lines.append(f"- Samples analyzed: {analysis.get('sample_count', 0)}")
        lines.append(f"- Source datasets: {analysis.get('source_count', 0)}")
        lines.append(f"- Categories present: {analysis.get('category_count', 0)}")
        lines.append(f"- Cluster count (k-means): {analysis.get('cluster_count', 0)}")
        sil = analysis.get("silhouette_score")
        lines.append(f"- Silhouette score: {sil if sil is not None else 'n/a'}")
        lines.append("")

        lines.append("## Category Findings")
        lines.append("")
        cat_stats = analysis.get("category_stats", {})
        for category in sorted(cat_stats):
            c = cat_stats[category]
            reco = analysis.get("renderer_recommendations", {}).get(category, {})
            lines.append(f"### {category}")
            lines.append("")
            lines.append(f"- Count: {c.get('count', 0)}")
            lines.append(f"- Source mix: {json.dumps(c.get('source_counts', {}), sort_keys=True)}")
            lines.append(f"- Label quality: {json.dumps(c.get('label_quality_counts', {}), sort_keys=True)}")
            lines.append(f"- Suggested render mode: {reco.get('suggested_render_mode', 'n/a')}")
            hints = reco.get("parameter_hints", {})
            if hints:
                lines.append(f"- Parameter hints: {json.dumps(hints, sort_keys=True)}")
            lines.append("")

        lines.append("## Overlap / Confusion Risk")
        lines.append("")
        overlap = analysis.get("category_overlap", {})
        pairs = overlap.get("pairs", [])
        if pairs:
            lines.append("Closest category centroids (higher overlap risk):")
            for pair in pairs[:8]:
                dist = round(pair.get("centroid_distance", 0.0), 4)
                lines.append(f"- {pair['category_a']} vs {pair['category_b']}: centroid distance {dist}")
        else:
            lines.append("- Not enough category diversity for centroid overlap analysis.")
        lines.append("")

        lines.append("## Safe Contact-Like Archetypes")
        lines.append("")
        lines.append(
            "The analyzer emits only abstract archetype tags (for example `quiet_contact_archetype`, `intermittent_machinery_archetype`) and does not build nation/class-specific military signature labels."
        )
        archetypes = analysis.get("safe_archetype_distribution", {})
        lines.append(f"- Distribution: {json.dumps(archetypes, sort_keys=True)}")
        lines.append("")

        lines.append("## Practical Takeaways For Renderer Design")
        lines.append("")
        lines.append("- Marine mammal categories are suitable for hybrid procedural generation anchored by exemplar fragments.")
        lines.append("- Surface vessel classes are suitable for parametric low-band machinery/cavitation style rendering.")
        lines.append("- Ambient beds are suitable for layered texture synthesis with spectral and modulation controls.")
        lines.append("- Sparse categories should remain synthetic or deferred until additional curated data is pulled.")
        lines.append("")

        self.analysis_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_gap_reports(self, index_rows: list[dict[str, Any]]) -> dict[str, Any]:
        primary_counts = Counter(row.get("category_label", "unknown") for row in index_rows)
        inclusive_counts = Counter()
        for row in index_rows:
            labels = row.get("category_labels") or []
            if isinstance(labels, list):
                for label in labels:
                    inclusive_counts[str(label)] += 1

        gap_payload: dict[str, Any] = {
            "report_version": "hydrophone_dataset_gap_report.v1",
            "generated_utc": utc_now_iso(),
            "total_indexed_samples": len(index_rows),
            "category_gaps": {},
            "source_status": read_json(self.pull_status_path).get("source_status", []),
        }

        for cat in TOP_LEVEL_CATEGORIES:
            count_primary = int(primary_counts.get(cat, 0))
            count_inclusive = int(inclusive_counts.get(cat, 0))
            if count_inclusive >= 40:
                status = "well_covered"
            elif count_inclusive >= 15:
                status = "moderate"
            elif count_inclusive >= 1:
                status = "thin"
            else:
                status = "missing"

            gap_payload["category_gaps"][cat] = {
                "primary_count": count_primary,
                "inclusive_count": count_inclusive,
                "coverage_status": status,
            }

        manual_sources = [
            s
            for s in self.manifest.get("sources", [])
            if s.get("pull_mode") == "metadata_only"
        ]
        gap_payload["metadata_only_sources"] = [
            {
                "source_id": s.get("source_id"),
                "name": s.get("name"),
                "manual_steps": s.get("config", {}).get("manual_steps", []),
            }
            for s in manual_sources
        ]

        write_json(self.gap_json_path, gap_payload)

        lines: list[str] = []
        lines.append("# Hydrophone Dataset Gap Report")
        lines.append("")
        lines.append(f"Generated: {gap_payload['generated_utc']}")
        lines.append("")
        lines.append("## Coverage Snapshot")
        lines.append("")
        for cat in TOP_LEVEL_CATEGORIES:
            row = gap_payload["category_gaps"][cat]
            lines.append(
                f"- {cat}: {row['inclusive_count']} inclusive samples "
                f"(primary={row['primary_count']}, status={row['coverage_status']})"
            )
        lines.append("")

        lines.append("## Gaps That Matter For Subsim")
        lines.append("")
        lines.append("- `weather_geophony` remains thin/missing in this v1 subset and needs dedicated source pulls.")
        lines.append("- `anthropogenic_non_vessel` remains thin/missing and needs explicit harbor/industrial/noise-event sets.")
        lines.append("- `submarine_like_archetype_inspiration` is intentionally not sourced from real military signatures; derive this only as abstract procedural archetypes.")
        lines.append("")

        if gap_payload["metadata_only_sources"]:
            lines.append("## Metadata-Only Sources Pending Manual Follow-Up")
            lines.append("")
            for s in gap_payload["metadata_only_sources"]:
                lines.append(f"### {s['source_id']}")
                lines.append("")
                for step in s.get("manual_steps", []):
                    lines.append(f"- {step}")
                lines.append("")

        lines.append("## Recommended Next Pulls")
        lines.append("")
        lines.append("- Add a weather/geophony-focused hydrophone subset (storms, rain, seismic/ice where available).")
        lines.append("- Add a curated anthropogenic non-vessel subset (fixed machinery, offshore infrastructure, harbor clutter).")
        lines.append("- Keep contact-like categories abstract and game-oriented instead of platform-specific.")
        lines.append("")

        self.gap_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return gap_payload

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate(self) -> dict[str, Any]:
        checks = {
            "manifest_exists": self.manifest_path.exists(),
            "taxonomy_exists": self.taxonomy_path.exists(),
            "pull_records_exists": self.pull_records_path.exists(),
            "index_exists": self.index_path.exists(),
            "features_csv_exists": self.features_csv_path.exists(),
            "analysis_json_exists": self.analysis_json_path.exists(),
            "analysis_md_exists": self.analysis_md_path.exists(),
            "gap_json_exists": self.gap_json_path.exists(),
            "gap_md_exists": self.gap_md_path.exists(),
        }

        missing = [k for k, ok in checks.items() if not ok]
        index_rows = read_jsonl(self.index_path) if self.index_path.exists() else []
        feature_rows = pd.read_csv(self.features_csv_path) if self.features_csv_path.exists() else pd.DataFrame()

        summary = {
            "generated_utc": utc_now_iso(),
            "checks": checks,
            "missing_checks": missing,
            "index_rows": len(index_rows),
            "feature_rows": int(len(feature_rows)),
            "category_count": int(len({r.get('category_label') for r in index_rows})),
        }

        if missing:
            raise RuntimeError(f"Validation failed; missing artifacts: {', '.join(missing)}")
        if not index_rows:
            raise RuntimeError("Validation failed; normalized index is empty")
        if feature_rows.empty:
            raise RuntimeError("Validation failed; feature table is empty")

        self.log(
            f"[validate] ok index_rows={summary['index_rows']} feature_rows={summary['feature_rows']}"
        )
        return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Subsim Hydrophone Dataset Pull + Analyzer")
    parser.add_argument(
        "command",
        choices=["pull", "normalize", "features", "analyze", "report", "validate", "run-all"],
        help="Pipeline command",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="Pipeline root directory (default: dataset/hydrophone)",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_ROOT / "hydrophone_sources_manifest.json",
        help="Source manifest path",
    )
    parser.add_argument(
        "--taxonomy",
        type=Path,
        default=DEFAULT_ROOT / "hydrophone_taxonomy.json",
        help="Taxonomy config path",
    )
    parser.add_argument("--force-download", action="store_true", help="Redownload remote artifacts")
    parser.add_argument(
        "--limit-per-source",
        type=int,
        default=None,
        help="Optional hard cap on records kept per source during pull",
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose logs")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    pipeline = HydrophonePipeline(
        root=args.root,
        manifest_path=args.manifest,
        taxonomy_path=args.taxonomy,
        force_download=args.force_download,
        limit_per_source=args.limit_per_source,
        verbose=args.verbose,
    )

    command = args.command
    if command == "pull":
        payload = pipeline.pull()
    elif command == "normalize":
        payload = pipeline.normalize()
    elif command == "features":
        payload = pipeline.extract_features()
    elif command == "analyze":
        payload = pipeline.analyze()
    elif command == "report":
        payload = pipeline.report()
    elif command == "validate":
        payload = pipeline.validate()
    elif command == "run-all":
        pull_payload = pipeline.pull()
        normalize_payload = pipeline.normalize()
        feature_payload = pipeline.extract_features()
        analysis_payload = pipeline.analyze()
        report_payload = pipeline.report()
        validate_payload = pipeline.validate()
        payload = {
            "run_all_utc": utc_now_iso(),
            "pull": pull_payload,
            "normalize": normalize_payload,
            "features": feature_payload,
            "analysis": {
                "sample_count": analysis_payload.get("sample_count"),
                "cluster_count": analysis_payload.get("cluster_count"),
            },
            "report": report_payload,
            "validate": validate_payload,
        }
        write_json(pipeline.root / "run_all_summary.json", payload)
    else:
        raise RuntimeError(f"Unknown command: {command}")

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
