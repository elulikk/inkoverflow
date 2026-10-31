"""Epson L3150 family (L3110 / L3150 / L3210 / L3250): style "epson_l3150".

Printer body with the scanner and document lid on top, the tank unit bolted on the right,
the waste-ink pads behind a door at the back, on the tank side.
"""
from parts import (box, cut, feet, finish, felt_sheets, ink_block, join, pad_tub,
                   paper_support, power_button, rear_ports, tank_windows, cylinder)

# ---- main dimensions (dm) --------------------------------------------------------
X0, X1 = -1.875, 1.875          # full width
TX = 1.20                       # where the main body ends and the tank unit starts
Y0, Y1 = -1.40, 1.40            # main body depth (front is Y0)
BASE_TOP = 1.08                 # printer body
SCAN_TOP = 1.50                 # scanner unit
LID_TOP = 1.66                  # document lid
TANK_TOP = 1.40
TANK_Y0 = -1.44
WIN_Z0, WIN_Z1 = 0.12, 0.54     # tank windows
WIN_W, WIN_GAP = 0.118, 0.034
DOOR = (0.30, 1.06, 0.07, 0.58)     # rear pad door, tank side, next to the corner: x0, x1, z0, z1
LIQUID_DEPTH = 0.40


def body():
    ports, port_insides = rear_ports(-0.42, -0.80, Y1)
    base = box("body", X0, TX, Y0, Y1, 0.02, BASE_TOP, rv=0.16, re=0.035)
    slot = box("c_slot", -1.46, 0.96, Y0 - 0.2, Y0 + 0.55, 0.17, 0.42, rv=0.03)
    door = box("c_door", DOOR[0], DOOR[1], Y1 - 0.62, Y1 + 0.2, DOOR[2], DOOR[3], rv=0.02)
    feed = box("c_feed", -1.05, 0.75, Y1 - 0.30, Y1 - 0.10, BASE_TOP - 0.06, BASE_TOP + 0.2)
    cut(base, slot, door, feed, *ports)
    finish(base)

    finish(box("scanner", X0, TX, Y0 - 0.03, Y1, BASE_TOP + 0.012, SCAN_TOP, rv=0.16, re=0.04))
    finish(box("lid", X0 + 0.03, TX - 0.03, -1.12, Y1 - 0.02, SCAN_TOP + 0.008, LID_TOP,
               rv=0.13, re=0.05))

    # front cover between the slot and the scanner, a hair proud of the body
    finish(box("front_panel", -1.50, 1.00, Y0 - 0.018, Y0 + 0.02, 0.46, 1.03, re=0.012))

    # dark interior of the output slot and the feeder (seen through the openings)
    finish(join("slot_inner",
                box("a", -1.45, 0.95, Y0 + 0.50, Y0 + 0.53, 0.18, 0.41),
                box("b", -1.04, 0.74, Y1 - 0.31, Y1 - 0.11, BASE_TOP - 0.07, BASE_TOP - 0.05),
                *port_insides))

    # output tray with its extender and a small lip
    finish(join("tray",
                box("t1", -1.24, 0.74, Y0 - 0.66, Y0 + 0.3, 0.19, 0.225, rv=0.03, re=0.008),
                box("t2", -1.10, 0.60, Y0 - 1.02, Y0 - 0.60, 0.205, 0.228, rv=0.03, re=0.006),
                box("t3", -1.10, 0.60, Y0 - 1.05, Y0 - 0.99, 0.205, 0.30, re=0.01)))

    paper_support(-0.92, 0.62, (0, Y1 - 0.16, BASE_TOP + 0.02))
    feet([(-1.6, -1.1), (0.95, -1.1), (-1.6, 1.1), (1.6, 1.1), (1.6, -1.2)])


def control_panel():
    y = Y0 + 0.13
    finish(join("buttons", power_button(-1.62, y, SCAN_TOP),
                *[box(f"b{i}", -1.40 + i * 0.16, -1.30 + i * 0.16, y - 0.045, y + 0.045,
                      SCAN_TOP - 0.01, SCAN_TOP + 0.016, rv=0.02, re=0.008)
                  for i in range(5)]))
    finish(join("leds", *[box(f"l{i}", -1.37 + i * 0.16, -1.33 + i * 0.16, y + 0.06, y + 0.075,
                              SCAN_TOP - 0.01, SCAN_TOP + 0.006) for i in range(5)]))


def tank_unit():
    unit = box("tank_unit", TX + 0.008, X1, TANK_Y0, 0.95, 0.02, TANK_TOP, rv=0.14, re=0.04)
    cx = (TX + X1) / 2
    total = 4 * WIN_W + 3 * WIN_GAP
    centres = [cx - total / 2 + WIN_W / 2 + i * (WIN_W + WIN_GAP) for i in range(4)]
    cut(unit, *tank_windows(centres, WIN_W, TANK_Y0, WIN_Z0, WIN_Z1, LIQUID_DEPTH, r=0.014))
    finish(unit)
    # cap cover on top of the tanks
    finish(box("tank_cap", TX + 0.06, X1 - 0.05, TANK_Y0 + 0.06, 0.40, TANK_TOP - 0.01,
               TANK_TOP + 0.035, rv=0.10, re=0.02))
    ink_block("liquid", WIN_W - 0.012, LIQUID_DEPTH)


def pads():
    """The waste-ink pads: felt sheets standing upright, side by side, in a plastic box
    that sits behind the rear door (the door is see-through in the scene)."""
    bx0, bx1 = DOOR[0] + 0.03, DOOR[1] - 0.03
    by0, by1 = Y1 - 0.58, Y1 - 0.045
    bz0, bz1 = DOOR[2] + 0.015, DOOR[3] - 0.03
    t = 0.018                                   # wall thickness
    tab = box("tab", (bx0 + bx1) / 2 - 0.08, (bx0 + bx1) / 2 + 0.08, by1 - 0.01, by1 + 0.012,
              bz0 + 0.02, bz0 + 0.11, rv=0.01, re=0.004)
    # the wall facing the door is low, so the sheets show above it
    pad_tub(bx0, bx1, by0, by1, bz0, bz1,
            lip=(bx0 + t, bx1 - t, by1 - t - 0.01, by1 + 0.1, bz0 + 0.13, bz1 + 0.1),
            extra=[tab])
    felt_sheets("pads", (bx0 + t + 0.008, bx1 - t - 0.008, by0 + t + 0.01, by1 - t - 0.012,
                         bz0 + t, bz1 - 0.035),
                n=6, stack='x', gap=0.012, uneven=0.012, cuts=2, bump=0.007, freq=11.0)

    finish(box("pad_cavity", DOOR[0], DOOR[1], Y1 - 0.62, Y1 - 0.60, DOOR[2], DOOR[3]))
    finish(box("pad_door", DOOR[0] + 0.004, DOOR[1] - 0.004, Y1 - 0.025, Y1 - 0.012,
               DOOR[2] + 0.004, DOOR[3] - 0.004, rv=0.018, re=0.006))
    finish(cylinder("pad_screw", DOOR[0] + 0.09, (DOOR[2] + DOOR[3]) / 2 - 0.06,
                    Y1 - 0.016, Y1 + 0.004, 0.022, seg=20, axis='Y'))


def build():
    body()
    control_panel()
    tank_unit()
    pads()


STYLES = {"epson_l3150": build}
