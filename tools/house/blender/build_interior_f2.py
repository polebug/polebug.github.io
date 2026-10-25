"""Stage 3, floor 2: hearth, reading corner, bookcase and desk.

Run after build_interior_f1.py:
    Blender -b assets/blender/companion-house.blend --python build_interior_f2.py
Replaces the whitebox collection 04_Floor2 with 22_Floor2 and saves in place. Assets are empties
named "F2 ..." with one child mesh per material; positions follow the approved whitebox.
"""
import bpy, math, os, sys
from mathutils import Vector, Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from house_spec import *   # noqa: E402,F403
import interior_common as ic  # noqa: E402
from interior_common import (sweep_tube, tufted_top, ph_model, ph_planted, P, ladder_chair, vase_with_flowers, curtains, sconce, rug, stool, wood_blinds, sheer_panels,  # noqa: E402
                             look_cam, armchair, potted_plant)

A = ic.setup(2, "22_Floor2", "04_Floor2", seed=202)
Z, CEIL, rng = ic.Z, ic.CEIL, ic.rng
CH_REL = CEIL - Z                     # ceiling (joist underside) above the floor: 2.09 m
STONES = ["stone_a", "stone_b", "stone_c"]


def stone_face(a, fmap, u0, u1, z0, z1, skip=(), course=(0.13, 0.2), length=(0.16, 0.32), proud=0.035):
    """Irregular coursed stones on one face; fmap(u, d, z) with d = outward distance from the face."""
    z = z0
    while z < z1 - 0.03:
        h = min(rng.uniform(*course), z1 - z)
        u = u0 - rng.uniform(0, 0.1)
        while u < u1:
            L = rng.uniform(*length)
            ua, ub = max(u, u0) + 0.005, min(u + L, u1) - 0.005
            mid = ((ua + ub) / 2, z + h / 2)
            if ub - ua > 0.04 and not any(s0 <= mid[0] <= s1 and t0 <= mid[1] <= t1 for s0, s1, t0, t1 in skip):
                za, zb = z + 0.005 + rng.uniform(0, 0.008), z + h - 0.005
                loop = [(ua, -0.02), (ub, -0.02), (ub, proud * rng.uniform(0.4, 1.0)), (ua, proud * rng.uniform(0.4, 1.0))]
                a.m(rng.choice(STONES), bevel=0.012, segments=2).solid([fmap(uu, dd, za) for uu, dd in loop],
                                                                      [fmap(uu, dd, zb) for uu, dd in loop])
            u += L
        z += h


# ================================================================== fireplace
def fireplace():
    a = A("Fireplace", (FX, DEPTH))
    core = a.m("soot")
    W2, D, OW2, OZ0, OZ1, MZ = 0.56, 0.70, 0.28, 0.08, 0.62, 1.0
    core.box(-W2, -OW2, -D, 0, 0, MZ)                     # jambs
    core.box(OW2, W2, -D, 0, 0, MZ)
    core.box(-OW2, OW2, -0.1, 0, 0, MZ)                   # firebox back
    core.box(-OW2, OW2, -D, -0.1, OZ1, MZ)                # above the opening
    core.box(-OW2, OW2, -D, -0.1, 0, OZ0)                 # raised firebox floor
    front = lambda u, d, z: (u, -D - d, z)
    stone_face(a, front, -W2, W2, 0, MZ, skip=[(-OW2 - 0.06, OW2 + 0.06, OZ0 - 0.01, OZ1 + 0.14)])
    stone_face(a, lambda u, d, z: (W2 + d, -u, z), 0.0, D, 0, MZ)
    a.m("stone_c", bevel=0.015).box(-OW2 - 0.07, OW2 + 0.07, -D - 0.04, -D + 0.04, OZ1, OZ1 + 0.13)   # lintel
    a.m("stone_c", bevel=0.01).box(-OW2, OW2, -D - 0.02, -D + 0.02, 0.0, OZ0)                          # sill stone
    m = a.m("mantel", bevel=0.01)
    m.box(-W2 - 0.02, W2 + 0.06, -D - 0.1, 0, MZ, MZ + 0.09)          # mantel shelf (short on the wall side)
    for s in (-1, 1):                                                                                  # corbels
        x = s * (W2 - 0.08)
        m.solid([(x - 0.05, -D - 0.05, MZ), (x - 0.05, -D + 0.02, MZ), (x - 0.05, -D + 0.02, MZ - 0.16)],
                [(x + 0.05, -D - 0.05, MZ), (x + 0.05, -D + 0.02, MZ), (x + 0.05, -D + 0.02, MZ - 0.16)])
    # chimney breast up to the ceiling, stones on its three open faces
    BW2, BD = 0.40, 0.50
    a.m("soot").box(-BW2, BW2, -BD, 0, MZ + 0.09, CH_REL)
    stone_face(a, lambda u, d, z: (u, -BD - d, z), -BW2, BW2, MZ + 0.09, CH_REL)
    stone_face(a, lambda u, d, z: (BW2 + d, -u, z), 0.0, BD, MZ + 0.09, CH_REL)
    stone_face(a, lambda u, d, z: (-BW2 - d, -u, z), 0.0, BD, MZ + 0.09, CH_REL)
    # fire: andirons, logs, flames
    ir = a.m("iron", bevel=0.003)
    for s in (-1, 1):
        x = s * 0.17
        ir.box(x - 0.015, x + 0.015, -0.55, -0.15, OZ0, OZ0 + 0.03)
        ir.box(x - 0.015, x + 0.015, -0.58, -0.54, OZ0, OZ0 + 0.16)
        ir.lathe([(0, 0), (0.025, 0), (0.025, 0.02), (0, 0.04)], (x, -0.56, OZ0 + 0.16), seg=10)
    lg, le = a.m("log", bevel=0.004), a.m("log_end")
    for (p, q, r) in (((-0.24, -0.42, 0.16), (0.24, -0.38, 0.16), 0.05), ((-0.22, -0.28, 0.17), (0.22, -0.3, 0.17), 0.048),
                      ((-0.1, -0.45, 0.25), (0.16, -0.25, 0.27), 0.04)):
        lg.rod(p, q, r, seg=10)
        le.rod(Vector(p) + (Vector(p) - Vector(q)).normalized() * 0.002, Vector(p) - (Vector(q) - Vector(p)).normalized() * 0.004, r * 0.92, seg=10)
    fl, fc = a.m("fire", smooth=True), a.m("fire_core", smooth=True)
    for (x, y, h, r) in ((-0.1, -0.35, 0.26, 0.06), (0.05, -0.33, 0.32, 0.07), (0.15, -0.36, 0.22, 0.05), (-0.18, -0.32, 0.18, 0.045)):
        tear = lambda rr, hh: [(0, 0), (rr * 0.8, hh * 0.08), (rr, hh * 0.25), (rr * 0.82, hh * 0.5), (rr * 0.4, hh * 0.8), (0, hh)]
        fl.lathe(tear(r, h), (x, y, 0.2), seg=14)                         # teardrop flames
        fc.lathe(tear(r * 0.55, h * 0.6), (x, y - 0.035, 0.2), seg=12)
    a.build()


def hearth():
    a = A("Hearth stone", (FX, DEPTH - 0.76))     # in front of the 4 cm proud facing stones
    h = a.m("stone_c", bevel=0.012)
    xs = [-0.58, -0.12, 0.3, 0.72]
    for x0, x1 in zip(xs, xs[1:]):
        h.box(x0 + 0.004, x1 - 0.004, -0.45, 0.0, 0.0, 0.05)
    a.build()


def log_basket():
    a = A("Log basket", (-3.28, 4.72))
    a.m("wicker", bevel=0.004).lathe([(0, 0), (0.17, 0), (0.2, 0.3), (0.185, 0.3), (0.158, 0.015), (0, 0.015)], seg=28, closed=False)
    a.m("wicker").torus((0, 0, 0.3), 0.195, 0.012, seg=28, rseg=6)
    lg, le = a.m("log"), a.m("log_end")
    for k, (dx, dy, dz, ang) in enumerate(((-0.06, -0.05, 0.12, 0.2), (0.06, 0.04, 0.12, -0.3), (0.0, 0.0, 0.22, 1.2), (-0.05, 0.07, 0.25, 0.7))):
        d = Vector((math.cos(ang), math.sin(ang), 0.15)).normalized() * 0.2
        c = Vector((dx, dy, dz))
        lg.rod(c - d, c + d, 0.045, seg=9)
        le.rod(c + d, c + d * 1.02, 0.042, seg=9)
    a.build()


def footstool():
    a = A("Hearth footstool", (-3.3, 3.55))
    w = a.m("chair", smooth=True)
    for k in range(4):
        t = math.pi / 4 + k * math.pi / 2
        w.lathe([(0, 0), (0.02, 0), (0.028, 0.06), (0.02, 0.12), (0.025, 0.16), (0, 0.16)], (0.13 * math.cos(t), 0.13 * math.sin(t), 0), seg=10)
    w.lathe([(0, 0.16), (0.2, 0.16), (0.2, 0.19), (0, 0.19)], seg=28)
    a.m("cushion_red", smooth=True).lathe([(0, 0.19), (0.19, 0.19), (0.205, 0.23), (0.19, 0.29), (0.12, 0.305), (0, 0.31)], seg=32)
    a.build()


# ================================================================== reading corner

def lounge_chair(name, x, y, rz, S=1.0):
    """Mid-century lounge chair after the user's photo: chrome tubular frame on glides, taupe leather
    sling, glossy dark-green tufted leather seat and back cushions, bolster headrest, padded arms.
    Built facing -y (back at +y), like the armchairs it replaces."""
    a = A(name, (x, y), rz)
    cr = a.m("chrome", smooth=True)
    R, W = 0.014, 0.36
    for sx in (-1, 1):
        X = sx * W
        cr.rod((X, -0.34, 0.02), (X, -0.34, 0.58), R, seg=12)                 # front leg up to the arm
        cr.rod((X, -0.34, 0.58), (X, 0.10, 0.60), R, seg=12)                  # arm tube
        cr.rod((X, 0.10, 0.60), (X, 0.18, 0.30), R, seg=12)                   # bends down to the seat rail
        cr.rod((X, -0.30, 0.27), (X, 0.24, 0.24), R, seg=12)                  # seat rail
        cr.rod((X, 0.24, 0.24), (X, 0.42, 1.02), R, seg=12)                   # raked back post
        cr.rod((X, 0.30, 0.02), (X, 0.27, 0.25), R, seg=12)                   # rear leg
        for yy in (-0.34, 0.30):
            a.m("glide", smooth=True).lathe([(0, 0), (0.025, 0), (0.022, 0.02), (0, 0.02)], (X, yy, 0), seg=12)
    cr.rod((-W, -0.30, 0.27), (W, -0.30, 0.27), R, seg=12)                    # front stretcher
    cr.rod((-W, 0.42, 1.02), (W, 0.42, 1.02), R, seg=12)                      # top rail
    sl = a.m("leather_taupe", bevel=0.004)
    sl.solid([(-W + 0.01, -0.30, 0.255), (W - 0.01, -0.30, 0.255), (W - 0.01, 0.24, 0.225), (-W + 0.01, 0.24, 0.225)],
             [(-W + 0.01, -0.30, 0.265), (W - 0.01, -0.30, 0.265), (W - 0.01, 0.24, 0.235), (-W + 0.01, 0.24, 0.235)])
    sl.solid([(-W + 0.01, 0.255, 0.24), (W - 0.01, 0.255, 0.24), (W - 0.01, 0.435, 1.0), (-W + 0.01, 0.435, 1.0)],
             [(-W + 0.01, 0.265, 0.235), (W - 0.01, 0.265, 0.235), (W - 0.01, 0.445, 0.995), (-W + 0.01, 0.445, 0.995)])
    gl = a.m("leather_green", bevel=0.035, segments=5, smooth=True)
    top = a.m("leather_green_top", smooth=True)
    bt = a.m("leather_green_dk", smooth=True)
    x0, x1 = -W + 0.035, W - 0.035
    gl.box(x0, x1, -0.36, 0.22, 0.27, 0.38)                                   # seat cushion body
    for p in tufted_top(top, x0, x1, Vector((0, -0.36, 0.38)), Vector((0, 0.58, 0)), Vector((0, 0, 1)), 0,
                        (0.45,), 3, 0.05, depth=0.018, sigma=0.035, nu=50, nv=30):
        bt.ellipsoid(p, (0.01, 0.01, 0.006), seg=8, rings=4)
    bdir = Vector((0, 0.17, 0.72)).normalized()                               # back cushion along the raked post
    base = Vector((0, 0.17, 0.42))
    up = bdir * 0.5
    nrm = Vector((0, -bdir.z, bdir.y))
    gl.solid([(x0, 0.24, 0.40), (x1, 0.24, 0.40), (x1, 0.30, 0.40), (x0, 0.30, 0.40)],
             [(x0, 0.24 + up.y, 0.40 + up.z), (x1, 0.24 + up.y, 0.40 + up.z), (x1, 0.30 + up.y, 0.40 + up.z), (x0, 0.30 + up.y, 0.40 + up.z)])
    for p in tufted_top(top, x0, x1, base, up, nrm, 0, (0.3, 0.62), 3, 0.06, depth=0.02, sigma=0.03, nu=50, nv=40):
        bt.ellipsoid(p, (0.01, 0.006, 0.01), seg=8, rings=4)
    hp = base + up + Vector((0, 0.03, 0.08))                                  # bolster headrest
    gl.rod((x0, hp.y, hp.z), (x1, hp.y, hp.z), 0.075, seg=20)
    for xx in (x0, x1):
        top.ellipsoid((xx, hp.y, hp.z), (0.02, 0.075, 0.075), seg=16, rings=8)
    for sx in (-1, 1):                                                        # padded arms on the arm tubes
        gl.box(sx * W - 0.05, sx * W + 0.05, -0.36, 0.06, 0.6, 0.67)
    e = a.build()
    e.scale = (S, S, S)                          # sized to the chibi figures (user: chairs read too small)
    return e


def rocking_chair(name, x, y, rz, S=1.0):
    """Mid-century rocking lounge chair after the user's photo: cherry rocker side panels, rust boucle
    back cushion, navy boucle seat, brushed-steel arm rods with cherry arm caps. Faces -y (back at +y)."""
    a = A(name, (x, y), rz)
    wd = a.m("rock_wood", bevel=0.006, smooth=True)
    W = 0.33
    prof = []                                                  # side panel: rocker curve below, sloped top
    for k in range(17):
        t = k / 16
        yy = -0.48 + 0.98 * t
        prof.append((yy, 0.10 * (2 * t - 1) ** 2 + 0.02))
    top = [(0.50, 0.30), (0.30, 0.25), (-0.40, 0.33), (-0.48, 0.20)]
    loop = prof + top
    for sx in (-1, 1):
        X = sx * W
        wd.solid([(X - 0.018, yy, zz) for yy, zz in loop], [(X + 0.018, yy, zz) for yy, zz in loop])
    for yy, zz in ((-0.30, 0.20), (0.25, 0.17)):               # stretchers
        wd.beam((-W, yy, zz), (W, yy, zz), 0.04, 0.04)
    seat = a.m("cushion_navy", bevel=0.05, segments=5, smooth=True)
    seat.solid([(-W + 0.03, -0.44, 0.24), (W - 0.03, -0.44, 0.24), (W - 0.03, 0.24, 0.20), (-W + 0.03, 0.24, 0.20)],
               [(-W + 0.03, -0.44, 0.40), (W - 0.03, -0.44, 0.40), (W - 0.03, 0.24, 0.34), (-W + 0.03, 0.24, 0.34)])
    back = a.m("cushion_rust", bevel=0.05, segments=5, smooth=True)
    back.solid([(-W - 0.02, 0.10, 0.32), (W + 0.02, 0.10, 0.32), (W + 0.02, 0.26, 0.28), (-W - 0.02, 0.26, 0.28)],
               [(-W - 0.02, 0.36, 0.95), (W + 0.02, 0.36, 0.95), (W + 0.02, 0.52, 0.91), (-W - 0.02, 0.52, 0.91)])
    wd.box(-W + 0.01, W - 0.01, 0.30, 0.34, 0.25, 0.75)       # back board behind the cushion
    st = a.m("steel", smooth=True)
    for sx in (-1, 1):
        X = sx * (W + 0.03)
        st.rod((X, -0.36, 0.16), (X, -0.30, 0.58), 0.011, seg=10)          # front arm rod from the rocker
        st.rod((X, 0.10, 0.22), (X, 0.0, 0.58), 0.011, seg=10)             # rear arm rod
        st.rod((X, -0.36, 0.16), (X - sx * 0.03, -0.36, 0.16), 0.016, seg=10)   # bolt into the side panel
        st.rod((X, 0.10, 0.22), (X - sx * 0.03, 0.10, 0.22), 0.016, seg=10)
        a.m("rock_wood", bevel=0.006, smooth=True).box(X - 0.03, X + 0.03, -0.38, 0.05, 0.58, 0.61)   # arm cap
    e = a.build()
    e.scale = (S, S, S)
    return e


def log_table():
    """Charred-wood log coffee table after the user's photo: an irregular three-lobed slab of a trunk
    cross-section with radial cracks on a squat round pedestal, all burnt black (shou sugi ban)."""
    a = A("Coffee table", (-0.3, 2.5))
    H, T = 0.42, 0.13
    n = 120
    def rad(t):
        return 0.52 * (1 + 0.16 * math.cos(3 * t + 0.4) + 0.06 * math.cos(5 * t + 1.1) + 0.03 * math.sin(11 * t))
    out = [(rad(2 * math.pi * k / n) * math.cos(2 * math.pi * k / n), rad(2 * math.pi * k / n) * math.sin(2 * math.pi * k / n)) for k in range(n)]
    ch = a.m("charred", bevel=0.012, segments=3, smooth=True)
    ch.solid([(x, y, H - T) for x, y in out], [(x, y, H) for x, y in out])
    ch.lathe([(0, 0), (0.30, 0), (0.33, 0.04), (0.31, H - T - 0.02), (0.26, H - T), (0, H - T)], seg=40)
    dk = a.m("crack")
    for ang, L_ in ((0.9, 0.32), (2.6, 0.22), (4.4, 0.28)):    # radial checks, slightly sunk
        r0 = 0.12
        p0 = (r0 * math.cos(ang), r0 * math.sin(ang))
        p1 = ((r0 + L_) * math.cos(ang + 0.08), (r0 + L_) * math.sin(ang + 0.08))
        dk.beam((p0[0], p0[1], H - 0.001), (p1[0], p1[1], H - 0.001), 0.012, 0.004)
    a.build()


def cesca_chair(name, x, y, rz):
    """Cantilever chair after the user's photo: chrome tube frame (no back legs), walnut-framed cane
    back panel, tufted tan leather seat. Faces -y (back at +y)."""
    a = A(name, (x, y), rz)
    cr = a.m("chrome", smooth=True)
    R, W, SH = 0.012, 0.215, 0.46
    for sx in (-1, 1):
        X = sx * W
        # Cesca cantilever, front = -y: floor runner from the back to the front, up at the front
        # (the cantilever), back under the seat, then up as the back post
        pts = [(0.22, 0.0), (-0.20, 0.0)]
        pts += [(-0.20 - 0.04 * math.sin(t), 0.04 - 0.04 * math.cos(t)) for t in [k * math.pi / 8 for k in range(1, 5)]]
        pts += [(-0.24, SH - 0.095)]
        pts += [(-0.20 - 0.04 * math.cos(t), SH - 0.095 + 0.04 * math.sin(t)) for t in [k * math.pi / 8 for k in range(1, 5)]]
        pts += [(0.16, SH - 0.055)]
        pts += [(0.16 + 0.04 * math.sin(t), SH - 0.055 + 0.04 * (1 - math.cos(t))) for t in [k * math.pi / 8 for k in range(1, 5)]]
        pts += [(0.22, 0.80)]
        sweep_tube(cr, [Vector((X, y_, z_)) for y_, z_ in pts], R)          # one continuous bent tube
        for gy in (-0.20, 0.20):
            a.m("glide", smooth=True).box(X - 0.015, X + 0.015, gy - 0.03, gy + 0.03, -0.004, 0.012)
    sweep_tube(cr, [Vector((-W, 0.22, 0.0)), Vector((W, 0.22, 0.0))], R)            # rear floor bar
    seat = a.m("leather_tan", bevel=0.03, segments=4, smooth=True)
    seat.box(-W - 0.02, W + 0.02, -0.24, 0.20, SH - 0.04, SH + 0.015)
    top = a.m("leather_tan_top", smooth=True)
    bt = a.m("leather_dk", smooth=True)
    for p in tufted_top(top, -W - 0.01, W + 0.01, Vector((0, -0.23, SH + 0.012)), Vector((0, 0.42, 0)), Vector((0, 0, 1)), 0,
                        (0.33, 0.66), 3, 0.025, depth=0.012, sigma=0.03, nu=50, nv=40, crease=0.004):
        bt.ellipsoid(p, (0.006, 0.006, 0.004), seg=6, rings=3)
    wd = a.m("walnut", bevel=0.008, smooth=True)
    yb, z0, z1, BW = 0.22, 0.58, 0.86, W + 0.03
    wd.box(-BW, BW, yb - 0.012, yb + 0.012, z0, z0 + 0.04)
    wd.box(-BW, BW, yb - 0.012, yb + 0.012, z1 - 0.04, z1)
    for sx in (-1, 1):
        wd.box(sx * BW - (0.04 if sx > 0 else 0), sx * BW + (0.04 if sx < 0 else 0), yb - 0.0115, yb + 0.0115, z0 + 0.04, z1 - 0.04)   # stiles between the rails (no shared faces)
    a.m("cane").box(-BW + 0.04, BW - 0.04, yb - 0.002, yb + 0.002, z0 + 0.04, z1 - 0.04)
    a.build()


def coffee_table():
    a = A("Coffee table", (-0.3, 2.5))
    L2, W2, H = 0.575, 0.3, 0.40
    t = a.m("table", bevel=0.005)
    for k in range(3):
        y0 = -W2 + k * 2 * W2 / 3
        t.box(-L2, L2, y0 + 0.002, y0 + 2 * W2 / 3 - 0.002, H - 0.045, H - rng.uniform(0, 0.0015))
    fr = a.m("table", bevel=0.006)
    for s in (-1, 1):
        x = s * 0.45
        fr.box(x - 0.035, x + 0.035, -W2 + 0.02, W2 - 0.02, 0.0, 0.06)            # foot
        fr.box(x - 0.03, x + 0.03, -W2 + 0.03, W2 - 0.03, H - 0.08, H - 0.045)    # top cleat
        for sy in (-1, 1):
            fr.box(x - 0.03, x + 0.03, sy * 0.2 - 0.03, sy * 0.2 + 0.03, 0.06, H - 0.08)
    for sy in (-1, 1):
        fr.box(-0.42, 0.42, sy * 0.2 - 0.02, sy * 0.2 + 0.02, 0.09, 0.12)         # shelf rails
    for k in range(3):
        y0 = -0.24 + k * 0.16
        fr.box(-0.42, 0.42, y0 + 0.003, y0 + 0.16 - 0.003, 0.12, 0.14)            # shelf boards
    # books on the lower shelf
    for k, (w, key) in enumerate(((0.035, "b1"), (0.03, "b4"))):
        a.m(key, bevel=0.003).box(-0.25, 0.0, -0.12, 0.06, 0.14 + k * 0.035, 0.14 + k * 0.035 + w)
    a.build()


def tea_set():
    a = A("Tea set", (-0.3, 2.5, Z + 0.40))
    c = a.m("ceramic", smooth=True)
    c.lathe([(0, 0), (0.055, 0), (0.085, 0.04), (0.08, 0.09), (0.05, 0.12), (0.03, 0.125), (0, 0.125)], (0.15, -0.02, 0), seg=28)
    c.lathe([(0, 0.125), (0.035, 0.125), (0.03, 0.135), (0.012, 0.14), (0.014, 0.16), (0, 0.165)], (0.15, -0.02, 0), seg=16)
    c.rod((0.15 + 0.075, -0.02, 0.05), (0.15 + 0.15, -0.02, 0.115), 0.016, seg=10, r2=0.008)          # spout
    c.torus((0.15 - 0.095, -0.02, 0.075), 0.04, 0.009, seg=14, rseg=6, axis='y')                        # handle
    for (x, y) in ((0.38, 0.15), (0.03, -0.18)):
        c.lathe([(0, 0), (0.07, 0), (0.075, 0.012), (0.068, 0.012), (0.03, 0.004), (0, 0.004)], (x, y, 0), seg=24)   # saucer
        c.lathe([(0, 0.006), (0.03, 0.006), (0.042, 0.06), (0.037, 0.06), (0.027, 0.012), (0, 0.012)], (x, y, 0), seg=20)
        c.torus((x + 0.05, y, 0.035), 0.016, 0.005, seg=10, rseg=5, axis='y')
    a.build()


# ================================================================== bookcase, desk, plants
def bookcase():
    a = A("Bookcase", (3.27, DEPTH))
    W2, D, H = 0.825, 0.40, 1.97
    c = a.m("cab", bevel=0.004)
    c.box(-W2 + 0.02, W2 - 0.02, -D + 0.03, 0, 0, 0.08)                       # plinth
    for s in (-1, 1):
        c.box(s * W2 - (0.025 if s > 0 else 0), s * W2 + (0.025 if s < 0 else 0), -D, 0, 0, H)
    c.box(-W2 - 0.025, W2 + 0.025, -D - 0.025, 0, H, H + 0.03)               # crown
    c.box(-W2, W2, -0.012, 0, 0.08, H)                                        # back panel
    c.box(-W2 + 0.025, W2 - 0.025, -D + 0.02, 0, 0.08, 0.1)                   # cabinet floor
    c.box(-W2, W2, -D - 0.015, 0, 0.78, 0.8)                                  # counter shelf
    for zb in (1.18, 1.58):
        c.box(-W2 + 0.025, W2 - 0.025, -D + 0.02, 0, zb, zb + 0.022)
    for s in (-1, 1):                                                          # cabinet doors
        xa, xb = (-W2 + 0.028, -0.003) if s < 0 else (0.003, W2 - 0.028)
        c.box(xa, xb, -D, -D + 0.02, 0.1, 0.775)
        c.box(xa + 0.06, xb - 0.06, -D - 0.008, -D, 0.17, 0.705)
        a.m("brass", smooth=True).lathe([(0, 0), (0.014, 0), (0.016, 0.02), (0, 0.028)], (s * 0.06, -D, 0.44), axis='-y', seg=10)
    # Tidy shelves: books stand in colour runs with matched heights, spines flush with the shelf front,
    # and each shelf has one quiet accent (a flat stack, a vase, a pair of jars) instead of scattered decor.
    FRONT = -D + 0.06                       # spine line, 6 cm behind the shelf edge
    def book_run(x, x_end, zb, height, colors, depth=0.19):
        return ic.book_run(a, x, x_end, zb, height, colors, FRONT, depth)
    def bookend(x, zb):
        a.m("iron", bevel=0.002).box(x, x + 0.006, FRONT + 0.02, FRONT + 0.16, zb, zb + 0.16)
        a.m("iron").box(x - 0.1, x + 0.006, FRONT + 0.02, FRONT + 0.16, zb, zb + 0.004)
    def flat_stack(x, zb, colors):
        z = zb
        for k, c in enumerate(colors):
            th = 0.03 + 0.004 * (k % 2)
            w = 0.24 - 0.02 * k
            a.m(c, bevel=0.002).box(x - w / 2, x + w / 2, FRONT, FRONT + 0.17 - 0.01 * k, z, z + th)
            z += th
        return z
    L, R = -W2 + 0.03, W2 - 0.03
    # bottom shelf: two runs of tall books, a pair of jars at the right end
    zb = 0.8
    x = book_run(L, L + 0.62, zb, 0.28, ["b1", "b6"])
    x = book_run(x + 0.02, R - 0.26, zb, 0.27, ["b3", "b4"])
    for k in range(2):
        cx = R - 0.19 + k * 0.11
        a.m("glass", smooth=True).lathe([(0, zb), (0.045, zb), (0.045, zb + 0.13), (0, zb + 0.13)], (cx, FRONT + 0.09, 0), seg=16)
        a.m("jar_lid").lathe([(0, zb + 0.13), (0.04, zb + 0.13), (0.04, zb + 0.15), (0, zb + 0.15)], (cx, FRONT + 0.09, 0), seg=16)
    # middle shelf: one long run held by a bookend, a flat stack on the right
    zb = 1.202
    x = book_run(L, R - 0.36, zb, 0.25, ["b2", "b6", "b5"])
    bookend(x + 0.002, zb)
    flat_stack(R - 0.16, zb, ["b1", "b6", "b4"])
    # top shelf: books either side of a single vase
    zb = 1.602
    x = book_run(L, -0.14, zb, 0.24, ["b4", "b3"])
    a.m("ceramic", smooth=True).lathe([(0, zb), (0.045, zb), (0.06, zb + 0.07), (0.035, zb + 0.17), (0.04, zb + 0.2), (0, zb + 0.19)],
                                      (0.0, FRONT + 0.09, 0), seg=20)
    book_run(0.14, R, zb, 0.24, ["b6", "b1"])
    a.build()


def desk():
    """Longer, deeper walnut writing desk (10-20, user): 2.4 x 0.9 m, tapered legs, drawer apron."""
    a = A("Desk", (IN_X - 0.45, 2.05))
    X2, Y2, H = 0.45, 1.2, TABLE_H
    t = a.m("walnut", bevel=0.006)
    t.box(-X2, X2, -Y2, Y2, H - 0.035, H)
    fr = a.m("walnut", bevel=0.005)
    lx, ly = X2 - 0.06, Y2 - 0.06
    for sx in (-1, 1):
        for sy in (-1, 1):
            fr.beam((sx * lx, sy * ly, 0), (sx * lx, sy * ly, H - 0.035), 0.038, 0.038, w2=0.055, h2=0.055)
    fr.box(lx - 0.03, lx - 0.01, -ly + 0.03, ly - 0.03, H - 0.15, H - 0.035)        # back apron
    for s in (-1, 1):
        fr.box(-lx + 0.03, lx - 0.03, s * ly - 0.01, s * ly + 0.01, H - 0.15, H - 0.035)
    fr.box(-lx + 0.01, -lx + 0.03, -ly + 0.03, ly - 0.03, H - 0.15, H - 0.035)       # front apron with drawers
    for s in (-1, 1):
        fr.box(-lx - 0.005, -lx + 0.01, s * 0.55 - 0.3, s * 0.55 + 0.3, H - 0.14, H - 0.045)
        a.m("brass", smooth=True).lathe([(0, 0), (0.012, 0), (0.014, 0.018), (0, 0.024)], (-lx - 0.005, s * 0.55, H - 0.093), axis='x', seg=10)
    # all-in-one computer facing the chair (-x)
    al, sc_ = a.m("alu", bevel=0.004), a.m("screen")
    al.box(0.08, 0.26, -0.1, 0.1, H, H + 0.008)
    al.beam((0.2, 0, H + 0.005), (0.13, 0, H + 0.24), 0.12, 0.012, side=(0, 1, 0))
    al.box(0.07, 0.095, -0.31, 0.31, H + 0.12, H + 0.58)
    sc_.box(0.066, 0.07, -0.295, 0.295, H + 0.185, H + 0.565)
    # keyboard with keys, mouse, mug, notebook and pencil
    al.box(-0.23, -0.1, -0.21, 0.21, H, H + 0.012)
    k = a.m("key", bevel=0.002, segments=1)
    for r in range(5):
        for cidx in range(15):
            y0 = -0.2 + cidx * 0.0265
            x0 = -0.222 + r * 0.0245
            k.box(x0, x0 + 0.019, y0, y0 + 0.021, H + 0.012, H + 0.019)
    a.m("key", smooth=True).ellipsoid((-0.16, 0.32, H + 0.012), (0.055, 0.032, 0.016), seg=12, rings=6)
    c = a.m("ceramic", smooth=True)
    c.lathe([(0, 0), (0.04, 0), (0.042, 0.1), (0.036, 0.1), (0.034, 0.008), (0, 0.008)], (-0.05, -0.62, H), seg=20)
    c.torus((-0.05, -0.62 - 0.05, H + 0.05), 0.025, 0.007, seg=12, rseg=5, axis='x')
    a.m("b2", bevel=0.002).box(-0.27, -0.06, -0.52, -0.3, H, H + 0.015)
    a.m("paper").box(-0.265, -0.065, -0.515, -0.305, H + 0.015, H + 0.018)
    a.m("b4").rod((-0.24, -0.33, H + 0.024), (-0.1, -0.4, H + 0.024), 0.004, seg=6)
    a.build()



# ================================================================== build everything
# 10-20: fireplace, hearth and log basket removed (user); the chimney above is unchanged for now
footstool()
# 10-20 (user): left chair is a rocking lounge chair, right one the green leather chair; both sized up
# 1.35x so they read larger than the chibi figures; charred log coffee table; real (Poly Haven) props
CHAIR_S = 1.1                                          # user: 1.35 then 1.18 read too big
rocking_chair("Armchair reading", -2.55, 2.65, math.radians(60), S=CHAIR_S)
lounge_chair("Armchair guest", 1.75, 2.85, math.radians(-60), S=CHAIR_S)
log_table()
ph_model("ceramic_pot", "Table crock", (-0.15, 2.45, Z + 0.42), 0.32, 0.6)
ph_model("carved_wooden_plate", "Table plate", (-0.5, 2.6, Z + 0.42), 1.0, 0.3)
a_, b_, s_, h_ = WIN_BACK[2]
wood_blinds("Back window blind", ((a_ + b_) / 2, DEPTH, Z), 0.0, b_ - a_, s_, h_, drop=h_ - 0.5)   # raised: let the daylight in
sheer_panels("Back window sheers", a_, b_, h_, DEPTH)
for sx in (-1, 1):                                    # side windows: blinds only
    yc = SIDE_WIN[(2, sx)]
    wood_blinds(f"Side window blind {'L' if sx < 0 else 'R'}", (sx * IN_X, yc, Z), math.radians(90 if sx < 0 else -90),
                side_win_w(2, sx), side_win_sill(2, sx), side_win_head(2, sx), drop=side_win_head(2, sx) - 0.5)
bookcase()
desk()
cesca_chair("Desk chair", IN_X - 1.22, 2.05, math.radians(90))   # cane-back cantilever chair (user photo)
ph_model("jug_01", "Desk jug", (IN_X - 0.3, 2.05 + 0.95, Z + TABLE_H), 0.8, 2.0)
stool("Plant stool", IN_X - 0.4, 0.45, H=0.45, seat="chair")
ph_planted("calathea_orbifolia_01", "_b", "Plant on stool", (IN_X - 0.4, 0.45, Z + 0.45), 1.0, 0.5)
ph_model("potted_plant_01", "Window plant", (-0.95, 4.4, Z), 0.95, 2.2)   # swapped with the corner plant, lower (user)
ph_planted("pachira_aquatica_01", "_c", "Corner plant", (-4.3, 0.9, Z), 0.95, 0.7, 4.0)
rug("Living rug", -0.6, 2.7, w=5.0, d=2.2)
sconce("Wall sconce left", -2.95, 1.5)              # moved out of the wider window's sheers; the right one was removed

look_cam("Cam_F2_Hearth", (-1.4, 3.35, Z + 1.3), (-4.1, 4.4, Z + 0.65), 26)
look_cam("Cam_F2_Reading", (0.3, 0.9, Z + 1.5), (-1.2, 2.9, Z + 0.55), 28)
look_cam("Cam_F2_Bookcase", (1.6, 2.4, Z + 1.45), (3.3, DEPTH, Z + 1.0), 28)
look_cam("Cam_F2_Desk", (2.3, 0.45, Z + 1.5), (4.3, 2.0, Z + 0.75), 28)
ic.finish("F2_SAVED")
