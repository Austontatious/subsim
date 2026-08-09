from subsim.engine.sensors import PassiveContact, PingReturn
from subsim.testing.sonar_console.contracts import OwnshipSensorContext
from subsim.testing.sonar_console.perception import PerceptionEngine


def test_repeated_weak_passive_track_resolves_as_clutter() -> None:
    engine = PerceptionEngine()
    track = _passive_contact("weak-clutter", confidence=0.50, gain=0.30)

    frames = [
        engine.update(
            tick=tick,
            t=tick * 0.2,
            passive_tracks=[track],
            ping_returns=[],
            ownship=_ownship(),
            classification_scores={"weak-clutter": 0.42},
        )
        for tick in range(1, 5)
    ]

    first_track = frames[0][0][0]
    second_track = frames[1][0][0]
    third_tracks, third_events, _ = frames[2]
    third_track = third_tracks[0]
    fourth_tracks = frames[3][0]

    assert first_track.ambiguity_flags == ["possible_contact"]
    assert first_track.lifecycle_state == "possible"
    assert first_track.bearing_confidence < track.confidence
    assert first_track.lost is False
    assert "suspect_contact" in second_track.ambiguity_flags
    assert second_track.lifecycle_state == "suspect"
    assert second_track.faded is True
    assert "clutter" in third_track.ambiguity_flags
    assert "unconfirmed_contact" in third_track.ambiguity_flags
    assert third_track.lifecycle_state == "rejected"
    assert third_track.lost is True
    assert third_track.contact_quality < second_track.contact_quality
    assert any(
        event.event_type == "clutter_rejected"
        and event.details.get("reason") == "unconfirmed_passive_clutter"
        for event in third_events
    )
    assert fourth_tracks == []


def test_strengthening_passive_track_stays_actionable() -> None:
    engine = PerceptionEngine()
    samples = [
        _passive_contact("hunter", confidence=0.42, gain=0.29),
        _passive_contact("hunter", confidence=0.55, gain=0.37),
        _passive_contact("hunter", confidence=0.68, gain=0.47),
    ]

    tracks = []
    for tick, sample in enumerate(samples, start=1):
        frame_tracks, _, _ = engine.update(
            tick=tick,
            t=tick * 0.2,
            passive_tracks=[sample],
            ping_returns=[],
            ownship=_ownship(),
            classification_scores={"hunter": 0.58 + (tick * 0.08)},
        )
        tracks.append(frame_tracks[0])

    assert tracks[0].lost is False
    assert tracks[-1].lost is False
    assert "clutter" not in tracks[-1].ambiguity_flags
    assert "suspect_contact" not in tracks[-1].ambiguity_flags
    assert tracks[-1].lifecycle_state == "confirmed"
    assert tracks[-1].contact_quality > tracks[0].contact_quality


def test_active_ping_confirms_weak_passive_track() -> None:
    engine = PerceptionEngine()
    frame_tracks, _, _ = engine.update(
        tick=1,
        t=0.2,
        passive_tracks=[_passive_contact("pinged", confidence=0.40, gain=0.28)],
        ping_returns=[
            PingReturn(
                contact_id="pinged",
                delay_s=0.6,
                range_m=450.0,
                bearing_deg=45.0,
                atten=0.8,
            )
        ],
        ownship=_ownship(ping_active=True),
        classification_scores={"pinged": 0.35},
    )

    track = frame_tracks[0]
    assert track.lost is False
    assert "possible_contact" not in track.ambiguity_flags
    assert "clutter" not in track.ambiguity_flags
    assert track.lifecycle_state == "confirmed"
    assert track.source_channels == ["passive", "active_ping"]


def _ownship(*, ping_active: bool = False) -> OwnshipSensorContext:
    return OwnshipSensorContext(
        heading_deg=90.0,
        speed_mps=4.0,
        depth_m=170.0,
        pitch=0.0,
        roll=0.0,
        self_noise=0.25,
        self_noise_bucket="low",
        sensor_noise=0.12,
        ping_cooldown_s=0.0,
        ping_active=ping_active,
        thermocline_side="above",
        masking=ping_active,
    )


def _passive_contact(contact_id: str, *, confidence: float, gain: float) -> PassiveContact:
    return PassiveContact(
        contact_id=contact_id,
        azimuth_deg=45.0,
        distance_m=1200.0,
        confidence=confidence,
        gain=gain,
        occlusion_layers=0,
    )
