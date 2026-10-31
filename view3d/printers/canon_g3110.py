"""Canon PIXMA G series MegaTank (G2110 / G3110 / G3160 / G2410 / G3410): style
"canon_g3110".

Canon lists 445 x 330 x 163 mm (W x D x H). Matte black. The ink tanks stand at the front
corners, in two pods that stick out of the front: the big black one on the left, cyan,
magenta and yellow on the right. Between them the front panel with the Canon logo, the
output slot and its tray. On top the scanner with its lid, the control panel (small
screen and buttons) on the right over the colour tanks, the rear paper support at the
back. The waste ink goes from the service station (right, where the carriage parks) into
felt pads in the base; the scene shows them through a pane in the right side.
"""
from parts import (box, cut, feet, felt_sheets, finish, ink_block, join, output_tray,
                   pad_tub, paper_support, power_button, rear_ports, service_station,
                   side_pad_bay, tank_windows)

X0, X1 = -2.225, 2.225
Y0, Y1 = -1.65, 1.65
BODY = 1.22                     # body and the tank pods
SCAN = 1.47                     # scanner unit
LID = 1.63                      # document lid
POD = 1.625                     # the pods are outside x = +-POD
RECESS = 0.06                   # how far the front between the pods is set back
TANKS = [-1.925, 1.755, 1.925, 2.095]       # window centres: K (left pod), C M Y (right)
TANK_W = [0.30, 0.13, 0.13, 0.13]
WIN_Z0, WIN_Z1 = 0.28, 0.78
LIQ_DEPTH = 0.40
PADWIN = (-0.55, 0.55, 0.10, 0.62)          # right side window y0, y1, z0, z1
SLOT = (-1.25, 1.25, 0.25, 0.62)            # output slot x0, x1, z0, z1


def body():
    ports, port_insides = rear_ports(0.60, -1.40, Y1)
    base = box("body", X0, X1, Y0, Y1, 0.02, BODY, rv=0.10, re=0.03)
    front = box("c_front", -POD + 0.015, POD - 0.015, Y0 - 0.2, Y0 + RECESS, 0.06,
                BODY + 0.1, rv=0.02)
    sx0, sx1, sz0, sz1 = SLOT
    slot = box("c_slot", sx0, sx1, Y0 - 0.2, Y0 + 0.60, sz0, sz1, rv=0.03)
    wins = tank_windows(TANKS, TANK_W, Y0, WIN_Z0, WIN_Z1, LIQ_DEPTH)
    cut(base, front, slot, *wins, *side_pad_bay(X1, PADWIN, 0.85), *ports)
    finish(base)

    # glossy strip with the logo, between the pods and over the slot
    finish(box("front_panel", -1.55, 1.55, Y0 + RECESS - 0.02, Y0 + RECESS + 0.01, 0.70, 1.15,
               rv=0.0, re=0.01))
    # scanner unit over the middle and the right pod; the left pod's top shows
    finish(box("scanner", -POD + 0.02, X1 - 0.005, Y0 + RECESS - 0.01, Y1 - 0.005, BODY + 0.008,
               SCAN, rv=0.09, re=0.035))
    finish(box("lid", -POD + 0.04, 1.30, Y0 + RECESS + 0.02, Y1 - 0.26, SCAN + 0.006, LID,
               rv=0.08, re=0.04))
    # cap cover over the black tank
    finish(box("tank_cap", X0 + 0.05, -POD - 0.04, Y0 + 0.06, Y0 + 0.80, BODY - 0.01,
               BODY + 0.035, rv=0.06, re=0.015))

    finish(join("slot_inner",
                box("a", sx0 + 0.01, sx1 - 0.01, Y0 + 0.56, Y0 + 0.59, sz0 + 0.005, sz1 - 0.005),
                *port_insides))
    output_tray(-1.10, 1.10, Y0 + 0.45, Y0 - 0.60, sz0 + 0.005)
    paper_support(-1.15, 1.05, (0, Y1 - 0.13, SCAN - 0.03), lean=-15, height=1.0)
    feet([(-1.95, -1.35), (1.95, -1.35), (-1.95, 1.35), (1.95, 1.35)])


def control_panel():
    """On the scanner unit's top right: the small screen, the buttons round it, the
    power button at the front right."""
    top = SCAN
    finish(box("panel", 1.36, X1 - 0.07, Y0 + 0.10, Y0 + 0.82, top - 0.005, top + 0.008,
               rv=0.04, re=0.005))
    p = top + 0.008
    finish(box("lcd", 1.48, 1.80, Y0 + 0.46, Y0 + 0.70, p - 0.004, p + 0.006,
               rv=0.012, re=0.003))
    keys = [box(f"b{i}", x - 0.045, x + 0.045, Y0 + 0.24 - 0.035, Y0 + 0.24 + 0.035,
                p - 0.004, p + 0.016, rv=0.015, re=0.006)
            for i, x in enumerate((1.52, 1.66, 1.80))]
    keys += [box(f"n{i}", 1.90, 1.99, y - 0.035, y + 0.035, p - 0.004, p + 0.016,
                 rv=0.015, re=0.006) for i, y in enumerate((Y0 + 0.50, Y0 + 0.64))]
    finish(join("buttons", power_button(2.06, Y0 + 0.24, p, r=0.045, ring=0.062, h=0.02,
                                        ring_h=0.01), *keys))
    finish(join("leds", *[box(f"l{i}", 1.88, 1.92, y - 0.012, y + 0.012, p - 0.004, p + 0.005)
                          for i, y in enumerate((Y0 + 0.24, Y0 + 0.34))]))


def inside():
    ink_block("liquid", TANK_W[1] - 0.012, LIQ_DEPTH)
    y0, y1, z0, z1 = PADWIN
    bx0, bx1, by0, by1, bz0, bz1 = 1.42, 2.15, y0 + 0.05, y1 - 0.05, z0 - 0.015, z0 + 0.15
    t = 0.018
    pad_tub(bx0, bx1, by0, by1, bz0, bz1,
            lip=(bx1 - t - 0.01, bx1 + 0.1, by0 + t, by1 - t, bz0 + 0.07, bz1 + 0.1))
    felt_sheets("pads", (bx0 + t + 0.01, bx1 - t - 0.012, by0 + t + 0.01, by1 - t - 0.012,
                         bz0 + t, bz0 + t + 3 * 0.042 + 2 * 0.004), n=3, cuts=2)
    service_station(1.50, 2.05, -0.45, 0.30, 0.36, 0.55, drain=(1.70, -0.08),
                    caps=[(1.58, 1.74, -0.28, 0.04), (1.80, 1.98, -0.28, 0.04)])


def build():
    body()
    control_panel()
    inside()


STYLES = {"canon_g3110": build}
