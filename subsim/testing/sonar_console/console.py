"""Orchestration layer for machine-readable sonar console production."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from ...acoustic_contract import build_foundation_state
from ...config import FRAME_DT, THERMOCLINE_DEPTH_M
from ...events import EVENT_PING, EVENT_RETURN
from ...game import Game
from ...input import Action
from .contracts import GroundTruthFrame, OwnshipSensorContext, SonarConsoleFrame, SonarEvent
from .ground_truth import build_ground_truth_frame
from .perception import PerceptionEngine


@dataclass(frozen=True)
class FixtureConfig:
    name: str
    seed: int
    difficulty: str
    ticks: int
    agent: str | None = None
    mode: str = "skirmish"

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FixtureConfig":
        return cls(
            name=str(payload["name"]),
            seed=int(payload["seed"]),
            difficulty=str(payload["difficulty"]),
            ticks=int(payload["ticks"]),
            agent=str(payload["agent"]) if payload.get("agent") else None,
            mode=str(payload.get("mode", "skirmish")),
        )


@dataclass
class SonarRun:
    fixture: FixtureConfig
    perceived_frames: list[SonarConsoleFrame]
    truth_frames: list[GroundTruthFrame]
    actions: list[dict[str, Any]]


class SonarConsole:
    """Main producer for perceived and truth streams."""

    def __init__(
        self,
        *,
        history_window: int = 12,
        detection_threshold: float = 0.12,
    ) -> None:
        self.perception = PerceptionEngine(
            history_window=history_window,
            detection_threshold=detection_threshold,
        )

    def step(
        self,
        *,
        tick: int,
        t: float,
        ownship: OwnshipSensorContext,
        passive_tracks,
        ping_returns,
        contacts,
        world,
        classification_scores: Mapping[str, float],
        game_events: Sequence[Mapping[str, Any]],
        fire_control: Mapping[str, Any] | None = None,
    ) -> tuple[SonarConsoleFrame, GroundTruthFrame]:
        perceived_tracks, derived_events, source_to_track = self.perception.update(
            tick=tick,
            t=t,
            passive_tracks=passive_tracks,
            ping_returns=ping_returns,
            ownship=ownship,
            classification_scores=classification_scores,
        )
        frame_events = list(derived_events)
        frame_events.extend(self._translate_game_events(tick=tick, t=t, game_events=game_events, source_to_track=source_to_track))

        perceived_frame = SonarConsoleFrame(
            tick=tick,
            t=t,
            ownship=ownship,
            tracks=perceived_tracks,
            events=frame_events,
            fire_control=dict(fire_control or {}),
        )
        truth_frame = build_ground_truth_frame(
            tick=tick,
            t=t,
            world=world,
            contacts=list(contacts),
            source_to_track=source_to_track,
        )
        return perceived_frame, truth_frame

    def consume_game_tick(
        self,
        *,
        game: Game,
        tick: int,
        game_events: Sequence[Mapping[str, Any]],
    ) -> tuple[SonarConsoleFrame, GroundTruthFrame]:
        objective = getattr(game, "_objective", None)
        classification_scores = {}
        for track in game.sensor_tick.passive_tracks:
            if objective:
                classification_scores[track.contact_id] = float(objective.classification_for(track.contact_id))
            else:
                classification_scores[track.contact_id] = 0.0

        ownship = self._build_ownship_context(
            game=game,
            ping_active=bool(game.sensor_tick.ping_emitted),
        )
        return self.step(
            tick=tick,
            t=game.world.time,
            ownship=ownship,
            passive_tracks=game.sensor_tick.passive_tracks,
            ping_returns=game.sensor_tick.ping_returns,
            contacts=list(game.contacts),
            world=game.world,
            classification_scores=classification_scores,
            game_events=game_events,
            fire_control=game.build_fire_control_observation(),
        )

    def run_game(self, *, game: Game, ticks: int) -> SonarRun:
        if not game.trace_enabled:
            raise ValueError("Game.trace_enabled must be True to run SonarConsole replay-safe capture")
        perceived: list[SonarConsoleFrame] = []
        truth: list[GroundTruthFrame] = []
        actions: list[dict[str, Any]] = []

        for tick in range(ticks):
            game.tick(FRAME_DT)
            if not game.trace:
                break
            trace_entry = game.trace[-1]
            frame_events = trace_entry.get("events", [])
            frame_action = trace_entry.get("action", {})
            p_frame, t_frame = self.consume_game_tick(game=game, tick=tick, game_events=frame_events)
            perceived.append(p_frame)
            truth.append(t_frame)
            actions.append(
                {
                    "tick": tick,
                    "t": game.world.time,
                    "action": dict(frame_action),
                }
            )
            if not game.running:
                break

        fixture = FixtureConfig(name="runtime", seed=game.seed, difficulty=game.difficulty, ticks=ticks, agent=game.agent)
        return SonarRun(fixture=fixture, perceived_frames=perceived, truth_frames=truth, actions=actions)

    def run_fixture(self, fixture: FixtureConfig) -> SonarRun:
        game = Game(
            headless=True,
            seed=fixture.seed,
            difficulty=fixture.difficulty,
            mode_override=fixture.mode,
            trace_enabled=True,
            agent=fixture.agent,
            render=False,
            health_check=True,
        )
        try:
            run = self.run_game(game=game, ticks=fixture.ticks)
            run.fixture = fixture
            return run
        finally:
            game.shutdown()

    def load_fixture(self, path: str | Path) -> FixtureConfig:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return FixtureConfig.from_dict(payload)

    def _build_ownship_context(self, *, game: Game, ping_active: bool) -> OwnshipSensorContext:
        depth = game.world.player.position[2]
        self_noise = game.world.player.own_noise
        foundation = build_foundation_state(
            own_noise=self_noise,
            sensor_noise=float(getattr(game.sensors, "sensor_noise", 0.0)),
            ping_active=ping_active,
        )
        if depth <= THERMOCLINE_DEPTH_M:
            thermocline_side = "below"
        else:
            thermocline_side = "above"
        return OwnshipSensorContext(
            heading_deg=game.world.player.heading_deg,
            speed_mps=game.world.player.speed_mps,
            depth_m=depth,
            pitch=game._last_action.pitch,
            roll=game._last_action.roll,
            self_noise=self_noise,
            self_noise_bucket=foundation.own_noise_bucket,
            sensor_noise=foundation.sensor_noise,
            ping_cooldown_s=float(getattr(game, "_ping_cooldown", 0.0)),
            ping_active=foundation.ping_active,
            thermocline_side=thermocline_side,
            masking=foundation.masking,
        )

    def _translate_game_events(
        self,
        *,
        tick: int,
        t: float,
        game_events: Sequence[Mapping[str, Any]],
        source_to_track: Mapping[str, str],
    ) -> list[SonarEvent]:
        translated: list[SonarEvent] = []
        for event in game_events:
            event_type = str(event.get("type", ""))
            payload = event.get("payload", {}) or {}
            mapped = self._map_event_type(event_type)
            if mapped is None:
                continue
            track_id = None
            if isinstance(payload, Mapping):
                source_id = payload.get("id") or payload.get("target") or payload.get("contact")
                if source_id is not None:
                    track_id = source_to_track.get(str(source_id))
            translated.append(
                SonarEvent(
                    event_type=mapped,
                    tick=tick,
                    t=float(event.get("t", t)),
                    track_id=track_id,
                    severity="info",
                    details=dict(payload) if isinstance(payload, Mapping) else {},
                )
            )
        return translated

    def _map_event_type(self, event_type: str) -> str | None:
        if event_type == EVENT_PING:
            return "sensor_masking_event"
        if event_type == EVENT_RETURN:
            return "contact_strengthened"
        if event_type == "FIRE_SOLUTION_READY":
            return "classification_changed"
        if event_type in {"UI_ALERT", "OBJECTIVE_STAGE_ADVANCE"}:
            return "console_notice"
        return None


def action_from_frame_payload(payload: Mapping[str, Any]) -> Action:
    data = payload.get("action", {})
    return Action(
        heading_deg=float(data.get("heading_deg", 0.0)),
        pitch=float(data.get("pitch", 0.0)),
        roll=float(data.get("roll", 0.0)),
        ping=bool(data.get("ping", False)),
        torpedo=bool(data.get("torpedo", False)),
    )


__all__ = [
    "FixtureConfig",
    "SonarRun",
    "SonarConsole",
    "action_from_frame_payload",
]
