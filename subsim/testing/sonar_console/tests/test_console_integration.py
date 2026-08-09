from dataclasses import replace
from pathlib import Path

from subsim.acoustic_contract import own_noise_bucket
from subsim.testing.sonar_console.console import SonarConsole


FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "skirmish_seed_7.json"


def test_fixture_emits_perceived_and_truth_streams() -> None:
    console = SonarConsole()
    fixture = console.load_fixture(FIXTURE_PATH)
    run = console.run_fixture(fixture)

    assert run.perceived_frames
    assert len(run.perceived_frames) == len(run.truth_frames)

    seen_track = any(frame.tracks for frame in run.perceived_frames)
    assert seen_track, "fixture should yield at least one perceived track"

    for frame in run.perceived_frames:
        serialized = frame.to_dict()
        assert "entities" not in serialized
        for track in serialized["tracks"]:
            assert "entity_id" not in track
            assert "kind" not in track
            assert "range_m_true" not in track

    for frame in run.truth_frames:
        assert frame.entities
        serialized = frame.to_dict()
        assert "tracks" not in serialized

    for frame in run.perceived_frames:
        assert frame.ownship.self_noise_bucket == own_noise_bucket(frame.ownship.self_noise)


def test_fixture_deterministic_across_runs() -> None:
    console_a = SonarConsole()
    fixture = console_a.load_fixture(FIXTURE_PATH)
    fixture = replace(fixture, ticks=80)

    run_a = console_a.run_fixture(fixture)
    console_b = SonarConsole()
    run_b = console_b.run_fixture(fixture)

    assert [frame.to_dict() for frame in run_a.perceived_frames] == [frame.to_dict() for frame in run_b.perceived_frames]
    assert [frame.to_dict() for frame in run_a.truth_frames] == [frame.to_dict() for frame in run_b.truth_frames]
