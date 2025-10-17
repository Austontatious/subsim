extends Node
class_name SubsimEngine

# Public API:
# - step(dt: float)
# - cmd_ping()
# - set_telegraph(tele: int)  # -5..5 reverse/full ahead in detents
# - turn_deg(delta: float)
# - set_heading_target(deg: float)
# - set_depth_target(meters: float)

const D0 := 500.0      # rolloff reference
const KNOT := 0.514444
const FULL_KTS := 35.0
const MAX_SPEED := FULL_KTS * KNOT # m/s at Full ahead (forward or reverse)
# Telegraph detents: -5..5 (Rev Full .. Ahead Full)
const TELE_TO_SPEED := {
    -5: -MAX_SPEED,
    -4: -(0.75 * MAX_SPEED),
    -3: -(0.5 * MAX_SPEED),
    -2: -(0.25 * MAX_SPEED),
    -1: -(0.125 * MAX_SPEED),
     0: 0.0,
     1: 0.125 * MAX_SPEED,
     2: 0.25 * MAX_SPEED,
     3: 0.5 * MAX_SPEED,
     4: 0.75 * MAX_SPEED,
     5: 1.0 * MAX_SPEED,
}
const TURN_RATE_DEGPS := 40.0

signal sfx_ping()
signal mix_contact(id: String, pan_l: float, pan_r: float, gain: float)

var rng: RandomNumberGenerator = RandomNumberGenerator.new()

# State
var heading_deg: float = 0.0
var heading_target_deg: float = 0.0
var speed_mps: float = 0.0
var depth_m: float = 200.0
var depth_target: float = 200.0
var telegraph: int = -1  # Stop
var ping_age: float = 999.0

# Contacts (demo)
class Contact:
    var id: String = ""
    var typ: String = "merchant" # "sub" | "merchant" | "escort"
    var x: float = 0.0; var y: float = 0.0
    var heading_deg: float = 0.0
    var speed_mps: float = 0.0
    var confidence: float = 0.4

func _ready() -> void:
    rng.seed = 7
    _spawn_demo()

func _spawn_demo():
    _contacts.clear()
    var h := Contact.new(); h.id = "H"; h.typ="sub"; h.x=1200; h.y=0; h.heading_deg=200; h.speed_mps=10
    var m := Contact.new(); m.id = "M"; m.typ="merchant"; m.x=-1800; m.y=800; m.heading_deg=20; m.speed_mps=6
    _contacts = [h, m]

var _contacts: Array = []

func step(dt: float) -> void:
    # player kinematics
    var tgt: float = float(TELE_TO_SPEED.get(telegraph, 0.0))
    speed_mps = move_toward(speed_mps, tgt, 1.5 * dt)
    depth_m = move_toward(depth_m, depth_target, 3.0 * dt)

    # turn towards target heading with bounded rate
    var diff: float = _angle_diff_deg(heading_target_deg, heading_deg)
    var max_step: float = TURN_RATE_DEGPS * dt
    var step_deg: float = clamp(diff, -max_step, max_step)
    heading_deg = fposmod(heading_deg + step_deg + 360.0, 360.0)

    var rad: float = deg_to_rad(heading_deg)
    var vx: float = cos(rad) * speed_mps
    var vy: float = sin(rad) * speed_mps
    _player_x += vx * dt
    _player_y += vy * dt

    # update contacts
    for c in _contacts:
        var cr: float = deg_to_rad(c.heading_deg)
        c.x += cos(cr) * c.speed_mps * dt
        c.y += sin(cr) * c.speed_mps * dt
        c.confidence = clamp(c.confidence + rng.randf_range(-0.02, 0.03), 0.2, 1.0)

    # sensors
    ping_age += dt
    _emit_passive_mix()
    # Note: active returns handled when cmd_ping() is called

func _emit_passive_mix():
    var own_noise: float = clamp(speed_mps * 0.05, 0.0, 0.8)
    for c in _contacts:
        var dx: float = c.x - _player_x
        var dy: float = c.y - _player_y
        var dist: float = sqrt(dx*dx + dy*dy)
        var bearing: float = rad_to_deg(atan2(dy, dx)) - heading_deg
        var az: float = deg_to_rad(fposmod(bearing, 360.0))
        var l: float = sqrt(0.5 * (1.0 + cos(az)))
        var r: float = sqrt(0.5 * (1.0 - cos(az)))
        # distance rolloff + confidence + own_noise, no occlusion yet
        var g: float = 1.0 / (1.0 + pow(dist / D0, 2.0))
        g *= (0.4 + 0.6 * c.confidence)
        g *= max(0.2, 1.0 - own_noise)
        emit_signal("mix_contact", c.id, l, r, g)

# Commands
func cmd_ping():
    ping_age = 0.0
    emit_signal("sfx_ping")

func set_telegraph(tele: int) -> void:
    telegraph = tele

func turn_deg(delta: float) -> void:
    heading_deg = fposmod(heading_deg + delta, 360.0)
    heading_target_deg = heading_deg

func set_heading_target(deg: float) -> void:
    heading_target_deg = fposmod(deg + 360.0, 360.0)

func set_depth_target(meters: float) -> void:
    depth_target = clamp(meters, 0.0, 1000.0)

# Exposed for HUD
var _player_x: float = 0.0
var _player_y: float = 0.0
func get_player_pose() -> Dictionary:
    return {
        "x": _player_x, "y": _player_y, "depth": depth_m,
        "heading": heading_deg, "heading_target": heading_target_deg,
        "speed": speed_mps, "ping_age": ping_age
    }
func get_contacts() -> Array:
    return _contacts

func _angle_diff_deg(target: float, current: float) -> float:
    var a := fposmod(target - current + 540.0, 360.0) - 180.0
    return a
