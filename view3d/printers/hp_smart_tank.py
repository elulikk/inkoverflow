"""HP Smart Tank family: styles "hp_smart_tank_580" and "hp_smart_tank_210".

Both share the white body (HP: 434 x 360 mm), the four tanks behind small windows at the
front left, the output slot at the front right and the waste-ink bay on the right side:
the service station (where the carriage parks) drains into felt pads lying in the base,
seen through a see-through pane. The 580 adds the scanner lid and the icon display; the
210/220 is print-only, lower, with a flat top cover and a few buttons.
"""
from parts import (box, box_y, cut, cylinder, feet, felt_sheets, finish, ink_block,
                   join, pad_tub, power_button, rear_ports, service_station, side_pad_bay,
                   tank_windows)

# HP lists the 580 at 434.7 x 361.5 x 157.3 mm (W x D x H, trays closed)
HX0, HX1 = -2.173, 2.173
HY0, HY1 = -1.808, 1.808
H_REAR = HY1 - 0.46             # where the lid ends and the rear paper cover starts
H_SLOT = (-1.09, 1.35, 0.15, 0.69)          # output slot x0, x1, z0, z1
H_TANKS = [-1.99 + i * 0.243 for i in range(4)]   # window centres, K C M Y
H_WIN_W, H_WIN_Z0, H_WIN_Z1 = 0.13, 0.17, 0.47
H_LIQ_DEPTH = 0.40
H_PADWIN = (-0.95, 0.55, 0.10, 0.62)        # right side window y0, y1, z0, z1


def body(top, cover_top, extra_cutters=()):
    """White base up to `top`, the dark control strip / lid / rear cover up to `cover_top`
    (the lid itself 0.037 higher), and everything on the front face. `extra_cutters` are
    cut from the base too."""
    ports, port_insides = rear_ports(0.55, -1.50, HY1)
    base = box("body", HX0, HX1, HY0, HY1, 0.02, top, rv=0.09, re=0.03)
    sx0, sx1, sz0, sz1 = H_SLOT
    slot = box("c_slot", sx0, sx1, HY0 - 0.2, HY0 + 0.62, sz0, sz1, rv=0.025)
    wins = tank_windows(H_TANKS, H_WIN_W, HY0, H_WIN_Z0, H_WIN_Z1, H_LIQ_DEPTH)
    bay = side_pad_bay(HX1, H_PADWIN, 0.92)
    cut(base, slot, *wins, *extra_cutters, *bay, *ports)
    finish(base)

    # dark top: control strip on the left, lid, rear paper cover
    finish(box("panel", HX0 + 0.012, -1.645, HY0 - 0.004, H_REAR - 0.012, top - 0.004,
               cover_top - 0.005, rv=0.08, re=0.025))
    finish(box("lid", -1.625, HX1 - 0.012, HY0 - 0.014, H_REAR - 0.012, top + 0.006,
               cover_top + 0.037, rv=0.07, re=0.03))
    rear = box("rear_cover", HX0 + 0.012, HX1 - 0.012, H_REAR, HY1 - 0.004, top - 0.004,
               cover_top, rv=0.08, re=0.025)
    cut(rear, box("c_groove", -1.45, 1.85, H_REAR + 0.20, H_REAR + 0.225, cover_top - 0.015,
                  cover_top + 0.065))
    finish(rear)

    # output slot: dark interior, the ribbed exit cover, the tray floor and its lip
    finish(join("slot_inner",
                box("a", sx0 + 0.01, sx1 - 0.01, HY0 + 0.58, HY0 + 0.61, sz0 + 0.005, sz1 - 0.005),
                *port_insides))
    ribs = [box("p", sx0 + 0.01, sx1 - 0.01, HY0 + 0.20, HY0 + 0.24, 0.33, sz1 - 0.004)]
    n = 13
    for i in range(n):
        x = sx0 + 0.12 + i * (sx1 - sx0 - 0.24) / (n - 1)
        ribs.append(box(f"r{i}", x - 0.012, x + 0.012, HY0 + 0.07, HY0 + 0.21, 0.37,
                        sz1 - 0.004, re=0.006))
    finish(join("slot_panel", *ribs))
    finish(join("tray",
                box("t1", sx0 + 0.03, sx1 - 0.03, HY0 - 0.03, HY0 + 0.58, sz0, sz0 + 0.035,
                    rv=0.02, re=0.006),
                box("t2", sx0 + 0.03, sx1 - 0.03, HY0 - 0.04, HY0 - 0.005, sz0, sz0 + 0.07,
                    rv=0.012, re=0.008)))

    # front details: the round logo, the model plate, the tabs above the tank windows
    finish(cylinder("logo", 0.073, 1.10, HY0 - 0.008, HY0 + 0.01, 0.163, seg=64, axis='Y'))
    finish(box_y("label_plate", 1.40, 2.03, HY0 - 0.005, HY0 + 0.01, 0.15, 0.28, r=0.02))
    finish(join("tank_tabs", *[box_y(f"g{i}", c - 0.06, c + 0.06, HY0 - 0.004, HY0 + 0.01,
                                     0.50, 0.61, r=0.015) for i, c in enumerate(H_TANKS)]))
    feet([(-1.9, -1.5), (1.9, -1.5), (-1.9, 1.5), (1.9, 1.5)])


def tanks_and_pads():
    ink_block("liquid", H_WIN_W - 0.012, H_LIQ_DEPTH)
    y0, y1, z0, z1 = H_PADWIN
    bx0, bx1, by0, by1, bz0, bz1 = 1.32, 2.09, y0 + 0.05, y1 - 0.05, z0 - 0.015, z0 + 0.15
    t = 0.018
    pad_tub(bx0, bx1, by0, by1, bz0, bz1,
            lip=(bx1 - t - 0.01, bx1 + 0.1, by0 + t, by1 - t, bz0 + 0.07, bz1 + 0.1))
    felt_sheets("pads", (bx0 + t + 0.01, bx1 - t - 0.012, by0 + t + 0.01, by1 - t - 0.012,
                         bz0 + t, bz0 + t + 3 * 0.042 + 2 * 0.004), n=3, cuts=2)
    # above the pads, with the two printhead caps on top and the drain that drips into them
    service_station(1.42, 2.02, -0.62, 0.12, 0.36, 0.55, drain=(1.70, -0.25),
                    caps=[(1.52, 1.68, -0.42, -0.10), (1.74, 1.92, -0.42, -0.10)])


def build_580():
    # finger notch in the front edge that opens the lid
    body(1.445, 1.535, extra_cutters=[box("c_notch", -0.37, 0.62, HY0 - 0.1, HY0 + 0.035,
                                          1.385, 1.545, rv=0.02)])
    # lighter grey lining of the finger notch that opens the lid
    finish(box("notch", -0.36, 0.61, HY0 + 0.025, HY0 + 0.04, 1.39, 1.445))
    top = 1.53
    # small icon display, the buttons around it and the power button at the front
    finish(box("lcd", -2.03, -1.77, HY0 + 0.75, HY0 + 1.08, top - 0.01, top + 0.004,
               rv=0.015, re=0.004))
    finish(box("lcd_bezel", -2.06, -1.74, HY0 + 0.72, HY0 + 1.11, top - 0.01, top + 0.0015,
               rv=0.03))
    btns = []
    for y in (HY0 + 0.50, HY0 + 0.30):
        for col in range(2):
            x = -2.02 + col * 0.13
            btns.append(box(f"b{y}{col}", x - 0.045, x + 0.045, y - 0.045, y + 0.045,
                            top - 0.01, top + 0.014, rv=0.02, re=0.008))
    finish(join("buttons", power_button(-1.745, HY0 + 0.40, top, r=0.05, ring=0.068,
                                        h=0.02, ring_h=0.011), *btns))
    finish(box("leds", -1.79, -1.74, HY0 + 0.15, HY0 + 0.17, top - 0.01, top + 0.005))
    tanks_and_pads()


def build_210():
    """HP: 434.1 x 360 x 134.5 mm. No scanner and no display: power, cancel and resume
    buttons and the status lights on the control strip."""
    body(1.205, 1.305)
    top = 1.30
    btns = [box(f"b{i}", x - 0.05, x + 0.05, HY0 + 0.52 - 0.05, HY0 + 0.52 + 0.05,
                top - 0.01, top + 0.014, rv=0.02, re=0.008)
            for i, x in enumerate((-2.02, -1.88))]
    finish(join("buttons", power_button(-1.745, HY0 + 0.40, top, r=0.05, ring=0.068,
                                        h=0.02, ring_h=0.011), *btns))
    finish(box("leds", -2.05, -1.75, HY0 + 0.78, HY0 + 0.80, top - 0.01, top + 0.005))
    tanks_and_pads()


STYLES = {"hp_smart_tank_580": build_580, "hp_smart_tank_210": build_210}
