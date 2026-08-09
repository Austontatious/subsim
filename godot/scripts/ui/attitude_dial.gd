extends Control
class_name AttitudeDial

# Artificial-horizon style attitude control:
# - Drag vertical = pitch
# - Drag horizontal = roll
# - Muted water/sky
# - Subtle inertia + auto-centering when released

@export var pitch: float = 0.0 # [-1, 1]
@export var roll: float = 0.0  # [-1, 1]

signal attitude_changed(pitch: float, roll: float)

var dragging: bool = false
var _active_touch: int = -1

var _desired_pitch: float = 0.0
var _desired_roll: float = 0.0

var _vp: float = 0.0
var _vr: float = 0.0
var _dp: float = 0.0
var _dr: float = 0.0

var _last_emit_p: float = 0.0
var _last_emit_r: float = 0.0


func _ready() -> void:
    mouse_filter = Control.MOUSE_FILTER_STOP
    _desired_pitch = pitch
    _desired_roll = roll
    _dp = pitch
    _dr = roll
    _last_emit_p = pitch
    _last_emit_r = roll


func _process(dt: float) -> void:
    if not dragging:
        # Gentle auto-stabilize back to neutral when released.
        _desired_pitch = move_toward(_desired_pitch, 0.0, dt * 0.9)
        _desired_roll = move_toward(_desired_roll, 0.0, dt * 1.1)

    var rp: Vector2 = _spring_scalar(_dp, _vp, _desired_pitch, dt, 10.0, 0.85)
    _dp = rp.x
    _vp = rp.y
    var rr: Vector2 = _spring_scalar(_dr, _vr, _desired_roll, dt, 10.0, 0.85)
    _dr = rr.x
    _vr = rr.y

    pitch = clamp(_dp, -1.0, 1.0)
    roll = clamp(_dr, -1.0, 1.0)

    if dragging:
        if abs(pitch - _last_emit_p) >= 0.02 or abs(roll - _last_emit_r) >= 0.02:
            _last_emit_p = pitch
            _last_emit_r = roll
            emit_signal("attitude_changed", pitch, roll)

    queue_redraw()


func gui_input(event: InputEvent) -> void:
    if event is InputEventMouseButton:
        var mb := event as InputEventMouseButton
        if mb.button_index == MOUSE_BUTTON_LEFT:
            dragging = mb.pressed
            _active_touch = -1
            if dragging:
                _apply_from_pos(mb.position)
    elif event is InputEventMouseMotion and dragging and _active_touch == -1:
        _apply_from_pos((event as InputEventMouseMotion).position)
    elif event is InputEventScreenTouch:
        var st := event as InputEventScreenTouch
        if st.pressed:
            if not dragging:
                dragging = true
                _active_touch = st.index
                _apply_from_pos(_screen_to_local(st.position))
            elif _active_touch != st.index:
                # Multi-touch gesture in progress, release control.
                dragging = false
                _active_touch = -1
        else:
            if _active_touch == st.index:
                dragging = false
                _active_touch = -1
    elif event is InputEventScreenDrag and dragging:
        var sd := event as InputEventScreenDrag
        if _active_touch == sd.index:
            _apply_from_pos(_screen_to_local(sd.position))


func _apply_from_pos(pos: Vector2) -> void:
    var r: float = min(size.x, size.y) * 0.46
    var c: Vector2 = size * 0.5
    var v: Vector2 = pos - c
    var denom: float = max(1.0, r * 0.75)
    # Up drag = positive pitch (climb), right drag = positive roll (starboard).
    _desired_roll = clamp(v.x / denom, -1.0, 1.0)
    _desired_pitch = clamp(-v.y / denom, -1.0, 1.0)


func _screen_to_local(screen_pos: Vector2) -> Vector2:
    # Touch events report viewport coordinates; convert to this control's local space.
    return get_global_transform_with_canvas().affine_inverse() * screen_pos


func _draw() -> void:
    var r: float = min(size.x, size.y) * 0.46
    var c: Vector2 = size * 0.5

    var disc := Color(0.03, 0.08, 0.12, 0.22)
    var ring := Color(0.55, 0.82, 1.0, 0.50)
    var sky := Color(0.08, 0.11, 0.14, 0.18)
    var water := Color(0.02, 0.07, 0.10, 0.24)
    var line := Color(0.55, 0.82, 1.0, 0.32)
    var bubble := Color(0.90, 0.96, 1.0, 0.88)

    draw_circle(c, r, disc)
    draw_arc(c, r, 0.0, TAU, 160, ring, 2.0)
    draw_arc(c, r * 0.86, 0.0, TAU, 160, Color(ring.r, ring.g, ring.b, ring.a * 0.7), 2.0)

    # Horizon render with roll rotation and pitch shift.
    var roll_rad: float = deg_to_rad(roll * 25.0)
    var pitch_off: float = pitch * r * 0.28

    draw_set_transform(c, roll_rad, Vector2.ONE)
    draw_rect(Rect2(Vector2(-r, -r), Vector2(2.0 * r, r + pitch_off)), sky, true)
    draw_rect(Rect2(Vector2(-r, pitch_off), Vector2(2.0 * r, r - pitch_off)), water, true)
    draw_line(Vector2(-r, pitch_off), Vector2(r, pitch_off), line, 2.0)
    draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)

    # Center reticle
    draw_line(c + Vector2(-r * 0.12, 0), c + Vector2(r * 0.12, 0), line, 2.0)
    draw_line(c + Vector2(0, -r * 0.12), c + Vector2(0, r * 0.12), line, 2.0)

    # Bubble indicator
    var b: Vector2 = c + Vector2(roll, -pitch) * (r * 0.22)
    draw_circle(b, r * 0.06, bubble)
    draw_arc(b, r * 0.10, 0.0, TAU, 64, Color(bubble.r, bubble.g, bubble.b, 0.45), 2.0)

    # Tiny numeric pitch (optional, but useful)
    var font := get_theme_default_font()
    var fs := int(get_theme_default_font_size() * 0.9)
    var s := "P %+.2f" % pitch
    var sz := font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, fs)
    draw_string(font, c + Vector2(-sz.x * 0.5, r * 0.62), s, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, Color(0.65, 0.82, 1.0, 0.55))


func _spring_scalar(x: float, v: float, xt: float, dt: float, freq: float, damp: float) -> Vector2:
    var w: float = max(0.01, freq) * TAU
    var z: float = clamp(damp, 0.05, 2.0)

    var f: float = 1.0 + 2.0 * dt * z * w
    var oo: float = w * w
    var hoo: float = dt * oo
    var hhoo: float = dt * hoo
    var det_inv: float = 1.0 / max(1e-6, f + hhoo)

    var x_new: float = (f * x + dt * v + hhoo * xt) * det_inv
    var v_new: float = (v + hoo * (xt - x)) * det_inv
    return Vector2(x_new, v_new)
