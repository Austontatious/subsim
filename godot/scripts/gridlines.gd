extends MeshInstance3D

@export var half_size: float = 50.0
@export var step: float = 5.0
@export var y_level: float = 0.0

var _shader_mat: ShaderMaterial
var _skew: float = 0.0

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
    var shader := Shader.new()
    shader.code = """
shader_type spatial;
render_mode unshaded, cull_disabled, blend_mix;
uniform float skew : hint_range(-10.0, 10.0) = 0.0;
uniform float half_size = 50.0;

void vertex() {
    float t = POSITION.z / max(1.0, half_size);
    // Non-linear pull for a curved look
    float curv = t * abs(t);
    POSITION.x += skew * curv;
}

void fragment() {
    ALBEDO = COLOR.rgb;
    ALPHA = COLOR.a;
}
"""
    _shader_mat = ShaderMaterial.new()
    _shader_mat.shader = shader
    _shader_mat.set_shader_parameter("half_size", half_size)
    _shader_mat.set_shader_parameter("skew", _skew)
    material_override = _shader_mat

func _add_line(im: ImmediateMesh, a: Vector3, b: Vector3, color: Color) -> void:
    im.surface_set_color(color)
    im.surface_add_vertex(a)
    im.surface_set_color(color)
    im.surface_add_vertex(b)

func set_grid_skew(v: float) -> void:
    _skew = v
    if _shader_mat:
        _shader_mat.set_shader_parameter("skew", _skew)
