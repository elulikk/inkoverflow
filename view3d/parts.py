"""Shared building blocks for the printer models (view3d/printers/*.py), run inside Blender.

Two layers: the primitives (box, box_x, box_y, cylinder, cut, join, finish) and the parts
that several printers have, sized by arguments: feet, rear ports, tank windows, the ink
block, the power button, a paper support, felt pads, the service station and the side
window that shows the waste-ink bay, a cartridge. A printer file only gives measurements.

Units are decimetres, Blender is Z-up and the printer front faces -Y (see make_model.py).
Each part makes the objects (meshes) the style's QML file loads by name.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

# Curves get as many segments as their size needs (a 2 mm button corner does not need the
# 10 of a 16 mm body corner): fewer triangles for slow PCs, same look. False = the counts
# exactly as asked (to compare against older meshes).
ADAPTIVE = True


def _segs(asked, radius, step, lo):
    """Segments for a curve of `radius`: one per `step` dm, between `lo` and `asked`."""
    if not ADAPTIVE:
        return asked
    return max(lo, min(asked, round(radius / step)))


# ==== primitives ====================================================================
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
        bmesh.ops.bevel(bm, geom=vertical, offset=rv, segments=_segs(seg_v, rv, 0.012, 2),
                        profile=0.5, affect='EDGES', clamp_overlap=True)
    if re > 0:
        sharp = [e for e in bm.edges
                 if len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(50)]
        bmesh.ops.bevel(bm, geom=sharp, offset=re, segments=_segs(seg_e, re, 0.008, 1),
                        profile=0.5, affect='EDGES', clamp_overlap=True)
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


def _rotated(bm, deg, axis):
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


def cylinder(name, x, y, z0, z1, r, seg=40, axis='Z'):
    """Upright cylinder at (x, y) from z0 to z1; axis='Y' lies it along Y instead, with its
    centre at (x, height y) and z0..z1 its span along Y."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=_segs(seg, r, 0.004, 12),
                          radius1=r, radius2=r, depth=z1 - z0)
    if axis == 'Y':
        _rotated(bm, 90, 'X')
        bmesh.ops.translate(bm, vec=(x, (z0 + z1) / 2, y), verts=bm.verts)
    else:
        bmesh.ops.translate(bm, vec=(x, y, (z0 + z1) / 2), verts=bm.verts)
    return obj_from_bm(name, bm)


def tilted(ob, deg, at):
    """Lean `ob` back by `deg` degrees about X, then move it to `at`."""
    ob.data.transform(Matrix.Rotation(math.radians(deg), 4, 'X'))
    ob.data.transform(Matrix.Translation(at))
    return ob


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
    return ob


# ==== shared parts ==================================================================
def feet(points, r=0.09):
    """Rubber feet under the base: `feet`."""
    finish(join("feet", *[cylinder(f"f{i}", x, y, 0.0, 0.03, r, seg=24)
                          for i, (x, y) in enumerate(points)]))


def rear_ports(usb_x, power_x, y1):
    """USB and power sockets in the back face at y1 (x = their left edge). Returns the
    cutters for the body and the dark insides to join into its `slot_inner`."""
    cutters = [box("c_usb", usb_x, usb_x + 0.12, y1 - 0.05, y1 + 0.1, 0.30, 0.38),
               box("c_pwr", power_x, power_x + 0.18, y1 - 0.05, y1 + 0.1, 0.26, 0.40, rv=0.02)]
    insides = [box("i_usb", usb_x + 0.01, usb_x + 0.11, y1 - 0.06, y1 - 0.04, 0.31, 0.37),
               box("i_pwr", power_x + 0.01, power_x + 0.17, y1 - 0.06, y1 - 0.04, 0.27, 0.39)]
    return cutters, insides


def tank_windows(centres, w, y0, z0, z1, depth=0.40, r=0.018):
    """Ink tank windows in a front face at y0, one per centre, `w` wide (or a list, one
    width each: a wider black tank): the frosted panes (`tank_windows`) and the dark back
    of each tank (`tank_cavity`). Returns the cutters that open the windows in the shell;
    the ink block (`ink_block`) is `depth` deep."""
    widths = w if isinstance(w, (list, tuple)) else [w] * len(centres)
    wins, backs, cutters = [], [], []
    for i, (c, w) in enumerate(zip(centres, widths)):
        x0, x1 = c - w / 2, c + w / 2
        cutters.append(box_y(f"c_w{i}", x0, x1, y0 - 0.2, y0 + depth + 0.06, z0, z1,
                             r=r + 0.004))
        wins.append(box_y(f"w{i}", x0 + 0.004, x1 - 0.004, y0 + 0.012, y0 + 0.022,
                          z0 + 0.004, z1 - 0.004, r=r))
        backs.append(box(f"k{i}", x0, x1, y0 + depth + 0.04, y0 + depth + 0.06, z0, z1))
    finish(join("tank_windows", *wins))
    finish(join("tank_cavity", *backs))
    return cutters


def ink_block(name, w, d, cuts=14):
    """Ink of one tank or cartridge, full height 1 with its base at the origin; the scene
    sets the level. The top is a grid so the shader can ripple it."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.translate(bm, vec=(0, 0, 0.5), verts=bm.verts)
    bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if
                                         all(v.co.z > 0.99 for v in e.verts)],
                              cuts=cuts, use_grid_fill=True)
    bmesh.ops.scale(bm, vec=(w, d, 1.0), verts=bm.verts)
    finish(obj_from_bm(name, bm), angle=60)


def power_button(x, y, z, r=0.055, ring=0.075, h=0.022, ring_h=0.012, axis='Z'):
    """Round power button with its light ring (`power_ring`); returns the button, to join
    into the style's `buttons`. axis='Z': on a top face at height z; axis='Y': on a front
    face at y, centred at height z."""
    if axis == 'Y':
        finish(cylinder("power_ring", x, z, y - ring_h, y + 0.01, ring, axis='Y'))
        return cylinder("p", x, z, y - h, y + 0.01, r, axis='Y')
    finish(cylinder("power_ring", x, y, z - 0.01, z + ring_h, ring))
    return cylinder("p", x, y, z - 0.01, z + h, r)


def paper_support(x0, x1, at, lean=-18, height=0.95, thick=0.025):
    """Rear paper support from x0 to x1, leaning back by `lean` degrees with its foot
    moved to `at` (0, y, z): `paper_support`."""
    sup = box("paper_support", x0, x1, -thick, thick, 0.0, height, re=0.012)
    finish(tilted(sup, lean, at))


def output_tray(x0, x1, y_in, y_out, z, extender=0.40, inset=0.15, stop=0.09):
    """Output tray pulled out of the front slot (`tray`): the floor from y_in (inside the
    slot) to y_out, its narrower extender `extender` further out and the paper stop at the
    end, `stop` high. z is the floor's underside."""
    finish(join("tray",
                box("t1", x0, x1, y_out, y_in, z, z + 0.03, rv=0.03, re=0.008),
                box("t2", x0 + inset, x1 - inset, y_out - extender, y_out + 0.05, z + 0.008,
                    z + 0.03, rv=0.03, re=0.006),
                box("t3", x0 + inset, x1 - inset, y_out - extender - 0.03, y_out - extender + 0.03,
                    z + 0.008, z + stop, re=0.01)))


def felt_sheets(name, bounds, n, cuts=4, bump=0.006, freq=9.0, stack='z', gap=0.004,
                inset=0.012, uneven=0.0):
    """Waste-ink felt: `n` sheets in the box `bounds` (x0, x1, y0, y1, z0, z1), stacked
    flat (stack='z', each `inset` smaller than the one under it) or standing side by side
    along X (stack='x', tops `uneven` apart). The noise makes them look like felt."""
    x0, x1, y0, y1, z0, z1 = bounds
    sheets = []
    for i in range(n):
        if stack == 'z':
            th = (z1 - z0 - gap * (n - 1)) / n
            z = z0 + i * (th + gap)
            d = inset * i
            bm = box_bm(x0 + d, x1 - d * 0.5, y0 + d * 0.6, y1 - d, z, z + th,
                        rv=0.014, re=0.012, seg_v=3, seg_e=2)
            shift = Vector((0, i * 2.7, 0))
        else:
            w = (x1 - x0 - gap * (n - 1)) / n
            sx = x0 + i * (w + gap)
            top = z1 - uneven * ((i * 7) % 3)
            bm = box_bm(sx, sx + w, y0, y1, z0, top, rv=0.012, re=0.014, seg_v=3, seg_e=2)
            shift = Vector((i * 3.1, 0, 0))
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
        for v in bm.verts:
            v.co += v.normal * bump * noise.noise(v.co * freq + shift)
        sheets.append(obj_from_bm(f"{name}{i}", bm))
    finish(join(name, *sheets), angle=70)


def pad_tub(x0, x1, y0, y1, z0, z1, lip, t=0.018, extra=()):
    """Open plastic box the felt sits in (`pad_box`); `lip` is the cutter bounds that
    lower one wall so the felt shows over it. `extra` objects are joined in."""
    tub = box("tub", x0, x1, y0, y1, z0, z1, rv=0.025, re=0.008, seg_v=6, seg_e=2)
    inner = box("c_tin", x0 + t, x1 - t, y0 + t, y1 - t, z0 + t, z1 + 0.1, rv=0.012)
    cut(tub, inner, box("c_lip", *lip))
    finish(join("pad_box", tub, *extra))


def service_station(x0, x1, y0, y1, z0, z1, caps, top_h=0.025, top_in=0.04, leg_h=0.11,
                    drain=None, cap_h=0.025, cap_r=0.025):
    """Where the carriage parks: a block with a top plate, two legs and the drain tube
    (`service_station`), and the rubber caps that seal the heads (`station_caps`, one per
    (x0, x1, y0, y1) in `caps`)."""
    dx, dy = drain if drain else ((x0 + x1) / 2, (y0 + y1) / 2)
    finish(join("service_station",
                box("s1", x0, x1, y0, y1, z0, z1, rv=0.03, re=0.01),
                box("s2", x0 + 0.05, x1 - 0.05, y0 + top_in, y1 - top_in, z1, z1 + top_h,
                    rv=0.02),
                cylinder("s3", dx, dy, z0 - leg_h + 0.02, z0 + 0.01, 0.022, seg=20),
                box("s4", x0 + 0.02, x0 + 0.06, y0 + 0.02, y1 - 0.02, z0 - leg_h, z0 + 0.01),
                box("s5", x1 - 0.06, x1 - 0.02, y0 + 0.02, y1 - 0.02, z0 - leg_h, z0 + 0.01)))
    top = z1 + top_h
    finish(join("station_caps", *[box(f"c{i}", cx0, cx1, cy0, cy1, top, top + cap_h,
                                      rv=cap_r, re=0.008)
                                  for i, (cx0, cx1, cy0, cy1) in enumerate(caps)]))


def side_pad_bay(xr, win, depth):
    """Waste-ink bay behind a see-through pane in the right side face at x = xr. `win` is
    the pane (y0, y1, z0, z1) and `depth` how far in the bay goes. Makes the dark lining
    (`pad_cavity`), the pane (`pad_window`) and its trim (`pad_trim`); returns the cutters
    that open the pane and hollow the bay in the body. The tub, felt and service station
    inside are separate parts (pad_tub, felt_sheets, service_station)."""
    y0, y1, z0, z1 = win
    bay = box("pad_cavity", xr - depth, xr - 0.03, y0 - 0.03, y1 + 0.03, z0 - 0.04, z1 + 0.03)
    inside = box("c_in", xr - depth + 0.02, xr + 0.1, y0 - 0.01, y1 + 0.01, z0 - 0.02, z1 + 0.01)
    cut(bay, inside)
    finish(bay)

    finish(box_x("pad_window", xr - 0.03, xr - 0.012, y0 + 0.004, y1 - 0.004,
                 z0 + 0.004, z1 - 0.004, r=0.036))
    trim = box_x("pad_trim", xr - 0.02, xr + 0.006, y0 - 0.02, y1 + 0.02, z0 - 0.02,
                 z1 + 0.02, r=0.05, re=0.006)
    hole = box_x("c_trim", xr - 0.1, xr + 0.1, y0 + 0.01, y1 - 0.01, z0 + 0.01, z1 - 0.01,
                 r=0.032)
    cut(trim, hole)
    finish(trim)
    return [box_x("c_padwin", xr - 0.06, xr + 0.2, y0, y1, z0, z1, r=0.04),
            box("c_bay", xr - depth - 0.005, xr - 0.025, y0 - 0.035, y1 + 0.035,
                z0 - 0.045, z1 + 0.035)]


def cartridge(w, d, h, prefix="cart"):
    """One ink cartridge standing with its base at the origin (front -Y): a see-through
    body (`<prefix>_shell`), a label on the back half of the top (`_label`), the grip tab
    at the front (`_tab`) and the ink inside (`_ink`, see ink_block)."""
    finish(box(f"{prefix}_shell", -w / 2, w / 2, -d / 2, d / 2, 0.0, h, rv=0.012, re=0.008,
               seg_v=4, seg_e=2))
    finish(box(f"{prefix}_label", -w / 2 + 0.008, w / 2 - 0.008, 0.0, d / 2 - 0.025,
               h - 0.002, h + 0.008, rv=0.01))
    finish(box(f"{prefix}_tab", -w / 2 + 0.015, w / 2 - 0.015, -d / 2 - 0.03, -d / 2 + 0.04,
               h - 0.06, h + 0.012, rv=0.01, re=0.006))
    ink_block(f"{prefix}_ink", w - 0.03, d - 0.05, cuts=8)
