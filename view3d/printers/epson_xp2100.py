"""Epson XP-2100 family (XP-2100 / XP-2101 / XP-2105): style "epson_xp2100".

Epson lists 375 x 300 x 145 mm (W x D x H, trays closed). All black: a glossy front strip
with the buttons and the EPSON logo, the output slot under it, the scanner unit on top and
the rear paper support standing up at the back. No tanks: four separate cartridges (Epson
206: K, C, M, Y) ride in the print carriage under the scanner unit, which hinges up at the
back to reach them (the scene opens it). The waste ink goes from the service station
(right, where the carriage parks) into felt pads lying in the base; the scene shows them
through a see-through pane on the right side.
"""
from parts import (box, box_y, cartridge, cut, cylinder, feet, felt_sheets, finish, join,
                   pad_tub, paper_support, power_button, rear_ports, service_station,
                   side_pad_bay)

XX0, XX1 = -1.875, 1.875
XY0, XY1 = -1.50, 1.50
X_BODY = 0.92                   # printer body
X_SCAN = 1.36                   # scanner unit
X_LID = 1.45                    # document lid
X_REAR = XY1 - 0.34             # where the scanner unit ends and the rear feeder starts
X_SLOT = (-1.40, 1.10, 0.10, 0.44)          # output slot x0, x1, z0, z1
X_PANEL = (-1.72, 1.72, 0.50, 0.88)         # glossy front strip x0, x1, z0, z1
X_PADWIN = (-0.85, 0.60, 0.08, 0.46)        # right side window y0, y1, z0, z1


def body():
    ports, port_insides = rear_ports(0.40, -1.30, XY1)
    base = box("body", XX0, XX1, XY0, XY1, 0.02, X_BODY, rv=0.10, re=0.03)
    sx0, sx1, sz0, sz1 = X_SLOT
    slot = box("c_slot", sx0, sx1, XY0 - 0.2, XY0 + 0.60, sz0, sz1, rv=0.03)
    # the strip sits in a shallow recess, so it reads as a separate glossy part
    px0, px1, pz0, pz1 = X_PANEL
    recess = box("c_panel", px0, px1, XY0 - 0.2, XY0 + 0.02, pz0, pz1, rv=0.04)
    # open top under the scanner unit, where the carriage and the cartridges run
    well = box("c_well", XX0 + 0.10, XX1 - 0.10, XY0 + 0.20, X_REAR - 0.05, 0.30,
               X_BODY + 0.1, rv=0.05)
    cut(base, slot, recess, *side_pad_bay(XX1, X_PADWIN, 0.87), *ports, well)
    finish(base)

    finish(box("front_panel", px0 + 0.006, px1 - 0.006, XY0 - 0.012, XY0 + 0.03,
               pz0 + 0.006, pz1 - 0.006, rv=0.035, re=0.012))

    # scanner unit (hinged at the back in the scene) and the document lid on it
    finish(box("scanner", XX0 + 0.005, XX1 - 0.005, XY0 - 0.005, X_REAR, X_BODY + 0.008,
               X_SCAN, rv=0.10, re=0.035))
    finish(box("lid", XX0 + 0.025, XX1 - 0.025, XY0 + 0.015, X_REAR - 0.02, X_SCAN + 0.006,
               X_LID, rv=0.09, re=0.04))
    # finger grip under the front edge of the scanner unit
    finish(box("grip", -0.35, 0.35, XY0 - 0.02, XY0 + 0.01, X_BODY + 0.01, X_BODY + 0.05,
               rv=0.015))

    # rear feeder cover with its paper slot, and the paper support standing up behind it
    rear = box("rear_cover", XX0 + 0.005, XX1 - 0.005, X_REAR + 0.01, XY1, X_BODY - 0.01,
               X_SCAN - 0.04, rv=0.10, re=0.03)
    cut(rear, box("c_feed", -1.25, 0.95, X_REAR + 0.10, X_REAR + 0.20, X_SCAN - 0.20,
                  X_SCAN + 0.1))
    finish(rear)
    paper_support(-1.20, 0.90, (0, X_REAR + 0.24, X_SCAN - 0.20), lean=-14, height=1.05,
                  thick=0.022)
    finish(box("paper_guide", -1.20, -1.10, X_REAR + 0.11, X_REAR + 0.19, X_SCAN - 0.22,
               X_SCAN - 0.04, re=0.008))

    # dark interior seen through the openings
    finish(join("slot_inner",
                box("a", sx0 + 0.01, sx1 - 0.01, XY0 + 0.56, XY0 + 0.59, sz0 + 0.005, sz1 - 0.005),
                box("b", -1.24, 0.94, X_REAR + 0.10, X_REAR + 0.20, X_SCAN - 0.21, X_SCAN - 0.19),
                *port_insides))

    # output tray pulled out of the slot, with its extender and the paper stop
    finish(join("tray",
                box("t1", -1.10, 0.80, XY0 - 0.55, XY0 + 0.50, sz0, sz0 + 0.03, rv=0.03, re=0.008),
                box("t2", -0.95, 0.65, XY0 - 0.95, XY0 - 0.50, sz0 + 0.01, sz0 + 0.032,
                    rv=0.03, re=0.006),
                box("t3", -0.95, 0.65, XY0 - 0.98, XY0 - 0.92, sz0 + 0.01, sz0 + 0.10, re=0.01)))
    feet([(-1.6, -1.2), (1.6, -1.2), (-1.6, 1.2), (1.6, 1.2)])


def control_panel():
    """Buttons on the glossy front strip: power (with its ring light) on the left, the
    Wi-Fi and status lights, then the Wi-Fi, copy and stop buttons."""
    y = XY0 - 0.012
    z = 0.69
    btns = [power_button(-1.45, y, z, axis='Y')]
    for i, x in enumerate((-0.62, -0.40, -0.12, 0.10)):
        btns.append(cylinder(f"b{i}", x, z, y - 0.018, y + 0.01, 0.050, axis='Y'))
    finish(join("buttons", *btns))
    # Wi-Fi and status lights, then the ink light on its own (it blinks for a low cartridge)
    finish(join("leds", *[box_y(f"l{i}", -1.17, -1.13, y - 0.014, y + 0.01, zz - 0.02,
                                zz + 0.02, r=0.01) for i, zz in enumerate((0.77, 0.69))]))
    finish(box_y("ink_led", -1.17, -1.13, y - 0.014, y + 0.01, 0.59, 0.63, r=0.01))


def inside():
    # floor and back wall of the well the carriage runs in, under the scanner unit
    finish(join("bay",
                box("f", XX0 + 0.10, 1.05, XY0 + 0.20, X_REAR - 0.05, 0.28, 0.30),
                box("w", XX0 + 0.10, XX1 - 0.10, X_REAR - 0.07, X_REAR - 0.05, 0.28, X_BODY)))

    y0, y1, z0, z1 = X_PADWIN
    bx0, bx1, by0, by1, bz0, bz1 = 1.08, 1.80, y0 + 0.05, y1 - 0.05, z0 - 0.015, z0 + 0.14
    t = 0.018
    pad_tub(bx0, bx1, by0, by1, bz0, bz1,
            lip=(bx1 - t - 0.01, bx1 + 0.1, by0 + t, by1 - t, bz0 + 0.07, bz1 + 0.1))
    felt_sheets("pads", (bx0 + t + 0.01, bx1 - t - 0.012, by0 + t + 0.01, by1 - t - 0.012,
                         bz0 + t, bz0 + t + 3 * 0.040 + 2 * 0.004), n=3, cuts=2)
    # one cap for the black and colour heads, and the drain
    service_station(1.12, 1.62, -0.45, 0.30, 0.25, 0.34, caps=[(1.22, 1.52, -0.30, 0.12)],
                    top_h=0.015, top_in=0.05, leg_h=0.05, cap_h=0.02, cap_r=0.03)

    # one Epson 206 cartridge; the scene places four of them in the carriage
    cartridge(0.118, 0.44, 0.40)


def build():
    body()
    control_panel()
    inside()


STYLES = {"epson_xp2100": build}
