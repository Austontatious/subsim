extends Control
class_name HeadingDial

# Mobile-first heading control:
# - Center readout (large)
# - 10-degree ticks
# - Drag to set target heading (with subtle resistance)
# - Optional ghost needle for target bearing (relative, 0 = ahead)

@export var current_heading: float = 0.0
@export var target_heading: float = 0.0

# Relative bearing (degrees, 0=ahead, 90=starboard/right, 180=astern, 270=port/left).
@export var ghost_bearing: float = 0.0
@export var ghost_visible: bool = false

signal target_changed(deg: float)

var dragging: bool = false
var _active_touch: int = -1

var _desired_target: float = 0.0
var _vel: float = 0.0
var _display_target: float = 0.0
var _last_emit: float = 0.0


func _ready() -> void:
    mouse_filter = Control.MOUSE_FILTER_STOP
    _desired_target = target_heading
    _display_target = target_heading
    _last_emit = target_heading


func _process(dt: float) -> void:
    # When not dragging, follow externally-set target_heading smoothly.
    if not dragging:
        _desired_target = target_heading

    # Spring toward desired target for a "dial with resistance" feel.
    var res: Vector2 = _spring_angle(_display_target, _vel, _desired_target, dt, 14.0, 0.85)
    _display_target = res.x
    _vel = res.y

    # Only drive the output target while dragging. Otherwise we are just a display.
    if dragging:
        target_heading = _display_target
        if _angle_abs_diff(_last_emit, target_heading) >= 0.25:
            _last_emit = target_heading
            emit_signal("target_changed", target_heading)

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
        # If a second finger comes down, stop dial dragging (pinch gesture is global).
        if st.pressed:
            if not dragging:
                dragging = true
                _active_touch = st.index
                _apply_from_pos(_screen_to_local(st.position))
            elif _active_touch != st.index:
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
    var c: Vector2 = size * 0.5
    var v: Vector2 = pos - c
    if v.length() < 6.0:
        return
    # 0° at up (north), increasing clockwise (screen-space).
    var ang: float = atan2(v.y, v.x)
    var deg: float = fposmod(rad_to_deg(ang) + 90.0 + 360.0, 360.0)
    _desired_target = deg


func _screen_to_local(screen_pos: Vector2) -> Vector2:
    # Touch events report viewport coordinates; convert to this control's local space.
    return get_global_transform_with_canvas().affine_inverse() * screen_pos


func _draw() -> void:
    var r: float = min(size.x, size.y) * 0.46
    var c: Vector2 = size * 0.5

    var base := Color(0.03, 0.08, 0.12, 0.24)
    var ring := Color(0.55, 0.82, 1.0, 0.55)
    var tick := Color(0.55, 0.82, 1.0, 0.60)
    var accent := Color(1.00, 0.66, 0.35, 0.90)
    var ghost := Color(0.35, 0.90, 1.0, 0.75)

    draw_circle(c, r, base)
    draw_arc(c, r, 0.0, TAU, 160, ring, 2.0)
    draw_arc(c, r * 0.86, 0.0, TAU, 160, Color(ring.r, ring.g, ring.b, ring.a * 0.65), 2.0)

    # Ticks: every 10°, longer every 30°.
    for d in range(0, 360, 10):
        var major := (d % 30) == 0
        var len0 := r * (0.08 if major else 0.045)
        var w := 2.0 if major else 1.0
        # Rotate tick card by current heading so the lubber line reads current heading.
        var ang_tick: float = deg_to_rad(float(d) - current_heading - 90.0)
        var p1: Vector2 = c + Vector2(r - len0, 0).rotated(ang_tick)
        var p2: Vector2 = c + Vector2(r, 0).rotated(ang_tick)
        draw_line(p1, p2, tick, w)

    # Cardinal hints (subtle).
    var font := get_theme_default_font()
    var fs := int(get_theme_default_font_size() * 0.85)
    for item in [
        {"lab": "N", "deg": 0.0},
        {"lab": "E", "deg": 90.0},
        {"lab": "S", "deg": 180.0},
        {"lab": "W", "deg": 270.0}
    ]:
        var a: float = deg_to_rad(float(item.get("deg", 0.0)) - current_heading - 90.0)
        var tp: Vector2 = c + Vector2(r * 0.70, 0).rotated(a)
        var lab: String = String(item.get("lab", ""))
        var sz: Vector2 = font.get_string_size(lab, HORIZONTAL_ALIGNMENT_LEFT, -1, fs)
        draw_string(
            font,
            tp - Vector2(sz.x * 0.5, -fs * 0.35),
            lab,
            HORIZONTAL_ALIGNMENT_LEFT,
            -1,
            fs,
            Color(tick.r, tick.g, tick.b, 0.55)
        )

    # Lubber line (fixed at top).
    var tip: Vector2 = c + Vector2(0.0, -r * 1.02)
    draw_line(c + Vector2(0, -r * 0.92), tip, ring, 2.0)
    draw_colored_polygon([tip, tip + Vector2(-6, 10), tip + Vector2(6, 10)], ring)

    # Target heading bug (relative to current).
    var rel: float = _angle_diff_deg(target_heading, current_heading) # [-180,180]
    var a_bug: float = deg_to_rad(rel - 90.0)
    var q1: Vector2 = c + Vector2(r * 0.78, 0).rotated(a_bug)
    var q2: Vector2 = c + Vector2(r * 0.98, 0).rotated(a_bug)
    draw_line(q1, q2, accent, 3.0)

    # Ghost bearing needle (relative, 0=ahead).
    if ghost_visible:
        var a_ghost: float = deg_to_rad(ghost_bearing - 90.0)
        var g1: Vector2 = c + Vector2(r * 0.18, 0).rotated(a_ghost)
        var g2: Vector2 = c + Vector2(r * 0.96, 0).rotated(a_ghost)
        draw_line(g1, g2, ghost, 2.0)

    # Center readout: target large, current small.
    var tgt: int = int(round(_display_target)) % 360
    var cur: int = int(round(current_heading)) % 360

    var big: int = int(get_theme_default_font_size() * 2.3)
    var small: int = int(get_theme_default_font_size() * 0.9)
    var s_tgt := "%03d" % tgt
    var s_cur := "CUR %03d" % cur
    var sz_tgt := font.get_string_size(s_tgt, HORIZONTAL_ALIGNMENT_LEFT, -1, big)
    var sz_cur := font.get_string_size(s_cur, HORIZONTAL_ALIGNMENT_LEFT, -1, small)
    draw_string(
        font,
        c - Vector2(sz_tgt.x * 0.5, -big * 0.35),
        s_tgt,
        HORIZONTAL_ALIGNMENT_LEFT,
        -1,
        big,
        Color(0.90, 0.96, 1.0, 0.92)
    )
    draw_string(
        font,
        c + Vector2(-sz_cur.x * 0.5, big * 0.46),
        s_cur,
        HORIZONTAL_ALIGNMENT_LEFT,
        -1,
        small,
        Color(0.65, 0.82, 1.0, 0.70)
    )


func _angle_diff_deg(a: float, b: float) -> float:
    return fposmod(a - b + 540.0, 360.0) - 180.0


func _angle_abs_diff(a: float, b: float) -> float:
    return abs(_angle_diff_deg(a, b))


func _spring_angle(x: float, v: float, xt: float, dt: float, freq: float, damp: float) -> Vector2:
    # Lightweight second-order spring. freq in Hz-ish (larger = stiffer), damp near 1.0 = critically damped.
    var w: float = max(0.01, freq) * TAU
    var z: float = clamp(damp, 0.05, 2.0)
    # Convert angle to a signed error to avoid wrap discontinuities.
    var e: float = deg_to_rad(_angle_diff_deg(xt, x))
    var xr: float = 0.0
    var vr: float = deg_to_rad(v)

    var f: float = 1.0 + 2.0 * dt * z * w
    var oo: float = w * w
    var hoo: float = dt * oo
    var hhoo: float = dt * hoo
    var det_inv: float = 1.0 / max(1e-6, f + hhoo)

    xr = (f * 0.0 + dt * vr + hhoo * e) * det_inv
    vr = (vr + hoo * (e - xr)) * det_inv

    var x_out: float = fposmod(x + rad_to_deg(xr) + 360.0, 360.0)
    var v_out: float = rad_to_deg(vr)
    return Vector2(x_out, v_out)
