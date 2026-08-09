extends Node
class_name SubsimEngine

# Public API:
# - step(dt: float)
# - cmd_ping()
# - cmd_fire()
# - set_telegraph(tele: int)  # -5..5 reverse/full ahead in detents
# - turn_deg(delta: float)
# - set_heading_target(deg: float)
# - set_depth_target(meters: float)
# - set_pitch_roll(pitch: float, roll: float)  # -1..1 controls (attitude dial)
# - get_player_pose() / get_contacts() / get_torpedoes()

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
const TORPEDO_SPEED_MPS := 42.0
const TORPEDO_MAX_AGE_S := 22.0
const TORPEDO_FIRE_COOLDOWN_S := 1.1
const TORPEDO_LAUNCH_OFFSET_M := 18.0
const TORPEDO_HIT_RADIUS_M := 40.0
const TORPEDO_MAX_ACTIVE := 4
const TORPEDO_AMMO_INITIAL := 8

signal sfx_ping()
signal sfx_fire()
signal sfx_return(id: String, bearing_deg: float, distance_m: float, strength: float)
signal mix_contact(id: String, pan_l: float, pan_r: float, gain: float)
signal torpedo_fired(id: String, ammo_remaining: int, active_count: int)
signal torpedo_expired(id: String, reason: String, active_count: int)

var rng: RandomNumberGenerator = RandomNumberGenerator.new()

# State
var heading_deg: float = 0.0
var heading_target_deg: float = 0.0
var speed_mps: float = 0.0
var depth_m: float = 200.0
var depth_target: float = 200.0
var telegraph: int = -1  # Stop
var ping_age: float = 999.0
var pitch_cmd: float = 0.0
var roll_cmd: float = 0.0
var _torpedo_ammo: int = TORPEDO_AMMO_INITIAL
var _torpedoes: Array = [] # [{id,x,y,heading_deg,speed_mps,age_s,max_age_s}]
var _fire_cooldown_s: float = 0.0
var _torpedo_seq: int = 0

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
    var r := Contact.new(); r.id = "R"; r.typ = "escort"; r.x = 1500; r.y = -400; r.heading_deg = 45; r.speed_mps = 8
    _contacts = [r]
    _wander_reset()
    _torpedo_ammo = TORPEDO_AMMO_INITIAL
    _torpedoes.clear()
    _fire_cooldown_s = 0.0
    _torpedo_seq = 0

var _contacts: Array = []
var _wander_next_change: float = 0.0
var _wander_target_hdg: float = 0.0

func step(dt: float) -> void:
    # player kinematics
    var tgt: float = float(TELE_TO_SPEED.get(telegraph, 0.0))
    speed_mps = move_toward(speed_mps, tgt, 1.5 * dt)

    # Attitude dial: pitch drives depth target rate, roll is currently cosmetic/for future.
    # pitch_cmd > 0 means "climb" (shallower).
    var depth_rate: float = 18.0 # m/s toward shallower/deeper
    depth_target = clamp(depth_target - pitch_cmd * depth_rate * dt, 0.0, 1000.0)
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

    _update_wander(dt)
    _update_torpedoes(dt)
    if _fire_cooldown_s > 0.0:
        _fire_cooldown_s = max(0.0, _fire_cooldown_s - dt)

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
    _emit_active_returns()

func cmd_fire() -> bool:
    if not can_fire_torpedo():
        return false

    var launch_rad: float = deg_to_rad(heading_deg)
    var torp_id: String = "T%03d" % _torpedo_seq
    _torpedo_seq += 1
    var torp := {
        "id": torp_id,
        "x": _player_x + cos(launch_rad) * TORPEDO_LAUNCH_OFFSET_M,
        "y": _player_y + sin(launch_rad) * TORPEDO_LAUNCH_OFFSET_M,
        "heading_deg": heading_deg,
        "speed_mps": TORPEDO_SPEED_MPS,
        "age_s": 0.0,
        "max_age_s": TORPEDO_MAX_AGE_S,
    }
    _torpedoes.append(torp)
    _torpedo_ammo = max(0, _torpedo_ammo - 1)
    _fire_cooldown_s = TORPEDO_FIRE_COOLDOWN_S
    emit_signal("sfx_fire")
    emit_signal("torpedo_fired", torp_id, _torpedo_ammo, _torpedoes.size())
    return true

func can_fire_torpedo() -> bool:
    if _torpedo_ammo <= 0:
        return false
    if _fire_cooldown_s > 0.0:
        return false
    return _torpedoes.size() < TORPEDO_MAX_ACTIVE

func set_telegraph(tele: int) -> void:
    telegraph = tele

func turn_deg(delta: float) -> void:
    heading_deg = fposmod(heading_deg + delta, 360.0)
    heading_target_deg = heading_deg

func set_heading_target(deg: float) -> void:
    heading_target_deg = fposmod(deg + 360.0, 360.0)

func set_depth_target(meters: float) -> void:
    depth_target = clamp(meters, 0.0, 1000.0)

func set_pitch_roll(pitch: float, roll: float) -> void:
    pitch_cmd = clamp(pitch, -1.0, 1.0)
    roll_cmd = clamp(roll, -1.0, 1.0)

# Exposed for HUD
var _player_x: float = 0.0
var _player_y: float = 0.0
func get_player_pose() -> Dictionary:
    return {
        "x": _player_x, "y": _player_y, "depth": depth_m,
        "heading": heading_deg, "heading_target": heading_target_deg,
        "speed": speed_mps, "ping_age": ping_age,
        "pitch": pitch_cmd, "roll": roll_cmd,
        "torpedo_ammo": _torpedo_ammo,
        "active_torpedoes": _torpedoes.size(),
        "fire_cooldown_s": _fire_cooldown_s,
        "can_fire_torpedo": can_fire_torpedo()
    }

func get_contacts() -> Array:
    return _contacts

func get_torpedoes() -> Array:
    var out: Array = []
    for t in _torpedoes:
        if t is Dictionary:
            out.append((t as Dictionary).duplicate())
    return out

func _angle_diff_deg(target: float, current: float) -> float:
    var a := fposmod(target - current + 540.0, 360.0) - 180.0
    return a

func _wander_reset() -> void:
    _wander_next_change = rng.randf_range(1.5, 4.0)
    if _contacts.size() > 0:
        var c: Contact = _contacts[0]
        _wander_target_hdg = fposmod(c.heading_deg + rng.randf_range(-90.0, 90.0) + 360.0, 360.0)

func _update_wander(dt: float) -> void:
    if _contacts.size() == 0:
        return
    var c: Contact = _contacts[0]
    _wander_next_change -= dt
    if _wander_next_change <= 0.0:
        _wander_reset()
        # vary speed a bit 2..12 m/s
        c.speed_mps = clamp(c.speed_mps + rng.randf_range(-2.0, 2.0), 2.0, 12.0)
    # smoothly steer toward target heading
    var dh: float = _angle_diff_deg(_wander_target_hdg, c.heading_deg)
    var max_turn: float = TURN_RATE_DEGPS * 0.5 * dt
    var step_h: float = clamp(dh, -max_turn, max_turn)
    c.heading_deg = fposmod(c.heading_deg + step_h + 360.0, 360.0)


func _update_torpedoes(dt: float) -> void:
    if _torpedoes.is_empty():
        return

    for i in range(_torpedoes.size() - 1, -1, -1):
        var t: Dictionary = _torpedoes[i]
        var age_s: float = float(t.get("age_s", 0.0)) + dt
        var max_age_s: float = float(t.get("max_age_s", TORPEDO_MAX_AGE_S))
        var heading: float = float(t.get("heading_deg", heading_deg))
        var speed: float = float(t.get("speed_mps", TORPEDO_SPEED_MPS))
        var x: float = float(t.get("x", _player_x))
        var y: float = float(t.get("y", _player_y))
        var heading_rad: float = deg_to_rad(heading)
        x += cos(heading_rad) * speed * dt
        y += sin(heading_rad) * speed * dt

        t["age_s"] = age_s
        t["x"] = x
        t["y"] = y
        _torpedoes[i] = t

        var torp_id: String = str(t.get("id", ""))
        if age_s >= max_age_s:
            _torpedoes.remove_at(i)
            emit_signal("torpedo_expired", torp_id, "expired", _torpedoes.size())
            continue

        var hit_contact_idx: int = -1
        for j in range(_contacts.size()):
            var c: Contact = _contacts[j]
            var dx: float = c.x - x
            var dy: float = c.y - y
            var dist: float = sqrt(dx * dx + dy * dy)
            if dist <= TORPEDO_HIT_RADIUS_M:
                hit_contact_idx = j
                break

        if hit_contact_idx >= 0:
            _contacts.remove_at(hit_contact_idx)
            _torpedoes.remove_at(i)
            emit_signal("torpedo_expired", torp_id, "hit_contact", _torpedoes.size())


func _emit_active_returns() -> void:
    if _contacts.is_empty():
        return
    for c in _contacts:
        var dx: float = c.x - _player_x
        var dy: float = c.y - _player_y
        var dist: float = max(1.0, sqrt(dx * dx + dy * dy))
        var bearing_rel: float = fposmod(rad_to_deg(atan2(dy, dx)) - heading_deg + 360.0, 360.0)
        var delay_s: float = clamp((2.0 * dist) / 1482.0, 0.05, 2.2)
        var strength: float = 1.0 / (1.0 + pow(dist / D0, 2.0))
        var contact_id: String = c.id
        _schedule_return(contact_id, bearing_rel, dist, strength, delay_s)


func _schedule_return(contact_id: String, bearing_deg: float, distance_m: float, strength: float, delay_s: float) -> void:
    var timer: SceneTreeTimer = get_tree().create_timer(delay_s)
    timer.timeout.connect(func() -> void:
        emit_signal("sfx_return", contact_id, bearing_deg, distance_m, strength)
    )
