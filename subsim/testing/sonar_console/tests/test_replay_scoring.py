from dataclasses import replace
from pathlib import Path

from subsim.testing.sonar_console.console import SonarConsole
from subsim.testing.sonar_console.playtester_stub import run_stub_playtester
from subsim.testing.sonar_console.replay import replay_jsonl, write_jsonl
from subsim.testing.sonar_console.scoring import score_run


FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "skirmish_seed_7.json"


def test_replay_roundtrip_and_scoring(tmp_path) -> None:
    console = SonarConsole()
    fixture = replace(console.load_fixture(FIXTURE_PATH), ticks=90)
    run = console.run_fixture(fixture)

    out_path = write_jsonl(
        path=tmp_path / "sonar_console.jsonl",
        perceived_frames=run.perceived_frames,
        truth_frames=run.truth_frames,
        actions=run.actions,
    )
    perceived, truth, actions = replay_jsonl(out_path)
    assert [frame.to_dict() for frame in perceived] == [frame.to_dict() for frame in run.perceived_frames]
    assert [frame.to_dict() for frame in truth] == [frame.to_dict() for frame in run.truth_frames]
    assert len(actions) == len(run.actions)

    summary, rows = score_run(perceived_frames=perceived, truth_frames=truth)
    assert rows
    assert summary.aligned_samples > 0
    assert 0.0 <= summary.false_positive_rate <= 1.0
    assert summary.track_persistence >= 0.0


def test_playtester_stub_consumes_perceived_stream() -> None:
    console = SonarConsole()
    fixture = replace(console.load_fixture(FIXTURE_PATH), ticks=70)
    state = run_stub_playtester(fixture=fixture)
    assert state.tracks
    assert state.engage_recommendations >= 0
