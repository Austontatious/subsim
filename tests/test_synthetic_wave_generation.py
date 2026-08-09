from __future__ import annotations

from pathlib import Path

from scripts.hydrophone.generate_synthetic_waves import SUBLIKE_DISCLAIMER, generate_synthetic_dataset
from scripts.hydrophone.hydrophone_common import read_jsonl, read_wav_info


def test_synthetic_generator_writes_valid_wavs_and_manifest(tmp_path: Path) -> None:
    waves_dir = tmp_path / "waves"
    manifest_path = tmp_path / "manifest.jsonl"
    report_path = tmp_path / "synthetic_report.md"

    rows = generate_synthetic_dataset(
        count=9,
        sample_rate=8000,
        duration_sec=1.25,
        waves_dir=waves_dir,
        manifest_path=manifest_path,
        report_path=report_path,
        seed=99,
    )

    manifest_rows = read_jsonl(manifest_path)
    assert len(rows) == len(manifest_rows) == 9
    assert report_path.exists()
    for row in manifest_rows:
        path = Path(row["path"])
        assert path.exists()
        sample_rate, duration = read_wav_info(path)
        assert sample_rate == 8000
        assert abs(duration - 1.25) < 1.0 / sample_rate
        assert row["sample_rate_hz"] == 8000
        assert row["duration_sec"] == 1.25
        if row["label"] == "synthetic_submarine_like":
            assert row["disclaimer"] == SUBLIKE_DISCLAIMER
