"""Whitebox (stage 1) of the companion house, built at real scale.

Run:  Blender -b --factory-startup --python build_whitebox.py
Writes assets/blender/companion-house.blend (overwrites it).

Units: metres, Z up. Origin = centre of the front face of the house at ground level.
The house opens toward -Y (camera side); the back wall's interior face is at y = DEPTH.
Positions are measured from the 2026-10-19 target image with a perspective camera
(see docs/3d-modeling-plan.md); furniture sizes follow the chibi character (1.35 m),
not the image, so the furniture is slightly cartoon-scaled.
"""
import bpy, math, random, os
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
OUT = os.path.join(ROOT, "assets", "blender", "companion-house.blend")
rng = random.Random(19)

# ------------------------------------------------------------------ dimensions
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from house_spec import *   # noqa: E402,F401  shared with build_architecture.py

# ------------------------------------------------------------------ scene reset
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
for c in list(bpy.data.collections):
    bpy.data.collections.remove(c)
sc = bpy.context.scene
sc.unit_settings.system = 'METRIC'

COLS = {}
def col(name):
    if name not in COLS:
        c = bpy.data.collections.new(name)
        sc.collection.children.link(c)
        COLS[name] = c
    return COLS[name]

PALETTE = {
    "timber": (0.62, 0.46, 0.32), "wall": (0.78, 0.66, 0.52), "floor": (0.84, 0.74, 0.60),
    "roof": (0.80, 0.38, 0.24), "stone": (0.70, 0.71, 0.72), "glass": (0.62, 0.80, 0.95),
    "wood": (0.86, 0.80, 0.72), "fabric_red": (0.80, 0.42, 0.40), "fabric_green": (0.58, 0.72, 0.48),
    "fabric": (0.93, 0.91, 0.86), "metal": (0.36, 0.42, 0.62), "plant": (0.42, 0.66, 0.38),
    "pot": (0.85, 0.55, 0.45), "fire": (1.0, 0.62, 0.25), "char": (0.98, 0.55, 0.78),
    "grass": (0.55, 0.74, 0.40), "pine": (0.24, 0.48, 0.34), "trunk": (0.45, 0.33, 0.25),
    "water": (0.40, 0.66, 0.85), "snow": (0.96, 0.97, 1.0), "rock": (0.48, 0.52, 0.60),
    "hill": (0.27, 0.42, 0.34), "book": (0.55, 0.62, 0.80), "cutter": (1, 0, 0),
}

def finish(o, c, color):
    for uc in list(o.users_collection):
        uc.objects.unlink(o)
    col(c).objects.link(o)
    o.color = (*PALETTE[color], 1.0)
    return o

def box(name, c, size, at, color="wood", rz=0.0, rx=0.0, ry=0.0):
    """size = (sx, sy, sz); at = (cx, cy, z_bottom)."""
    sx, sy, sz = size
    bpy.ops.mesh.primitive_cube_add(size=1)
    o = bpy.context.object
    o.name = name
    o.scale = (sx, sy, sz)
    o.location = (at[0], at[1], at[2] + sz / 2)
    o.rotation_euler = (rx, ry, rz)
    return finish(o, c, color)

def beam(name, c, p1, p2, w, h, color="timber"):
    """Timber of cross-section w x h running from point p1 to p2 (end centres)."""
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    bpy.ops.mesh.primitive_cube_add(size=1)
    o = bpy.context.object
    o.name = name
    o.scale = (w, h, d.length)
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    o.location = (p1 + p2) / 2
    return finish(o, c, color)

def cyl(name, c, r, h, at, color="wood", r2=None, verts=24, rx=0.0, rz=0.0):
    if r2 is None:
        bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, vertices=verts)
    else:
        bpy.ops.mesh.primitive_cone_add(radius1=r, radius2=r2, depth=h, vertices=verts)
    o = bpy.context.object
    o.name = name
    o.location = (at[0], at[1], at[2] + h / 2)
    o.rotation_euler = (rx, 0, rz)
    return finish(o, c, color)

def ball(name, c, r, at, color="plant", scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=20, ring_count=12)
    o = bpy.context.object
    o.name = name
    o.location = at
    o.scale = scale
    return finish(o, c, color)

def local(x, y, z, ox, oy, rz):
    """Point in an object's local frame (front = -Y) -> world."""
    v = Vector((x, y, z))
    v.rotate(__import__("mathutils").Euler((0, 0, rz)))
    return (ox + v.x, oy + v.y, z)

def cut(target, name, size, at, rz=0.0):
    """Boolean window/door opening; the cutter stays hidden for later edits."""
    k = box(name, "90_Cutters", size, at, "cutter", rz)
    k.display_type = 'WIRE'
    k.hide_render = True
    m = target.modifiers.new(name, 'BOOLEAN')
    m.operation = 'DIFFERENCE'
    m.object = k
    m.solver = 'EXACT'
    return k

# ------------------------------------------------------------------ furniture kit
def chair(name, c, x, y, z, rz, seat=0.36, w=0.42, back=0.82, color="wood"):
    box(name + " seat", c, (w, w, 0.05), local(0, 0, z + seat - 0.05, x, y, rz), color, rz)
    box(name + " back", c, (w, 0.05, back - seat), local(0, w / 2 - 0.025, z + seat, x, y, rz), color, rz)
    for i, (lx, ly) in enumerate([(-1, -1), (1, -1), (-1, 1), (1, 1)]):
        box(f"{name} leg {i}", c, (0.045, 0.045, seat - 0.05),
            local(lx * (w / 2 - 0.03), ly * (w / 2 - 0.03), z, x, y, rz), color, rz)

def stool(name, c, x, y, z, h=0.42, r=0.17):
    cyl(name + " top", c, r, 0.05, (x, y, z + h - 0.05))
    for i in range(3):
        a = i * 2 * math.pi / 3
        box(f"{name} leg {i}", c, (0.04, 0.04, h - 0.05), (x + 0.11 * math.cos(a), y + 0.11 * math.sin(a), z))

def table(name, c, x, y, z, w, d, h, rz=0.0, shelf=False, color="wood"):
    box(name + " top", c, (w, d, 0.06), (x, y, z + h - 0.06), color, rz)
    for i, (lx, ly) in enumerate([(-1, -1), (1, -1), (-1, 1), (1, 1)]):
        box(f"{name} leg {i}", c, (0.07, 0.07, h - 0.06),
            local(lx * (w / 2 - 0.06), ly * (d / 2 - 0.06), z, x, y, rz), color, rz)
    if shelf:
        box(name + " shelf", c, (w - 0.12, d - 0.12, 0.04), (x, y, z + 0.15), color, rz)

def armchair(name, c, x, y, z, rz, color="fabric_green"):
    W, D = 0.95, 0.85
    box(name + " base", c, (W, D, 0.36), (x, y, z + 0.06), color, rz)
    box(name + " back", c, (W, 0.22, 0.62), local(0, D / 2 - 0.11, z + 0.36, x, y, rz), color, rz)
    for s in (-1, 1):
        box(f"{name} arm {s}", c, (0.18, D - 0.1, 0.24), local(s * (W / 2 - 0.09), 0.05, z + 0.36, x, y, rz), color, rz)
    for i, (lx, ly) in enumerate([(-1, -1), (1, -1), (-1, 1), (1, 1)]):
        box(f"{name} foot {i}", c, (0.06, 0.06, 0.06), local(lx * 0.4, ly * 0.35, z, x, y, rz), "wood", rz)

def plant(name, c, x, y, z, h=0.8, r=0.16, crown=0.32):
    cyl(name + " pot", c, r, r * 1.6, (x, y, z), "pot", r2=r * 0.75)
    return ball(name + " leaves", c, crown, (x, y, z + r * 1.6 + crown * 0.9 + max(0, h - 2 * crown - r * 1.6)),
         "plant", (1, 1, 1.15))

def shelf_unit(name, c, x, y, z, w, d, h, boards, rz=0.0, books=True):
    box(name + " back", c, (w, 0.03, h), local(0, d / 2 - 0.015, z, x, y, rz), "wood", rz)
    for s in (-1, 1):
        box(f"{name} side {s}", c, (0.04, d, h), local(s * (w / 2 - 0.02), 0, z, x, y, rz), "wood", rz)
    for i, bz in enumerate(boards):
        box(f"{name} board {i}", c, (w, d, 0.03), (x, y, z + bz), "wood", rz)
        if books and i < len(boards) - 1:
            gap = boards[i + 1] - bz
            box(f"{name} books {i}", c, (w * 0.7, d * 0.7, min(0.26, gap * 0.75)),
                local(rng.uniform(-0.05, 0.05), 0, z + bz + 0.03, x, y, rz), "book", rz)

def wall_shelf(name, c, x, y, z, w, d=0.22, color="wood"):
    box(name, c, (w, d, 0.04), (x, y, z), color)

def person(name, c, x, y, z, rz=0.0, seated=False):
    """Proportion block from the approved chibi turnaround (about 2.3 heads tall)."""
    head_r = 0.29
    if seated:
        box(name + " legs", c, (0.26, 0.42, 0.12), local(0, -0.21, z + 0.30, x, y, rz), "char", rz)
        cyl(name + " body", c, 0.21, 0.50, local(0, 0.08, z + 0.32, x, y, rz), "char", r2=0.15)
        ball(name + " head", c, head_r, local(0, 0.05, z + 0.32 + 0.50 + head_r * 0.85, x, y, rz), "char")
    else:
        for s in (-1, 1):
            cyl(f"{name} leg {s}", c, 0.065, 0.36, local(s * 0.08, 0, z, x, y, rz), "char")
        cyl(name + " dress", c, 0.25, 0.48, (x, y, z + 0.34), "char", r2=0.15)
        ball(name + " head", c, head_r, (x, y, z + 0.82 + head_r * 0.95), "char")

def window_frame(name, c, plane, a, b, z0, z1, fixed):
    """Glass + frame inside an opening. plane 'y' = back wall (a..b along x, at y=fixed);
    plane 'x' = side wall (a..b along y, at x=fixed)."""
    t = 0.06
    if plane == "y":
        box(name + " glass", c, (b - a, 0.02, z1 - z0), ((a + b) / 2, fixed, z0), "glass")
        box(name + " sill", c, (b - a + 0.16, 0.2, 0.05), ((a + b) / 2, fixed - 0.06, z0 - 0.05), "timber")
        box(name + " mullion", c, (t, 0.05, z1 - z0), ((a + b) / 2, fixed - 0.02, z0), "timber")
        box(name + " transom", c, (b - a, 0.05, t), ((a + b) / 2, fixed - 0.02, (z0 + z1) / 2), "timber")
    else:
        box(name + " glass", c, (0.02, b - a, z1 - z0), (fixed, (a + b) / 2, z0), "glass")
        box(name + " mullion", c, (0.05, t, z1 - z0), (fixed, (a + b) / 2, z0), "timber")

def curtains(name, c, a, b, z0, z1, y):
    for s, xx in (("L", a - 0.12), ("R", b + 0.12)):
        box(f"{name} curtain {s}", c, (0.26, 0.08, z1 - z0 + 0.15), (xx, y - 0.1, z0 - 0.1), "fabric")
    box(name + " rod", c, (b - a + 0.7, 0.03, 0.03), ((a + b) / 2, y - 0.12, z1 + 0.1), "metal")

# ------------------------------------------------------------------ structure
S = "01_Structure"
box("Stone plinth", "03_Stonework", (2 * HALF_W + 0.4, DEPTH + 0.55, BASE_H), (0, DEPTH / 2 + 0.1, 0), "stone")
for i, top in enumerate((0.45, 0.30, 0.15)):
    box(f"Front step {i + 1}", "03_Stonework", (2.0, 0.32, top), (0, -0.16 - 0.32 * i, 0), "stone")

# slabs stop 1 cm short of the wall faces so no two surfaces share a plane
SLAB_D = DEPTH + WALL_T - 0.01
box("Floor 1 boards", S, (2 * HALF_W - 0.02, SLAB_D, FLOOR[1] - BASE_H), (0, SLAB_D / 2, BASE_H), "floor")
for f in (2, 3):
    box(f"Floor {f} slab", S, (2 * HALF_W - 0.02, SLAB_D, SLAB), (0, SLAB_D / 2, FLOOR[f] - SLAB), "floor")
    box(f"Floor {f} front beam", S, (2 * HALF_W + 0.7, 0.32, SLAB), (0, -0.02, FLOOR[f] - SLAB), "timber")

# Roof carrying chain (purlin roof): roof deck -> purlins -> front truss / back gable -> posts.
PURLIN = 0.24                        # purlin depth (square section)
EAVE_PX = HALF_W - POST / 2          # eave purlins sit on the post centrelines
MID_PX = 2.6                         # middle purlins
def purlin_top(x):
    return roof_under(x)
post_top = purlin_top(EAVE_PX) - PURLIN
for sx in (-1, 1):
    for yy, tag in ((POST / 2, "front"), (DEPTH + WALL_T - POST / 2, "back")):
        box(f"Post {tag} {'L' if sx < 0 else 'R'}", S, (POST, POST, post_top - BASE_H),
            (sx * (HALF_W - POST / 2), yy, BASE_H), "timber")
    # knee braces: from the post's inner face up to the underside of each front beam
    for f in (2, 3):
        under = FLOOR[f] - SLAB
        beam(f"Brace {f} {'L' if sx < 0 else 'R'}", S, (sx * (HALF_W - POST + 0.03), POST / 2, under - 0.62),
             (sx * (HALF_W - POST - 0.55), POST / 2, under + 0.03), 0.14, 0.14)

# back wall (floors 1-2) and side walls, with window openings
back = box("Back wall F1-F2", S, (2 * IN_X, WALL_T, FLOOR[3] - FLOOR[1]), (0, DEPTH + WALL_T / 2, FLOOR[1]), "wall")
for f, (a, b, z0, z1) in ((f, w) for f, w in WIN_BACK.items() if f < 3):
    cut(back, f"Cut back F{f}", (b - a, 0.6, z1 - z0), ((a + b) / 2, DEPTH + WALL_T / 2, FLOOR[f] + z0))
    window_frame(f"Window back F{f}", S, "y", a, b, FLOOR[f] + z0, FLOOR[f] + z1, DEPTH + 0.05)
    curtains(f"Window back F{f}", f"0{f + 2}_Floor{f}", a, b, FLOOR[f] + z0, FLOOR[f] + z1, DEPTH)

for sx in (-1, 1):
    side_len = DEPTH + WALL_T - 2 * POST
    side = box(f"Side wall {'L' if sx < 0 else 'R'} F1-F2", S, (WALL_T, side_len, FLOOR[3] - FLOOR[1]),
               (sx * (IN_X + WALL_T / 2), POST + side_len / 2, FLOOR[1]), "wall")
    for f in (1, 2):
        if (f, sx) not in SIDE_WIN:
            continue
        yc = SIDE_WIN[(f, sx)]
        ws = side_win_sill(f, sx)
        ww, wh = side_win_w(f, sx), side_win_head(f, sx)
        cut(side, f"Cut side F{f} {sx}", (0.6, ww, wh - ws), (sx * (IN_X + WALL_T / 2), yc, FLOOR[f] + ws))
        window_frame(f"Window side F{f} {sx}", S, "x", yc - ww / 2, yc + ww / 2, FLOOR[f] + ws, FLOOR[f] + wh,
                     sx * (IN_X + 0.05))
    knee = roof_under(IN_X) - FLOOR[3]
    box(f"Knee wall {'L' if sx < 0 else 'R'} F3", S, (WALL_T, side_len, knee),
        (sx * (IN_X + WALL_T / 2), POST + side_len / 2, FLOOR[3]), "wall")

# attic gable (back), extruded from its outline, with the window cut
top_in = roof_under(0)
pts = [(-IN_X, FLOOR[3]), (IN_X, FLOOR[3]), (IN_X, roof_under(IN_X)), (0, top_in), (-IN_X, roof_under(IN_X))]
me = bpy.data.meshes.new("Gable")
vs = [(x, DEPTH, z) for x, z in pts] + [(x, DEPTH + WALL_T, z) for x, z in pts]
n = len(pts)
faces = [list(range(n))[::-1], list(range(n, 2 * n))] + [[i, (i + 1) % n, n + (i + 1) % n, n + i] for i in range(n)]
me.from_pydata(vs, [], faces)
gable = bpy.data.objects.new("Back gable F3", me)
sc.collection.objects.link(gable)
finish(gable, S, "wall")
cut(gable, "Cut back F3", (1.6, 0.6, 0.95), (0.05, DEPTH + WALL_T / 2, FLOOR[3] + 0.75))
window_frame("Window back F3", S, "y", -0.75, 0.85, FLOOR[3] + 0.75, FLOOR[3] + 1.70, DEPTH + 0.05)
curtains("Window back F3", "05_Floor3", -0.75, 0.85, FLOOR[3] + 0.75, FLOOR[3] + 1.70, DEPTH)

# roof deck (rafters + boards + tiles as one slab), purlins, front truss
R = "02_Roof"
y_front, y_back = -OVER_F, DEPTH + WALL_T + OVER_B
length = y_back - y_front
slope_len = EAVE_X / math.cos(PITCH)
for sx in (-1, 1):
    cx = sx * EAVE_X / 2
    cz = RIDGE - math.tan(PITCH) * EAVE_X / 2 - ROOF_T / 2 / math.cos(PITCH)
    box(f"Roof deck {'L' if sx < 0 else 'R'}", R, (slope_len, length, ROOF_T),
        (cx, (y_front + y_back) / 2, cz - ROOF_T / 2), "roof", ry=sx * PITCH)
    # verge board along the front edge of the deck
    beam(f"Verge board {'L' if sx < 0 else 'R'}", R, (0, y_front + 0.03, RIDGE - 0.02),
         (sx * EAVE_X, y_front + 0.03, RIDGE - math.tan(PITCH) * EAVE_X - 0.02), 0.06, 0.34)
# purlins run front-to-back under the deck, carried by the front truss and the back gable
for name, x in (("Ridge purlin", 0.0), ("Purlin mid L", -MID_PX), ("Purlin mid R", MID_PX),
                ("Eave purlin L", -EAVE_PX), ("Eave purlin R", EAVE_PX)):
    box(name, R, (PURLIN, length, PURLIN), (x, (y_front + y_back) / 2, purlin_top(x) - PURLIN), "timber")
# front truss in the plane y = POST / 2: principal rafters under the purlins, collar, king post, struts
TY = POST / 2
RAFTER = 0.22
def rafter_under(x):
    return purlin_top(x) - PURLIN - RAFTER / math.cos(PITCH)
for sx in (-1, 1):
    beam(f"Principal rafter {'L' if sx < 0 else 'R'}", R,
         (sx * EAVE_PX, TY, post_top - RAFTER / 2), (0, TY, purlin_top(0) - PURLIN - RAFTER / 2), 0.22, RAFTER)
COLLAR = FLOOR[3] + 2.2
x_c = (purlin_top(0) - PURLIN - RAFTER / math.cos(PITCH) - (COLLAR + 0.24)) / math.tan(PITCH)
box("Collar beam", R, (2 * x_c + 0.2, 0.2, 0.24), (0, TY, COLLAR), "timber")
box("King post", R, (0.22, 0.2, rafter_under(0) - COLLAR - 0.24 + 0.05), (0, TY, COLLAR + 0.24), "timber")
for sx in (-1, 1):
    beam(f"Strut {'L' if sx < 0 else 'R'}", R, (sx * 0.1, TY, COLLAR + 0.3),
         (sx * 1.1, TY, rafter_under(1.1) + 0.03), 0.16, 0.16)

# ------------------------------------------------------------------ floor 1: dining + kitchen
C1, z = "03_Floor1", FLOOR[1]
# dining set, bed and desk enlarged about 1.2x on 10-19 (they read too small next to the character)
DCH = dict(seat=0.44, w=0.48, back=0.98)
table("Dining table", C1, -2.6, 2.6, z, 2.3, 1.0, TABLE_H)
chair("Dining chair W", C1, -4.07, 2.6, z, math.radians(90), **DCH)
chair("Dining chair S1", C1, -3.1, 1.8, z, math.radians(180), **DCH)
chair("Dining chair S2", C1, -2.1, 1.8, z, math.radians(180), **DCH)
chair("Dining chair E", C1, -1.13, 2.6, z, math.radians(-90), **DCH)
cyl("Dining pendant shade", C1, 0.24, 0.16, (-2.6, 2.6, z + 1.62), "fabric", r2=0.06)
cyl("Dining pendant cord", C1, 0.01, CLEAR - 1.78, (-2.6, 2.6, z + 1.78), "metal")
cyl("Table vase", C1, 0.07, 0.2, (-2.6, 2.75, z + TABLE_H), "fabric")
ball("Table flowers", C1, 0.14, (-2.6, 2.75, z + TABLE_H + 0.3), "plant")
for i, bz in enumerate((0.85, 1.2, 1.55)):
    wall_shelf(f"Jar shelf right {i}", C1, -1.35, DEPTH - 0.11, z + bz, 0.8)
    for j in range(3):
        cyl(f"Jar R{i}{j}", C1, 0.04, 0.13, (-1.6 + j * 0.24, DEPTH - 0.11, z + bz + 0.04), "glass")
for i, bz in enumerate((1.1, 1.45)):
    wall_shelf(f"Jar shelf left {i}", C1, -4.2, DEPTH - 0.11, z + bz, 0.7)
plant("Climbing plant", C1, -4.3, 0.7, z, h=1.6, r=0.18, crown=0.3).scale = (0.8, 0.8, 2.2)
# kitchen run along the back wall
# kitchen enlarged with the dining set on 10-19; worktops COUNTER_H, a little above the table
box("Backsplash tiles", C1, (2.95, 0.03, 0.7), (3.25, DEPTH - 0.015, z + COUNTER_H), "fabric")
box("Cast-iron stove", C1, (1.2, 0.66, COUNTER_H), (2.35, DEPTH - 0.33, z), "metal")
cyl("Stockpot", C1, 0.2, 0.26, (2.4, DEPTH - 0.33, z + COUNTER_H), "metal")
box("Back counter", C1, (1.55, 0.66, COUNTER_H), (3.94, DEPTH - 0.33, z), "wood")
box("Farmhouse sink", C1, (0.6, 0.52, 0.2), (3.465, DEPTH - 0.34, z + COUNTER_H - 0.17), "fabric")
box("Side counter", C1, (0.66, 2.34, COUNTER_H), (IN_X - 0.33, 3.17, z), "wood")
box("Pan rail", C1, (1.1, 0.05, 0.05), (2.15, DEPTH - 0.04, z + 1.64), "timber")
for j in range(5):
    cyl(f"Hanging pan {j}", C1, 0.1 if j % 2 else 0.05, 0.03, (1.7 + j * 0.2, DEPTH - 0.1, z + 1.36), "metal",
        rx=math.pi / 2)
wall_shelf("Dish shelf", C1, 4.0, DEPTH - 0.11, z + 1.66, 1.1)
table("Kitchen island", C1, 1.6, 2.5, z, 1.9, 0.95, COUNTER_H, shelf=True)
ball("Island produce bowl", C1, 0.14, (1.4, 2.5, z + COUNTER_H + 0.04), "pot", (1.3, 1.3, 0.6))
stool("Island stool 1", C1, 1.15, 1.62, z, h=BAR_STOOL_H)
stool("Island stool 2", C1, 2.05, 1.62, z, h=BAR_STOOL_H)
box("Rug entry", C1, (1.2, 0.65, 0.01), (-0.1, 1.0, z), "fabric")
box("Rug kitchen", C1, (1.2, 0.65, 0.01), (2.9, 1.0, z), "fabric")
cyl("Wall sconce F1", C1, 0.07, 0.18, (0.8, DEPTH - 0.08, z + 1.45), "fire")

# ------------------------------------------------------------------ floor 2: hearth + reading + desk
C2, z = "04_Floor2", FLOOR[2]
box("Hearth stone", C2, (1.35, 0.45, 0.08), (-4.0, 3.95, z), "stone")
box("Fireplace body", C2, (1.12, 0.72, 1.0), (-4.12, DEPTH - 0.36, z), "stone")
box("Fireplace firebox", C2, (0.6, 0.1, 0.5), (-4.12, DEPTH - 0.75, z + 0.12), "fire")
box("Fireplace mantel", C2, (1.2, 0.82, 0.08), (-4.11, DEPTH - 0.41, z + 1.0), "timber")
box("Chimney breast", C2, (0.8, 0.5, CLEAR - 1.08), (-4.12, DEPTH - 0.25, z + 1.08), "stone")

# ------------------------------------------------------------------ flues (user choice: up the back wall)
# Fireplace: masonry flue continues through the attic's back-left corner and out of the left roof
# slope. Height rule: 0.9 m above where it leaves the roof and 0.6 m above any roof within 3 m.
FX, FW, FD = -4.12, 0.6, 0.5
roof_top = lambda x: RIDGE - math.tan(PITCH) * abs(x)
fl_top = max(roof_top(FX + FW / 2) + 0.9, roof_top(FX + FW / 2 + 3.0) + 0.6)
box("Chimney flue attic", "05_Floor3", (FW, FD, roof_under(FX + FW / 2) - FLOOR[3] + 0.05), (FX, DEPTH - FD / 2, FLOOR[3]), "stone")
box("Chimney stack", "02_Roof", (FW + 0.1, FD + 0.1, fl_top - roof_under(FX + FW / 2) + 0.05),
    (FX, DEPTH - FD / 2, roof_under(FX + FW / 2)), "stone")
box("Chimney cap", "02_Roof", (FW + 0.25, FD + 0.25, 0.08), (FX, DEPTH - FD / 2, fl_top), "stone")
cut(bpy.data.objects["Roof deck L"], "Cut roof chimney", (FW + 0.12, FD + 0.12, 3.0),
    (FX, DEPTH - FD / 2, roof_under(FX) - 1.0))
# Cast-iron range: stove pipe straight back through the wall into an insulated steel flue fixed to
# the outside of the back wall, through the back eave, ending 0.6 m above the ridge (within 3 m).
# stove centre SX and flue line FLUE_X come from house_spec.py
# vertical stub from the back of the range top, then an elbow straight back through the wall
cyl("Stove pipe riser", C1, 0.08, FLUE_Z - COUNTER_H + 0.08, (FLUE_X, DEPTH - 0.12, FLOOR[1] + COUNTER_H), "metal")
cyl("Stove pipe through wall", C1, 0.08, 0.45, (FLUE_X, DEPTH + 0.1, 0), "metal",
    rx=math.pi / 2).location = (FLUE_X, DEPTH + 0.1, FLOOR[1] + FLUE_Z)
sp_top = RIDGE + 0.6
cyl("Stove flue exterior", "02_Roof", 0.1, sp_top - (FLOOR[1] + 1.0), (FLUE_X, DEPTH + WALL_T + 0.2, FLOOR[1] + 1.0), "metal")
for i, zz in enumerate((FLOOR[2] - 0.3, FLOOR[3] - 0.3, FLOOR[3] + 0.6)):
    box(f"Flue bracket {i}", "02_Roof", (0.06, 0.24, 0.04), (FLUE_X, DEPTH + WALL_T + 0.1, zz), "metal")
cyl("Stove flue cap", "02_Roof", 0.16, 0.12, (FLUE_X, DEPTH + WALL_T + 0.2, sp_top), "metal", r2=0.02)
cut(bpy.data.objects["Roof deck R"], "Cut roof stove flue", (0.3, 0.3, 3.0),
    (FLUE_X, DEPTH + WALL_T + 0.2, roof_under(FLUE_X) - 1.0))
armchair("Armchair reading", C2, -2.45, 2.65, z, math.radians(60))
box("Plaid throw", C2, (0.5, 0.08, 0.5), local(0, 0.3, z + 0.55, -2.45, 2.65, math.radians(60)), "fabric_red",
    math.radians(60))
person("Owner seated", "00_Reference", -2.5, 2.7, z + 0.14, math.radians(60), seated=True)   # on the 1.1x rocking chair
table("Coffee table", C2, -0.3, 2.5, z, 1.15, 0.6, 0.40, shelf=True)
cyl("Coffee vase", C2, 0.08, 0.22, (-0.4, 2.5, z + 0.40), "fabric")
ball("Coffee flowers", C2, 0.16, (-0.4, 2.5, z + 0.75), "plant")
armchair("Armchair guest", C2, 1.6, 2.85, z, math.radians(-60))
plant("Window plant", C2, -0.7, 4.5, z, h=1.2, r=0.2, crown=0.38)
shelf_unit("Living bookcase", C2, 3.27, DEPTH - 0.2, z, 1.65, 0.4, 2.0, (0.0, 0.8, 1.2, 1.6, 1.97))
box("Bookcase cabinet doors", C2, (1.6, 0.03, 0.78), (3.27, DEPTH - 0.41, z + 0.02), "timber")
table("Desk", C2, IN_X - 0.4, 1.9, z, 0.8, 1.8, TABLE_H)
box("Monitor screen", C2, (0.05, 0.62, 0.42), (IN_X - 0.48, 1.9, z + TABLE_H + 0.18), "metal")
box("Monitor stand", C2, (0.12, 0.12, 0.2), (IN_X - 0.41, 1.9, z + TABLE_H), "fabric")
box("Keyboard", C2, (0.15, 0.42, 0.02), (IN_X - 0.72, 1.9, z + TABLE_H), "fabric")
chair("Desk chair", C2, IN_X - 1.18, 1.9, z, math.radians(90), **DCH)
stool("Desk stool", C2, IN_X - 0.4, 0.55, z, h=0.6)
stool("Hearth stool", C2, -3.3, 3.55, z, h=0.3, r=0.2)
plant("Hearth plant", C2, -4.3, 0.9, z, h=0.9)
box("Living rug", C2, (5.0, 2.2, 0.01), (-0.6, 2.7, z), "fabric_red")
for i, (xx, yy) in enumerate(((-2.7, DEPTH - 0.08), (2.2, DEPTH - 0.08))):
    cyl(f"Wall sconce F2 {i}", C2, 0.07, 0.2, (xx, yy, z + 1.5), "fire")

# ------------------------------------------------------------------ floor 3: attic bedroom
C3, z = "05_Floor3", FLOOR[3]
# bed side-on to the overview camera (as in the target image): long side along the back wall,
# headboard at the left end beside the nightstand
BED_X, BED_Y = -1.0, DEPTH - 0.92
box("Bed frame", C3, (2.4, 1.8, 0.32), (BED_X, BED_Y, z), "wood")
box("Mattress", C3, (2.2, 1.7, 0.2), (BED_X - 0.01, BED_Y, z + 0.32), "fabric")
box("Bedspread", C3, (1.75, 1.82, 0.05), (BED_X + 0.32, BED_Y, z + 0.5), "fabric_red")
box("Headboard", C3, (0.1, 1.8, 0.85), (BED_X - 1.15, BED_Y, z), "wood")
box("Footboard", C3, (0.08, 1.8, 0.52), (BED_X + 1.16, BED_Y, z), "wood")
for s_ in (-1, 1):
    box(f"Pillow {s_}", C3, (0.4, 0.7, 0.16), (BED_X - 0.88, BED_Y + s_ * 0.42, z + 0.52), "fabric")
box("Bed-front trunk", C3, (1.1, 0.48, 0.48), (BED_X + 0.35, BED_Y - 1.2, z), "timber")
box("Nightstand", C3, (0.5, 0.42, 0.58), (-2.52, DEPTH - 0.23, z), "wood")
cyl("Bedside lamp", C3, 0.16, 0.18, (-2.52, DEPTH - 0.23, z + 0.8), "fabric", r2=0.08)
cyl("Lamp stem", C3, 0.02, 0.22, (-2.52, DEPTH - 0.23, z + 0.58), "metal")
box("Side table right", C3, (0.45, 0.4, 0.5), (2.1, DEPTH - 0.22, z), "wood")
cyl("Lantern", C3, 0.08, 0.22, (1.55, DEPTH - 0.08, z + 1.25), "fire")
shelf_unit("Attic bookshelf", C3, 2.9, DEPTH - 0.18, z, 0.7, 0.35, 1.4, (0.0, 0.45, 0.85, 1.37))
armchair("Armchair attic", C3, 3.1, 3.9, z, math.radians(-20), color="wood")
box("Attic armchair throw", C3, (0.5, 0.5, 0.06), (3.0, 3.75, z + 0.42), "book")
box("Low cabinet", C3, (0.5, 0.45, 0.75), (4.2, 4.4, z), "wood")
plant("Attic plant big", C3, -3.55, 3.85, z, h=1.1, r=0.2, crown=0.36)
plant("Attic plant L", C3, -4.3, 1.0, z, h=0.7)
plant("Attic plant R", C3, 4.3, 1.0, z, h=0.7)
plant("Bookshelf top plant", C3, 2.9, DEPTH - 0.18, z + 1.4, h=0.4, r=0.09, crown=0.16)
box("Attic rug", C3, (4.0, 2.2, 0.01), (-0.5, 3.0, z), "fabric")

# reference people for scale on the other floors
person("Owner standing F1", "00_Reference", 1.0, 1.2, FLOOR[1])
person("Owner standing F3", "00_Reference", 1.2, 2.4, FLOOR[3])

# ------------------------------------------------------------------ exterior near
X = "06_Exterior"
for name, xx, yy, s in (("Pot step L", -1.45, -0.35, 1.0), ("Pot step R", 1.35, -0.35, 1.0), ("Pot big L", -4.4, -0.45, 1.25)):
    plant(name, X, xx, yy, 0, h=0.6 * s, r=0.22 * s, crown=0.3 * s)
for i in range(7):
    cyl(f"Path stone {i}", X, 0.32 + rng.uniform(-0.05, 0.08), 0.04,
        (rng.uniform(-0.25, 0.25) + 0.1 * i, -1.3 - 0.75 * i, 0), "stone", verts=9)
for i in range(4):
    for j in range(4 - i):
        cyl(f"Log {i}{j}", X, 0.11, 0.55, (4.4 + j * 0.23 + i * 0.11, -0.45, 0.11 + i * 0.2), "trunk",
            rx=math.pi / 2).location.z = 0.11 + i * 0.2
box("Woodpile base", X, (1.0, 0.6, 0.02), (4.75, -0.45, 0), "trunk")
cyl("Barrel", X, 0.36, 0.85, (5.65, -0.35, 0), "trunk")
ball("Barrel plant", X, 0.38, (5.65, -0.35, 1.05), "plant")
box("Leaning tool", X, (0.04, 0.04, 1.3), (4.05, -0.2, 0), "trunk", ry=math.radians(-12))
for i in range(14):
    sx = rng.choice((-1, 1))
    ball(f"Bush {i}", X, rng.uniform(0.35, 0.7), (sx * rng.uniform(2.2, 9.0), rng.uniform(-1.4, 1.0), 0.2), "plant",
         (1.3, 1.0, 0.8))

# ------------------------------------------------------------------ environment
E = "07_Environment"
# Overview camera: above the attic floor so every floor is seen slightly from above, as in the
# target image; distance and lens chosen so the front plane maps to the image at 0.0131 m/px.
CAM_D, CAM_Z, PX = 24.0, 6.0, 0.0131
CAM_LENS = 36 * CAM_D / (1672 * PX)
HORIZON = 500 - (CAM_Z - 4.75) / PX      # = 404.6, image row of the camera's horizon
CAM_SHIFT = (HORIZON - 941 / 2) / 1672

def from_image(px, base_py):
    """Ground point under image pixel (px, base_py) -> world (x, y) and metres per pixel there."""
    ycam = CAM_Z * CAM_D / ((base_py - HORIZON) * PX)
    k = PX * ycam / CAM_D
    return (px - 836) * k, ycam - CAM_D, k

def from_image_at(px, py, y):
    """Image pixel seen at world depth y -> world (x, z) and metres per pixel there."""
    k = PX * (y + CAM_D) / CAM_D
    return (px - 836) * k, CAM_Z + (HORIZON - py) * k, k

box("Ground", E, (4000, 4000, 0.1), (0, 1500, -0.1), "grass")
_, lake_near, _ = from_image(836, 695)
_, lake_far, _ = from_image(836, 590)
# 10-20: the user likes the water behind the house and wants more of it. The lake is egg-shaped:
# the near half keeps its original radius (so the near pines, boulders and fences stay where the
# target has them) and only the far half reaches LAKE_EXTRA metres further back; the forest beyond
# starts FOREST_GAP past the new far shore (tree tops keep their image rows). Width 44 m (was 30).
LAKE_EXTRA, FOREST_GAP = 55.0, 4.0
# lake: an irregular oval behind the house, wide enough to show through the gaps left and right
LAKE_C = (0.0, (lake_near + lake_far) / 2 + 1)
LAKE_A, LAKE_B = 44.0, (lake_far - lake_near) / 2 + 2
LAKE_B_FAR = LAKE_B + LAKE_EXTRA
lake_far += LAKE_EXTRA
lake_pts = []
for i in range(48):
    t = 2 * math.pi * i / 48
    w = 1 + 0.06 * math.sin(3 * t + 0.7) + 0.04 * math.sin(7 * t)
    b = LAKE_B_FAR if math.sin(t) > 0 else LAKE_B
    lake_pts.append((LAKE_C[0] + LAKE_A * w * math.cos(t), LAKE_C[1] + b * w * math.sin(t), 0.01))
lm = bpy.data.meshes.new("Lake")
lm.from_pydata(lake_pts, [], [list(range(48))])
lake = bpy.data.objects.new("Lake", lm)
sc.collection.objects.link(lake)
finish(lake, E, "water")
lake["c_y"], lake["b_near"], lake["b_far"] = LAKE_C[1], LAKE_B, LAKE_B_FAR   # read by build_environment
shore = [(x * 1.06, LAKE_C[1] + (y - LAKE_C[1]) * 1.12, 0.005) for x, y, _ in lake_pts]
sm = bpy.data.meshes.new("Lake shore")
sm.from_pydata(shore, [], [list(range(48))])
so = bpy.data.objects.new("Lake shore", sm)
sc.collection.objects.link(so)
finish(so, E, "stone")

def lake_dist(x, y):
    """< 1 inside the lake oval (scaled by the wobble-free ellipse)."""
    b = LAKE_B_FAR if y > LAKE_C[1] else LAKE_B
    return math.hypot((x - LAKE_C[0]) / (LAKE_A * 1.1), (y - LAKE_C[1]) / (b * 1.1))

def pine(name, x, y, h, r=None):
    r = r or h * 0.2
    cyl(name + " trunk", E, r * 0.12, h * 0.25, (x, y, 0), "trunk", verts=8)
    for k in range(3):
        cyl(f"{name} tier {k}", E, r * (1.0 - 0.25 * k), h * 0.45, (x, y, h * (0.18 + 0.22 * k)), "pine",
            r2=0, verts=10)

# near pines, one per tree in the target image: (trunk px, top py, base py)
for name, (px, top, base) in {"Pine L1": (30, 50, 600), "Pine L2": (105, 230, 650), "Pine L3": (200, 280, 700),
                              "Pine L4": (340, 430, 750), "Pine R1": (1315, 420, 725),
                              "Pine R2": (1545, 300, 750), "Pine R3": (1640, 240, 725)}.items():
    x, y, k = from_image(px, base)
    if lake_dist(x, y) < 1.15:
        # the painting leaves the trunk base ambiguous; keep the tree on the near shore and keep
        # its top on the same image row
        y = LAKE_C[1] - LAKE_B * 1.1 * 1.15 * math.sqrt(max(0.0, 1 - (x / (LAKE_A * 1.1 * 1.15)) ** 2)) - 1.0
        x, ztop, k = from_image_at(px, top, y)
        pine(name, x, y, ztop)
    else:
        pine(name, x, y, (base - top) * k)
# forest between the lake and the mountains
# forest beyond the lake: tree tops between image rows 290 and 370
for i in range(160):
    y = rng.uniform(lake_far + FOREST_GAP, lake_far + FOREST_GAP + 45)
    x, ztop, _ = from_image_at(rng.uniform(-80, 1750), rng.uniform(290, 370), y)
    if lake_dist(x, y) < 1.15:
        continue
    pine(f"Pine far {i}", x, y, ztop)
# forested ridges below the snow line: (centre px, top row, half-width px) at depth 300
for i, (px, top, hw) in enumerate(((250, 255, 420), (830, 300, 420), (1420, 290, 380))):
    x, ztop, k = from_image_at(px, top, 300)
    ball(f"Forest hill {i}", E, 1, (x, 300, 0), "hill", (hw * k, 60, ztop))
# boulders: (centre px, base py, width px, height px); the last three sit below the frame edge
for i, (px, base, wpx, hpx) in enumerate(((60, 800, 120, 110), (150, 800, 105, 120), (238, 780, 85, 55),
                                          (362, 810, 125, 50), (1497, 825, 105, 50), (1606, 825, 132, 95),
                                          (162, 960, 175, 60), (440, 960, 60, 40), (1512, 960, 175, 60))):
    x, y, k = from_image(px, base)
    ball(f"Boulder {i}", E, 1, (x, y, 0), "rock", (wpx * k / 2, wpx * k / 2.4, hpx * k))
# rock islands seen across the lake
for i, (px, base, wpx, hpx) in enumerate(((242, 595, 115, 50), (1410, 595, 120, 40), (1455, 500.5, 90, 40))):
    x, y, k = from_image(px, max(base, 590))
    ball(f"Lake rock hill {i}", E, 1, (x, y, 0), "rock", (wpx * k / 2, wpx * k / 3, hpx * k))
# fences: (px start, px end, base py)
for side, (p0, p1, base) in (("L", (0, 310, 825)), ("R", (1450, 1672, 850))):
    x0, y, k = from_image(p0, base)
    x1, _, _ = from_image(p1, base)
    box(f"Fence rail top {side}", E, (x1 - x0, 0.06, 0.08), ((x0 + x1) / 2, y, 0.7), "trunk")
    box(f"Fence rail low {side}", E, (x1 - x0, 0.06, 0.08), ((x0 + x1) / 2, y, 0.35), "trunk")
    for j in range(int((x1 - x0) / 1.4) + 1):
        box(f"Fence post {side}{j}", E, (0.12, 0.12, 0.95), (x0 + j * 1.4, y, 0), "trunk")
# snow peaks at depth 1200: (apex px, apex row, base half-width px)
for name, (px, py, hw) in {"Peak main": (455, 55, 380), "Peak left": (100, 200, 260),
                           "Peak mid": (800, 160, 220), "Peak centre-right": (1000, 145, 230),
                           "Peak right": (1200, 140, 250), "Peak far right": (1450, 150, 260),
                           "Peak edge right": (1650, 240, 220)}.items():
    x, z, k = from_image_at(px, py, 1200)
    cyl(name, E, hw * k, z, (x, 1200, 0), "rock", r2=0, verts=7, rz=rng.uniform(0, 1))
    cyl(name + " snow", E, hw * k * 0.38, z * 0.38, (x, 1200 - 1, z * 0.62), "snow", r2=0, verts=7)

# ------------------------------------------------------------------ cameras, render setup
K = "08_Cameras"
def camera(name, loc, rot_deg, lens, shift_y=0.0):
    cd = bpy.data.cameras.new(name)
    cd.lens, cd.sensor_fit, cd.sensor_width = lens, 'HORIZONTAL', 36
    cd.shift_y, cd.clip_start, cd.clip_end = shift_y, 0.1, 5000
    o = bpy.data.objects.new(name, cd)
    col(K).objects.link(o)
    o.location = loc
    o.rotation_euler = [math.radians(a) for a in rot_deg]
    return o

ov = camera("Cam_Overview", (0, -CAM_D, CAM_Z), (90, 0, 0), CAM_LENS, shift_y=CAM_SHIFT)
_r = CAM_D + DEPTH / 2
camera("Cam_Side_20deg", (_r * math.sin(math.radians(20)), DEPTH / 2 - _r * math.cos(math.radians(20)), CAM_Z),
       (90, 0, 20), CAM_LENS, shift_y=CAM_SHIFT)
for f in (1, 2, 3):
    camera(f"Cam_Room_F{f}", (0, -2.8, FLOOR[f] + 1.25), (84, 0, 0), 22)
camera("Cam_Back_Check", (-7, 22, 7), (80, 0, 200), 30)   # structure check only, not a game view
sc.camera = ov

sc.render.engine = 'BLENDER_WORKBENCH'
sc.render.resolution_x, sc.render.resolution_y = 1672, 941
sc.display.shading.light = 'STUDIO'
sc.display.shading.color_type = 'OBJECT'
sc.display.shading.show_cavity = True
sc.display.shading.show_shadows = True
sc.display.shading.show_object_outline = True
sc.view_settings.view_transform = 'Standard'
if sc.world is None:
    sc.world = bpy.data.worlds.new("World")
sc.world.color = (0.55, 0.75, 0.95)
col("90_Cutters").hide_render = True

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("WHITEBOX_SAVED", OUT, len(bpy.data.objects), "objects")
