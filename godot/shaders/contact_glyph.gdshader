shader_type spatial;
render_mode unshaded, cull_disabled, blend_mix, depth_prepass_alpha;

uniform vec4 tint : source_color = vec4(0.35, 0.90, 1.00, 1.0);
uniform int shape = 0; // 0=circle, 1=triangle
uniform float edge_softness : hint_range(0.001, 0.2) = 0.02;
uniform float glow : hint_range(0.0, 2.0) = 0.8;

float sdSegment(vec2 p, vec2 a, vec2 b) {
    vec2 pa = p - a;
    vec2 ba = b - a;
    float h = clamp(dot(pa, ba) / max(1e-6, dot(ba, ba)), 0.0, 1.0);
    return length(pa - ba * h);
}

bool insideTriangle(vec2 p, vec2 a, vec2 b, vec2 c) {
    vec2 v0 = c - a;
    vec2 v1 = b - a;
    vec2 v2 = p - a;
    float dot00 = dot(v0, v0);
    float dot01 = dot(v0, v1);
    float dot02 = dot(v0, v2);
    float dot11 = dot(v1, v1);
    float dot12 = dot(v1, v2);
    float invDenom = 1.0 / max(1e-6, (dot00 * dot11 - dot01 * dot01));
    float u = (dot11 * dot02 - dot01 * dot12) * invDenom;
    float v = (dot00 * dot12 - dot01 * dot02) * invDenom;
    return (u >= 0.0) && (v >= 0.0) && (u + v <= 1.0);
}

float sdCircle(vec2 p, float r) {
    return length(p) - r;
}

float sdTriangle(vec2 p) {
    // Simple triangle for glyphs (oriented "up" in UV space).
    vec2 a = vec2(0.0, -0.92);
    vec2 b = vec2(0.82, 0.72);
    vec2 c = vec2(-0.82, 0.72);
    float d = min(sdSegment(p, a, b), min(sdSegment(p, b, c), sdSegment(p, c, a)));
    bool inside = insideTriangle(p, a, b, c);
    return inside ? -d : d;
}

void fragment() {
    // UV in [-1, 1]
    vec2 p = (UV - vec2(0.5)) * 2.0;

    float d = 0.0;
    if (shape == 0) {
        d = sdCircle(p, 0.62);
    } else {
        d = sdTriangle(p);
    }

    float aa = max(edge_softness, fwidth(d));
    float fill = smoothstep(aa, -aa, d);

    // Soft outer glow
    float g = smoothstep(0.35, 0.0, d);

    vec3 col = tint.rgb;
    float a_out = clamp(fill + g * glow * 0.15, 0.0, 1.0) * tint.a;

    ALBEDO = col;
    ALPHA = a_out;
}
