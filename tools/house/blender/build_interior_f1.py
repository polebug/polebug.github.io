"""Stage 3, floor 1: detailed dining room and kitchen.

Run after build_architecture.py:
    Blender -b assets/blender/companion-house.blend --python build_interior_f1.py
Replaces the whitebox collection 03_Floor1 with 21_Floor1 and saves in place. Every asset is an
empty (named "F1 ...") with one child mesh per material, built in local coordinates; positions and
sizes follow the approved whitebox (docs/3d-modeling-plan.md, section 3).
"""
import bpy, math, random, os, sys
from mathutils import Vector, Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from house_spec import *   # noqa: E402,F403

import interior_common as ic  # noqa: E402
from interior_common import (ph_planted, P, ladder_chair, vase_with_flowers, curtains, shelf, sconce, rug, wood_blinds, sheer_panels, tufted_top, ph_model,  # noqa: E402
                             stool, look_cam)
A = ic.setup(1, "21_Floor1", "03_Floor1", seed=101)
Z, CEIL, rng = ic.Z, ic.CEIL, ic.rng

# ================================================================== living-dining (10-20 refit)
# After the user's reference photos (warm mid-century living room): wall-hung TV over a low walnut
# console (navy fluted outer doors, arched glass middle doors); tufted cognac leather sofa facing it
# with the walnut dining table standing right behind its back; two leather soft-pad office chairs on
# the far side of the table and a round leather pouf; one large vintage rug under sofa and table;
# honey wooden venetian blinds with sheer side panels; linear walnut pendant over the table and a
# brass floor lamp with a pleated shade. The small ornaments of the photos are left out on purpose.
P.update({
    "walnut": (0.40, 0.22, 0.13), "black_lacq": (0.03, 0.03, 0.03), "leather": (0.46, 0.21, 0.09), "leather_dk": (0.26, 0.11, 0.05), "leather_top": (0.46, 0.21, 0.09),
    "leather_seat": (0.46, 0.21, 0.09), "leather_pillow": (0.46, 0.21, 0.09),
    "leather_tan": (0.62, 0.30, 0.14),  "navy": (0.10, 0.13, 0.20), "rug_vintage": (0.80, 0.70, 0.58),
    "blind": (0.78, 0.46, 0.20), "tape": (0.86, 0.80, 0.68), "shade_green": (0.24, 0.30, 0.20),
    "accent_red": (0.75, 0.10, 0.08), "accent_green": (0.30, 0.48, 0.30), "marble": (0.88, 0.86, 0.82),
})
# layout (user, 10-20): TV on the left wall (its window removed), sofa facing it, the only table on
# this floor standing right behind the sofa's back, chairs on the table's far side
LV_Y = 2.5                          # centre line (y) of TV, sofa and table
SOFA_X, TABLE_X = -1.45, 0.75     # table moved next to the kitchen, same direction (user)


def tv_and_console():
    """TV wall after the user's photo: a large thin-bezel TV hung on the wall over a long, low media
    console - satin-black carcass on a recessed black plinth, three walnut drawers with round cut-out
    pulls on the left, two fluted walnut doors with carved finger pulls on the right."""
    a = A("TV console", (-IN_X, LV_Y), math.radians(90))     # local -y = into the room (+x)
    W, D, H, PL = 2.4, 0.42, 0.50, 0.09
    bk = a.m("black_lacq", bevel=0.003)
    bk.box(-W / 2 + 0.07, W / 2 - 0.07, -D + 0.05, -0.02, 0.0, PL)                 # recessed plinth
    bk.box(-W / 2, W / 2, -D, 0, H - 0.025, H)                                      # top
    bk.box(-W / 2, W / 2, -D, 0, PL, PL + 0.02)                                     # bottom
    for x in (-W / 2, -W / 2 + 0.75, W / 2 - 0.02):
        bk.box(x, x + 0.02, -D, 0, PL, H)                                           # sides and divider
    bk.box(-W / 2, W / 2, -0.015, 0, PL, H)                                         # back
    wd = a.m("walnut", bevel=0.002)
    pull = a.m("black_lacq", smooth=True)
    z0, z1 = PL + 0.02, H - 0.025
    xa, xb = -W / 2 + 0.02, -W / 2 + 0.75
    hs = [z0, z0 + 0.155, z0 + 0.255, z1]                                           # deep, shallow, shallow (bottom up)
    for k, (za, zb) in enumerate(zip(hs, hs[1:])):
        wd.box(xa + 0.003, xb - 0.003, -D - 0.004, -D + 0.016, za + 0.003, zb - 0.003)
        pull.lathe([(0, 0), (0.022, 0), (0.022, 0.012), (0, 0.012)], ((xa + xb) / 2, -D - 0.004, (za + zb) / 2), axis='-y', seg=20)
    fl = a.m("walnut", smooth=True)
    xa, xb = -W / 2 + 0.77, W / 2 - 0.02
    xm = (xa + xb) / 2
    for side in ((xa, xm), (xm, xb)):                                               # fluted doors
        da, db = side[0] + 0.003, side[1] - 0.003
        wd.box(da, db, -D + 0.004, -D + 0.016, z0 + 0.003, z1 - 0.003)
        n = int((db - da) / 0.018)
        for k in range(n):
            x = da + (k + 0.5) * (db - da) / n
            fl.rod((x, -D + 0.004, z0 + 0.006), (x, -D + 0.004, z1 - 0.006), 0.0085, seg=8)
    for sx in (-1, 1):                                                              # carved finger pulls at the meeting edges
        wd.beam((xm + sx * 0.012, -D - 0.006, z0 + 0.12), (xm + sx * 0.012, -D - 0.006, z1 - 0.06), 0.014, 0.02)
    # large wall-hung TV (75", 1.66 x 0.94 m), thin black bezel
    tv, scr = a.m("iron", bevel=0.002), a.m("black_glass")
    TW, TH, tz = 1.66, 0.94, 0.88
    tv.box(-TW / 2, TW / 2, -0.045, -0.02, tz, tz + TH)
    tv.box(-0.25, 0.25, -0.02, 0, tz + 0.25, tz + 0.65)                             # wall bracket
    scr.box(-TW / 2 + 0.008, TW / 2 - 0.008, -0.047, -0.045, tz + 0.008, tz + TH - 0.008)
    a.build()


def leather_sofa():
    """Chestnut leather sofa after the user's photo: low and deep, one overstuffed deep-tufted seat,
    three plump tufted pillow back cushions, chunky rounded square arms with buttons on the front;
    built facing -y, turned to face the TV."""
    a = A("Leather sofa", (SOFA_X, LV_Y), math.radians(-90))  # faces the TV (-x)
    W, D, AW, AH, SEAT = 2.3, 1.0, 0.26, 0.58, 0.42
    body = a.m("leather", bevel=0.09, segments=6, smooth=True)   # separate keys per part: each key keeps its own bevel/smooth options
    body.box(-W / 2 + 0.03, W / 2 - 0.03, -D / 2 + 0.05, D / 2 - 0.03, 0.04, 0.26)               # low base
    body.box(-W / 2 + AW - 0.02, W / 2 - AW + 0.02, D / 2 - 0.24, D / 2, 0.22, 0.66)         # back frame
    for sx in (-1, 1):                                                                         # chunky arms
        x0, x1 = (-W / 2, -W / 2 + AW) if sx < 0 else (W / 2 - AW, W / 2)
        body.box(x0, x1, -D / 2, D / 2, 0.04, AH)
    top = a.m("leather_top", smooth=True)
    bt = a.m("leather_dk", smooth=True)
    xs0, xs1 = -W / 2 + AW + 0.004, W / 2 - AW - 0.004
    seat = a.m("leather_seat", bevel=0.06, segments=6, smooth=True)
    seat.box(xs0, xs1, -D / 2 + 0.03, D / 2 - 0.25, 0.24, SEAT - 0.04)                          # seat block
    for p in tufted_top(top, xs0, xs1, Vector((0, -D / 2 + 0.03, SEAT - 0.04)), Vector((0, D - 0.28, 0)),
                        Vector((0, 0, 1)), 0, (0.25, 0.5, 0.75), 8, 0.07, depth=0.022, sigma=0.03, nu=200, nv=70):
        bt.ellipsoid(p, (0.01, 0.01, 0.006), seg=8, rings=4)
    # three plump back cushions leaning on the back frame
    cw = (xs1 - xs0) / 3
    lean = Vector((0, 0.16, 0.42))
    nrm = Vector((0, -lean.z, lean.y)).normalized()
    pil = a.m("leather_pillow", bevel=0.08, segments=6, smooth=True)
    for k in range(3):
        x0, x1 = xs0 + k * cw + 0.008, xs0 + (k + 1) * cw - 0.008
        y0, z0 = D / 2 - 0.36, SEAT - 0.02
        pil.solid([(x0, y0, z0), (x1, y0, z0), (x1, y0 + 0.16, z0), (x0, y0 + 0.16, z0)],
                  [(x0, y0 + lean.y, z0 + lean.z), (x1, y0 + lean.y, z0 + lean.z), (x1, y0 + 0.16 + lean.y, z0 + lean.z), (x0, y0 + 0.16 + lean.y, z0 + lean.z)])
        base = Vector((0, y0, z0)) + nrm * 0.0
        for p in tufted_top(top, x0 + 0.04, x1 - 0.04, base + Vector((0, 0, 0.04)), lean * 0.82, nrm, 0, (0.25, 0.52, 0.79), 2, 0.06,
                            depth=0.02, sigma=0.03, nu=80, nv=70, crease=0.006):
            bt.ellipsoid(p, (0.01, 0.006, 0.01), seg=8, rings=4)
    for sx in (-1, 1):                                                                         # buttons on the arm fronts
        xm = sx * (W / 2 - AW / 2)
        for z in (0.22, 0.42):
            bt.ellipsoid((xm, -D / 2 - 0.004, z), (0.01, 0.006, 0.01), seg=8, rings=4)
    a.build()


def walnut_table():
    """Mid-century walnut dining table: apron and four tapered, slightly splayed legs."""
    a = A("Dining table", (TABLE_X, LV_Y), math.radians(90))
    L, W, H, T = 1.8, 0.9, TABLE_H, 0.035
    wd = a.m("walnut", bevel=0.008, segments=3)
    wd.box(-L / 2, L / 2, -W / 2, W / 2, H - T, H)
    fr = a.m("walnut", bevel=0.004)
    for sy in (-1, 1):
        fr.box(-L / 2 + 0.12, L / 2 - 0.12, sy * (W / 2 - 0.08) - 0.011, sy * (W / 2 - 0.08) + 0.011, H - T - 0.09, H - T)
    for sx in (-1, 1):
        fr.box(sx * (L / 2 - 0.12) - 0.011, sx * (L / 2 - 0.12) + 0.011, -W / 2 + 0.08, W / 2 - 0.08, H - T - 0.09, H - T)
    for sx in (-1, 1):
        for sy in (-1, 1):
            fr.beam((sx * (L / 2 - 0.14), sy * (W / 2 - 0.1), H - T), (sx * (L / 2 - 0.08), sy * (W / 2 - 0.06), 0), 0.055, 0.055, w2=0.032, h2=0.032)
    a.build()


def dining_chair(name, x, y, rz):
    """Mid-century walnut dining chair, tan leather seat, bent-plywood back rail; faces -y when rz = 0."""
    a = A(name, (x, y), rz)
    wd = a.m("walnut", bevel=0.004)
    SH, S = 0.45, 0.44
    for sx in (-1, 1):
        wd.beam((sx * 0.18, -0.17, SH - 0.05), (sx * 0.21, -0.21, 0), 0.035, 0.035, w2=0.022, h2=0.022)   # front legs
        wd.beam((sx * 0.18, 0.17, SH - 0.05), (sx * 0.21, 0.23, 0), 0.035, 0.035, w2=0.022, h2=0.022)    # back legs
        wd.beam((sx * 0.18, 0.17, SH - 0.05), (sx * 0.19, 0.22, 0.84), 0.03, 0.03)                         # back posts
    wd.box(-S / 2, S / 2, -S / 2, S / 2 - 0.02, SH - 0.08, SH - 0.04)                                     # seat frame
    seg = 14
    for k in range(seg):                                                                                 # curved back rail
        t0, t1 = -0.5 + k / seg, -0.5 + (k + 1) / seg
        p0 = Vector((t0 * 0.46, 0.21 + 0.06 * (2 * t0) ** 2, 0.66))
        p1 = Vector((t1 * 0.46, 0.21 + 0.06 * (2 * t1) ** 2, 0.66))
        wd.beam(p0, p1, 0.016, 0.14)
    a.m("leather_tan", bevel=0.025, segments=4).box(-S / 2 + 0.01, S / 2 - 0.01, -S / 2 + 0.01, S / 2 - 0.03, SH - 0.04, SH + 0.02)
    a.build()

def softpad_chair(name, x, y, rz):
    """Mid-century soft-pad office chair: leather pads on an aluminium frame, five-star base.
    Built with its back at +y (facing -y); rz = pi turns it to face +y."""
    a = A(name, (x, y), rz)
    pad = a.m("leather_tan", bevel=0.025, segments=4)
    al = a.m("chrome", smooth=True)
    SH, W = 0.47, 0.48
    for k in range(4):                                                     # seat pads
        y0 = -0.22 + k * 0.11
        pad.box(-W / 2 + 0.02, W / 2 - 0.02, y0, y0 + 0.105, SH - 0.06, SH)
    for k in range(4):                                                     # back pads, leaning back
        z0 = SH + 0.06 + k * 0.11
        yb = 0.24 + 0.03 * k
        pad.box(-W / 2 + 0.02, W / 2 - 0.02, yb - 0.06, yb, z0, z0 + 0.105)
    for sx in (-1, 1):                                                     # side frames and arms
        al.beam((sx * W / 2, -0.24, SH - 0.03), (sx * W / 2, 0.24, SH - 0.03), 0.015, 0.05)
        al.beam((sx * W / 2, 0.24, SH - 0.03), (sx * W / 2, 0.36, SH + 0.47), 0.015, 0.05)
        al.beam((sx * W / 2, 0.14, SH - 0.02), (sx * W / 2 + sx * 0.01, 0.16, SH + 0.2), 0.012, 0.02)
        pad.box(sx * W / 2 - 0.035, sx * W / 2 + 0.035, -0.18, 0.2, SH + 0.2, SH + 0.235)   # arm pad
    al.rod((0, 0, 0.12), (0, 0, SH - 0.06), 0.025, seg=12)
    al.lathe([(0, 0.1), (0.06, 0.1), (0.04, 0.14), (0, 0.14)], seg=16)
    cas = a.m("iron", smooth=True)
    for k in range(5):
        t = 2 * math.pi * k / 5
        p = Vector((0.32 * math.cos(t), 0.32 * math.sin(t), 0.055))
        al.beam((0, 0, 0.12), p, 0.035, 0.03, w2=0.025, h2=0.02)
        cas.torus(p + Vector((0, 0, -0.025)), 0.022, 0.012, seg=10, rseg=6, axis='x')
    a.build()


def leather_pouf(name, x, y):
    a = A(name, (x, y))
    lt = a.m("leather_dk", smooth=True)
    R, H = 0.23, 0.42
    lt.lathe([(0, 0.02), (R - 0.02, 0.02), (R, 0.06), (R + 0.005, H / 2), (R, H - 0.05), (R - 0.04, H - 0.005), (0, H + 0.01)], seg=40)
    bt = a.m("leather", smooth=True)
    for k in range(6):
        t = 2 * math.pi * k / 6
        bt.ellipsoid((0.12 * math.cos(t), 0.12 * math.sin(t), H - 0.005), (0.01, 0.01, 0.006), seg=8, rings=4)
    bt.ellipsoid((0, 0, H + 0.008), (0.01, 0.01, 0.006), seg=8, rings=4)
    a.build()


def big_rug():
    """One large natural jute rug in front of the sofa (after the user's photo)."""
    a = A("Living rug", (-2.4, LV_Y))
    w, d = 3.0, 2.6
    a.m("jute", bevel=0.004).box(-w / 2, w / 2, -d / 2, d / 2, 0.0, 0.012)
    a.build()


def linear_pendant():
    a = A("Dining pendant", (TABLE_X, LV_Y), math.radians(90))
    C = CEIL - Z
    zb = 1.45
    wd = a.m("walnut", bevel=0.006)
    wd.box(-0.6, 0.6, -0.03, 0.03, zb, zb + 0.035)
    wd.box(-0.35, 0.35, -0.04, 0.04, C - 0.04, C)                          # ceiling canopy
    a.m("bulb").box(-0.58, 0.58, -0.018, 0.018, zb - 0.002, zb)
    ir = a.m("iron")
    for x in (-0.3, 0.3):
        ir.rod((x, 0, zb + 0.035), (x, 0, C - 0.04), 0.0015, seg=4)
    a.m("accent_red", smooth=True).ellipsoid((-0.3, 0, zb + 0.3), (0.035, 0.035, 0.035), seg=14, rings=8)
    a.m("iron").rod((-0.3, 0, zb + 0.265), (-0.3, 0, zb + 0.2), 0.008, seg=8)
    a.m("accent_green", smooth=True).lathe([(0, 0), (0.035, 0), (0, 0.11)], (0.3, 0, zb + 0.18), seg=16)
    a.build()


def floor_lamp():
    """Brass floor lamp: weighted base, pole, angled arm and a pleated dark-green shade."""
    a = A("Floor lamp", (SOFA_X, LV_Y + 1.45), math.radians(-90))   # arm reaches over the sofa end
    a.m("marble", smooth=True).lathe([(0, 0), (0.15, 0), (0.15, 0.03), (0.13, 0.04), (0, 0.04)], seg=32)
    br = a.m("brass", smooth=True)
    br.rod((0, 0, 0.04), (0, 0, 1.25), 0.012, seg=10)
    tip = Vector((0.55, -0.25, 1.62))
    br.rod((0, 0, 1.0), tip, 0.009, seg=10)
    br.ellipsoid((0, 0, 1.0), (0.02, 0.02, 0.02), seg=10, rings=6)
    sh = a.m("shade_green", smooth=False)
    n = 28
    top_r, bot_r, h = 0.05, 0.2, 0.17
    c = tip + Vector((0, 0, -0.02))
    for k in range(n):                                                    # pleats: alternating radii
        t0, t1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        f0, f1 = (1.0 if k % 2 == 0 else 0.93), (0.93 if k % 2 == 0 else 1.0)
        pts_top = [c + Vector((top_r * math.cos(t), top_r * math.sin(t), 0)) for t in (t0, t1)]
        pts_bot = [c + Vector((bot_r * f * math.cos(t), bot_r * f * math.sin(t), -h)) for t, f in ((t0, f0), (t1, f1))]
        sh.solid([pts_bot[0], pts_bot[1], pts_top[1], pts_top[0]],
                 [pts_bot[0] + Vector((0, 0, 0.002)), pts_bot[1] + Vector((0, 0, 0.002)), pts_top[1] + Vector((0, 0, 0.002)), pts_top[0] + Vector((0, 0, 0.002))])
    a.m("bulb", smooth=True).ellipsoid(c + Vector((0, 0, -0.08)), (0.03, 0.03, 0.04), seg=10, rings=6)
    a.build()

# ================================================================== window, shelves, plants, light, rugs


def climbing_plant():
    a = A("Climbing plant", (-4.3, 0.7))
    a.m("terracotta", bevel=0.004).lathe([(0, 0), (0.13, 0), (0.17, 0.25), (0.19, 0.25), (0.19, 0.29), (0.155, 0.29), (0.155, 0.27), (0, 0.27)], seg=24)
    a.m("soil").lathe([(0, 0.255), (0.155, 0.255), (0.155, 0.265), (0, 0.265)], seg=24)
    bam = a.m("bamboo")
    stakes = [(-0.08, -0.06), (0.09, -0.04), (0.0, 0.09)]
    for sx, sy in stakes:
        bam.rod((sx, sy, 0.2), (sx * 0.6, sy * 0.6, 1.85), 0.009, seg=6)
    for zz in (0.75, 1.25, 1.7):
        for k in range(3):
            p0, p1 = stakes[k], stakes[(k + 1) % 3]
            f = (zz - 0.2) / 1.65
            s0, s1 = 1 - 0.4 * f, 1 - 0.4 * f
            bam.rod((p0[0] * s0, p0[1] * s0, zz), (p1[0] * s1, p1[1] * s1, zz), 0.005, seg=5)
    st, lf, lf2 = a.m("stem"), a.m("leaf", smooth=True), a.m("leaf_dark", smooth=True)
    for vine in range(3):
        prev = None
        for k in range(40):
            t = k / 39
            ang = vine * 2.1 + t * 9.0
            rad = 0.12 * (1 - 0.35 * t)
            p = Vector((math.cos(ang) * rad, math.sin(ang) * rad, 0.27 + t * 1.6))
            if prev is not None:
                st.rod(prev, p, 0.004, seg=5)
            prev = p
            if k % 2 == 0:
                out = Vector((math.cos(ang), math.sin(ang), 0))
                leaf_c = p + out * 0.05 + Vector((0, 0, rng.uniform(-0.02, 0.02)))
                rot = Matrix.Rotation(ang, 3, 'Z') @ Matrix.Rotation(rng.uniform(0.3, 0.8), 3, 'Y')
                (lf if rng.random() < 0.6 else lf2).ellipsoid(leaf_c, (0.05, 0.03, 0.005), seg=8, rings=4, rot=rot)
    a.build()



# ================================================================== kitchen
# 10-20 refit after the user's reference photos (natural mid-century kitchen): L-shaped run of
# cherry-veneer slab fronts with stainless bar pulls on the drawers and round knobs on the doors,
# recessed plinth, light travertine worktop, vertical finger-tile splashback, built-in gas hob with a
# slim stainless hood under a wall cabinet, dark-wood open shelves with a utensil rail and woven
# basket, a magnetic knife strip, undermount sink with a tall cream tap under the side window and a
# white gauze cafe curtain on ring clips. Props from Poly Haven (CC0): enamel pot, jug, potted
# plant, ceramic pot, carved plate, lemons.
CH = COUNTER_H
KD = 0.62                     # base cabinet depth
KX0 = SX - 0.40               # back run starts at the left edge of the hob drawers
HOOD_Z0, WALLCAB_Z0, WALLCAB_Z1 = 1.40, 1.62, 2.05
SPLASH_Z1 = HOOD_Z0
SHELF_X0, SHELF_X1 = SX + 0.40, SX + 1.20
P.update({
    "cab_cherry": (0.62, 0.35, 0.21), "shelf_dark": (0.40, 0.22, 0.14), "worktop_stone": (0.90, 0.85, 0.77),
    "tile_finger": (0.93, 0.91, 0.84), "steel": (0.80, 0.80, 0.80), "black_glass": (0.05, 0.05, 0.06),
    "gauze": (0.97, 0.97, 0.96), "basket": (0.80, 0.60, 0.32), "glass": (0.80, 0.85, 0.85),
    "knife_handle": (0.30, 0.20, 0.13), "oil": (0.82, 0.68, 0.25), "tap": (0.93, 0.91, 0.85),
})
MODELS = os.path.join(os.path.dirname(bpy.data.filepath), "models")




def slab_fronts(a, kind, xa, xb, depth):
    """Flat cherry slab fronts on a base cabinet bay (local frame: front face at y = -depth)."""
    fr, hd = a.m("cab_cherry", bevel=0.002), a.m("steel", smooth=True)
    y0, y1 = -depth - 0.019, -depth
    if kind == "drawers":                         # three deep drawers, long bar pulls near the top
        zs = [0.1, 0.33, 0.55, CH - 0.035]
        for z0, z1 in zip(zs, zs[1:]):
            fr.box(xa + 0.0015, xb - 0.0015, y0, y1, z0 + 0.0015, z1 - 0.0015)
            zc, half = z1 - 0.05, min(0.17, (xb - xa) / 2 - 0.08)
            xm = (xa + xb) / 2
            hd.rod((xm - half, y0 - 0.03, zc), (xm + half, y0 - 0.03, zc), 0.006, seg=10)
            for sx in (-1, 1):
                hd.rod((xm + sx * half, y0, zc), (xm + sx * half, y0 - 0.03, zc), 0.0055, seg=8)
    elif kind in ("door2", "door1", "sink"):     # tall slab doors, knob at the upper inner corner
        n = 1 if kind == "door1" else 2
        w = (xb - xa) / n
        for k in range(n):
            da, db = xa + k * w + 0.0015, xa + (k + 1) * w - 0.0015
            fr.box(da, db, y0, y1, 0.1015, CH - 0.0365)
            kx = db - 0.04 if (n == 2 and k == 0) or n == 1 else da + 0.04
            hd.lathe([(0, 0), (0.006, 0), (0.006, 0.014), (0.016, 0.02), (0.017, 0.03), (0.012, 0.036), (0, 0.037)],
                     (kx, y0, CH - 0.11), axis='-y', seg=14)
    elif kind == "panel":
        fr.box(xa + 0.0015, xb - 0.0015, y0, y1, 0.1015, CH - 0.0365)


def base_run(name, origin, length, depth, rz, bays, sink=None, hob=None):
    """Plinth (recessed), carcass, 3 cm stone worktop with a 2 cm nose, then slab fronts per bay.
    Local frame: back at y = 0, front face at y = -depth, running x 0..length."""
    a = A(name, origin, rz)
    ca, wt = a.m("cab_cherry", bevel=0.002), a.m("worktop_stone", bevel=0.004, segments=2)
    ca.box(0, length, -depth + 0.06, 0, 0, 0.1)
    holes = [h for h in (sink, hob) if h]
    ca.box(0, length, -depth, 0, 0.1, CH - 0.035)
    # worktop pieces around the sink / hob cut-outs
    xs = [0.0, length]
    for h in holes:
        xs += [h[0], h[1]]
    xs = sorted(set(xs))
    for xa, xb in zip(xs, xs[1:]):
        cut = next((h for h in holes if h[0] <= xa and xb <= h[1]), None)
        if cut is None:
            wt.box(xa, xb, -depth - 0.02, 0, CH - 0.03, CH)
        else:
            wt.box(xa, xb, -depth - 0.02, -depth + 0.05, CH - 0.03, CH)          # front strip
            wt.box(xa, xb, -0.08, 0, CH - 0.03, CH)                              # back strip
    x = 0.0
    for kind, w in bays:
        slab_fronts(a, kind, x, x + w, depth)
        x += w
    return a


def undermount_sink(a, x0, x1, depth):
    st = a.m("steel", smooth=False)
    yf, yb, zb = -depth + 0.05, -0.08, CH - 0.22
    t = 0.008
    st.box(x0, x1, yf, yb, zb, zb + t)
    st.box(x0, x1, yf, yf + t, zb, CH - 0.03)
    st.box(x0, x1, yb - t, yb, zb, CH - 0.03)
    st.box(x0, x0 + t, yf, yb, zb, CH - 0.03)
    st.box(x1 - t, x1, yf, yb, zb, CH - 0.03)
    xm = (x0 + x1) / 2
    st.lathe([(0, 0), (0.03, 0), (0.03, 0.004), (0, 0.004)], ((xm), (yf + yb) / 2, zb + t), seg=16)   # drain
    tp = a.m("tap", smooth=True)                                     # tall cream gooseneck tap
    ty = -0.11                                                     # clear of the full-length curtain
    tp.lathe([(0, 0), (0.028, 0), (0.026, 0.02), (0.018, 0.04), (0, 0.04)], (xm, ty, CH), seg=16)
    tp.rod((xm, ty, CH + 0.03), (xm, ty, CH + 0.32), 0.014, seg=14)
    pts = [Vector((xm, ty - 0.11 * (1 - math.cos(t_)), CH + 0.32 + 0.09 * math.sin(t_))) for t_ in [k * math.pi / 10 for k in range(11)]]
    for p, q in zip(pts, pts[1:]):
        tp.rod(p, q, 0.014, seg=14)
    tp.rod(pts[-1], pts[-1] + Vector((0, 0, -0.06)), 0.014, seg=14)
    tp.rod((xm + 0.015, ty, CH + 0.2), (xm + 0.08, ty, CH + 0.22), 0.007, seg=8)   # lever


def gas_hob(a, xc, yc):
    """Built-in black-glass gas hob, two burners with cast grates (local frame of the run)."""
    g = a.m("black_glass", bevel=0.003)
    g.box(xc - 0.36, xc + 0.36, yc - 0.25, yc + 0.25, CH - 0.002, CH + 0.006)
    ir = a.m("iron", bevel=0.002)
    st = a.m("steel", smooth=True)
    for bx in (xc - 0.18, xc + 0.18):
        st.lathe([(0, 0), (0.06, 0), (0.06, 0.02), (0.045, 0.03), (0, 0.03)], (bx, yc + 0.02, CH + 0.006), seg=20)
        ir.lathe([(0, 0.03), (0.035, 0.03), (0.035, 0.04), (0, 0.04)], (bx, yc + 0.02, CH + 0.006), seg=16)
        for k in range(4):                                    # grate arms on four small feet
            ang = k * math.pi / 2 + math.pi / 4
            p0 = Vector((bx + 0.07 * math.cos(ang), yc + 0.02 + 0.07 * math.sin(ang), CH + 0.05))
            p1 = Vector((bx + 0.15 * math.cos(ang), yc + 0.02 + 0.15 * math.sin(ang), CH + 0.05))
            ir.beam(p0, p1, 0.016, 0.03)
        for k in range(2):                                    # control knobs along the front edge
            pass
    for kx in (xc - 0.06, xc + 0.06):
        ir.lathe([(0, 0), (0.022, 0), (0.022, 0.03), (0, 0.032)], (kx, yc - 0.19, CH + 0.006), seg=16)


def splashback():
    """Vertical finger tiles (2.5 x 20 cm, stacked) along the back wall between worktop and hood line."""
    a = A("Splashback finger tiles", (0, DEPTH, Z))
    x0, x1, z0, z1 = KX0, IN_X, CH, SPLASH_Z1
    a.m("grout").box(x0, x1, -0.010, 0.0, z0, z1)
    t = a.m("tile_finger", bevel=0.002, segments=1)
    TW, TH = 0.025, 0.20
    nz = int(math.ceil((z1 - z0) / TH))
    for j in range(nz):
        za, zb = z0 + j * TH + 0.0012, min(z0 + (j + 1) * TH, z1) - 0.0012
        if zb - za < 0.02:
            continue
        x = x0
        while x < x1 - 0.005:
            xa, xb = x + 0.0012, min(x + TW, x1) - 0.0012
            if math.hypot((xa + xb) / 2 - FLUE_X, (za + zb) / 2 - FLUE_Z) > 0.1:
                t.box(xa, xb, -0.018 - rng.uniform(0, 0.0015), -0.010, za, zb)
            x += TW
    a.build()


def hood_and_wall_cabinet():
    a = A("Hood and wall cabinet", (SX, DEPTH, Z))
    st = a.m("steel", bevel=0.004)
    W, D = 0.78, 0.50
    st.box(-W / 2, W / 2, -D, -0.02, HOOD_Z0 + 0.03, WALLCAB_Z0)                  # hood body
    st.solid([(-W / 2, -D - 0.03, HOOD_Z0), (W / 2, -D - 0.03, HOOD_Z0), (W / 2, -D + 0.08, HOOD_Z0), (-W / 2, -D + 0.08, HOOD_Z0)],
             [(-W / 2, -D, HOOD_Z0 + 0.12), (W / 2, -D, HOOD_Z0 + 0.12), (W / 2, -D + 0.08, HOOD_Z0 + 0.03), (-W / 2, -D + 0.08, HOOD_Z0 + 0.03)])  # sloped visor
    st.box(-W / 2, W / 2, -0.34, -0.02, HOOD_Z0, HOOD_Z0 + 0.03)                  # filter tray
    a.m("black_glass").box(-W / 2 + 0.05, W / 2 - 0.05, -D - 0.004, -D, HOOD_Z0 + 0.13, WALLCAB_Z0 - 0.015)  # control strip
    a.m("steel", smooth=True).lathe([(0, 0), (0.022, 0), (0.022, 0.006), (0, 0.008)], (-0.05, -D - 0.004, (HOOD_Z0 + 0.13 + WALLCAB_Z0) / 2), axis='-y', seg=16)
    a.m("bulb").box(-0.2, 0.2, -0.3, -0.24, HOOD_Z0 - 0.002, HOOD_Z0)            # light strip
    cab = a.m("cab_cherry", bevel=0.002)                                          # wall cabinet over the hood
    CW, CD = 0.80, 0.34
    cab.box(-CW / 2, CW / 2, -CD + 0.019, 0, WALLCAB_Z0, WALLCAB_Z1)
    for k in range(2):
        da, db = -CW / 2 + k * CW / 2 + 0.0015, -CW / 2 + (k + 1) * CW / 2 - 0.0015
        cab.box(da, db, -CD, -CD + 0.019, WALLCAB_Z0 + 0.0015, WALLCAB_Z1 - 0.0015)
        kx = db - 0.04 if k == 0 else da + 0.04
        a.m("steel", smooth=True).lathe([(0, 0), (0.006, 0), (0.006, 0.014), (0.016, 0.02), (0.017, 0.03), (0.012, 0.036), (0, 0.037)],
                                        (kx, -CD, WALLCAB_Z0 + 0.06), axis='-y', seg=14)
    a.build()


def open_shelves():
    """Dark-wood open shelves beside the wall cabinet, a stainless utensil rail under them."""
    a = A("Open shelves", (0, DEPTH, Z))
    b = a.m("shelf_dark", bevel=0.003)
    D = 0.30
    for z in (1.55, 1.82):
        b.box(SHELF_X0, SHELF_X1, -D, 0, z, z + 0.03)
    b.box(SHELF_X1 - 0.025, SHELF_X1, -D, 0, 1.55, WALLCAB_Z1)                   # end panel
    b.box(SHELF_X0, SHELF_X1, -D, 0, WALLCAB_Z1 - 0.025, WALLCAB_Z1)             # top
    st = a.m("steel", smooth=True)
    rz, ry = 1.47, -0.05
    st.rod((SHELF_X0 + 0.05, ry, rz), (SHELF_X1 - 0.05, ry, rz), 0.007, seg=10)
    for x in (SHELF_X0 + 0.07, SHELF_X1 - 0.07):
        st.rod((x, ry, rz), (x, 0, rz), 0.006, seg=8)
    wood, bk = a.m("board", bevel=0.002), a.m("basket", bevel=0.002)
    tools = ["spatula", "ladle", "skimmer", "whisk", "tongs", "spoon"]
    for j, kind in enumerate(tools):
        x = SHELF_X0 + 0.28 + j * 0.085
        st.torus((x, ry, rz - 0.02), 0.014, 0.0025, seg=10, rseg=4, axis='x')       # S-hook
        top = Vector((x, ry, rz - 0.04))
        if kind in ("spatula", "spoon"):
            wood.rod(top, top + Vector((0, 0, -0.24)), 0.007, seg=6)
            if kind == "spatula":
                wood.box(x - 0.03, x + 0.03, ry - 0.005, ry + 0.005, rz - 0.36, rz - 0.27)
            else:
                wood.ellipsoid((x, ry - 0.005, rz - 0.31), (0.03, 0.012, 0.045), seg=10, rings=6)
        elif kind == "ladle":
            st.rod(top, top + Vector((0, 0, -0.26)), 0.005, seg=6)
            st.lathe([(0, 0), (0.04, 0), (0.045, 0.03), (0.04, 0.03), (0.035, 0.004), (0, 0.004)], (x, ry - 0.04, rz - 0.33), axis='y', seg=16)
        elif kind == "skimmer":
            st.rod(top, top + Vector((0, 0, -0.24)), 0.005, seg=6)
            st.lathe([(0, 0), (0.045, 0), (0.05, 0.012), (0, 0.006)], (x, ry - 0.01, rz - 0.32), axis='y', seg=16)
        elif kind == "whisk":
            st.rod(top, top + Vector((0, 0, -0.12)), 0.009, seg=8)
            for k in range(6):
                ang = k * math.pi / 3
                pts = [Vector((x + 0.03 * math.sin(math.pi * u) * math.cos(ang), ry + 0.03 * math.sin(math.pi * u) * math.sin(ang), rz - 0.16 - 0.14 * u)) for u in [i / 8 for i in range(9)]]
                for p, q in zip(pts, pts[1:]):
                    st.rod(p, q, 0.0015, seg=4)
        else:                                                                     # tongs
            for sx in (-1, 1):
                st.beam(top, (x + sx * 0.015, ry, rz - 0.3), 0.012, 0.003)
    # woven basket hung at the left end of the rail, wooden spoons standing in it
    bx, bz = SHELF_X0 + 0.12, rz - 0.07
    for r in range(8):
        for c in range(14):
            ang = c * 2 * math.pi / 14
            zz = bz - 0.03 - r * 0.026
            rad = 0.085 - 0.012 * (r / 7) ** 2
            ox, oy = bx + rad * math.cos(ang), ry - 0.06 + 0.5 * rad * math.sin(ang)
            bk.box(ox - 0.02, ox + 0.02, oy - 0.004, oy + 0.004, zz - 0.012, zz + 0.012)
    bk.torus((bx, ry - 0.06, bz + 0.05), 0.07, 0.008, seg=20, rseg=6, axis='y')      # handle hoop
    for k in range(2):
        wood.rod((bx - 0.02 + 0.04 * k, ry - 0.06, bz - 0.15), (bx - 0.03 + 0.06 * k, ry - 0.06, bz + 0.12), 0.007, seg=6)
    a.build()


def knife_strip():
    a = A("Knife strip", (0, DEPTH, Z))
    x0, x1, z = SHELF_X1 + 0.25, SHELF_X1 + 0.70, 1.20
    a.m("knife_handle", bevel=0.004).box(x0, x1, -0.03, 0.0, z - 0.025, z + 0.025)
    st, hd = a.m("steel"), a.m("knife_handle", bevel=0.003)
    for k, (w, L) in enumerate(((0.09, 0.2), (0.07, 0.19), (0.04, 0.2), (0.03, 0.15))):
        x = x0 + 0.06 + k * 0.11
        st.solid([(x - w / 2, -0.034, z + 0.05), (x + w / 2, -0.034, z + 0.05), (x + w / 2, -0.034, z + 0.05 - L), (x - w / 2 + (0.0 if k < 2 else w * 0.6), -0.034, z + 0.05 - L)],
                 [(x - w / 2, -0.031, z + 0.05), (x + w / 2, -0.031, z + 0.05), (x + w / 2, -0.031, z + 0.05 - L), (x - w / 2 + (0.0 if k < 2 else w * 0.6), -0.031, z + 0.05 - L)])
        hx = x + w / 2 - 0.012
        st.rod((hx, -0.037, z + 0.05 - L), (hx, -0.037, z + 0.05 - L - 0.02), 0.009, seg=8)
        hd.rod((hx, -0.037, z + 0.03 - L), (hx, -0.037, z - 0.08 - L), 0.011, seg=8)
    a.build()


def oil_rack():
    """Small stainless rack on the worktop beside the hob: glass oil bottles with pourers."""
    a = A("Oil rack", (SX + 0.62, DEPTH - 0.14, Z + CH))
    st, gl, oil = a.m("steel", smooth=True), a.m("glass", smooth=True), a.m("oil", smooth=True)
    for sx in (-1, 1):
        for sy in (-1, 1):
            st.rod((sx * 0.2, sy * 0.06, 0), (sx * 0.2, sy * 0.06, 0.14), 0.003, seg=6)
    for zz in (0.01, 0.12):
        st.box(-0.2, 0.2, -0.065, 0.065, zz, zz + 0.004)
    for k in range(4):
        x = -0.15 + k * 0.1
        gl.lathe([(0, 0), (0.028, 0), (0.028, 0.15), (0.012, 0.2), (0.012, 0.23), (0, 0.23)], (x, 0, 0.014), seg=16)
        oil.lathe([(0, 0), (0.024, 0), (0.024, 0.09), (0, 0.09)], (x, 0, 0.018), seg=12)
        st.lathe([(0, 0.23), (0.013, 0.23), (0.008, 0.27), (0, 0.27)], (x, 0, 0.014), seg=10)
    a.build()


def cafe_curtain():
    """White gauze cafe curtain on ring clips across the kitchen side window (right wall)."""
    yc = SIDE_WIN[(1, 1)]
    y0, y1 = yc - side_win_w(1, 1) / 2 - 0.12, yc + side_win_w(1, 1) / 2 + 0.12
    rod_z, hem = side_win_head(1, 1) + 0.06, side_win_sill(1, 1) + 0.03   # full drop, hem just above the sill
    a = A("Cafe curtain", (0, 0, Z))
    wx = IN_X - 0.035
    nclip = 9
    cloth = a.m("gauze", smooth=True)                 # single sheer sheet (no thickness)
    def fn(u, v):
        y = y0 + 0.03 + u * (y1 - y0 - 0.06)
        k = u * (nclip - 1)
        sag = 0.05 * math.sin(math.pi * (k - math.floor(k))) ** 2
        top = rod_z - 0.045 - sag
        z = top - v * (top - hem) - 0.02 * math.sin(7.3 * u + 3 * v) * v
        crinkle = 0.004 * math.sin(97 * u + 3.1 * math.sin(9 * v)) + 0.0025 * math.sin(181 * u + 11 * v)
        x = wx - 0.006 - 0.018 * (0.5 + 0.5 * math.sin(2 * math.pi * k)) * (0.4 + 0.6 * v) - 0.006 * math.sin(23 * u + 5 * v) - crinkle
        return (x, y, z)
    cloth.surface(fn, 220, 70)
    st = a.m("steel", smooth=True)
    st.rod((wx, y0 - 0.06, rod_z), (wx, y1 + 0.06, rod_z), 0.011, seg=12)
    for y in (y0 - 0.06, y1 + 0.06):
        st.ellipsoid((wx, y + (-0.02 if y < y0 else 0.02), rod_z), (0.02, 0.02, 0.02), seg=10, rings=6)
        st.box(wx - 0.01, IN_X, y - 0.008, y + 0.008, rod_z - 0.008, rod_z + 0.008)
    for k in range(nclip):
        y = y0 + 0.03 + k * (y1 - y0 - 0.06) / (nclip - 1)
        st.torus((wx, y, rod_z), 0.018, 0.0025, seg=12, rseg=4, axis='y')
        st.rod((wx, y, rod_z - 0.018), (wx, y, rod_z - 0.045), 0.002, seg=4)
        st.box(wx - 0.006, wx + 0.006, y - 0.008, y + 0.008, rod_z - 0.058, rod_z - 0.04)
    a.build()


def saucepan():
    a = A("Saucepan", (SX - 0.18, DEPTH - KD / 2 + 0.02, Z + CH + 0.055))
    s = a.m("steel", smooth=True)
    s.lathe([(0, 0), (0.1, 0), (0.105, 0.008), (0.105, 0.11), (0.1, 0.11), (0.1, 0.008), (0, 0.006)], seg=32)
    s.lathe([(0, 0.13), (0.11, 0.112), (0.11, 0.106), (0, 0.124)], seg=32)                 # lid
    s.lathe([(0, 0.13), (0.012, 0.13), (0.016, 0.145), (0, 0.15)], seg=12)
    a.m("knife_handle", bevel=0.004).beam((0.1, 0, 0.09), (0.3, 0, 0.11), 0.03, 0.02)
    a.build()


def downlights():
    from build_interior_f1_spec import KITCHEN_DOWNLIGHTS
    a = A("Kitchen downlights", (0, 0, Z))
    st, gl = a.m("steel", smooth=True), a.m("bulb")
    zc = FLOOR[2] - 0.06 - Z
    for x, y in KITCHEN_DOWNLIGHTS:
        st.lathe([(0.035, zc), (0.05, zc), (0.05, zc - 0.006), (0.035, zc - 0.006)], (x, y, 0), seg=24)   # trim ring
        gl.lathe([(0, zc - 0.002), (0.036, zc - 0.002), (0.036, zc), (0, zc)], (x, y, 0), seg=24)
    a.build()


def dish_shelf():
    a = A("Dish shelf", (4.15, DEPTH, Z + 1.72))
    b = a.m("shelf_dark", bevel=0.004)
    b.box(-0.5, 0.5, -0.22, 0, 0, 0.025)
    b.box(-0.5, 0.5, -0.22, -0.205, 0.025, 0.06)                     # plate rail
    for s in (-1, 1):
        x = s * 0.42
        b.solid([(x - 0.012, -0.003, -0.002), (x - 0.012, -0.19, -0.002), (x - 0.012, -0.003, -0.13)],
                [(x + 0.012, -0.003, -0.002), (x + 0.012, -0.19, -0.002), (x + 0.012, -0.003, -0.13)])
    c = a.m("ceramic", smooth=True)
    for k in range(4):                                                  # plates leaning on the wall
        x = -0.4 + k * 0.09
        tilt = Matrix.Rotation(-0.25, 3, 'X')
        cen = Vector((x, -0.06, 0.13))
        prof = [(0, 0), (0.11, 0), (0.12, 0.012), (0.115, 0.014), (0.1, 0.004), (0, 0.004)]
        i0 = len(c.v)
        c.lathe(prof, (0, 0, 0), axis='y', seg=24)
        for i in range(i0, len(c.v)):
            c.v[i] = tuple(cen + tilt @ Vector(c.v[i]))
    for k in range(3):                                                  # stacked bowls
        c.lathe([(0, 0), (0.05, 0), (0.08, 0.06), (0.074, 0.06), (0.045, 0.006), (0, 0.006)], (0.1, -0.11, 0.025 + k * 0.022), seg=20)
    for x in (0.3, 0.4):                                                # cups
        c.lathe([(0, 0), (0.035, 0), (0.04, 0.08), (0.034, 0.08), (0.03, 0.006), (0, 0.006)], (x, -0.11, 0.025), seg=16)
        c.torus((x + 0.045, -0.11, 0.065), 0.016, 0.005, seg=10, rseg=5, axis='y')
    a.build()

def island():
    a = A("Kitchen island", (1.6, 2.5))
    L, W, H = 1.9, 0.95, CH
    tp = a.m("worktop", bevel=0.004)
    n = 24                                                               # butcher-block strips
    for k in range(n):
        y0 = -W / 2 + k * W / n
        tp.box(-L / 2, L / 2, y0 + 0.001, y0 + W / n - 0.001, H - 0.05, H - rng.uniform(0, 0.0015))
    fr = a.m("cab_cherry", bevel=0.005)
    for sx in (-1, 1):
        for sy in (-1, 1):
            fr.beam((sx * (L / 2 - 0.08), sy * (W / 2 - 0.08), 0), (sx * (L / 2 - 0.08), sy * (W / 2 - 0.08), H - 0.05), 0.075, 0.075)
    for sy in (-1, 1):
        fr.box(-L / 2 + 0.1, L / 2 - 0.1, sy * (W / 2 - 0.08) - 0.015, sy * (W / 2 - 0.08) + 0.015, H - 0.17, H - 0.05)
    for sx in (-1, 1):
        fr.box(sx * (L / 2 - 0.08) - 0.015, sx * (L / 2 - 0.08) + 0.015, -W / 2 + 0.1, W / 2 - 0.1, H - 0.17, H - 0.05)
    for k in range(9):                                                   # slatted lower shelf
        x0 = -L / 2 + 0.12 + k * (L - 0.24) / 9
        fr.box(x0 + 0.005, x0 + (L - 0.24) / 9 - 0.005, -W / 2 + 0.1, W / 2 - 0.1, 0.18, 0.2)
    for sy in (-1, 1):
        fr.box(-L / 2 + 0.1, L / 2 - 0.1, sy * (W / 2 - 0.08) - 0.015, sy * (W / 2 - 0.08) + 0.015, 0.16, 0.2)
    fr.box(-0.35, 0.35, -W / 2 + 0.05, -W / 2 + 0.064, H - 0.165, H - 0.055)   # drawer front, proud of the apron
    a.m("steel", smooth=True).rod((-0.06, -W / 2 + 0.045, H - 0.11), (0.06, -W / 2 + 0.045, H - 0.11), 0.008, seg=8)
    # produce bowl and a chopping board on top
    bw = a.m("board", smooth=True)
    bw.lathe([(0, 0), (0.07, 0), (0.15, 0.08), (0.14, 0.08), (0.065, 0.01), (0, 0.01)], (-0.2, 0.0, H), seg=28)
    for k, (dx, dy, key, r) in enumerate(((-0.24, 0.02, "apple", 0.04), (-0.16, -0.03, "orange", 0.042), (-0.2, 0.06, "pear", 0.038),
                                          (-0.13, 0.05, "apple", 0.04), (-0.27, -0.05, "orange", 0.04))):
        a.m(key, smooth=True).ellipsoid((dx, dy, H + 0.05 + (0.03 if k > 2 else 0.0)), (r, r, r * (1.15 if key == "pear" else 0.95)), seg=12, rings=8)
    a.m("board", bevel=0.006).box(0.25, 0.65, -0.18, 0.08, H, H + 0.025)
    a.build()


# ================================================================== build everything
tv_and_console()
leather_sofa()
walnut_table()
for k, dy in enumerate((-0.45, 0.45)):
    dining_chair(f"Dining chair W{k + 1}", TABLE_X - 0.62, LV_Y + dy, math.radians(90))
    dining_chair(f"Dining chair E{k + 1}", TABLE_X + 0.62, LV_Y + dy, math.radians(-90))
leather_pouf("Leather pouf", -2.35, LV_Y - 1.2)
big_rug()
linear_pendant()
floor_lamp()
a, b, s, h = WIN_BACK[1]
wood_blinds("Back window blind", ((a + b) / 2, DEPTH, Z), 0.0, b - a, s, h, drop=h - 0.5)   # raised: let the daylight in
sheer_panels("Back window sheers", a, b, h, DEPTH)
# (jar shelves removed: the wide back window takes that wall)
ph_model("potted_plant_01", "Corner plant front", (-4.25, 0.75, Z), 1.35, 1.7)   # 10-20: replaces the modelled climbing plant (read as plastic)
sconce()
ph_planted("pachira_aquatica_01", "_c", "Money tree", (-4.1, 4.3, Z), 1.35, 0.75)

splashback()
# back run along the back wall: hob drawers, two double-door bays, blind corner behind the side run
CORNER_X = IN_X - KD
back_len = IN_X - KX0
bays = [("drawers", 0.80), ("door2", 0.90), ("door2", CORNER_X - KX0 - 1.70), ("panel", KD)]
back_run = base_run("Back counter", (KX0, DEPTH), back_len, KD, 0.0, bays, hob=(SX - KX0 - 0.35, SX - KX0 + 0.35))
gas_hob(back_run, SX - KX0, -KD / 2)
back_run.build()
# side run on the right wall, facing the room; local x runs from y = DEPTH - KD down to y = 2.0
SIDE_LEN = DEPTH - KD - 2.0
yc = SIDE_WIN[(1, 1)]
s_sink0 = (DEPTH - KD) - (yc + 0.4)                      # sink bay centred under the window
side_bays = [("door2", 0.78), ("door1", s_sink0 - 0.78), ("sink", 0.80), ("panel", SIDE_LEN - s_sink0 - 0.80)]
side_run = base_run("Side counter", (IN_X, DEPTH - KD, Z), SIDE_LEN, KD, math.radians(-90), side_bays,
                    sink=(s_sink0 + 0.06, s_sink0 + 0.74))
undermount_sink(side_run, s_sink0 + 0.06, s_sink0 + 0.74, KD)
side_run.build()
hood_and_wall_cabinet()
open_shelves()
knife_strip()
oil_rack()
cafe_curtain()
dish_shelf()
downlights()
# props (Poly Haven, CC0)
saucepan()
ph_model("potted_plant_04", "Shelf aloe", (SHELF_X0 + 0.5, DEPTH - 0.15, Z + 1.58), 1.3)
ph_model("ceramic_pot", "Shelf crock", (SHELF_X0 + 0.2, DEPTH - 0.15, Z + 1.85), 0.26, 0.4)
ph_model("carved_wooden_plate", "Shelf plate", (SHELF_X0 + 0.55, DEPTH - 0.03, Z + 1.85 + 0.13), 1.0).rotation_euler = (math.radians(80), 0, 0)
ph_model("jug_01", "Worktop jug", (IN_X - 0.3, DEPTH - KD - 0.45, Z + CH), 0.9, 2.2)
for k, (dx, dy) in enumerate(((0.0, 0.0), (0.07, 0.03), (0.03, -0.06))):
    ph_model("lemon", f"Lemon {k}", (3.25 + dx, DEPTH - 0.3 + dy, Z + CH + 0.033), 1.0, k * 1.3).rotation_euler = (math.radians(90), 0, k * 1.3)
# 10-20: the kitchen island and its stools were removed: the dining table is the only table on this floor

# ------------------------------------------------------------------ detail cameras for this floor

look_cam("Cam_F1_Dining", (1.2, 0.6, Z + 1.45), (-2.2, 2.9, Z + 0.8), 24)
look_cam("Cam_F1_Kitchen", (0.9, 1.0, Z + 1.35), (3.4, 4.6, Z + 1.05), 22)
look_cam("Cam_F1_Island", (-1.4, 0.4, Z + 1.4), (-4.6, 2.6, Z + 1.2), 26)   # TV wall
look_cam("Cam_F1_Window", (-1.7, 3.2, Z + 1.6), (-2.8, DEPTH, Z + 1.45), 26)

ic.finish("F1_SAVED")
