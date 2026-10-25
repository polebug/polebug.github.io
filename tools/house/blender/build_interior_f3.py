"""Stage 3, floor 3: the attic bedroom.

Run after build_interior_f2.py:
    Blender -b assets/blender/companion-house.blend --python build_interior_f3.py
Replaces the whitebox collection 05_Floor3 with 23_Floor3 and saves in place. Assets are empties
named "F3 ..."; positions follow the approved whitebox. Everything here also has to clear the
sloping roof: rafters bottom out at roof_under(x), purlins hang 0.24 m lower at x = 0 and +/-2.6.
"""
from mathutils import noise
import bpy, math, os, sys
from mathutils import Vector, Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from house_spec import *   # noqa: E402,F403
import interior_common as ic  # noqa: E402
from interior_common import (sweep_tube, ph_model, ph_planted, wood_blinds, sheer_panels, P, vase_with_flowers, curtains, sconce, rug, look_cam, armchair,  # noqa: E402
                             potted_plant, book_run)

A = ic.setup(3, "23_Floor3", "05_Floor3", seed=303)
Z, rng = ic.Z, ic.rng
P.update({
    "bed_wood": (0.62, 0.42, 0.27), "sheet": (0.97, 0.96, 0.93), "duvet": (0.90, 0.86, 0.78),   # natural linen off-white (user, 10-20)
    "duvet_band": (0.96, 0.94, 0.89), "pillow": (0.91, 0.88, 0.81), "trunk": (0.56, 0.38, 0.24),
    "trunk_metal": (0.30, 0.30, 0.32), "strap": (0.40, 0.25, 0.16), "lamp_shade": (0.95, 0.86, 0.66),
    "arm_tan": (0.70, 0.52, 0.36), "arm_tan_dk": (0.62, 0.45, 0.31), "throw_blue": (0.38, 0.56, 0.78),
    "throw_line": (0.86, 0.90, 0.95), "candle": (0.97, 0.94, 0.86),
})
# 10-20: platform bed pulled off the back wall so a nightstand stands on each side of the headboard
BED_X, BED_Y = -0.75, 3.5                  # still side-on to the camera, head at -x


# ================================================================== bed
def bed():
    """Mid-century walnut platform bed after the user's photo: low wide platform frame on splayed
    tapered legs, plain slab headboard, crumpled natural-linen duvet and pillows. Head at -x."""
    a = A("Bed", (BED_X, BED_Y))
    L2, W2 = 1.15, 0.92
    w = a.m("walnut", bevel=0.006, smooth=True)
    PZ0, PZ1 = 0.20, 0.26
    w.box(-L2 + 0.02, L2 + 0.10, -W2 - 0.08, W2 + 0.08, PZ0, PZ1)              # platform, overhanging the mattress
    w.box(-L2 + 0.10, L2 - 0.05, -W2 + 0.05, W2 - 0.05, PZ0 - 0.06, PZ0)       # recessed under-frame
    for sx, lx in ((-1, -L2 + 0.22), (1, L2 - 0.12)):                           # splayed tapered legs
        for sy in (-1, 1):
            top = Vector((lx, sy * (W2 - 0.12), PZ0 - 0.06))
            foot = Vector((lx + sx * 0.07, sy * (W2 - 0.04), 0.0))
            w.beam(top, foot, 0.06, 0.06, w2=0.035, h2=0.035)
    hb = [(-L2 - 0.02, PZ1), (-L2 + 0.04, PZ1), (-L2 - 0.02, 1.02), (-L2 - 0.08, 1.02)]   # slab headboard, leaning back
    w.solid([(x, -W2 - 0.06, z) for x, z in hb], [(x, W2 + 0.06, z) for x, z in hb])
    # mattress with a fitted white sheet
    a.m("sheet", bevel=0.05, segments=3, smooth=True).box(-L2 + 0.06, L2 - 0.02, -W2 + 0.02, W2 - 0.02, PZ1, 0.50)
    # pillows: two standing against the headboard, two lying in front (linen)
    pl = a.m("pillow", smooth=True)
    def pillow(c, a_, b_, t_, rot, seed):
        """Rectangular stuffed pillow: superquadric (square outline, round edge) with soft creases."""
        def fn(u, v):
            th, ph = 2 * math.pi * u, math.pi * (v - 0.5)
            ct, st, cp, sp = math.cos(th), math.sin(th), math.cos(ph), math.sin(ph)
            e = 0.45                                    # rounder, softer corners
            sq = lambda x_: math.copysign(abs(x_) ** e, x_)
            x_ = a_ * sq(ct) * (abs(cp) ** 0.6)
            y_ = b_ * sq(st) * (abs(cp) ** 0.6)
            z_ = t_ * sp * (1 - 0.35 * (abs(sq(ct)) ** 6 + abs(sq(st)) ** 6) / 2)
            p_ = Vector((x_, y_, z_))
            p_ += Vector((0, 0, 1)) * (0.014 * noise.noise(Vector((x_ * 7, y_ * 7, seed))) + 0.005 * noise.noise(Vector((x_ * 25, y_ * 25, seed + 3)))) * cp   # soft dents and creases
            return c + rot @ p_
        pl.surface(fn, 48, 26)
    for sy in (-1, 1):
        pillow(Vector((-L2 + 0.08, sy * 0.43, 0.71)), 0.22, 0.36, 0.07, Matrix.Rotation(1.25, 3, 'Y'), 1.0 + sy)         # standing, leaning back on the headboard
        pillow(Vector((-L2 + 0.40, sy * 0.41, 0.548)), 0.25, 0.34, 0.065, Matrix.Rotation(0.06, 3, 'Y'), 3.0 + sy)       # lying on the mattress
    # crumpled linen duvet: drapes over the sides and the foot, with soft folds and wrinkles
    TOP = 0.56
    def duvet(u, v):
        x = -L2 + 0.48 + u * (2 * L2 - 0.48 + 0.04)
        yy = -1.0 + 2.0 * v                                     # -1..1 across, with the drop on both sides
        side = max(0.0, abs(yy) - 0.82) / 0.18                  # 0 on top, 1 at the hem
        y = math.copysign(min(abs(yy), 0.82) / 0.82 * (W2 + 0.01) + side * 0.03, yy)
        foot = max(0.0, (u - 0.9) / 0.1)                        # rolls over the foot end
        x += foot * 0.05
        # side drop and foot drop do not add up at the corners (it hung to the floor like a leg)
        z = TOP - max(side * 0.30, foot * foot * 0.26) - 0.025 * (1 - math.cos(math.pi * min(abs(yy), 0.82) / 0.82)) * 0.5
        wr = (0.018 * noise.noise(Vector((x * 2.5, y * 2.5, 0.3))) + 0.009 * noise.noise(Vector((x * 7.0, y * 6.0, 1.7)))
              + 0.006 * abs(math.sin(11 * x + 7 * noise.noise(Vector((x * 1.5, y * 1.5, 2.0))))) + 0.003 * noise.noise(Vector((x * 20, y * 18, 4.0))))
        return (x, y, z + wr)
    a.m("duvet", solidify=0.03, smooth=True).surface(duvet, 150, 110)
    a.build()


def trunk():
    a = A("Bed-front trunk", (BED_X + 0.35, BED_Y - 1.2))
    L2, W2, H = 0.55, 0.24, 0.48
    b = a.m("trunk", bevel=0.01)
    b.box(-L2, L2, -W2, W2, 0.03, 0.35)                              # body
    lid = a.m("trunk", bevel=0.012, segments=3)
    prof = [(-W2, 0.35), (W2, 0.35)] + [(W2 * math.cos(t), 0.35 + 0.1 * math.sin(t)) for t in [k * math.pi / 8 for k in range(1, 8)]]
    lid.solid([(-L2, y, z) for y, z in prof], [(L2, y, z) for y, z in prof])
    m = a.m("trunk_metal", bevel=0.003)
    span = lambda s_, e: (e - 0.07, e + 0.004) if s_ > 0 else (-e - 0.004, -e + 0.07)
    for sx in (-1, 1):                                               # metal corner caps
        for sy in (-1, 1):
            for z0, z1 in ((0.03, 0.11), (0.27, 0.35)):
                m.box(*span(sx, L2), *span(sy, W2), z0, z1)
    for x in (-0.3, 0.3):                                            # leather straps over the lid
        st = a.m("strap")
        st.box(x - 0.03, x + 0.03, -W2 - 0.004, -W2, 0.03, 0.35)
        pts = [(W2 * math.cos(t) * 1.02, 0.35 + 0.102 * math.sin(t)) for t in [k * math.pi / 10 for k in range(11)]]
        for (y0, z0), (y1, z1) in zip(pts, pts[1:]):
            st.beam((x, y0, z0), (x, y1, z1), 0.06, 0.006, side=(1, 0, 0))
    m.box(-0.05, 0.05, -W2 - 0.012, -W2, 0.27, 0.36)                 # hasp
    for sx in (-1, 1):
        m.torus((sx * (L2 + 0.02), 0, 0.24), 0.05, 0.008, seg=14, rseg=5, axis='x')
    for sx in (-1, 1):
        for sy in (-1, 1):
            m.box(sx * (L2 - 0.06) - 0.03, sx * (L2 - 0.06) + 0.03, sy * (W2 - 0.06) - 0.03, sy * (W2 - 0.06) + 0.03, 0, 0.03)   # feet
    a.build()


def nightstand(name, x, y, lamp=True):
    """Mid-century walnut nightstand: two drawers with brass knobs on splayed tapered legs, brass
    mushroom lamp. Front faces +x (toward the foot of the bed)."""
    a = A(name, (x, y), math.radians(90))
    X2, Y2, H, LEG = 0.25, 0.21, 0.58, 0.16
    w = a.m("walnut", bevel=0.005, smooth=True)
    w.box(-X2, X2, -Y2, Y2, LEG, H)                                              # case
    for k, (z0, z1) in enumerate(((LEG + 0.015, LEG + 0.2), (LEG + 0.21, H - 0.015))):
        w.box(-X2 + 0.015, X2 - 0.015, -Y2 - 0.012, -Y2, z0, z1)                # drawer fronts
        a.m("brass", smooth=True).lathe([(0, 0), (0.012, 0), (0.015, 0.016), (0, 0.022)], (0, -Y2 - 0.012, (z0 + z1) / 2), axis='-y', seg=12)
    for sx in (-1, 1):
        for sy in (-1, 1):
            w.beam((sx * (X2 - 0.05), sy * (Y2 - 0.05), LEG), (sx * (X2 - 0.01), sy * (Y2 - 0.01), 0), 0.035, 0.035, w2=0.02, h2=0.02)
    if lamp:
        b = a.m("brass_lamp", smooth=True)
        b.lathe([(0, H), (0.07, H), (0.07, H + 0.012), (0.015, H + 0.02), (0.008, H + 0.30), (0, H + 0.30)], (0.08, 0.04, 0), seg=28)
        b.lathe([(0.0, H + 0.42), (0.06, H + 0.41), (0.11, H + 0.37), (0.135, H + 0.31), (0.13, H + 0.305), (0.105, H + 0.365),
                 (0.057, H + 0.402), (0.0, H + 0.41)], (0.08, 0.04, 0), seg=40, closed=True)
        a.m("bulb", smooth=True).ellipsoid((0.08, 0.04, H + 0.33), (0.03, 0.03, 0.03))
    a.build()


def side_table():
    a = A("Side table", (2.1, DEPTH - 0.22))
    X2, Y2, H = 0.225, 0.2, 0.5
    w = a.m("bed_wood", bevel=0.005)
    w.box(-X2, X2, -Y2, Y2, H - 0.025, H)
    for sx in (-1, 1):
        for sy in (-1, 1):
            w.beam((sx * (X2 - 0.04), sy * (Y2 - 0.04), 0), (sx * (X2 - 0.03), sy * (Y2 - 0.03), H - 0.025), 0.026, 0.026, w2=0.034, h2=0.034)
    w.box(-X2 + 0.04, X2 - 0.04, -Y2 + 0.04, Y2 - 0.04, 0.1, 0.12)
    a.build()


def attic_bookshelf():
    a = A("Attic bookshelf", (2.9, DEPTH))
    W2, D, H = 0.35, 0.35, 1.4
    c = a.m("bed_wood", bevel=0.004)
    for s in (-1, 1):
        c.box(s * W2 - (0.022 if s > 0 else 0), s * W2 + (0.022 if s < 0 else 0), -D, 0, 0, H)
    c.box(-W2, W2, -0.012, 0, 0.04, H)
    for zb in (0.04, 0.45, 0.85):
        c.box(-W2 + 0.022, W2 - 0.022, -D + 0.01, 0, zb, zb + 0.02)
    c.box(-W2 - 0.02, W2 + 0.02, -D - 0.02, 0, H, H + 0.025)
    c.box(-W2 + 0.022, W2 - 0.022, -D + 0.015, -D + 0.035, 0, 0.04)
    front = -D + 0.05
    book_run(a, -W2 + 0.03, W2 - 0.03, 0.06, 0.3, ["b1", "b10"], front, depth=0.22)
    x = book_run(a, -W2 + 0.03, 0.12, 0.47, 0.26, ["b2", "b9"], front, depth=0.22)
    a.m("glass", smooth=True).lathe([(0, 0.47), (0.045, 0.47), (0.045, 0.6), (0, 0.6)], (0.24, front + 0.1, 0), seg=16)
    a.m("jar_lid").lathe([(0, 0.6), (0.04, 0.6), (0.04, 0.62), (0, 0.62)], (0.24, front + 0.1, 0), seg=16)
    book_run(a, -W2 + 0.03, -0.05, 0.87, 0.24, ["b6", "b3"], front, depth=0.2)
    zz = 0.87
    for k, col in enumerate(("b11", "b4")):                       # a short flat stack on the top shelf
        a.m(col, bevel=0.002).box(0.02, 0.28 - 0.02 * k, front + 0.01, front + 0.2 - 0.01 * k, zz, zz + 0.03)
        zz += 0.03
    a.build()


def bowl_chair(name, x, y, rz):
    """Bowl rocker after the user's photo: a shallow oval walnut shell whose rounded underside rocks on
    the floor, rim rising toward the back, holding a plump cream boucle seat cushion and a thick quilted
    back roll that follows the rim. Faces -y (back at +y)."""
    a = A(name, (x, y), rz)
    S_ = 0.8                                   # 10-20: scaled down (user: too big)
    C = Vector((0, 0, 0.30))
    RX, RY, RZ = 0.56, 0.50, 0.28
    def rim_phi(th):
        target = 0.30 + 0.20 * (math.sin(th) + 1) / 2               # front rim low, back rim higher
        return math.asin(max(-1.0, min(1.0, (target - C.z) / RZ)))
    def shell_pt(th, v):
        ph = -math.pi / 2 + (rim_phi(th) + math.pi / 2) * v
        return C + Vector((RX * math.cos(ph) * math.cos(th), RY * math.cos(ph) * math.sin(th), RZ * math.sin(ph)))
    # parameter seam at the back (+y), where the back roll hides it
    a.m("walnut", solidify=0.035, smooth=True).surface(lambda u, v: shell_pt(math.pi / 2 + 2 * math.pi * u, v), 72, 30)
    cu = a.m("cushion_cream", smooth=True)
    # cloud-like wrap (user): soft overlapping closed puffs - a big seat puff sunk into the bowl and a
    # ring of plump lobes around the sides and back, taller at the back, all bulging over the rim
    def puff(c, ax, ay, az, yaw, seed, e=0.8):
        R = Matrix.Rotation(yaw, 3, 'Z')
        def fn(u, v):
            th, ph = 2 * math.pi * u, math.pi * (v - 0.5)
            sq = lambda t_, ee: math.copysign(abs(t_) ** ee, t_)
            cp = abs(math.cos(ph)) ** e
            p_ = Vector((ax * sq(math.cos(th), e) * cp, ay * sq(math.sin(th), e) * cp, az * sq(math.sin(ph), e)))
            p_ *= 1 + 0.035 * noise.noise(p_ * 6 + Vector((seed, 0, 0)))
            return c + R @ p_
        cu.surface(fn, 40, 24)
    def seat(u, v):                                                            # one soft closed cushion, dished in the middle (user)
        th, ph = 2 * math.pi * u, math.pi * (v - 0.5)
        sq = lambda t_, ee: math.copysign(abs(t_) ** ee, t_)
        cp = abs(math.cos(ph)) ** 0.7
        x_, y_ = 0.53 * sq(math.cos(th), 0.8) * cp, 0.47 * sq(math.sin(th), 0.8) * cp
        z_ = 0.12 * sq(math.sin(ph), 0.7)
        if ph > 0:                                                             # sink the top in the middle: sat-in hollow
            r2 = (x_ / 0.53) ** 2 + (y_ / 0.47) ** 2
            z_ -= 0.075 * max(0.0, 1 - r2) ** 1.5
        p_ = Vector((x_, y_ - 0.02, 0.33 + z_))
        p_ *= 1.0
        p_.z += 0.01 * noise.noise(Vector((p_.x * 6, p_.y * 6, 0.4))) * cp
        return p_
    cu.surface(seat, 72, 40)
    for k in range(9):                                                         # lobes from one side, round the back, to the other
        th = math.radians(-25 + k * 230 / 8)
        back = max(0.0, math.sin(th))
        c = Vector((0.39 * math.cos(th), 0.33 * math.sin(th) + 0.01, 0.40 + 0.20 * back))
        puff(c, 0.17 + 0.03 * back, 0.13, 0.13 + 0.09 * back, th + math.pi / 2, k * 1.7)
    e = a.build()
    e.scale = (S_, S_, S_)
    return e


def arc_floor_lamp(name, x, y, rz):
    """Brass arc floor lamp after the user's photo: round base, slender pole sweeping over into a
    hanging cream pleated shade. The shade hangs toward local -y."""
    a = A(name, (x, y), rz)
    wd = a.m("walnut", smooth=True)                                            # dark walnut base and curved stem (user)
    wd.lathe([(0, 0), (0.15, 0), (0.15, 0.02), (0.13, 0.035), (0, 0.04)], seg=40)
    P0, P1, P2, P3 = Vector((0, 0, 0.04)), Vector((0, 0.30, 1.12)), Vector((0, 0.10, 1.92)), Vector((0, -0.42, 1.55))   # lamp 1.65 m tall at the arc (user)
    pts = []
    for k in range(41):                                                        # one smooth bezier arc, no straight pole
        t = k / 40
        pts.append(P0 * (1 - t) ** 3 + P1 * 3 * t * (1 - t) ** 2 + P2 * 3 * t * t * (1 - t) + P3 * t ** 3)
    sweep_tube(wd, pts, 0.014, seg=14)
    br = a.m("brass_lamp", smooth=True)
    br.rod(P3, P3 + Vector((0, 0, -0.04)), 0.016, seg=12)                       # brass socket
    tip = pts[-1]
    sh = a.m("lamp_cream", smooth=False)
    n = 36
    c = tip + Vector((0, 0, -0.03))
    for k in range(n):                                                      # pleated cone shade
        t0, t1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        f0, f1 = (1.0, 0.92) if k % 2 == 0 else (0.92, 1.0)
        top = [c + Vector((0.035 * math.cos(t), 0.035 * math.sin(t), 0)) for t in (t0, t1)]
        bot = [c + Vector((0.24 * f * math.cos(t), 0.24 * f * math.sin(t), -0.16)) for t, f in ((t0, f0), (t1, f1))]
        sh.solid([bot[0], bot[1], top[1], top[0]], [q + Vector((0, 0, 0.003)) for q in (bot[0], bot[1], top[1], top[0])])
    a.m("bulb", smooth=True).ellipsoid(c + Vector((0, 0, -0.08)), (0.03, 0.03, 0.04), seg=10, rings=6)
    a.build()


def chest_of_drawers():
    a = A("Chest of drawers", (4.2, 4.4))
    X2, Y2, H = 0.25, 0.225, 0.75
    w = a.m("bed_wood", bevel=0.005)
    w.box(-X2, X2, -Y2 + 0.02, Y2, 0.06, H - 0.025)
    w.box(-X2 - 0.015, X2 + 0.015, -Y2 - 0.005, Y2, H - 0.025, H)
    w.box(-X2 + 0.02, X2 - 0.02, -Y2 + 0.04, Y2 - 0.02, 0, 0.06)
    zs = [0.07, 0.29, 0.5, H - 0.035]
    for z0, z1 in zip(zs, zs[1:]):
        w.box(-X2 + 0.015, X2 - 0.015, -Y2, -Y2 + 0.02, z0 + 0.004, z1 - 0.004)
        for x in (-0.12, 0.12):
            a.m("brass", smooth=True).lathe([(0, 0), (0.012, 0), (0.014, 0.018), (0, 0.024)], (x, -Y2, (z0 + z1) / 2), axis='-y', seg=10)
    c = a.m("candle", smooth=True)
    c.lathe([(0, H), (0.035, H), (0.035, H + 0.12), (0, H + 0.12)], (0.08, 0.05, 0), seg=16)
    a.m("brass", smooth=True).lathe([(0, H), (0.06, H), (0.06, H + 0.012), (0.04, H + 0.012), (0, H + 0.01)], (0.08, 0.05, 0), seg=20)
    a.m("bulb", smooth=True).lathe([(0, H + 0.12), (0.01, H + 0.13), (0, H + 0.16)], (0.08, 0.05, 0), seg=10)
    a.build()


# ================================================================== build everything
bed()
# (10-20: the bed-front trunk was removed, user)
nightstand("Nightstand back", BED_X - 1.0, BED_Y + 0.92 + 0.30)
nightstand("Nightstand front", BED_X - 1.0, BED_Y - 0.92 - 0.30)
side_table()
ph_model("jug_01", "Side table jug", (1.97, DEPTH - 0.24, Z + 0.5), 0.6, 2.4)   # 10-20: real (Poly Haven) props instead of modelled plants
ph_model("potted_plant_04", "Side table aloe", (2.24, DEPTH - 0.18, Z + 0.5), 1.2, 1.0)
sconce("Wall lantern", 2.1, 1.25)                   # over the side table, clear of the sheers
attic_bookshelf()
ph_planted("calathea_orbifolia_01", "_e", "Bookshelf top plant", (2.9, DEPTH - 0.17, Z + 1.425), 1.0, 0.35, 3.0)
bowl_chair("Armchair attic", 3.0, 2.7, math.radians(-35))     # walnut bowl rocker with a quilted cream cushion (user photo)
arc_floor_lamp("Attic floor lamp", 3.55, 3.25, math.radians(-49))     # brass arc lamp, shade reaching over the bowl chair
chest_of_drawers()
ph_model("potted_plant_01", "Attic plant big", (-3.55, 3.85, Z), 1.3, 0.5)
ph_planted("calathea_orbifolia_01", "_a", "Attic plant L", (-4.3, 1.0, Z), 1.1, 0.7, 2.0)
ph_model("potted_plant_02", "Attic plant R", (4.3, 1.0, Z), 0.85, 4.4)
a_, b_, s_, h_ = WIN_BACK[3]
wood_blinds("Back window blind", ((a_ + b_) / 2, DEPTH, Z), 0.0, b_ - a_, s_, h_, drop=h_ - 0.5)   # raised: let the daylight in
sheer_panels("Back window sheers", a_, b_, h_, DEPTH, hem=s_ - 0.04)   # stop above the bed
rug("Bedroom rug", -0.3, 3.3, w=3.4, d=2.8)

look_cam("Cam_F3_Bed", (1.3, 1.4, Z + 1.45), (-1.2, 4.2, Z + 0.45), 26)
look_cam("Cam_F3_Nightstand", (-1.2, 2.3, Z + 1.2), (-2.6, 4.7, Z + 0.6), 28)
look_cam("Cam_F3_Corner", (1.9, 2.75, Z + 1.4), (3.4, 4.45, Z + 0.6), 26)
ic.finish("F3_SAVED")
