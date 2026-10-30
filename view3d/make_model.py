"""Builds the 3D printers in Blender and converts them for Qt Quick 3D, one style each.

Run from the project folder (no style = all of them):
    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b -P view3d/make_model.py
    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b -P view3d/make_model.py -- hp_smart_tank_580

Styles: epson_l3150 (Epson L3150/L3250 family), hp_smart_tank_580 and epson_xp2100 (Epson
XP-2100/2101/2105, cartridges 206). Each one is written
to view3d/meshes/<style>/*.mesh through pyside6-balsam. Only the geometry comes from here:
colours, glass, ink and pads are materials in the style's QML file (EpsonL3150.qml,
HpSmartTank580.qml). Units are decimetres; the scene scales them. Blender is Z-up with the
front of the printer facing -Y; glTF turns that into Y-up with the front facing +Z.
"""
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector, noise

HERE = Path(__file__).resolve().parent
BALSAM = HERE.parent / ".venv" / "Lib" / "site-packages" / "PySide6" / "balsam.exe"

# ==== Epson L3150 family =========================================================
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


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def box_bm(x0, x1, y0, y1, z0, z1, rv=0.0, re=0.0, seg_v=10, seg_e=3):
    """A box with rounded vertical edges (radius rv) and softened top/bottom edges (re)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(x1 - x0, y1 - y0, z1 - z0), verts=bm.verts)
    bmesh.ops.translate(bm, vec=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), verts=bm.verts)
    if rv > 0:
        vertical = [e for e in bm.edges
                    if abs(e.verts[0].co.z - e.verts[1].co.z) > 1e-6]
        bmesh.ops.bevel(bm, geom=vertical, offset=rv, segments=seg_v, profile=0.5,
                        affect='EDGES', clamp_overlap=True)
    if re > 0:
        sharp = [e for e in bm.edges
                 if len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(50)]
        bmesh.ops.bevel(bm, geom=sharp, offset=re, segments=seg_e, profile=0.5,
                        affect='EDGES', clamp_overlap=True)
    return bm


def obj_from_bm(name, bm):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def box(name, *bounds, **kw):
    return obj_from_bm(name, box_bm(*bounds, **kw))


def cylinder(name, x, y, z0, z1, r, seg=40, axis='Z'):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r,
                          depth=z1 - z0)
    if axis == 'Y':
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0),
                         matrix=__import__('mathutils').Matrix.Rotation(math.radians(90), 3, 'X'))
        bmesh.ops.translate(bm, vec=(x, (z0 + z1) / 2, y), verts=bm.verts)
    else:
        bmesh.ops.translate(bm, vec=(x, y, (z0 + z1) / 2), verts=bm.verts)
    return obj_from_bm(name, bm)


def cut(target, *cutters):
    """Boolean difference, applied; the cutters are deleted."""
    for c in cutters:
        mod = target.modifiers.new("cut", 'BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.solver = 'EXACT'
        mod.object = c
        c.hide_set(True)
    bake(target)
    for c in cutters:
        bpy.data.objects.remove(c, do_unlink=True)


def bake(ob):
    """Apply every modifier of ob into its mesh."""
    deps = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(ob.evaluated_get(deps))
    old = ob.data
    ob.modifiers.clear()
    ob.data = mesh
    bpy.data.meshes.remove(old)
    mesh.name = ob.name


def join(name, *objs):
    bm = bmesh.new()
    for ob in objs:
        bm.from_mesh(ob.data)
    for ob in objs:
        bpy.data.objects.remove(ob, do_unlink=True)
    return obj_from_bm(name, bm)


def finish(ob, angle=38):
    """Smooth shading with hard edges above `angle` degrees."""
    mesh = ob.data
    for p in mesh.polygons:
        p.use_smooth = True
    try:
        mesh.set_sharp_from_angle(angle=math.radians(angle))
    except AttributeError:
        pass


# ---- the parts ------------------------------------------------------------------
def body():
    base = box("body", X0, TX, Y0, Y1, 0.02, BASE_TOP, rv=0.16, re=0.035)
    slot = box("c_slot", -1.46, 0.96, Y0 - 0.2, Y0 + 0.55, 0.17, 0.42, rv=0.03)
    door = box("c_door", DOOR[0], DOOR[1], Y1 - 0.62, Y1 + 0.2, DOOR[2], DOOR[3], rv=0.02)
    feed = box("c_feed", -1.05, 0.75, Y1 - 0.30, Y1 - 0.10, BASE_TOP - 0.06, BASE_TOP + 0.2)
    usb = box("c_usb", -0.42, -0.30, Y1 - 0.05, Y1 + 0.1, 0.30, 0.38)
    power = box("c_pwr", -0.80, -0.62, Y1 - 0.05, Y1 + 0.1, 0.26, 0.40, rv=0.02)
    cut(base, slot, door, feed, usb, power)
    finish(base)

    scan = box("scanner", X0, TX, Y0 - 0.03, Y1, BASE_TOP + 0.012, SCAN_TOP, rv=0.16, re=0.04)
    finish(scan)
    lid = box("lid", X0 + 0.03, TX - 0.03, -1.12, Y1 - 0.02, SCAN_TOP + 0.008, LID_TOP,
              rv=0.13, re=0.05)
    finish(lid)

    # front cover between the slot and the scanner, a hair proud of the body
    cover = box("front_panel", -1.50, 1.00, Y0 - 0.018, Y0 + 0.02, 0.46, 1.03, rv=0.0, re=0.012)
    finish(cover)

    # dark interior of the output slot and the feeder (seen through the openings)
    inner = join("slot_inner",
                 box("a", -1.45, 0.95, Y0 + 0.50, Y0 + 0.53, 0.18, 0.41),
                 box("b", -1.04, 0.74, Y1 - 0.31, Y1 - 0.11, BASE_TOP - 0.07, BASE_TOP - 0.05),
                 box("c", -0.41, -0.31, Y1 - 0.06, Y1 - 0.04, 0.31, 0.37),
                 box("d", -0.79, -0.63, Y1 - 0.06, Y1 - 0.04, 0.27, 0.39))
    finish(inner)

    # output tray with its extender and a small lip
    tray = join("tray",
                box("t1", -1.24, 0.74, Y0 - 0.66, Y0 + 0.3, 0.19, 0.225, rv=0.03, re=0.008),
                box("t2", -1.10, 0.60, Y0 - 1.02, Y0 - 0.60, 0.205, 0.228, rv=0.03, re=0.006),
                box("t3", -1.10, 0.60, Y0 - 1.05, Y0 - 0.99, 0.205, 0.30, re=0.01))
    finish(tray)

    # rear paper support, leaning back
    sup = box("paper_support", -0.92, 0.62, -0.025, 0.025, 0.0, 0.95, rv=0.0, re=0.012)
    sup.data.transform(__import__('mathutils').Matrix.Rotation(math.radians(-18), 4, 'X'))
    sup.data.transform(__import__('mathutils').Matrix.Translation((0, Y1 - 0.16, BASE_TOP + 0.02)))
    finish(sup)

    # feet
    feet = join("feet", *[cylinder(f"f{i}", x, y, 0.0, 0.03, 0.09, seg=24)
                          for i, (x, y) in enumerate([(-1.6, -1.1), (0.95, -1.1),
                                                      (-1.6, 1.1), (1.6, 1.1),
                                                      (1.6, -1.2)])])
    finish(feet)


def control_panel():
    y = Y0 + 0.13
    btn = join("buttons",
               cylinder("p", -1.62, y, SCAN_TOP - 0.01, SCAN_TOP + 0.022, 0.055),
               *[box(f"b{i}", -1.40 + i * 0.16, -1.30 + i * 0.16, y - 0.045, y + 0.045,
                     SCAN_TOP - 0.01, SCAN_TOP + 0.016, rv=0.02, re=0.008)
                 for i in range(5)])
    finish(btn)
    ring = cylinder("power_ring", -1.62, y, SCAN_TOP - 0.01, SCAN_TOP + 0.012, 0.075)
    finish(ring)
    leds = join("leds", *[box(f"l{i}", -1.37 + i * 0.16, -1.33 + i * 0.16, y + 0.06, y + 0.075,
                              SCAN_TOP - 0.01, SCAN_TOP + 0.006) for i in range(5)])
    finish(leds)


def tank_unit():
    unit = box("tank_unit", TX + 0.008, X1, TANK_Y0, 0.95, 0.02, TANK_TOP, rv=0.14, re=0.04)
    cx = (TX + X1) / 2
    total = 4 * WIN_W + 3 * WIN_GAP
    holes = []
    for i in range(4):
        x0 = cx - total / 2 + i * (WIN_W + WIN_GAP)
        holes.append(box(f"h{i}", x0, x0 + WIN_W, TANK_Y0 - 0.2, TANK_Y0 + LIQUID_DEPTH + 0.06,
                         WIN_Z0, WIN_Z1, rv=0.018))
    cut(unit, *holes)
    finish(unit)
    # frosted window of each tank, slightly recessed
    wins = []
    backs = []
    for i in range(4):
        x0 = cx - total / 2 + i * (WIN_W + WIN_GAP)
        wins.append(box(f"w{i}", x0 + 0.004, x0 + WIN_W - 0.004, TANK_Y0 + 0.012,
                        TANK_Y0 + 0.022, WIN_Z0 + 0.004, WIN_Z1 - 0.004, rv=0.014))
        backs.append(box(f"k{i}", x0, x0 + WIN_W, TANK_Y0 + LIQUID_DEPTH + 0.04,
                         TANK_Y0 + LIQUID_DEPTH + 0.06, WIN_Z0, WIN_Z1))
    finish(join("tank_windows", *wins))
    finish(join("tank_cavity", *backs))
    # cap cover on top of the tanks
    cap = box("tank_cap", TX + 0.06, X1 - 0.05, TANK_Y0 + 0.06, 0.40, TANK_TOP - 0.01,
              TANK_TOP + 0.035, rv=0.10, re=0.02)
    finish(cap)


def liquid(width=WIN_W, depth=LIQUID_DEPTH):
    """One tank of ink, full height 1 with its base at the origin; the scene sets the
    level. The top is a fine grid so the shader can ripple it."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.translate(bm, vec=(0, 0, 0.5), verts=bm.verts)
    bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if
                                         all(v.co.z > 0.99 for v in e.verts)],
                              cuts=14, use_grid_fill=True)
    bmesh.ops.scale(bm, vec=(width - 0.012, depth, 1.0), verts=bm.verts)
    ob = obj_from_bm("liquid", bm)
    finish(ob, angle=60)


def pads():
    """The waste-ink pads: felt sheets standing upright, side by side, in a plastic box
    that sits behind the rear door (the door is see-through in the scene)."""
    bx0, bx1 = DOOR[0] + 0.03, DOOR[1] - 0.03
    by0, by1 = Y1 - 0.58, Y1 - 0.045
    bz0, bz1 = DOOR[2] + 0.015, DOOR[3] - 0.03
    t = 0.018                                   # wall thickness
    tub = box("tub", bx0, bx1, by0, by1, bz0, bz1, rv=0.025, re=0.008, seg_v=6, seg_e=2)
    inside = box("c_in", bx0 + t, bx1 - t, by0 + t, by1 - t, bz0 + t, bz1 + 0.1, rv=0.012)
    # the wall facing the door is low, so the sheets show above it
    lip = box("c_lip", bx0 + t, bx1 - t, by1 - t - 0.01, by1 + 0.1, bz0 + 0.13, bz1 + 0.1)
    cut(tub, inside, lip)
    tab = box("tab", (bx0 + bx1) / 2 - 0.08, (bx0 + bx1) / 2 + 0.08, by1 - 0.01, by1 + 0.012,
              bz0 + 0.02, bz0 + 0.11, rv=0.01, re=0.004)
    finish(join("pad_box", tub, tab))

    n, gap = 6, 0.012
    x0, x1 = bx0 + t + 0.008, bx1 - t - 0.008
    w = (x1 - x0 - gap * (n - 1)) / n
    sheets = []
    for i in range(n):
        sx = x0 + i * (w + gap)
        top = bz1 - 0.035 - 0.012 * ((i * 7) % 3)          # uneven tops, as real felt
        bm = box_bm(sx, sx + w, by0 + t + 0.01, by1 - t - 0.012, bz0 + t, top,
                    rv=0.012, re=0.014, seg_v=3, seg_e=2)
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=3, use_grid_fill=True)
        for v in bm.verts:
            v.co += v.normal * 0.007 * noise.noise(v.co * 11.0 + Vector((i * 3.1, 0, 0)))
        sheets.append(obj_from_bm(f"pad{i}", bm))
    finish(join("pads", *sheets), angle=70)

    cav = box("pad_cavity", DOOR[0], DOOR[1], Y1 - 0.62, Y1 - 0.60, DOOR[2], DOOR[3])
    finish(cav)
    door = box("pad_door", DOOR[0] + 0.004, DOOR[1] - 0.004, Y1 - 0.025, Y1 - 0.012,
               DOOR[2] + 0.004, DOOR[3] - 0.004, rv=0.018, re=0.006)
    finish(door)
    screw = cylinder("pad_screw", DOOR[0] + 0.09, (DOOR[2] + DOOR[3]) / 2 - 0.06,
                     Y1 - 0.016, Y1 + 0.004, 0.022, seg=20, axis='Y')
    finish(screw)




def build_epson_l3150():
    body()
    control_panel()
    tank_unit()
    liquid()
    pads()


# ==== HP Smart Tank 580 ===========================================================
# HP lists 434.7 x 361.5 x 157.3 mm (W x D x H, trays closed). White body, dark grey
# scanner lid and control strip on top, the four tanks behind small windows at the
# front left, the output slot at the front right. The waste ink goes from the service
# station (right side, where the carriage parks) into felt pads lying in the base under
# it; the scene shows them through a see-through window on the right side.
HX0, HX1 = -2.173, 2.173
HY0, HY1 = -1.808, 1.808
H_BODY = 1.445                  # white body; the dark top parts sit on it
H_TOP = 1.572
H_REAR = HY1 - 0.46             # where the lid ends and the rear paper cover starts
H_SLOT = (-1.09, 1.35, 0.15, 0.69)          # output slot x0, x1, z0, z1
H_TANKS = [-1.99 + i * 0.243 for i in range(4)]   # window centres, K C M Y
H_WIN_W, H_WIN_Z0, H_WIN_Z1 = 0.13, 0.17, 0.47
H_LIQ_DEPTH = 0.40
H_PADWIN = (-0.95, 0.55, 0.10, 0.62)        # right side window y0, y1, z0, z1


def _rotated(bm, deg, axis):
    from mathutils import Matrix
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0),
                     matrix=Matrix.Rotation(math.radians(deg), 3, axis))
    return bm


def box_y(name, x0, x1, y0, y1, z0, z1, r=0.0, re=0.0, seg=8):
    """A box whose edges along Y are rounded (a plate on the front face)."""
    # built with z and y swapped, then turned 90 degrees about X: (x, y, z) -> (x, -z, y)
    bm = box_bm(x0, x1, z0, z1, -y1, -y0, rv=r, re=re, seg_v=seg, seg_e=2)
    return obj_from_bm(name, _rotated(bm, 90, 'X'))


def box_x(name, x0, x1, y0, y1, z0, z1, r=0.0, re=0.0, seg=8):
    """A box whose edges along X are rounded (a plate on a side face)."""
    # built with x and z swapped, then turned 90 degrees about Y: (x, y, z) -> (z, y, -x)
    bm = box_bm(-z1, -z0, y0, y1, x0, x1, rv=r, re=re, seg_v=seg, seg_e=2)
    return obj_from_bm(name, _rotated(bm, 90, 'Y'))


def hp_body():
    base = box("body", HX0, HX1, HY0, HY1, 0.02, H_BODY, rv=0.09, re=0.03)
    sx0, sx1, sz0, sz1 = H_SLOT
    slot = box("c_slot", sx0, sx1, HY0 - 0.2, HY0 + 0.62, sz0, sz1, rv=0.025)
    wins = [box_y(f"c_w{i}", c - H_WIN_W / 2, c + H_WIN_W / 2, HY0 - 0.2, HY0 + 0.46,
                  H_WIN_Z0, H_WIN_Z1, r=0.022) for i, c in enumerate(H_TANKS)]
    notch = box("c_notch", -0.37, 0.62, HY0 - 0.1, HY0 + 0.035, 1.385, H_BODY + 0.1, rv=0.02)
    y0, y1, z0, z1 = H_PADWIN
    padwin = box_x("c_padwin", HX1 - 0.06, HX1 + 0.2, y0, y1, z0, z1, r=0.04)
    # the body is solid: hollow out the bay behind the window (lined by pad_cavity)
    bay = box("c_bay", HX1 - 0.925, HX1 - 0.025, y0 - 0.035, y1 + 0.035, z0 - 0.045, z1 + 0.035)
    usb = box("c_usb", 0.55, 0.67, HY1 - 0.05, HY1 + 0.1, 0.30, 0.38)
    power = box("c_pwr", -1.50, -1.32, HY1 - 0.05, HY1 + 0.1, 0.26, 0.40, rv=0.02)
    cut(base, slot, *wins, notch, padwin, bay, usb, power)
    finish(base)

    # dark top: control strip on the left, scanner lid, rear paper cover
    finish(box("panel", HX0 + 0.012, -1.645, HY0 - 0.004, H_REAR - 0.012, H_BODY - 0.004, 1.53,
               rv=0.08, re=0.025))
    finish(box("lid", -1.625, HX1 - 0.012, HY0 - 0.014, H_REAR - 0.012, H_BODY + 0.006, H_TOP,
               rv=0.07, re=0.03))
    rear = box("rear_cover", HX0 + 0.012, HX1 - 0.012, H_REAR, HY1 - 0.004, H_BODY - 0.004,
               1.535, rv=0.08, re=0.025)
    groove = box("c_groove", -1.45, 1.85, H_REAR + 0.20, H_REAR + 0.225, 1.52, 1.6)
    cut(rear, groove)
    finish(rear)

    # lighter grey lining of the finger notch that opens the lid
    finish(box("notch", -0.36, 0.61, HY0 + 0.025, HY0 + 0.04, 1.39, H_BODY))

    # output slot: dark interior, the ribbed exit cover, the tray floor and its lip
    finish(join("slot_inner",
                box("a", sx0 + 0.01, sx1 - 0.01, HY0 + 0.58, HY0 + 0.61, sz0 + 0.005, sz1 - 0.005),
                box("b", 0.56, 0.66, HY1 - 0.06, HY1 - 0.04, 0.31, 0.37),
                box("c", -1.49, -1.33, HY1 - 0.06, HY1 - 0.04, 0.27, 0.39)))
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

    finish(join("feet", *[cylinder(f"f{i}", x, y, 0.0, 0.03, 0.09, seg=24)
                          for i, (x, y) in enumerate([(-1.9, -1.5), (1.9, -1.5),
                                                      (-1.9, 1.5), (1.9, 1.5)])]))


def hp_control_panel():
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
    finish(join("buttons", cylinder("p", -1.745, HY0 + 0.40, top - 0.01, top + 0.02, 0.05),
                *btns))
    finish(cylinder("power_ring", -1.745, HY0 + 0.40, top - 0.01, top + 0.011, 0.068))
    finish(box("leds", -1.79, -1.74, HY0 + 0.15, HY0 + 0.17, top - 0.01, top + 0.005))


def hp_tanks():
    wins, backs = [], []
    for i, c in enumerate(H_TANKS):
        x0, x1 = c - H_WIN_W / 2, c + H_WIN_W / 2
        wins.append(box_y(f"w{i}", x0 + 0.004, x1 - 0.004, HY0 + 0.012, HY0 + 0.022,
                          H_WIN_Z0 + 0.004, H_WIN_Z1 - 0.004, r=0.018))
        backs.append(box(f"k{i}", x0, x1, HY0 + 0.44, HY0 + 0.46, H_WIN_Z0, H_WIN_Z1))
    finish(join("tank_windows", *wins))
    finish(join("tank_cavity", *backs))
    liquid(H_WIN_W, H_LIQ_DEPTH)


def hp_pads():
    """Service station (right, under the carriage's parking place) and the felt pads it
    drains into, lying flat in a tray in the base."""
    y0, y1, z0, z1 = H_PADWIN
    # dark bay behind the side window, open towards the window
    bay = box("pad_cavity", HX1 - 0.92, HX1 - 0.03, y0 - 0.03, y1 + 0.03, z0 - 0.04, z1 + 0.03)
    inside = box("c_in", HX1 - 0.90, HX1 + 0.1, y0 - 0.01, y1 + 0.01, z0 - 0.02, z1 + 0.01)
    cut(bay, inside)
    finish(bay)

    bx0, bx1, by0, by1, bz0, bz1 = 1.32, 2.09, y0 + 0.05, y1 - 0.05, z0 - 0.015, z0 + 0.15
    t = 0.018
    tub = box("tub", bx0, bx1, by0, by1, bz0, bz1, rv=0.025, re=0.008, seg_v=6, seg_e=2)
    inner = box("c_tin", bx0 + t, bx1 - t, by0 + t, by1 - t, bz0 + t, bz1 + 0.1, rv=0.012)
    lip = box("c_lip", bx1 - t - 0.01, bx1 + 0.1, by0 + t, by1 - t, bz0 + 0.07, bz1 + 0.1)
    cut(tub, inner, lip)
    finish(join("pad_box", tub))

    sheets = []
    th = 0.042
    for i in range(3):
        z = bz0 + t + i * (th + 0.004)
        inset = 0.012 * i
        bm = box_bm(bx0 + t + 0.01 + inset, bx1 - t - 0.012 - inset * 0.5,
                    by0 + t + 0.01 + inset * 0.6, by1 - t - 0.012 - inset,
                    z, z + th, rv=0.014, re=0.012, seg_v=3, seg_e=2)
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=4, use_grid_fill=True)
        for v in bm.verts:
            v.co += v.normal * 0.006 * noise.noise(v.co * 9.0 + Vector((0, i * 2.7, 0)))
        sheets.append(obj_from_bm(f"pad{i}", bm))
    finish(join("pads", *sheets), angle=70)

    # the service station sits above the pads, with the two printhead caps on top and
    # the drain that drips into the felt
    finish(join("service_station",
                box("s1", 1.42, 2.02, -0.62, 0.12, 0.36, 0.55, rv=0.03, re=0.01),
                box("s2", 1.47, 1.97, -0.58, 0.08, 0.55, 0.575, rv=0.02),
                cylinder("s3", 1.70, -0.25, 0.27, 0.37, 0.022, seg=20),
                box("s4", 1.44, 1.48, -0.60, 0.10, 0.25, 0.37),
                box("s5", 1.96, 2.00, -0.60, 0.10, 0.25, 0.37)))
    finish(join("station_caps",
                box("c1", 1.52, 1.68, -0.42, -0.10, 0.575, 0.60, rv=0.025, re=0.008),
                box("c2", 1.74, 1.92, -0.42, -0.10, 0.575, 0.60, rv=0.025, re=0.008)))

    # see-through pane in the side, with a thin dark trim
    finish(box_x("pad_window", HX1 - 0.03, HX1 - 0.012, y0 + 0.004, y1 - 0.004,
                 z0 + 0.004, z1 - 0.004, r=0.036))
    trim = box_x("pad_trim", HX1 - 0.02, HX1 + 0.006, y0 - 0.02, y1 + 0.02, z0 - 0.02,
                 z1 + 0.02, r=0.05, re=0.006)
    hole = box_x("c_trim", HX1 - 0.1, HX1 + 0.1, y0 + 0.01, y1 - 0.01, z0 + 0.01, z1 - 0.01,
                 r=0.032)
    cut(trim, hole)
    finish(trim)


def build_hp_smart_tank_580():
    hp_body()
    hp_control_panel()
    hp_tanks()
    hp_pads()


# ==== HP Smart Tank 210 / 220 ======================================================
# Same footprint as the 580 (HP: 434.1 x 360 x 134.5 mm) but a print-only machine: no
# scanner lid and no display. A dark top cover, a small control strip at the front left
# (power, cancel, resume, status lights), the tanks and the waste-ink bay as in the 580.
H2_BODY = 1.205                 # white body; the dark top parts sit on it
H2_TOP = 1.345


def hp210_body():
    base = box("body", HX0, HX1, HY0, HY1, 0.02, H2_BODY, rv=0.09, re=0.03)
    sx0, sx1, sz0, sz1 = H_SLOT
    slot = box("c_slot", sx0, sx1, HY0 - 0.2, HY0 + 0.62, sz0, sz1, rv=0.025)
    wins = [box_y(f"c_w{i}", c - H_WIN_W / 2, c + H_WIN_W / 2, HY0 - 0.2, HY0 + 0.46,
                  H_WIN_Z0, H_WIN_Z1, r=0.022) for i, c in enumerate(H_TANKS)]
    y0, y1, z0, z1 = H_PADWIN
    padwin = box_x("c_padwin", HX1 - 0.06, HX1 + 0.2, y0, y1, z0, z1, r=0.04)
    bay = box("c_bay", HX1 - 0.925, HX1 - 0.025, y0 - 0.035, y1 + 0.035, z0 - 0.045, z1 + 0.035)
    usb = box("c_usb", 0.55, 0.67, HY1 - 0.05, HY1 + 0.1, 0.30, 0.38)
    power = box("c_pwr", -1.50, -1.32, HY1 - 0.05, HY1 + 0.1, 0.26, 0.40, rv=0.02)
    cut(base, slot, *wins, padwin, bay, usb, power)
    finish(base)

    # dark top: the control strip (left) and one flat cover over the mechanism
    finish(box("panel", HX0 + 0.012, -1.645, HY0 - 0.004, H_REAR - 0.012, H2_BODY - 0.004, 1.30,
               rv=0.08, re=0.025))
    finish(box("lid", -1.625, HX1 - 0.012, HY0 - 0.014, H_REAR - 0.012, H2_BODY + 0.006, H2_TOP,
               rv=0.07, re=0.03))
    rear = box("rear_cover", HX0 + 0.012, HX1 - 0.012, H_REAR, HY1 - 0.004, H2_BODY - 0.004,
               1.305, rv=0.08, re=0.025)
    groove = box("c_groove", -1.45, 1.85, H_REAR + 0.20, H_REAR + 0.225, 1.29, 1.4)
    cut(rear, groove)
    finish(rear)

    finish(join("slot_inner",
                box("a", sx0 + 0.01, sx1 - 0.01, HY0 + 0.58, HY0 + 0.61, sz0 + 0.005, sz1 - 0.005),
                box("b", 0.56, 0.66, HY1 - 0.06, HY1 - 0.04, 0.31, 0.37),
                box("c", -1.49, -1.33, HY1 - 0.06, HY1 - 0.04, 0.27, 0.39)))
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

    finish(cylinder("logo", 0.073, 1.10, HY0 - 0.008, HY0 + 0.01, 0.163, seg=64, axis='Y'))
    finish(box_y("label_plate", 1.40, 2.03, HY0 - 0.005, HY0 + 0.01, 0.15, 0.28, r=0.02))
    finish(join("tank_tabs", *[box_y(f"g{i}", c - 0.06, c + 0.06, HY0 - 0.004, HY0 + 0.01,
                                     0.50, 0.61, r=0.015) for i, c in enumerate(H_TANKS)]))
    finish(join("feet", *[cylinder(f"f{i}", x, y, 0.0, 0.03, 0.09, seg=24)
                          for i, (x, y) in enumerate([(-1.9, -1.5), (1.9, -1.5),
                                                      (-1.9, 1.5), (1.9, 1.5)])]))


def hp210_control_panel():
    top = 1.30
    # no display: power button with its ring, cancel and resume buttons, status lights
    btns = [box(f"b{i}", x - 0.05, x + 0.05, HY0 + 0.52 - 0.05, HY0 + 0.52 + 0.05,
                top - 0.01, top + 0.014, rv=0.02, re=0.008)
            for i, x in enumerate((-2.02, -1.88))]
    finish(join("buttons", cylinder("p", -1.745, HY0 + 0.40, top - 0.01, top + 0.02, 0.05),
                *btns))
    finish(cylinder("power_ring", -1.745, HY0 + 0.40, top - 0.01, top + 0.011, 0.068))
    finish(box("leds", -2.05, -1.75, HY0 + 0.78, HY0 + 0.80, top - 0.01, top + 0.005))


def build_hp_smart_tank_210():
    hp210_body()
    hp210_control_panel()
    hp_tanks()
    hp_pads()


# ==== Epson XP-2100 family (XP-2100 / XP-2101 / XP-2105) =========================
# Epson lists 375 x 300 x 145 mm (W x D x H, trays closed). All black: a glossy front
# strip with the buttons and the EPSON logo, the output slot under it, the scanner unit
# on top and the rear paper support standing up at the back. No tanks: four separate
# cartridges (Epson 206: K, C, M, Y) ride in the print carriage under the scanner unit,
# which hinges up at the back to reach them (the scene opens it). The waste ink goes from
# the service station (right, where the carriage parks) into felt pads lying in the base;
# like the HP, the scene shows them through a see-through pane on the right side.
XX0, XX1 = -1.875, 1.875
XY0, XY1 = -1.50, 1.50
X_BODY = 0.92                   # printer body
X_SCAN = 1.36                   # scanner unit
X_LID = 1.45                    # document lid
X_REAR = XY1 - 0.34             # where the scanner unit ends and the rear feeder starts
X_SLOT = (-1.40, 1.10, 0.10, 0.44)          # output slot x0, x1, z0, z1
X_PANEL = (-1.72, 1.72, 0.50, 0.88)         # glossy front strip x0, x1, z0, z1
X_PADWIN = (-0.85, 0.60, 0.08, 0.46)        # right side window y0, y1, z0, z1


def xp_body():
    base = box("body", XX0, XX1, XY0, XY1, 0.02, X_BODY, rv=0.10, re=0.03)
    sx0, sx1, sz0, sz1 = X_SLOT
    slot = box("c_slot", sx0, sx1, XY0 - 0.2, XY0 + 0.60, sz0, sz1, rv=0.03)
    # the strip sits in a shallow recess, so it reads as a separate glossy part
    px0, px1, pz0, pz1 = X_PANEL
    recess = box("c_panel", px0, px1, XY0 - 0.2, XY0 + 0.02, pz0, pz1, rv=0.04)
    y0, y1, z0, z1 = X_PADWIN
    padwin = box_x("c_padwin", XX1 - 0.06, XX1 + 0.2, y0, y1, z0, z1, r=0.04)
    bay = box("c_bay", XX1 - 0.88, XX1 - 0.025, y0 - 0.035, y1 + 0.035, z0 - 0.045, z1 + 0.035)
    usb = box("c_usb", 0.40, 0.52, XY1 - 0.05, XY1 + 0.1, 0.30, 0.38)
    power = box("c_pwr", -1.30, -1.12, XY1 - 0.05, XY1 + 0.1, 0.26, 0.40, rv=0.02)
    # open top under the scanner unit, where the carriage and the cartridges run
    well = box("c_well", XX0 + 0.10, XX1 - 0.10, XY0 + 0.20, X_REAR - 0.05, 0.30,
               X_BODY + 0.1, rv=0.05)
    cut(base, slot, recess, padwin, bay, usb, power, well)
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
    feed = box("c_feed", -1.25, 0.95, X_REAR + 0.10, X_REAR + 0.20, X_SCAN - 0.20, X_SCAN + 0.1)
    cut(rear, feed)
    finish(rear)
    sup = box("paper_support", -1.20, 0.90, -0.022, 0.022, 0.0, 1.05, re=0.012)
    sup.data.transform(__import__('mathutils').Matrix.Rotation(math.radians(-14), 4, 'X'))
    sup.data.transform(__import__('mathutils').Matrix.Translation((0, X_REAR + 0.24, X_SCAN - 0.20)))
    finish(sup)
    finish(box("paper_guide", -1.20, -1.10, X_REAR + 0.11, X_REAR + 0.19, X_SCAN - 0.22,
               X_SCAN - 0.04, re=0.008))

    # dark interior seen through the openings
    finish(join("slot_inner",
                box("a", sx0 + 0.01, sx1 - 0.01, XY0 + 0.56, XY0 + 0.59, sz0 + 0.005, sz1 - 0.005),
                box("b", -1.24, 0.94, X_REAR + 0.10, X_REAR + 0.20, X_SCAN - 0.21, X_SCAN - 0.19),
                box("c", 0.41, 0.51, XY1 - 0.06, XY1 - 0.04, 0.31, 0.37),
                box("d", -1.29, -1.13, XY1 - 0.06, XY1 - 0.04, 0.27, 0.39)))

    # output tray pulled out of the slot, with its extender and the paper stop
    finish(join("tray",
                box("t1", -1.10, 0.80, XY0 - 0.55, XY0 + 0.50, sz0, sz0 + 0.03, rv=0.03, re=0.008),
                box("t2", -0.95, 0.65, XY0 - 0.95, XY0 - 0.50, sz0 + 0.01, sz0 + 0.032,
                    rv=0.03, re=0.006),
                box("t3", -0.95, 0.65, XY0 - 0.98, XY0 - 0.92, sz0 + 0.01, sz0 + 0.10, re=0.01)))

    finish(join("feet", *[cylinder(f"f{i}", x, y, 0.0, 0.03, 0.09, seg=24)
                          for i, (x, y) in enumerate([(-1.6, -1.2), (1.6, -1.2),
                                                      (-1.6, 1.2), (1.6, 1.2)])]))


def xp_control_panel():
    """Buttons on the glossy front strip: power (with its ring light) on the left, the
    Wi-Fi and status lights, then the Wi-Fi, copy and stop buttons."""
    y = XY0 - 0.012
    z = 0.69
    finish(cylinder("power_ring", -1.45, z, y - 0.012, y + 0.01, 0.075, axis='Y'))
    btns = [cylinder("p", -1.45, z, y - 0.022, y + 0.01, 0.055, axis='Y')]
    for i, x in enumerate((-0.62, -0.40, -0.12, 0.10)):
        btns.append(cylinder(f"b{i}", x, z, y - 0.018, y + 0.01, 0.050, axis='Y'))
    finish(join("buttons", *btns))
    # Wi-Fi and status lights, then the ink light on its own (it blinks for a low cartridge)
    leds = [box_y(f"l{i}", -1.17, -1.13, y - 0.014, y + 0.01, zz - 0.02, zz + 0.02, r=0.01)
            for i, zz in enumerate((0.77, 0.69))]
    finish(join("leds", *leds))
    finish(box_y("ink_led", -1.17, -1.13, y - 0.014, y + 0.01, 0.59, 0.63, r=0.01))


def xp_cartridge_bay():
    """Floor and back wall of the well the carriage runs in, under the scanner unit."""
    finish(join("bay",
                box("f", XX0 + 0.10, 1.05, XY0 + 0.20, X_REAR - 0.05, 0.28, 0.30),
                box("w", XX0 + 0.10, XX1 - 0.10, X_REAR - 0.07, X_REAR - 0.05, 0.28, X_BODY)))


def xp_pads():
    """Service station (right, under the carriage's parking place) and the felt pads in
    the base under it, seen through a pane in the right side."""
    y0, y1, z0, z1 = X_PADWIN
    bay = box("pad_cavity", XX1 - 0.87, XX1 - 0.03, y0 - 0.03, y1 + 0.03, z0 - 0.04, z1 + 0.03)
    inside = box("c_in", XX1 - 0.85, XX1 + 0.1, y0 - 0.01, y1 + 0.01, z0 - 0.02, z1 + 0.01)
    cut(bay, inside)
    finish(bay)

    bx0, bx1, by0, by1, bz0, bz1 = 1.08, 1.80, y0 + 0.05, y1 - 0.05, z0 - 0.015, z0 + 0.14
    t = 0.018
    tub = box("tub", bx0, bx1, by0, by1, bz0, bz1, rv=0.025, re=0.008, seg_v=6, seg_e=2)
    inner = box("c_tin", bx0 + t, bx1 - t, by0 + t, by1 - t, bz0 + t, bz1 + 0.1, rv=0.012)
    lip = box("c_lip", bx1 - t - 0.01, bx1 + 0.1, by0 + t, by1 - t, bz0 + 0.07, bz1 + 0.1)
    cut(tub, inner, lip)
    finish(join("pad_box", tub))

    sheets = []
    th = 0.040
    for i in range(3):
        z = bz0 + t + i * (th + 0.004)
        inset = 0.012 * i
        bm = box_bm(bx0 + t + 0.01 + inset, bx1 - t - 0.012 - inset * 0.5,
                    by0 + t + 0.01 + inset * 0.6, by1 - t - 0.012 - inset,
                    z, z + th, rv=0.014, re=0.012, seg_v=3, seg_e=2)
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=4, use_grid_fill=True)
        for v in bm.verts:
            v.co += v.normal * 0.006 * noise.noise(v.co * 9.0 + Vector((0, i * 2.7, 0)))
        sheets.append(obj_from_bm(f"pad{i}", bm))
    finish(join("pads", *sheets), angle=70)

    # service station above the pads: one cap for the black and colour heads, the drain
    finish(join("service_station",
                box("s1", 1.12, 1.62, -0.45, 0.30, 0.25, 0.34, rv=0.03, re=0.01),
                box("s2", 1.17, 1.57, -0.40, 0.25, 0.34, 0.355, rv=0.02),
                cylinder("s3", 1.37, -0.08, 0.20, 0.26, 0.022, seg=20),
                box("s4", 1.14, 1.18, -0.43, 0.28, 0.20, 0.26),
                box("s5", 1.56, 1.60, -0.43, 0.28, 0.20, 0.26)))
    finish(box("station_caps", 1.22, 1.52, -0.30, 0.12, 0.355, 0.375, rv=0.03, re=0.008))

    finish(box_x("pad_window", XX1 - 0.03, XX1 - 0.012, y0 + 0.004, y1 - 0.004,
                 z0 + 0.004, z1 - 0.004, r=0.036))
    trim = box_x("pad_trim", XX1 - 0.02, XX1 + 0.006, y0 - 0.02, y1 + 0.02, z0 - 0.02,
                 z1 + 0.02, r=0.05, re=0.006)
    hole = box_x("c_trim", XX1 - 0.1, XX1 + 0.1, y0 + 0.01, y1 - 0.01, z0 + 0.01, z1 - 0.01,
                 r=0.032)
    cut(trim, hole)
    finish(trim)


def xp_cartridge():
    """One Epson 206 cartridge, standing with its base at the origin (front -Y): a
    see-through body (the scene puts the ink inside it), a label on the back half of the
    top and the grip tab at the front. The scene places four of them in the carriage."""
    w, d, h = 0.118, 0.44, 0.40
    finish(box("cart_shell", -w / 2, w / 2, -d / 2, d / 2, 0.0, h, rv=0.012, re=0.008,
               seg_v=4, seg_e=2))
    finish(box("cart_label", -w / 2 + 0.008, w / 2 - 0.008, 0.0, d / 2 - 0.025,
               h - 0.002, h + 0.008, rv=0.01))
    finish(box("cart_tab", -w / 2 + 0.015, w / 2 - 0.015, -d / 2 - 0.03, -d / 2 + 0.04,
               h - 0.06, h + 0.012, rv=0.01, re=0.006))
    # the ink inside: full height 1, base at the origin; the scene sets the level
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.translate(bm, vec=(0, 0, 0.5), verts=bm.verts)
    bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if
                                         all(v.co.z > 0.99 for v in e.verts)],
                              cuts=8, use_grid_fill=True)
    bmesh.ops.scale(bm, vec=(w - 0.03, d - 0.05, 1.0), verts=bm.verts)
    finish(obj_from_bm("cart_ink", bm), angle=60)


def build_epson_xp2100():
    xp_body()
    xp_control_panel()
    xp_cartridge_bay()
    xp_pads()
    xp_cartridge()


STYLES = {"epson_l3150": build_epson_l3150, "hp_smart_tank_580": build_hp_smart_tank_580,
          "hp_smart_tank_210": build_hp_smart_tank_210,
          "epson_xp2100": build_epson_xp2100}


def export(style):
    """Build one style and write view3d/meshes/<style>/*.mesh."""
    clear()
    STYLES[style]()
    glb = HERE / f"{style}.glb"
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB', export_yup=True,
                              export_normals=True, export_materials='NONE',
                              export_apply=True)
    print("written", glb)
    if not BALSAM.is_file():
        print("balsam.exe not found; run it on", glb.name, "by hand")
        return
    # balsam writes <out>/meshes/*.mesh plus a generic QML file we do not use
    tmp = HERE / f"_build_{style}"
    shutil.rmtree(tmp, ignore_errors=True)
    subprocess.run([str(BALSAM), "-o", str(tmp), str(glb)], check=True)
    dest = HERE / "meshes" / style
    shutil.rmtree(dest, ignore_errors=True)
    shutil.move(str(tmp / "meshes"), str(dest))
    shutil.rmtree(tmp, ignore_errors=True)
    glb.unlink()
    print("meshes ->", dest)


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for style in args or list(STYLES):
        if style not in STYLES:
            raise SystemExit(f"unknown style {style!r}; known: {', '.join(STYLES)}")
        export(style)


main()
