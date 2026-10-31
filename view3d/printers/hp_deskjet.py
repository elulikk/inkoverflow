"""HP DeskJet 2700 family (DeskJet 2710 / 2720 / 2752 / 2755, DeskJet Ink Advantage 2775 /
2776 / 2778): style "hp_deskjet_2775".

HP lists the Ink Advantage 2775 at 425 x 304 x 154 mm (W x D x H, trays closed). White,
with light grey accents. The scanner lid over most of the top, the control panel (small
icon screen and buttons) at its front left, the rear paper input with its support at the
back. In front, the cartridge door, which folds down to reach the two HP 667 cartridges
(black and tri-colour) in the carriage, and under it the output slot and its tray. The
waste ink goes from the service station (right, where the carriage parks) into a felt
pad in the base, seen through a pane in the right side.
"""
from parts import (box, box_y, cartridge, cut, feet, felt_sheets, finish, join, output_tray,
                   pad_tub, paper_support, power_button, rear_ports, service_station,
                   side_pad_bay)

X0, X1 = -2.125, 2.125
Y0, Y1 = -1.52, 1.52
BODY = 1.02
SCAN = 1.36
LID = 1.54
REAR = Y1 - 0.28                # where the scanner ends and the rear paper input starts
DOOR = (-1.30, 1.30, 0.50, 0.98)            # cartridge door x0, x1, z0 (its hinge), z1
BAY_DEPTH = 0.75                # the hollow behind the door, where the carriage runs
SLOT = (-1.25, 1.25, 0.22, 0.47)
PADWIN = (-0.40, 0.60, 0.10, 0.48)          # right side window y0, y1, z0, z1


def body():
    ports, port_insides = rear_ports(0.40, -1.40, Y1)
    base = box("body", X0, X1, Y0, Y1, 0.02, BODY, rv=0.10, re=0.035)
    dx0, dx1, dz0, dz1 = DOOR
    door_hole = box("c_door", dx0, dx1, Y0 - 0.2, Y0 + 0.03, dz0, dz1, rv=0.03)
    bay = box("c_bay", dx0 + 0.08, dx1 - 0.08, Y0, Y0 + BAY_DEPTH, dz0 + 0.02, dz1 + 0.01)
    sx0, sx1, sz0, sz1 = SLOT
    slot = box("c_slot", sx0, sx1, Y0 - 0.2, Y0 + 0.60, sz0, sz1, rv=0.03)
    cut(base, door_hole, bay, slot, *side_pad_bay(X1, PADWIN, 0.80), *ports)
    finish(base)

    # the door, closed; the scene folds it down about its bottom edge
    finish(box_y("door", dx0 + 0.006, dx1 - 0.006, Y0 - 0.004, Y0 + 0.026, dz0 + 0.006,
                 dz1 - 0.006, r=0.025, re=0.008))
    # floor and back wall of the bay behind it
    finish(join("bay",
                box("f", dx0 + 0.08, dx1 - 0.08, Y0 + 0.02, Y0 + BAY_DEPTH, dz0 + 0.02, dz0 + 0.04),
                box("w", dx0 + 0.08, dx1 - 0.08, Y0 + BAY_DEPTH - 0.02, Y0 + BAY_DEPTH,
                    dz0 + 0.02, dz1 + 0.01)))

    finish(box("scanner", X0 + 0.006, X1 - 0.006, Y0 - 0.004, REAR, BODY + 0.008, SCAN,
               rv=0.09, re=0.035))
    finish(box("lid", -1.12, X1 - 0.025, Y0 + 0.02, REAR - 0.02, SCAN + 0.006, LID,
               rv=0.08, re=0.04))
    # grey rear cover with the paper slot, and the input tray standing behind it
    rear = box("rear_cover", X0 + 0.01, X1 - 0.01, REAR + 0.01, Y1, BODY - 0.01, SCAN + 0.03,
               rv=0.09, re=0.03)
    cut(rear, box("c_feed", -1.35, 1.05, REAR + 0.07, REAR + 0.17, SCAN - 0.15, SCAN + 0.1))
    finish(rear)
    paper_support(-1.30, 1.00, (0, REAR + 0.19, SCAN - 0.12), lean=-10, height=1.05,
                  thick=0.022)

    finish(join("slot_inner",
                box("a", sx0 + 0.01, sx1 - 0.01, Y0 + 0.56, Y0 + 0.59, sz0 + 0.005, sz1 - 0.005),
                box("b", -1.34, 1.04, REAR + 0.07, REAR + 0.17, SCAN - 0.16, SCAN - 0.14),
                *port_insides))
    output_tray(-1.10, 1.10, Y0 + 0.45, Y0 - 0.55, sz0 + 0.005)
    feet([(-1.85, -1.25), (1.85, -1.25), (-1.85, 1.25), (1.85, 1.25)])


def control_panel():
    """Front left of the top, beside the lid: the small icon screen, the keys round it,
    the power button."""
    top = SCAN
    finish(box("panel", X0 + 0.07, -1.16, Y0 + 0.03, Y0 + 0.90, top - 0.005, top + 0.008,
               rv=0.05, re=0.005))
    p = top + 0.008
    finish(box("lcd", -1.86, -1.44, Y0 + 0.40, Y0 + 0.66, p - 0.004, p + 0.005,
               rv=0.012, re=0.003))
    keys = [box(f"b{i}", x - 0.05, x + 0.05, Y0 + 0.20 - 0.035, Y0 + 0.20 + 0.035,
                p - 0.004, p + 0.016, rv=0.015, re=0.006)
            for i, x in enumerate((-1.84, -1.68, -1.52))]
    finish(join("buttons", power_button(-1.32, Y0 + 0.20, p, r=0.045, ring=0.062, h=0.02,
                                        ring_h=0.01), *keys))
    finish(box("leds", -1.86, -1.44, Y0 + 0.30, Y0 + 0.32, p - 0.004, p + 0.004))


def inside():
    y0, y1, z0, z1 = PADWIN
    bx0, bx1, by0, by1, bz0, bz1 = 1.38, 2.08, y0 + 0.05, y1 - 0.05, z0 - 0.015, z0 + 0.14
    t = 0.018
    pad_tub(bx0, bx1, by0, by1, bz0, bz1,
            lip=(bx1 - t - 0.01, bx1 + 0.1, by0 + t, by1 - t, bz0 + 0.07, bz1 + 0.1))
    felt_sheets("pads", (bx0 + t + 0.01, bx1 - t - 0.012, by0 + t + 0.01, by1 - t - 0.012,
                         bz0 + t, bz0 + t + 2 * 0.045 + 0.004), n=2, cuts=2)
    # under the parked carriage, at the front: one cap per cartridge; the drain runs back
    service_station(1.40, 1.90, -1.30, -0.80, 0.30, 0.42, drain=(1.65, -1.05),
                    caps=[(1.46, 1.60, -1.20, -0.90), (1.66, 1.84, -1.20, -0.90)],
                    top_h=0.015, top_in=0.05, leg_h=0.08, cap_h=0.02, cap_r=0.03)

    # the two HP 667 cartridges, black (narrow) and tri-colour; the scene puts them in the
    # carriage
    cartridge(0.20, 0.36, 0.30, prefix="cart_k")
    cartridge(0.32, 0.36, 0.30, prefix="cart_c")


def build():
    body()
    control_panel()
    inside()


STYLES = {"hp_deskjet_2775": build}
