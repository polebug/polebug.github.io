"""Stage 5: stylised picture-book materials, lighting and render setup (EEVEE).

Run last, after build_environment.py:
    Blender -b assets/blender/companion-house.blend --python build_materials.py

Every object keeps the colour it was given while modelling (object.color). One shared material,
"Painted", reads that colour through Object Info, so the palette stays in the build scripts:
  * light is quantised into three soft bands (lit / mid / shade); shade is tinted cool blue-violet;
  * a world-space noise breaks each flat area into slightly uneven, hand-painted colour;
  * a screen-space paper grain sits over everything;
  * thin warm-brown outlines come from Freestyle (silhouettes, borders, sharp creases).
Glass, flames, bulbs and the lake get their own small materials. The snow on the mountains is no
longer decided face by face: each vertex carries its position in the overview camera, and the shader
reads a smoothed snow mask taken from the target image, so snow lines are soft instead of stepped.
Shadows are real (sun + EEVEE), so they move when the sun moves; nothing is painted into colours.
"""
import bpy, math, os, sys
import numpy as np
from mathutils import Vector, Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from house_spec import *   # noqa: E402,F403

sc = bpy.context.scene
ROOT = os.path.abspath(os.path.join(os.path.dirname(bpy.data.filepath), "..", ".."))
TEX = os.path.join(ROOT, "assets", "blender", "textures")
os.makedirs(TEX, exist_ok=True)
SUN_TO = Vector((-0.45, -0.62, 0.64)).normalized()      # direction toward the sun: upper left, in front
# LIGHTING = False shows flat colour only (tried 10-19 and rejected: the user wants the light kept).
LIGHTING = True
PINE_GREEN = (0.20, 0.40, 0.24)     # 10-19: one foliage colour for every pine; only light varies it


def new_mat(name):
    m = bpy.data.materials.get(name)
    if m:
        bpy.data.materials.remove(m)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes.clear()
    return m, m.node_tree.nodes, m.node_tree.links


def node(N, t, loc, **kw):
    n = N.new(t)
    n.location = loc
    for k, v in kw.items():
        setattr(n, k, v)
    return n


def toon_chain(N, L, color_socket, x=0):
    """color -> painted, banded, paper-grained emission. Returns the emission node."""
    diff = node(N, "ShaderNodeBsdfDiffuse", (x - 900, 300))
    diff.inputs["Color"].default_value = (1, 1, 1, 1)
    s2r = node(N, "ShaderNodeShaderToRGB", (x - 700, 300))
    L.new(diff.outputs[0], s2r.inputs[0])
    bw = node(N, "ShaderNodeRGBToBW", (x - 520, 300))
    L.new(s2r.outputs["Color"], bw.inputs[0])
    ramp = node(N, "ShaderNodeValToRGB", (x - 340, 300))
    cr = ramp.color_ramp
    cr.interpolation = 'EASE'
    cr.elements[0].position, cr.elements[0].color = 0.22, (0.52, 0.53, 0.68, 1)    # shade: cool violet
    cr.elements[1].position, cr.elements[1].color = 0.85, (1.0, 0.97, 0.92, 1)     # lit, faintly warm
    mid = cr.elements.new(0.5)
    mid.color = (0.82, 0.80, 0.84, 1)
    L.new(bw.outputs[0], ramp.inputs[0])
    # painterly unevenness inside flat colour areas (world space, so it sticks to the surface)
    tc = node(N, "ShaderNodeTexCoord", (x - 900, -100))
    nz = node(N, "ShaderNodeTexNoise", (x - 700, -100))
    nz.inputs["Scale"].default_value = 1.2
    nz.inputs["Detail"].default_value = 4.0
    nz.inputs["Distortion"].default_value = 1.2            # wobbly, wash-like blotches
    L.new(tc.outputs["Object"], nz.inputs["Vector"])
    gr = node(N, "ShaderNodeTexNoise", (x - 700, -230))     # pigment granulation
    gr.inputs["Scale"].default_value = 40.0
    gr.inputs["Detail"].default_value = 1.0
    L.new(tc.outputs["Object"], gr.inputs["Vector"])
    wash = node(N, "ShaderNodeMath", (x - 560, -150), operation='MULTIPLY_ADD')
    L.new(nz.outputs["Fac"], wash.inputs[0])
    wash.inputs[1].default_value = 0.8
    L.new(gr.outputs["Fac"], wash.inputs[2])
    vr = node(N, "ShaderNodeMapRange", (x - 420, -100))
    vr.inputs["From Min"].default_value, vr.inputs["From Max"].default_value = 0.6, 1.3
    vr.inputs["To Min"].default_value, vr.inputs["To Max"].default_value = 0.86, 1.1
    L.new(wash.outputs[0], vr.inputs["Value"])
    # paper grain fixed to the picture plane
    pg = node(N, "ShaderNodeTexNoise", (x - 700, -350))
    pg.inputs["Scale"].default_value = 260.0
    pg.inputs["Detail"].default_value = 2.0
    L.new(tc.outputs["Window"], pg.inputs["Vector"])
    pr = node(N, "ShaderNodeMapRange", (x - 520, -350))
    pr.inputs["To Min"].default_value, pr.inputs["To Max"].default_value = 0.95, 1.02
    L.new(pg.outputs["Fac"], pr.inputs["Value"])
    # object colours were picked as display (sRGB) values: convert to linear before shading
    lin = node(N, "ShaderNodeGamma", (x - 340, 500))
    lin.inputs["Gamma"].default_value = 2.2
    L.new(color_socket, lin.inputs["Color"])
    m1 = node(N, "ShaderNodeVectorMath", (x - 160, 150), operation='MULTIPLY')
    L.new(lin.outputs[0], m1.inputs[0])
    if LIGHTING:
        L.new(ramp.outputs["Color"], m1.inputs[1])
    else:
        m1.inputs[1].default_value = (1.0, 1.0, 1.0)
    m2 = node(N, "ShaderNodeVectorMath", (x, 0), operation='SCALE')
    L.new(m1.outputs[0], m2.inputs[0])
    L.new(vr.outputs[0], m2.inputs["Scale"])
    m3 = node(N, "ShaderNodeVectorMath", (x + 160, 0), operation='SCALE')
    L.new(m2.outputs[0], m3.inputs[0])
    L.new(pr.outputs[0], m3.inputs["Scale"])
    em = node(N, "ShaderNodeEmission", (x + 340, 0))
    L.new(m3.outputs[0], em.inputs["Color"])
    return em


# ------------------------------------------------------------------ Painted (the default material)
painted, N, L = new_mat("Painted")
oi = node(N, "ShaderNodeObjectInfo", (-1100, 500))
em = toon_chain(N, L, oi.outputs["Color"])
out = node(N, "ShaderNodeOutputMaterial", (600, 0))
L.new(em.outputs[0], out.inputs["Surface"])
aov = node(N, "ShaderNodeOutputAOV", (600, -200))          # outline mask for the compositor
aov.aov_name = "outline"
L.new(oi.outputs["Object Index"], aov.inputs["Value"])


def flat_emission(name, rgb, strength=1.0):
    m, N, L = new_mat(name)
    e = node(N, "ShaderNodeEmission", (0, 0))
    e.inputs["Color"].default_value = (*(c ** 2.2 for c in rgb), 1)
    e.inputs["Strength"].default_value = strength
    o = node(N, "ShaderNodeOutputMaterial", (200, 0))
    L.new(e.outputs[0], o.inputs["Surface"])
    return m

glass = flat_emission("Glass", (0.66, 0.84, 0.96))           # windows read as bright sky-lake views
fire = flat_emission("Flame", (1.0, 0.55, 0.15), 4.0)
fire_core = flat_emission("Flame core", (1.0, 0.85, 0.45), 6.0)
bulb = flat_emission("Lamp glow", (1.0, 0.86, 0.55), 3.0)

# foliage (pines): one green everywhere; the colour differences in the target are light, not paint.
# Light picks the colour directly: sunlit -> pale yellow-green, half-lit -> mid green, shade -> deep
# teal-green. EEVEE shadows mean fronds under other fronds stay dark.
fol, N, L = new_mat("Pine foliage")
d_ = node(N, "ShaderNodeBsdfDiffuse", (-900, 300))
s2 = node(N, "ShaderNodeShaderToRGB", (-700, 300))
L.new(d_.outputs[0], s2.inputs[0])
bw_ = node(N, "ShaderNodeRGBToBW", (-520, 300))
L.new(s2.outputs["Color"], bw_.inputs[0])
fr = node(N, "ShaderNodeValToRGB", (-340, 300))
c_ = fr.color_ramp
c_.interpolation = 'EASE'
lin = lambda r, g, b: (r ** 2.2, g ** 2.2, b ** 2.2, 1)
c_.elements[0].position, c_.elements[0].color = 0.4, lin(0.11, 0.27, 0.21)     # shade: deep teal-green
c_.elements[1].position, c_.elements[1].color = 0.95, lin(0.80, 0.82, 0.38)     # sun: pale yellow-green
md = c_.elements.new(0.7)
md.color = lin(0.25, 0.44, 0.24)                                                 # half-lit green
L.new(bw_.outputs[0], fr.inputs[0])
tcf = node(N, "ShaderNodeTexCoord", (-900, -100))
nzf = node(N, "ShaderNodeTexNoise", (-700, -100))
nzf.inputs["Scale"].default_value = 2.5
L.new(tcf.outputs["Object"], nzf.inputs["Vector"])
vrf = node(N, "ShaderNodeMapRange", (-520, -100))
vrf.inputs["To Min"].default_value, vrf.inputs["To Max"].default_value = 0.9, 1.08
L.new(nzf.outputs["Fac"], vrf.inputs["Value"])
scf = node(N, "ShaderNodeVectorMath", (-160, 150), operation='SCALE')
if LIGHTING:
    L.new(fr.outputs["Color"], scf.inputs[0])
else:
    scf.inputs[0].default_value = lin(0.20, 0.40, 0.24)[:3]        # one flat pine green
L.new(vrf.outputs[0], scf.inputs["Scale"])
emf = node(N, "ShaderNodeEmission", (100, 150))
L.new(scf.outputs[0], emf.inputs["Color"])
of = node(N, "ShaderNodeOutputMaterial", (300, 150))
L.new(emf.outputs[0], of.inputs["Surface"])

# lake: painted blue, lighter toward the far shore
lake_m, N, L = new_mat("Lake water")
sh = node(N, "ShaderNodeAttribute", (-1100, 300), attribute_name="shore")
mix = node(N, "ShaderNodeMix", (-760, 300), data_type='RGBA')
mix.inputs[6].default_value = (0.62, 0.70, 0.62, 1)      # shallow: clear water over a stony bed
mix.inputs[7].default_value = (0.24, 0.50, 0.84, 1)      # deep blue
L.new(sh.outputs["Fac"], mix.inputs["Factor"])
em = toon_chain(N, L, mix.outputs[2])
o = node(N, "ShaderNodeOutputMaterial", (600, 0))
L.new(em.outputs[0], o.inputs["Surface"])


# ------------------------------------------------------------------ snow mask from the target image
timg = bpy.data.images.load(os.path.join(ROOT, "assets", "concepts", "home-interior-refined-2026-10-19.png"), check_existing=True)
IW, IH = timg.size
IMG = np.array(timg.pixels[:], dtype=np.float32).reshape(IH, IW, 4)[..., :3]      # bottom-up rows
r_, g_, b_ = IMG[..., 0], IMG[..., 1], IMG[..., 2]
SKY = (b_ > 0.55) & (b_ - r_ > 0.25) & (b_ - g_ > 0.08)
SNOW = ((IMG.mean(-1) > 0.65) & (IMG.max(-1) - IMG.min(-1) < 0.16)).astype(np.float32)
ROCK = ((~SKY) & (b_ - g_ > 0.05) & (g_ - r_ < 0.08)).astype(np.float32)

def blur(a, k):
    c = np.cumsum(np.cumsum(np.pad(a, ((k + 1, k), (k + 1, k)), mode='edge'), 0), 1)
    return (c[2 * k + 1:, 2 * k + 1:] - c[:-2 * k - 1, 2 * k + 1:] - c[2 * k + 1:, :-2 * k - 1] + c[:-2 * k - 1, :-2 * k - 1]) / (2 * k + 1) ** 2

sn, rk = blur(blur(SNOW, 2), 2), blur(blur(ROCK, 2), 2)
prob = sn / np.maximum(sn + rk, 1e-3)
mask = bpy.data.images.get("target-snow-mask") or bpy.data.images.new("target-snow-mask", IW, IH, alpha=False, float_buffer=False)
px = np.ones((IH, IW, 4), np.float32)
px[..., 0] = px[..., 1] = px[..., 2] = prob
mask.pixels = px.ravel()
mask.filepath_raw = os.path.join(TEX, "target-snow-mask.png")
mask.file_format = 'PNG'
mask.save()
mask.colorspace_settings.name = 'Non-Color'

cam = bpy.data.objects["Cam_Overview"]
dg = bpy.context.evaluated_depsgraph_get()
PROJ = np.array(cam.calc_matrix_camera(dg, x=sc.render.resolution_x, y=sc.render.resolution_y)) @ \
    np.array(cam.matrix_world.inverted())
cam_pos = np.array(cam.matrix_world.translation)


def overview_uv(o, snow_class):
    """UV 'overview' = where each vertex falls in the overview image; attribute 'seen' = 1 where the
    face looks toward that camera and lies in the frame; 'cls' = the class it had in modelling."""
    me = o.data
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(n, 3) @ np.array(o.matrix_world)[:3, :3].T + np.array(o.matrix_world)[:3, 3]
    h = np.c_[co, np.ones(n)] @ PROJ.T
    ndc = h[:, :2] / h[:, 3:4]
    uv = (ndc + 1) / 2
    if "overview" not in me.uv_layers:
        me.uv_layers.new(name="overview")
    nl = len(me.loops)
    vi = np.empty(nl, np.int32)
    me.loops.foreach_get("vertex_index", vi)
    me.uv_layers["overview"].data.foreach_set("uv", uv[vi].astype(np.float32).ravel())
    pn = np.empty(len(me.polygons) * 3, np.float32)
    me.polygons.foreach_get("normal", pn)
    pc = np.empty(len(me.polygons) * 3, np.float32)
    me.polygons.foreach_get("center", pc)
    pn, pc = pn.reshape(-1, 3), pc.reshape(-1, 3)
    pn = pn * np.where(pn[:, 2:3] < 0, -1.0, 1.0)         # terrain faces: use the upward normal
    facing = ((cam_pos - pc) * pn).sum(1) > 0
    ls = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_start", ls)
    lt = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_total", lt)
    seen_poly = facing
    seen_loop = np.repeat(seen_poly, lt)
    inframe = ((uv[vi] > 0.003) & (uv[vi] < 0.997)).all(1)
    for nm, val in (("seen", (seen_loop & inframe).astype(np.float32)), ("cls", np.full(nl, snow_class, np.float32))):
        a = me.attributes.get(nm) or me.attributes.new(nm, 'FLOAT', 'CORNER')
        a.data.foreach_set("value", val)


def mountain_material(name, rock_rgb):
    m, N, L = new_mat(name)
    uvn = node(N, "ShaderNodeUVMap", (-1500, 400))
    uvn.uv_map = "overview"
    tex = node(N, "ShaderNodeTexImage", (-1300, 400), image=mask, interpolation='Linear', extension='EXTEND')
    L.new(uvn.outputs[0], tex.inputs[0])
    seen = node(N, "ShaderNodeAttribute", (-1300, 150), attribute_name="seen")
    cls = node(N, "ShaderNodeAttribute", (-1300, 0), attribute_name="cls")
    pick = node(N, "ShaderNodeMix", (-1050, 300), data_type='FLOAT')
    L.new(seen.outputs["Fac"], pick.inputs["Factor"])
    L.new(cls.outputs["Fac"], pick.inputs[2])
    L.new(tex.outputs["Color"], pick.inputs[3])
    # unseen faces: snow where the face turns up toward the light, rock elsewhere
    geo = node(N, "ShaderNodeNewGeometry", (-1500, -250))
    dot = node(N, "ShaderNodeVectorMath", (-1300, -250), operation='DOT_PRODUCT')
    dot.inputs[1].default_value = tuple(SUN_TO)
    L.new(geo.outputs["Normal"], dot.inputs[0])
    sm = node(N, "ShaderNodeMapRange", (-1050, 50))
    sm.inputs["From Min"].default_value, sm.inputs["From Max"].default_value = 0.42, 0.58   # soft snow edge
    L.new(pick.outputs[0], sm.inputs["Value"])
    mix = node(N, "ShaderNodeMix", (-800, 300), data_type='RGBA')
    mix.inputs[6].default_value = (*rock_rgb, 1)        # display values: the toon chain linearises them
    mix.inputs[7].default_value = (0.98, 0.98, 1.0, 1)
    L.new(sm.outputs[0], mix.inputs["Factor"])
    em = toon_chain(N, L, mix.outputs[2])
    o = node(N, "ShaderNodeOutputMaterial", (600, 0))
    L.new(em.outputs[0], o.inputs["Surface"])
    return m

mtn_back = mountain_material("Mountain snow and rock", (0.50, 0.53, 0.64))
mtn_front = mountain_material("Front range rock", (0.40, 0.42, 0.52))


# ------------------------------------------------------------------ assign
def assign(o, m):
    if o.type != 'MESH':
        return
    o.data.materials.clear()
    o.data.materials.append(m)

import colorsys
def graded(o):
    base = o.get("base_color")
    if base is None:                                  # keep the modelling colour so reruns don't compound
        base = tuple(o.color[:3])
        o["base_color"] = base
    r, g, b = base
    h, sat, v = colorsys.rgb_to_hsv(r, g, b)
    hd = h * 360
    n = o.name
    if any(k in n for k in ("Boulder", "Lake rock", "Lake shore stones")):
        return (0.86 + 0.04 * (hash(n) % 3 - 1), 0.79, 0.64)                 # warm cream rocks
    if sat < 0.15 and v < 0.95:                                               # greys: plinth, chimney, steps
        return (min(1, r * 1.07), g * 1.02, b * 0.92)
    if 0 <= hd <= 48 and sat > 0.2:                                           # wood, terracotta, roof
        sat, v = min(0.66, sat * 1.22), min(0.95, v * 1.08)
    elif 60 <= hd <= 175:                                                     # foliage and grass
        hd, sat, v = max(62.0, hd - 7.0), min(0.7, sat * 1.0), min(0.92, v * 1.1)
    return colorsys.hsv_to_rgb(hd / 360, sat, v)

for o in bpy.data.objects:
    if o.type == 'MESH' or (o.type == 'EMPTY'):
        o.color = (*graded(o), 1.0)

special = 0
for o in bpy.data.objects:
    if o.type != 'MESH':
        continue
    n = o.name
    if o.modifiers.get("Twigs") or n.startswith(("Twig ", "Tree source", "G ", "fern_02", "moss_01", "Moss clump", "rock_07", "stone_01", "periwinkle", "PH ", "Char ")):
        continue                                  # realistic trees (trees.py) keep bark and needle materials
    if n.startswith("Mountains ") or n.startswith("Front range "):
        if n.endswith("mtn_forest"):
            assign(o, painted)
            continue
        overview_uv(o, 1.0 if n.endswith("mtn_snow") else 0.0)
        assign(o, mtn_front if n.startswith("Front range") else mtn_back)
        special += 1
    elif "needle" in n:
        o.color = (*PINE_GREEN, 1.0)      # same green on every frond; shaded like everything else
        assign(o, painted)
    elif "glass" in n.lower():
        assign(o, glass)
    elif n.endswith(" - fire_core"):
        assign(o, fire_core)
    elif n.endswith(" - fire"):
        assign(o, fire)
    elif n.endswith(" - bulb"):
        assign(o, bulb)
    elif n == "Lake":
        assign(o, lake_m)
    else:
        assign(o, painted)

# ------------------------------------------------------------------ lights
for o in list(bpy.data.objects):
    if o.type == 'LIGHT':
        bpy.data.objects.remove(o, do_unlink=True)
LC = bpy.data.collections.get("08_Cameras")

def light(name, kind, loc, energy, color, **kw):
    ld = bpy.data.lights.new(name, kind)
    ld.energy, ld.color = energy, color
    for k, v in kw.items():
        setattr(ld, k, v)
    o = bpy.data.objects.new(name, ld)
    LC.objects.link(o)
    o.location = loc
    return o

sun = light("Sun", 'SUN', (0, 0, 30), 4.0, (1.0, 0.96, 0.9), angle=math.radians(3))
sun.rotation_euler = (-SUN_TO).to_track_quat('-Z', 'Y').to_euler()
sun.data.use_shadow = True
# warm interior lamps (they also make the rooms read inside the shaded house)
for name, loc, e in (("Dining pendant light", (0.75, 2.5, FLOOR[1] + 1.38), 35),      # linear pendant (10-20 refit)
                     ("F1 floor lamp light", (-1.70, 3.40, FLOOR[1] + 1.50), 18),
                     ("F1 sconce light", (0.8, DEPTH - 0.3, FLOOR[1] + 1.55), 15),
                     ("F2 sconce light L", (-2.95, DEPTH - 0.3, FLOOR[2] + 1.6), 15),
                     ("Bedside lamp light", (-1.71, 4.70, FLOOR[3] + 0.91), 20),
                     ("Bedside lamp light 2", (-1.71, 2.30, FLOOR[3] + 0.91), 20),
                     ("Attic floor lamp light", (3.25, 2.95, FLOOR[3] + 1.40), 18),
                     ("Attic lantern light", (2.1, DEPTH - 0.3, FLOOR[3] + 1.35), 12)):
    light(name, 'POINT', loc, e, (1.0, 0.72, 0.42), shadow_soft_size=0.15)
# (10-20: ceiling 'Daylight fill' lights were tried and removed - the user found the even light unnatural;
# daylight now comes only from the sun and sky through the open front and the windows)
# 10-20 kitchen refit: recessed downlights in the floor-1 kitchen ceiling (between the joists), as in
# the user's reference photos; fixtures are modelled in build_interior_f1.py (KITCHEN_DOWNLIGHTS)
from build_interior_f1_spec import KITCHEN_DOWNLIGHTS   # noqa: E402
for i, (x, y) in enumerate(KITCHEN_DOWNLIGHTS):
    light(f"Kitchen downlight {i}", 'SPOT', (x, y, FLOOR[2] - 0.075), 28, (1.0, 0.86, 0.7),
          spot_size=math.radians(110), spot_blend=0.6, shadow_soft_size=0.04)

# world: saturated blue sky seen by the camera, softer blue-white fill for lighting
w = sc.world
w.use_nodes = True
WN, WL = w.node_tree.nodes, w.node_tree.links
WN.clear()
lp = WN.new("ShaderNodeLightPath")
sky_tc = WN.new("ShaderNodeTexCoord")
skysep = WN.new("ShaderNodeSeparateXYZ")
WL.new(sky_tc.outputs["Window"], skysep.inputs[0])
grad = WN.new("ShaderNodeValToRGB")
grad.color_ramp.elements[0].color = (0.55 ** 2.2, 0.80 ** 2.2, 1.0, 1)      # lower sky, paler
grad.color_ramp.elements[1].color = (0.27 ** 2.2, 0.62 ** 2.2, 0.99 ** 2.2, 1)      # upper sky
WL.new(skysep.outputs["Y"], grad.inputs[0])
wn = WN.new("ShaderNodeTexNoise")                                # watercolour blotches in the sky
wn.inputs["Scale"].default_value = 6.0
wn.inputs["Detail"].default_value = 4.0
WL.new(sky_tc.outputs["Window"], wn.inputs["Vector"])
wr = WN.new("ShaderNodeMapRange")
wr.inputs["To Min"].default_value, wr.inputs["To Max"].default_value = 0.9, 1.07
WL.new(wn.outputs["Fac"], wr.inputs["Value"])
skyc = WN.new("ShaderNodeVectorMath")
skyc.operation = 'SCALE'
WL.new(grad.outputs["Color"], skyc.inputs[0])
WL.new(wr.outputs[0], skyc.inputs["Scale"])
bg_cam = WN.new("ShaderNodeBackground")
WL.new(skyc.outputs[0], bg_cam.inputs["Color"])
bg_amb = WN.new("ShaderNodeBackground")
bg_amb.inputs["Color"].default_value = (0.62, 0.72, 0.88, 1)
bg_amb.inputs["Strength"].default_value = 0.5
mixw = WN.new("ShaderNodeMixShader")
WL.new(lp.outputs["Is Camera Ray"], mixw.inputs["Fac"])
WL.new(bg_amb.outputs[0], mixw.inputs[1])
WL.new(bg_cam.outputs[0], mixw.inputs[2])
wo = WN.new("ShaderNodeOutputWorld")
WL.new(mixw.outputs[0], wo.inputs["Surface"])

# ------------------------------------------------------------------ outlines (Freestyle)
NOL = bpy.data.collections.get("38_No_Outline") or bpy.data.collections.new("38_No_Outline")
for o in list(NOL.objects):
    NOL.objects.unlink(o)
for cn in ("33_Far", "39_Scatter_Sources"):     # instanced grass/flowers/trees take the source's index
    for o in bpy.data.collections[cn].all_objects:
        NOL.objects.link(o)
for o in bpy.data.objects:
    if o.modifiers.get("Scatter") and o.name not in NOL.objects:
        NOL.objects.link(o)
for o in bpy.data.objects:          # leaves, grass and flowers would turn into scribbles
    if o.type == 'MESH' and any(k in o.name for k in (" - leaf", " - flower", " - stem", "needle", "Lake shore stones")):
        if o.name not in NOL.objects:
            NOL.objects.link(o)

# Freestyle took over 16 minutes on ~2 million vertices (10-19), so outlines are drawn in the
# compositor instead: edges where the surface normal or the depth jumps, only on objects whose
# pass index is 1 (everything not in 38_No_Outline).
sc.render.use_freestyle = False
vl = sc.view_layers[0]
vl.use_pass_normal = True
vl.use_pass_z = True
if "outline" not in [a.name for a in vl.aovs]:
    a_ = vl.aovs.add()
    a_.name, a_.type = "outline", 'VALUE'
for o in bpy.data.objects:
    if o.type == 'MESH':
        o.pass_index = 0 if o.name in NOL.objects else 1
for o in bpy.data.objects:          # assets: children meshes inherit from their empty
    if o.type == 'EMPTY':
        for c in o.children:
            if c.type == 'MESH' and c.name not in NOL.objects:
                c.pass_index = 1
# ------------------------------------------------------------------ render settings
sc.render.engine = 'BLENDER_EEVEE'
sc.eevee.taa_render_samples = 32
sc.view_settings.view_transform = 'Standard'
sc.view_settings.look = 'None'
sc.render.resolution_x, sc.render.resolution_y = 1672, 941
sc.camera = cam
sc.use_nodes = True
cg = bpy.data.node_groups.get("Watercolour") or bpy.data.node_groups.new("Watercolour", "CompositorNodeTree")
cg.nodes.clear()
if not cg.interface.items_tree:
    cg.interface.new_socket("Image", in_out='OUTPUT', socket_type='NodeSocketColor')
rl = cg.nodes.new("CompositorNodeRLayers")
kw = cg.nodes.new("CompositorNodeKuwahara")
try:
    kw.inputs["Type"].default_value = 'Anisotropic'
except Exception:
    pass
kw.inputs["Size"].default_value = 3
hs = cg.nodes.new("CompositorNodeHueSat")
hs.inputs["Saturation"].default_value = 0.96
go = cg.nodes.new("NodeGroupOutput")
cg.links.new(rl.outputs["Image"], kw.inputs["Image"])
cg.links.new(kw.outputs[0], hs.inputs["Image"])
C = cg.nodes
def math(op, a, b=None, val=None):
    m = C.new("ShaderNodeMath")
    m.operation = op
    cg.links.new(a, m.inputs[0])
    if b is not None:
        cg.links.new(b, m.inputs[1])
    elif val is not None:
        m.inputs[1].default_value = val
    return m.outputs[0]
def sobel(sock):
    f = C.new("CompositorNodeFilter")
    try:
        f.inputs["Type"].default_value = 'Sobel'
    except Exception:
        f.filter_type = 'SOBEL'
    cg.links.new(sock, f.inputs["Image"])
    return f.outputs[0]
n_edge = math('GREATER_THAN', sobel(rl.outputs["Normal"]), val=0.9)
z_rel = math('DIVIDE', sobel(rl.outputs["Depth"]), rl.outputs["Depth"])
z_edge = math('GREATER_THAN', z_rel, val=0.06)
edge = math('MAXIMUM', n_edge, z_edge)
inside = math('GREATER_THAN', rl.outputs["outline"], val=0.5)
edge = math('MULTIPLY', edge, inside)
# 10-19: the user judged these compositor outlines worse than none, so they are switched off
# (opacity 0) until a better line method is found; the edge nodes stay for later experiments.
OUTLINE_OPACITY = 0.0
edge = math('MULTIPLY', edge, val=OUTLINE_OPACITY)
ink = C.new("ShaderNodeMix")
ink.data_type = 'RGBA'
ink.blend_type = 'MIX'
cg.links.new(edge, ink.inputs["Factor"])
cg.links.new(hs.outputs[0], ink.inputs[6])
ink.inputs[7].default_value = (0.11, 0.06, 0.03, 1)        # warm dark-brown ink
cg.links.new(ink.outputs[2], go.inputs[0])
sc.compositing_node_group = cg
mask.pack()
bpy.ops.wm.save_mainfile()
print("MATERIALS_SAVED", special, "mountain meshes,", len(NOL.objects), "objects without outline")
