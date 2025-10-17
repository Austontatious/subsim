extends Node2D

var snapshot: Dictionary = {}

func update(s: Dictionary) -> void:
    snapshot = s
    queue_redraw()

func _draw() -> void:
    # Simple player proxy and dummy contacts for early visuals
    var center = get_viewport_rect().size / 2.0
    if Engine.has_singleton(""):
        pass
    # Draw a fixed triangle using heading from a stub dictionary if provided
    # This renderer will later be fed real snapshots.
    draw_circle(center, 4.0, Color(0.9, 0.9, 0.9))

