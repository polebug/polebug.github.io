"""Stage 2: detailed architecture of the companion house.

Run after build_whitebox.py, on its output:
    Blender -b assets/blender/companion-house.blend --python build_architecture.py
Replaces the whitebox structure, roof and stonework with built-up construction and saves in place.
Furniture (collections 03_Floor1..05_Floor3) stays whitebox until stage 3.

Construction, bottom to top:
  stone plinth (rubble core, facing stones, cap slabs) and solid block steps
  sill board + floor boards (F1); joists + subfloor + floor boards (F2, F3)
  corner posts, front beams with shaped ends, knee braces, iron bolt heads
  walls: interior boards | core | exterior boards, cut around every opening; floor bands outside
  windows: frame, two-leaf casements with glazing bars, glass, sills, trims
  roof: purlins (shaped front/back heads) -> common rafters -> sheathing -> battens -> beaver-tail
        clay tiles, ridge caps, verge and fascia boards; trimmed openings for both flues
  flues: stone chimney with flashing, cap and hood; kitchen hood duct with a louvred vent cap
"""
import bpy, bmesh, math, random, os, sys
from mathutils import Vector, Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from house_spec import *   # noqa: E402,F403

rng = random.Random(2026)
sc = bpy.context.scene
COS, SIN, TAN = math.cos(PITCH), math.sin(PITCH), math.tan(PITCH)
BOARD = 0.022            # wall board thickness (interior and exterior layers)

# ------------------------------------------------------------------ remove whitebox structure
OLD = ("01_Structure", "02_Roof", "03_Stonework", "90_Cutters")
NEW = ("11_Frame", "12_Walls", "13_Floors", "14_Windows", "15_Roof", "16_Stonework", "17_Flues")
for cn in OLD + NEW:
    c = bpy.data.collections.get(cn)
    if c:
        for o in list(c.all_objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(c)
for n in ("Chimney flue attic", "Stove pipe riser", "Stove pipe through wall"):
    if n in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[n], do_unlink=True)
for m in list(bpy.data.meshes):
    if m.users == 0:
        bpy.data.meshes.remove(m)

COLS = {}
def col(name):
    if name not in COLS:
        c = bpy.data.collections.new(name)
        sc.collection.children.link(c)
        COLS[name] = c
    return COLS[name]

COLOR = {
    "timber": (0.50, 0.33, 0.20), "timber_dark": (0.40, 0.26, 0.16), "board_in": (0.78, 0.58, 0.38),
    "board_out": (0.55, 0.37, 0.23), "floor": (0.74, 0.55, 0.36), "joist": (0.62, 0.44, 0.28),
    "tile_a": (0.80, 0.35, 0.20), "tile_b": (0.74, 0.30, 0.18), "tile_c": (0.86, 0.42, 0.24),
    "batten": (0.60, 0.45, 0.30), "stone_a": (0.70, 0.70, 0.72), "stone_b": (0.62, 0.63, 0.66),
    "stone_c": (0.76, 0.74, 0.72), "mortar": (0.55, 0.54, 0.52), "glass": (0.62, 0.80, 0.95),
    "frame": (0.58, 0.40, 0.25), "iron": (0.20, 0.20, 0.22), "steel": (0.55, 0.57, 0.60),
    "flashing": (0.45, 0.47, 0.50), "limestone": (0.88, 0.76, 0.60), "pearl": (0.97, 0.88, 0.77),   # warm pearl: neutral off-white read green under sky + lawn bounce (user)
}


# ------------------------------------------------------------------ mesh builder
class Mesh:
    """Collects many solids into one mesh object (one object per material group)."""

    def __init__(self):
        self.v, self.f = [], []

    def solid(self, bottom, top):
        """Prism between two vertex loops of equal length."""
        n, i0 = len(bottom), len(self.v)
        self.v += [tuple(p) for p in bottom] + [tuple(p) for p in top]
        self.f.append([i0 + k for k in range(n)][::-1])
        self.f.append([i0 + n + k for k in range(n)])
        for k in range(n):
            a, b = i0 + k, i0 + (k + 1) % n
            self.f.append([a, b, b + n, a + n])

    def box(self, x0, x1, y0, y1, z0, z1):
        self.solid([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)],
                   [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)])

    def mapped_box(self, fmap, u0, u1, d0, d1, z0, z1):
        loop = [(u0, d0), (u1, d0), (u1, d1), (u0, d1)]
        self.solid([fmap(u, d, z0) for u, d in loop], [fmap(u, d, z1) for u, d in loop])

    def mapped_poly(self, fmap, poly, d0, d1):
        """poly: [(u, z)] in the wall plane, extruded through the wall depth d0..d1."""
        self.solid([fmap(u, d0, z) for u, z in poly], [fmap(u, d1, z) for u, z in poly])

    def beam(self, p1, p2, w, h, side=None):
        """Rectangular timber between end centres p1, p2; w along `side`, h perpendicular."""
        p1, p2 = Vector(p1), Vector(p2)
        d = (p2 - p1).normalized()
        side = Vector(side) if side else (Vector((0, 1, 0)) if abs(d.y) < 0.9 else Vector((1, 0, 0)))
        side = (side - d * side.dot(d)).normalized()
        up = d.cross(side)
        corners = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
        self.solid([p1 + side * a + up * b for a, b in corners], [p2 + side * a + up * b for a, b in corners])

    def cylinder(self, c, axis, r, length, seg=16, r2=None):
        c, axis = Vector(c), Vector(axis).normalized()
        a = axis.orthogonal().normalized()
        b = axis.cross(a)
        r2 = r if r2 is None else r2
        ring = lambda rr, base: [base + (a * math.cos(t) + b * math.sin(t)) * rr
                                 for t in (2 * math.pi * k / seg for k in range(seg))]
        self.solid(ring(r, c), ring(r2, c + axis * length))

    def build(self, name, collection, color, bevel=0.0, segments=2):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        o = bpy.data.objects.new(name, me)
        col(collection).objects.link(o)
        o.color = (*COLOR[color], 1.0)
        if bevel:
            m = o.modifiers.new("Bevel", 'BEVEL')
            m.width, m.segments, m.limit_method, m.angle_limit = bevel, segments, 'ANGLE', math.radians(40)
        return o


# wall-plane mappings: u runs along the wall, d through it (0 = interior face), z up
def back_map(u, d, z):
    return (u, DEPTH + d, z)

def side_map(sx):
    return lambda u, d, z: (sx * (IN_X + d), u, z)


def split_columns(u0, u1, cuts, wmin, wmax):
    """Plank columns between u0 and u1, never straddling a cut position."""
    cols, u = [], u0
    cuts = sorted(c for c in cuts if u0 < c < u1)
    while u < u1 - 1e-4:
        w = rng.uniform(wmin, wmax)
        nxt = min([u + w, u1] + [c for c in cuts if c > u + 1e-4])
        if nxt not in cuts and u1 - nxt < wmin * 0.4 and not [c for c in cuts if nxt < c < u1]:
            nxt = u1
        cols.append((u, nxt))
        u = nxt
    return cols


def wall_layer(mesh, fmap, u0, u1, z0, top, d0, d1, openings, plank=(0.15, 0.22), gap=0.005, jitter=0.002):
    """Vertical boards (or a solid core when plank is None) filling u0..u1, z0..top(u),
    with every opening (ua, ub, za, zb) cut out. `top` is a number or a function of u."""
    top_fn = top if callable(top) else (lambda u, t=top: t)
    cuts = [c for o in openings for c in o[:2]]
    if plank is None:
        cols = split_columns(u0, u1, cuts + ([0.0] if callable(top) else []), 1e9, 1e9)
        gap, jitter = 0.0, 0.0
    else:
        cols = split_columns(u0, u1, cuts, *plank)
    for a, b in cols:
        a2, b2 = a + gap / 2, b - gap / 2
        if b2 - a2 < 0.01:
            continue
        mid = (a + b) / 2
        # only openings that overlap this layer's height (an upper floor's window must not extend the
        # lower layer up into the next storey, where it would double the wall and render black)
        holes = sorted((za, zb) for ua, ub, za, zb in openings
                       if ua - 1e-4 <= mid <= ub + 1e-4 and zb > z0 and za < top_fn(mid))
        segs, z = [], z0
        for za, zb in holes:
            if za > z:
                segs.append((z, za))
            z = max(z, zb)
        segs.append((z, None))
        off = rng.uniform(-jitter, jitter)
        for lo, hi in segs:
            if hi is not None:
                if hi - lo > 0.01:
                    mesh.mapped_poly(fmap, [(a2, lo), (b2, lo), (b2, hi), (a2, hi)], d0 + off, d1 + off)
                continue
            pts = [(a2, lo), (b2, lo), (b2, top_fn(b2))]
            if a2 < 0 < b2:
                pts.append((0.0, top_fn(0.0)))
            pts.append((a2, top_fn(a2)))
            if min(p[1] for p in pts[2:]) - lo > 0.01:
                mesh.mapped_poly(fmap, pts, d0 + off, d1 + off)


# ------------------------------------------------------------------ stonework
ST = "16_Stonework"
PL_X0, PL_X1, PL_Y0, PL_Y1 = -HALF_W - 0.2, HALF_W + 0.2, -0.175, DEPTH + 0.375
CAP = 0.05
core = Mesh()
CZ = BASE_H - CAP
core.box(PL_X0 + 0.04, -1.0, PL_Y0 + 0.04, PL_Y1 - 0.04, 0.0, CZ)
core.box(1.0, PL_X1 - 0.04, PL_Y0 + 0.04, PL_Y1 - 0.04, 0.0, CZ)
core.box(-1.0, 1.0, -0.03, PL_Y1 - 0.04, 0.0, CZ)          # recessed behind the steps
core.build("Plinth rubble core", ST, "mortar")

stones = {k: Mesh() for k in ("stone_a", "stone_b", "stone_c")}
def face_stones(fmap, u0, u1, skip=()):
    """Two irregular courses of facing stones on one plinth face (d = outward depth)."""
    z = 0.0
    for course in range(2):
        h = (BASE_H - CAP) / 2 + (0.015 if course == 0 else -0.015)
        u = u0 + (0.0 if course == 0 else -rng.uniform(0.1, 0.2))
        while u < u1:
            L = rng.uniform(0.28, 0.55)
            a, b = max(u, u0) + 0.008, min(u + L, u1) - 0.008
            if b - a > 0.08 and not any(s0 < (a + b) / 2 < s1 for s0, s1 in skip):
                hh = h - 0.016 - rng.uniform(0, 0.03)
                zz = z + 0.008 + rng.uniform(0, 0.015)
                stones[rng.choice(list(stones))].mapped_box(fmap, a, b, -0.06, rng.uniform(0.0, 0.025), zz, zz + hh)
            u += L
        z += h
face_stones(lambda u, d, z: (u, PL_Y0 - d, z), PL_X0, PL_X1, skip=[(-1.05, 1.05)])
face_stones(lambda u, d, z: (u, PL_Y1 + d, z), PL_X0, PL_X1)
for sx in (-1, 1):
    face_stones(lambda u, d, z, sx=sx: (sx * (PL_X1 + d), u, z), PL_Y0, PL_Y1)
for k, m in stones.items():
    m.build(f"Plinth facing stones {k[-1]}", ST, k, bevel=0.022, segments=3)

caps = Mesh()
def cap_run(x0, x1, y0, y1, along_x):
    u, (u0, u1) = (x0 if along_x else y0), ((x0, x1) if along_x else (y0, y1))
    while u < u1 - 0.05:
        L = min(rng.uniform(0.5, 0.9), u1 - u)
        if along_x:
            caps.box(u + 0.004, u + L - 0.004, y0, y1, BASE_H - CAP, BASE_H - rng.uniform(0, 0.006))
        else:
            caps.box(x0, x1, u + 0.004, u + L - 0.004, BASE_H - CAP, BASE_H - rng.uniform(0, 0.006))
        u += L
cap_run(PL_X0, -1.0, PL_Y0 - 0.02, 0.0, True)
cap_run(1.0, PL_X1, PL_Y0 - 0.02, 0.0, True)
cap_run(-1.0, 1.0, -0.03, 0.0, True)                       # strip under the floor edge, above the top step
cap_run(PL_X0, PL_X1, DEPTH + WALL_T, PL_Y1 + 0.02, True)
for sx in (-1, 1):
    x0, x1 = (PL_X0 - 0.02, -HALF_W) if sx < 0 else (HALF_W, PL_X1 + 0.02)
    cap_run(x0, x1, 0.0, DEPTH + WALL_T, False)
caps.build("Plinth cap slabs", ST, "stone_c", bevel=0.012)

steps = Mesh()
for i, top in enumerate((0.45, 0.30, 0.15)):
    y1 = -0.03 - 0.32 * i
    y0 = y1 - 0.32
    split = rng.uniform(-0.35, 0.35)
    for a, b in ((-1.0, split - 0.006), (split + 0.006, 1.0)):
        steps.box(a, b, y0, y1, 0.0, top)
steps.build("Front steps (solid blocks)", ST, "stone_c", bevel=0.018, segments=3)

# ------------------------------------------------------------------ floors
FL = "13_Floors"
def floor_boards(m, z_top, x0, x1, y0, y1, holes=()):
    """Boards running front-to-back, random lengths with staggered butt joints."""
    x = x0
    while x < x1 - 0.02:
        w = min(rng.uniform(0.22, 0.28), x1 - x)     # 10-22 (user): wide planks, the narrow ones read as hatching
        y = y0 - rng.uniform(0, 1.2)
        while y < y1:
            L = rng.uniform(1.2, 2.4)
            a, b = max(y, y0), min(y + L, y1)
            xa, xb = x + 0.002, x + w - 0.002
            segs = [(a, b)]
            for hx0, hx1, hy0, hy1 in holes:
                if xb > hx0 and xa < hx1:
                    segs = [s for p, q in segs for s in ((p, min(q, hy0)), (max(p, hy1), q)) if s[1] - s[0] > 0.02]
            for p, q in segs:
                if q - p > 0.02:
                    m.box(xa, xb, p + 0.002, q - 0.002, z_top - 0.03, z_top - rng.uniform(0, 0.0015))
            y += L
        x += w

# 10-20: the fireplace and its chimney were removed (user); CHIMNEY = False drops the flue, the stack,
# the roof and floor openings and the trimmed rafters / joists around them
CHIMNEY = False
CHIM_HOLE = (FX - FW / 2 - 0.03, FX + FW / 2 + 0.03, DEPTH - FD - 0.03, DEPTH + 0.01)
boards = Mesh()
# 10-20: floor 1 is warm limestone (user, natural mid-century refit): one slab layer whose joints come
# from the CC0 Tiles143 texture (build_materials_real.py); floors 2 and 3 keep the boards
lime = Mesh()
lime.box(-IN_X, IN_X, 0.0, DEPTH, FLOOR[1] - 0.03, FLOOR[1])
lime.build("Floor 1 limestone", FL, "limestone")
floor_boards(boards, FLOOR[2], -IN_X, IN_X, TRUSS_Y, DEPTH)
floor_boards(boards, FLOOR[3], -IN_X, IN_X, TRUSS_Y, DEPTH, holes=[CHIM_HOLE] if CHIMNEY else [])
boards.build("Floor boards", FL, "floor", bevel=0.003, segments=1)

sub = Mesh()
sub.box(-(IN_X + WALL_T - BOARD - 0.002), IN_X + WALL_T - BOARD - 0.002, 0.0, DEPTH + WALL_T - BOARD - 0.002,
        BASE_H, FLOOR[1] - 0.03)
for f in (2, 3):
    z1 = FLOOR[f] - 0.03
    if f == 3 and CHIMNEY:
        hx0, hx1, hy0, hy1 = CHIM_HOLE
        sub.box(-IN_X, hx0, TRUSS_Y, DEPTH + 0.07, z1 - 0.03, z1)
        sub.box(hx1, IN_X, TRUSS_Y, DEPTH + 0.07, z1 - 0.03, z1)
        sub.box(hx0, hx1, TRUSS_Y, hy0, z1 - 0.03, z1)
    else:
        sub.box(-IN_X, IN_X, TRUSS_Y, DEPTH + 0.07, z1 - 0.03, z1)
sub.build("Subfloor", FL, "joist")

joists = Mesh()
for f in (2, 3):
    zb, zt = FLOOR[f] - SLAB, FLOOR[f] - 0.06
    for k in range(16):
        x = -4.5 + 0.6 * k
        y_end = DEPTH + 0.07
        if CHIMNEY and f == 3 and CHIM_HOLE[0] - 0.05 < x < CHIM_HOLE[1] + 0.05:
            y_end = CHIM_HOLE[2] - 0.12          # trimmed joist stops at the header
        joists.box(x - 0.05, x + 0.05, TRUSS_Y, y_end, zb, zt)
    if CHIMNEY and f == 3:   # header (doubled) across the chimney opening, carried by the neighbouring joists
        joists.box(-4.45, -3.35, CHIM_HOLE[2] - 0.12, CHIM_HOLE[2] - 0.02, zb, zt)
joists.build("Floor joists", FL, "joist", bevel=0.006, segments=1)

edge = Mesh()
edge.box(-IN_X, IN_X, -0.035, 0.0, BASE_H, FLOOR[1])
edge.build("Floor 1 front edge board", FL, "timber", bevel=0.005)

# ------------------------------------------------------------------ timber frame
FR = "11_Frame"
frame = Mesh()
post_top = roof_under(EAVE_PX) - PURLIN
for sx in (-1, 1):
    for y0 in (0.0, DEPTH + WALL_T - POST):
        frame.box(sx * HALF_W - (POST if sx > 0 else 0), sx * HALF_W + (POST if sx < 0 else 0),
                  y0, y0 + POST, BASE_H, post_top)

def shaped_beam_x(m, x0, x1, y0, y1, zb, zt, head=0.35, cut=0.12):
    """Beam along X whose protruding heads have a sloped underside (a common chalet beam end)."""
    prof = [(x0, zt - cut), (x0 + head, zb), (x1 - head, zb), (x1, zt - cut), (x1, zt), (x0, zt)]
    m.solid([(x, y0, z) for x, z in prof], [(x, y1, z) for x, z in prof])

for f in (2, 3):
    shaped_beam_x(frame, -HALF_W - 0.35, HALF_W + 0.35, -0.18, TRUSS_Y, FLOOR[f] - SLAB, FLOOR[f])
    for sx in (-1, 1):
        under = FLOOR[f] - SLAB
        frame.beam((sx * (HALF_W - POST + 0.03), POST / 2, under - 0.62),
                   (sx * (HALF_W - POST - 0.55), POST / 2, under + 0.03), 0.14, 0.14)
frame.build("Posts, front beams, braces", FR, "timber", bevel=0.018, segments=2)

bolts = Mesh()
def bolt(x, y, z, axis=(0, -1, 0)):
    bolts.cylinder((x, y, z), axis, 0.026, 0.018, seg=10, r2=0.022)
for f in (2, 3):
    for sx in (-1, 1):
        for dz in (-0.07, -0.19):
            bolt(sx * (HALF_W - POST / 2), -0.18, FLOOR[f] + dz)

# ------------------------------------------------------------------ walls
WL = "12_Walls"
bin_, core_m, bout = Mesh(), Mesh(), Mesh()
def win_back(f):
    a, b, s, h = WIN_BACK[f]
    return (a, b, FLOOR[f] + s, FLOOR[f] + h)
def win_side(f, sx):
    yc = SIDE_WIN[(f, sx)]
    return (yc - side_win_w(f, sx) / 2, yc + side_win_w(f, sx) / 2, FLOOR[f] + side_win_sill(f, sx), FLOOR[f] + side_win_head(f, sx))
board_top = lambda u: roof_under(u) + 0.16 / COS                  # underside of the roof sheathing
FLUE_HOLE = (FLUE_X - 0.08, FLUE_X + 0.08, FLOOR[1] + FLUE_Z - 0.08, FLOOR[1] + FLUE_Z + 0.08)

# back wall, floors 1-2
ob = [win_back(1), win_back(2)]
# 10-20: every interior wall is smooth warm pearl-white plaster (user); the plaster stands 4 mm proud
# of the old board plane so it never shares a face with the corner posts
PL0, PLANK = -0.004, None
for f in (1, 2):
    wall_layer(bin_, back_map, -IN_X, IN_X, FLOOR[f], FLOOR[f] + CLEAR, PL0, BOARD, ob + [FLUE_HOLE], plank=PLANK)
wall_layer(core_m, back_map, -IN_X, IN_X, FLOOR[1], FLOOR[3], BOARD, WALL_T - BOARD, ob + [FLUE_HOLE], plank=None)
wall_layer(bout, back_map, -IN_X, IN_X, BASE_H, FLOOR[3], WALL_T - BOARD, WALL_T, ob + [FLUE_HOLE])
# back gable (attic): boards notched around the ridge and middle purlins
purl = [(x - PURLIN / 2, x + PURLIN / 2, roof_under(x) - PURLIN, 99.0) for x in (0.0, -MID_PX, MID_PX)]
og = [win_back(3)]
wall_layer(bin_, back_map, -IN_X, IN_X, FLOOR[3], board_top, PL0, BOARD, og + purl, plank=PLANK)
wall_layer(core_m, back_map, -IN_X, IN_X, FLOOR[3], board_top, BOARD, WALL_T - BOARD, og + purl, plank=None)
wall_layer(bout, back_map, -IN_X, IN_X, FLOOR[3], board_top, WALL_T - BOARD, WALL_T, og + purl)
# side walls and attic knee walls
y_in1, y_out1 = DEPTH, DEPTH + WALL_T - POST
for sx in (-1, 1):
    fm = side_map(sx)
    os_ = [win_side(f, sx) for f in (1, 2) if (f, sx) in SIDE_WIN]
    for f in (1, 2):
        wall_layer(bin_, fm, POST, y_in1, FLOOR[f], FLOOR[f] + CLEAR, PL0, BOARD, os_, plank=PLANK)
    wall_layer(bin_, fm, POST, y_in1, FLOOR[3], post_top, PL0, BOARD, [], plank=PLANK)
    wall_layer(core_m, fm, POST, y_out1, FLOOR[1], post_top, BOARD, WALL_T - BOARD, os_, plank=None)
    wall_layer(bout, fm, POST, y_out1, BASE_H, post_top, WALL_T - BOARD, WALL_T, os_)
bin_.build("Interior pearl white walls", WL, "pearl")
core_m.build("Wall core", WL, "board_out")
bout.build("Wall boards exterior", WL, "board_out", bevel=0.003, segments=1)

bands = Mesh()
for f in (2, 3):
    z0, z1 = FLOOR[f] - SLAB - 0.03, FLOOR[f] + 0.03
    bands.mapped_box(back_map, -IN_X, IN_X, WALL_T, WALL_T + 0.025, z0, z1)
    for sx in (-1, 1):
        bands.mapped_box(side_map(sx), POST, y_out1, WALL_T, WALL_T + 0.025, z0, z1)
bands.build("Exterior floor bands", WL, "timber", bevel=0.006)

# ------------------------------------------------------------------ windows
WN = "14_Windows"
wframe, wglass = Mesh(), Mesh()
def window(fmap, ua, ub, zs, zh, leaves, cols, rows):
    T, FW_ = WALL_T, 0.06
    mb = lambda *a: wframe.mapped_box(fmap, *a)
    mb(ua, ua + FW_, 0, T, zs, zh)                                  # jambs
    mb(ub - FW_, ub, 0, T, zs, zh)
    mb(ua, ub, 0, T, zh - FW_, zh)                                  # head
    mb(ua, ub, 0, T, zs, zs + 0.05)                                 # frame sill
    mb(ua - 0.06, ub + 0.06, T - 0.02, T + 0.07, zs - 0.045, zs)    # exterior sill, projecting
    mb(ua - 0.05, ub + 0.05, -0.04, 0.03, zs - 0.03, zs)            # interior stool
    mb(ua - 0.03, ub + 0.03, -0.015, 0.0, zs - 0.1, zs - 0.03)      # apron under the stool
    for d0, d1 in ((-0.015, 0.0), (T, T + 0.015)):                  # trims, inside and out
        mb(ua - 0.07, ua, d0, d1, zs - (0.0 if d0 < 0 else 0.045), zh + 0.07)
        mb(ub, ub + 0.07, d0, d1, zs - (0.0 if d0 < 0 else 0.045), zh + 0.07)
        mb(ua - 0.07, ub + 0.07, d0, d1, zh, zh + 0.07)
    ia, ib, iz0, iz1 = ua + FW_, ub - FW_, zs + 0.05, zh - FW_
    lw = (ib - ia) / leaves
    SW, DM = 0.05, (0.045, 0.095)                                   # sash rail width, depth band
    for k in range(leaves):
        a, b = ia + k * lw + 0.003, ia + (k + 1) * lw - 0.003
        mb(a, a + SW, *DM, iz0, iz1)
        mb(b - SW, b, *DM, iz0, iz1)
        mb(a, b, *DM, iz0, iz0 + SW + 0.01)
        mb(a, b, *DM, iz1 - SW, iz1)
        ga, gb, gz0, gz1 = a + SW, b - SW, iz0 + SW + 0.01, iz1 - SW
        for c in range(1, cols):
            u = ga + (gb - ga) * c / cols
            mb(u - 0.011, u + 0.011, 0.055, 0.085, gz0, gz1)
        for r in range(1, rows):
            z = gz0 + (gz1 - gz0) * r / rows
            mb(ga, gb, 0.055, 0.085, z - 0.011, z + 0.011)
        wglass.mapped_box(fmap, ga, gb, 0.068, 0.074, gz0, gz1)
        # knob on the meeting stile
        if leaves == 2:
            u = b - SW / 2 if k == 0 else a + SW / 2
            wframe.cylinder(fmap(u, 0.045, (iz0 + iz1) / 2), (0, -1, 0) if fmap is back_map else (-1, 0, 0), 0.012, 0.03, seg=8)

window(back_map, *WIN_BACK[1][:2], FLOOR[1] + WIN_BACK[1][2], FLOOR[1] + WIN_BACK[1][3], 4, 2, 3)   # wide 4-leaf window
window(back_map, *WIN_BACK[2][:2], FLOOR[2] + WIN_BACK[2][2], FLOOR[2] + WIN_BACK[2][3], 6, 2, 3)
window(back_map, *WIN_BACK[3][:2], FLOOR[3] + WIN_BACK[3][2], FLOOR[3] + WIN_BACK[3][3], 4, 2, 2)
for sx in (-1, 1):
    for f in (1, 2):
        if (f, sx) not in SIDE_WIN:
            continue
        ua, ub, zs, zh = win_side(f, sx)
        window(side_map(sx), ua, ub, zs, zh, 2 if ub - ua > 1.0 else 1, 1, 3)
wframe.build("Window frames and sashes", WN, "frame", bevel=0.004, segments=1)
wglass.build("Window glass", WN, "glass")

# ------------------------------------------------------------------ roof
RF = "15_Roof"
Y_F, Y_B = -OVER_F, DEPTH + WALL_T + OVER_B
U_EAVE = EAVE_X / COS
RU0 = roof_under(0)
def slope_pt(sx, u, v, n):
    """Roof slope frame: u down-slope from the ridge line, v along Y, n out of the roof."""
    return (sx * (u * COS + n * SIN), v, RU0 - u * SIN + n * COS)
def slope_box(m, sx, u0, u1, v0, v1, n0, n1):
    bot = [slope_pt(sx, u, v, n0) for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))]
    top = [slope_pt(sx, u, v, n1) for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))]
    m.solid(bot, top)

N_RAF, N_BRD, N_BAT = 0.16, 0.185, 0.215     # layer tops: rafters, sheathing, battens
# openings in slope coordinates: (side, u0, u1, v0, v1)
def u_of(x, n=N_BAT):
    return (abs(x) - n * SIN) / COS
HOLES = [(-1, u_of(FX + FW / 2) - 0.06, u_of(FX - FW / 2) + 0.06, DEPTH - FD - 0.06, DEPTH + 0.06)] if CHIMNEY else []
def in_hole(sx, u0, u1, v0, v1):
    return any(s == sx and u1 > a and u0 < b and v1 > c and v0 < d for s, a, b, c, d in HOLES)
def minus_holes(sx, u0, u1, v0, v1):
    segs = [(v0, v1)]
    for s, a, b, c, d in HOLES:
        if s == sx and u1 > a and u0 < b:
            segs = [q for p0, p1 in segs for q in ((p0, min(p1, c)), (max(p0, d), p1)) if q[1] - q[0] > 0.02]
    return segs

purlins = Mesh()
for x in (0.0, -MID_PX, MID_PX, -EAVE_PX, EAVE_PX):
    zt = roof_under(x)
    zb = zt - PURLIN
    prof = [(Y_F, zt - 0.1), (Y_F + 0.3, zb), (Y_B - 0.3, zb), (Y_B, zt - 0.1), (Y_B, zt), (Y_F, zt)]
    purlins.solid([(x - PURLIN / 2, y, z) for y, z in prof], [(x + PURLIN / 2, y, z) for y, z in prof])

# front truss in the plane y = TRUSS_Y
RAF_W = 0.22
def rafter_under(x):
    return roof_under(x) - PURLIN - RAFTER / COS
for sx in (-1, 1):
    purlins.beam((sx * EAVE_PX, TRUSS_Y, post_top - RAFTER / 2), (0, TRUSS_Y, RU0 - PURLIN - RAFTER / 2), RAF_W, RAFTER)
x_c = (RU0 - PURLIN - RAFTER / COS - (COLLAR + 0.24)) / TAN
purlins.box(-x_c - 0.1, x_c + 0.1, TRUSS_Y - 0.1, TRUSS_Y + 0.1, COLLAR, COLLAR + 0.24)
purlins.box(-0.11, 0.11, TRUSS_Y - 0.1, TRUSS_Y + 0.1, COLLAR + 0.24, rafter_under(0) + 0.05)
for sx in (-1, 1):
    purlins.beam((sx * 0.1, TRUSS_Y, COLLAR + 0.3), (sx * 1.1, TRUSS_Y, rafter_under(1.1) + 0.03), 0.16, 0.16)
    bolt(sx * x_c, TRUSS_Y - 0.11, COLLAR + 0.12)
    bolt(sx * 0.6, TRUSS_Y - 0.11, (COLLAR + 0.3 + rafter_under(1.1)) / 2 + 0.02)
bolt(0, TRUSS_Y - 0.11, COLLAR + 0.36)
purlins.build("Purlins and front truss", RF, "timber", bevel=0.018, segments=2)

# common rafters on the purlins, trimmed around the chimney
rafters = Mesh()
VS = [Y_F + 0.05 + k * (Y_B - Y_F - 0.1) / 8 for k in range(9)]
for sx in (-1, 1):
    vs = list(VS)
    if sx < 0 and CHIMNEY:
        vs = [v for v in vs if not (DEPTH - FD - 0.15 < v < DEPTH + 0.15)] + [DEPTH - FD - 0.15, DEPTH + 0.15]
        # headers between the trimmers, above and below the chimney
        for u in (HOLES[0][1] - 0.05, HOLES[0][2] + 0.05):
            slope_box(rafters, sx, u - 0.05, u + 0.05, DEPTH - FD - 0.1, DEPTH + 0.1, 0.0, N_RAF)
    for v in vs:
        u_parts = [(0.0, U_EAVE)]
        if CHIMNEY and sx < 0 and DEPTH - FD - 0.1 < v < DEPTH + 0.1:
            u_parts = [(0.0, HOLES[0][1] - 0.1), (HOLES[0][2] + 0.1, U_EAVE)]
        for u0, u1 in u_parts:
            slope_box(rafters, sx, u0 + (0.0 if u0 else 0.0), u1, v - 0.05, v + 0.05, 0.0, N_RAF)
    slope_box(rafters, sx, U_EAVE, U_EAVE + 0.025, Y_F, Y_B, -0.02, N_BAT)       # fascia board
rafters.build("Rafters and fascia", RF, "timber", bevel=0.008, segments=1)

sheath, battens = Mesh(), Mesh()
for sx in (-1, 1):
    u = 0.0
    while u < U_EAVE:
        u1 = min(u + 0.18, U_EAVE)
        for v0, v1 in minus_holes(sx, u, u1, Y_F, Y_B):
            slope_box(sheath, sx, u + 0.002, u1 - 0.002, v0, v1, N_RAF, N_BRD)
        u = u1
EXPO, TL, TW, TT = 0.17, 0.38, 0.18, 0.014     # beaver-tail tiles: exposure, length, width, thickness
rows = int(U_EAVE / EXPO) + 2
for sx in (-1, 1):
    for r in range(rows):
        u_low = U_EAVE + 0.05 - r * EXPO
        ub = u_low - TL + 0.04                  # batten under the tile heads
        if ub < 0.02:
            continue
        for v0, v1 in minus_holes(sx, ub, ub + 0.05, Y_F, Y_B):
            slope_box(battens, sx, ub, ub + 0.05, v0, v1, N_BRD, N_BAT)
sheath.build("Roof sheathing boards", RF, "batten", bevel=0.002, segments=1)
battens.build("Tile battens", RF, "batten")

tiles = {k: Mesh() for k in ("tile_a", "tile_b", "tile_c")}
def tile(sx, u_low, v0, v1, n_low, n_high):
    """One beaver-tail tile, its rounded tail pointing down-slope, resting at n_high (head) and
    n_low (tail, lifted by the course below)."""
    u_head = u_low - TL
    vm, half = (v0 + v1) / 2, (v1 - v0) / 2
    outline = [(u_head, v0), (u_head, v1), (u_low - 0.05, v1)]
    for k in range(1, 6):
        t = math.pi / 2 * (1 - k / 6) * 2 - math.pi / 2       # sweep from +90deg to -90deg
        outline.append((u_low - 0.05 + 0.05 * math.cos(t), vm + half * math.sin(t)))
    outline.append((u_low - 0.05, v0))
    n_at = lambda u: n_high + (n_low - n_high) * (u - u_head) / TL
    bot = [slope_pt(sx, u, v, n_at(u)) for u, v in outline]
    top = [slope_pt(sx, u, v, n_at(u) + TT) for u, v in outline]
    tiles[rng.choice(list(tiles))].solid(bot, top)
for sx in (-1, 1):
    for r in range(rows):
        u_low = U_EAVE + 0.05 - r * EXPO
        if u_low - TL < -0.05:
            break
        v = Y_F - 0.04 - (TW / 2 if r % 2 else 0.0)
        while v < Y_B + 0.04:
            v0, v1 = max(v, Y_F - 0.04), min(v + TW, Y_B + 0.04)
            if v1 - v0 > 0.05 and not in_hole(sx, u_low - TL, u_low, v0, v1):
                tile(sx, u_low, v0 + 0.003, v1 - 0.003, N_BAT + TT + 0.004, N_BAT)
            v += TW
for k, m in tiles.items():
    m.build(f"Roof tiles {k[-1]}", RF, k, bevel=0.003, segments=1)

ridge = Mesh()
RC_R = 0.15
v = Y_F - 0.06
while v < Y_B + 0.06:
    L = 0.36
    c0 = (0.0, v, RIDGE - 0.16)
    seg = 10
    arc = [(math.cos(math.pi * k / seg), math.sin(math.pi * k / seg)) for k in range(seg + 1)]
    outer = [(RC_R * a, RC_R * b) for a, b in arc]
    inner = [(RC_R * 0.88 * a, RC_R * 0.88 * b) for a, b in arc][::-1]
    prof = outer + inner
    ridge.solid([(x, v, c0[2] + z) for x, z in prof], [(x * 1.06, v + L, c0[2] + z * 1.06) for x, z in prof])
    v += L - 0.05
ridge.build("Ridge caps", RF, "tile_b", bevel=0.003, segments=1)

verge = Mesh()
for y0, y1 in ((Y_F - 0.035, Y_F), (Y_B, Y_B + 0.035)):
    for sx in (-1, 1):
        prof = [slope_pt(sx, u, 0, n) for u, n in ((0.0, -0.12), (U_EAVE + 0.025, -0.12), (U_EAVE + 0.025, N_BAT), (0.0, N_BAT))]
        verge.solid([(p[0], y0, p[2]) for p in prof], [(p[0], y1, p[2]) for p in prof])
verge.build("Verge boards", RF, "timber_dark", bevel=0.006)

# ------------------------------------------------------------------ flues
FU = "17_Flues"
if CHIMNEY:
    ch = Mesh()
    cx0, cx1, cy0, cy1 = FX - FW / 2, FX + FW / 2, DEPTH - FD, DEPTH
    top = chimney_top()
    ch.box(cx0, cx1, cy0, cy1, FLOOR[3], top)                  # flue body from the attic floor up
    ch.build("Chimney flue body", FU, "mortar")
    cst = {k: Mesh() for k in ("stone_a", "stone_b", "stone_c")}
    z = FLOOR[3] + 0.01
    while z < top - 0.05:
        h = min(rng.uniform(0.16, 0.24), top - z)
        for face in range(4):
            if face == 0:
                u0, u1, mk = cx0, cx1, lambda u, d, zz: (u, cy0 - d, zz)
            elif face == 1:
                u0, u1, mk = cx0, cx1, lambda u, d, zz: (u, cy1 + d, zz)
            elif face == 2:
                u0, u1, mk = cy0, cy1, lambda u, d, zz: (cx0 - d, u, zz)
            else:
                u0, u1, mk = cy0, cy1, lambda u, d, zz: (cx1 + d, u, zz)
            if face == 1 and z < roof_under(cx0) - 0.3:
                continue                                        # back face hidden in the gable wall
            u = u0 - rng.uniform(0, 0.12)
            while u < u1:
                L = rng.uniform(0.18, 0.32)
                a, b = max(u, u0) + 0.006, min(u + L, u1) - 0.006
                if b - a > 0.05:
                    cst[rng.choice(list(cst))].mapped_box(mk, a, b, -0.005, 0.04, z + 0.006, z + h - 0.006)
                u += L
        z += h
    for k, m in cst.items():
        m.build(f"Chimney stones {k[-1]}", FU, k, bevel=0.012, segments=2)
    hat = Mesh()
    hat.box(cx0 - 0.08, cx1 + 0.08, cy0 - 0.08, cy1 + 0.08, top, top + 0.07)
    for px in (cx0 - 0.02, cx1 - 0.1):
        for py in (cy0 - 0.02, cy1 - 0.1):
            hat.box(px, px + 0.12, py, py + 0.12, top + 0.07, top + 0.26)
    hat.box(cx0 - 0.12, cx1 + 0.12, cy0 - 0.12, cy1 + 0.12, top + 0.26, top + 0.33)
    hat.build("Chimney cap and hood", FU, "stone_c", bevel=0.01)
    flash = Mesh()
    u0, u1, v0, v1 = HOLES[0][1:]
    for (ua, ub, va, vb) in ((u0 - 0.06, u1 + 0.06, v0 - 0.06, v0 + 0.01), (u0 - 0.06, u1 + 0.06, v1 - 0.01, v1 + 0.06),
                             (u0 - 0.06, u0 + 0.01, v0, v1), (u1 - 0.01, u1 + 0.06, v0, v1)):
        slope_box(flash, -1, ua, ub, va, vb, N_BAT + 0.032, N_BAT + 0.036)   # apron on the tiles around the stack
    # step flashing as thin sheets just outside the facing stones (which stand 4 cm proud of the body)
    for x0, x1, y0_, y1_ in ((cx0 - 0.053, cx0 - 0.045, cy0 - 0.053, cy1 + 0.053), (cx1 + 0.045, cx1 + 0.053, cy0 - 0.053, cy1 + 0.053),
                             (cx0 - 0.053, cx1 + 0.053, cy0 - 0.053, cy0 - 0.045), (cx0 - 0.053, cx1 + 0.053, cy1 + 0.045, cy1 + 0.053)):
        zlo = roof_top(max(abs(x0), abs(x1))) - 0.1
        flash.box(x0, x1, y0_, y1_, zlo, roof_top(min(abs(x0), abs(x1))) + 0.12)
    flash.build("Chimney flashing", FU, "flashing")

# hood duct: round duct through the back wall into a louvred stainless vent cap on the outside
steel = Mesh()
VZ = FLOOR[1] + FLUE_Z
steel.cylinder((FLUE_X, DEPTH - 0.02, VZ), (0, 1, 0), 0.075, WALL_T + 0.04)             # duct sleeve
OY = DEPTH + WALL_T
steel.box(FLUE_X - 0.14, FLUE_X + 0.14, OY, OY + 0.006, VZ - 0.14, VZ + 0.14)          # wall plate
steel.box(FLUE_X - 0.12, FLUE_X - 0.11, OY, OY + 0.07, VZ - 0.12, VZ + 0.12)           # cap sides
steel.box(FLUE_X + 0.11, FLUE_X + 0.12, OY, OY + 0.07, VZ - 0.12, VZ + 0.12)
steel.box(FLUE_X - 0.12, FLUE_X + 0.12, OY, OY + 0.08, VZ + 0.11, VZ + 0.125)          # hood top
for k in range(5):                                                                      # louvres
    zz = VZ + 0.09 - k * 0.045
    steel.solid([(FLUE_X - 0.11, OY + 0.01, zz - 0.03), (FLUE_X + 0.11, OY + 0.01, zz - 0.03),
                 (FLUE_X + 0.11, OY + 0.07, zz - 0.035), (FLUE_X - 0.11, OY + 0.07, zz - 0.035)],
                [(FLUE_X - 0.11, OY + 0.01, zz), (FLUE_X + 0.11, OY + 0.01, zz),
                 (FLUE_X + 0.11, OY + 0.07, zz - 0.026), (FLUE_X - 0.11, OY + 0.07, zz - 0.026)])
steel.build("Hood vent (stainless)", FU, "steel")

bolts.build("Bolt heads", FR, "iron")

# ------------------------------------------------------------------ detail cameras
def look_cam(name, loc, target, lens=35):
    cd = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    cd.lens, cd.clip_start, cd.clip_end = lens, 0.05, 5000
    o = bpy.data.objects.get(name)
    if o is None:
        o = bpy.data.objects.new(name, cd)
        bpy.data.collections["08_Cameras"].objects.link(o)
    o.location = loc
    d = Vector(target) - Vector(loc)
    o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return o

look_cam("Cam_Detail_Eave_Front", (-7.6, -4.6, 5.0), (-5.0, -0.5, 6.4), 35)
look_cam("Cam_Detail_Steps", (2.4, -3.6, 1.3), (0.0, -0.3, 0.35), 30)
look_cam("Cam_Detail_Window_F2", (0.4, 2.6, FLOOR[2] + 1.15), (0.65, DEPTH, FLOOR[2] + 1.2), 32)
look_cam("Cam_Detail_Attic_Roof", (1.5, 1.2, FLOOR[3] + 1.0), (-2.6, 3.6, 7.4), 24)
# look_cam("Cam_Detail_Chimney", (-9.5, 10.5, 11.0), (FX, DEPTH - 0.3, 8.4), 40)
look_cam("Cam_Detail_Ceiling_F1", (1.0, 1.0, FLOOR[1] + 1.1), (-1.0, 3.5, FLOOR[2] - 0.2), 22)
look_cam("Cam_Detail_Back_Flue", (4.0, 9.0, 2.6), (FLUE_X, DEPTH + 0.2, FLOOR[1] + FLUE_Z), 32)

bpy.ops.wm.save_mainfile()
nv = sum(len(o.data.vertices) for c in NEW for o in bpy.data.collections[c].objects if o.type == 'MESH')
print("ARCH_SAVED", len([o for c in NEW for o in bpy.data.collections[c].objects]), "objects", nv, "verts")
