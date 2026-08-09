"""Tiny consumer example that emulates ReadyPlayer1-style stream consumption."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from .console import FixtureConfig, SonarConsole
from .contracts import SonarConsoleFrame
from .features import top_label


@dataclass
class BeliefTrack:
    track_id: str
    threat_score: float = 0.0
    last_seen_t: float = 0.0
    label: str = "unknown"


@dataclass
class PlaytesterBeliefState:
    tracks: Dict[str, BeliefTrack] = field(default_factory=dict)
    engage_recommendations: int = 0

    def update(self, frame: SonarConsoleFrame) -> None:
        for track in frame.tracks:
            label = top_label(track.classification_probs) or "unknown"
            threat_score = track.classification_probs.get("hunter", 0.0) * track.contact_quality
            belief = self.tracks.setdefault(track.track_id, BeliefTrack(track_id=track.track_id))
            belief.last_seen_t = frame.t
            belief.label = label
            belief.threat_score = max(belief.threat_score * 0.9, threat_score)
            if belief.threat_score >= 0.45 and not track.lost:
                self.engage_recommendations += 1


def run_stub_playtester(*, fixture: FixtureConfig) -> PlaytesterBeliefState:
    console = SonarConsole()
    run = console.run_fixture(fixture)
    state = PlaytesterBeliefState()
    for frame in run.perceived_frames:
        state.update(frame)
    return state


__all__ = ["BeliefTrack", "PlaytesterBeliefState", "run_stub_playtester"]
