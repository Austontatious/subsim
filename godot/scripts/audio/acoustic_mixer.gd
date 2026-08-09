extends Node
class_name AcousticMixer

# Acoustic substrate player for the Godot/APK frontend.
# This intentionally mirrors desktop semantics:
# - foundational ambient + self-noise + player hum bed
# - passive contact loops with variant selection
# - earcons for ping/fire and lightweight active return cues

const STALE_CONTACT_TIMEOUT_S := 0.45
const MAX_PAN_PIXELS := 280.0
const STREAM_VARIANTS := ["clean", "lp1", "lp2", "lp3"]
const STREAM_ASSETS := ["ambient", "player_hum", "merchant", "hunter", "ping", "torpedo", "mine"]
const FOUNDATION_GAIN_BOOST_DB := 3.0
const CONTACT_GAIN_BOOST_DB := 4.5
const EARCON_GAIN_BOOST_DB := 3.0
const PRESET_PACK_PATH := "res://audio/runtime_acoustic_presets_v1.json"
const DEFAULT_RUNTIME_PRESET := "medium_clutter"

@onready var engine: SubsimEngine = get_parent().get_node_or_null("Engine") as SubsimEngine
@export var runtime_preset_name: String = DEFAULT_RUNTIME_PRESET

var _streams: Dictionary = {}
var _contact_players: Dictionary = {} # id -> AudioStreamPlayer2D
var _contact_last_seen: Dictionary = {} # id -> time
var _contact_kind: Dictionary = {} # id -> kind
var _contact_confidence: Dictionary = {} # id -> confidence estimate
var _contact_state: Dictionary = {} # id -> {"asset": String, "variant": String}
var _time_s: float = 0.0
var _runtime_preset_pack: Dictionary = {}
var _runtime_preset: Dictionary = {}

var _ambient_player: AudioStreamPlayer
var _self_noise_player: AudioStreamPlayer
var _hum_player: AudioStreamPlayer
var _ping_player: AudioStreamPlayer
var _fire_player: AudioStreamPlayer


func _ready() -> void:
    _load_runtime_preset()
    _load_stream_bank()
    _create_foundation_players()
    _create_earcon_players()

    if engine:
        engine.mix_contact.connect(_on_mix_contact)
        engine.sfx_ping.connect(_on_sfx_ping)
        engine.sfx_fire.connect(_on_sfx_fire)
        if engine.has_signal("sfx_return"):
            engine.sfx_return.connect(_on_sfx_return)


func _process(delta: float) -> void:
    _time_s += delta
    _refresh_contact_kind_cache()
    _update_foundation_mix()
    _cleanup_stale_contacts()


func _load_runtime_preset() -> void:
    _runtime_preset_pack = {}
    if FileAccess.file_exists(PRESET_PACK_PATH):
        var text := FileAccess.get_file_as_string(PRESET_PACK_PATH)
        var parsed = JSON.parse_string(text)
        if parsed is Dictionary:
            _runtime_preset_pack = parsed

    if _runtime_preset_pack.is_empty():
        _runtime_preset_pack = _fallback_runtime_preset_pack()

    var presets: Dictionary = _runtime_preset_pack.get("presets", {})
    var default_name: String = str(_runtime_preset_pack.get("default_preset", DEFAULT_RUNTIME_PRESET))
    var selected_name: String = runtime_preset_name
    if not presets.has(selected_name):
        selected_name = default_name
    if not presets.has(selected_name):
        var keys: Array = presets.keys()
        if keys.size() > 0:
            selected_name = str(keys[0])

    runtime_preset_name = selected_name
    _runtime_preset = presets.get(selected_name, {})
func _fallback_runtime_preset_pack() -> Dictionary:
    return {
        "default_preset": DEFAULT_RUNTIME_PRESET,
        "presets": {
            "medium_clutter": {
                "global_mix_gain": 1.0,
                "foundation": {
                    "ambient_multiplier": 1.0,
                    "self_noise_multiplier": 1.0,
                    "player_hum_multiplier": 1.0,
                    "self_noise_masking_pressure": 1.0
                },
                "families": {
                    "ambient_soundscape": {"enabled": true, "intensity": 1.0, "density": 1.0},
                    "marine_mammal_whale": {"enabled": true, "intensity": 1.0, "density": 1.0},
                    "marine_mammal_other": {"enabled": true, "intensity": 1.0, "density": 1.0},
                    "surface_vessel": {"enabled": true, "intensity": 1.0, "density": 1.0},
                    "intermittent_machinery_archetype": {"enabled": true, "intensity": 1.0, "density": 1.0}
                }
            }
        }
    }


func _runtime_family_weight(family: String, fallback_weight: float = 1.0) -> float:
    var families: Dictionary = _runtime_preset.get("families", {})
    if not families.has(family):
        return fallback_weight
    var cfg = families.get(family, {})
    if not (cfg is Dictionary):
        return fallback_weight
    var cfg_dict: Dictionary = cfg
    if not bool(cfg_dict.get("enabled", true)):
        return 0.0
    var intensity: float = clamp(float(cfg_dict.get("intensity", 1.0)), 0.0, 2.0)
    var density: float = clamp(float(cfg_dict.get("density", 1.0)), 0.0, 2.0)
    var global_gain: float = clamp(float(_runtime_preset.get("global_mix_gain", 1.0)), 0.0, 2.0)
    return clamp(intensity * density * global_gain * fallback_weight, 0.0, 2.0)


func _runtime_foundation_multiplier(key: String, fallback_value: float = 1.0) -> float:
    var foundation_cfg = _runtime_preset.get("foundation", {})
    if not (foundation_cfg is Dictionary):
        return fallback_value
    return clamp(float((foundation_cfg as Dictionary).get(key, fallback_value)), 0.5, 1.6)


func _load_stream_bank() -> void:
    _streams.clear()
    for asset_name in STREAM_ASSETS:
        var variants: Dictionary = {}
        for variant in STREAM_VARIANTS:
            var stream: AudioStream = _load_stream(asset_name, variant)
            if stream != null:
                variants[variant] = stream
        _streams[asset_name] = variants


func _load_stream(asset_name: String, variant: String) -> AudioStream:
    var path := "res://audio/sfx/%s_%s.wav" % [asset_name, variant]
    if not ResourceLoader.exists(path):
        return null
    return load(path) as AudioStream


func _pick_stream(asset_name: String, variant: String) -> AudioStream:
    var variants: Dictionary = _streams.get(asset_name, {})
    if variants.has(variant):
        return variants[variant] as AudioStream
    if variants.has("clean"):
        return variants["clean"] as AudioStream
    return null


func _loop_stream(stream: AudioStream) -> AudioStream:
    if stream is AudioStreamWAV:
        var duplicated := (stream as AudioStreamWAV).duplicate() as AudioStreamWAV
        duplicated.loop_mode = AudioStreamWAV.LOOP_FORWARD
        return duplicated
    return stream


func _create_player(name: String) -> AudioStreamPlayer:
    var player := AudioStreamPlayer.new()
    player.name = name
    add_child(player)
    return player


func _create_foundation_players() -> void:
    _ambient_player = _create_player("AmbientBed")
    _self_noise_player = _create_player("SelfNoiseBed")
    _hum_player = _create_player("PlayerHumBed")

    var ambient := _pick_stream("ambient", "lp3")
    if ambient:
        _ambient_player.stream = _loop_stream(ambient)
        _ambient_player.play()
    var self_noise := _pick_stream("ambient", "lp1")
    if self_noise:
        _self_noise_player.stream = _loop_stream(self_noise)
        _self_noise_player.play()
    var hum := _pick_stream("player_hum", "clean")
    if hum:
        _hum_player.stream = _loop_stream(hum)
        _hum_player.play()


func _create_earcon_players() -> void:
    _ping_player = _create_player("PingEarcon")
    _ping_player.stream = _pick_stream("ping", "clean")

    _fire_player = _create_player("FireEarcon")
    _fire_player.stream = _pick_stream("torpedo", "clean")
    if _ping_player:
        _ping_player.volume_db = EARCON_GAIN_BOOST_DB
    if _fire_player:
        _fire_player.volume_db = EARCON_GAIN_BOOST_DB


func _refresh_contact_kind_cache() -> void:
    if not engine:
        return
    var contacts: Array = engine.get_contacts()
    for c in contacts:
        var contact_id := _contact_id(c)
        if contact_id == "":
            continue
        _contact_kind[contact_id] = _contact_kind_name(c)
        _contact_confidence[contact_id] = _contact_confidence_value(c)


func _contact_id(contact) -> String:
    if contact is Dictionary:
        return str(contact.get("id", ""))
    if contact == null:
        return ""
    return str(contact.id)


func _contact_kind_name(contact) -> String:
    if contact is Dictionary:
        return str(contact.get("typ", "merchant"))
    if contact == null:
        return "merchant"
    var kind: String = str(contact.typ)
    if kind == "escort":
        return "hunter"
    if kind == "sub":
        return "hunter"
    return kind


func _contact_confidence_value(contact) -> float:
    if contact is Dictionary:
        return clamp(float(contact.get("confidence", 0.4)), 0.0, 1.0)
    if contact == null:
        return 0.4
    return clamp(float(contact.confidence), 0.0, 1.0)


func _infer_occlusion_layers(gain: float, confidence: float) -> int:
    # Engine stub does not emit explicit occlusion; infer coarse masking only when weak + uncertain.
    if gain < 0.06 and confidence < 0.25:
        return 2
    if gain < 0.14 and confidence < 0.4:
        return 1
    return 0


func _variant_for_contract_inputs(confidence: float, occlusion_layers: int, own_noise: float) -> String:
    var c: float = clamp(confidence, 0.0, 1.0)
    var n: float = clamp(own_noise, 0.0, 1.0)
    var score: float = (max(0, occlusion_layers) * 0.45) + ((1.0 - c) * 0.55) + (n * 0.35)
    if score >= 1.20:
        return "lp3"
    if score >= 0.80:
        return "lp2"
    if score >= 0.35:
        return "lp1"
    return "clean"


func _contact_asset(kind: String) -> String:
    if kind == "hunter" or kind == "escort" or kind == "sub":
        return "hunter"
    return "merchant"


func _ensure_contact_player(contact_id: String, kind: String, variant: String) -> AudioStreamPlayer2D:
    var player: AudioStreamPlayer2D = _contact_players.get(contact_id, null) as AudioStreamPlayer2D
    if player == null:
        player = AudioStreamPlayer2D.new()
        player.name = "Contact_%s" % contact_id
        player.max_distance = 2000.0
        player.attenuation = 1.0
        player.panning_strength = 1.0
        add_child(player)
        _contact_players[contact_id] = player

    var asset_name := _contact_asset(kind)
    var prior: Dictionary = _contact_state.get(contact_id, {})
    if prior.get("asset", "") != asset_name or prior.get("variant", "") != variant:
        var stream := _pick_stream(asset_name, variant)
        if stream:
            player.stream = _loop_stream(stream)
            player.play()
            _contact_state[contact_id] = {"asset": asset_name, "variant": variant}
    elif player.stream and not player.playing:
        player.play()
    return player


func _set_player_linear_volume(player: AudioStreamPlayer, gain: float) -> void:
    player.volume_db = linear_to_db(max(0.0001, clamp(gain, 0.0, 1.0))) + FOUNDATION_GAIN_BOOST_DB


func _set_player2d_linear_volume(player: AudioStreamPlayer2D, gain: float) -> void:
    player.volume_db = linear_to_db(max(0.0001, clamp(gain, 0.0, 1.0))) + CONTACT_GAIN_BOOST_DB


func _update_foundation_mix() -> void:
    if _ambient_player == null or _self_noise_player == null or _hum_player == null:
        return

    var own_noise: float = 0.0
    var ping_active: bool = false
    if engine:
        own_noise = clamp(engine.speed_mps * 0.05, 0.0, 0.8)
        ping_active = engine.ping_age < 0.7
    var sensor_noise: float = own_noise * 0.35

    var ambient: float = clamp(0.20 + sensor_noise * 0.32 - (0.06 if ping_active else 0.0), 0.0, 1.0)
    var self_noise: float = clamp(0.08 + own_noise * 0.72, 0.0, 1.0)
    var hum: float = clamp(0.12 + own_noise * 0.60, 0.0, 1.0)
    if ping_active:
        ambient *= 0.92
        hum *= 0.88

    var ambient_mult: float = _runtime_foundation_multiplier("ambient_multiplier", 1.0)
    var self_noise_mult: float = _runtime_foundation_multiplier("self_noise_multiplier", 1.0)
    var hum_mult: float = _runtime_foundation_multiplier("player_hum_multiplier", 1.0)
    var masking_mult: float = _runtime_foundation_multiplier("self_noise_masking_pressure", 1.0)
    var ambient_family_weight: float = _runtime_family_weight("ambient_soundscape", 1.0)
    var marine_life_weight: float = 0.5 * (
        _runtime_family_weight("marine_mammal_whale", 1.0) + _runtime_family_weight("marine_mammal_other", 1.0)
    )
    ambient *= ambient_mult * ambient_family_weight * clamp(0.9 + marine_life_weight * 0.08, 0.7, 1.3)
    self_noise *= self_noise_mult * masking_mult
    hum *= hum_mult

    _set_player_linear_volume(_ambient_player, clamp(ambient, 0.0, 1.0))
    _set_player_linear_volume(_self_noise_player, clamp(self_noise * 0.45, 0.0, 1.0))
    _set_player_linear_volume(_hum_player, clamp(hum, 0.0, 1.0))


func _cleanup_stale_contacts() -> void:
    var stale: Array = []
    for contact_id in _contact_players.keys():
        var last_seen: float = float(_contact_last_seen.get(contact_id, -999.0))
        if (_time_s - last_seen) > STALE_CONTACT_TIMEOUT_S:
            stale.append(contact_id)

    for contact_id in stale:
        var player: AudioStreamPlayer2D = _contact_players.get(contact_id, null) as AudioStreamPlayer2D
        if player:
            player.stop()
            player.queue_free()
        _contact_players.erase(contact_id)
        _contact_last_seen.erase(contact_id)
        _contact_confidence.erase(contact_id)
        _contact_state.erase(contact_id)


func _on_mix_contact(contact_id: String, pan_l: float, pan_r: float, gain: float) -> void:
    var kind: String = str(_contact_kind.get(contact_id, "merchant"))
    var confidence: float = float(_contact_confidence.get(contact_id, clamp(gain, 0.0, 1.0)))
    var own_noise: float = 0.0
    if engine:
        own_noise = clamp(engine.speed_mps * 0.05, 0.0, 0.8)
    var occlusion_layers: int = _infer_occlusion_layers(gain, confidence)
    var variant: String = _variant_for_contract_inputs(confidence, occlusion_layers, own_noise)
    var vessel_weight: float = _runtime_family_weight("surface_vessel", 1.0)
    var machinery_weight: float = _runtime_family_weight("intermittent_machinery_archetype", 1.0)
    var ambiguity: float = clamp((1.0 - confidence) + own_noise * 0.35, 0.0, 1.0)
    var runtime_gain: float = gain * vessel_weight * lerp(1.0, machinery_weight, ambiguity)
    runtime_gain = clamp(runtime_gain, 0.0, 1.0)
    var player: AudioStreamPlayer2D = _ensure_contact_player(contact_id, kind, variant)
    var pan: float = clamp(pan_r - pan_l, -1.0, 1.0)
    player.position = Vector2(pan * MAX_PAN_PIXELS, 0.0)
    _set_player2d_linear_volume(player, runtime_gain)
    _contact_last_seen[contact_id] = _time_s


func _on_sfx_ping() -> void:
    if _ping_player and _ping_player.stream:
        _ping_player.play()


func _on_sfx_fire() -> void:
    if _fire_player and _fire_player.stream:
        _fire_player.play()


func _on_sfx_return(_contact_id: String, bearing_deg: float, _distance_m: float, strength: float) -> void:
    var stream: AudioStream = _pick_stream("ping", "lp1")
    if stream == null:
        return
    var player: AudioStreamPlayer2D = AudioStreamPlayer2D.new()
    player.name = "ReturnCue"
    player.stream = stream
    player.max_distance = 2000.0
    player.attenuation = 1.0
    var pan: float = sin(deg_to_rad(fposmod(bearing_deg, 360.0)))
    player.position = Vector2(clamp(pan, -1.0, 1.0) * MAX_PAN_PIXELS, 0.0)
    _set_player2d_linear_volume(player, strength)
    add_child(player)
    player.play()
    player.finished.connect(func() -> void:
        player.queue_free()
    )
