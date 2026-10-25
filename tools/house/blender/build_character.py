"""The owner: the blogger avatar, rebuilt to match the user's 3D character model sheet (2026-10-21):
assets/concepts/owner-character-3d-v01.png (front) and owner-character-3d-side-back-v01.png.

Run after the interiors:
    Blender -b assets/blender/companion-house.blend --python build_character.py
Removes the purple proportion blocks ("Owner ...") and builds the character in 40_Characters at the
three spots (standing on floors 1 and 3, seated in the floor-2 rocking chair).

Measured off the front sheet (1.35 m tall, ~0.99 mm per pixel): skull/face 0.37 m wide (chin 0.885 m,
crown 1.30 m); big voluminous black bob 0.62 m wide, slightly messy strands with a few flyaways and
a cowlick, centre parting, ends at 0.86 m, framing the face; large rounded ears; eyes 0.17 m apart at
1.035 m with big dark-brown irises, white sclera and highlight dots; thin arched brows; round brown
glasses (rim radius 0.062 m); small nose and smile, soft blush. Black short-sleeve hoodie dress:
V-neck with hood lying on the back, drawstrings with round tips, kangaroo pocket, A-line hem at
0.37 m; slim arms with real hands; legs to cream foam slide slippers.
Every object is named "Char ..." so the material passes leave it alone; its materials are made here.
"""
import bpy, math, os, sys, random
from mathutils import Vector, Matrix, noise

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from house_spec import *   # noqa: E402,F403
from meshkit import Asset  # noqa: E402
from interior_common import sweep_tube  # noqa: E402

sc = bpy.context.scene
for o in list(bpy.data.objects):
    if o.name.startswith(("Owner ", "Char ")):
        bpy.data.objects.remove(o, do_unlink=True)
COL = bpy.data.collections.get("40_Characters") or bpy.data.collections.new("40_Characters")
if COL.name not in sc.collection.children:
    sc.collection.children.link(COL)

KEYS = ("skin", "cheek", "hair", "dress", "pocket", "slipper", "glasses", "sclera", "iris", "pupil", "shine", "brow", "mouth")
PAL = {k: (0.5, 0.5, 0.5) for k in KEYS}


# ------------------------------------------------------------------ materials
def mat(name, base, rough, coat=0.0, sss=0.0, sheen=0.0, emit=0.0, bump=0.0, bump_scale=80.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    N.clear()
    bs = N.new("ShaderNodeBsdfPrincipled")
    bs.inputs["Base Color"].default_value = (*base, 1)
    bs.inputs["Roughness"].default_value = rough
    bs.inputs["Coat Weight"].default_value = coat
    bs.inputs["Subsurface Weight"].default_value = sss
    bs.inputs["Subsurface Radius"].default_value = (0.04, 0.016, 0.01)
    bs.inputs["Sheen Weight"].default_value = sheen
    if emit:
        bs.inputs["Emission Color"].default_value = (*base, 1)
        bs.inputs["Emission Strength"].default_value = emit
    if bump:
        tc, nz, bp = N.new("ShaderNodeTexCoord"), N.new("ShaderNodeTexNoise"), N.new("ShaderNodeBump")
        if isinstance(bump_scale, tuple):                     # anisotropic: streaks along z (hair strands)
            mp = N.new("ShaderNodeMapping")
            mp.inputs["Scale"].default_value = bump_scale
            L.new(tc.outputs["Object"], mp.inputs[0])
            nz.inputs["Scale"].default_value = 1.0
        else:
            nz.inputs["Scale"].default_value = bump_scale
        nz.inputs["Detail"].default_value = 8.0
        bp.inputs["Strength"].default_value = bump
        bp.inputs["Distance"].default_value = 0.001
        L.new(mp.outputs[0] if isinstance(bump_scale, tuple) else tc.outputs["Object"], nz.inputs["Vector"])
        L.new(nz.outputs["Fac"], bp.inputs["Height"])
        L.new(bp.outputs[0], bs.inputs["Normal"])
    L.new(bs.outputs[0], N.new("ShaderNodeOutputMaterial").inputs["Surface"])
    return m

MATS = {
    "skin": mat("Char skin", (0.88, 0.58, 0.42), 0.5, sss=0.18),
    "cheek": mat("Char cheek", (0.86, 0.42, 0.38), 0.55, sss=0.15),
    "hair": mat("Char hair", (0.006, 0.0045, 0.0035), 0.45, sheen=0.12, bump=0.4, bump_scale=(320.0, 320.0, 16.0)),
    "dress": mat("Char dress", (0.006, 0.006, 0.007), 0.9, sheen=0.2, bump=0.25, bump_scale=300.0),
    "pocket": None,
    "slipper": mat("Char slipper", (0.84, 0.78, 0.66), 0.75, sheen=0.4, bump=0.1, bump_scale=150.0),
    "glasses": mat("Char glasses", (0.12, 0.045, 0.018), 0.3, coat=0.5),
    "sclera": mat("Char sclera", (0.92, 0.90, 0.87), 0.15, coat=0.6),
    "iris": mat("Char iris", (0.006, 0.004, 0.003), 0.12, coat=0.8),
    "pupil": mat("Char pupil", (0.004, 0.003, 0.003), 0.1, coat=0.8),
    "shine": mat("Char eye shine", (1.0, 1.0, 1.0), 0.1, emit=1.5),
    "brow": mat("Char brow", (0.02, 0.015, 0.012), 0.6),
    "mouth": mat("Char mouth", (0.35, 0.12, 0.09), 0.45),
}
MATS["pocket"] = MATS["dress"]
SUBSURF = {"slipper": 2, "cheek": 1, "hair": 1}     # skin and dress are voxel-remeshed instead


# ------------------------------------------------------------------ head
# Deep, round Pixar-style skull measured off both sheets: 0.35 m wide, 0.42 m deep (face front 0.21 m
# ahead of the skull centre, ears 0.25 m behind the face front), chin 0.895 m, crown 1.305 m; the
# lower face is full (wide round cheeks, small round chin).
HC = 1.06
RX, RYF, RYB, RZU, RZD = 0.19, 0.21, 0.21, 0.25, 0.18
EX, EZ = 0.094, -0.025             # eye centres relative to HC (big, wide-set)


def _h(s):
    return (1 - abs(s) ** 2.3) ** (1 / 2.3) if s < 0 else math.sqrt(max(0.0, 1 - s * s))


def skull_pt(c, th, s, grow=0.0):
    """th: 0 = front (-y); s: -1 chin .. +1 crown."""
    h = _h(s)
    z = s * (RZU if s > 0 else RZD)
    ry = RYF if math.cos(th) > 0 else RYB
    return c + Vector(((RX + grow) * h * math.sin(th), -(ry + grow) * h * math.cos(th), z + grow * s))


def _front(c, x, z):
    s = max(-0.999, min(0.999, z / RZU if z > 0 else z / RZD))
    h = _h(s)
    r = max(-0.999, min(0.999, x / (RX * h + 1e-6)))
    return c + Vector((x, -RYF * h * math.sqrt(1 - r * r), z))


def face_pt(c, x, z, lift=0.0):
    p = _front(c, x, z)
    e = 0.002
    n = (_front(c, x + e, z) - p).cross(_front(c, x, z + e) - p).normalized()
    if n.y > 0:
        n = -n
    return p + n * lift, n


def head(a, dz):
    c = Vector((0, 0, HC + dz))
    sk = a.m("skin", smooth=True)
    sk.surface(lambda u, v: skull_pt(c, 2 * math.pi * u, -math.cos(math.pi * v)), 64, 40)
    sk.rod(Vector((0, 0.02, 0.79 + dz)), Vector((0, 0.02, 0.94 + dz)), 0.045, seg=20)       # short neck
    for sx in (-1, 1):                                                                       # big rounded ears, set well back
        ec = c + Vector((sx * 0.205, 0.0, -0.06))
        sk.ellipsoid(ec, (0.03, 0.05, 0.064), seg=22, rings=14, rot=Matrix.Rotation(sx * 0.7, 3, 'Z'))
        sk.ellipsoid(ec + Vector((sx * 0.012, -0.018, 0)), (0.01, 0.028, 0.038), seg=14, rings=8, rot=Matrix.Rotation(sx * 0.7, 3, 'Z'))

    for sx in (-1, 1):
        # eyes: a white eyeball set into the face, a big dark-brown iris, pupil and two highlights
        fp, n = face_pt(c, sx * EX, EZ)
        R = n.to_track_quat('-Y', 'Z').to_matrix()
        eb = fp - n * 0.031
        a.m("sclera", smooth=True).ellipsoid(eb, (0.049, 0.04, 0.052), seg=32, rings=20, rot=R)
        front = eb + n * 0.04
        a.m("iris", smooth=True).ellipsoid(front + n * 0.0005, (0.04, 0.003, 0.043), seg=32, rings=10, rot=R)
        a.m("pupil", smooth=True).ellipsoid(front + n * 0.0022, (0.026, 0.002, 0.028), seg=24, rings=8, rot=R)
        a.m("shine", smooth=True).ellipsoid(front + n * 0.004 + R @ Vector((sx * 0.014, 0, 0.016)), (0.012, 0.0015, 0.013), seg=16, rings=6, rot=R)
        a.m("shine", smooth=True).ellipsoid(front + n * 0.004 + R @ Vector((-sx * 0.012, 0, -0.015)), (0.0045, 0.0015, 0.0045), seg=12, rings=5, rot=R)
        # upper lid: a soft skin fold with a dark lash line and lashes at the outer corner
        lid = [face_pt(c, sx * (EX + 0.051 * math.cos(t)), EZ + 0.05 * math.sin(t) + 0.003, 0.004)[0]
               for t in [math.radians(15 + 150 * k / 16) for k in range(17)]]
        sweep_tube(a.m("brow", smooth=True), lid, 0.0034, seg=6)
        for k in range(3):
            ang = math.radians(12 + 15 * k)
            q0, _ = face_pt(c, sx * (EX + 0.051 * math.cos(ang)), EZ + 0.05 * math.sin(ang) + 0.003, 0.005)
            q1, _ = face_pt(c, sx * (EX + 0.07 * math.cos(ang - 0.2)), EZ + 0.065 * math.sin(ang - 0.2) + 0.003, 0.012)
            sweep_tube(a.m("brow", smooth=True), [q0, q1], 0.0024, seg=5)
        # short, softly arched brow
        brow = [face_pt(c, sx * (0.052 + 0.06 * k / 8), 0.072 + 0.008 * math.sin(math.pi * k / 8) - 0.006 * k / 8, 0.003)[0] for k in range(9)]
        sweep_tube(a.m("brow", smooth=True), brow, 0.0036, seg=6)
        # soft blush on the full cheeks
        pc, nc = face_pt(c, sx * 0.115, -0.075, 0.001)
        a.m("cheek", smooth=True).ellipsoid(pc, (0.036, 0.003, 0.022), seg=20, rings=8, rot=nc.to_track_quat('-Y', 'Z').to_matrix())
    pn, _ = face_pt(c, 0.0, -0.06, 0.0)
    sk.ellipsoid(pn, (0.015, 0.013, 0.011), seg=16, rings=10)                     # small button nose
    sm = [face_pt(c, 0.02 * math.cos(t), -0.10 - 0.0075 * math.sin(t), 0.001)[0] for t in [k * math.pi / 10 for k in range(11)]]
    sweep_tube(a.m("mouth", smooth=True), sm, 0.0032, seg=6)                     # small closed smile

    # round brown glasses: rings in a plane just in front of the face, bridge, temples back to the ears
    gl = a.m("glasses", smooth=True)
    ends = []
    for sx in (-1, 1):
        fp, n = face_pt(c, sx * EX, EZ)
        ctr = Vector((sx * EX, fp.y - 0.03, fp.z))
        nn = Vector((sx * 0.12, -1, 0)).normalized()                           # rim plane turned slightly with the face
        u_ = (Vector((1, 0, 0)) - nn * nn.x).normalized()
        w_ = nn.cross(u_).normalized()
        ring = [ctr + (u_ * math.cos(2 * math.pi * k / 56) + w_ * math.sin(2 * math.pi * k / 56)) * 0.072 for k in range(57)]
        sweep_tube(gl, ring, 0.0078, seg=10)
        outer = ctr + u_ * sx * 0.072
        sweep_tube(gl, [outer, outer + Vector((sx * 0.025, 0.035, 0.002)), Vector((sx * 0.172, 0.025, outer.z + 0.006))], 0.0045, seg=8)
        ends.append(ctr - u_ * sx * 0.072)
    mid = (ends[0] + ends[1]) / 2 + Vector((0, -0.004, 0.01))
    sweep_tube(gl, [ends[0], mid, ends[1]], 0.0045, seg=8)

    hair(a, c)


# ------------------------------------------------------------------ hair
def ribbon(m, path, w0, w1, t0, centre):
    """A flat tapered hair lock along `path`: width w0 -> w1, thickness t0, facing away from centre."""
    nseg = 10
    rings = []
    for i, p in enumerate(path):
        T = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        Nn = (p - centre)
        Nn = (Nn - T * Nn.dot(T)).normalized()
        B = T.cross(Nn).normalized()
        f = i / (len(path) - 1)
        w = (w0 + (w1 - w0) * f ** 1.5) * (0.75 + 0.25 * math.sin(math.pi * min(1.0, f * 4)))   # narrow root, full body, pointed tip
        t = t0 * (1 - 0.6 * f)
        prof = [(math.cos(2 * math.pi * k / nseg), math.sin(2 * math.pi * k / nseg)) for k in range(nseg)]
        rings.append([p + B * w * cx + Nn * t * sy * abs(sy) ** 0.4 for cx, sy in prof])   # lens section: thin edges
    i0 = len(m.v)
    for r in rings:
        m.v += [tuple(q) for q in r]
    for i in range(len(rings) - 1):
        for k in range(nseg):
            a_, b_ = i0 + i * nseg + k, i0 + i * nseg + (k + 1) % nseg
            m.f.append([a_, b_, b_ + nseg, a_ + nseg])
    m.f.append([i0 + k for k in range(nseg)][::-1])
    m.f.append([i0 + (len(rings) - 1) * nseg + k for k in range(nseg)])


def hair(a, c):
    """Voluminous centre-parted bob made of a few hundred tapered locks, plus a dark inner mass."""
    rng = random.Random(7)
    m = a.m("hair", smooth=True)
    hc = c + Vector((0, 0.05, 0.04))                      # hair mass centre sits back and up (deep skull)
    RB = (0.33, 0.30)                                     # bob radii at the widest (x, y)
    RBF = 0.25                                            # ... in front (beside the face)
    z_end = c.z - 0.20                                    # ends at about 0.86 m
    DOME = (0.255, 0.30, 0.255, 0.225)                    # smooth crown: x, back y, top z, front y (from hc)
    # dark inner mass so no skin shows between locks: the back and top of the head
    inner = a.m("hair", smooth=True)
    def inner_pt(u, v):
        th = math.radians(-92 + 184 * u)                  # back half only: the sides are all locks
        z = hc.z + 0.24 - (0.24 + (hc.z - z_end) - 0.11) * v
        t = (z - hc.z) / 0.24
        f = math.sqrt(max(0.0, 1 - max(0.0, t) ** 2)) if t > 0 else 1.0
        return Vector((RB[0] * 0.86 * f * math.sin(th), hc.y + RB[1] * 0.86 * f * math.cos(th), z))   # back mass
    inner.surface(inner_pt, 48, 20)
    def cap_pt(u, v):                                     # scalp cap over the top, down to the forehead hairline
        th = 2 * math.pi * u
        off = abs(((th - math.pi) + math.pi) % (2 * math.pi) - math.pi)      # angle away from the face direction
        lim = 0.80 - 0.62 * min(1.0, off / math.radians(80)) ** 1.3          # high at the parting, down to the temples
        return skull_pt(c, th + math.pi, 1 - (1 - lim) * v, grow=0.008)
    inner.surface(cap_pt, 48, 14)
    # locks
    def end_point(az, jitter):
        r = 1 + 0.04 * jitter
        ry = RBF if math.cos(az) > 0 else RB[1]
        return Vector((RB[0] * r * math.sin(az), hc.y - ry * r * math.cos(az), z_end + 0.02 * jitter + 0.015 * (math.cos(az) < 0)))
    def lock_path(root, az, jitter, flyaway=0.0):
        """Root on the parting -> over the skull -> down the bob to its end, slightly flared and messy."""
        end = end_point(az, jitter)
        mid = Vector((0.82 * end.x, end.y * 0.9 + hc.y * 0.1, hc.z + 0.05))                  # temples narrower than the flared ends
        top = root + (Vector((end.x, end.y, 0)) - Vector((root.x, root.y, 0))).normalized() * 0.07 + Vector((0, 0, 0.035))
        pts = []
        n = 22
        for i in range(n):
            t = i / (n - 1)
            if t < 0.35:                                                   # root -> along the smooth hair dome -> temple
                s = t / 0.35
                p = root * (1 - s) ** 2 + top * 2 * s * (1 - s) + mid * s * s
                d_ = (p - hc)
                if d_.z > 0:                                               # project onto the dome so the crown is smooth
                    d_.normalize()
                    rd = 1 / math.sqrt((d_.x / DOME[0]) ** 2 + (d_.y / (DOME[1] if d_.y > 0 else DOME[3])) ** 2 + (d_.z / DOME[2]) ** 2)
                    p = p.lerp(hc + d_ * rd, min(1.0, s * 3))
            else:                                                          # temple -> straight-ish down -> flared end
                s = (t - 0.35) / 0.65
                p = mid * (1 - s) + end * s
                p.x += (0.015 * math.sin(math.pi * s) + 0.03 * max(0.0, (s - 0.7) / 0.3) ** 2) * (1 if p.x > 0 else -1)   # bob flares out at the ends
            wob = Vector((noise.noise(Vector((az * 3, t * 4, jitter))), noise.noise(Vector((az * 3 + 5, t * 4, jitter))),
                          noise.noise(Vector((az * 3 + 9, t * 4, jitter)))))
            p = p + wob * (0.004 + 0.012 * t * t + flyaway * t * t)
            pts.append(p)
        return pts
    def root_on_part(az):
        """Parting from the front hairline (az = 0) back over the crown (az = pi)."""
        f = min(1.0, abs(az) / math.pi)
        y = -0.13 + 0.29 * f
        z = c.z + RZU * math.sqrt(max(0.0, 1 - (y / 0.21) ** 2)) + 0.02
        return Vector((math.copysign(0.012, az), y, z))
    for layer, (w, t_, rshrink) in enumerate(((0.075, 0.026, 0.0), (0.055, 0.02, 0.04))):
        for k in range(84):
            side = 1 if k % 2 == 0 else -1
            u = (k // 2) / 42.0
            az = side * (1.45 + (math.pi - 1.45) * u + rng.uniform(-0.03, 0.03))      # end azimuth: from behind the ears round to the back
            jit = rng.uniform(-1, 1)
            root = root_on_part(side * (abs(az) - 1.45) / (math.pi - 1.45) * math.pi)
            pts = lock_path(root, az, jit)
            if rshrink:
                pts = [hc + (p - hc) * (1 - rshrink) for p in pts]
            ribbon(m, pts, w, w * 0.32, t_, hc)
    # face-framing locks falling from the parting beside the face down to the cheeks
    for k in range(40):                                   # sweep from the parting over the temples, down beside the cheeks
        side = 1 if k % 2 == 0 else -1
        az = side * rng.uniform(1.35, 1.65)             # behind the ears, which stick out in front of them
        root = root_on_part(side * rng.uniform(0.0, 0.35))
        pts = lock_path(root, az, rng.uniform(-1, 1))
        ribbon(m, pts, 0.06, 0.012, 0.02, hc)
    # curtain bangs: from the parting down over the sides of the forehead to the brows, then round the temples
    for k in range(44):
        side = 1 if k % 2 == 0 else -1
        f = rng.uniform(0.0, 1.0)                         # 0 = innermost (closest to the parting) .. 1 = outermost
        rx = 0.075 + 0.05 * f                             # how far in from the face edge the lock reaches at brow level
        pts = []
        for i in range(16):
            t = i / 15
            x = side * (0.014 + (rx + (0.215 - rx) * max(0.0, (t - 0.45) / 0.55) ** 1.2) * min(1.0, t / 0.45 + 0.15))
            z = 0.21 - (0.21 + 0.06 + 0.06 * f) * t ** 1.15
            q, n = face_pt(c, max(-0.172, min(0.172, x)), max(-0.15, min(0.235, z + 0.02)), 0.02 + 0.012 * f + 0.02 * t)
            if abs(x) > 0.172:
                q.x = x
            pts.append(q + Vector((0, 0.0, 0)) + Vector((noise.noise(Vector((k, t * 3, 0))) * 0.004, 0, 0)))
        ribbon(m, pts, 0.065, 0.014, 0.02, c)
    # a few flyaways and the cowlick
    for k in range(14):
        side = 1 if k % 2 == 0 else -1
        az = side * rng.uniform(0.8, 2.8)
        pts = lock_path(root_on_part(side * rng.uniform(0.3, 3.0)), az, rng.uniform(-1, 1), flyaway=0.09)
        pts = [hc + (p - hc) * 1.04 for p in pts]
        ribbon(m, pts, 0.006, 0.0015, 0.004, hc)
    crown = root_on_part(math.pi * 0.55)
    for k, (dx, h) in enumerate(((0.0, 0.11), (0.02, 0.085), (-0.015, 0.07))):
        ck = [crown + Vector((dx, 0, 0)), crown + Vector((dx + 0.01, -0.02, h * 0.6)), crown + Vector((dx + 0.04, -0.05, h)),
              crown + Vector((dx + 0.075, -0.06, h * 0.75))]
        ribbon(m, ck, 0.028, 0.006, 0.01, crown - Vector((0, 0, 0.1)))


# ------------------------------------------------------------------ body
def squash_y(mesh, i0, k=0.82):
    for i in range(i0, len(mesh.v)):
        x, y, z = mesh.v[i]
        mesh.v[i] = (x, y * k, z)


def torso(a, dz, hem=True):
    d = a.m("dress", smooth=True)
    i0 = len(d.v)
    prof = [(0.0, 0.87), (0.06, 0.87), (0.10, 0.845), (0.135, 0.80), (0.145, 0.76), (0.138, 0.70), (0.142, 0.62), (0.155, 0.52)]
    if hem:
        prof += [(0.172, 0.43), (0.186, 0.375), (0.182, 0.368), (0.0, 0.368)]
    else:
        prof += [(0.16, 0.45), (0.0, 0.45)]
    d.lathe(prof, (0, 0, dz), seg=48)
    squash_y(d, i0, 0.74)
    for sx in (-1, 1):                                                           # short sleeves, slightly away from the body
        d.rod(Vector((sx * 0.105, 0, 0.775 + dz)), Vector((sx * 0.188, 0.0, 0.655 + dz)), 0.05, seg=24, r2=0.054)   # sloping shoulders, short sleeves
    # hood: a soft roll from the V at the chest round the neck, and the hood itself lying on the back
    hd = a.m("dress", smooth=True)
    collar = []
    for k in range(29):
        t = 2 * math.pi * k / 28 - math.pi / 2                                   # starts and ends at the front V
        x, y = 0.078 * math.cos(t), 0.068 * math.sin(t)
        vfront = max(0.0, -math.sin(t)) ** 6                                     # front of the loop dips into a V
        collar.append(Vector((x * (1 - 0.6 * vfront), y - 0.03 * vfront, 0.875 - 0.08 * vfront + dz)))
    sweep_tube(hd, collar, 0.022, seg=12)
    for k in range(9):                                                           # the hood lying on the back: a soft
        t = k / 8                                                                # inverted triangle, wide at the shoulders
        hd.ellipsoid(Vector((0, 0.10 + 0.012 * (1 - t), 0.83 - 0.20 * t + dz)), (0.15 * (1 - 0.82 * t) + 0.02, 0.04, 0.035),
                     seg=28, rings=12)
    hd.ellipsoid(Vector((0, 0.10, 0.80 + dz)), (0.09, 0.045, 0.04), seg=24, rings=10)
    for sx in (-1, 1):                                                           # drawstrings with round tips
        p0 = Vector((sx * 0.024, -0.112, 0.78 + dz))
        sweep_tube(hd, [p0, p0 + Vector((sx * 0.002, -0.015, -0.05)), p0 + Vector((sx * 0.004, -0.02, -0.105))], 0.0045, seg=8)
        hd.ellipsoid(p0 + Vector((sx * 0.004, -0.021, -0.112)), (0.009, 0.009, 0.01), seg=12, rings=8)
    # kangaroo pocket on the front of the skirt
    if hem:
        pk = a.m("pocket", bevel=0.004, smooth=True)
        y0 = -0.157 * 0.74 - 0.003
        pk.solid([(-0.10, y0, 0.47 + dz), (0.10, y0, 0.47 + dz), (0.075, y0 + 0.004, 0.585 + dz), (-0.075, y0 + 0.004, 0.585 + dz)],
                 [(-0.10, y0 - 0.008, 0.47 + dz), (0.10, y0 - 0.008, 0.47 + dz), (0.075, y0 - 0.004, 0.585 + dz), (-0.075, y0 - 0.004, 0.585 + dz)])


def limb(sk, pts, radii, seg=18):
    """One smooth round limb through `pts` with a radius per point (no sausage joints), capped."""
    path, rad = [], []
    for i in range(len(pts) - 1):
        for k in range(8):
            t = k / 8
            path.append(pts[i] * (1 - t) + pts[i + 1] * t)
            rad.append(radii[i] * (1 - t) + radii[i + 1] * t)
    path.append(pts[-1]); rad.append(radii[-1])
    nprev, i0 = None, len(sk.v)
    for i, p in enumerate(path):
        T = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        if nprev is None:
            nprev = T.orthogonal().normalized()
        n = (nprev - T * nprev.dot(T)).normalized()
        b = T.cross(n)
        sk.v += [tuple(p + (n * math.cos(2 * math.pi * k / seg) + b * math.sin(2 * math.pi * k / seg)) * rad[i]) for k in range(seg)]
        nprev = n
    for i in range(len(path) - 1):
        for k in range(seg):
            a_, b_ = i0 + i * seg + k, i0 + i * seg + (k + 1) % seg
            sk.f.append([a_, b_, b_ + seg, a_ + seg])
    for p, r in ((path[0], rad[0]), (path[-1], rad[-1])):
        sk.ellipsoid(p, (r, r, r), seg=seg, rings=10)


def hand(sk, wrist, down, out):
    """Small relaxed hand: palm plus four curled fingers and a thumb."""
    palm = wrist + down * 0.04
    sk.ellipsoid(palm, (0.025, 0.036, 0.046), seg=14, rings=10, rot=Matrix.Rotation(math.atan2(out.x, -out.y) if out.length else 0, 3, 'Z'))
    for k in range(4):
        base = palm + down * 0.026 + Vector((0, -0.016 + 0.011 * k, 0))
        sk.rod(base, base + down * (0.03 - 0.004 * abs(k - 1.5)) + out * 0.006, 0.0075, seg=8)
    sk.rod(palm + Vector((0, -0.024, 0.0)), palm + Vector((0, -0.036, -0.022)) + out * 0.006, 0.0075, seg=8)


def slipper(a, heel):
    """Chunky cream foam slide: thick rounded sole, a broad padded strap over the instep, toes out front."""
    sl = a.m("slipper", smooth=True)
    x, y, z = heel
    sl.box(x - 0.058, x + 0.058, y - 0.20, y + 0.025, z, z + 0.036)
    sl.solid([(x - 0.062, y - 0.14, z + 0.03), (x + 0.062, y - 0.14, z + 0.03), (x + 0.062, y - 0.055, z + 0.03), (x - 0.062, y - 0.055, z + 0.03)],
             [(x - 0.052, y - 0.132, z + 0.085), (x + 0.052, y - 0.132, z + 0.085), (x + 0.052, y - 0.062, z + 0.092), (x - 0.052, y - 0.062, z + 0.092)])
    sk = a.m("skin", smooth=True)
    sk.ellipsoid(Vector((x, y - 0.085, z + 0.052)), (0.038, 0.095, 0.026), seg=18, rings=10)   # foot
    for k in range(5):                                                                       # toes
        sk.ellipsoid(Vector((x - 0.026 + 0.013 * k, y - 0.17, z + 0.042)), (0.0075, 0.011, 0.008), seg=8, rings=6)


REMESH = {"skin": (0.0032, 6), "dress": (0.005, 8)}


def fuse(o, voxel, smooth):
    """Sculpt-style blockout fusion: voxel-remesh the overlapping primitives of one material into a
    single watertight surface, relax it, and bake the result back into the object's mesh."""
    for mo in list(o.modifiers):
        o.modifiers.remove(mo)
    rm = o.modifiers.new("Remesh", 'REMESH')
    rm.mode, rm.voxel_size, rm.adaptivity, rm.use_smooth_shade = 'VOXEL', voxel, 0.0, True
    sm = o.modifiers.new("Relax", 'CORRECTIVE_SMOOTH')
    sm.iterations, sm.smooth_type, sm.use_only_smooth = smooth, 'SIMPLE', True
    dg = bpy.context.evaluated_depsgraph_get()
    new = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    old = o.data
    o.modifiers.clear()
    o.data = new
    bpy.data.meshes.remove(old)
    for p in o.data.polygons:
        p.use_smooth = True


def build_owner(name, loc, rz, pose="stand", seat_z=0.42):
    a = Asset("Char " + name, COL, PAL, loc, rz)
    sk = a.m("skin", smooth=True)
    if pose == "stand":
        dz = 0.0
        torso(a, dz)
        for sx in (-1, 1):
            limb(sk, [Vector((sx * 0.072, 0, 0.44)), Vector((sx * 0.08, 0.0, 0.31)), Vector((sx * 0.083, -0.008, 0.22)),
                      Vector((sx * 0.084, 0.0, 0.14)), Vector((sx * 0.085, 0.005, 0.07))], [0.06, 0.056, 0.049, 0.045, 0.036])
            slipper(a, Vector((sx * 0.09, 0.10, 0.0)))
            sh, wr = Vector((sx * 0.172, 0.0, 0.69)), Vector((sx * 0.192, 0.0, 0.49))
            limb(sk, [sh, (sh + wr) / 2 + Vector((sx * 0.006, 0, 0)), wr], [0.043, 0.037, 0.031])
            hand(sk, wr, Vector((0, 0, -1)), Vector((sx, 0, 0)))
    else:
        dz = seat_z - 0.45
        torso(a, dz, hem=False)
        d = a.m("dress", smooth=True)
        d.ellipsoid(Vector((0, -0.11, seat_z + 0.035)), (0.17, 0.16, 0.06), seg=28, rings=12)   # skirt over the thighs
        for sx in (-1, 1):
            hip, knee = Vector((sx * 0.065, -0.05, seat_z + 0.04)), Vector((sx * 0.07, -0.25, seat_z + 0.035))
            ank = Vector((sx * 0.075, -0.28, max(0.075, seat_z - 0.26)))
            limb(sk, [hip, knee, ank], [0.046, 0.037, 0.028])
            slipper(a, ank + Vector((0, 0.04, -0.075)))
            sh, el = Vector((sx * 0.18, 0.0, 0.68 + dz)), Vector((sx * 0.19, -0.06, 0.53 + dz))
            wr = Vector((sx * 0.10, -0.19, seat_z + 0.10))
            limb(sk, [sh, el, wr], [0.033, 0.029, 0.024])
            hand(sk, wr, Vector((0, -0.6, -0.8)).normalized(), Vector((-sx, 0, 0)))
    head(a, dz)
    e = a.build()
    for o in list(e.children):                       # blockout parts -> one seamless surface (voxel remesh + smooth)
        key = o.name.split(" - ")[-1]
        if key in REMESH:
            fuse(o, *REMESH[key])
    for o in e.children:
        key = o.name.split(" - ")[-1]
        o.data.materials.clear()
        o.data.materials.append(MATS[key])
        if key in SUBSURF:
            mo = o.modifiers.new("Smooth", 'SUBSURF')
            mo.levels = mo.render_levels = SUBSURF[key]
    return e


if __name__ == "__main__":
    build_owner("Owner F1", (1.0, 1.2, FLOOR[1]), 0.0)
    build_owner("Owner F3", (1.2, 2.4, FLOOR[3]), math.radians(-10))
    build_owner("Owner F2", (-2.5, 2.67, FLOOR[2]), math.radians(60), pose="sit", seat_z=0.42)   # in the rocking chair
    bpy.ops.wm.save_mainfile()
    print("CHAR_SAVED", len([o for o in COL.all_objects]), "objects")
