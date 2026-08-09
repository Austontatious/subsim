extends Node3D

@onready var engine: SubsimEngine = $Engine as SubsimEngine
@onready var space3d: Node3D = get_node_or_null("Battlespace3D") as Node3D
@onready var sonar: SonarOverlay = $CanvasLayer/HUD/SonarOverlay as SonarOverlay
@onready var attitude: AttitudeDial = $CanvasLayer/HUD/Controls/AttitudeDial as AttitudeDial
@onready var heading: HeadingDial = $CanvasLayer/HUD/Controls/HeadingDial as HeadingDial
@onready var context: ContextStrip = $CanvasLayer/HUD/ContextStrip as ContextStrip

const DT := 1.0 / 30.0

var _touch: Dictionary = {} # index -> Vector2
var _pinch_prev_dist: float = 0.0
var _two_finger_candidate: bool = false
var _two_finger_moved: bool = false
var _two_finger_t0_ms: int = 0


func _ready() -> void:
	get_viewport().size_changed.connect(_layout_ui)
	_layout_ui()

	if heading and heading.has_signal("target_changed"):
		heading.target_changed.connect(_on_heading_target)
	if context and context.has_signal("ping_pressed"):
		context.ping_pressed.connect(_on_ping_pressed)
	if context and context.has_signal("fire_pressed"):
		context.fire_pressed.connect(_on_fire_pressed)

	if engine:
		engine.sfx_ping.connect(_on_engine_ping)
		if engine.has_signal("sfx_fire"):
			engine.sfx_fire.connect(_on_engine_fire)

		# Default cruise: avoid speed chrome; keep it "sub-feel" instead of instrument ops.
		engine.set_telegraph(2)


func _layout_ui() -> void:
	var vp: Vector2 = get_viewport().get_visible_rect().size
	var w: float = vp.x
	var h: float = vp.y
	if w <= 0.0 or h <= 0.0:
		return

	var dial_size: float = clamp(h * 0.42, 200.0, min(w * 0.46, h * 0.52))
	var y_center: float = h * 0.47
	var margin: float = max(18.0, w * 0.055)

	if attitude:
		attitude.position = Vector2(margin, y_center - dial_size * 0.5)
		attitude.size = Vector2(dial_size, dial_size)
	if heading:
		heading.position = Vector2(w - margin - dial_size, y_center - dial_size * 0.5)
		heading.size = Vector2(dial_size, dial_size)

	if context:
		# Mobile controls should stay comfortably tappable.
		var strip_h: float = clamp(h * 0.14, 96.0, 140.0)
		context.offset_top = -strip_h - 10.0
		context.offset_bottom = -10.0


func _physics_process(_dt: float) -> void:
	if attitude and engine and engine.has_method("set_pitch_roll"):
		engine.set_pitch_roll(attitude.pitch, attitude.roll)

	engine.step(DT)
	var p: Dictionary = engine.get_player_pose()
	var contacts: Array = engine.get_contacts()
	var torpedoes: Array = []
	if engine and engine.has_method("get_torpedoes"):
		torpedoes = engine.get_torpedoes()

	# Update battlespace layer.
	if space3d and space3d.has_method("update_from_engine"):
		space3d.update_from_engine(p)
		if space3d.has_method("render_contacts"):
			space3d.render_contacts(contacts)
		if space3d.has_method("render_torpedoes"):
			space3d.render_torpedoes(torpedoes)

	# Heading dial (compass degrees for UX).
	var cur_h_engine: float = float(p.get("heading", 0.0))
	var tgt_h_engine: float = float(p.get("heading_target", cur_h_engine))
	var cur_h: float = _engine_to_compass(cur_h_engine)
	var tgt_h: float = _engine_to_compass(tgt_h_engine)
	heading.current_heading = cur_h
	if not heading.dragging:
		heading.target_heading = tgt_h

	var ghost: Dictionary = _best_contact_bearing_rel_compass(contacts, float(p.get("x", 0.0)), float(p.get("y", 0.0)), cur_h)
	var ghost_ok: bool = bool(ghost.get("ok", false))
	if ghost_ok:
		heading.ghost_visible = true
		heading.ghost_bearing = float(ghost.get("bearing", 0.0))
	else:
		heading.ghost_visible = false

	# Context strip: always visible on mobile for discoverability.
	var show_strip: bool = true
	var torpedo_ammo: int = int(p.get("torpedo_ammo", 0))
	var active_torpedoes: int = int(p.get("active_torpedoes", 0))
	var fire_cooldown_s: float = float(p.get("fire_cooldown_s", 0.0))
	var torp_ready: bool = torpedo_ammo > 0
	var fire_ready: bool = bool(p.get("can_fire_torpedo", false)) or (torpedo_ammo > 0 and fire_cooldown_s <= 0.05)
	if context:
		context.set_status(
			float(p.get("depth", 0.0)),
			float(p.get("speed", 0.0)),
			torp_ready,
			fire_ready,
			torpedo_ammo,
			active_torpedoes,
			fire_cooldown_s
		)
		context.show_strip(show_strip)


func _input(event: InputEvent) -> void:
	# Global touch gesture layer (so pinch works even over UI controls).
	if event is InputEventScreenTouch:
		var st := event as InputEventScreenTouch
		if st.pressed:
			_touch[st.index] = st.position
			if _touch.size() == 2:
				_two_finger_candidate = true
				_two_finger_moved = false
				_two_finger_t0_ms = Time.get_ticks_msec()
				_pinch_prev_dist = _pinch_dist()
		else:
			_touch.erase(st.index)
			if _touch.size() == 0:
				if _two_finger_candidate and not _two_finger_moved:
					var dt_ms: int = Time.get_ticks_msec() - _two_finger_t0_ms
					if dt_ms <= 240:
						engine.cmd_ping()
				_two_finger_candidate = false
				_two_finger_moved = false
				_pinch_prev_dist = 0.0
	elif event is InputEventScreenDrag:
		var sd := event as InputEventScreenDrag
		if _touch.has(sd.index):
			_touch[sd.index] = sd.position
		if _touch.size() == 2:
			var d: float = _pinch_dist()
			if _pinch_prev_dist > 0.0 and d > 0.0:
				var factor: float = d / _pinch_prev_dist
				if abs(1.0 - factor) > 0.03:
					_two_finger_moved = true
				_pinch_prev_dist = d
				if space3d and space3d.has_method("apply_zoom_factor"):
					# Pinch out (factor>1) -> zoom in.
					space3d.apply_zoom_factor(1.0 / max(0.001, factor))

	# Dev keyboard fallback
	if event.is_action_pressed("ui_accept"):
		engine.cmd_ping()


func _pinch_dist() -> float:
	var keys: Array = _touch.keys()
	if keys.size() != 2:
		return 0.0
	var a: Vector2 = _touch[keys[0]]
	var b: Vector2 = _touch[keys[1]]
	return a.distance_to(b)


func _on_heading_target(deg_compass: float) -> void:
	var deg_engine: float = _compass_to_engine(deg_compass)
	engine.set_heading_target(deg_engine)


func _on_ping_pressed() -> void:
	if engine and engine.has_method("cmd_ping"):
		engine.cmd_ping()


func _on_fire_pressed() -> void:
	if engine and engine.has_method("cmd_fire"):
		engine.cmd_fire()


func _on_engine_ping() -> void:
	if space3d and space3d.has_method("spawn_ping"):
		space3d.spawn_ping()
	if sonar:
		sonar.ping_pulse()

func _on_engine_fire() -> void:
	if sonar:
		sonar.pulse(0.85, 0.22)


func _engine_to_compass(deg_engine: float) -> float:
	# Engine uses math angle: 0=+X, +CCW. UI uses compass: 0=up/N, +CW.
	return fposmod(90.0 - deg_engine + 360.0, 360.0)


func _compass_to_engine(deg_compass: float) -> float:
	return fposmod(90.0 - deg_compass + 360.0, 360.0)


func _best_contact_bearing_rel_compass(contacts: Array, px: float, py: float, cur_compass: float) -> Dictionary:
	var best = null
	var best_q: float = -1.0
	for c in contacts:
		var q: float = _contact_confidence(c)
		if q > best_q:
			best_q = q
			best = c
	if best == null:
		return {"ok": false}

	var dx: float = _contact_x(best) - px
	var dy: float = _contact_y(best) - py
	var ang_abs_engine: float = rad_to_deg(atan2(dy, dx))
	var bearing_abs_compass: float = _engine_to_compass(ang_abs_engine)
	var rel: float = fposmod(bearing_abs_compass - cur_compass + 360.0, 360.0)
	return {"ok": true, "bearing": rel, "quality": best_q}


func _contact_confidence(c) -> float:
	if c is Dictionary:
		return float(c.get("confidence", 0.0))
	if c != null and c.has_method("get"):
		# fallthrough for unexpected types
		pass
	return float(c.confidence) if c != null else 0.0


func _contact_x(c) -> float:
	if c is Dictionary:
		return float(c.get("x", 0.0))
	return float(c.x) if c != null else 0.0


func _contact_y(c) -> float:
	if c is Dictionary:
		return float(c.get("y", 0.0))
	return float(c.y) if c != null else 0.0
