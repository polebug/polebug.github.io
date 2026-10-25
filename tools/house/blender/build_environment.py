"""Stage 4: detailed surroundings.

Run after the interior scripts:
    Blender -b assets/blender/companion-house.blend --python build_environment.py
Reads the placement of every whitebox environment piece (collections 06_Exterior, 07_Environment,
which build_whitebox.py fits to the target image), then replaces them with detailed versions:

  31_Yard       Chinese moss garden: timber steps, slate path, moss beds, stones, ferns, water bowl, lights
  32_Landscape  near pines (each built branch by branch), boulders, split-rail fences, lake shore,
                grass and wild-flower scatter (geometry nodes), the lake itself is kept
  33_Far        pine variants instanced over the far forest, forested ridges, snow mountains
"""
import bpy, bmesh, math, random, os, sys
from mathutils import Vector, Matrix, noise

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from house_spec import *   # noqa: E402,F403
from meshkit import Mesh, Asset  # noqa: E402
import trees  # noqa: E402
import garden as G  # noqa: E402
G.TEX = os.path.join(os.path.dirname(bpy.data.filepath), "textures")

rng = random.Random(404)
sc = bpy.context.scene
OB = bpy.data.objects

# ------------------------------------------------------------------ read the whitebox layout
if "07_Environment" not in bpy.data.collections:
    raise SystemExit("build_environment.py needs the whitebox environment: run build_whitebox.py and the "
                     "following stages first (it reads the placements fitted to the target image).")
def dims(n):
    o = OB[n]
    return Vector(o.location), Vector(o.dimensions)

near_pines = []
far_pines = []
for o in list(bpy.data.collections["07_Environment"].objects):
    if o.name.endswith(" trunk") and o.name.startswith("Pine "):
        loc, d = dims(o.name)
        (far_pines if " far " in o.name else near_pines).append((o.name[:-6], loc.x, loc.y, d.z * 4))
boulders = [dims(o.name) for o in bpy.data.collections["07_Environment"].objects if o.name.startswith("Boulder ")]
boulders = [b for b in boulders if b[0].y >= 0]      # 10-21 (user): no boulders on the front lawn
rock_hills = [dims(o.name) for o in bpy.data.collections["07_Environment"].objects if o.name.startswith("Lake rock hill ")]
forest_hills = [dims(o.name) for o in bpy.data.collections["07_Environment"].objects if o.name.startswith("Forest hill ")]
peaks = [(OB[n].location.x, OB[n].location.y, OB[n].dimensions.z, OB[n].dimensions.x / 2)
         for n in [o.name for o in bpy.data.collections["07_Environment"].objects]
         if n.startswith("Peak ") and not n.endswith(" snow")]
fences = {}
for side in ("L", "R"):
    loc, d = dims(f"Fence rail top {side}")
    posts = sorted(OB[n].location.x for n in [o.name for o in bpy.data.collections["07_Environment"].objects]
                   if n.startswith(f"Fence post {side}"))
    fences[side] = (loc.x - d.x / 2, loc.x + d.x / 2, loc.y, posts)
bushes = [dims(o.name) for o in bpy.data.collections["06_Exterior"].objects if o.name.startswith("Bush ")]
path_stones = [dims(o.name) for o in bpy.data.collections["06_Exterior"].objects if o.name.startswith("Path stone ")]
pots = {n: dims(f"{n} pot") for n in ("Pot step L", "Pot step R", "Pot big L")}
barrel_loc, barrel_dim = dims("Barrel")
lake = OB["Lake"]
lake_pts = [lake.matrix_world @ v.co for v in lake.data.vertices]
lake_c = Vector((0.0, lake["c_y"], 0.0))            # egg-shaped lake: near and far half radii differ
LAKE_BN, LAKE_BF = lake["b_near"], lake["b_far"]

# keep the lake and its shore, remove the rest of the whitebox environment
for cn in ("06_Exterior", "07_Environment", "31_Yard", "32_Landscape", "33_Far", "39_Scatter_Sources"):
    c = bpy.data.collections.get(cn)
    if not c:
        continue
    for o in list(c.all_objects):
        if o.name in ("Lake", "Lake shore"):
            continue
        bpy.data.objects.remove(o, do_unlink=True)
for m in list(bpy.data.meshes):
    if m.users == 0:
        bpy.data.meshes.remove(m)
for ng in list(bpy.data.node_groups):
    if ng.name.startswith("Scatter ") and ng.users == 0:
        bpy.data.node_groups.remove(ng)
COLS = {}
for cn in ("31_Yard", "32_Landscape", "33_Far", "39_Scatter_Sources"):
    c = bpy.data.collections.get(cn) or bpy.data.collections.new(cn)
    if c.name not in sc.collection.children:
        sc.collection.children.link(c)
    COLS[cn] = c
for o in (lake, OB["Lake shore"]):
    for uc in list(o.users_collection):
        uc.objects.unlink(o)
    COLS["32_Landscape"].objects.link(o)
for cn in ("06_Exterior", "07_Environment"):
    c = bpy.data.collections.get(cn)
    if c:
        bpy.data.collections.remove(c)
COLS["39_Scatter_Sources"].hide_render = True
COLS["39_Scatter_Sources"].hide_viewport = True

P = {
    "grass": (0.62, 0.76, 0.36), "grass_blade": (0.55, 0.72, 0.33), "ground": (0.47, 0.64, 0.31),
    "bark": (0.60, 0.36, 0.22), "needle_dk": (0.12, 0.31, 0.20), "needle": (0.22, 0.43, 0.24), "needle_lt": (0.74, 0.78, 0.34),
    "rock_a": (0.66, 0.64, 0.62), "rock_b": (0.72, 0.66, 0.60), "rock_c": (0.58, 0.60, 0.64),
    "fence": (0.52, 0.38, 0.26), "fence_end": (0.74, 0.62, 0.44), "terracotta": (0.80, 0.47, 0.33),
    "soil": (0.30, 0.22, 0.16), "leaf": (0.36, 0.58, 0.30), "leaf_dark": (0.26, 0.46, 0.26), "stem": (0.40, 0.52, 0.28),
    "flower_o": (0.97, 0.56, 0.18), "flower_w": (0.97, 0.96, 0.92), "flower_y": (0.98, 0.82, 0.26),
    "stave": (0.62, 0.42, 0.25), "hoop": (0.20, 0.20, 0.22), "log": (0.45, 0.30, 0.18), "log_end": (0.82, 0.68, 0.48),
    "flag": (0.74, 0.71, 0.66), "sand": (0.82, 0.76, 0.62), "reed": (0.55, 0.62, 0.36),
    "hill": (0.24, 0.40, 0.30), "hill_rock": (0.45, 0.45, 0.44), "forest": (0.22, 0.40, 0.29), "mtn_rock": (0.36, 0.40, 0.52), "mtn_rock_dk": (0.27, 0.30, 0.38),
    "mtn_snow": (1.0, 1.0, 1.0), "mtn_forest": (0.20, 0.36, 0.28), "wood": (0.66, 0.50, 0.32),
}
def A(name, loc, col="31_Yard", rz=0.0):
    return Asset(name, COLS[col], P, loc, rz)


# ================================================================== pines
SUN = Vector((-0.45, -0.62, 0.64)).normalized()     # light from the upper left, as painted in the target

# ---- realistic conifers (10-20): procedural spruce / larch from trees.py, see its docstring --------
BARK_DIR = os.path.join(os.path.dirname(bpy.data.filepath), "textures", "Bark014")
def bark_material():
    m = bpy.data.materials.get("Bark")
    if m:
        bpy.data.materials.remove(m)
    m = bpy.data.materials.new("Bark")
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    bs = N["Principled BSDF"]
    tc, mp = N.new("ShaderNodeTexCoord"), N.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (2.5, 2.5, 1.2)
    L.new(tc.outputs["Object"], mp.inputs[0])
    def img(kind, cs):
        im = N.new("ShaderNodeTexImage")
        im.image = bpy.data.images.load(os.path.join(BARK_DIR, f"Bark014_2K-JPG_{kind}.jpg"), check_existing=True)
        im.image.colorspace_settings.name = cs
        im.projection, im.projection_blend = 'BOX', 0.3
        L.new(mp.outputs[0], im.inputs[0])
        return im
    tint = N.new("ShaderNodeMix")                      # spruce bark: grey-brown with a red cast
    tint.data_type, tint.blend_type = 'RGBA', 'MULTIPLY'
    tint.inputs["Factor"].default_value = 1.0
    tint.inputs[7].default_value = (0.45, 0.30, 0.22, 1)
    L.new(img("Color", "sRGB").outputs[0], tint.inputs[6])
    L.new(tint.outputs[2], bs.inputs["Base Color"])
    L.new(img("Roughness", "Non-Color").outputs[0], bs.inputs["Roughness"])
    nm = N.new("ShaderNodeNormalMap")
    L.new(img("NormalGL", "Non-Color").outputs[0], nm.inputs["Color"])
    L.new(nm.outputs[0], bs.inputs["Normal"])
    return m
BARK = bark_material()

# near trees (hero detail): spruce, with one larch for the mix seen in the photos
# 10-20: the user found the pines beside the house too crowded and had them removed, then asked for
# a few back on each side as long as they stand clear of the house: only the outer ones at the
# picture edges stay (L1, L2 left; R2, R3 right); L3, L4 and R1 next to the walls are skipped.
NEAR_KEEP = ("Pine L1", "Pine L2", "Pine R2", "Pine R3")
near_pines = [p_ for p_ in near_pines if p_[0] in NEAR_KEEP]
for i, (name, x, y, h) in enumerate(near_pines):
    sp = "spruce"                                  # larch reads oddly up close; it stays in the forest mix
    o = trees.build_tree(f"{name} {sp}", COLS["32_Landscape"], sp, h, seed=100 + i, lod=0, bark_mat=BARK,
                         crown_base=0.05, radius=max(0.26, 2.4 / h))   # open-grown; short trees keep a full 2.4 m crown radius
    o.location = (x, y, 0)
    o.rotation_euler = (0, 0, rng.uniform(0, 6.28))

# forest-edge trees behind the lake (60-150 m): medium detail sources, linked copies scaled to height
SRC_H = 20.0
def sources(lod, kinds):
    out = []
    for k, sp in enumerate(kinds):
        o = trees.build_tree(f"Tree source L{lod} {k} {sp}", COLS["39_Scatter_Sources"], sp, SRC_H,
                             seed=500 + 10 * lod + k, lod=lod, bark_mat=BARK)
        out.append(o)
    return out
MID = sources(1, ("spruce", "spruce", "spruce", "larch"))
for i, (name, x, y, h) in enumerate(far_pines):
    src = MID[i % len(MID)]
    o = bpy.data.objects.new(f"Forest edge tree {i:03d}", src.data)
    COLS["33_Far"].objects.link(o)
    if src.modifiers.get("Twigs"):
        o.modifiers.new("Twigs", 'NODES').node_group = src.modifiers["Twigs"].node_group
    s_ = h / SRC_H * rng.uniform(0.9, 1.15)
    o.location, o.scale, o.rotation_euler = (x, y, 0), (s_, s_, s_), (0, 0, rng.uniform(0, 6.28))
FAR = sources(2, ("spruce", "spruce", "larch"))


# ================================================================== rocks
def rock_mesh(name, coll, loc, size, color, seed, sub=3, flat=0.35):
    """Displaced icosphere, flattened where it meets the ground (only the part above z = 0 stays)."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
    sx, sy, sz = size
    off = Vector((seed * 1.7, seed * 0.3, seed * 2.1))
    for v in bm.verts:
        p = v.co.copy()
        n1 = noise.noise(p * 1.3 + off)
        n2 = noise.noise(p * 3.1 + off * 2)
        k = 1 + 0.22 * n1 + 0.07 * n2
        q = Vector((p.x * sx * k, p.y * sy * k, p.z * sz * k))
        if q.z < -sz * flat:
            q.z = -sz * flat
        v.co = q
    for v in bm.verts:
        v.co.z += sz * flat
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    o.location = loc
    o.color = (*P[color], 1)
    return o

GM = dict(
    granite=G.textured_mat("G granite", "Rock063", 0.55, (0.9, 0.88, 0.85)),
    leaf_ger=G.leaf_mat("G geranium leaf", (0.08, 0.2, 0.04)),
    petal=G.plain_mat("G geranium petal", (0.7, 0.03, 0.03), 0.5, 0.2),
    stem=G.leaf_mat("G stem", (0.12, 0.2, 0.05), 0.1),
    lav_leaf=G.leaf_mat("G lavender leaf", (0.25, 0.3, 0.2), 0.15, 0.6),
    lav_flower=G.plain_mat("G lavender flower", (0.22, 0.12, 0.45), 0.6),
    box=G.leaf_mat("G box leaf", (0.04, 0.13, 0.03), 0.25, 0.35),
    box_core=G.leaf_mat("G box core", (0.015, 0.05, 0.012), 0.1, 0.6),
    twig=G.plain_mat("G twig", (0.08, 0.05, 0.03), 0.8),
    grass=G.leaf_mat("G grass", (0.25, 0.28, 0.08), 0.35, 0.5),
    fern=G.leaf_mat("G fern", (0.08, 0.22, 0.04), 0.35),
    soil=G.plain_mat("G soil", (0.05, 0.035, 0.025), 0.95),
    mulch=G.textured_mat("G mulch", "Ground037", 1.2, (0.35, 0.27, 0.2)),
    terracotta=G.terracotta_mat(),
)
# boulders: weathered granite sunk into the turf, with gravel and a few plants at their feet
for i, (loc, d) in enumerate(boulders):
    G.rock(f"G boulder {i}", COLS["32_Landscape"], (loc.x, loc.y, 0), (d.x / 2, d.y / 2, d.z / 2 * 0.8),
           seed=i + 1, sink=0.3, rz=rng.uniform(0, 6.3), mat=GM["granite"])
    G.pebbles(f"G boulder gravel {i}", COLS["32_Landscape"], (loc.x, loc.y), d.x * 0.7, 40, 100 + i, GM["granite"])
for i, (loc, d) in enumerate(rock_hills):
    G.rock(f"G lake rock {i}", COLS["32_Landscape"], (loc.x, loc.y, 0), (d.x / 2, d.y / 2, d.z / 2),
           seed=40 + i, sink=0.25, mat=GM["granite"])


# ================================================================== fences
for side, (x0, x1, y, posts) in fences.items():
    a = A(f"Fence {side}", (0, y, 0), "32_Landscape")
    f, e = a.m("fence", bevel=0.01, smooth=True), a.m("fence_end")
    for k, px in enumerate(posts):
        h = 0.95 + rng.uniform(-0.04, 0.04)
        f.rod((px, 0, 0), (px + rng.uniform(-0.01, 0.01), rng.uniform(-0.01, 0.01), h - 0.04), 0.06, seg=9, r2=0.055)
        f.lathe([(0.055, h - 0.04), (0.03, h), (0, h + 0.012)], (px, 0, 0), seg=9)         # weathered post top
    for z in (0.35, 0.72):
        xs = [x0 - 0.1] + posts[1:-1] + [x1 + 0.1] if len(posts) > 2 else [x0 - 0.1, x1 + 0.1]
        for a0, a1 in zip(xs, xs[1:]):
            r = rng.uniform(0.036, 0.046)
            p0 = Vector((a0 - 0.05, rng.uniform(-0.01, 0.01), z + rng.uniform(-0.02, 0.02)))
            p1 = Vector((a1 + 0.05, rng.uniform(-0.01, 0.01), z + rng.uniform(-0.02, 0.02)))
            mid = (p0 + p1) / 2 + Vector((0, 0, -0.015))                                  # slight sag
            f.rod(p0, mid, r, seg=8)
            f.rod(mid, p1, r, seg=8)
        e.rod((x0 - 0.1, 0, 0.35), (x0 - 0.104, 0, 0.35), 0.042, seg=8)
        e.rod((x1 + 0.1, 0, 0.72), (x1 + 0.104, 0, 0.72), 0.042, seg=8)
    a.build()


# ================================================================== lake: shoreline, shallows, stones
# After the user's reference photo (10-19): irregular shoreline with grass running to the water, a
# shallow, lighter margin over a stony bed, half-sunk stones and patches of gravel bar; no even ring
# of sand. The water is a ring mesh whose attribute "shore" goes 0 at the edge -> 1 in the deep, and
# the lake material reads it. Water sits 3 cm below the ground; the bed slopes down under it.
sa = Vector((max(p.x for p in lake_pts) - lake_c.x, LAKE_BN, 0))
def sa_y(dy):
    return LAKE_BF if dy > 0 else LAKE_BN
for n_ in ("Lake", "Lake shore"):
    if n_ in OB:
        bpy.data.objects.remove(OB[n_], do_unlink=True)
SEG, RINGS = 160, 14
WATER_Z = 0.015                                     # just above the ground plane, which is not cut
def shore_r(t):
    """Shoreline radius factor (on the old ellipse) at angle t: two scales of wobble, kept 0.93..1.06
    so the grass and tree masks that use the ellipse still fit."""
    return 1.0 + 0.035 * math.sin(3 * t + 0.4) + 0.02 * math.sin(7 * t + 1.3) + 0.012 * noise.noise(Vector((math.cos(t) * 3, math.sin(t) * 3, 0.7)))
def lake_xy(t, f):
    return (lake_c.x + sa.x * shore_r(t) * f * math.cos(t), lake_c.y + sa_y(math.sin(t)) * shore_r(t) * f * math.sin(t))
wv, wf, wshore = [], [], []
for k in range(RINGS + 1):
    f = 1.0 - (k / RINGS) ** 1.6                    # rings crowd toward the edge where colour changes fast
    for t_i in range(SEG):
        t = 2 * math.pi * t_i / SEG
        x, y = lake_xy(t, f)
        wv.append((x, y, WATER_Z))
        wshore.append(min(1.0, (1.0 - f) * 9.0))    # 0 at the shoreline, 1 from ~11 % inward
for k in range(RINGS):
    for t_i in range(SEG):
        a0, a1 = k * SEG + t_i, k * SEG + (t_i + 1) % SEG
        wf.append([a0, a1, a1 + SEG, a0 + SEG])
wme = bpy.data.meshes.new("Lake")
wme.from_pydata(wv, [], wf)
at = wme.attributes.new("shore", 'FLOAT', 'POINT')
at.data.foreach_set("value", wshore)
water = bpy.data.objects.new("Lake", wme)
COLS["32_Landscape"].objects.link(water)
water.color = (0.30, 0.55, 0.85, 1)
# bank: a narrow strip that dips from ground level to below the water, so the edge has a real slope
bv, bf = [], []
for t_i in range(SEG):
    t = 2 * math.pi * t_i / SEG
    for f, z in ((1.03, 0.004), (1.0, WATER_Z + 0.003), (0.97, WATER_Z - 0.01)):
        x, y = lake_xy(t, f)
        bv.append((x, y, z))
for t_i in range(SEG):
    a, b = t_i * 3, ((t_i + 1) % SEG) * 3
    bf += [[a, b, b + 1, a + 1], [a + 1, b + 1, b + 2, a + 2]]
bme = bpy.data.meshes.new("Lake bank")
bme.from_pydata(bv, [], bf)
bank = bpy.data.objects.new("Lake bank", bme)
COLS["32_Landscape"].objects.link(bank)
bank.color = (0.55, 0.52, 0.42, 1)                  # wet earth and gravel

shore = A("Lake shore stones and reeds", (0, 0, 0), "32_Landscape")
def stone(p, s, flat=0.4):
    shore.m(rng.choice(["rock_a", "rock_c", "rock_b"]), smooth=True).ellipsoid(
        p, (s * rng.uniform(0.9, 1.4), s, s * flat), seg=9, rings=6, rot=Matrix.Rotation(rng.uniform(0, 6.3), 3, 'Z'))
near_side = lambda t: math.sin(t) < 0.55             # far shore is hidden behind the forest
for k in range(260):                                  # stones along the waterline, mostly half sunk
    t = rng.uniform(0, 2 * math.pi)
    if not near_side(t):
        continue
    f = rng.uniform(0.94, 1.04)
    x, y = lake_xy(t, f)
    s = rng.choice((0.08, 0.12, 0.18, 0.25, 0.35, 0.55)) * rng.uniform(0.8, 1.2)
    stone((x, y, WATER_Z - 0.02 + s * rng.uniform(0.0, 0.25)), s)
for k in range(9):                                    # gravel bars: dense clusters of small stones
    t = rng.uniform(0, 2 * math.pi)
    if not near_side(t):
        continue
    cx, cy = lake_xy(t, 0.985)
    for j in range(70):
        x, y = cx + rng.gauss(0, 0.9), cy + rng.gauss(0, 0.35)
        stone((x, y, WATER_Z), rng.uniform(0.04, 0.1), flat=0.5)
for k in range(40):                                   # stones on the shallow bed, seen through the water
    t = rng.uniform(0, 2 * math.pi)
    x, y = lake_xy(t, rng.uniform(0.9, 0.97))
    stone((x, y, WATER_Z - 0.01), rng.uniform(0.15, 0.4), flat=0.12)   # just breaking the surface
for k in range(14):                                   # a few reed clumps, not a ring
    t = rng.uniform(math.pi * 1.1, math.pi * 1.9)
    x, y = lake_xy(t, 0.99)
    for j in range(9):
        q = Vector((x, y, 0)) + Vector((rng.uniform(-0.3, 0.3), rng.uniform(-0.2, 0.2), 0))
        top = q + Vector((rng.uniform(-0.15, 0.15), rng.uniform(-0.15, 0.15), rng.uniform(0.6, 1.1)))
        shore.m("reed").rod(q, top, 0.012, seg=4, r2=0.003)
shore.build()


# ================================================================== front garden (Chinese moss garden, 10-20)
# After the user's reference photos: timber steps; a path of long cleft slate slabs in two staggered
# columns with real moss in the joints; either side a mounded bed carpeted with scanned moss and
# planted with drifts of scanned ferns, low black path lights; a hollowed granite lily bowl against
# the plinth on the right. No landscape stones by the door (removed at the user's request).
# No pots and NO round clipped shrubs (box balls) anywhere - removed at the user's request, 10-20.
Y = "31_Yard"
CM = dict(
    slate=G.textured_mat("G slate", "Rock035", 1.0, (2.2, 2.2, 2.1)),   # 10-21 (user): real dark stone
    limestone=G.stone_mat("G limestone", (0.22, 0.22, 0.21), scale=4.0, rough=0.9, bump=0.8),
    granite_bowl=G.stone_mat("G bowl granite", (0.3, 0.28, 0.24), scale=3.0, speckle=0.5, rough=0.85),
    moss=G.moss_mat(),
    timber=G.wood_mat(),
    creeper=G.leaf_mat("G creeper", (0.1, 0.25, 0.04), 0.3),
    yellow=G.plain_mat("G yellow flower", (0.8, 0.6, 0.02), 0.5),
    heuchera=G.leaf_mat("G heuchera", (0.35, 0.5, 0.05), 0.35),
    ligularia=G.leaf_mat("G ligularia", (0.06, 0.18, 0.04), 0.25, 0.35),
    sedge=G.leaf_mat("G variegated sedge", (0.45, 0.5, 0.28), 0.3),
    shrub=G.leaf_mat("G shrub leaf", (0.12, 0.22, 0.05), 0.25),
    metal=G.plain_mat("G black metal", (0.02, 0.02, 0.02), 0.4),
    glow=bpy.data.materials.get("Lamp glow") or G.plain_mat("G glow", (1, 0.8, 0.5), 0.5),
    water=G.plain_mat("G basin water", (0.01, 0.02, 0.02), 0.03),
    pad=G.leaf_mat("G lily pad", (0.15, 0.32, 0.05), 0.2, 0.3),
)
# timber steps replace the stone block steps of the architecture stage
for n_ in ("Front steps (solid blocks)",):
    if n_ in OB:
        bpy.data.objects.remove(OB[n_], do_unlink=True)
G.wooden_steps("G timber steps", COLS[Y], -1.0, 1.0, [(-0.99, -0.67, 0.15), (-0.67, -0.35, 0.30), (-0.35, -0.03, 0.45)],
               CM["timber"])
PATH = (-0.75, 0.75, -5.6, -1.0)
G.slate_path("G slate path", COLS[Y], *PATH, 31, CM["slate"])
bpy.data.objects["G slate path"].location.z -= 0.03      # 10-21 (user): set into the lawn, ~1 cm proud
# ---- real plants (10-20): CC0 scanned ferns and moss from Poly Haven replace the hand-built plants;
# the user rejected the procedural ferns/shrubs, the clipped box balls and the stones by the door.
G.MODELS = os.path.join(os.path.dirname(bpy.data.filepath), "models")
SRC = COLS["39_Scatter_Sources"]
FERNS = list(G.load_model("fern_02", ["fern_02_a", "fern_02_b", "fern_02_c", "fern_02_d"], SRC).values())
FERNS_BIG = [f for f in FERNS if f.name.startswith(("fern_02_b", "fern_02_c"))]
FERNS_SMALL = [f for f in FERNS if f.name.startswith(("fern_02_a", "fern_02_d"))]
MOSS_STRANDS = list(G.load_model("moss_01", [f"moss_01_{c}_LOD0" for c in "acdefg"], SRC).values())   # leafy cushion strands only
MOSS = G.moss_clump(MOSS_STRANDS, SRC, 7, n=60, r=0.03)

MOSS_JOBS = []                                   # run after scatter() is defined (lawn section)
def moss_cover(name, base_obj, density):
    MOSS_JOBS.append((name, base_obj, density))

# 10-21 (user): no separate joint strip; the lawn itself grows between the slabs (see mask_under below)

# ---- natural lawn right up to the house (user, 10-20: one lawn, one colour - no moss beds), with
# loose evergreen shrubs along the plinth, a garden maple (鸡爪槭) at each front corner as in the
# user's reference, real ferns in front of the shrubs, low path lights.
BEDS = []
RING_STONES = list(G.load_model("rock_07", ["rock_07_LOD1"], SRC).values()) + \
              list(G.load_model("stone_01", ["stone_01_LOD1"], SRC).values())
PERIWINKLE = list(G.load_model("periwinkle_plant", [f"periwinkle_plant_0{i}_LOD1" for i in range(1, 7)], SRC).values())
for sgn, h_, seed in ((-1, 4.4, 3), (1, 3.7, 8)):
    trees.build_maple(f"G maple {'L' if sgn < 0 else 'R'}", COLS[Y], h_, 2.6, seed, BARK,
                      (0.18 * -sgn, -0.05)).location = (sgn * 6.0, -1.5, 0)
    # stone surround at the foot of each maple (user, 10-20): scanned field stones (Poly Haven
    # rock_07, stone_01) set edge to edge round a mulch mound planted with scanned periwinkle
    cx_, cy_, R_ = sgn * 6.0, -1.5, 0.62
    mound = G.tree_ring(f"G tree ring {'L' if sgn < 0 else 'R'}", COLS[Y], (cx_, cy_), R_ - 0.02, 140 + seed,
                        (GM["soil"], GM["soil"]), n=0)                   # dark soil mound only
    # pick stones until their lengths fill the circumference (8 % overlap so they sit edge to edge)
    picks, total = [], 0.0
    while total < 2 * math.pi * R_ * 1.08:
        src = rng.choice(RING_STONES)
        long_ = max(src.dimensions.x, src.dimensions.y)
        sc_ = rng.uniform(0.26, 0.32) / long_
        picks.append((src, sc_, long_ * sc_))
        total += long_ * sc_
    a_ = rng.uniform(0, 6.3)
    for k_, (src, sc_, width) in enumerate(picks):
        a_ += width / 2 / R_ * (2 * math.pi * R_ / total) * 1.0
        o = G.place(src, f"G ring stone {'L' if sgn < 0 else 'R'}{k_:02d}", COLS[Y],
                    (cx_ + R_ * math.cos(a_), cy_ + R_ * math.sin(a_), -0.02), sc_)
        along = 0.0 if src.dimensions.x >= src.dimensions.y else math.pi / 2    # long axis along the ring
        o.rotation_euler = (rng.uniform(-0.15, 0.15), rng.uniform(-0.15, 0.15),
                            a_ + math.pi / 2 - along + rng.choice((0.0, math.pi)))
        a_ += width / 2 / R_ * (2 * math.pi * R_ / total)
    for k in range(26):                              # periwinkle carpet filling the ring
        r__ = 0.1 + (R_ - 0.22) * math.sqrt(rng.random())
        a__ = rng.uniform(0, 6.3)
        G.place(rng.choice(PERIWINKLE), f"G periwinkle {'L' if sgn < 0 else 'R'}{k}", COLS[Y],
                (cx_ + r__ * math.cos(a__), cy_ + r__ * math.sin(a__), 0.02), rng.uniform(1.3, 1.8), rng.uniform(0, 6.3))
TREE_RINGS = [(-6.0, -1.5, 0.75), (6.0, -1.5, 0.75)]
for k, (x, y, sx_, sz_) in enumerate(((-4.3, -0.7, 1.1, 0.95), (-3.0, -0.75, 0.85, 0.75), (-5.5, -0.95, 0.8, 0.7),
                                      (1.95, -0.7, 0.8, 0.7), (5.35, -0.95, 0.85, 0.75), (6.6, -0.6, 0.9, 0.8))):
    trees.build_shrub(f"G shrub {k}", COLS[Y], (sx_, sx_ * 0.85, sz_), 900 + k, BARK).location = (x, y, 0)
for k, (x, y, sc_) in enumerate(((-3.7, -1.45, 0.9), (-2.4, -1.35, 0.8), (-1.45, -0.6, 0.75), (1.4, -0.6, 0.75),
                                 (2.6, -1.35, 0.85), (4.6, -1.5, 0.9))):
    src = rng.choice(FERNS_BIG if sc_ > 0.85 else FERNS_SMALL)
    G.place(src, f"G fern {k}", COLS[Y], (x, y, 0.0), sc_ * rng.uniform(0.9, 1.1), rng.uniform(0, 6.3))
for sgn in (-1, 1):
    s = "L" if sgn < 0 else "R"
    for k, (x, y) in enumerate(((sgn * 1.05, -2.7), (sgn * 1.05, -1.3))):
        G.garden_light(f"G light {s}{k}", COLS[Y], (x, y, 0.04), (CM["metal"], CM["glow"]))
# lily bowl on the right, against the plinth wall (user, 10-20)
# 10-21 (user): the lily bowl read as fake and is gone

def in_bed(x, y, pad=0.1):
    """No lawn under the beds, the path and the steps."""
    if any(math.hypot(x - tx, y - ty) < tr for tx, ty, tr in TREE_RINGS):
        return True
    return any(x0 - pad < x < x1 + pad and y0 - pad < y < y1 + 0.3 for x0, x1, y0, y1 in BEDS)

# woodpile: split logs on two sleepers against the plinth
wp = A("Woodpile", (4.75, -0.45, 0.0))
for x in (-0.38, 0.38):
    wp.m("log", bevel=0.01).box(x - 0.05, x + 0.05, -0.28, 0.27, 0, 0.08)
z = 0.08
for row, n in enumerate((8, 8, 7, 6)):
    # quarter-split logs lie on a flat face (arc above), so every piece rests on the row below
    width = 0.108
    x = -(n * width) / 2 + width / 2 + (0.0 if row % 2 == 0 else width / 2 * 0.5)
    for k in range(n):
        rr = rng.uniform(0.095, 0.103)
        rot = rng.choice([0.0, math.pi / 2])
        quarter = [(0.0, 0.0)] + [(rr * math.cos(rot + t), rr * math.sin(rot + t)) for t in [j * (math.pi / 2) / 6 for j in range(7)]]
        cx = x + k * width + (-rr / 2 if rot == 0.0 else rr / 2)
        cz = z
        L = rng.uniform(0.5, 0.56)
        wp.m("log", bevel=0.004).solid([(cx + px, -L / 2, cz + pz) for px, pz in quarter], [(cx + px, L / 2, cz + pz) for px, pz in quarter])
        wp.m("log_end").solid([(cx + px * 0.97, -L / 2 - 0.003, cz + pz * 0.97) for px, pz in quarter],
                              [(cx + px * 0.97, -L / 2, cz + pz * 0.97) for px, pz in quarter])
    z += 0.1
wp.build()

# rake leaning on the edge of the floor-1 boards
rk = A("Garden rake", (4.05, 0.0, 0.0))
foot, contact = Vector((0, -0.6, 0.0)), Vector((0, -0.04, FLOOR[1] + 0.005))
top = foot + (contact - foot).normalized() * 1.45
rk.m("wood", smooth=True).rod(foot + (contact - foot).normalized() * 0.04, top, 0.016, seg=10)
d = (contact - foot).normalized()
head = foot + d * 0.04
rk.m("hoop", bevel=0.003).box(head.x - 0.2, head.x + 0.2, head.y - 0.02, head.y + 0.02, head.z + 0.02, head.z + 0.05)
for k in range(11):
    x = -0.18 + k * 0.036
    rk.m("hoop").rod((x, head.y - 0.0, head.z + 0.025), (x, head.y - 0.05, head.z - 0.02 + 0.02), 0.004, seg=5)
rk.build()

# flagstone path
fp = A("Flagstone path", (0, 0, 0))
for i, (loc, d) in enumerate(path_stones):
    if loc.y > PATH[2] - 0.3:
        continue                                           # the slate path replaces the first stones
    r = d.x / 2
    n = 18                                           # natural slab: irregular outline from noise, not a polygon
    pts = []
    ph = rng.uniform(0, 10)
    for k in range(n):
        t = 2 * math.pi * k / n
        rad = r * (0.88 + 0.14 * noise.noise(Vector((math.cos(t) * 1.5 + ph, math.sin(t) * 1.5, ph))) + 0.05 * math.sin(3 * t + ph))
        pts.append((loc.x + rad * math.cos(t) * 1.1, loc.y + rad * math.sin(t) * 0.85))
    top = rng.uniform(0.012, 0.022)                  # nearly flush with the turf
    fp.m("flag", bevel=0.012, segments=2).solid([(x, y, -0.02) for x, y in pts], [(x, y, top) for x, y in pts])
fp.build()


# ================================================================== ground, grass, wild flowers
gr = bpy.data.objects.get("Ground")
if gr is None:
    me = bpy.data.meshes.new("Ground")
    me.from_pydata([(-2000, -500, 0), (2000, -500, 0), (2000, 3000, 0), (-2000, 3000, 0)], [], [[0, 1, 2, 3]])
    gr = bpy.data.objects.new("Ground", me)
    COLS["32_Landscape"].objects.link(gr)
gr.color = (*P["ground"], 1)

def density(x, y):
    """0 under the house, steps, path, rocks, woodpile, pots and lake; full on open grass."""
    if -HALF_W - 0.3 < x < HALF_W + 0.3 and -0.3 < y < DEPTH + 0.5:
        return 0.0
    if -1.1 < x < 1.1 and -1.05 < y < 0:
        return 0.0
    if in_bed(x, y, 0.05):
        return 0.0
    for loc, d in path_stones:
        if math.hypot(x - loc.x, y - loc.y) < d.x / 2 + 0.05:
            return 0.0
    for loc, d in boulders:
        if ((x - loc.x) / (d.x / 2)) ** 2 + ((y - loc.y) / (d.y / 2)) ** 2 < 1.0:
            return 0.0
    if 4.2 < x < 6.1 and -0.85 < y < -0.05:
        return 0.0
    ld = math.hypot((x - lake_c.x) / (sa.x * 1.08), (y - lake_c.y) / (sa_y(y - lake_c.y) * 1.08))
    if ld < 1.0:
        return 0.0
    f = 1.0 if y < 12 else max(0.6, 1 - (y - 12) / 40)
    return f * (0.55 + 0.45 * (noise.noise(Vector((x * 0.3, y * 0.3, 0))) * 0.5 + 0.5))

patch = bpy.data.meshes.new("Grass patch")
NXG, NYG = 241, 131                                        # lawn patch covers everything the cameras see near the house
xs = [-60 + 0.5 * i for i in range(NXG)]
ys = [-25 + 0.5 * j for j in range(NYG)]
patch.from_pydata([(x, y, 0.004) for y in ys for x in xs], [],
                  [[j * NXG + i, j * NXG + i + 1, (j + 1) * NXG + i + 1, (j + 1) * NXG + i] for j in range(NYG - 1) for i in range(NXG - 1)])
attr = patch.attributes.new("dens", 'FLOAT', 'POINT')
for k, v in enumerate(patch.vertices):
    attr.data[k].value = density(v.co.x, v.co.y)

def lawn_patch_source():
    """A 30 x 30 cm patch of short lawn: 40 fine blades, 2-5 cm tall, leaning every which way."""
    m = Mesh()
    for k in range(40):
        p = Vector((rng.uniform(-0.15, 0.15), rng.uniform(-0.15, 0.15), 0))
        t = rng.uniform(0, 2 * math.pi)
        h = rng.uniform(0.02, 0.05)
        d = Vector((math.cos(t), math.sin(t), 0))
        side = Vector((-d.y, d.x, 0)) * 0.0035
        tip = p + d * h * rng.uniform(0.2, 0.6) + Vector((0, 0, h))
        mid = p * 0.5 + tip * 0.5 + Vector((0, 0, h * 0.08))
        i0 = len(m.v)
        m.v += [tuple(p - side), tuple(p + side), tuple(mid - side * 0.6), tuple(mid + side * 0.6), tuple(tip)]
        m.f += [[i0, i0 + 1, i0 + 3, i0 + 2], [i0 + 2, i0 + 3, i0 + 4]]
    return m.build("Lawn patch", COLS["39_Scatter_Sources"], P["grass_blade"])

def flower_source(name, key):
    m = Mesh()
    m.rod((0, 0, 0), (0.005, 0, 0.14), 0.003, seg=4)
    for j in range(5):
        t = 2 * math.pi * j / 5
        m.ellipsoid((0.005 + 0.012 * math.cos(t), 0.012 * math.sin(t), 0.142), (0.012, 0.007, 0.002), seg=6, rings=3,
                    rot=Matrix.Rotation(t, 3, 'Z'))
    return m.build(name, COLS["39_Scatter_Sources"], P[key])

def scatter(name, source, coll, density_max, color, mesh, scale=(0.7, 1.3), seed=0, attr_name="dens"):
    ng = bpy.data.node_groups.new(f"Scatter {name}", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = ng.nodes
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    dist = N.new("GeometryNodeDistributePointsOnFaces")
    dist.distribute_method = 'POISSON'            # Poisson mode takes a max density and a factor field
    dist.inputs["Density Max"].default_value = density_max
    dist.inputs["Distance Min"].default_value = 0.0
    dist.inputs["Seed"].default_value = seed
    na = N.new("GeometryNodeInputNamedAttribute")
    na.data_type = 'FLOAT'
    na.inputs["Name"].default_value = attr_name
    inst = N.new("GeometryNodeInstanceOnPoints")
    oi = N.new("GeometryNodeObjectInfo")
    oi.inputs["Object"].default_value = source
    oi.inputs["As Instance"].default_value = True
    rot = N.new("FunctionNodeRandomValue")
    rot.data_type = 'FLOAT_VECTOR'
    rs = N.new("FunctionNodeRandomValue")
    rs.data_type = 'FLOAT'
    L = ng.links
    L.new(gi.outputs[0], dist.inputs["Mesh"])
    # density factor: route the named attribute into the (enabled) "Density Factor" socket
    L.new(na.outputs["Attribute"], dist.inputs["Density Factor"])
    L.new(dist.outputs["Points"], inst.inputs["Points"])
    L.new(oi.outputs["Geometry"], inst.inputs["Instance"])
    vin = [s for s in rot.inputs if s.enabled and s.type == 'VECTOR']
    vin[0].default_value, vin[1].default_value = (0, 0, 0), (0, 0, 6.283)
    L.new([s for s in rot.outputs if s.enabled][0], inst.inputs["Rotation"])
    fin = [s for s in rs.inputs if s.enabled and s.type == 'VALUE']
    fin[0].default_value, fin[1].default_value = scale
    L.new([s for s in rs.outputs if s.enabled][0], inst.inputs["Scale"])
    L.new(inst.outputs["Instances"], go.inputs[0])
    o = bpy.data.objects.new(name, mesh)
    coll.objects.link(o)
    o.color = (*P[color], 1)
    mod = o.modifiers.new("Scatter", 'NODES')
    mod.node_group = ng
    return o

for name_, base_, dens_ in MOSS_JOBS:              # real moss carpets queued by the front garden
    me_ = base_.data
    at_ = me_.attributes.get("dens") or me_.attributes.new("dens", 'FLOAT', 'POINT')
    at_.data.foreach_set("value", [1.0] * len(me_.vertices))
    scatter(name_, MOSS, COLS[Y], dens_, "grass", me_, scale=(0.55, 0.85), seed=len(name_)).location = base_.location
lawn = lawn_patch_source()
lawn_o = scatter("Lawn", lawn, COLS["32_Landscape"], 48.0, "grass_blade", patch, scale=(0.9, 1.3), seed=1)
G.mask_under(lawn_o.modifiers["Scatter"].node_group, bpy.data.objects["G slate path"])   # no blades through the slabs
# single lawn tone (user, 10-20): the second, lighter grass layer is gone
scatter("Wild flowers yellow", flower_source("Wild flower yellow", "flower_y"), COLS["32_Landscape"], 0.35, "flower_y", patch, seed=2)
scatter("Wild flowers white", flower_source("Wild flower white", "flower_w"), COLS["32_Landscape"], 0.3, "flower_w", patch, seed=3)


# ================================================================== far terrain: forested ridges and snow mountains
def heightfield(name, coll, x0, x1, y0, y1, step_x, step_y, hfun, classify):
    """Quad grid; each face goes to the mesh its classify(centre, normal) key names."""
    nx, ny = int((x1 - x0) / step_x) + 1, int((y1 - y0) / step_y) + 1
    H = [[hfun(x0 + i * step_x, y0 + j * step_y) for i in range(nx)] for j in range(ny)]
    meshes = {}
    for j in range(ny - 1):
        for i in range(nx - 1):
            q = [Vector((x0 + (i + a) * step_x, y0 + (j + b) * step_y, H[j + b][i + a])) for a, b in ((0, 0), (1, 0), (1, 1), (0, 1))]
            nrm = (q[1] - q[0]).cross(q[3] - q[0]).normalized()
            key = classify(sum(q, Vector()) / 4, nrm)
            m = meshes.setdefault(key, Mesh())
            i0 = len(m.v)
            m.v += [tuple(p) for p in q]
            m.f.append([i0, i0 + 1, i0 + 2, i0 + 3])
    out = {}
    for key, m in meshes.items():
        o = m.build(f"{name} {key}", coll, P[key])
        out[key] = o
    return out

def hill_h(x, y):
    h = 0.0
    lower = 12.0                                         # room for the trees standing on it
    for loc, d in forest_hills:
        rx, ry, hz = d.x / 2, d.y / 2, d.z / 2
        t = 1 - ((x - loc.x) / rx) ** 2 - ((y - loc.y) / ry) ** 2
        if t > 0:
            h = max(h, hz * math.sqrt(t))
    if h <= 0:
        return -1.0
    # erosion: gullies running down the fall line (ridged noise stretched across the slope) and a
    # little rock-step texture; forested slopes in IMG_6020 are cut by ravines, not smooth domes
    g = noise.ridged_multi_fractal(Vector((x / 55.0, y / 160.0, 3.0)), 1.0, 2.0, 3, 1.0, 2.0)
    return max(0.5, h * (1 + 0.1 * noise.noise(Vector((x / 40, y / 40, 1.0)))) - lower - h * 0.22 * max(0.0, g - 0.6))

def forest_density(me, z_full, z_none, seed):
    """Per-vertex tree density: full low down, thinning to nothing at the tree line, broken by
    noise into clumps and small meadows (as the slopes in IMG_6008)."""
    at = me.attributes.get("tdens") or me.attributes.new("tdens", 'FLOAT', 'POINT')
    al = me.attributes.get("ldens") or me.attributes.new("ldens", 'FLOAT', 'POINT')
    vals = [0.0] * len(me.vertices)
    lvals = [0.0] * len(me.vertices)
    for poly in me.polygons:
        zs = [me.vertices[i].co.z for i in poly.vertices]
        if max(zs) > z_none or min(zs) < 0.5 or poly.normal.z < 0.55:   # above tree line / cliff
            continue
        for i in poly.vertices:
            v = me.vertices[i]
            z = v.co.z
            alt = 1.0 if z <= z_full else max(0.0, 1 - (z - z_full) / max(1e-3, z_none - z_full))
            n = noise.noise(Vector((v.co.x / 35.0, v.co.y / 35.0, seed)))
            d = max(0.0, min(1.0, alt * (0.7 + 0.9 * n)))
            # larch grows in patches (bright yellow-green drifts across the slope in IMG_6020)
            lm = max(0.0, min(1.0, 0.5 + 1.6 * noise.noise(Vector((v.co.x / 60.0, v.co.y / 45.0, seed + 7)))))
            vals[i], lvals[i] = d * (1 - 0.75 * lm), d * lm
    at.data.foreach_set("value", vals)
    al.data.foreach_set("value", lvals)

def forest_scatter(name, base_obj, density, scale, seed):
    """Spruce sources on the spruce field, the larch source on the larch field; scale is relative to
    the 20 m source trees."""
    for k, src in enumerate(FAR):
        larch = src["species"] == "larch"
        scatter(f"{name} {k} {src['species']}", src, COLS["33_Far"], density / (1 if larch else 2), "needle",
                base_obj.data, scale=scale, seed=seed + k, attr_name="ldens" if larch else "tdens")

# ---- snow mountains traced from the target image ------------------------------------------------
# The painted range is one continuous wall of peaks across the whole picture. Its skyline is read
# column by column from the target image and turned into the crest of a 3D range at y = MTN_Y by
# casting the overview camera's ray through each skyline pixel. The slopes fall away in front of
# and behind the crest with gullies, and every face takes snow / rock / forest from the target
# pixel it covers in the overview, so the painted snow pattern lands on real geometry.
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
TARGET = os.path.join(os.path.dirname(bpy.data.filepath), "..", "concepts", "home-interior-refined-2026-10-19.png")
timg = bpy.data.images.load(os.path.abspath(TARGET), check_existing=True)
IW, IH = timg.size
IMG = np.array(timg.pixels[:], dtype=np.float32).reshape(IH, IW, 4)[::-1, :, :3]
r_, g_, b_ = IMG[..., 0], IMG[..., 1], IMG[..., 2]
SKY = (b_ > 0.55) & (b_ - r_ > 0.25) & (b_ - g_ > 0.08)
SNOW = (IMG.mean(-1) > 0.65) & (IMG.max(-1) - IMG.min(-1) < 0.16)
ROCK = (~SKY) & (b_ - g_ > 0.05) & (g_ - r_ < 0.08)
MTN = SNOW | ROCK
def box_blur(m, k=3):
    """Majority-style smoothing so painted brush specks don't turn into single-face speckles."""
    f = m.astype(np.float32)
    c = np.cumsum(np.cumsum(np.pad(f, ((k + 1, k), (k + 1, k))), 0), 1)
    return (c[2 * k + 1:, 2 * k + 1:] - c[:-2 * k - 1, 2 * k + 1:] - c[2 * k + 1:, :-2 * k - 1] + c[:-2 * k - 1, :-2 * k - 1]) / (2 * k + 1) ** 2
SNOW_S, ROCK_S = box_blur(SNOW), box_blur(ROCK)
cam = sc.camera
frame = [cam.matrix_world @ v for v in cam.data.view_frame(scene=sc)]       # tr, br, bl, tl
def pixel_ray(px, row):
    tr, br, bl, tl = frame
    p = tl + (tr - tl) * ((px + 0.5) / IW) + (bl - tl) * ((row + 0.5) / IH)
    return cam.matrix_world.translation, (p - cam.matrix_world.translation).normalized()

MTN_Y = 1250.0
sky_rows = np.full(IW, np.nan)
for x in range(IW):
    col = SKY[15:440, x]
    if col.all():
        continue
    row = 15 + int(np.argmin(col))
    if MTN[row:row + 3, x].mean() > 0.6:             # first thing under the sky is mountain, not tree/roof
        sky_rows[x] = row
known = np.where(~np.isnan(sky_rows))[0]
sky_rows = np.interp(np.arange(IW), known, sky_rows[known])
# 10-20: the near pines that hid both picture edges in the target are gone, so the columns outside the
# first/last traced ones are seen now: let the ridge fall away (0.45 px per px) instead of running flat
_xs = np.arange(IW)
sky_rows = np.where(_xs < known[0], sky_rows + (known[0] - _xs) * 0.45, sky_rows)
sky_rows = np.where(_xs > known[-1], sky_rows + (_xs - known[-1]) * 0.45, sky_rows)
print("MTN_SKY_TRACED_COLS", int(known[0]), int(known[-1]))
sky_rows = np.array([np.median(sky_rows[max(0, x - 3):x + 4]) for x in range(IW)])
# 10-20: light Gaussian (sigma 4 px) on top of the median: removes the pixel-scale sawtooth the user saw
# on the right-hand ridge while keeping every peak and saddle of the painted skyline
_k = np.exp(-0.5 * (np.arange(-12, 13) / 4.0) ** 2)
sky_rows = np.convolve(np.pad(sky_rows, 12, mode='edge'), _k / _k.sum(), mode='valid')
crest_x, crest_z = [], []
for x in range(0, IW, 2):
    o, d = pixel_ray(x, sky_rows[x])
    t = (MTN_Y - o.y) / d.y
    crest_x.append(o.x + d.x * t)
    crest_z.append(o.z + d.z * t)
CX, CZ = np.array(crest_x), np.array(crest_z)

def crest(x):
    # beyond the frame the range carries on as a mirror image of the traced skyline, lowering slowly,
    # so a camera turned to the side still sees peaks and saddles rather than a smooth ramp
    span = CX[-1] - CX[0]
    if x < CX[0]:
        d = CX[0] - x
        return float(np.interp(CX[0] + d % span, CX, CZ)) * max(0.55, 1 - d / 1400)
    if x > CX[-1]:
        d = x - CX[-1]
        return float(np.interp(CX[-1] - d % span, CX, CZ)) * max(0.55, 1 - d / 1400)
    return float(np.interp(x, CX, CZ))

# ---- mountain body: three layers, spurs running from upper-left to lower-right ----------------------
# Read from the target (docs/scene-review-log.md, 10-19): the range runs across the picture; every spur
# and gully on it falls from upper-left to lower-right, parallel, at about 35-40 degrees on screen; in
# front of the snow range stands a lower, darker rocky range; forested hills cover the foot of both.
# In world terms a spur leaves the crest toward the camera and to the right, so it projects down-right.
SPUR_D = Vector((0.6, -0.8, 0.0))                  # horizontal direction a spur runs away from its crest
SPUR_N = Vector((0.8, 0.6, 0.0))                   # across the spur
CREST_SLOPE = 1.6                                  # steep sides of the main crest
BACK_SLOPE = 0.85                                  # back faces (not seen from the overview)

def build_heights(crest_fn, ridge_y, gx, gy, spur_gap, along, across, seed):
    """Height grid = max(steep cones round the crest, ridged spurs) capped by the crest pushed down
    the faces, so the traced skyline stays exact and the faces are made of parallel spurs."""
    rs = random.Random(seed)
    # 10-20: cones every 1 m (was 6 m). At 6 m the union of slope-1.6 cones left a 4.8 m V-notch
    # between neighbours - a regular comb of teeth along the ridge, ~9 px apart in the overview.
    cx = np.arange(gx[0] - 400, gx[-1] + 400, 1.0, dtype=np.float32)
    cz = np.array([crest_fn(x) for x in cx], dtype=np.float32)
    sx, sz, sb, sl = [], [], [], []
    x = gx[0] - 400
    while x < gx[-1] + 400:
        z = crest_fn(x)
        if z > 5:
            sx.append(x)
            sz.append(z * rs.uniform(0.9, 1.0))
            sb.append(rs.uniform(-0.6, 0.6))           # gentle bend so no spur is a ruled straight line
            sl.append(z / along * rs.uniform(0.55, 0.85))  # spurs die out before the valley floor
        x += spur_gap * rs.uniform(0.7, 1.3)
    sx, sz, sb, sl = (np.array(v) for v in (sx, sz, sb, sl))
    top = np.array([crest_fn(x) for x in gx])[None, :]
    H = np.zeros((len(gy), len(gx)), dtype=np.float32)
    CH = 2                                             # small row chunks keep the 1 m cone array in memory
    for j0 in range(0, len(gy), CH):
        yy = gy[j0:j0 + CH][:, None, None].astype(np.float32)
        xx = gx[None, :, None]
        dy = yy - ridge_y
        front = dy < 0
        dist = np.sqrt((xx - cx[None, None, :]) ** 2 + dy ** 2)
        cone = (cz[None, None, :] - np.where(front, CREST_SLOPE, BACK_SLOPE) * dist).max(-1)
        px, py = xx - sx[None, None, :], np.broadcast_to(dy, (dy.shape[0], 1, 1))
        a = px * SPUR_D.x + py * SPUR_D.y
        c = px * SPUR_N.x + py * SPUR_N.y
        L = sl[None, None, :]
        c = c - sb[None, None, :] * a * a / np.maximum(L, 1.0)                 # bend along its length
        W = 14.0                                                                # rounded spur crest
        prof = across * (np.sqrt(c * c + W * W) - W)
        fade = np.clip(a / L, 0.0, 1.0) ** 2 * 0.35 * sz[None, None, :]        # sinks into the face at its foot
        rise = np.exp(-np.maximum(a, 0) / 25.0) * 6.0                          # merges into the crest at its head
        spur = np.where(a >= 0, sz[None, None, :] - along * a - prof - fade - rise, -1e9).max(-1)
        wall = top - np.where(front[..., 0], CREST_SLOPE * 0.5, BACK_SLOPE) * np.abs(dy[..., 0])
        H[j0:j0 + CH] = np.maximum(0.0, np.minimum(np.maximum(cone, spur), wall))
    return H

def grid_lookup(H, gx, gy, step, x, y, gully_amp, crest_fn):
    i, j = int(round((x - gx[0]) / step)), int(round((y - gy[0]) / step))
    h = float(H[min(max(j, 0), len(gy) - 1), min(max(i, 0), len(gx) - 1)])
    if h <= 0:
        return 0.0
    # gullies follow the spur direction as well
    u = (x * SPUR_N.x + y * SPUR_N.y) / 14.0
    v = (x * SPUR_D.x + y * SPUR_D.y) / 90.0
    gully = abs(noise.noise(Vector((u, v, 4.0))))
    # fade the erosion out toward the crest so the traced skyline is not eaten into
    near = min(1.0, max(0.0, (crest_fn(x) - h) / 40.0))
    return max(0.0, h - near * (min(h * 0.05, gully_amp) * (1 - gully) - 1.5 * noise.noise(Vector((x / 15, y / 15, 2)))))

# back snow range on the traced skyline
MX0, MX1, MY0, MY1, MSTEP = -1500.0, 1500.0, 950.0, 1550.0, 3.0
gx = np.arange(MX0, MX1 + 1e-6, MSTEP)
gy = np.arange(MY0, MY1 + 1e-6, MSTEP)
HGRID = build_heights(crest, MTN_Y, gx, gy, spur_gap=55.0, along=0.62, across=1.35, seed=11)

# Main peak (left): in the target it is a clean pyramid, not a bundle of spurs. Its summit sends the
# left and right skyline ridges sideways, one back ridge, and a sharp front arete that comes toward
# the viewer and to the LEFT (on screen it drops from the summit to about x 370, y 195). The arete
# splits a smooth, sunlit left face from a right face that carries the range's parallel ribs.
def pixel_on_plane(px, row, y):
    o, d = pixel_ray(px, row)
    t = (y - o.y) / d.y
    return o + d * t
_sm = pixel_on_plane(446, 50, MTN_Y)
PK_X, PK_Z = _sm.x, _sm.z
PK_RIDGES = [(0.0, 0.53), (90.0, 0.8), (180.0, 0.75), (247.0, 0.72), (360.0, 0.53)]   # (bearing deg, slope)
PK_FACE = 1.3                                   # slope across the middle of a face
_dx = gx[None, :] - PK_X
_dy = gy[:, None] - MTN_Y
_r = np.hypot(_dx, _dy)
_th = np.degrees(np.arctan2(_dy, _dx)) % 360.0
_slope = np.zeros_like(_r)
for (a0, s0), (a1, s1) in zip(PK_RIDGES, PK_RIDGES[1:]):
    sel = (_th >= a0) & (_th < a1)
    f = (_th - a0) / (a1 - a0)
    _slope = np.where(sel, s0 + (s1 - s0) * f + (PK_FACE - (s0 + s1) / 2) * np.sin(np.pi * f) ** 0.7, _slope)
PYR = (PK_Z - _r * _slope).astype(np.float32)
_wall = np.array([crest(x) for x in gx])[None, :] - np.where(_dy < 0, CREST_SLOPE * 0.5, BACK_SLOPE) * np.abs(_dy)
left_face = (_th >= 180.0) & (_th < 247.0) & (PYR > 0.25 * PK_Z) & (_dy < -40.0)   # leave the skyline band alone
# on the pyramid the range's spurs only show as low ribs (at most ~12 m proud of the face), so they read
# as texture on the faces instead of hard ridges cutting across the peak
peak_zone = PYR > 0.15 * PK_Z
ribbed = np.minimum(_wall, PYR + 0.45 * np.clip(HGRID - PYR, 0.0, 26.0))
HGRID = np.where(left_face, np.minimum(PYR, _wall),
                 np.where(peak_zone, np.maximum(ribbed, np.minimum(PYR, _wall)),
                          np.maximum(HGRID, np.minimum(PYR, _wall)))).astype(np.float32)
HGRID = np.maximum(HGRID, 0.0)

# ---- structure lines the user marked on the main peak (10-19), in target-image pixels -------------
# Each line is placed so that it appears exactly where it is drawn: for every pixel on it we walk out
# along the overview camera's ray and stop where the ray is `prot` metres above the surface behind,
# so the ridge stands proud of the face by that much while keeping its screen position. A ridge is
# then a chain of such points with steep falls (slope RIDGE_SIDE) on both sides, merged by max().
RIDGE_SIDE = 1.5
def surf(x, y):
    i, j = int(round((x - gx[0]) / MSTEP)), int(round((y - gy[0]) / MSTEP))
    if not (0 <= i < len(gx) and 0 <= j < len(gy)):
        return 0.0
    return float(HGRID[j, i])

def ray_point(px, row, prot):
    o, d = pixel_ray(px, row)
    prev = None
    for k in range(1000):
        y = gy[0] + 1.0 * k
        t = (y - o.y) / d.y
        p = o + d * t
        if p.z - surf(p.x, p.y) <= prot:
            return p if prev is None else prev.lerp(p, 0.5)
        prev = p
    return p

def add_ridge(pixels, prof):
    """pixels: polyline in target pixels; prof(t) = metres the ridge stands proud, t in 0..1."""
    global HGRID
    pts = []
    seg_len = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pixels, pixels[1:])]
    total = sum(seg_len)
    acc = 0.0
    for (a, b), L in zip(zip(pixels, pixels[1:]), seg_len):
        n = max(2, int(L / 3))
        for k in range(n):
            f = k / n
            t = (acc + L * f) / total
            pts.append(ray_point(a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, prof(t)))
        acc += L
    pts.append(ray_point(*pixels[-1], prof(1.0)))
    R = 140.0
    for p in pts:
        i0, i1 = np.searchsorted(gx, p.x - R), np.searchsorted(gx, p.x + R)
        j0, j1 = np.searchsorted(gy, p.y - R), np.searchsorted(gy, p.y + R)
        if i1 <= i0 or j1 <= j0:
            continue
        dist = np.hypot(gx[None, i0:i1] - p.x, gy[j0:j1, None] - p.y)
        cone = p.z - RIDGE_SIDE * dist
        # no skyline cap here: every ridge point lies on the ray of a pixel below the painted skyline,
        # and its cone falls away faster than the sightline rises, so the skyline cannot move
        HGRID[j0:j1, i0:i1] = np.maximum(HGRID[j0:j1, i0:i1], cone)

bump = lambda peak: (lambda t: peak * math.sin(math.pi * t) ** 0.7)
# upper inverted V: the summit's two front ridges
add_ridge([(453, 48), (430, 75), (405, 110), (384, 146)], bump(18.0))
add_ridge([(453, 48), (500, 88), (545, 135)], bump(18.0))
# lower inverted V: a lower peak standing in front of the main face, its apex at (462, 113)
add_ridge([(462, 113), (430, 140), (386, 168), (339, 184)], lambda t: 45.0 * (1 - t) ** 0.7)
add_ridge([(462, 113), (530, 152), (603, 198)], lambda t: 45.0 * (1 - t) ** 0.7)
# two curved ribs on the lower peak's face
add_ridge([(436, 171), (446, 200), (462, 227)], bump(11.0))
add_ridge([(469, 155), (489, 192), (514, 229)], bump(11.0))

def mtn_h(x, y):
    return grid_lookup(HGRID, gx, gy, MSTEP, x, y, 9.0, crest)

# front rocky range: crests read off the target (orange lines of the structure analysis)
FRONT_Y = 880.0
FRONT_LINES = [[(-120, 300), (60, 215), (170, 165), (240, 200), (300, 230)],   # left end ramps off-frame (10-20)
               [(560, 250), (665, 165), (760, 230)],
               [(1060, 230), (1170, 170), (1300, 260), (1420, 300), (1520, 300)]]
fx, fz = [], []
for line_ in FRONT_LINES:
    seg_x, seg_z = [], []
    for (pa, ra), (pb, rb) in zip(line_, line_[1:]):
        for t in np.linspace(0, 1, 12, endpoint=False):
            o, d = pixel_ray(pa + (pb - pa) * t, ra + (rb - ra) * t)
            tt = (FRONT_Y - o.y) / d.y
            seg_x.append(o.x + d.x * tt)
            seg_z.append(o.z + d.z * tt)
    fx.append(np.array(seg_x))
    fz.append(np.array(seg_z))

def front_crest(x):
    best = 0.0
    for sx_, sz_ in zip(fx, fz):
        if sx_[0] - 1 <= x <= sx_[-1] + 1:
            best = max(best, float(np.interp(x, sx_, sz_)))
    return best

FX0, FX1, FY0, FY1, FSTEP = -900.0, 900.0, 760.0, 1000.0, 3.0
fgx = np.arange(FX0, FX1 + 1e-6, FSTEP)
fgy = np.arange(FY0, FY1 + 1e-6, FSTEP)
FGRID = build_heights(front_crest, FRONT_Y, fgx, fgy, spur_gap=35.0, along=0.7, across=1.5, seed=23)

def front_h(x, y):
    return grid_lookup(FGRID, fgx, fgy, FSTEP, x, y, 5.0, front_crest)

def project_class(c, rock_key):
    u, v, depth = world_to_camera_view(sc, cam, c)
    px, row = int(u * IW), int((1 - v) * IH)
    if 1 <= px < IW - 1 and 1 <= row < IH - 1 and not SKY[row, px]:
        snow, rock = SNOW_S[row, px], ROCK_S[row, px]
        if snow + rock > 0.3:
            return "mtn_snow" if snow >= rock else rock_key
        green = (g_[row, px] > r_[row, px] + 0.05) and (g_[row, px] > b_[row, px] - 0.05)
        if green:
            return "mtn_forest"
    return None

def mtn_class(c, n):
    k = project_class(c, "mtn_rock")
    if k:
        return k
    # unseen faces: snow on the faces turned to the light (from the upper left), rock on the rest
    if c.z < 50:
        return "mtn_forest"
    lit = n.x * -0.7 + n.y * -0.35 + n.z * 0.62
    return "mtn_snow" if (c.z > 0.45 * crest(c.x) and lit > 0.45) else "mtn_rock"

def front_class(c, n):
    if c.z < 40:
        return "mtn_forest"
    k = project_class(c, "mtn_rock_dk")
    if k == "mtn_snow" and n.z < 0.55:
        return "mtn_rock_dk"           # the front range keeps snow only in its gentle gullies
    return k or "mtn_rock_dk"

MOUNT = heightfield("Mountains", COLS["33_Far"], MX0, MX1, MY0, MY1, MSTEP, MSTEP, mtn_h, mtn_class)
FRONT = heightfield("Front range", COLS["33_Far"], FX0, FX1, FY0, FY1, FSTEP, FSTEP, front_h, front_class)
# forest climbing the feet of both ranges up to the tree line (bare green faces before 10-19)
for tag, objs, seed in (("Mountain forest", MOUNT, 41), ("Front range forest", FRONT, 53)):
    base = objs.get("mtn_forest")
    if base is None:
        continue
    forest_density(base.data, 45.0, 95.0, seed / 10)
    area = sum(p.area for p in base.data.polygons)
    dens = min(0.1, 250000.0 / max(area, 1.0))       # cap instance count for render speed
    print("FOREST", tag, int(area), "m2, density", round(dens, 4))
    forest_scatter(tag, base, dens, (0.8, 1.4), seed)
# ---- forested foothills (10-20): the slope between the lake and the snow range -------------------
# In the photos (IMG_6008/6020) a continuous forested mountainside rises from the valley floor to the
# foot of the rock; the old model had a low hump of trees and then flat ground. The top edge of the
# forest is read from the target image column by column (rows ~240-330; the roof hides the middle,
# which is interpolated), cast along the overview camera's rays to the crest plane y = FOOT_CREST,
# and lowered by the height of the trees standing on it. The slope rises from y = FOOT_Y0 with a
# concave profile, is cut by fall-line gullies, and turns to rock where it is steep.
forest_px = (g_ > r_ + 0.02) & (g_ > b_ - 0.04) & (IMG.mean(-1) < 0.5)
cols, rows = [], []
for x in list(range(120, 600, 10)) + list(range(1080, 1630, 10)):
    run = np.convolve(forest_px[100:420, x].astype(int), np.ones(6, int), 'valid')
    if (run >= 6).any():
        cols.append(x)
        rows.append(100 + int(np.argmax(run >= 6)))
rows = np.array([np.median(rows[max(0, k - 3):k + 4]) for k in range(len(rows))])
FOOT_CREST, FOOT_Y0, FOOT_TREE = 650.0, 170.0, 20.0
fx_, fz_ = [], []
for x, row in zip(cols, rows):
    o, d = pixel_ray(x, row)
    t = (FOOT_CREST - o.y) / d.y
    fx_.append(o.x + d.x * t)
    fz_.append(o.z + d.z * t - FOOT_TREE)
fx_, fz_ = np.array(fx_), np.array(fz_)
def foot_crest(x):
    return float(np.interp(x, fx_, fz_)) * (1 + 0.08 * noise.noise(Vector((x / 90.0, 0.0, 6.0))))

def foot_h(x, y):
    top = foot_crest(x)
    if y <= FOOT_Y0:
        return 0.0
    if y <= FOOT_CREST:
        t = (y - FOOT_Y0) / (FOOT_CREST - FOOT_Y0)
        h = top * t ** 1.35
    else:
        t = (y - FOOT_CREST) / 250.0
        h = top * max(0.0, 1 - t) ** 1.2
    g = noise.ridged_multi_fractal(Vector((x / 45.0, y / 140.0, 3.0)), 1.0, 2.0, 3, 1.0, 2.0)
    return max(0.0, h * (1 + 0.06 * noise.noise(Vector((x / 35, y / 35, 1.0)))) - h * 0.25 * max(0.0, g - 0.55))

FOOT = heightfield("Foothills", COLS["33_Far"], -900, 900, FOOT_Y0, 900, 4, 4, foot_h,
                   lambda c, n: "hill" if n.z > 0.6 else "hill_rock")
forest_density(FOOT["hill"].data, 1e9, 1e9 + 1, 2.0)
forest_scatter("Foothill forest", FOOT["hill"], 0.25, (0.7, 1.3), 5)     # Poisson yields ~1/9 of Density Max
print("FOOTHILLS crest z range", round(float(fz_.min()), 1), round(float(fz_.max()), 1))

err = []
for x in range(100, IW - 100, 200):                 # check: the traced crest reprojects onto the skyline
    u, v, _ = world_to_camera_view(sc, cam, Vector((CX[x // 2], MTN_Y, CZ[x // 2])))
    err.append(abs((1 - v) * IH - sky_rows[x]))
print("MTN_SKYLINE_REPROJECTION_PX", round(max(err), 2))


# ================================================================== detail cameras
def look_cam(name, loc, target, lens):
    cd = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    cd.lens, cd.clip_start, cd.clip_end = lens, 0.03, 6000
    o = bpy.data.objects.get(name) or bpy.data.objects.new(name, cd)
    if o.name not in bpy.data.collections["08_Cameras"].objects:
        bpy.data.collections["08_Cameras"].objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()

look_cam("Cam_Env_Yard", (-2.6, -4.6, 1.5), (0.2, -0.4, 0.35), 28)
look_cam("Cam_Env_Woodpile", (3.2, -2.7, 1.25), (5.0, -0.35, 0.35), 30)
look_cam("Cam_Env_Pine", (-9.5, -1.5, 1.8), (-16.0, 12.0, 6.0), 26)
look_cam("Cam_Env_Fence", (-6.8, -1.2, 1.25), (-11.0, 2.6, 0.6), 30)
look_cam("Cam_Env_Mountains", (0, -24, 6), (-250, 1200, 160), 55)

bpy.ops.wm.save_mainfile()
cnt = sum(len(o.data.vertices) for cn in ("31_Yard", "32_Landscape", "33_Far") for o in COLS[cn].objects
          if o.type == 'MESH' and not o.modifiers.get("Scatter"))
print("ENV_SAVED", cnt, "verts (before scatter instances)", len(far_pines), "far pines")
