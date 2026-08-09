from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
GODOT_ROOT = REPO_ROOT / "godot"


def test_context_strip_exposes_ping_and_fire_buttons() -> None:
    scene = (GODOT_ROOT / "main" / "Main.tscn").read_text(encoding="utf-8")
    assert '[node name="ContextStrip"' in scene
    assert '[node name="PingButton" type="Button" parent="CanvasLayer/HUD/ContextStrip"]' in scene
    assert '[node name="FireButton" type="Button" parent="CanvasLayer/HUD/ContextStrip"]' in scene

    script = (GODOT_ROOT / "scripts" / "ui" / "context_strip.gd").read_text(encoding="utf-8")
    required_tokens = (
        "signal ping_pressed()",
        "signal fire_pressed()",
        '@onready var ping_btn: Button = $PingButton as Button',
        '@onready var fire_btn: Button = $FireButton as Button',
        "func _on_ping_pressed() -> void:",
        'emit_signal("ping_pressed")',
        "func _on_fire_pressed() -> void:",
        'emit_signal("fire_pressed")',
    )
    for token in required_tokens:
        assert token in script


def test_main_wires_mobile_buttons_and_uses_larger_strip_height() -> None:
    script = (GODOT_ROOT / "main" / "main.gd").read_text(encoding="utf-8")
    required_tokens = (
        "context.ping_pressed.connect(_on_ping_pressed)",
        "context.fire_pressed.connect(_on_fire_pressed)",
        "func _on_ping_pressed() -> void:",
        "engine.cmd_ping()",
        "func _on_fire_pressed() -> void:",
        "engine.cmd_fire()",
        "var strip_h: float = clamp(h * 0.14, 96.0, 140.0)",
        "var show_strip: bool = true",
    )
    for token in required_tokens:
        assert token in script


def test_engine_fire_path_has_real_torpedo_state() -> None:
    script = (GODOT_ROOT / "scripts" / "engine_port" / "engine.gd").read_text(encoding="utf-8")
    required_tokens = (
        "const TORPEDO_AMMO_INITIAL",
        "var _torpedo_ammo: int = TORPEDO_AMMO_INITIAL",
        "var _torpedoes: Array = []",
        "func cmd_fire() -> bool:",
        "func can_fire_torpedo() -> bool:",
        "func _update_torpedoes(dt: float) -> void:",
        "func get_torpedoes() -> Array:",
        'emit_signal("torpedo_fired"',
    )
    for token in required_tokens:
        assert token in script
