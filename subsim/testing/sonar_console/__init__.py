"""Machine-readable sonar console for AI playtesting instrumentation."""

from .console import FixtureConfig, SonarConsole, SonarRun
from .contracts import (
    GroundTruthFrame,
    OwnshipSensorContext,
    PerceivedTrack,
    SonarConsoleFrame,
    SonarEvent,
    TrackTruthAlignment,
    TruthEntity,
)
from .replay import load_jsonl, replay_jsonl, write_jsonl
from .scoring import ScoreSummary, align_frame, align_streams, score_alignment, score_run

__all__ = [
    "FixtureConfig",
    "GroundTruthFrame",
    "OwnshipSensorContext",
    "PerceivedTrack",
    "ScoreSummary",
    "SonarConsole",
    "SonarConsoleFrame",
    "SonarEvent",
    "SonarRun",
    "TrackTruthAlignment",
    "TruthEntity",
    "align_frame",
    "align_streams",
    "load_jsonl",
    "replay_jsonl",
    "score_alignment",
    "score_run",
    "write_jsonl",
]
