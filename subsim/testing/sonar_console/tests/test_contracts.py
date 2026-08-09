from subsim.testing.sonar_console.contracts import (
    GroundTruthFrame,
    OwnshipSensorContext,
    PerceivedTrack,
    SonarConsoleFrame,
    SonarEvent,
    TruthEntity,
)


def test_contract_roundtrip_serialization() -> None:
    ownship = OwnshipSensorContext(
        heading_deg=90.0,
        speed_mps=4.0,
        depth_m=-120.0,
        pitch=0.1,
        roll=0.0,
        self_noise=0.2,
        self_noise_bucket="low",
        sensor_noise=0.1,
        ping_cooldown_s=1.5,
        ping_active=False,
        thermocline_side="above",
        masking=False,
    )
    track = PerceivedTrack(
        track_id="T001",
        first_seen_at=1.0,
        last_updated_at=2.0,
        bearing_deg_estimate=40.0,
        bearing_confidence=0.8,
        bearing_rate_deg_per_min=12.0,
        signal_strength=0.5,
        signal_strength_trend=0.03,
        doppler_estimate=0.2,
        classification_probs={"hunter": 0.7, "merchant": 0.1, "unknown": 0.2},
        contact_quality=0.6,
        intermittent=False,
        faded=False,
        lost=False,
        ambiguity_flags=[],
        source_channels=["passive"],
        history_window_summary={"window_samples": 2.0},
    )
    event = SonarEvent(event_type="contact_detected", tick=3, t=0.1, track_id="T001", severity="info", details={})
    fire_control = {
        "schema_version": "subsim.fire_control.v1",
        "fire_control_solution_state": "ready",
        "fire_control_ready": True,
        "fire_control_solution_quality": 0.8,
    }
    frame = SonarConsoleFrame(
        tick=3,
        t=0.1,
        ownship=ownship,
        tracks=[track],
        events=[event],
        fire_control=fire_control,
    )
    truth = GroundTruthFrame(
        tick=3,
        t=0.1,
        entities=[
            TruthEntity(
                entity_id="enemy-1",
                kind="hunter",
                bearing_deg_true=41.0,
                range_m_true=550.0,
                course_deg_true=91.0,
                speed_mps_true=4.5,
                depth_m_true=-150.0,
                detectability=0.4,
                occlusion_layers=0,
                matched_track_id="T001",
            )
        ],
    )

    assert SonarConsoleFrame.from_dict(frame.to_dict()) == frame
    assert frame.to_dict()["fire_control"] == fire_control
    assert GroundTruthFrame.from_dict(truth.to_dict()) == truth
