extends Node3D

@onready var engine: SubsimEngine = $Engine as SubsimEngine
@onready var hud_label: Label = $CanvasLayer/HUD/Label
@onready var tele: VSlider = $CanvasLayer/HUD/Telegraph
@onready var tele_label: Label = $CanvasLayer/HUD/TelegraphLabel
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
        if space3d.has_method("render_contacts"):
            space3d.render_contacts(engine.get_contacts())
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
    # Ensure the visual HeadingWheel control doesn't steal input from the dial
    if heading_wheel:
        heading_wheel.mouse_filter = Control.MOUSE_FILTER_IGNORE
        heading_wheel.gui_input.connect(_on_wheel_input)
    depth_dial.gui_input.connect(_on_depth_input)
    if compass and compass.has_signal("target_changed"):
        compass.connect("target_changed", Callable(self, "_on_compass_target"))
    if engine:
        engine.sfx_ping.connect(_on_engine_ping)
    var ping_btn := get_node_or_null("CanvasLayer/HUD/PingButton")
    if ping_btn:
        ping_btn.connect("pressed", Callable(self, "_on_ping_pressed"))
    _on_tele_changed(tele.value)

func _on_tele_changed(v: float) -> void:
    engine.set_telegraph(int(round(v)))
    if tele_label:
        tele_label.text = _telegraph_text(int(round(v)))

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
        # Map pointer position to an absolute heading target (0 at up/North)
        var ang: float = rad_to_deg(atan2(dir.y, dir.x))
        var deg: float = fposmod(ang + 90.0 + 360.0, 360.0)
        engine.set_heading_target(deg)

var depth_dragging: bool = false
func _on_depth_input(event: InputEvent) -> void:
    if event is InputEventMouseButton:
        var mb := event as InputEventMouseButton
        if mb.button_index == MOUSE_BUTTON_LEFT:
            depth_dragging = mb.pressed
    elif event is InputEventMouseMotion and depth_dragging:
        # Map vertical mouse movement in the control to depth 0..1000m
        var r: Rect2 = depth_dial.get_global_rect()
        var pos: Vector2 = (event as InputEventMouseMotion).position + r.position
        var t: float = clamp((pos.y - r.position.y) / max(1.0, r.size.y), 0.0, 1.0)
        engine.set_depth_target(1000.0 * t)
    elif event is InputEventScreenTouch:
        var st := event as InputEventScreenTouch
        depth_dragging = st.pressed
        if st.pressed:
            var r2: Rect2 = depth_dial.get_global_rect()
            var t2: float = clamp((st.position.y - r2.position.y) / max(1.0, r2.size.y), 0.0, 1.0)
            engine.set_depth_target(1000.0 * t2)
    elif event is InputEventScreenDrag and depth_dragging:
        var sd := event as InputEventScreenDrag
        var r3: Rect2 = depth_dial.get_global_rect()
        var t3: float = clamp((sd.position.y - r3.position.y) / max(1.0, r3.size.y), 0.0, 1.0)
        engine.set_depth_target(1000.0 * t3)

func _on_compass_target(deg: float) -> void:
    engine.set_heading_target(deg)

func _on_engine_ping() -> void:
    if space3d and space3d.has_method("spawn_ping"):
        space3d.spawn_ping()

func _on_ping_pressed() -> void:
    engine.cmd_ping()

func _telegraph_text(t: int) -> String:
    var map := {
        -5: "REV FULL", -4: "REV 3/4", -3: "REV 1/2", -2: "REV 1/4", -1: "REV 1/8",
         0: "STOP",
         1: "AHEAD 1/8", 2: "AHEAD 1/4", 3: "AHEAD 1/2", 4: "AHEAD 3/4", 5: "AHEAD FULL"
    }
    return map.get(t, str(t))
