from pathlib import Path

from subsim.assets import ensure_assets
from subsim.config import ASSET_VARIANTS


def test_ensure_assets_creates_variants(tmp_path: Path) -> None:
    assets = ensure_assets(tmp_path / "sfx")
    assert assets, "expected asset mapping"
    for name, variants in assets.items():
        assert set(variants.keys()) == set(ASSET_VARIANTS)
        for variant, wav in variants.items():
            assert wav.exists()
            assert wav.stat().st_size > 256


def test_assets_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "sfx"
    first = ensure_assets(target)
    timestamps = {wav: wav.stat().st_mtime for mapping in first.values() for wav in mapping.values()}
    second = ensure_assets(target)
    for mapping in second.values():
        for wav in mapping.values():
            assert wav.stat().st_mtime == timestamps[wav]
