extends Node3D

@onready var cam_pivot: Node3D = $CameraPivot
@onready var cam: Camera3D = $CameraPivot/Camera3D
@onready var grid := $Grid
var contacts_root: Node3D
var torpedoes_root: Node3D

const WORLD_SCALE := 0.02 # meters to world units

var zoom: float = 1.0
var zoom_min: float = 0.5
var zoom_max: float = 3.0

const GLYPH_SHADER := preload("res://shaders/contact_glyph.gdshader")

var _player_marker: Node3D
var _cam_base: Vector3 = Vector3(0, 12, 24)
var _parallax: Vector3 = Vector3.ZERO
var _last_hdg: float = 0.0
var _have_hdg: bool = false

func _ready() -> void:
    # Container for dynamic contact markers
    contacts_root = Node3D.new()
    contacts_root.name = "Contacts"
    add_child(contacts_root)
    torpedoes_root = Node3D.new()
    torpedoes_root.name = "Torpedoes"
    add_child(torpedoes_root)

    _player_marker = _make_player_marker()
    add_child(_player_marker)
    _apply_zoom(1.0)

func update_from_engine(pose: Dictionary) -> void:
    var hdg: float = float(pose.get("heading", 0.0))
    rotation.y = deg_to_rad(hdg)

    # Keep player centered: offset contacts by -player position.
    var px: float = float(pose.get("x", 0.0))
    var py: float = float(pose.get("y", 0.0))
    if contacts_root:
        contacts_root.position = Vector3(-px * WORLD_SCALE, 0.0, -py * WORLD_SCALE)

    # Optionally position camera pivot later based on player position
    # Apply gridline skew (opposes the turn) based on heading error
    var tgt: float = float(pose.get("heading_target", hdg))
    var err: float = fposmod(tgt - hdg + 540.0, 360.0) - 180.0
    var skew_scale: float = 6.0 # stronger visual
    var skew_val: float = float(clamp(err / 45.0, -1.0, 1.0)) * skew_scale
    if grid and grid.has_method("set_grid_skew"):
        grid.set_grid_skew(-skew_val) # oppose the turn visually
    # Move grid vertically to reflect player depth
    var depth: float = float(pose.get("depth", 0.0))
    if grid:
        grid.position.y = -depth * WORLD_SCALE

    # Tiny parallax drift on turns (premium feel without chrome).
    var d_h: float = 0.0
    if _have_hdg:
        d_h = fposmod(hdg - _last_hdg + 540.0, 360.0) - 180.0
    _have_hdg = true
    _last_hdg = hdg
    var drift: float = clamp(d_h / 12.0, -1.0, 1.0) * 0.35
    _parallax.x = lerp(_parallax.x, -drift, 0.12)
    _update_camera()

    # Billboard player marker.
    if _player_marker and _player_marker.get_child_count() > 0:
        var glyph := _player_marker.get_child(0)
        if glyph and glyph is Node3D:
            (glyph as Node3D).look_at(cam.global_position, Vector3.UP)

func _unhandled_input(event: InputEvent) -> void:
    if event is InputEventMagnifyGesture:
        var m: InputEventMagnifyGesture = event as InputEventMagnifyGesture
        _apply_zoom(pow(1.0 / 0.9, m.factor))
    elif event is InputEventMouseButton and event.pressed:
        var mb: InputEventMouseButton = event as InputEventMouseButton
        if mb.button_index == MOUSE_BUTTON_WHEEL_UP:
            _apply_zoom(0.9)
        elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
            _apply_zoom(1.1)

func apply_zoom_factor(f: float) -> void:
    _apply_zoom(f)

func _apply_zoom(f: float) -> void:
    zoom = clamp(zoom * f, zoom_min, zoom_max)
    var t: float = (zoom - zoom_min) / max(0.001, (zoom_max - zoom_min))
    # Smaller zoom => closer camera (zoom in).
    var y: float = lerp(8.0, 19.0, t)
    var z: float = lerp(16.0, 44.0, t)
    _cam_base = Vector3(0.0, y, z)
    _update_camera()

func _update_camera() -> void:
    cam_pivot.position = _cam_base + _parallax

var waves: Array[Dictionary] = [] # [{node: MeshInstance3D, age: float, ttl: float}]
const PING_TTL := 3.0
const WAVE_SPEED := 50.0 # world units per second

func spawn_ping() -> void:
    var sphere: MeshInstance3D = MeshInstance3D.new()
    var mesh: SphereMesh = SphereMesh.new()
    mesh.radial_segments = 32
    mesh.rings = 16
    sphere.mesh = mesh
    var mat: StandardMaterial3D = StandardMaterial3D.new()
    mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
    mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
    mat.albedo_color = Color(0.4, 0.8, 1.0, 0.35)
    sphere.material_override = mat
    add_child(sphere)
    sphere.scale = Vector3(0.01, 0.01, 0.01)
    waves.append({"node": sphere, "age": 0.0, "ttl": PING_TTL})

func _process(delta: float) -> void:
    for w in waves:
        var age: float = float(w.get("age", 0.0)) + delta
        w["age"] = age
        var r: float = max(0.01, age * WAVE_SPEED)
        var s: Vector3 = Vector3(r, r, r)
        var node: MeshInstance3D = w.get("node") as MeshInstance3D
        node.scale = s
        var ttl: float = float(w.get("ttl", PING_TTL))
        var t: float = clamp(1.0 - (age / ttl), 0.0, 1.0)
        var col: Color = Color(0.4, 0.8, 1.0, 0.35 * t)
        (node.material_override as StandardMaterial3D).albedo_color = col
    for i in range(waves.size()-1, -1, -1):
        if float(waves[i].get("age", 0.0)) >= float(waves[i].get("ttl", PING_TTL)):
            var n: Node3D = waves[i].get("node") as Node3D
            n.queue_free()
            waves.remove_at(i)

# Contact markers -------------------------------------------------------------
var _contact_nodes: Dictionary = {} # id -> Node3D
var _torpedo_nodes: Dictionary = {} # id -> Node3D

func render_contacts(contacts: Array) -> void:
    var seen: Dictionary = {}
    for c in contacts:
        var id: String = _contact_id(c)
        if id == "":
            continue
        seen[id] = true
        var node: Node3D = _contact_nodes.get(id)
        if node == null:
            node = _make_contact_node(c)
            _contact_nodes[id] = node
            contacts_root.add_child(node)
        _update_contact_node(node, c)
    # Remove stale markers
    for k in _contact_nodes.keys():
        if not seen.has(k):
            var n: Node3D = _contact_nodes[k]
            if is_instance_valid(n):
                n.queue_free()
            _contact_nodes.erase(k)

func render_torpedoes(torpedoes: Array) -> void:
    var seen: Dictionary = {}
    for t in torpedoes:
        var id: String = _torpedo_id(t)
        if id == "":
            continue
        seen[id] = true
        var node: Node3D = _torpedo_nodes.get(id)
        if node == null:
            node = _make_torpedo_node()
            _torpedo_nodes[id] = node
            torpedoes_root.add_child(node)
        _update_torpedo_node(node, t)
    for k in _torpedo_nodes.keys():
        if not seen.has(k):
            var n: Node3D = _torpedo_nodes[k]
            if is_instance_valid(n):
                n.queue_free()
            _torpedo_nodes.erase(k)

func _make_contact_node(c) -> Node3D:
    var n := Node3D.new()
    n.name = _contact_id(c)
    var mesh := MeshInstance3D.new()
    var quad := QuadMesh.new()
    quad.size = Vector2(2.2, 2.2)
    mesh.mesh = quad

    var mat := ShaderMaterial.new()
    mat.shader = GLYPH_SHADER
    mat.set_shader_parameter("tint", _contact_color(c))
    mat.set_shader_parameter("shape", _contact_shape(c))
    mesh.material_override = mat
    n.add_child(mesh)

    # Lift slightly above the grid plane.
    mesh.position = Vector3(0, 0.25, 0)
    return n

func _update_contact_node(n: Node3D, c) -> void:
    var x: float = _contact_x(c) * WORLD_SCALE
    var y: float = _contact_y(c) * WORLD_SCALE
    n.position = Vector3(x, 0.0, y)

    # Billboard toward camera.
    if n.get_child_count() > 0:
        var glyph := n.get_child(0)
        if glyph and glyph is Node3D:
            (glyph as Node3D).look_at(cam.global_position, Vector3.UP)

    # Subtle size emphasis based on confidence.
    var conf: float = _contact_confidence(c)
    n.scale = Vector3.ONE * lerp(0.85, 1.2, clamp(conf, 0.0, 1.0))

func _contact_id(c) -> String:
    if c is Dictionary:
        return String(c.get("id", ""))
    return String(c.id)

func _contact_heading(c) -> float:
    if c is Dictionary:
        return float(c.get("heading_deg", c.get("heading", 0.0)))
    return float(c.heading_deg)

func _contact_x(c) -> float:
    if c is Dictionary:
        return float(c.get("x", 0.0))
    return float(c.x)

func _contact_y(c) -> float:
    if c is Dictionary:
        return float(c.get("y", 0.0))
    return float(c.y)

func _contact_color(c) -> Color:
    var t := ""
    if c is Dictionary:
        t = String(c.get("typ", ""))
    else:
        t = String(c.typ)
    if t == "sub":
        return Color(1.0, 0.5, 0.2, 1.0)
    if t == "escort":
        return Color(1.0, 0.55, 0.30, 1.0) # hostile-ish
    return Color(0.45, 0.90, 1.0, 1.0)

func _contact_shape(c) -> int:
    var t := ""
    if c is Dictionary:
        t = String(c.get("typ", ""))
    else:
        t = String(c.typ)
    # triangle for hostile/unknown subs, circle for neutral.
    if t in ["sub", "escort"]:
        return 1
    return 0

func _contact_confidence(c) -> float:
    if c is Dictionary:
        return float(c.get("confidence", 0.0))
    return float(c.confidence)

func _make_torpedo_node() -> Node3D:
    var n := Node3D.new()
    var mesh := MeshInstance3D.new()
    var sphere := SphereMesh.new()
    sphere.radial_segments = 12
    sphere.rings = 8
    sphere.radius = 0.22
    sphere.height = 0.44
    mesh.mesh = sphere
    var mat := StandardMaterial3D.new()
    mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
    mat.albedo_color = Color(1.0, 0.68, 0.34, 0.92)
    mesh.material_override = mat
    mesh.position = Vector3(0, 0.18, 0)
    n.add_child(mesh)
    return n

func _update_torpedo_node(n: Node3D, t) -> void:
    var x: float = float(t.get("x", 0.0)) * WORLD_SCALE
    var y: float = float(t.get("y", 0.0)) * WORLD_SCALE
    n.position = Vector3(x, 0.0, y)
    if n.get_child_count() > 0:
        var glyph := n.get_child(0)
        if glyph and glyph is Node3D:
            (glyph as Node3D).look_at(cam.global_position, Vector3.UP)

func _torpedo_id(t) -> String:
    if t is Dictionary:
        return String(t.get("id", ""))
    return ""

func _make_player_marker() -> Node3D:
    var n := Node3D.new()
    n.name = "Player"
    var mesh := MeshInstance3D.new()
    var quad := QuadMesh.new()
    quad.size = Vector2(2.6, 2.6)
    mesh.mesh = quad
    var mat := ShaderMaterial.new()
    mat.shader = GLYPH_SHADER
    mat.set_shader_parameter("tint", Color(0.55, 0.90, 1.0, 1.0))
    mat.set_shader_parameter("shape", 1)
    mesh.material_override = mat
    mesh.position = Vector3(0, 0.25, 0)
    n.add_child(mesh)
    return n
