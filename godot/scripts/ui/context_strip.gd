extends Control
class_name ContextStrip

signal ping_pressed()
signal fire_pressed()

@export var fade_time: float = 0.18

@onready var torp_label: Label = $TorpedoLabel as Label
@onready var depth_label: Label = $DepthLabel as Label
@onready var speed_label: Label = $SpeedLabel as Label
@onready var ping_btn: Button = $PingButton as Button
@onready var fire_btn: Button = $FireButton as Button

var _shown: bool = false
var _tween: Tween


func _ready() -> void:
    modulate.a = 0.0
    visible = false
    ping_btn.pressed.connect(_on_ping_pressed)
    fire_btn.pressed.connect(_on_fire_pressed)
    _layout()


func _notification(what: int) -> void:
    if what == NOTIFICATION_RESIZED:
        _layout()


func set_status(
    depth_m: float,
    speed_mps: float,
    torpedo_ready: bool,
    fire_ready: bool,
    torpedo_ammo: int = 0,
    active_torpedoes: int = 0,
    fire_cooldown_s: float = 0.0
) -> void:
    torp_label.text = "TORP %d | ACT %d" % [max(0, torpedo_ammo), max(0, active_torpedoes)]
    depth_label.text = "DEPTH %.0fm" % depth_m
    speed_label.text = "SPD %.1f" % speed_mps
    ping_btn.visible = true
    fire_btn.visible = true

    var cooling: bool = fire_cooldown_s > 0.05
    fire_btn.disabled = (not fire_ready) or cooling
    if cooling:
        fire_btn.text = "FIRE %.1fs" % fire_cooldown_s
    elif not torpedo_ready:
        fire_btn.text = "FIRE"
    else:
        fire_btn.text = "FIRE"


func show_strip(show: bool) -> void:
    if show == _shown:
        return
    _shown = show

    if _tween and is_instance_valid(_tween):
        _tween.kill()
    _tween = create_tween()

    if show:
        visible = true
        _tween.tween_property(self, "modulate:a", 1.0, fade_time).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
    else:
        _tween.tween_property(self, "modulate:a", 0.0, fade_time).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
        _tween.tween_callback(func(): visible = false)


func _on_ping_pressed() -> void:
    emit_signal("ping_pressed")


func _on_fire_pressed() -> void:
    emit_signal("fire_pressed")


func _layout() -> void:
    if torp_label == null or depth_label == null or speed_label == null or ping_btn == null or fire_btn == null:
        return

    var w: float = size.x
    var h: float = size.y
    if w <= 0.0 or h <= 0.0:
        return

    var pad: float = clamp(h * 0.14, 12.0, 22.0)
    var text_y: float = clamp((h - 26.0) * 0.5, 18.0, h - 30.0)
    var btn_h: float = clamp(h - (pad * 2.0), 44.0, 72.0)
    var btn_w: float = clamp(w * 0.16, 108.0, 150.0)
    var btn_gap: float = 12.0

    var right_buttons_width: float = (btn_w * 2.0) + btn_gap
    var info_w: float = max(220.0, w - right_buttons_width - (pad * 3.0))
    var col_w: float = info_w / 3.0

    torp_label.position = Vector2(pad, text_y)
    depth_label.position = Vector2(pad + col_w, text_y)
    speed_label.position = Vector2(pad + col_w * 2.0, text_y)

    ping_btn.custom_minimum_size = Vector2(btn_w, btn_h)
    ping_btn.size = ping_btn.custom_minimum_size
    ping_btn.position = Vector2(w - pad - right_buttons_width, (h - btn_h) * 0.5)

    fire_btn.custom_minimum_size = Vector2(btn_w, btn_h)
    fire_btn.size = fire_btn.custom_minimum_size
    fire_btn.position = Vector2(w - pad - btn_w, (h - btn_h) * 0.5)
