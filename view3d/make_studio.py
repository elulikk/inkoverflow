"""Writes view3d/studio.hdr: a dark photo-studio environment (equirectangular, Radiance
RGBE) with a few soft boxes. Qt Quick 3D uses it to light the scene and to give the black
plastic its reflections. Run with any Python 3:  python view3d/make_studio.py
"""
import math
import struct
from pathlib import Path

OUT = Path(__file__).resolve().parent / "studio.hdr"
W, H = 512, 256

# (direction yaw°, pitch°), angular half-size (w°, h°), rgb intensity
# yaw 0 = towards the viewer's default camera side; pitch 90 = straight up.
BOXES = [
    ((0, 75), (55, 14), (5.0, 5.0, 5.2)),       # big overhead box
    ((-45, 25), (16, 22), (3.2, 3.1, 3.0)),     # key, front-left
    ((60, 15), (8, 26), (1.6, 1.8, 2.1)),       # fill strip, front-right (cool)
    ((160, 20), (6, 30), (2.6, 2.9, 3.2)),      # rim strip, behind right
    ((-150, 20), (6, 30), (1.8, 2.0, 2.4)),     # rim strip, behind left
]


def smooth(edge0, edge1, x):
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3 - 2 * t)


def angle_diff(a, b):
    d = (a - b + 180) % 360 - 180
    return abs(d)


def radiance(yaw, pitch):
    # base: dark studio, a touch lighter towards the horizon, darker floor
    if pitch >= 0:
        base = 0.035 + 0.03 * (1 - pitch / 90)
    else:
        base = 0.02 + 0.015 * (1 + pitch / 90)
    r = g = b = base
    b *= 1.15
    for (by, bp), (hw, hh), (cr, cg, cb) in BOXES:
        # soft rectangle in yaw/pitch space; yaw width shrinks near the poles
        dy = angle_diff(yaw, by) * math.cos(math.radians(pitch))
        dp = abs(pitch - bp)
        k = (1 - smooth(hw * 0.7, hw, dy)) * (1 - smooth(hh * 0.7, hh, dp))
        r += cr * k
        g += cg * k
        b += cb * k
    return r, g, b


def rgbe(r, g, b):
    v = max(r, g, b)
    if v < 1e-32:
        return (0, 0, 0, 0)
    m, e = math.frexp(v)
    scale = m * 256.0 / v
    return (int(r * scale), int(g * scale), int(b * scale), e + 128)


def scanline(pixels):
    """New-style RLE scanline written as literal runs only (valid and widely read)."""
    out = bytearray([2, 2, (W >> 8) & 0xFF, W & 0xFF])
    for c in range(4):
        channel = [p[c] for p in pixels]
        i = 0
        while i < W:
            n = min(128, W - i)
            out.append(n)
            out.extend(channel[i:i + n])
            i += n
    return out


def main():
    data = bytearray(b"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n")
    data += f"-Y {H} +X {W}\n".encode()
    for y in range(H):
        pitch = 90 - (y + 0.5) / H * 180
        row = []
        for x in range(W):
            yaw = (x + 0.5) / W * 360 - 180
            row.append(rgbe(*radiance(yaw, pitch)))
        data += scanline(row)
    OUT.write_bytes(bytes(data))
    print("written", OUT)


main()
