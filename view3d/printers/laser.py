"""Mono laser printers, one body per family with a printer-only and a multifunction
(scanner on top) model each:

    hp_laserjet_m111 / hp_laserjet_m141     HP LaserJet M110-M111w / MFP M140-M141w
    brother_hl1212w / brother_dcp1612w      Brother HL-1210W-1212W / DCP-1610W-1612W
    pantum_p2500w / pantum_m6550nw          Pantum P2500(W) / M6500-M6550(NW)
    samsung_m2020w / samsung_m2070w         Samsung Xpress M2020(W) / M2070(W)

They share the shape: a box with the paper tray behind a door at the bottom of the front,
the printed sheet coming out on top (into a recess in the top, or into a pocket under the
scanner), the toner cartridge (with its drum) under a cover at the top front, or under
the scanner, which lifts. Each SPECS entry is a model's size, from the maker; the scene
(LaserPrinter.qml and its family files) uses the same numbers. No ink and no waste pads.
"""
import math

from mathutils import Matrix

from parts import box, box_y, cut, cylinder, feet, finish, join, power_button, rear_ports

# w, d, h: width, depth, height (dm, trays closed). mfp: the scanner on top. r: how round
# the vertical corners are. lcd: a small screen on the panel. keys: buttons beside power.
SPECS = {
    "hp_laserjet_m111": dict(w=3.46, d=1.89, h=1.59, mfp=False, r=0.10, lcd=False, keys=1),
    "hp_laserjet_m141": dict(w=3.60, d=2.64, h=1.97, mfp=True, r=0.10, lcd=False, keys=3),
    "brother_hl1212w": dict(w=3.40, d=2.38, h=1.89, mfp=False, r=0.12, lcd=False, keys=1),
    "brother_dcp1612w": dict(w=3.85, d=3.40, h=2.55, mfp=True, r=0.12, lcd=True, keys=4),
    "pantum_p2500w": dict(w=3.37, d=2.20, h=1.78, mfp=False, r=0.16, lcd=False, keys=1),
    "pantum_m6550nw": dict(w=4.17, d=3.05, h=3.01, mfp=True, r=0.14, lcd=True, keys=4),
    "samsung_m2020w": dict(w=3.31, d=2.15, h=1.78, mfp=False, r=0.08, lcd=False, keys=1),
    "samsung_m2070w": dict(w=4.06, d=3.60, h=2.53, mfp=True, r=0.08, lcd=True, keys=4),
}

SCAN_H = 0.75                   # scanner unit and lid on a multifunction
COVER = 1.20                    # depth of the top cover of a printer, from the front


def layout(s):
    """The numbers the parts share (also the scene's, see LaserPrinter.qml)."""
    x1, y0, y1 = s["w"] / 2, -s["d"] / 2, s["d"] / 2
    top = s["h"] - SCAN_H if s["mfp"] else s["h"]         # top of the printer body
    tw = min(2 * x1 - 0.55, 3.0)                          # toner cartridge length
    # the cartridge: its centre y, its bottom z (under the cover, or under the pocket the
    # sheets come out into on a multifunction)
    return dict(x1=x1, y0=y0, y1=y1, top=top, tw=tw, td=0.82, th=0.62,
                ty=y0 + 0.55, tz=top - (0.96 if s["mfp"] else 0.90))


def body(s, L):
    """The body, the paper tray door, the toner well and where the sheets land: a pocket
    under the scanner (multifunction), or a recess in the top cover (printer), which lifts
    on its back edge to reach the toner."""
    x1, y0, y1, top = L["x1"], L["y0"], L["y1"], L["top"]
    ports, port_insides = rear_ports(0.30, -x1 + 0.45, y1)
    base = box("body", -x1, x1, y0, y1, 0.02, top, rv=s["r"], re=0.03)
    tw, ty, td = L["tw"], L["ty"], L["td"]
    cutters = list(ports)
    if s["mfp"]:
        cutters.append(box("c_out", -x1 + 0.40, x1 - 0.40, y0 - 0.1, y1 - 0.60, top - 0.32,
                           top + 0.1, rv=0.04))
        ox0, ox1, oy0, oy1, oz = -x1 + 0.42, x1 - 0.42, y0 + 0.02, y1 - 0.62, top - 0.30
        exit_y = oy1
    else:
        cutters.append(box("c_cover", -x1 - 0.1, x1 + 0.1, y0 - 0.1, y0 + COVER, top - 0.16,
                           top + 0.1))
        ox0, ox1, oy0, oy1, oz = -x1 + 0.42, x1 - 0.97, y0 + 0.14, y0 + COVER - 0.10, top - 0.10
        exit_y = y0 + COVER + 0.02
    # the well the cartridge sits in, open under the cover (or the pocket)
    cutters.append(box("c_well", -tw / 2 - 0.08, tw / 2 + 0.08, ty - td / 2 - 0.06,
                       ty + td / 2 + 0.06, L["tz"] - 0.04, top - (0.30 if s["mfp"] else 0.0)))
    # the front door of the paper tray sits in a shallow recess
    dz1 = min(0.70, top * 0.45)
    cutters.append(box("c_door", -x1 + 0.38, x1 - 0.38, y0 - 0.1, y0 + 0.012, 0.10, dz1,
                       rv=0.03))
    cut(base, *cutters)
    finish(base)

    finish(box_y("tray_door", -x1 + 0.39, x1 - 0.39, y0 - 0.004, y0 + 0.014, 0.11, dz1 - 0.01,
                 r=0.03, re=0.006))
    # where the printed sheets land and the paper stop at its front
    finish(box("out_floor", ox0, ox1, oy0, oy1, oz, oz + 0.02, rv=0.02))
    finish(box("out_stop", -0.55, 0.55, oy0 + 0.02, oy0 + 0.05, oz, oz + 0.14, re=0.01))
    finish(join("slot_inner",
                box("a", ox0, ox1, exit_y - 0.03, exit_y, top - 0.13 if not s["mfp"] else oz,
                    top - 0.03 if not s["mfp"] else oz + 0.25),     # the exit at the back
                box("b", -tw / 2 - 0.07, tw / 2 + 0.07, ty - td / 2 - 0.05, ty + td / 2 + 0.05,
                    L["tz"] - 0.04, L["tz"] - 0.02),                 # the floor of the well
                *port_insides))
    if not s["mfp"]:
        # the top cover with the recess the sheets land in, hinged at its back edge
        cover = box("top_cover", -x1 + 0.006, x1 - 0.006, y0 - 0.004, y0 + COVER - 0.004,
                    top - 0.155, top + 0.004, rv=s["r"] * 0.8, re=0.02)
        cut(cover, box("c_rec", -x1 + 0.40, x1 - 0.95, y0 + 0.12, y0 + COVER - 0.08, top - 0.10,
                       top + 0.1, rv=0.05))
        finish(cover)
    feet([(-x1 + 0.3, y0 + 0.3), (x1 - 0.3, y0 + 0.3), (-x1 + 0.3, y1 - 0.3), (x1 - 0.3, y1 - 0.3)])


def scanner(s, L):
    x1, y0, y1, top = L["x1"], L["y0"], L["y1"], L["top"]
    finish(box("scanner", -x1 + 0.006, x1 - 0.006, y0 - 0.004, y1 - 0.004, top + 0.008,
               s["h"] - 0.16, rv=s["r"], re=0.03))
    finish(box("lid", -x1 + 0.03, x1 - 0.03, y0 + 0.40, y1 - 0.03, s["h"] - 0.154, s["h"],
               rv=s["r"] * 0.8, re=0.035))


def control_panel(s, L):
    """Printers: on the top cover, at the right of the output recess (it lifts with the
    cover). Multifunction: the front of the scanner's top, in front of the lid, on the right."""
    x1, y0 = L["x1"], L["y0"]
    if s["mfp"]:
        top = s["h"] - 0.16
        px0, px1, py0, py1 = x1 - 1.45, x1 - 0.10, y0 + 0.04, y0 + 0.36
    else:
        top = L["top"]
        px0, px1, py0, py1 = x1 - 0.85, x1 - 0.12, y0 + 0.15, y0 + 0.75
    finish(box("panel", px0, px1, py0, py1, top - 0.005, top + 0.008, rv=0.035, re=0.005))
    p = top + 0.008
    cy = (py0 + py1) / 2
    keys = []
    if s["mfp"]:
        if s["lcd"]:
            finish(box("lcd", px0 + 0.10, px0 + 0.50, cy - 0.08, cy + 0.08, p - 0.004, p + 0.005,
                       rv=0.01, re=0.003))
        start = px0 + (0.62 if s["lcd"] else 0.15)
        keys = [box(f"b{i}", start + i * 0.15 - 0.045, start + i * 0.15 + 0.045, cy - 0.04,
                    cy + 0.04, p - 0.004, p + 0.016, rv=0.015, re=0.006) for i in range(s["keys"])]
        power = power_button(px1 - 0.12, cy, p, r=0.045, ring=0.062, h=0.02, ring_h=0.01)
    else:
        cx = (px0 + px1) / 2
        keys = [box(f"b{i}", cx - 0.05, cx + 0.05, py0 + 0.30 + i * 0.13, py0 + 0.38 + i * 0.13,
                    p - 0.004, p + 0.016, rv=0.02, re=0.006) for i in range(s["keys"])]
        power = power_button(cx, py0 + 0.14, p, r=0.05, ring=0.066, h=0.02, ring_h=0.01)
    finish(join("buttons", power, *keys))
    finish(join("leds", *[box(f"l{i}", px0 + 0.06, px0 + 0.10, cy - 0.06 + i * 0.12,
                              cy - 0.03 + i * 0.12, p - 0.004, p + 0.005) for i in range(2)]))


def toner(L):
    """The toner cartridge, base at the origin, centred (front -Y): the body (`toner_body`)
    with its grip (`toner_grip`); the drum (`toner_drum`) is a separate cylinder along X,
    centred on its axis, so the scene can place it under the front edge and turn it."""
    w, d, h = L["tw"], L["td"], L["th"]
    shell = box("toner_body", -w / 2, w / 2, -d / 2, d / 2, 0.0, h, rv=0.06, re=0.03,
                seg_v=6, seg_e=2)
    # the drum shows through a slot along the bottom of the front
    cut(shell, box("c_drum", -w / 2 + 0.12, w / 2 - 0.12, -d / 2 - 0.1, -d / 2 + 0.16, -0.1,
                   0.20))
    finish(shell)
    finish(box("toner_grip", -0.40, 0.40, -d / 2 + 0.08, -d / 2 + 0.22, h - 0.01, h + 0.07,
               rv=0.03, re=0.015))
    drum = cylinder("toner_drum", 0, 0, -(w / 2 - 0.13), w / 2 - 0.13, 0.12, seg=24)
    drum.data.transform(Matrix.Rotation(math.radians(90), 4, 'Y'))     # along X
    finish(drum)


def build_style(style):
    s = SPECS[style]
    L = layout(s)
    body(s, L)
    if s["mfp"]:
        scanner(s, L)
    control_panel(s, L)
    toner(L)


STYLES = {style: (lambda style=style: build_style(style)) for style in SPECS}
