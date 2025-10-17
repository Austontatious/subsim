extends Node

@onready var engine: SubsimEngine = $Engine as SubsimEngine
@onready var hud_label: Label = $CanvasLayer/HUD/Label

const DT := 1.0 / 30.0

func _physics_process(_dt: float) -> void:
    engine.step(DT)
    var p = engine.get_player_pose()
    hud_label.text = "HDG %03d  SPD %.1f m/s  DEPTH %.0f  PING %.1fs" % [int(p.heading), p.speed, p.depth, p.ping_age]

func _unhandled_input(event: InputEvent) -> void:
    if event.is_action_pressed("ui_left"):
        engine.turn_deg(-5)
    elif event.is_action_pressed("ui_right"):
        engine.turn_deg(+5)
    elif event.is_action_pressed("ui_up"):
        engine.set_telegraph(min(engine.telegraph + 1, 3))
    elif event.is_action_pressed("ui_down"):
        engine.set_telegraph(max(engine.telegraph - 1, -1))
    elif event.is_action_pressed("ui_accept"):
        engine.cmd_ping()
