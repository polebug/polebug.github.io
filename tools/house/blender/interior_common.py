"""Shared pieces for the stage-3 interior scripts (one script per floor).

Call setup(floor, collection, whitebox_collection) first: it clears the whitebox and any previous
build of that floor and defines A (asset factory), Z (floor level), CEIL and rng for the helpers.
"""
import bpy, math, random, os, sys
from mathutils import Vector, Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from house_spec import *   # noqa: E402,F403
from meshkit import Asset  # noqa: E402

P = PALETTE = {
    "table": (0.80, 0.58, 0.37), "chair": (0.68, 0.46, 0.28), "cab": (0.62, 0.46, 0.31),
    "worktop": (0.82, 0.64, 0.43), "enamel": (0.20, 0.33, 0.56), "iron": (0.13, 0.13, 0.14),
    "chrome": (0.82, 0.84, 0.86), "ceramic": (0.95, 0.94, 0.90), "tile": (0.93, 0.88, 0.76),
    "grout": (0.74, 0.71, 0.65), "glass": (0.70, 0.86, 0.88), "linen": (0.96, 0.93, 0.85),
    "rug": (0.88, 0.82, 0.68), "rug_band": (0.72, 0.36, 0.28), "leaf": (0.36, 0.58, 0.30),
    "leaf_dark": (0.26, 0.46, 0.26), "stem": (0.40, 0.52, 0.28), "flower_y": (0.98, 0.82, 0.26),
    "flower_w": (0.97, 0.96, 0.92), "terracotta": (0.80, 0.47, 0.33), "soil": (0.30, 0.22, 0.16),
    "brass": (0.80, 0.62, 0.30), "bulb": (1.0, 0.92, 0.62), "apple": (0.80, 0.22, 0.16),
    "orange": (0.95, 0.56, 0.16), "pear": (0.76, 0.80, 0.32), "copper": (0.78, 0.46, 0.28),
    "cork": (0.70, 0.55, 0.38), "bamboo": (0.78, 0.68, 0.45), "shade": (0.92, 0.78, 0.56),
    "jar_lid": (0.55, 0.42, 0.30), "crock": (0.86, 0.80, 0.68), "board": (0.74, 0.54, 0.34),
}

P.update({
    "soot": (0.18, 0.15, 0.13), "stone_a": (0.72, 0.71, 0.70), "stone_b": (0.63, 0.63, 0.65),
    "stone_c": (0.78, 0.75, 0.70), "fire": (1.0, 0.55, 0.15), "fire_core": (1.0, 0.86, 0.42),
    "log": (0.45, 0.30, 0.18), "log_end": (0.80, 0.66, 0.46), "mantel": (0.50, 0.33, 0.20),
    "fabric_green": (0.50, 0.63, 0.38), "fabric_green_dk": (0.42, 0.54, 0.32), "plaid": (0.74, 0.26, 0.22),
    "plaid_line": (0.95, 0.80, 0.45), "cushion_o": (0.96, 0.52, 0.24), "dot": (0.99, 0.94, 0.84),
    "cushion_red": (0.76, 0.24, 0.21), "wicker": (0.74, 0.58, 0.36), "alu": (0.80, 0.81, 0.82),
    "screen": (0.10, 0.12, 0.16), "key": (0.93, 0.93, 0.91), "paper": (0.97, 0.95, 0.89),
    "b1": (0.30, 0.45, 0.62), "b2": (0.70, 0.30, 0.25), "b3": (0.40, 0.55, 0.38), "b4": (0.85, 0.70, 0.40),
    "b5": (0.55, 0.42, 0.60), "b6": (0.88, 0.85, 0.78),
    "b7": (0.28, 0.40, 0.33), "b8": (0.52, 0.36, 0.26), "b9": (0.35, 0.58, 0.60), "b10": (0.80, 0.62, 0.30),
    "b11": (0.24, 0.30, 0.45),
})
P.update({"cushion_cream": (0.92, 0.88, 0.80), "lamp_cream": (0.95, 0.90, 0.80), "cushion_grey": (0.48, 0.48, 0.46), "rocker_wood": (0.78, 0.55, 0.32), "velvet": (0.52, 0.27, 0.13), "brass_lamp": (0.85, 0.66, 0.32), "walnut": (0.40, 0.22, 0.13), "leather_tan": (0.62, 0.30, 0.14), "leather_dk": (0.26, 0.11, 0.05), "leather_tan_top": (0.62, 0.30, 0.14), "cane": (0.80, 0.62, 0.36), "steel": (0.80, 0.80, 0.80), "rock_wood": (0.55, 0.28, 0.15), "cushion_navy": (0.13, 0.20, 0.36), "cushion_rust": (0.48, 0.15, 0.10),
          "charred": (0.035, 0.03, 0.028), "crack": (0.005, 0.005, 0.005), "jute": (0.95, 0.84, 0.67), "leather_green": (0.30, 0.34, 0.16), "leather_green_top": (0.30, 0.34, 0.16), "leather_green_dk": (0.18, 0.21, 0.09), "leather_taupe": (0.40, 0.34, 0.28),
          "glide": (0.25, 0.45, 0.50), "blind": (0.78, 0.46, 0.20), "tape": (0.86, 0.80, 0.68), "gauze": (0.97, 0.97, 0.96)})
BOOKS = ["b1", "b2", "b3", "b4", "b5", "b6"]

A = Z = CEIL = COL = PREFIX = None
rng = random.Random(0)


def setup(floor, collection, whitebox_collection, seed):
    global A, Z, CEIL, COL, PREFIX, rng
    sc = bpy.context.scene
    for cn in (whitebox_collection, collection):
        c = bpy.data.collections.get(cn)
        if c:
            for o in list(c.all_objects):
                bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.collections.remove(c)
    for m in list(bpy.data.meshes):
        if m.users == 0:
            bpy.data.meshes.remove(m)
    COL = bpy.data.collections.new(collection)
    sc.collection.children.link(COL)
    Z = FLOOR[floor]
    CEIL = FLOOR[floor + 1] - SLAB if floor < 3 else None
    PREFIX = f"F{floor} "
    rng = random.Random(seed)

    def factory(name, loc, rz=0.0):
        return Asset(PREFIX + name, COL, P, (loc[0], loc[1], loc[2] if len(loc) > 2 else Z), rz)
    A = factory
    return A


def finish(tag):
    bpy.ops.wm.save_mainfile()
    objs = list(COL.objects)
    print(tag, len([o for o in objs if o.type == 'EMPTY']), "assets",
          sum(len(o.data.vertices) for o in objs if o.type == 'MESH'), "verts")

def ladder_chair(name, x, y, rz):
    a = A(name, (x, y), rz)
    w = a.m("chair", bevel=0.005)
    S, D, SH, BH = 0.48, 0.46, 0.44, 0.98
    for sx in (-1, 1):
        w.beam((sx * 0.2, -0.19, 0), (sx * 0.2, -0.19, SH - 0.03), 0.032, 0.032, w2=0.042, h2=0.042)  # front legs
        w.beam((sx * 0.2, 0.19, 0), (sx * 0.2, 0.235, BH), 0.036, 0.036, w2=0.042, h2=0.042)          # back posts
        w.rod((sx * 0.2, -0.19, 0.14), (sx * 0.2, 0.19, 0.14), 0.011)                                  # side stretchers
        w.lathe([(0, 0), (0.024, 0), (0.026, 0.02), (0.012, 0.045), (0, 0.05)], (sx * 0.2, 0.235, BH))   # finials
    w.rod((-0.2, -0.19, 0.2), (0.2, -0.19, 0.2), 0.011)
    w.rod((-0.2, 0.19, 0.12), (0.2, 0.19, 0.12), 0.011)
    for zz in (0.62, 0.76, 0.90):                                                                       # ladder slats
        yy = 0.19 + 0.045 * (zz / BH) + 0.003
        prof = [(-0.2, yy), (-0.1, yy + 0.012), (0.0, yy + 0.016), (0.1, yy + 0.012), (0.2, yy)]
        w.solid([(px, py - 0.009, zz - 0.03) for px, py in prof] + [(px, py + 0.009, zz - 0.03) for px, py in prof[::-1]],
                [(px, py - 0.009, zz + 0.03) for px, py in prof] + [(px, py + 0.009, zz + 0.03) for px, py in prof[::-1]])
    seat = a.m("cork", bevel=0.012, segments=3)                                                        # rush-style seat
    seat.box(-S / 2 + 0.015, S / 2 - 0.015, -D / 2 + 0.01, D / 2 - 0.02, SH - 0.035, SH)
    a.build()

def vase_with_flowers(name, loc, h0, flower="flower_y", n=7):
    a = A(name, (loc[0], loc[1], h0))
    a.m("ceramic", smooth=True).lathe([(0, 0), (0.05, 0), (0.07, 0.06), (0.066, 0.13), (0.036, 0.185),
                                       (0.042, 0.215), (0.034, 0.215), (0, 0.2)], seg=24)
    st, lf, fl, ce = a.m("stem"), a.m("leaf", smooth=True), a.m(flower, smooth=True), a.m("flower_y", smooth=True)
    for k in range(n):
        t = 2 * math.pi * k / n + rng.uniform(-0.3, 0.3)
        lean = rng.uniform(0.15, 0.35)
        top = Vector((math.cos(t) * lean * 0.5, math.sin(t) * lean * 0.5, 0.2 + rng.uniform(0.18, 0.3)))
        st.rod((0, 0, 0.12), top, 0.004, seg=5)
        for p in range(5):                                     # five petals round a centre
            pt = 2 * math.pi * p / 5
            off = Vector((math.cos(pt), math.sin(pt), 0)) * 0.022
            fl.ellipsoid(top + off, (0.022, 0.012, 0.005), seg=8, rings=4, rot=Matrix.Rotation(pt, 3, 'Z'))
        ce.ellipsoid(top + Vector((0, 0, 0.004)), (0.01, 0.01, 0.008), seg=8, rings=4)
        mid = top * 0.6 + Vector((0, 0, 0.12)) * 0.4
        lf.ellipsoid(mid, (0.04, 0.012, 0.004), seg=8, rings=4, rot=Matrix.Rotation(t + 0.6, 3, 'Z') @ Matrix.Rotation(0.5, 3, 'Y'))
    a.build()

def curtains(x0, x1, sill, head, wall_y, name, hem=None):
    a = A(name, (0, 0, Z))
    rod_z, bottom = head + 0.17, (sill - 0.2 if hem is None else hem)
    cloth = a.m("linen", solidify=0.008, smooth=True)
    for side in (-1, 1):
        outer = (x0 - 0.3) if side < 0 else (x1 + 0.3)
        inward = 1 if side < 0 else -1
        def fn(u, v, outer=outer, inward=inward):
            t = v                                      # 0 at the rod, 1 at the hem
            pinch = 1 - 0.68 * math.exp(-((t - 0.55) / 0.12) ** 2)
            width = 0.46 * pinch * (1 + 0.15 * t)
            amp = 0.018 + 0.03 * (1 - pinch)
            x = outer + inward * u * width
            y = wall_y - 0.1 - amp * (0.5 + 0.5 * math.sin(2 * math.pi * 4.5 * u))
            z = rod_z - 0.03 - t * (rod_z - 0.03 - bottom)
            return (x, y, z)
        cloth.surface(fn, 28, 30)
        tz = rod_z - 0.03 - 0.55 * (rod_z - 0.03 - bottom)
        cx = outer + inward * 0.46 * 0.32 * 0.5
        a.m("rug_band", bevel=0.004).box(cx - 0.1, cx + 0.1, wall_y - 0.15, wall_y - 0.06, tz - 0.025, tz + 0.025)
    r = a.m("iron")
    r.rod((x0 - 0.42, wall_y - 0.1, rod_z), (x1 + 0.42, wall_y - 0.1, rod_z), 0.012, seg=10)
    for x in (x0 - 0.42, x1 + 0.42):
        r.ellipsoid((x + (-0.025 if x < x0 else 0.025), wall_y - 0.1, rod_z), (0.025, 0.025, 0.025), seg=10, rings=6)
    for x in (x0 - 0.3, x1 + 0.3):
        r.box(x - 0.012, x + 0.012, wall_y - 0.11, wall_y, rod_z - 0.01, rod_z + 0.01)
        r.box(x - 0.025, x + 0.025, wall_y - 0.008, wall_y, rod_z - 0.04, rod_z + 0.04)
    for x in (x0 - 0.3, x1 + 0.3):                      # tie-back hooks on the wall
        r.rod((x, wall_y, 1.2), (x, wall_y - 0.06, 1.2), 0.006, seg=6)
    a.build()

def shelf(name, cx, z, w, items, d=0.22):
    a = A(name, (cx, DEPTH, Z + z))
    b = a.m("board", bevel=0.004)
    b.box(-w / 2, w / 2, -d, 0, 0, 0.025)
    for s in (-1, 1):                                   # triangular brackets, near the ends, clear of the jars
        x = s * (w / 2 - 0.03)
        b.solid([(x - 0.012, -0.003, -0.002), (x - 0.012, -d + 0.03, -0.002), (x - 0.012, -0.003, -0.17)],
                [(x + 0.012, -0.003, -0.002), (x + 0.012, -d + 0.03, -0.002), (x + 0.012, -0.003, -0.17)])
    for i, kind in enumerate(items):
        x = -w / 2 + (i + 0.5) * w / len(items)
        y = -d / 2 + 0.01
        h = rng.uniform(0.12, 0.18)
        if kind == "jar":
            r = rng.uniform(0.04, 0.05)
            a.m("glass", smooth=True).lathe([(0, 0.025), (r, 0.025), (r, 0.025 + h), (r * 0.8, 0.03 + h), (0, 0.03 + h)], (x, y, 0), seg=16)
            a.m("jar_lid", bevel=0.003).lathe([(0, 0.03 + h), (r * 0.85, 0.03 + h), (r * 0.85, 0.055 + h), (0, 0.055 + h)], (x, y, 0), seg=16)
        elif kind == "bottle":
            r = 0.035
            a.m("glass", smooth=True).lathe([(0, 0.025), (r, 0.025), (r, 0.025 + h), (0.012, 0.07 + h), (0.012, 0.11 + h), (0, 0.11 + h)], (x, y, 0), seg=16)
            a.m("cork").lathe([(0, 0.11 + h), (0.011, 0.11 + h), (0.011, 0.13 + h), (0, 0.13 + h)], (x, y, 0), seg=8)
        else:
            a.m("crock", smooth=True).lathe([(0, 0.025), (0.05, 0.025), (0.058, 0.07), (0.05, 0.025 + h * 0.9), (0.042, 0.025 + h * 0.9),
                                             (0, 0.025 + h * 0.9)], (x, y, 0), seg=16)
    a.build()

def sconce(name="Wall sconce", x=0.8, h=1.45):
    a = A(name, (x, DEPTH, Z + h))
    ir = a.m("iron", bevel=0.003)
    ir.box(-0.05, 0.05, -0.012, 0, -0.08, 0.08)                     # back plate
    ir.beam((0, -0.01, 0.0), (0, -0.14, 0.05), 0.02, 0.02)            # arm
    ir.box(-0.06, 0.06, -0.26, -0.14, 0.04, 0.05)                     # lantern base
    for sx in (-1, 1):
        for sy in (-0.255, -0.145):
            ir.box(sx * 0.055 - 0.006, sx * 0.055 + 0.006, sy - 0.006, sy + 0.006, 0.05, 0.22)
    ir.lathe([(0.085, 0.22), (0.0, 0.29)], (0, -0.2, 0), seg=4)       # pyramid cap
    ir.rod((0, -0.2, 0.29), (0, -0.2, 0.33), 0.008, seg=6)
    a.m("glass").box(-0.05, 0.05, -0.25, -0.15, 0.05, 0.22)
    a.m("bulb", smooth=True).ellipsoid((0, -0.2, 0.12), (0.025, 0.025, 0.04))
    a.build()

def rug(name, cx, cy, w=1.2, d=0.65):
    """Plain beige linen-weave rug (10-20, user reference: one warm sand colour on every floor)."""
    a = A(name, (cx, cy))
    a.m("jute", bevel=0.004).box(-w / 2, w / 2, -d / 2, d / 2, 0.0, 0.012)
    a.build()

def stool(name, x, y, H=None, seat="cork"):
    a = A(name, (x, y))
    w = a.m("chair", bevel=0.004)
    H = BAR_STOOL_H if H is None else H
    a.m(seat, bevel=0.01, segments=3, smooth=False).lathe([(0, H - 0.04), (0.17, H - 0.04), (0.175, H - 0.02), (0.165, H), (0, H)], seg=28)
    for k in range(4):
        t = math.pi / 4 + k * math.pi / 2
        w.beam((0.11 * math.cos(t), 0.11 * math.sin(t), H - 0.04), (0.17 * math.cos(t), 0.17 * math.sin(t), 0), 0.03, 0.03, w2=0.034, h2=0.034)
    w.torus((0, 0, 0.22), 0.152, 0.011, seg=24, rseg=6)
    a.build()

def look_cam(name, loc, target, lens):
    cd = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    cd.lens, cd.clip_start, cd.clip_end = lens, 0.03, 5000
    o = bpy.data.objects.get(name) or bpy.data.objects.new(name, cd)
    if o.name not in bpy.data.collections["08_Cameras"].objects:
        bpy.data.collections["08_Cameras"].objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()


def armchair(name, x, y, rz, throw=False, cushion=False, fabric=("fabric_green", "fabric_green_dk"),
             throw_colors=("plaid", "plaid_line")):
    a = A(name, (x, y), rz)
    f, f2 = a.m(fabric[0], bevel=0.04, segments=3), a.m(fabric[1], bevel=0.045, segments=3)
    W2, D2 = 0.475, 0.425
    w = a.m("chair", smooth=True)
    for sx in (-1, 1):
        for sy in (-1, 1):
            w.lathe([(0, 0), (0.022, 0), (0.03, 0.05), (0.026, 0.085), (0, 0.085)], (sx * 0.4, sy * 0.36, 0), seg=10)
    f.box(-W2, W2, -D2, D2, 0.085, 0.30)                                   # base and skirt
    f.box(-W2, W2, 0.26, D2, 0.30, 0.98)                                    # back shell
    for s in (-1, 1):
        f.box(s * 0.3 if s > 0 else -W2, W2 if s > 0 else -0.3, -0.41, 0.4, 0.30, 0.6)   # arm sides
        f.rod((s * 0.39, -0.44, 0.6), (s * 0.39, 0.4, 0.6), 0.088, seg=16)               # rolled arm tops
    f2.box(-0.3, 0.3, -0.43, 0.26, 0.30, 0.46)                               # seat cushion
    f2.box(-0.3, 0.3, 0.12, 0.27, 0.46, 0.9)                                 # back cushion
    if throw:   # plaid throw over the back, falling onto the back cushion
        path = [(0.47, 0.5), (0.47, 0.82), (0.44, 0.98), (0.36, 1.03), (0.27, 0.97), (0.2, 0.84), (0.17, 0.7)]
        def pt(u, v):
            t = v * (len(path) - 1)
            i = min(int(t), len(path) - 2)
            f_ = t - i
            yy = path[i][0] + (path[i + 1][0] - path[i][0]) * f_
            zz = path[i][1] + (path[i + 1][1] - path[i][1]) * f_
            xx = -0.32 + u * 0.5
            wob = 0.012 * math.sin(2 * math.pi * 3 * u + v * 2)
            return (xx, yy - wob * 0.5, zz + wob)
        a.m(throw_colors[0], solidify=0.012, smooth=True).surface(pt, 18, 22)
        ln = a.m(throw_colors[1])
        for k in range(1, 4):     # woven stripes lying on the outer face of the throw
            u = k / 4
            pts = [Vector(pt(u, v / 21)) for v in range(22)]
            for p, q in zip(pts, pts[1:]):
                ln.rod(p + Vector((0, 0.0, 0.008)), q + Vector((0, 0.0, 0.008)), 0.006, seg=4)
    if cushion:   # orange cushion with cream dots, leaning in the corner of the seat
        c = Vector((0.12, 0.13, 0.66))
        R = Matrix.Rotation(-0.3, 3, 'X') @ Matrix.Rotation(-0.25, 3, 'Z')
        rad = (0.2, 0.065, 0.17)
        a.m("cushion_o", smooth=True).ellipsoid(c, rad, seg=20, rings=12, rot=R)
        dots = a.m("dot", smooth=True)
        for dx in (-0.12, 0.0, 0.12):
            for dz in (-0.1, 0.0, 0.1):
                k = 1 - (dx / rad[0]) ** 2 - (dz / rad[2]) ** 2
                if k <= 0.05:
                    continue
                p = c + R @ Vector((dx, -rad[1] * math.sqrt(k) - 0.002, dz))
                dots.ellipsoid(p, (0.02, 0.006, 0.02), seg=8, rings=4, rot=R)
    a.build()


def potted_plant(name, x, y, z0, pot_r, height, kind="bush", n=40):
    a = A(name, (x, y, z0))
    ph = pot_r * 1.4
    a.m("terracotta", bevel=0.004).lathe([(0, 0), (pot_r * 0.75, 0), (pot_r, ph), (pot_r * 1.1, ph), (pot_r * 1.1, ph + 0.035),
                                          (pot_r * 0.9, ph + 0.035), (pot_r * 0.9, ph - 0.01), (0, ph - 0.01)], seg=24)
    a.m("soil").lathe([(0, ph - 0.02), (pot_r * 0.9, ph - 0.02), (pot_r * 0.9, ph - 0.012), (0, ph - 0.012)], seg=24)
    st, lf, lf2 = a.m("stem"), a.m("leaf", smooth=True), a.m("leaf_dark", smooth=True)
    if kind == "fig":            # fiddle-leaf fig: one trunk, big leaves on the upper half
        top = Vector((0.03, -0.02, height))
        st.rod((0, 0, ph - 0.02), top, 0.018, seg=8, r2=0.01)
        for k in range(n):
            t = k / (n - 1)
            base = Vector((0, 0, ph)) + (top - Vector((0, 0, ph))) * (0.35 + 0.65 * t)
            ang = k * 2.4
            out = Vector((math.cos(ang), math.sin(ang), 0.35)).normalized()
            size = 0.13 * (1.1 - 0.4 * t)
            st.rod(base, base + out * 0.06, 0.004, seg=5)
            R = Matrix.Rotation(ang, 3, 'Z') @ Matrix.Rotation(-0.35 + 0.3 * t, 3, 'Y')
            (lf if k % 3 else lf2).ellipsoid(base + out * (0.06 + size * 0.8), (size, size * 0.62, 0.008), seg=10, rings=5, rot=R)
    else:                        # leafy bush: a few branches, each ending in a cluster of leaves
        r = (height - ph) * 0.5
        crown = Vector((0, 0, ph + r))
        nb = 5
        for b in range(nb):
            th = 2 * math.pi * b / nb + rng.uniform(-0.3, 0.3)
            sub = crown + Vector((math.cos(th) * r * 0.45, math.sin(th) * r * 0.45, rng.uniform(-0.2, 0.35) * r))
            st.rod((0, 0, ph - 0.02), sub, 0.006, seg=5, r2=0.004)
            for k in range(n // nb):
                d = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.6, 1))).normalized()
                c = sub + d * r * rng.uniform(0.15, 0.5)
                st.rod(sub, c, 0.003, seg=4)
                R = Matrix.Rotation(math.atan2(d.y, d.x), 3, 'Z') @ Matrix.Rotation(-0.4 - 0.5 * d.z, 3, 'Y')
                (lf if k % 3 else lf2).ellipsoid(c + d * 0.035, (0.065, 0.034, 0.005), seg=8, rings=4, rot=R)
    a.build()


def book_run(a, x, x_end, zb, height, colors, front, depth=0.19):
    """Spines flush and heights close, but colours mixed like a real shelf: drawn from the run's
    palette plus the shared muted tones, never the same colour three times running, with the odd
    two-volume set."""
    pool = colors * 2 + ["b7", "b8", "b9", "b10", "b11"]
    prev = []
    while x < x_end - 0.02:
        if len(prev) and rng.random() < 0.18:
            c = prev[-1]                                   # a matching volume
        else:
            c = rng.choice([k for k in pool if prev[-2:] != [k, k]])
        if len(prev) >= 2 and prev[-1] == prev[-2] == c:
            c = rng.choice([k for k in pool if k != c])
        t = min(rng.uniform(0.022, 0.042), x_end - x)
        h = height + rng.uniform(-0.03, 0.012)
        dd = depth - rng.uniform(0, 0.02)
        a.m(c, bevel=0.002).box(x, x + t - 0.002, front, front + dd, zb, zb + h)
        prev.append(c)
        x += t
    return x


# ---- window dressing shared by every floor (10-20): honey wooden blinds and sheer side panels
def wood_blinds(name, loc, rz, width, sill, head, drop=None):
    """Honey wooden venetian blind (5 cm slats, tilted open) with ladder tapes; local x = width,
    local -y = into the room, origin on the wall face at the window centre."""
    a = A(name, loc, rz)
    bl, tp = a.m("blind", bevel=0.002), a.m("tape")
    w = width + 0.06
    y = -0.07
    bl.box(-w / 2, w / 2, y - 0.03, y + 0.03, head + 0.06, head + 0.12)                  # head rail
    bottom = sill + 0.02 if drop is None else drop
    z = head + 0.03
    tilt = math.radians(35)
    while z > bottom + 0.06:
        dy, dz = 0.025 * math.cos(tilt), 0.025 * math.sin(tilt)
        bl.solid([(-w / 2 + 0.01, y - dy, z - dz), (w / 2 - 0.01, y - dy, z - dz), (w / 2 - 0.01, y + dy, z + dz), (-w / 2 + 0.01, y + dy, z + dz)],
                 [(-w / 2 + 0.01, y - dy, z - dz + 0.003), (w / 2 - 0.01, y - dy, z - dz + 0.003), (w / 2 - 0.01, y + dy, z + dz + 0.003), (-w / 2 + 0.01, y + dy, z + dz + 0.003)])
        z -= 0.045
    bl.box(-w / 2, w / 2, y - 0.028, y + 0.028, bottom, bottom + 0.03)                      # bottom rail
    for x in (-w / 2 + 0.12, 0.0, w / 2 - 0.12):                                            # ladder tapes
        for side in (-1, 1):
            tp.box(x - 0.018, x + 0.018, y + side * 0.03 - 0.001, y + side * 0.03 + 0.001, bottom, head + 0.06)
    a.build()


def sheer_panels(name, x0, x1, head, wall_y, hem=0.01):
    """Sheer panels gathered at both sides of a back window, floor-length unless `hem` is given."""
    a = A(name, (0, 0, Z))
    cloth = a.m("gauze", smooth=True)
    rod_z = head + 0.08                              # just under the ceiling joists
    for side in (-1, 1):
        xa = x0 - 0.42 if side < 0 else x1 + 0.08
        def fn(u, v, xa=xa):
            x = xa + u * 0.34
            y = wall_y - 0.13 - 0.03 * (0.5 + 0.5 * math.sin(2 * math.pi * 7 * u)) - 0.004 * math.sin(97 * u + 9 * v)
            z = rod_z - 0.03 - v * (rod_z - 0.03 - hem)
            return (x, y, z)
        cloth.surface(fn, 120, 40)
    r = a.m("brass", smooth=True)
    r.rod((x0 - 0.5, wall_y - 0.13, rod_z), (x1 + 0.5, wall_y - 0.13, rod_z), 0.01, seg=10)
    for x in (x0 - 0.45, x1 + 0.45):
        r.box(x - 0.01, x + 0.01, wall_y - 0.14, wall_y, rod_z - 0.01, rod_z + 0.01)
    a.build()


# ---- tufted leather faces (10-20), used by the floor-1 sofa and the floor-2 lounge chairs
def tufted_top(m, x0, x1, base, up, nrm, height, rows, cols, puff, depth=0.022, sigma=0.03, nu=90, nv=40, crease=0.01):
    """Puffy tufted leather face: a grid over the rectangle base + u*(x1-x0) along x + v*up, pushed out
    along nrm by a pillow profile, pulled in at the buttons (diamond pattern, alternate rows offset) and
    creased along the lines joining neighbouring buttons, as in deep-buttoned leather."""
    btn = []
    for r, v in enumerate(rows):
        n = cols if r % 2 == 0 else cols - 1
        for c in range(n):
            u = (c + (0.5 if r % 2 == 0 else 1.0)) / cols
            btn.append((u, v))
    L_ = x1 - x0
    hl = up.length
    P_ = [(bu * L_, bv * hl) for bu, bv in btn]
    step = L_ / cols
    seg_ = [(p, q) for i, p in enumerate(P_) for q in P_[i + 1:]
            if 0.2 * step < math.hypot(p[0] - q[0], p[1] - q[1]) < 1.25 * math.hypot(step / 2, (rows[1] - rows[0]) * hl if len(rows) > 1 else step)]
    def fn(u, v):
        pil = (math.sin(math.pi * u) ** 0.25) * (math.sin(math.pi * v) ** 0.25)
        X, Y = u * L_, v * hl
        d = sum(math.exp(-((X - px) ** 2 + (Y - py) ** 2) / (2 * sigma ** 2)) for px, py in P_)
        cr = 0.0
        for (ax, ay), (bx, by) in seg_:
            vx, vy = bx - ax, by - ay
            t = max(0.0, min(1.0, ((X - ax) * vx + (Y - ay) * vy) / (vx * vx + vy * vy)))
            dd = (X - ax - t * vx) ** 2 + (Y - ay - t * vy) ** 2
            cr = max(cr, math.exp(-dd / (2 * 0.008 ** 2)))
        off = puff * pil - (depth * min(1.0, d) + crease * cr) * pil
        p = base + Vector((x0 + u * L_, 0, 0)) + up * v + nrm * off
        return p
    m.surface(fn, nu, nv)
    return [base + Vector((x0 + bu * L_, 0, 0)) + up * bv + nrm * (puff - depth + 0.004) for bu, bv in btn]


# ---- Poly Haven (CC0) props, shared by all floors
def ph_model(asset, name, loc, scale=1.0, rz=0.0, only=None):
    """Append a Poly Haven model under an empty 'PH <name>' (materials kept). `only`: suffix of the
    variant to keep when a file lays several variants out side by side (it is moved to the origin)."""
    path = os.path.join(os.path.dirname(bpy.data.filepath), "models", asset, f"{asset}_1k.blend")
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = list(src.objects)
    e = bpy.data.objects.new("PH " + name, None)
    COL.objects.link(e)
    e.location, e.rotation_euler, e.scale = loc, (0, 0, rz), (scale,) * 3
    objs = [o for o in dst.objects if o is not None]
    if only:
        keep = [o for o in objs if o.name.endswith(only)]
        for o in objs:
            if o not in keep:
                bpy.data.objects.remove(o, do_unlink=True)
        objs = keep
        off = objs[0].location.copy()
        for o in objs:
            o.location.x -= off.x
            o.location.y -= off.y
    for o in objs:
        COL.objects.link(o)
        o.name = f"PH {name} {o.name}"
        o.parent = e
    for im in bpy.data.images:
        if im.filepath and not os.path.exists(bpy.path.abspath(im.filepath)):
            cand = os.path.join(os.path.dirname(bpy.data.filepath), "models", asset, "textures", os.path.basename(im.filepath))
            if os.path.exists(cand):
                im.filepath = cand
    return e


def ph_planted(asset, variant, name, loc, plant_scale=1.0, pot_scale=0.6, rz=0.0):
    """A pot-less Poly Haven plant set into the scanned ceramic_pot."""
    x, y, z = loc
    ph_model("ceramic_pot", name + " pot", (x, y, z), pot_scale, rz)
    return ph_model(asset, name, (x, y, z + 0.30 * pot_scale), plant_scale, rz + 0.7, only=variant)


# ---- bent tubes (10-20), used by the Cesca chair and the rocking lounge chair
def sweep_tube(m, path, r, seg=14):
    """Round tube swept along a polyline (rotation-minimising frames), so bends stay smooth."""
    rings, n_prev = [], None
    for i, p in enumerate(path):
        t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        if n_prev is None:
            n_prev = t.orthogonal().normalized()
        n = (n_prev - t * n_prev.dot(t)).normalized()
        b = t.cross(n)
        rings.append([p + (n * math.cos(2 * math.pi * k / seg) + b * math.sin(2 * math.pi * k / seg)) * r for k in range(seg)])
        n_prev = n
    i0 = len(m.v)
    for ring in rings:
        m.v += [tuple(q) for q in ring]
    for i in range(len(rings) - 1):
        for k in range(seg):
            a_, b_ = i0 + i * seg + k, i0 + i * seg + (k + 1) % seg
            m.f.append([a_, b_, b_ + seg, a_ + seg])
    m.f.append([i0 + k for k in range(seg)][::-1])
    m.f.append([i0 + (len(rings) - 1) * seg + k for k in range(seg)])
