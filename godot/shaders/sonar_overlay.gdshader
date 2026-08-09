shader_type canvas_item;

// Fullscreen sonar sweep overlay. Keep it subtle; it should sell motion, not UI chrome.

uniform vec4 sweep_color : source_color = vec4(0.35, 0.90, 1.00, 1.0);
uniform float sweep_speed_hz : hint_range(0.02, 1.0) = 0.12;
uniform float sweep_width : hint_range(0.002, 0.12) = 0.028;
uniform float sweep_intensity : hint_range(0.0, 1.0) = 0.22;

uniform float vignette : hint_range(0.0, 1.0) = 0.35;
uniform float noise_amount : hint_range(0.0, 0.2) = 0.04;

// Set by script on ping to create a brief "pulse" synchronized to audio/earcon.
uniform float ping_pulse : hint_range(0.0, 1.0) = 0.0;

uniform vec2 center_uv = vec2(0.5, 0.5);

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

void fragment() {
    vec2 uv = UV;
    vec2 p = uv - center_uv;
    float r = length(p);

    // Angle normalized to [0,1)
    float a = atan(p.y, p.x); // [-pi, pi]
    float ang = (a + PI) / (2.0 * PI);

    float t = TIME * sweep_speed_hz;
    float sweep = fract(t);
    float d = abs(ang - sweep);
    d = min(d, 1.0 - d); // wraparound distance on circle

    // Sweep line with soft edge
    float line = smoothstep(sweep_width, 0.0, d);

    // Fade sweep toward edges so it doesn't read like a UI widget.
    float radial_fade = smoothstep(0.95, 0.15, r);

    // Subtle vignette so the screen feels less flat.
    float vig = 1.0 - smoothstep(0.35, 1.1, r);
    float v = mix(1.0, vig, vignette);

    // Grain
    float n = hash12(uv * vec2(900.0, 500.0) + TIME * 0.07) - 0.5;
    float grain = n * noise_amount;

    float alpha = (sweep_intensity * line * radial_fade + ping_pulse * radial_fade) * v;
    alpha = clamp(alpha + grain, 0.0, 1.0);

    COLOR = vec4(sweep_color.rgb, alpha);
}
