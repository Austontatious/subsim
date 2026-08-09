extends ColorRect
class_name SonarOverlay

@export var pulse_ttl: float = 0.35
@export var pulse_strength: float = 0.55

var _pulse_age: float = 999.0
var _pulse_ttl: float = 0.35
var _pulse_strength: float = 0.55

func _ready() -> void:
    mouse_filter = Control.MOUSE_FILTER_IGNORE
    color = Color(0, 0, 0, 0) # shader drives output

func ping_pulse() -> void:
    pulse(pulse_strength, pulse_ttl)

func pulse(strength: float, ttl: float) -> void:
    _pulse_strength = clamp(strength, 0.0, 1.5)
    _pulse_ttl = max(0.05, ttl)
    _pulse_age = 0.0

func _process(dt: float) -> void:
    _pulse_age += dt
    var v: float = 0.0
    if _pulse_age < _pulse_ttl:
        var t: float = 1.0 - (_pulse_age / max(0.001, _pulse_ttl))
        # Fast attack, gentle release.
        v = _pulse_strength * t * t
    if material and material is ShaderMaterial:
        (material as ShaderMaterial).set_shader_parameter("ping_pulse", v)
