from pathlib import Path

from subsim.replay import compare_traces, load_trace, run_trace


def test_golden_skirmish_trace():
    golden_path = Path(__file__).parent / "golden" / "skirmish_seed_7.json"
    golden = load_trace(golden_path)
    actual = run_trace(seed=7, difficulty="normal", ticks=180)
    result = compare_traces(golden, actual)
    assert result.ok, result.message
