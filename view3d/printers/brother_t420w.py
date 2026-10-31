"""Brother InkBenefit Tank family (DCP-T220 / T420W / T520W / T720DW): style
"brother_t420w".

Brother lists the DCP-T420W at 435 x 359 x 159 mm (W x D x H). A flat dark grey box: the
scanner and its lid over the whole top, the control panel at the front left of the top,
the four tanks at the front right behind windows, under a flip cover with the logo.
Paper goes in through the cassette at the bottom of the front and comes out over it. The
waste ink goes from the service station (right, where the carriage parks) into felt pads
in the base, seen through a pane in the right side.
"""
from parts import (box, box_y, cut, feet, felt_sheets, finish, ink_block, join, output_tray,
                   pad_tub, power_button, rear_ports, service_station, side_pad_bay,
                   tank_windows)

X0, X1 = -2.175, 2.175
Y0, Y1 = -1.795, 1.795
BODY = 1.24
SCAN = 1.46
LID = 1.59
TANKS = [1.275, 1.475, 1.675, 1.875]        # window centres, K C M Y
TANK_W = 0.15
WIN_Z0, WIN_Z1 = 0.20, 0.62
LIQ_DEPTH = 0.40
PADWIN = (-0.20, 0.90, 0.10, 0.60)          # right side window y0, y1, z0, z1
SLOT = (-1.55, 0.85, 0.52, 0.92)            # output opening x0, x1, z0, z1
CASSETTE = (-1.45, 0.75, 0.08, 0.48)        # paper cassette front x0, x1, z0, z1


def body():
    ports, port_insides = rear_ports(0.50, -1.30, Y1)
    base = box("body", X0, X1, Y0, Y1, 0.02, BODY, rv=0.08, re=0.03)
    sx0, sx1, sz0, sz1 = SLOT
    slot = box("c_slot", sx0, sx1, Y0 - 0.2, Y0 + 0.60, sz0, sz1, rv=0.03)
    cx0, cx1, cz0, cz1 = CASSETTE
    pocket = box("c_cass", cx0, cx1, Y0 - 0.2, Y0 + 0.03, cz0, cz1, rv=0.02)
    wins = tank_windows(TANKS, TANK_W, Y0, WIN_Z0, WIN_Z1, LIQ_DEPTH)
    cut(base, slot, pocket, *wins, *side_pad_bay(X1, PADWIN, 0.85), *ports)
    finish(base)

    # the cassette's front, with its finger grip, a lighter grey
    front = box("cassette", cx0 + 0.008, cx1 - 0.008, Y0 + 0.002, Y0 + 0.03, cz0 + 0.008,
                cz1 - 0.008, rv=0.015, re=0.008)
    cut(front, box("c_grip", -0.55, -0.15, Y0 - 0.1, Y0 + 0.02, cz1 - 0.12, cz1))
    finish(front)
    # the flip cover over the tank caps, proud of the front, and the window surround
    finish(box_y("tank_cover", 1.08, 2.08, Y0 - 0.03, Y0 + 0.01, 0.72, 1.18, r=0.03, re=0.008))

    finish(box("scanner", X0 + 0.005, X1 - 0.005, Y0 - 0.005, Y1 - 0.005, BODY + 0.008, SCAN,
               rv=0.08, re=0.03))
    finish(box("lid", X0 + 0.03, X1 - 0.03, Y0 + 0.44, Y1 - 0.03, SCAN + 0.006, LID,
               rv=0.07, re=0.035))

    finish(join("slot_inner",
                box("a", sx0 + 0.01, sx1 - 0.01, Y0 + 0.56, Y0 + 0.59, sz0 + 0.005, sz1 - 0.005),
                *port_insides))
    # the paper comes out onto a short tray over the cassette
    output_tray(-1.30, 0.60, Y0 + 0.45, Y0 - 0.25, sz0 + 0.005, extender=0.25, stop=0.06)
    feet([(-1.9, -1.5), (1.9, -1.5), (-1.9, 1.5), (1.9, 1.5)])


def control_panel():
    """Front left of the top: power, the copy and Wi-Fi keys and the status lights."""
    top = SCAN
    finish(box("panel", X0 + 0.08, -0.85, Y0 + 0.04, Y0 + 0.42, top - 0.005, top + 0.008,
               rv=0.04, re=0.005))
    p = top + 0.008
    keys = [box(f"b{i}", x - 0.05, x + 0.05, Y0 + 0.23 - 0.04, Y0 + 0.23 + 0.04,
                p - 0.004, p + 0.016, rv=0.02, re=0.006)
            for i, x in enumerate((-1.70, -1.52, -1.34, -1.16))]
    finish(join("buttons", power_button(-1.96, Y0 + 0.23, p, r=0.05, ring=0.066, h=0.02,
                                        ring_h=0.01), *keys))
    finish(join("leds", *[box(f"l{i}", x - 0.02, x + 0.02, Y0 + 0.33, Y0 + 0.36, p - 0.004,
                              p + 0.005) for i, x in enumerate((-1.70, -1.52, -1.34))]))


def inside():
    ink_block("liquid", TANK_W - 0.012, LIQ_DEPTH)
    y0, y1, z0, z1 = PADWIN
    bx0, bx1, by0, by1, bz0, bz1 = 1.40, 2.10, y0 + 0.05, y1 - 0.05, z0 - 0.015, z0 + 0.15
    t = 0.018
    pad_tub(bx0, bx1, by0, by1, bz0, bz1,
            lip=(bx1 - t - 0.01, bx1 + 0.1, by0 + t, by1 - t, bz0 + 0.07, bz1 + 0.1))
    felt_sheets("pads", (bx0 + t + 0.01, bx1 - t - 0.012, by0 + t + 0.01, by1 - t - 0.012,
                         bz0 + t, bz0 + t + 3 * 0.042 + 2 * 0.004), n=3, cuts=2)
    service_station(1.48, 2.02, -0.10, 0.65, 0.36, 0.55, drain=(1.70, 0.27),
                    caps=[(1.56, 1.72, 0.10, 0.42), (1.78, 1.96, 0.10, 0.42)])


def build():
    body()
    control_panel()
    inside()


STYLES = {"brother_t420w": build}
