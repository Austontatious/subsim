extends Control
class_name CompassDial

@export var current_heading: float = 0.0
@export var target_heading: float = 0.0

signal target_changed(deg: float)

var dragging: bool = false

func _ready():
    # Capture touch/mouse events reliably for dragging
    mouse_filter = Control.MOUSE_FILTER_STOP

func _process(_dt: float) -> void:
    queue_redraw()

func _draw() -> void:
    var r: float = min(size.x, size.y) * 0.45
    var c: Vector2 = size * 0.5
    var outer_col := Color(0.7, 0.85, 1.0)
    var inner_col := Color(0.5, 0.7, 1.0)
    draw_circle(c, r, Color(0.1,0.15,0.2,0.3))
    draw_arc(c, r, 0.0, TAU, 128, outer_col, 2.0)
    draw_arc(c, r*0.8, 0.0, TAU, 128, inner_col, 2.0)

    var font := get_theme_default_font()
    var font_size := get_theme_default_font_size()

    # Outer dial ticks (rotate by current heading)
    for d in range(0, 360, 30):
        var ang: float = deg_to_rad(float(d) - current_heading - 90.0)
        var p1: Vector2 = c + Vector2(r*0.92, 0).rotated(ang)
        var p2: Vector2 = c + Vector2(r*1.00, 0).rotated(ang)
        draw_line(p1, p2, outer_col, 2.0)
        var label := str(d)
        var tp: Vector2 = c + Vector2(r*0.72, 0).rotated(ang)
        var sizev := font.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size)
        draw_string(font, tp - Vector2(sizev.x*0.5, -font_size*0.35), label, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, outer_col)

    # Inner dial ticks (rotate by target heading)
    for d in range(0, 360, 30):
        var ang2: float = deg_to_rad(float(d) - target_heading - 90.0)
        var q1: Vector2 = c + Vector2(r*0.62, 0).rotated(ang2)
        var q2: Vector2 = c + Vector2(r*0.78, 0).rotated(ang2)
        draw_line(q1, q2, inner_col, 2.0)

    # Pointer up (north)
    var tip: Vector2 = c + Vector2(0, -r*1.05)
    draw_colored_polygon([c + Vector2(-8, -r*0.95), c + Vector2(8, -r*0.95), tip], Color(1,0.6,0.4))

func gui_input(event: InputEvent) -> void:
    if event is InputEventMouseButton:
        var mb := event as InputEventMouseButton
        if mb.button_index == MOUSE_BUTTON_LEFT:
            dragging = mb.pressed
            if dragging:
                _apply_from_pos(mb.position)
    elif event is InputEventMouseMotion and dragging:
        _apply_from_pos((event as InputEventMouseMotion).position)
    elif event is InputEventScreenTouch:
        var st := event as InputEventScreenTouch
        if st.pressed:
            dragging = true
            _apply_from_pos(st.position)
        else:
            dragging = false
    elif event is InputEventScreenDrag:
        var sd := event as InputEventScreenDrag
        if dragging:
            _apply_from_pos(sd.position)

func _apply_from_pos(pos: Vector2) -> void:
    var c: Vector2 = size * 0.5
    var v: Vector2 = pos - c
    var ang: float = atan2(v.y, v.x)
    var deg: float = fposmod(rad_to_deg(ang) + 360.0, 360.0)
    target_heading = deg
    emit_signal("target_changed", target_heading)
