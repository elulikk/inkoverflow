"""HP Ink Tank family (Ink Tank 310 / 315 / 319 / Wireless 410 / 415 / 419): style
"hp_ink_tank_415".

HP lists the 415 at 525 x 310 x 158 mm (W x D x H, trays closed). Glossy black. The main
body is a compact DeskJet-like multifunction (scanner and lid on top, buttons on the
front of the scanner, the output slot in front, the rear paper input with its support);
the four tanks are in a unit bolted on its right side, the wide black one first, under a
lid that flips up to refill them. The waste ink goes from the service station (right,
where the carriage parks) into felt pads in the base, seen through a pane in the right
side of the main body, behind the tank unit.
"""
from parts import (box, cut, cylinder, feet, felt_sheets, finish, ink_block, join,
                   output_tray, pad_tub, paper_support, power_button, rear_ports,
                   service_station, side_pad_bay, tank_windows)

X0, X1 = -2.625, 2.625
Y0, Y1 = -1.55, 1.55
MAIN = 1.80                     # the main body ends here; the tank unit is to its right
BODY = 1.10
SCAN = 1.42
LID = 1.58
REAR = Y1 - 0.30                # where the scanner ends and the rear paper input starts
UNIT_Y1 = 0.40                  # back of the tank unit
UNIT_TOP = 1.02
TANKS = [1.98, 2.175, 2.33, 2.485]          # window centres: K C M Y
TANK_W = [0.20, 0.12, 0.12, 0.12]
WIN_Z0, WIN_Z1 = 0.25, 0.80
LIQ_DEPTH = 0.40
PADWIN = (0.60, 1.35, 0.10, 0.60)           # main body's right side window y0, y1, z0, z1
SLOT = (-1.60, 1.00, 0.30, 0.72)


def body():
    ports, port_insides = rear_ports(0.40, -1.60, Y1)
    base = box("body", X0, MAIN, Y0, Y1, 0.02, BODY, rv=0.14, re=0.04)
    sx0, sx1, sz0, sz1 = SLOT
    slot = box("c_slot", sx0, sx1, Y0 - 0.2, Y0 + 0.60, sz0, sz1, rv=0.04)
    cut(base, slot, *side_pad_bay(MAIN, PADWIN, 0.80), *ports)
    finish(base)

    finish(box("scanner", X0 + 0.01, MAIN - 0.01, Y0 + 0.02, REAR, BODY + 0.008, SCAN,
               rv=0.12, re=0.04))
    finish(box("lid", X0 + 0.04, MAIN - 0.04, Y0 + 0.06, REAR - 0.02, SCAN + 0.006, LID,
               rv=0.10, re=0.045))
    rear = box("rear_cover", X0 + 0.02, MAIN - 0.02, REAR + 0.01, Y1, BODY - 0.01, SCAN - 0.06,
               rv=0.12, re=0.03)
    cut(rear, box("c_feed", -1.60, 0.80, REAR + 0.08, REAR + 0.18, SCAN - 0.20, SCAN))
    finish(rear)
    paper_support(-1.55, 0.75, (0, REAR + 0.20, SCAN - 0.20), lean=-12, height=0.95,
                  thick=0.022)

    finish(join("slot_inner",
                box("a", sx0 + 0.01, sx1 - 0.01, Y0 + 0.56, Y0 + 0.59, sz0 + 0.005, sz1 - 0.005),
                box("b", -1.59, 0.79, REAR + 0.08, REAR + 0.18, SCAN - 0.21, SCAN - 0.19),
                *port_insides))
    output_tray(-1.40, 0.80, Y0 + 0.45, Y0 - 0.55, sz0 + 0.005)
    feet([(-2.3, -1.25), (1.5, -1.25), (-2.3, 1.25), (1.5, 1.25), (2.4, -1.25)])


def control_panel():
    """On the front of the scanner, left: power with its light, then cancel, colour copy
    and black copy, the Wi-Fi and status lights over them."""
    y = Y0 + 0.02
    z = (BODY + SCAN) / 2
    btns = [power_button(-2.40, y, z, r=0.045, ring=0.062, h=0.02, ring_h=0.012, axis='Y')]
    for i, x in enumerate((-2.18, -2.02, -1.86)):
        btns.append(cylinder(f"b{i}", x, z, y - 0.018, y + 0.01, 0.042, axis='Y'))
    finish(join("buttons", *btns))
    finish(join("leds", *[box(f"l{i}", x - 0.025, x + 0.025, y - 0.012, y + 0.01, z + 0.07,
                              z + 0.09) for i, x in enumerate((-2.18, -2.02, -1.86))]))


def tank_unit():
    unit = box("tank_unit", MAIN + 0.006, X1, Y0, UNIT_Y1, 0.02, UNIT_TOP, rv=0.12, re=0.04)
    cut(unit, *tank_windows(TANKS, TANK_W, Y0, WIN_Z0, WIN_Z1, LIQ_DEPTH))
    finish(unit)
    # the lid over the refill caps
    finish(box("tank_cap", MAIN + 0.05, X1 - 0.04, Y0 + 0.04, UNIT_Y1 - 0.04, UNIT_TOP - 0.01,
               UNIT_TOP + 0.05, rv=0.09, re=0.025))
    ink_block("liquid", TANK_W[1] - 0.012, LIQ_DEPTH)


def inside():
    y0, y1, z0, z1 = PADWIN
    bx0, bx1, by0, by1, bz0, bz1 = 1.06, 1.76, y0 + 0.05, y1 - 0.05, z0 - 0.015, z0 + 0.15
    t = 0.018
    pad_tub(bx0, bx1, by0, by1, bz0, bz1,
            lip=(bx1 - t - 0.01, bx1 + 0.1, by0 + t, by1 - t, bz0 + 0.07, bz1 + 0.1))
    felt_sheets("pads", (bx0 + t + 0.01, bx1 - t - 0.012, by0 + t + 0.01, by1 - t - 0.012,
                         bz0 + t, bz0 + t + 3 * 0.042 + 2 * 0.004), n=3, cuts=2)
    # under the parked carriage, in the middle of the depth; the drain runs back to the pads
    service_station(1.10, 1.65, -0.40, 0.35, 0.36, 0.55, drain=(1.38, -0.02),
                    caps=[(1.18, 1.34, -0.22, 0.10), (1.40, 1.58, -0.22, 0.10)])


def build():
    body()
    control_panel()
    tank_unit()
    inside()


STYLES = {"hp_ink_tank_415": build}
