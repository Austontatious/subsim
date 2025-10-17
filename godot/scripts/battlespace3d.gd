extends Node3D

@onready var cam_pivot: Node3D = $CameraPivot
@onready var cam: Camera3D = $CameraPivot/Camera3D
@onready var grid := $Grid
var contacts_root: Node3D

const WORLD_SCALE := 0.02 # meters to world units

var zoom: float = 1.0
var zoom_min: float = 0.5
var zoom_max: float = 3.0

func _ready() -> void:
    # Container for dynamic contact markers
    contacts_root = Node3D.new()
    contacts_root.name = "Contacts"
    add_child(contacts_root)

func update_from_engine(pose: Dictionary) -> void:
    var hdg: float = float(pose.get("heading", 0.0))
    rotation.y = deg_to_rad(hdg)
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

func _apply_zoom(f: float) -> void:
    zoom = clamp(zoom * f, zoom_min, zoom_max)
    cam_pivot.position = Vector3(0, lerp(8.0, 18.0, zoom - 1.0), lerp(16.0, 36.0, zoom - 1.0))

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

func _make_contact_node(c) -> Node3D:
    var n := Node3D.new()
    n.name = _contact_id(c)
    var mesh := MeshInstance3D.new()
    var geom := CylinderMesh.new()
    geom.top_radius = 0.0
    geom.bottom_radius = 0.6
    geom.height = 1.5
    mesh.mesh = geom
    var mat := StandardMaterial3D.new()
    mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
    mat.albedo_color = _contact_color(c)
    mesh.material_override = mat
    n.add_child(mesh)
    # Lift slightly above grid
    mesh.position = Vector3(0, 0.5, 0)

    # Add floating label
    var label := Label3D.new()
    label.text = n.name
    label.position = Vector3(0, 1.4, 0)
    label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
    label.modulate = Color(1,1,1,0.9)
    n.add_child(label)
    return n

func _update_contact_node(n: Node3D, c) -> void:
    var x: float = _contact_x(c) * WORLD_SCALE
    var y: float = _contact_y(c) * WORLD_SCALE
    n.position = Vector3(x, 0.0, y)
    var hdg: float = _contact_heading(c)
    n.rotation.y = deg_to_rad(hdg)

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
        return Color(0.2, 1.0, 0.6, 1.0)
    return Color(0.6, 0.9, 1.0, 1.0)
