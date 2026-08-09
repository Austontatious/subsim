from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
GODOT_ROOT = REPO_ROOT / "godot"


def test_godot_scene_contains_acoustic_mixer_node() -> None:
    scene = (GODOT_ROOT / "main" / "Main.tscn").read_text(encoding="utf-8")
    assert 'path="res://scripts/audio/acoustic_mixer.gd"' in scene
    assert '[node name="AcousticMixer"' in scene


def test_godot_mixer_wires_required_engine_signals() -> None:
    script = (GODOT_ROOT / "scripts" / "audio" / "acoustic_mixer.gd").read_text(encoding="utf-8")
    required_connections = (
        "engine.mix_contact.connect",
        "engine.sfx_ping.connect",
        "engine.sfx_fire.connect",
        "engine.sfx_return.connect",
    )
    for token in required_connections:
        assert token in script

    required_handlers = (
        "func _on_mix_contact(",
        "func _on_sfx_ping(",
        "func _on_sfx_fire(",
        "func _on_sfx_return(",
    )
    for token in required_handlers:
        assert token in script

    preset_tokens = (
        "runtime_acoustic_presets_v1.json",
        "runtime_preset_name",
        "_load_runtime_preset",
    )
    for token in preset_tokens:
        assert token in script


def test_godot_acoustic_assets_exist_for_required_families() -> None:
    sfx_root = GODOT_ROOT / "audio" / "sfx"
    assert sfx_root.is_dir(), "godot/audio/sfx directory must exist"
    preset_pack = GODOT_ROOT / "audio" / "runtime_acoustic_presets_v1.json"
    assert preset_pack.exists(), "missing Godot runtime acoustic preset pack"
    assert preset_pack.stat().st_size > 128, "Godot runtime acoustic preset pack appears empty"

    families = ("ambient", "player_hum", "merchant", "hunter", "ping", "torpedo", "mine")
    variants = ("clean", "lp1", "lp2", "lp3")

    for family in families:
        for variant in variants:
            wav = sfx_root / f"{family}_{variant}.wav"
            assert wav.exists(), f"missing Godot acoustic asset: {wav}"
            assert wav.stat().st_size > 256, f"asset appears empty or too small: {wav}"
