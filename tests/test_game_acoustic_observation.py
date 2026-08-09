from subsim.engine.sensors import SensorTick
from subsim.game import Game
from subsim.input import Action, InputFrame


def test_build_observation_contains_acoustic_contract_surface() -> None:
    game = Game(headless=True, seed=7, render=False)
    try:
        game.start_skirmish()
        frame = InputFrame(action=Action())
        game.step_sim(frame.action, frame, 1.0 / 30.0)
        obs = game.build_observation()
    finally:
        game.shutdown()

    assert "acoustic" in obs
    fire_control = obs["fire_control"]
    assert fire_control["schema_version"] == "subsim.fire_control.v1"
    assert fire_control["fire_control_solution_state"] in {
        "no_solution",
        "building_solution",
        "ready",
        "fired",
        "expired",
    }
    assert isinstance(fire_control["fire_control_ready"], bool)
    assert isinstance(fire_control["weapon_ready"], bool)
    assert isinstance(fire_control["valid_fire_opportunity"], bool)
    assert isinstance(fire_control["fire_control_solution_quality"], float)
    assert isinstance(fire_control["active_torpedo_count"], int)
    acoustic = obs["acoustic"]
    assert acoustic["schema_version"] == "acoustic-substrate.v1"
    assert "foundation" in acoustic
    assert "contacts" in acoustic
    assert "runtime_renderer" in acoustic
    assert isinstance(acoustic["contacts"], list)
    runtime_renderer = acoustic["runtime_renderer"]
    assert runtime_renderer["schema_version"] == "runtime-acoustic.v1"
    assert runtime_renderer["preset_name"] == "medium_clutter"
    assert "families" in runtime_renderer
    assert "foundation_profile" in runtime_renderer
    assert "layer_gains" in runtime_renderer
    if acoustic["contacts"]:
        contact = acoustic["contacts"][0]
        assert contact["variant"] in {"clean", "lp1", "lp2", "lp3"}
        assert contact["contact_id"]


def test_update_audio_mix_stops_stale_contact_loops() -> None:
    game = Game(headless=True, seed=7, render=False)
    try:
        game.start_skirmish()
        frame = InputFrame(action=Action())
        game.step_sim(frame.action, frame, 1.0 / 30.0)

        stale_contact_ids = {entry.contact_id for entry in game._acoustic_contacts}
        assert stale_contact_ids

        stopped: list[str] = []
        original_stop = game.audio.stop_loop

        def _record_stop(key: str) -> None:
            stopped.append(key)
            original_stop(key)

        game.audio.stop_loop = _record_stop  # type: ignore[method-assign]
        game.sensor_tick = SensorTick(passive_tracks=[], ping_returns=[], ping_emitted=False)
        game._update_audio_mix()

        assert stale_contact_ids.issubset(set(stopped))
        assert game._acoustic_contacts == []
    finally:
        game.shutdown()
