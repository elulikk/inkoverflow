// Waste-ink felt. A stain spreads from where the drain tube drips (`source`) and covers
// more of the felt as `fill` (0-1) grows; the edge is ragged and has a darker tide line.
VARYING vec3 vPos;

float hash(vec3 p)
{
    p = fract(p * 0.3183099 + 0.1);
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float vnoise(vec3 x)
{
    vec3 i = floor(x);
    vec3 f = fract(x);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(mix(hash(i + vec3(0, 0, 0)), hash(i + vec3(1, 0, 0)), f.x),
                   mix(hash(i + vec3(0, 1, 0)), hash(i + vec3(1, 1, 0)), f.x), f.y),
               mix(mix(hash(i + vec3(0, 0, 1)), hash(i + vec3(1, 0, 1)), f.x),
                   mix(hash(i + vec3(0, 1, 1)), hash(i + vec3(1, 1, 1)), f.x), f.y), f.z);
}

float fbm(vec3 p)
{
    return 0.55 * vnoise(p) + 0.28 * vnoise(p * 2.1) + 0.17 * vnoise(p * 4.3);
}

void MAIN()
{
    // felt fibres
    float fibre = fbm(vPos * vec3(60.0, 90.0, 60.0));
    vec3 felt = vec3(0.62, 0.60, 0.56) * (0.86 + 0.18 * fibre);

    // ink spreads mostly sideways and down from the drip point
    vec3 d = (vPos - source.xyz) * vec3(1.0, 1.25, 1.1);
    float dist = length(d) / reach;
    dist += (fbm(vPos * 7.0) - 0.5) * 0.35;
    float f = clamp(fill, 0.0, 1.05);
    float stain = 1.0 - smoothstep(f - 0.035, f + 0.035, dist);
    float tide = smoothstep(f - 0.09, f - 0.02, dist) * stain;
    float core = 1.0 - smoothstep(0.0, max(f * 0.6, 0.01), dist);

    vec3 ink = mix(inkTint.rgb, inkTint.rgb * 0.35, core * 0.7);
    ink *= 0.85 + 0.3 * fibre;
    vec3 c = mix(felt, ink, stain * 0.97);
    c = mix(c, inkTint.rgb * 0.22, tide * 0.65);

    BASE_COLOR = vec4(c, 1.0);
    ROUGHNESS = mix(0.95, 0.45, stain * 0.8);   // wet ink is a little shiny
    METALNESS = 0.0;
    SPECULAR_AMOUNT = mix(0.15, 0.55, stain);
    EMISSIVE_COLOR = vec3(highlight) * vec3(0.05, 0.22, 0.2);
}
