"""Game orchestration layer for SubSim."""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from .acoustic_contract import (
    SCHEMA_VERSION as ACOUSTIC_SCHEMA_VERSION,
    AcousticContactState,
    AcousticFoundationState,
    build_contact_state,
    build_foundation_state,
)
from .audio import AudioEngine
from .config import (
    AUDIO_MAX_DISTANCE_M,
    CRUISE_TELEGRAPH,
    FIRE_SOLUTION_READY_S,
    FIRE_SOLUTION_WINDOW_S,
    FRAME_DT,
    PING_COOLDOWN_S,
    PITCH_RATE_MPS,
)
from .engine import AiController, ContactManager, SensorSuite, WeaponEvent, WeaponManager, World, clamp
from .events import (
    EventBus,
    EVENT_CONTACT_NEW,
    EVENT_DETONATION,
    EVENT_FIRE_SOLUTION_MISS,
    EVENT_FIRE_SOLUTION_READY,
    EVENT_FIRE_SOLUTION_START,
    EVENT_MODE_CHANGE,
    EVENT_OBJECTIVE_COMPLETE,
    EVENT_OBJECTIVE_FAIL,
    EVENT_OBJECTIVE_STAGE,
    EVENT_PING,
    EVENT_RETURN,
    EVENT_TORP_HIT,
    EVENT_TORP_IN_WATER,
    EVENT_TORP_LAUNCH,
    EVENT_UI_ALERT,
    EVENT_UI_CONFIRM,
    GameEvent,
    events_to_trace,
)
from .input import Action, InputFrame, TwoDialInput
from .objectives import ObjectiveTracker
from .render import Renderer
from .runtime_acoustic import RuntimeHybridLayerV1, list_runtime_acoustic_presets
from .scenario import DIFFICULTY, Scenario, generate_skirmish


CONTACT_AUDIO = {
    "merchant": "merchant",
    "hunter": "hunter",
}


@dataclass
class RunStats:
    pings: int = 0
    torpedoes_fired: int = 0
    torpedo_hits: int = 0
    time_to_locate: float | None = None
    time_to_classify: float | None = None
    timeline: list[tuple[float, str]] = field(default_factory=list)


@dataclass
class TutorialState:
    steps: list[tuple[str, str]]
    step_index: int = 0

    def current(self) -> tuple[str, str]:
        return self.steps[self.step_index]

    def advance(self) -> None:
        if self.step_index < len(self.steps) - 1:
            self.step_index += 1

    def complete(self) -> bool:
        return self.step_index >= len(self.steps) - 1


@dataclass
class DebriefReport:
    outcome: str
    stats: RunStats
    objective_branch: str


@dataclass
class FireControl:
    active: bool = False
    ready_emitted: bool = False
    ready_time: float = 0.0
    window_end: float = 0.0
    target_id: str | None = None
    quality: float = 0.0


class ModeBase:
    name = "base"

    def on_enter(self, game: "Game") -> None:
        return

    def step(self, game: "Game", frame: InputFrame, dt: float) -> None:
        raise NotImplementedError


class MenuMode(ModeBase):
    name = "menu"

    def step(self, game: "Game", frame: InputFrame, dt: float) -> None:
        if frame.quit:
            game.running = False
            return
        if frame.menu_choice == 1:
            game.start_skirmish()
        elif frame.menu_choice == 2:
            game.start_tutorial()
        elif frame.menu_choice == 4:
            game.running = False


class TutorialMode(ModeBase):
    name = "tutorial"

    def step(self, game: "Game", frame: InputFrame, dt: float) -> None:
        game.step_sim(frame.action, frame, dt)
        game.update_tutorial(frame.action)


class SkirmishMode(ModeBase):
    name = "skirmish"

    def step(self, game: "Game", frame: InputFrame, dt: float) -> None:
        game.step_sim(frame.action, frame, dt)


class DebriefMode(ModeBase):
    name = "debrief"

    def step(self, game: "Game", frame: InputFrame, dt: float) -> None:
        if frame.quit:
            game.running = False
            return
        if frame.menu_choice == 1 or frame.confirm:
            game.start_menu()


MODE_MAP = {
    "menu": MenuMode,
    "tutorial": TutorialMode,
    "skirmish": SkirmishMode,
    "debrief": DebriefMode,
}


@dataclass
class Game:
    headless: bool = False
    seed: int = 0
    duration: Optional[float] = None
    difficulty: str = "normal"
    mode_override: Optional[str] = None
    trace_enabled: bool = False
    agent: Optional[str] = None
    health_check: bool = False
    render: bool = True
    acoustic_preset: str = "medium_clutter"

    def __post_init__(self) -> None:
        if self.agent and not self.render:
            self.headless = True
        self.audio = AudioEngine(headless=self.headless)
        self.renderer = Renderer(headless=self.headless or not self.render)
        self.input = TwoDialInput(self.renderer)
        self.events = EventBus()
        self.trace: list[dict] = []
        self.trace_meta: dict = {}
        self.running = True
        self._known_contacts: set[str] = set()
        self._scenario: Scenario | None = None
        self._objective: ObjectiveTracker | None = None
        self._stats = RunStats()
        self._tutorial = TutorialState(
            steps=[
                ("LISTEN", "Listen for a contact"),
                ("PING", "Use active ping"),
                ("ENGAGE", "Fire torpedo (2-step)"),
                ("EXTRACT", "Exit to safe waters"),
            ]
        )
        self._debrief: DebriefReport | None = None
        self.mode: ModeBase = MenuMode()
        self.help_overlay = False
        self.paused = False
        self._ping_cooldown = 0.0
        self._ping_risk_timer = 0.0
        self._base_aggression = 1.0
        self._threat_cooldown = 0.0
        self._fire_control = FireControl()
        self._torpedo_state = "idle"
        self._torpedo_state_timer = 0.0
        self._selected_contact_id: str | None = None
        self._locked_contact_id: str | None = None
        self._ui_message = ""
        self._ui_message_timer = 0.0
        self._last_action = Action()
        self._objective_complete_emitted = False
        self._objective_fail_emitted = False
        self._acoustic_foundation: AcousticFoundationState = build_foundation_state(
            own_noise=0.0,
            sensor_noise=0.0,
            ping_active=False,
        )
        self._acoustic_contacts: list[AcousticContactState] = []
        self._acoustic_runtime: dict[str, Any] = {}
        self._runtime_layer_keys: set[str] = set()
        self.runtime_hybrid = RuntimeHybridLayerV1(
            preset_name=self.acoustic_preset,
            runtime_seed=self.seed,
        )
        initial_runtime = self.runtime_hybrid.state_snapshot()
        initial_runtime["desktop_runtime_active"] = bool(self.runtime_hybrid.enabled)
        initial_runtime["foundation_profile"] = {
            "ambient_gain": self._acoustic_foundation.ambient_level,
            "self_noise_gain": self._acoustic_foundation.self_noise_level * 0.38,
            "hum_gain": self._acoustic_foundation.player_hum_level,
        }
        initial_runtime["layer_gains"] = {}
        self._acoustic_runtime = initial_runtime

        self._init_sim(seed=self.seed, contacts=None, sensor_noise=0.0, aggression=1.0)

        if self.mode_override:
            override = self.mode_override.lower()
            if override == "tutorial":
                self.start_tutorial()
            elif override == "skirmish":
                self.start_skirmish()
            elif override == "debrief":
                self.start_debrief(outcome="Abort")
            else:
                self.set_mode(override)
        elif self.headless or self.agent:
            self.start_skirmish()
        else:
            self._emit_mode_change(self.mode.name)

        if self.agent:
            self._init_agent()

    def _init_agent(self) -> None:
        if self.agent == "baseline":
            from .agents.baseline import BaselineAgent

            self._agent = BaselineAgent()
        else:
            self._agent = None
        if self._agent:
            self._agent.reset(self.build_observation())

    def _init_sim(
        self,
        *,
        seed: int,
        contacts,
        sensor_noise: float,
        aggression: float,
    ) -> None:
        self.world = World(seed=seed)
        self.contacts = ContactManager(seed=seed)
        if contacts is None:
            self.contacts.spawn_demo_contacts()
        else:
            self.contacts.spawn_contacts(contacts)
        self.sensors = SensorSuite(sensor_noise=sensor_noise)
        self.weapons = WeaponManager()
        self._base_aggression = aggression
        self.ai = AiController(self.contacts, aggression=aggression)
        self._known_contacts.clear()

    def set_mode(self, mode_name: str) -> None:
        mode_name = mode_name.lower()
        mode_cls = MODE_MAP.get(mode_name)
        if not mode_cls:
            return
        self.mode = mode_cls()
        self._emit_mode_change(self.mode.name)

    def _clear_acoustic_contacts(self) -> None:
        for entry in self._acoustic_contacts:
            self.audio.stop_loop(entry.contact_id)
        self._acoustic_contacts = []

    def _clear_runtime_layers(self) -> None:
        for layer_key in self._runtime_layer_keys:
            self.audio.stop_loop(layer_key)
        self._runtime_layer_keys = set()

    def start_menu(self) -> None:
        self._clear_acoustic_contacts()
        self._clear_runtime_layers()
        self.set_mode("menu")

    def start_tutorial(self) -> None:
        self._clear_acoustic_contacts()
        self._clear_runtime_layers()
        preset = DIFFICULTY.get("easy", next(iter(DIFFICULTY.values())))
        scenario = generate_skirmish(self.seed, preset)
        self._scenario = scenario
        self._objective = ObjectiveTracker(branch=scenario.objective_branch)
        self._stats = RunStats()
        self._objective_complete_emitted = False
        self._objective_fail_emitted = False
        self._tutorial = TutorialState(
            steps=[
                ("LISTEN", "Listen for a contact"),
                ("PING", "Use active ping"),
                ("ENGAGE", "Fire torpedo (2-step)"),
                ("EXTRACT", "Exit to safe waters"),
            ]
        )
        self._init_sim(
            seed=scenario.seed,
            contacts=scenario.contacts,
            sensor_noise=preset.sensor_noise,
            aggression=1.0 + preset.enemy_aggression,
        )
        self._ping_cooldown = 0.0
        self._fire_control = FireControl()
        self._torpedo_state = "idle"
        self._torpedo_state_timer = 0.0
        self._selected_contact_id = None
        self._locked_contact_id = None
        self._ui_message = ""
        self.set_mode("tutorial")
        if self.agent and hasattr(self, "_agent") and self._agent:
            self._agent.reset(self.build_observation())
        _, msg = self._tutorial.current()
        self.events.emit(EVENT_UI_ALERT, t=self.world.time, priority=30, payload={"message": msg})
        self._set_ui_message(msg, ttl=5.0)

    def start_skirmish(self, seed: Optional[int] = None) -> None:
        self._clear_acoustic_contacts()
        self._clear_runtime_layers()
        seed = self.seed if seed is None else seed
        preset = DIFFICULTY.get(self.difficulty, DIFFICULTY["normal"])
        scenario = generate_skirmish(seed, preset)
        self._scenario = scenario
        self._objective = ObjectiveTracker(branch=scenario.objective_branch)
        self._stats = RunStats()
        self._objective_complete_emitted = False
        self._objective_fail_emitted = False
        self._init_sim(
            seed=scenario.seed,
            contacts=scenario.contacts,
            sensor_noise=preset.sensor_noise,
            aggression=1.0 + preset.enemy_aggression,
        )
        self._ping_cooldown = 0.0
        self._fire_control = FireControl()
        self._torpedo_state = "idle"
        self._torpedo_state_timer = 0.0
        self._selected_contact_id = None
        self._locked_contact_id = None
        self._ui_message = ""
        self.set_mode("skirmish")
        if self.agent and hasattr(self, "_agent") and self._agent:
            self._agent.reset(self.build_observation())

    def start_debrief(self, outcome: str) -> None:
        self._clear_acoustic_contacts()
        self._clear_runtime_layers()
        branch = self._objective.branch if self._objective else "engage"
        self._debrief = DebriefReport(outcome=outcome, stats=self._stats, objective_branch=branch)
        self.set_mode("debrief")

    def shutdown(self) -> None:
        self.audio.shutdown()
        if self.renderer:
            self.renderer.close()

    def _emit_mode_change(self, mode: str) -> None:
        self.events.emit(EVENT_MODE_CHANGE, t=self.world.time, payload={"mode": mode})

    def _set_ui_message(self, message: str, ttl: float = 4.0) -> None:
        self._ui_message = message
        self._ui_message_timer = ttl

    def _tick_ui_message(self, dt: float) -> None:
        if self._ui_message_timer > 0.0:
            self._ui_message_timer = max(0.0, self._ui_message_timer - dt)
            if self._ui_message_timer <= 0.0:
                self._ui_message = ""

    def _distance_norm(self, distance_m: float) -> float:
        return min(1.0, max(0.0, distance_m / AUDIO_MAX_DISTANCE_M))

    def _apply_action(self, action: Action, dt: float) -> dict:
        action = action.normalized()
        self._last_action = action
        actions = {"ping": False, "torpedo": False}

        # Heading dial
        error = (action.heading_deg - self.world.player.heading_deg + 540.0) % 360.0 - 180.0
        turn_rate = 65.0
        delta = clamp(error, -turn_rate * dt, turn_rate * dt)
        self.world.player.change_heading(delta)
        self.world.player.telegraph = CRUISE_TELEGRAPH

        # Pitch dial
        if abs(action.pitch) > 1e-3:
            self.world.player.change_depth(action.pitch * PITCH_RATE_MPS * dt)

        # Ping button
        if action.ping and self._ping_cooldown <= 0.0:
            self._ping_cooldown = PING_COOLDOWN_S
            actions["ping"] = True
            self._stats.pings += 1
            self.events.emit(EVENT_PING, t=self.world.time, priority=70)
        elif action.ping and self._ping_cooldown > 0.0:
            self.events.emit(EVENT_UI_ALERT, t=self.world.time, priority=40, payload={"message": "Ping cooling"})

        # Torpedo button
        if action.torpedo:
            actions["torpedo"] = True

        return actions

    def _update_ping_cooldown(self, dt: float) -> None:
        if self._ping_cooldown > 0.0:
            self._ping_cooldown = max(0.0, self._ping_cooldown - dt)

    def _update_ping_risk(self, dt: float, ping_used: bool) -> None:
        if ping_used:
            self._ping_risk_timer = 12.0
        if self._ping_risk_timer > 0.0:
            self._ping_risk_timer = max(0.0, self._ping_risk_timer - dt)
        risk_bonus = 0.6 if self._ping_risk_timer > 0.0 else 0.0
        self.ai.aggression = self._base_aggression + risk_bonus

    def _update_threats(self, dt: float) -> None:
        if self._threat_cooldown > 0.0:
            self._threat_cooldown = max(0.0, self._threat_cooldown - dt)
            return
        nearest = None
        nearest_bearing = None
        for contact in self.contacts:
            if contact.kind != "hunter":
                continue
            dist = World.distance(self.world.player.position, contact.position)
            if nearest is None or dist < nearest:
                nearest = dist
                nearest_bearing = World.bearing(self.world.player.position, contact.position)
        if nearest is not None and nearest < 450.0:
            self._threat_cooldown = 5.0
            self.events.emit(
                EVENT_UI_ALERT,
                t=self.world.time,
                bearing_deg=nearest_bearing,
                distance_norm=self._distance_norm(nearest),
                priority=80,
                payload={"message": "Threat bearing"},
            )

    def _emit_sensor_events(self) -> None:
        for track in self.sensor_tick.passive_tracks:
            if track.contact_id not in self._known_contacts:
                self._known_contacts.add(track.contact_id)
                self.events.emit(
                    EVENT_CONTACT_NEW,
                    t=self.world.time,
                    bearing_deg=track.azimuth_deg,
                    distance_norm=self._distance_norm(track.distance_m),
                    priority=35,
                    payload={"id": track.contact_id},
                )
                if self._stats.time_to_locate is None:
                    self._stats.time_to_locate = self.world.time

        for ret in self.sensor_tick.ping_returns:
            self.events.emit(
                EVENT_RETURN,
                t=self.world.time + ret.delay_s,
                bearing_deg=ret.bearing_deg,
                distance_norm=self._distance_norm(ret.range_m),
                priority=55,
                payload={"id": ret.contact_id},
            )
            if self._stats.time_to_classify is None:
                self._stats.time_to_classify = self.world.time

    def _update_audio_mix(self) -> None:
        foundation = build_foundation_state(
            own_noise=self.world.player.own_noise,
            sensor_noise=self.sensors.sensor_noise,
            ping_active=self.sensor_tick.ping_emitted,
        )
        self._acoustic_foundation = foundation
        foundation_profile: dict[str, float] | None = None
        if self.runtime_hybrid and self.runtime_hybrid.enabled:
            foundation_profile = self.runtime_hybrid.apply_foundation_profile(foundation)
        self.audio.update_foundation(foundation, profile_overrides=foundation_profile)

        previous_contact_ids = {entry.contact_id for entry in self._acoustic_contacts}
        passive = self.sensor_tick.passive_tracks
        active_contact_ids = {ret.contact_id for ret in self.sensor_tick.ping_returns}
        current_contact_ids: set[str] = set()
        acoustic_contacts: list[AcousticContactState] = []
        for track in passive:
            contact = self.contacts.contacts[track.contact_id]
            current_contact_ids.add(track.contact_id)
            acoustic = build_contact_state(
                contact_id=track.contact_id,
                kind=contact.kind,
                bearing_deg=track.azimuth_deg,
                distance_m=track.distance_m,
                confidence=track.confidence,
                gain=track.gain,
                occlusion_layers=track.occlusion_layers,
                own_noise=self.world.player.own_noise,
                source_channels=("passive", "active_ping") if track.contact_id in active_contact_ids else ("passive",),
            )
            acoustic_contacts.append(acoustic)
            asset = CONTACT_AUDIO.get(contact.kind, "merchant")
            self.audio.play_loop(asset, track.contact_id, variant=acoustic.variant)
            self.audio.set_contact_mix(
                track.contact_id,
                azimuth_deg=track.azimuth_deg,
                distance_m=track.distance_m,
                confidence=track.confidence,
                occlusion_layers=track.occlusion_layers,
                own_noise=self.world.player.own_noise,
            )

        for stale_contact_id in previous_contact_ids - current_contact_ids:
            self.audio.stop_loop(stale_contact_id)
        self._acoustic_contacts = acoustic_contacts

        runtime_layer_gains: dict[str, float] = {}
        if self.runtime_hybrid and self.runtime_hybrid.enabled:
            runtime_layer_gains = self.runtime_hybrid.compute_layer_gains(
                foundation,
                contact_count=len(acoustic_contacts),
                active_ping_count=len(self.sensor_tick.ping_returns),
            )
            active_runtime_layer_keys: set[str] = set()
            for layer_key, spec in self.runtime_hybrid.layer_specs.items():
                wav_path = str(spec.get("wav_path") or "")
                if not wav_path:
                    continue
                active_runtime_layer_keys.add(layer_key)
                self.audio.play_external_loop(wav_path, layer_key)
                self.audio.set_runtime_layer_mix(layer_key, runtime_layer_gains.get(layer_key, 0.0))
            for stale_layer_key in self._runtime_layer_keys - active_runtime_layer_keys:
                self.audio.stop_loop(stale_layer_key)
            self._runtime_layer_keys = active_runtime_layer_keys
        else:
            self._clear_runtime_layers()

        runtime_state = self.runtime_hybrid.state_snapshot()
        runtime_state["desktop_runtime_active"] = bool(self.runtime_hybrid.enabled)
        runtime_state["foundation_profile"] = dict(
            foundation_profile
            or {
                "ambient_gain": foundation.ambient_level,
                "self_noise_gain": foundation.self_noise_level * 0.38,
                "hum_gain": foundation.player_hum_level,
            }
        )
        runtime_state["layer_gains"] = dict(runtime_layer_gains)
        self._acoustic_runtime = runtime_state

    def _update_contact_selection(self, frame: InputFrame) -> None:
        tracks = list(self.sensor_tick.passive_tracks)
        tracks.sort(key=lambda t: t.confidence, reverse=True)
        ids = [t.contact_id for t in tracks]
        if frame.cycle_contact and ids:
            if self._selected_contact_id in ids:
                idx = ids.index(self._selected_contact_id)
                self._selected_contact_id = ids[(idx + 1) % len(ids)]
            else:
                self._selected_contact_id = ids[0]
        if self._selected_contact_id is None and ids:
            self._selected_contact_id = ids[0]
        if frame.lock_contact and self._selected_contact_id:
            self._locked_contact_id = self._selected_contact_id
            self.events.emit(EVENT_UI_CONFIRM, t=self.world.time, priority=30, payload={"lock": self._locked_contact_id})

    def _best_contact_id(self) -> str | None:
        tracks = list(self.sensor_tick.passive_tracks)
        if not tracks:
            return None
        tracks.sort(key=lambda t: t.confidence, reverse=True)
        return tracks[0].contact_id

    def _target_contact_id(self) -> str | None:
        if self._locked_contact_id:
            return self._locked_contact_id
        return self._best_contact_id()

    def _contact_quality(self, contact_id: str) -> float:
        for track in self.sensor_tick.passive_tracks:
            if track.contact_id == contact_id:
                classify = self._objective.classification_for(contact_id) if self._objective else 0.0
                return max(track.confidence, classify)
        return 0.0

    def _handle_fire_control(self, fire_pressed: bool) -> bool:
        now = self.world.time
        torpedo_fired = False

        if self._fire_control.active:
            if not self._fire_control.ready_emitted and now >= self._fire_control.ready_time:
                self._fire_control.ready_emitted = True
                self.events.emit(
                    EVENT_FIRE_SOLUTION_READY,
                    t=now,
                    priority=60,
                    payload={"target": self._fire_control.target_id},
                )
            if now > self._fire_control.window_end:
                self.events.emit(
                    EVENT_FIRE_SOLUTION_MISS,
                    t=now,
                    priority=50,
                    payload={"reason": "late"},
                )
                self._fire_control = FireControl()

        if fire_pressed:
            if not self._fire_control.active:
                target_id = self._target_contact_id()
                if not target_id:
                    self.events.emit(
                        EVENT_UI_ALERT,
                        t=now,
                        priority=35,
                        payload={"message": "No contact"},
                    )
                else:
                    quality = self._contact_quality(target_id)
                    ready_time = now + FIRE_SOLUTION_READY_S
                    window_end = ready_time + FIRE_SOLUTION_WINDOW_S + quality * 0.6
                    self._fire_control = FireControl(
                        active=True,
                        ready_emitted=False,
                        ready_time=ready_time,
                        window_end=window_end,
                        target_id=target_id,
                        quality=quality,
                    )
                    bearing = self._track_bearing(target_id)
                    distance = self._track_distance(target_id)
                    self.events.emit(
                        EVENT_FIRE_SOLUTION_START,
                        t=now,
                        bearing_deg=bearing,
                        distance_norm=self._distance_norm(distance) if distance else None,
                        priority=55,
                        payload={"target": target_id},
                    )
            else:
                if now < self._fire_control.ready_time:
                    self.events.emit(
                        EVENT_FIRE_SOLUTION_MISS,
                        t=now,
                        priority=50,
                        payload={"reason": "early"},
                    )
                    self._fire_control = FireControl()
                elif now > self._fire_control.window_end:
                    self.events.emit(
                        EVENT_FIRE_SOLUTION_MISS,
                        t=now,
                        priority=50,
                        payload={"reason": "late"},
                    )
                    self._fire_control = FireControl()
                else:
                    target_id = self._fire_control.target_id
                    if target_id:
                        self.weapons.launch_torpedo(
                            self.world.player.position,
                            self.world.player.heading_deg,
                            target_id,
                        )
                        self._stats.torpedoes_fired += 1
                        torpedo_fired = True
                        bearing = self._track_bearing(target_id)
                        distance = self._track_distance(target_id)
                        self.events.emit(
                            EVENT_TORP_LAUNCH,
                            t=now,
                            bearing_deg=bearing,
                            distance_norm=self._distance_norm(distance) if distance else None,
                            priority=80,
                            payload={"target": target_id},
                        )
                        self.events.emit(
                            EVENT_TORP_IN_WATER,
                            t=now,
                            bearing_deg=bearing,
                            distance_norm=self._distance_norm(distance) if distance else None,
                            priority=70,
                            payload={"target": target_id},
                        )
                    self._fire_control = FireControl()
        return torpedo_fired

    def _track_bearing(self, contact_id: str) -> float | None:
        for track in self.sensor_tick.passive_tracks:
            if track.contact_id == contact_id:
                return track.azimuth_deg
        return None

    def _track_distance(self, contact_id: str) -> float | None:
        for track in self.sensor_tick.passive_tracks:
            if track.contact_id == contact_id:
                return track.distance_m
        return None

    def _handle_weapon_events(self, events: list[WeaponEvent]) -> bool:
        torpedo_hit = False
        for evt in events:
            bearing = World.bearing(self.world.player.position, evt.position)
            distance = World.distance(self.world.player.position, evt.position)
            if evt.kind == "torpedo-detonation":
                self._stats.torpedo_hits += 1
                torpedo_hit = True
                self.events.emit(
                    EVENT_TORP_HIT,
                    t=self.world.time,
                    bearing_deg=bearing,
                    distance_norm=self._distance_norm(distance),
                    priority=90,
                    payload={"contact": evt.contact_id},
                )
                self.events.emit(
                    EVENT_DETONATION,
                    t=self.world.time,
                    bearing_deg=bearing,
                    distance_norm=self._distance_norm(distance),
                    priority=85,
                    payload={"weapon": "torpedo", "contact": evt.contact_id},
                )
            elif evt.kind == "mine-detonation":
                self.events.emit(
                    EVENT_DETONATION,
                    t=self.world.time,
                    bearing_deg=bearing,
                    distance_norm=self._distance_norm(distance),
                    priority=80,
                    payload={"weapon": "mine", "contact": evt.contact_id},
                )
        return torpedo_hit

    def _update_objectives(self, dt: float, actions: dict, torpedo_fired: bool, torpedo_hit: bool) -> None:
        if not self._objective:
            return
        self._objective.update(
            self.world,
            self.sensor_tick,
            list(self.contacts),
            dt=dt,
            ping_used=actions.get("ping", False),
            torpedo_fired=torpedo_fired,
            torpedo_hit=torpedo_hit,
        )
        for update in self._objective.updates():
            self.events.emit(
                EVENT_OBJECTIVE_STAGE,
                t=self.world.time,
                priority=45,
                payload={"stage": update.stage, "message": update.message},
            )
            self._stats.timeline.append((self.world.time, update.message))
            self._set_ui_message(update.message, ttl=3.5)

        if self._objective.completed and not self._objective_complete_emitted:
            self._objective_complete_emitted = True
            self.events.emit(EVENT_OBJECTIVE_COMPLETE, t=self.world.time, priority=70)
        if self._objective.failed and not self._objective_fail_emitted:
            self._objective_fail_emitted = True
            self.events.emit(EVENT_OBJECTIVE_FAIL, t=self.world.time, priority=70)

    def update_tutorial(self, action: Action) -> None:
        step_key, _ = self._tutorial.current()
        advance = False
        if step_key == "LISTEN" and self._objective and self._objective.located:
            advance = True
        elif step_key == "PING" and action.ping:
            advance = True
        elif step_key == "ENGAGE" and action.torpedo:
            advance = True
        elif step_key == "EXTRACT" and self._objective and self._objective.completed:
            advance = True

        if advance and not self._tutorial.complete():
            self._tutorial.advance()
            _, msg = self._tutorial.current()
            self.events.emit(EVENT_UI_ALERT, t=self.world.time, priority=45, payload={"message": msg})
            self._set_ui_message(msg, ttl=5.0)

    def build_observation(self) -> dict:
        contacts = []
        if hasattr(self, "sensor_tick"):
            for track in self.sensor_tick.passive_tracks:
                contacts.append(
                    {
                        "id": track.contact_id,
                        "bearing": track.azimuth_deg,
                        "distance": track.distance_m,
                        "confidence": track.confidence,
                        "classify": self._objective.classification_for(track.contact_id) if self._objective else 0.0,
                        "gain": track.gain,
                        "occlusion_layers": track.occlusion_layers,
                    }
                )
        acoustic_contacts = [entry.to_dict() for entry in self._acoustic_contacts]
        return {
            "t": self.world.time,
            "player": {
                "heading": self.world.player.heading_deg,
                "depth": self.world.player.position[2],
                "speed": self.world.player.speed_mps,
                "pitch": self._last_action.pitch,
                "roll": self._last_action.roll,
            },
            "contacts": contacts,
            "objective": {
                "stage": self._objective.stage if self._objective else "",
                "branch": self._objective.branch if self._objective else "",
            },
            "ping_cooldown": self._ping_cooldown,
            "torpedo_state": self._torpedo_state,
            "fire_control": self.build_fire_control_observation(),
            "acoustic": {
                "schema_version": ACOUSTIC_SCHEMA_VERSION,
                "foundation": self._acoustic_foundation.to_dict(),
                "contacts": acoustic_contacts,
                "runtime_renderer": dict(self._acoustic_runtime),
            },
        }

    def build_fire_control_observation(self) -> dict[str, Any]:
        now = float(self.world.time)
        active = bool(self._fire_control.active)
        post_shot_cooldown = bool(self._torpedo_state_timer > 0.0 or self._torpedo_state == "fired")
        fire_control_ready = (
            active
            and now >= float(self._fire_control.ready_time)
            and now <= float(self._fire_control.window_end)
        )
        if active and now < float(self._fire_control.ready_time):
            solution_state = "building_solution"
            hold_reason = "building_solution"
        elif fire_control_ready:
            solution_state = "ready"
            hold_reason = "ready"
        elif active:
            solution_state = "expired"
            hold_reason = "solution_window_expired"
        elif post_shot_cooldown:
            solution_state = "fired"
            hold_reason = "post_shot_cooldown"
        else:
            solution_state = "no_solution"
            hold_reason = "no_solution"

        solution_start = None
        target_solution_age = None
        time_to_ready = None
        window_remaining = None
        if active:
            solution_start = float(self._fire_control.ready_time) - float(FIRE_SOLUTION_READY_S)
            target_solution_age = max(0.0, now - solution_start)
            time_to_ready = max(0.0, float(self._fire_control.ready_time) - now)
            window_remaining = max(0.0, float(self._fire_control.window_end) - now)

        weapon_ready = not post_shot_cooldown
        active_torpedo_count = len(getattr(self.weapons, "torpedoes", []) or [])
        return {
            "schema_version": "subsim.fire_control.v1",
            "fire_control_ready": bool(fire_control_ready),
            "fire_control_solution_state": solution_state,
            "fire_control_solution_quality": float(self._fire_control.quality) if active else 0.0,
            "weapon_ready": bool(weapon_ready),
            "valid_fire_opportunity": bool(fire_control_ready and weapon_ready),
            "fire_control_hold_reason": hold_reason,
            "target_id": self._fire_control.target_id if active else None,
            "target_solution_age_s": target_solution_age,
            "time_to_ready_s": time_to_ready,
            "solution_window_remaining_s": window_remaining,
            "active_torpedo_count": active_torpedo_count,
        }

    def _update_torpedo_state(self, dt: float) -> None:
        if self._torpedo_state_timer > 0.0:
            self._torpedo_state_timer = max(0.0, self._torpedo_state_timer - dt)
            if self._torpedo_state_timer <= 0.0:
                self._torpedo_state = "idle"

        if self._fire_control.active:
            now = self.world.time
            if now < self._fire_control.ready_time:
                self._torpedo_state = "solution"
            elif now <= self._fire_control.window_end:
                self._torpedo_state = "ready"
        elif self._torpedo_state_timer <= 0.0:
            self._torpedo_state = "idle"

    def step_sim(self, action: Action, frame: InputFrame, dt: float) -> None:
        if frame.toggle_help:
            self.help_overlay = not self.help_overlay
            self.events.emit(EVENT_UI_CONFIRM, t=self.world.time, priority=20, payload={"help": self.help_overlay})
        if frame.toggle_pause:
            self.paused = not self.paused
            self.events.emit(EVENT_UI_ALERT, t=self.world.time, priority=40, payload={"paused": self.paused})
        if frame.quit:
            self.running = False
            return
        if self.paused:
            return

        actions = self._apply_action(action, dt)
        self._update_ping_cooldown(dt)
        self.world.update(dt)
        self.contacts.update(dt)
        self._update_ping_risk(dt, actions.get("ping", False))
        self.ai.update(self.world, dt)

        ping_now = actions.get("ping", False)
        if ping_now:
            self.ai.notify_ping(self.world.time)
        self.sensor_tick = self.sensors.step(self.world, self.contacts, ping=ping_now)
        self._emit_sensor_events()
        self._update_audio_mix()
        self._update_threats(dt)

        self._update_contact_selection(frame)
        torpedo_fired = self._handle_fire_control(actions.get("torpedo", False))
        weapon_events = self.weapons.update(dt, self.world.time, list(self.contacts))
        torpedo_hit = self._handle_weapon_events(weapon_events)
        self._update_objectives(dt, actions, torpedo_fired, torpedo_hit)

        if torpedo_fired:
            self._torpedo_state = "fired"
            self._torpedo_state_timer = 1.0

        self._update_torpedo_state(dt)
        self._tick_ui_message(dt)

        if self._objective and self._objective.completed:
            self.start_debrief(outcome="Success")

        if self._scenario and self._scenario.time_limit:
            if self.world.time >= self._scenario.time_limit:
                self.start_debrief(outcome="Timed out")

        if self.health_check:
            self._health_check()

    def _health_check(self) -> None:
        import math

        if not math.isfinite(self.world.time):
            raise RuntimeError("Non-finite world time")
        x, y, z = self.world.player.position
        if not all(math.isfinite(v) for v in (x, y, z, self.world.player.heading_deg, self.world.player.speed_mps)):
            raise RuntimeError("Non-finite player state")
        if len(self.contacts.contacts) > 20:
            raise RuntimeError("Runaway contact count")
        for contact in self.contacts:
            cx, cy, cz = contact.position
            if not all(math.isfinite(v) for v in (cx, cy, cz, contact.heading_deg, contact.speed_mps)):
                raise RuntimeError("Non-finite contact state")

    def _collect_frame(self) -> InputFrame:
        frame = self.input.collect()
        if self.agent and hasattr(self, "_agent") and self._agent:
            obs = self.build_observation()
            agent_action = self._agent.act(obs).normalized()
            frame.action = agent_action
        return frame

    def _hud_payload(self) -> dict:
        objective_line = self._objective.status_line() if self._objective else ""
        tracks = []
        if hasattr(self, "sensor_tick"):
            for track in self.sensor_tick.passive_tracks:
                tracks.append(
                    {
                        "id": track.contact_id,
                        "bearing": track.azimuth_deg,
                        "distance": track.distance_m,
                        "confidence": track.confidence,
                        "classify": self._objective.classification_for(track.contact_id) if self._objective else 0.0,
                        "locked": track.contact_id == self._locked_contact_id,
                    }
                )
        debrief = None
        if self._debrief:
            debrief = {
                "outcome": self._debrief.outcome,
                "pings": self._debrief.stats.pings,
                "torpedoes": self._debrief.stats.torpedoes_fired,
                "hits": self._debrief.stats.torpedo_hits,
            }
        return {
            "mode": self.mode.name,
            "paused": self.paused,
            "help": self.help_overlay,
            "time": self.world.time,
            "heading": self.world.player.heading_deg,
            "speed": self.world.player.speed_mps,
            "depth": self.world.player.position[2],
            "heading_dial": self._last_action.heading_deg,
            "pitch": self._last_action.pitch,
            "roll": self._last_action.roll,
            "ping_cooldown": self._ping_cooldown,
            "torpedo_state": self._torpedo_state,
            "objective": objective_line,
            "tracks": tracks,
            "debrief": debrief,
            "message": self._ui_message,
        }

    def _record_trace(self, dt: float, action: Action, events: list[GameEvent]) -> None:
        if not self.trace_enabled:
            return
        contacts = []
        if hasattr(self, "sensor_tick"):
            for track in self.sensor_tick.passive_tracks:
                contacts.append(
                    {
                        "id": track.contact_id,
                        "bearing": track.azimuth_deg,
                        "distance": track.distance_m,
                        "confidence": track.confidence,
                        "classify": self._objective.classification_for(track.contact_id) if self._objective else 0.0,
                    }
                )
        record = {
            "t": self.world.time,
            "action": {
                "heading_deg": action.heading_deg,
                "pitch": action.pitch,
                "roll": action.roll,
                "ping": action.ping,
                "torpedo": action.torpedo,
            },
            "player": {
                "pos": self.world.player.position,
                "heading": self.world.player.heading_deg,
                "speed": self.world.player.speed_mps,
                "depth": self.world.player.position[2],
            },
            "objective": {
                "stage": self._objective.stage if self._objective else "",
                "branch": self._objective.branch if self._objective else "",
            },
            "contacts": contacts,
            "fire_control": self.build_fire_control_observation(),
            "events": events_to_trace(events),
        }
        self.trace.append(record)

    def tick(self, dt: float) -> None:
        frame = self._collect_frame()

        self.mode.step(self, frame, dt)

        if not self.headless and self.render:
            self.renderer.draw(self.world, list(self.contacts), hud=self._hud_payload())

        events = self.events.flush()
        self.audio.update(dt, events)
        self._record_trace(dt, frame.action, events)

    def run(self, max_ticks: Optional[int] = None) -> None:
        if max_ticks is not None:
            for _ in range(max_ticks):
                if not self.running:
                    break
                self.tick(FRAME_DT)
            self.shutdown()
            return

        start = time.perf_counter()
        last = start
        target_dt = FRAME_DT
        while self.running:
            now = time.perf_counter()
            dt = clamp(now - last, 0.0, 0.2)
            last = now
            self.tick(dt)
            if self.headless:
                time.sleep(max(0.0, target_dt - dt))
            if self.duration is not None and (now - start) >= self.duration:
                break
        self.shutdown()

    def write_trace(self, path: str, ticks: Optional[int] = None) -> None:
        payload = {
            "meta": {
                "seed": self.seed,
                "difficulty": self.difficulty,
                "tick_rate": 1.0 / FRAME_DT,
                "ticks": ticks,
            },
            "trace": self.trace,
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SubSim prototype")
    preset_names = list_runtime_acoustic_presets()
    parser.add_argument("--headless", action="store_true", help="run without window or audio")
    parser.add_argument("--render", action="store_true", help="force rendering even with agent")
    parser.add_argument("--seed", type=int, default=0, help="random seed")
    parser.add_argument("--duration", type=float, default=None, help="max runtime in seconds")
    parser.add_argument("--difficulty", type=str, default="normal", choices=sorted(DIFFICULTY.keys()))
    parser.add_argument("--mode", type=str, default=None, choices=list(MODE_MAP.keys()))
    parser.add_argument("--scenario", type=str, default=None, choices=list(MODE_MAP.keys()), help="alias for mode")
    parser.add_argument("--agent", type=str, default=None, choices=["baseline"], help="run agent baseline")
    parser.add_argument("--trace", type=str, default=None, help="write event trace to JSON")
    parser.add_argument("--replay", type=str, default=None, help="replay a trace file and compare")
    parser.add_argument("--ticks", type=int, default=None, help="fixed-step ticks (for tracing)")
    parser.add_argument(
        "--soak",
        type=int,
        nargs="?",
        const=30,
        default=None,
        help="headless soak run in minutes (default 30)",
    )
    parser.add_argument("--health-check", action="store_true", help="assert finite sim state")
    parser.add_argument(
        "--acoustic-preset",
        type=str,
        default="medium_clutter",
        choices=preset_names or None,
        help="runtime acoustic preset pack selection",
    )
    parser.add_argument(
        "--list-acoustic-presets",
        action="store_true",
        help="print runtime acoustic preset names and exit",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)
    if args.list_acoustic_presets:
        for preset_name in list_runtime_acoustic_presets():
            print(preset_name)
        return

    mode_override = args.mode or args.scenario
    duration = args.duration
    if args.headless and duration is None and args.ticks is None and not args.trace:
        duration = 3.0
    ticks = args.ticks
    if args.trace and ticks is None:
        ticks = 300
    if args.soak:
        duration = args.soak * 60.0
        ticks = None
    agent = args.agent
    if args.soak and agent is None:
        agent = "baseline"

    if args.replay:
        from .replay import replay_trace

        ok = replay_trace(args.replay)
        raise SystemExit(0 if ok else 1)

    game = Game(
        headless=args.headless or bool(args.trace) or bool(args.soak),
        seed=args.seed,
        duration=duration,
        difficulty=args.difficulty,
        mode_override=mode_override,
        trace_enabled=bool(args.trace),
        agent=agent,
        health_check=args.health_check or bool(args.soak),
        render=args.render,
        acoustic_preset=args.acoustic_preset,
    )

    if ticks is not None:
        game.run(max_ticks=ticks)
    else:
        game.run()

    if args.trace:
        game.write_trace(args.trace, ticks=ticks)


__all__ = ["main", "Game"]
