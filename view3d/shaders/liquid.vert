// Ink in one tank. The mesh is 1 unit tall with its base at y = 0; `level` (0-1)
// squashes it and the top surface ripples a little, as if the printer had just moved.
VARYING vec3 vPos;
VARYING float vTop;

void MAIN()
{
    vec3 p = VERTEX;
    float top = step(0.999, p.y);
    float h = max(level, 0.03);
    p.y *= h;
    float wave = sin(p.z * 22.0 + time * 2.1) * 0.6
               + sin(p.x * 31.0 - time * 1.6 + p.z * 9.0) * 0.4;
    p.y += top * wave * 0.022 * slosh;
    vPos = p;
    vTop = top;
    VERTEX = p;
}
