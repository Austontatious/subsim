extends Node3D

@onready var engine: SubsimEngine = $Engine as SubsimEngine
@onready var hud_label: Label = $CanvasLayer/HUD/Label
@onready var tele: VSlider = $CanvasLayer/HUD/Telegraph
@onready var heading_wheel: Control = $CanvasLayer/HUD/HeadingWheel
@onready var depth_dial: Control = $CanvasLayer/HUD/DepthDial
@onready var space3d: Node3D = get_node_or_null("Battlespace3D") as Node3D
@onready var compass = get_node_or_null("CanvasLayer/HUD/CompassDial")

const DT := 1.0 / 30.0

func _physics_process(_dt: float) -> void:
    engine.step(DT)
    var p = engine.get_player_pose()
    hud_label.text = "HDG %03d  SPD %.1f m/s  DEPTH %.0f  PING %.1fs" % [int(p.heading), p.speed, p.depth, p.ping_age]
    if space3d and space3d.has_method("update_from_engine"):
        space3d.update_from_engine(p)
    if compass:
        compass.set("current_heading", p.heading)
        compass.set("target_heading", p.heading_target)

func _unhandled_input(event: InputEvent) -> void:
    if event.is_action_pressed("ui_left"):
        engine.turn_deg(-5)
    elif event.is_action_pressed("ui_right"):
        engine.turn_deg(+5)
    elif event.is_action_pressed("ui_up"):
        engine.set_telegraph(min(engine.telegraph + 1, 5))
    elif event.is_action_pressed("ui_down"):
        engine.set_telegraph(max(engine.telegraph - 1, -5))
    elif event.is_action_pressed("ui_accept"):
        engine.cmd_ping()

func _ready() -> void:
    tele.connect("value_changed", Callable(self, "_on_tele_changed"))
    heading_wheel.gui_input.connect(_on_wheel_input)
    depth_dial.gui_input.connect(_on_depth_input)
    if compass and compass.has_signal("target_changed"):
        compass.connect("target_changed", Callable(self, "_on_compass_target"))
    if engine:
        engine.sfx_ping.connect(_on_engine_ping)

func _on_tele_changed(v: float) -> void:
    engine.set_telegraph(int(round(v)))

var wheel_dragging: bool = false
func _on_wheel_input(event: InputEvent) -> void:
    if event is InputEventMouseButton:
        var mb := event as InputEventMouseButton
        if mb.button_index == MOUSE_BUTTON_LEFT:
            wheel_dragging = mb.pressed
    elif event is InputEventMouseMotion and wheel_dragging:
        var center: Vector2 = heading_wheel.get_global_rect().get_center()
        var pos: Vector2 = (event as InputEventMouseMotion).position + heading_wheel.get_global_rect().position
        var dir: Vector2 = pos - center
        var ang: float = rad_to_deg(atan2(dir.y, dir.x))
        engine.turn_deg(ang - 90.0) # coarse turn; refine later to absolute set

var depth_dragging: bool = false
func _on_depth_input(event: InputEvent) -> void:
    if event is InputEventMouseButton:
        var mb := event as InputEventMouseButton
        if mb.button_index == MOUSE_BUTTON_LEFT:
            depth_dragging = mb.pressed
    elif event is InputEventMouseMotion and depth_dragging:
        # Map vertical mouse movement in the control to depth 0..1000m
        var r: Rect2 = depth_dial.get_global_rect()
        var t: float = clamp((event as InputEventMouseMotion).position.y / max(1.0, r.size.y), 0.0, 1.0)
        engine.set_depth_target(1000.0 * t)

func _on_compass_target(deg: float) -> void:
    engine.set_heading_target(deg)

func _on_engine_ping() -> void:
    if space3d and space3d.has_method("spawn_ping"):
        space3d.spawn_ping()
