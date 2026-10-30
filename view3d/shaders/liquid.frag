// Ink colour, darker at the bottom, a glossy surface and a thin bright meniscus.
VARYING vec3 vPos;
VARYING float vTop;

void MAIN()
{
    float h = clamp(vPos.y / max(level, 0.03), 0.0, 1.0);
    vec3 c = inkColor.rgb;
    float depth = mix(0.45, 1.0, smoothstep(0.0, 1.0, h));
    BASE_COLOR = vec4(c * depth, 1.0);
    ROUGHNESS = 0.06;
    METALNESS = 0.0;
    SPECULAR_AMOUNT = 0.9;
    float lum = dot(c, vec3(0.299, 0.587, 0.114));
    // a dark ink still reads as liquid thanks to a cool sheen near the top
    vec3 sheen = mix(vec3(0.35, 0.42, 0.55), c, smoothstep(0.08, 0.3, lum));
    EMISSIVE_COLOR = c * 0.07 * glow + sheen * smoothstep(0.88, 1.0, h) * 0.14 * glow;
}
