extends Node3D

@onready var cam_pivot: Node3D = $CameraPivot
@onready var cam: Camera3D = $CameraPivot/Camera3D

var zoom: float = 1.0
var zoom_min := 0.5
var zoom_max := 3.0

func update_from_engine(pose: Dictionary) -> void:
    rotation.y = deg_to_rad(pose.heading)

func _unhandled_input(event: InputEvent) -> void:
    if event is InputEventMagnifyGesture:
        var m = event as InputEventMagnifyGesture
        _apply_zoom(pow(1.0 / 0.9, m.factor))
    elif event is InputEventMouseButton and event.pressed:
        var mb = event as InputEventMouseButton
        if mb.button_index == MOUSE_BUTTON_WHEEL_UP:
            _apply_zoom(0.9)
        elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
            _apply_zoom(1.1)

func _apply_zoom(f: float) -> void:
    zoom = clamp(zoom * f, zoom_min, zoom_max)
    cam_pivot.position = Vector3(0, lerp(8.0, 18.0, zoom - 1.0), lerp(16.0, 36.0, zoom - 1.0))

var waves: Array = [] # [{node: MeshInstance3D, age: float, ttl: float}]
const PING_TTL := 3.0
const WAVE_SPEED := 50.0 # world units per second

func spawn_ping() -> void:
    var sphere := MeshInstance3D.new()
    var mesh := SphereMesh.new()
    mesh.radial_segments = 32
    mesh.rings = 16
    sphere.mesh = mesh
    var mat := StandardMaterial3D.new()
    mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
    mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
    mat.albedo_color = Color(0.4, 0.8, 1.0, 0.35)
    sphere.material_override = mat
    add_child(sphere)
    sphere.scale = Vector3(0.01, 0.01, 0.01)
    waves.append({"node": sphere, "age": 0.0, "ttl": PING_TTL})

func _process(delta: float) -> void:
    for w in waves:
        w.age += delta
        var r := max(0.01, w.age * WAVE_SPEED)
        var s := Vector3(r, r, r)
        (w.node as MeshInstance3D).scale = s
        var t := clamp(1.0 - (w.age / w.ttl), 0.0, 1.0)
        var col := Color(0.4, 0.8, 1.0, 0.35 * t)
        ((w.node as MeshInstance3D).material_override as StandardMaterial3D).albedo_color = col
    for i in range(waves.size()-1, -1, -1):
        if waves[i].age >= waves[i].ttl:
            var n := waves[i].node as Node3D
            n.queue_free()
            waves.remove_at(i)
