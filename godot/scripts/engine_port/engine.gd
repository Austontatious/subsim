extends Node
class_name Engine

# Public API:
# - step(dt: float)
# - cmd_ping()
# - set_telegraph(tele: int)  # -1 Stop, 0 1/4, 1 1/2, 2 Full, 3 Flank
# - turn_deg(delta: float)
# - set_depth_target(meters: float)

const D0 := 500.0      # rolloff reference
const MAX_SPEED := 8.0 # m/s at Flank
const TELE_TO_SPEED := { -1: 0.0, 0: 1.5, 1: 3.0, 2: 5.0, 3: MAX_SPEED }

signal sfx_ping()
signal mix_contact(id: String, pan_l: float, pan_r: float, gain: float)

var rng := RandomNumberGenerator.new()

# State
var heading_deg := 0.0
var speed_mps := 0.0
var depth_m := 200.0
var depth_target := 200.0
var telegraph := -1  # Stop
var ping_age := 999.0

# Contacts (demo)
class Contact:
    var id := ""
    var typ := "merchant" # "sub" | "merchant" | "escort"
    var x := 0.0; var y := 0.0
    var heading_deg := 0.0
    var speed_mps := 0.0
    var confidence := 0.4

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
    var tgt := TELE_TO_SPEED.get(telegraph, 0.0)
    speed_mps = move_toward(speed_mps, tgt, 1.5 * dt)
    depth_m = move_toward(depth_m, depth_target, 3.0 * dt)

    var rad := deg_to_rad(heading_deg)
    var vx := cos(rad) * speed_mps
    var vy := sin(rad) * speed_mps
    _player_x += vx * dt
    _player_y += vy * dt

    # update contacts
    for c in _contacts:
        var cr := deg_to_rad(c.heading_deg)
        c.x += cos(cr) * c.speed_mps * dt
        c.y += sin(cr) * c.speed_mps * dt
        c.confidence = clamp(c.confidence + rng.randf_range(-0.02, 0.03), 0.2, 1.0)

    # sensors
    ping_age += dt
    _emit_passive_mix()
    # Note: active returns handled when cmd_ping() is called

func _emit_passive_mix():
    var own_noise := clamp(speed_mps * 0.05, 0.0, 0.8)
    for c in _contacts:
        var dx := c.x - _player_x
        var dy := c.y - _player_y
        var dist := sqrt(dx*dx + dy*dy)
        var bearing := rad_to_deg(atan2(dy, dx)) - heading_deg
        var az := deg_to_rad(fposmod(bearing, 360.0))
        var l := sqrt(0.5 * (1.0 + cos(az)))
        var r := sqrt(0.5 * (1.0 - cos(az)))
        # distance rolloff + confidence + own_noise, no occlusion yet
        var g := 1.0 / (1.0 + pow(dist / D0, 2.0))
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

func set_depth_target(meters: float) -> void:
    depth_target = clamp(meters, 0.0, 1000.0)

# Exposed for HUD
var _player_x := 0.0
var _player_y := 0.0
func get_player_pose() -> Dictionary:
    return {
        "x": _player_x, "y": _player_y, "depth": depth_m,
        "heading": heading_deg, "speed": speed_mps, "ping_age": ping_age
    }
func get_contacts() -> Array:
    return _contacts

