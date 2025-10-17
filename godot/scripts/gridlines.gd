extends MeshInstance3D

@export var half_size: float = 50.0
@export var step: float = 5.0
@export var y_level: float = 0.0

func _ready() -> void:
    var im := ImmediateMesh.new()
    im.surface_begin(Mesh.PRIMITIVE_LINES)
    var col := Color(0.6, 0.8, 1.0, 0.35)
    # XZ grid at y_level
    var hs := half_size
    var st := step
    var y := y_level
    for x in range(int(-hs), int(hs)+1, int(st)):
        _add_line(im, Vector3(x, y, -hs), Vector3(x, y, hs), col)
    for z in range(int(-hs), int(hs)+1, int(st)):
        _add_line(im, Vector3(-hs, y, z), Vector3(hs, y, z), col)
    # Bounding cube edges
    var corners := [
        Vector3(-hs,-hs,-hs), Vector3(hs,-hs,-hs), Vector3(hs,-hs,hs), Vector3(-hs,-hs,hs),
        Vector3(-hs, hs,-hs), Vector3(hs, hs,-hs), Vector3(hs, hs,hs), Vector3(-hs, hs,hs)
    ]
    var edges := [
        [0,1],[1,2],[2,3],[3,0],
        [4,5],[5,6],[6,7],[7,4],
        [0,4],[1,5],[2,6],[3,7]
    ]
    for e in edges:
        _add_line(im, corners[e[0]], corners[e[1]], Color(0.5,0.7,1.0,0.25))
    im.surface_end()

    mesh = im
    var mat := StandardMaterial3D.new()
    mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
    mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
    material_override = mat

func _add_line(im: ImmediateMesh, a: Vector3, b: Vector3, color: Color) -> void:
    im.surface_set_color(color)
    im.surface_add_vertex(a)
    im.surface_set_color(color)
    im.surface_add_vertex(b)

