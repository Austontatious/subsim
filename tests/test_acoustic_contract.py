from subsim.acoustic_contract import (
    build_foundation_state,
    own_noise_bucket,
    pick_contact_variant,
)


def test_foundation_state_monotonic_with_own_noise() -> None:
    low = build_foundation_state(own_noise=0.1, sensor_noise=0.05, ping_active=False)
    high = build_foundation_state(own_noise=0.8, sensor_noise=0.05, ping_active=False)
    assert high.self_noise_level > low.self_noise_level
    assert high.player_hum_level > low.player_hum_level
    assert low.own_noise_bucket == "low"
    assert high.own_noise_bucket == "high"


def test_ping_masking_reduces_foundation_levels() -> None:
    base = build_foundation_state(own_noise=0.4, sensor_noise=0.2, ping_active=False)
    ping = build_foundation_state(own_noise=0.4, sensor_noise=0.2, ping_active=True)
    assert ping.masking
    assert ping.ambient_level <= base.ambient_level


def test_contact_variant_selection_uses_confidence_occlusion_and_noise() -> None:
    assert pick_contact_variant(confidence=0.95, occlusion_layers=0, own_noise=0.1) == "clean"
    assert pick_contact_variant(confidence=0.6, occlusion_layers=0, own_noise=0.3) in {"clean", "lp1", "lp2"}
    assert pick_contact_variant(confidence=0.2, occlusion_layers=1, own_noise=0.8) in {"lp2", "lp3"}


def test_own_noise_bucket_boundaries() -> None:
    assert own_noise_bucket(0.0) == "low"
    assert own_noise_bucket(0.3) == "medium"
    assert own_noise_bucket(0.9) == "high"
