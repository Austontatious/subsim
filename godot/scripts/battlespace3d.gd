extends Node3D

@onready var cam_pivot: Node3D = $CameraPivot
@onready var cam: Camera3D = $CameraPivot/Camera3D
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
        var id: String = String(c.get("id", ""))
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

func _make_contact_node(c: Dictionary) -> Node3D:
    var n := Node3D.new()
    n.name = String(c.get("id", "C"))
    var mesh := MeshInstance3D.new()
    var geom := CylinderMesh.new()
    geom.top_radius = 0.0
    geom.bottom_radius = 0.4
    geom.height = 1.0
    mesh.mesh = geom
    var mat := StandardMaterial3D.new()
    mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
    mat.albedo_color = Color(1.0, 0.6, 0.3, 1.0) if String(c.get("typ","")) == "sub" else Color(0.5, 0.9, 0.6, 1.0)
    mesh.material_override = mat
    n.add_child(mesh)
    # Lift slightly above grid
    mesh.position = Vector3(0, 0.5, 0)
    return n

func _update_contact_node(n: Node3D, c: Dictionary) -> void:
    var x: float = float(c.get("x", 0.0)) * WORLD_SCALE
    var y: float = float(c.get("y", 0.0)) * WORLD_SCALE
    n.position = Vector3(x, 0.0, y)
    var hdg: float = float(c.get("heading_deg", c.get("heading", 0.0)))
    n.rotation.y = deg_to_rad(hdg)
