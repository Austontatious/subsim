extends Node3D

@onready var engine: SubsimEngine = $Engine as SubsimEngine
@onready var hud_label: Label = $CanvasLayer/HUD/Label
@onready var tele: VSlider = $CanvasLayer/HUD/Telegraph
@onready var heading_wheel: Control = $CanvasLayer/HUD/HeadingWheel
@onready var depth_dial: Control = $CanvasLayer/HUD/DepthDial
@onready var space3d: Node3D = $Battlespace3D
@onready var compass: CompassDial = $CanvasLayer/HUD/CompassDial as CompassDial

const DT := 1.0 / 30.0

func _physics_process(_dt: float) -> void:
    engine.step(DT)
    var p = engine.get_player_pose()
    hud_label.text = "HDG %03d  SPD %.1f m/s  DEPTH %.0f  PING %.1fs" % [int(p.heading), p.speed, p.depth, p.ping_age]
    if space3d.has_method("update_from_engine"):
        space3d.update_from_engine(p)
    if compass:
        compass.current_heading = p.heading
        compass.target_heading = p.heading_target

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

func _ready() -> void:
    tele.connect("value_changed", Callable(self, "_on_tele_changed"))
    heading_wheel.gui_input.connect(_on_wheel_input)
    depth_dial.gui_input.connect(_on_depth_input)
    if compass:
        compass.target_changed.connect(_on_compass_target)
    if engine:
        engine.sfx_ping.connect(_on_engine_ping)

func _on_tele_changed(v: float) -> void:
    engine.set_telegraph(int(round(v)))

var wheel_dragging := false
func _on_wheel_input(event: InputEvent) -> void:
    if event is InputEventMouseButton:
        var mb := event as InputEventMouseButton
        if mb.button_index == MOUSE_BUTTON_LEFT:
            wheel_dragging = mb.pressed
    elif event is InputEventMouseMotion and wheel_dragging:
        var center := heading_wheel.get_global_rect().get_center()
        var pos := (event as InputEventMouseMotion).position + heading_wheel.get_global_rect().position
        var dir := pos - center
        var ang := rad_to_deg(atan2(dir.y, dir.x))
        engine.turn_deg(ang - 90.0) # coarse turn; refine later to absolute set

var depth_dragging := false
func _on_depth_input(event: InputEvent) -> void:
    if event is InputEventMouseButton:
        var mb := event as InputEventMouseButton
        if mb.button_index == MOUSE_BUTTON_LEFT:
            depth_dragging = mb.pressed
    elif event is InputEventMouseMotion and depth_dragging:
        # Map vertical mouse movement in the control to depth 0..1000m
        var r := depth_dial.get_global_rect()
        var t := clamp((event as InputEventMouseMotion).position.y / max(1.0, r.size.y), 0.0, 1.0)
        engine.set_depth_target(1000.0 * t)

func _on_compass_target(deg: float) -> void:
    engine.set_heading_target(deg)

func _on_engine_ping() -> void:
    if space3d and space3d.has_method("spawn_ping"):
        space3d.spawn_ping()
