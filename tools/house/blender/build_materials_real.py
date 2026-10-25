"""Realistic look (2026-10-20): the user dropped the watercolour style for real-world modelling.

Run after build_materials.py (which still builds the overview snow mask and assigns base materials):
    Blender -b assets/blender/companion-house.blend --python build_materials_real.py

  * Cycles (GPU/Metal), AgX view transform, denoising
  * physical sky (Nishita) + sun lamp in the same direction, so sky colour and shadows agree
  * house and interior: Wood092 pine and Fabric081C linen (tinted by object colour), procedural
    clay tiles, terracotta, glaze and metals; "Painted" (plain object colour) remains for small props
  * ground: CC0 Ground037 (grass + soil); rock faces and steep forest-slope faces: CC0 Rock063;
    snow mountains: Rock063 under a snow layer driven by the same target-image snow mask
  * water and window glass as real dielectrics; flames and bulbs stay emissive
  * aerial perspective: the mist pass blends distant terrain toward the sky colour in the compositor
The watercolour compositor (Kuwahara) and the toon light bands are no longer used.
"""
import bpy, math, os, sys
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from house_spec import *   # noqa: E402,F403

sc = bpy.context.scene
TEX = os.path.join(os.path.dirname(bpy.data.filepath), "textures")
SUN_TO = Vector((-0.45, -0.62, 0.64)).normalized()


def img_node(N, L, vec, folder, kind, cs):
    im = N.new("ShaderNodeTexImage")
    im.image = bpy.data.images.load(os.path.join(TEX, folder, f"{folder}_2K-JPG_{kind}.jpg"), check_existing=True)
    im.image.colorspace_settings.name = cs
    im.projection, im.projection_blend = 'BOX', 0.25
    L.new(vec, im.inputs[0])
    return im


def pbr(N, L, vec, folder, tint=(1, 1, 1), normal_strength=1.0):
    """Base colour (tinted), roughness and normal from a CC0 set; returns (colour, rough, normal) sockets."""
    c = img_node(N, L, vec, folder, "Color", "sRGB")
    t = N.new("ShaderNodeMix")
    t.data_type, t.blend_type = 'RGBA', 'MULTIPLY'
    t.inputs["Factor"].default_value = 1.0
    t.inputs[7].default_value = (*tint, 1)
    L.new(c.outputs[0], t.inputs[6])
    r = img_node(N, L, vec, folder, "Roughness", "Non-Color")
    n = img_node(N, L, vec, folder, "NormalGL", "Non-Color")
    nm = N.new("ShaderNodeNormalMap")
    nm.inputs["Strength"].default_value = normal_strength
    L.new(n.outputs[0], nm.inputs["Color"])
    return t.outputs[2], r.outputs[0], nm.outputs[0]


def fresh(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes.clear()
    return m, m.node_tree.nodes, m.node_tree.links


def surface(name, folder, scale, tint, rough_mul=1.0, normal_strength=1.0):
    m, N, L = fresh(name)
    tc, mp = N.new("ShaderNodeTexCoord"), N.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale, scale)
    L.new(tc.outputs["Object"], mp.inputs[0])
    col, rough, nrm = pbr(N, L, mp.outputs[0], folder, tint, normal_strength)
    bs = N.new("ShaderNodeBsdfPrincipled")
    L.new(col, bs.inputs["Base Color"])
    L.new(rough, bs.inputs["Roughness"])
    L.new(nrm, bs.inputs["Normal"])
    out = N.new("ShaderNodeOutputMaterial")
    L.new(bs.outputs[0], out.inputs["Surface"])
    return m


# ------------------------------------------------------------------ materials
# Painted -> plain PBR using the object colour (display values -> linear)
m, N, L = fresh("Painted")
oi = N.new("ShaderNodeObjectInfo")
gm = N.new("ShaderNodeGamma")
gm.inputs["Gamma"].default_value = 2.2
L.new(oi.outputs["Color"], gm.inputs["Color"])
bs = N.new("ShaderNodeBsdfPrincipled")
bs.inputs["Roughness"].default_value = 0.65
L.new(gm.outputs[0], bs.inputs["Base Color"])
L.new(bs.outputs[0], N.new("ShaderNodeOutputMaterial").inputs["Surface"])
painted = m

ground = surface("Ground grass", "Ground037", 0.35, (0.5, 0.72, 0.32))   # soil between blades reads green
forest_floor = surface("Forest floor", "Ground037", 0.06, (0.55, 0.62, 0.45))      # seen from far: darker, coarser
rock = surface("Rock", "Rock063", 0.12, (0.85, 0.85, 0.88), normal_strength=1.5)
stone = surface("Stone", "Rock063", 0.9, (0.95, 0.93, 0.9), normal_strength=0.8)   # finer scale for masonry and slabs
limestone = surface("Limestone floor", "Tiles143", 1 / 3.0, (1.12, 1.0, 0.84), rough_mul=0.85, normal_strength=0.6)   # 3 m repeat -> ~50 cm slabs

# snow mountains: rock under snow; the snow mask is the one build_materials.py derived from the target
mtn, N, L = fresh("Mountain snow and rock real")
# rock under snow; the snow mask is the one build_materials.py derived from the target (the version the
# user approved on 10-20). Only change since: the mask is sampled with cubic filtering so its edges no
# longer show the target image's pixel steps.
tc, mp = N.new("ShaderNodeTexCoord"), N.new("ShaderNodeMapping")
mp.inputs["Scale"].default_value = (0.02, 0.02, 0.02)
L.new(tc.outputs["Object"], mp.inputs[0])
rcol, rrough, rnrm = pbr(N, L, mp.outputs[0], "Rock063", (0.62, 0.66, 0.78), 2.0)
uvn = N.new("ShaderNodeUVMap")
uvn.uv_map = "overview"
mask = N.new("ShaderNodeTexImage")
mask.image = bpy.data.images.get("target-snow-mask")
mask.interpolation, mask.extension = 'Cubic', 'EXTEND'
L.new(uvn.outputs[0], mask.inputs[0])
seen = N.new("ShaderNodeAttribute")
seen.attribute_name = "seen"
cls = N.new("ShaderNodeAttribute")
cls.attribute_name = "cls"
pick = N.new("ShaderNodeMix")
pick.data_type = 'FLOAT'
L.new(seen.outputs["Fac"], pick.inputs["Factor"])
L.new(cls.outputs["Fac"], pick.inputs[2])
L.new(mask.outputs["Color"], pick.inputs[3])
geo = N.new("ShaderNodeNewGeometry")
sep = N.new("ShaderNodeSeparateXYZ")
L.new(geo.outputs["Normal"], sep.inputs[0])
flat = N.new("ShaderNodeMapRange")                       # snow slides off the steepest faces
flat.inputs["From Min"].default_value, flat.inputs["From Max"].default_value = 0.25, 0.45
L.new(sep.outputs["Z"], flat.inputs["Value"])
both = N.new("ShaderNodeMath")
both.operation = 'MULTIPLY'
L.new(pick.outputs[0], both.inputs[0])
L.new(flat.outputs[0], both.inputs[1])
edge = N.new("ShaderNodeMapRange")
edge.inputs["From Min"].default_value, edge.inputs["From Max"].default_value = 0.4, 0.6
L.new(both.outputs[0], edge.inputs["Value"])
rock_bs = N.new("ShaderNodeBsdfPrincipled")
L.new(rcol, rock_bs.inputs["Base Color"])
L.new(rrough, rock_bs.inputs["Roughness"])
L.new(rnrm, rock_bs.inputs["Normal"])
snow_bs = N.new("ShaderNodeBsdfPrincipled")
snow_bs.inputs["Base Color"].default_value = (0.92, 0.94, 0.98, 1)
snow_bs.inputs["Roughness"].default_value = 0.45
snow_bs.inputs["Subsurface Weight"].default_value = 0.2
snow_bs.inputs["Subsurface Radius"].default_value = (0.4, 0.6, 0.9)
mixs = N.new("ShaderNodeMixShader")
L.new(edge.outputs[0], mixs.inputs["Fac"])
L.new(rock_bs.outputs[0], mixs.inputs[1])
L.new(snow_bs.outputs[0], mixs.inputs[2])
L.new(mixs.outputs[0], N.new("ShaderNodeOutputMaterial").inputs["Surface"])

water, N, L = fresh("Lake water real")
sh = N.new("ShaderNodeAttribute")
sh.attribute_name = "shore"
cm = N.new("ShaderNodeMix")
cm.data_type = 'RGBA'
cm.inputs[6].default_value = (0.18, 0.2, 0.14, 1)        # shallow: stones of the bed show through
cm.inputs[7].default_value = (0.02, 0.07, 0.10, 1)       # deep
L.new(sh.outputs["Fac"], cm.inputs["Factor"])
wb = N.new("ShaderNodeBsdfPrincipled")
L.new(cm.outputs[2], wb.inputs["Base Color"])
wb.inputs["Roughness"].default_value = 0.04
wb.inputs["IOR"].default_value = 1.33
wn = N.new("ShaderNodeTexNoise")                         # small ripples
wn.inputs["Scale"].default_value = 3.0
bump = N.new("ShaderNodeBump")
bump.inputs["Strength"].default_value = 0.08
L.new(wn.outputs["Fac"], bump.inputs["Height"])
L.new(bump.outputs[0], wb.inputs["Normal"])
L.new(wb.outputs[0], N.new("ShaderNodeOutputMaterial").inputs["Surface"])

glass, N, L = fresh("Glass")
# 10-20 (user: "the side windows let no light in"): a refractive Glass BSDF blocks sunlight and sky
# light in Cycles (caustics are filtered out), so the windows only worked for the camera. Shadow and
# diffuse/glossy-bounce rays now pass straight through (thin window pane), camera rays still see glass.
gb = N.new("ShaderNodeBsdfGlass")
gb.inputs["Roughness"].default_value = 0.02
gtr = N.new("ShaderNodeBsdfTransparent")
glp = N.new("ShaderNodeLightPath")
gor = N.new("ShaderNodeMath"); gor.operation = 'MAXIMUM'
L.new(glp.outputs["Is Shadow Ray"], gor.inputs[0])
gor2 = N.new("ShaderNodeMath"); gor2.operation = 'MAXIMUM'
L.new(glp.outputs["Is Diffuse Ray"], gor2.inputs[0])
L.new(glp.outputs["Is Glossy Ray"], gor2.inputs[1])
L.new(gor2.outputs[0], gor.inputs[1])
gmx = N.new("ShaderNodeMixShader")
L.new(gor.outputs[0], gmx.inputs[0])
L.new(gb.outputs[0], gmx.inputs[1])
L.new(gtr.outputs[0], gmx.inputs[2])
L.new(gmx.outputs[0], N.new("ShaderNodeOutputMaterial").inputs["Surface"])

black_glass, N, L = fresh("Black glass")          # TV screen, hob, hood strip: opaque glossy black
bgb = N.new("ShaderNodeBsdfPrincipled")
bgb.inputs["Base Color"].default_value = (0.005, 0.005, 0.006, 1)
bgb.inputs["Roughness"].default_value = 0.05
L.new(bgb.outputs[0], N.new("ShaderNodeOutputMaterial").inputs["Surface"])


# ------------------------------------------------------------------ house and interior (10-20)
# Real materials for everything the interior/architecture scripts paint with an object colour.
#  * wood: CC0 ambientCG Wood092 (pine). Each board gets a "grain" UV laid out by script so the grain
#    runs along the board's long axis (per loose part, so joined frames work too); the texture is
#    normalised to its own mean colour and multiplied by the object colour, so every piece keeps the
#    tone the interior passes gave it (floors lighter, beams darker ...)
#  * fabric: CC0 ambientCG Fabric081C (linen weave), same tinting, with sheen
#  * clay roof tiles / terracotta, glazed ceramic, iron and bright metal are procedural
import bmesh, random
import numpy as np


def tex_mean(folder):
    im = bpy.data.images.load(os.path.join(TEX, folder, f"{folder}_2K-JPG_Color.jpg"), check_existing=True)
    px = np.empty(len(im.pixels), np.float32)
    im.pixels.foreach_get(px)
    c = px.reshape(-1, 4)[::97, :3]
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)    # stored sRGB -> linear
    return c.mean(0)


def obj_colour(N, L):
    oi = N.new("ShaderNodeObjectInfo")
    gm = N.new("ShaderNodeGamma")
    gm.inputs["Gamma"].default_value = 2.2
    L.new(oi.outputs["Color"], gm.inputs["Color"])
    return gm.outputs[0]


def grain_material(name, folder, scale, rough_mul=1.0, sheen=0.0, normal_strength=1.0):
    m, N, L = fresh(name)
    uv = N.new("ShaderNodeUVMap")
    uv.uv_map = "grain"
    mp = N.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale, scale)
    L.new(uv.outputs[0], mp.inputs[0])
    def img(kind, cs):
        im = N.new("ShaderNodeTexImage")
        im.image = bpy.data.images.load(os.path.join(TEX, folder, f"{folder}_2K-JPG_{kind}.jpg"), check_existing=True)
        im.image.colorspace_settings.name = cs
        L.new(mp.outputs[0], im.inputs[0])
        return im
    norm = N.new("ShaderNodeVectorMath")                 # texture / its mean -> variation around 1
    norm.operation = 'DIVIDE'
    norm.inputs[1].default_value = tuple(float(v) for v in tex_mean(folder))
    L.new(img("Color", "sRGB").outputs[0], norm.inputs[0])
    tint = N.new("ShaderNodeVectorMath")
    tint.operation = 'MULTIPLY'
    L.new(norm.outputs[0], tint.inputs[0])
    L.new(obj_colour(N, L), tint.inputs[1])
    bs = N.new("ShaderNodeBsdfPrincipled")
    L.new(tint.outputs[0], bs.inputs["Base Color"])
    rm = N.new("ShaderNodeMath")
    rm.operation, rm.use_clamp = 'MULTIPLY', True
    rm.inputs[1].default_value = rough_mul
    L.new(img("Roughness", "Non-Color").outputs[0], rm.inputs[0])
    L.new(rm.outputs[0], bs.inputs["Roughness"])
    nm = N.new("ShaderNodeNormalMap")
    nm.uv_map = "grain"
    nm.inputs["Strength"].default_value = normal_strength
    L.new(img("NormalGL", "Non-Color").outputs[0], nm.inputs["Color"])
    L.new(nm.outputs[0], bs.inputs["Normal"])
    if sheen:
        bs.inputs["Sheen Weight"].default_value = sheen
        bs.inputs["Sheen Roughness"].default_value = 0.4
    L.new(bs.outputs[0], N.new("ShaderNodeOutputMaterial").inputs["Surface"])
    return m


def solid_material(name, rough, metallic=0.0, coat=0.0, gain=1.0, noise_scale=0.0, noise_amt=0.0, bump=0.0):
    """Object colour with optional noise mottling (fired clay) and bump; for metal and glaze too."""
    m, N, L = fresh(name)
    col = obj_colour(N, L)
    if gain != 1.0:
        g = N.new("ShaderNodeVectorMath")
        g.operation, g.inputs[3].default_value = 'SCALE', gain
        L.new(col, g.inputs[0])
        col = g.outputs[0]
    bs = N.new("ShaderNodeBsdfPrincipled")
    bs.inputs["Roughness"].default_value = rough
    bs.inputs["Metallic"].default_value = metallic
    bs.inputs["Coat Weight"].default_value = coat
    if noise_scale:
        tc = N.new("ShaderNodeTexCoord")
        nz = N.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = noise_scale
        nz.inputs["Detail"].default_value = 6.0
        L.new(tc.outputs["Object"], nz.inputs["Vector"])
        mr = N.new("ShaderNodeMapRange")
        mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 1 - noise_amt, 1 + noise_amt
        L.new(nz.outputs["Fac"], mr.inputs["Value"])
        mul = N.new("ShaderNodeVectorMath")
        mul.operation = 'SCALE'
        L.new(col, mul.inputs[0])
        L.new(mr.outputs[0], mul.inputs[3])
        col = mul.outputs[0]
        if bump:
            b = N.new("ShaderNodeBump")
            b.inputs["Strength"].default_value = bump
            b.inputs["Distance"].default_value = 0.002
            L.new(nz.outputs["Fac"], b.inputs["Height"])
            L.new(b.outputs[0], bs.inputs["Normal"])
    L.new(col, bs.inputs["Base Color"])
    L.new(bs.outputs[0], N.new("ShaderNodeOutputMaterial").inputs["Surface"])
    return m


def grain_uv(o, done=set()):
    """Planar UV per face, with v along the long axis of the loose part the face belongs to."""
    me = o.data
    if me.name in done:
        return
    done.add(me.name)
    sc_ = o.scale
    bm = bmesh.new()
    bm.from_mesh(me)
    uvl = bm.loops.layers.uv.get("grain") or bm.loops.layers.uv.new("grain")
    seen = set()
    rnd = random.Random(hash(me.name) & 0xffff)
    for f0 in bm.faces:
        if f0.index in seen:
            continue
        island, stack = [], [f0]
        seen.add(f0.index)
        while stack:
            f = stack.pop()
            island.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in seen:
                        seen.add(g.index)
                        stack.append(g)
        co = np.array([[v.co[i] * sc_[i] for i in range(3)] for f in island for v in f.verts])
        ext = co.max(0) - co.min(0)
        long_ax = int(np.argmax(ext))
        off = (rnd.uniform(0, 3), rnd.uniform(0, 3))
        for f in island:
            n_ax = int(np.argmax([abs(c) for c in f.normal]))
            plane = [a for a in range(3) if a != n_ax]
            if long_ax in plane:
                va, ua = long_ax, [a for a in plane if a != long_ax][0]
            else:
                ua, va = plane
            for lp in f.loops:
                p = lp.vert.co
                lp[uvl].uv = (p[ua] * sc_[ua] + off[0], p[va] * sc_[va] + off[1])
    bm.to_mesh(me)
    bm.free()


wood = grain_material("Wood pine", "Wood092", 1.1, rough_mul=0.9)
fabric = grain_material("Fabric linen", "Fabric081C", 5.0, rough_mul=1.0, sheen=0.6, normal_strength=0.7)
clay = solid_material("Clay tile", 0.75, noise_scale=6.0, noise_amt=0.14, bump=0.3)
terracotta = solid_material("Terracotta", 0.85, noise_scale=12.0, noise_amt=0.10, bump=0.2)
glaze = solid_material("Glazed ceramic", 0.12, coat=0.6)
iron = solid_material("Black iron", 0.5, metallic=1.0, gain=3.0, noise_scale=30.0, noise_amt=0.25)
bright = solid_material("Bright metal", 0.22, metallic=1.0)
matte = solid_material("Matte", 0.8)
brushed = solid_material("Brushed steel", 0.38, metallic=1.0)
pearl = solid_material("Pearl white plaster", 0.85, noise_scale=25.0, noise_amt=0.025, bump=0.04)   # floor-1 walls (10-20)
gauze, N, L = fresh("Gauze")                    # sheer crinkled cotton gauze (10-20, user: 轻纱质感)
tcg, mpg = N.new("ShaderNodeTexCoord"), N.new("ShaderNodeMapping")
mpg.inputs["Scale"].default_value = (90.0, 90.0, 6.0)          # crinkles run down the drop
L.new(tcg.outputs["Object"], mpg.inputs[0])
nzg = N.new("ShaderNodeTexNoise")
nzg.inputs["Detail"].default_value = 4.0
L.new(mpg.outputs[0], nzg.inputs["Vector"])
cov = N.new("ShaderNodeMapRange")                                # how much of the light the cloth stops
cov.inputs["To Min"].default_value, cov.inputs["To Max"].default_value = 0.30, 0.55
L.new(nzg.outputs["Fac"], cov.inputs["Value"])
gp = N.new("ShaderNodeBsdfPrincipled")
gp.inputs["Base Color"].default_value = (0.95, 0.95, 0.94, 1)
gp.inputs["Roughness"].default_value = 0.7
gp.inputs["Sheen Weight"].default_value = 0.6
gbump = N.new("ShaderNodeBump")
gbump.inputs["Strength"].default_value = 0.25
L.new(nzg.outputs["Fac"], gbump.inputs["Height"])
L.new(gbump.outputs[0], gp.inputs["Normal"])
gt = N.new("ShaderNodeBsdfTranslucent")
gt.inputs["Color"].default_value = (0.95, 0.95, 0.93, 1)
cloth_mix = N.new("ShaderNodeMixShader")
cloth_mix.inputs[0].default_value = 0.45
L.new(gp.outputs[0], cloth_mix.inputs[1])
L.new(gt.outputs[0], cloth_mix.inputs[2])
see = N.new("ShaderNodeMixShader")                               # transparent where the weave is open
L.new(cov.outputs[0], see.inputs[0])
L.new(N.new("ShaderNodeBsdfTransparent").outputs[0], see.inputs[1])
L.new(cloth_mix.outputs[0], see.inputs[2])
L.new(see.outputs[0], N.new("ShaderNodeOutputMaterial").inputs["Surface"])
# ---- living-dining refit (10-20): leather, satin paint, procedural vintage rug
leather, N, L = fresh("Leather")                  # cognac leather: pebble grain, soft sheen, slight mottling
lb = N.new("ShaderNodeBsdfPrincipled")
lb.inputs["Coat Weight"].default_value = 0.45
lb.inputs["Coat Roughness"].default_value = 0.35
ltc = N.new("ShaderNodeTexCoord")
lvo = N.new("ShaderNodeTexVoronoi")
lvo.inputs["Scale"].default_value = 450.0
L.new(ltc.outputs["Object"], lvo.inputs["Vector"])
lnz = N.new("ShaderNodeTexNoise")
lnz.inputs["Scale"].default_value = 9.0
lnz.inputs["Detail"].default_value = 5.0
L.new(ltc.outputs["Object"], lnz.inputs["Vector"])
lbump = N.new("ShaderNodeBump")
lbump.inputs["Strength"].default_value = 0.12
lbump.inputs["Distance"].default_value = 0.0005
L.new(lvo.outputs["Distance"], lbump.inputs["Height"])
lwr = N.new("ShaderNodeTexNoise")                    # soft creases of worn leather
lwr.inputs["Scale"].default_value = 22.0
lwr.inputs["Detail"].default_value = 8.0
lwr.inputs["Distortion"].default_value = 1.5
L.new(ltc.outputs["Object"], lwr.inputs["Vector"])
lbump2 = N.new("ShaderNodeBump")
lbump2.inputs["Strength"].default_value = 0.18
lbump2.inputs["Distance"].default_value = 0.002
L.new(lwr.outputs["Fac"], lbump2.inputs["Height"])
L.new(lbump.outputs[0], lbump2.inputs["Normal"])
L.new(lbump2.outputs[0], lb.inputs["Normal"])
lrm = N.new("ShaderNodeMapRange")
lrm.inputs["To Min"].default_value, lrm.inputs["To Max"].default_value = 0.22, 0.42
L.new(lnz.outputs["Fac"], lrm.inputs["Value"])
L.new(lrm.outputs[0], lb.inputs["Roughness"])
lcol = obj_colour(N, L)
lmot = N.new("ShaderNodeMapRange")
lmot.inputs["To Min"].default_value, lmot.inputs["To Max"].default_value = 0.8, 1.15
L.new(lnz.outputs["Fac"], lmot.inputs["Value"])
lsc = N.new("ShaderNodeVectorMath")
lsc.operation = 'SCALE'
L.new(lcol, lsc.inputs[0])
L.new(lmot.outputs[0], lsc.inputs[3])
L.new(lsc.outputs[0], lb.inputs["Base Color"])
L.new(lb.outputs[0], N.new("ShaderNodeOutputMaterial").inputs["Surface"])

satin = solid_material("Satin paint", 0.35, coat=0.2)


def ramp(N, stops):
    r = N.new("ShaderNodeValToRGB")
    r.color_ramp.interpolation = 'CONSTANT'
    els = r.color_ramp.elements
    while len(els) > 1:
        els.remove(els[-1])
    els[0].position, els[0].color = stops[0][0], (*stops[0][1], 1)
    for pos, col in stops[1:]:
        e = els.new(pos)
        e.color = (*col, 1)
    return r


rugm, N, L = fresh("Vintage rug")                # rust / cream vintage rug, pattern in rug-local metres (3.0 x 2.6)
CREAM, RUST, BROWN, PALE = (0.66, 0.52, 0.34), (0.42, 0.10, 0.03), (0.16, 0.06, 0.03), (0.58, 0.27, 0.11)
rtc = N.new("ShaderNodeTexCoord")
rsep = N.new("ShaderNodeSeparateXYZ")
L.new(rtc.outputs["Object"], rsep.inputs[0])
def absdiv(sock, d):
    a_ = N.new("ShaderNodeMath"); a_.operation = 'ABSOLUTE'
    L.new(sock, a_.inputs[0])
    q = N.new("ShaderNodeMath"); q.operation = 'DIVIDE'; q.inputs[1].default_value = d
    L.new(a_.outputs[0], q.inputs[0])
    return q.outputs[0]
mx = N.new("ShaderNodeMath"); mx.operation = 'MAXIMUM'
L.new(absdiv(rsep.outputs[0], 1.5), mx.inputs[0])
L.new(absdiv(rsep.outputs[1], 1.3), mx.inputs[1])
border = ramp(N, [(0.0, CREAM), (0.80, BROWN), (0.83, RUST), (0.875, CREAM), (0.895, RUST), (0.95, PALE)])
L.new(mx.outputs[0], border.inputs[0])
rwarp = N.new("ShaderNodeTexNoise")
rwarp.inputs["Scale"].default_value = 3.0
L.new(rtc.outputs["Object"], rwarp.inputs["Vector"])
radd = N.new("ShaderNodeVectorMath"); radd.operation = 'MULTIPLY_ADD'
L.new(rwarp.outputs["Color"], radd.inputs[0])
radd.inputs[1].default_value = (0.06, 0.06, 0.06)
L.new(rtc.outputs["Object"], radd.inputs[2])
rvo = N.new("ShaderNodeTexVoronoi")
rvo.inputs["Scale"].default_value = 4.0
L.new(radd.outputs[0], rvo.inputs["Vector"])
field = ramp(N, [(0.0, RUST), (0.09, CREAM), (0.15, BROWN), (0.2, CREAM), (0.33, PALE), (0.45, CREAM), (0.6, RUST)])
L.new(rvo.outputs["Distance"], field.inputs[0])
inb = N.new("ShaderNodeMath"); inb.operation = 'GREATER_THAN'; inb.inputs[1].default_value = 0.78
L.new(mx.outputs[0], inb.inputs[0])
pick = N.new("ShaderNodeMix"); pick.data_type = 'RGBA'
L.new(inb.outputs[0], pick.inputs["Factor"])
L.new(field.outputs["Color"], pick.inputs[6])
L.new(border.outputs["Color"], pick.inputs[7])
wear = N.new("ShaderNodeTexNoise")                       # worn, faded patches
wear.inputs["Scale"].default_value = 6.0
wear.inputs["Detail"].default_value = 8.0
L.new(rtc.outputs["Object"], wear.inputs["Vector"])
wr = N.new("ShaderNodeMapRange")
wr.inputs["From Min"].default_value, wr.inputs["From Max"].default_value = 0.45, 0.75
wr.inputs["To Min"].default_value, wr.inputs["To Max"].default_value = 0.0, 0.45
L.new(wear.outputs["Fac"], wr.inputs["Value"])
fade = N.new("ShaderNodeMix"); fade.data_type = 'RGBA'
L.new(wr.outputs[0], fade.inputs["Factor"])
L.new(pick.outputs[2], fade.inputs[6])
fade.inputs[7].default_value = (*CREAM, 1)
rb = N.new("ShaderNodeBsdfPrincipled")
rb.inputs["Roughness"].default_value = 0.95
rb.inputs["Sheen Weight"].default_value = 0.4
L.new(fade.outputs[2], rb.inputs["Base Color"])
pile = N.new("ShaderNodeTexNoise")
pile.inputs["Scale"].default_value = 600.0
L.new(rtc.outputs["Object"], pile.inputs["Vector"])
rbump = N.new("ShaderNodeBump")
rbump.inputs["Strength"].default_value = 0.3
rbump.inputs["Distance"].default_value = 0.001
L.new(pile.outputs["Fac"], rbump.inputs["Height"])
L.new(rbump.outputs[0], rb.inputs["Normal"])
L.new(rb.outputs[0], N.new("ShaderNodeOutputMaterial").inputs["Surface"])

jute = grain_material("Linen rug", "Fabric081C", 0.9, rough_mul=1.25, sheen=0.35, normal_strength=3.0)   # coarse chunky weave
# chunky hand-loomed knit on top of the linen texture (reference photo): rows of small loops as a
# bump, plus a slight heathered colour variation
_N, _L = jute.node_tree.nodes, jute.node_tree.links
_bs = next(n for n in _N if n.type == 'BSDF_PRINCIPLED')
_nm = next(n for n in _N if n.type == 'NORMAL_MAP')
_tc = _N.new("ShaderNodeTexCoord")
_mp = _N.new("ShaderNodeMapping")
_mp.inputs["Scale"].default_value = (45.0, 70.0, 45.0)           # ~22 x 14 mm chunky loops (reads at room distance)
_L.new(_tc.outputs["Object"], _mp.inputs[0])
_vo = _N.new("ShaderNodeTexVoronoi")
_L.new(_mp.outputs[0], _vo.inputs["Vector"])
_bp = _N.new("ShaderNodeBump")
_bp.inputs["Strength"].default_value = 1.0
_bp.inputs["Distance"].default_value = 0.008
_L.new(_vo.outputs["Distance"], _bp.inputs["Height"])
_L.new(_nm.outputs[0], _bp.inputs["Normal"])
_L.new(_bp.outputs[0], _bs.inputs["Normal"])
_hz = _N.new("ShaderNodeTexNoise")
_hz.inputs["Scale"].default_value = 60.0
_L.new(_tc.outputs["Object"], _hz.inputs["Vector"])
_mr = _N.new("ShaderNodeMapRange")
_mr.inputs["From Max"].default_value = 0.7
_mr.inputs["To Min"].default_value, _mr.inputs["To Max"].default_value = 1.12, 0.72
_L.new(_vo.outputs["Distance"], _mr.inputs["Value"])                # loops lighter on top, darker in the gaps
_vm = _N.new("ShaderNodeVectorMath"); _vm.operation = 'SCALE'
_src = _bs.inputs["Base Color"].links[0].from_socket
_L.new(_src, _vm.inputs[0]); _L.new(_mr.outputs[0], _vm.inputs[3])
_L.new(_vm.outputs[0], _bs.inputs["Base Color"])
cane, N, L = fresh("Cane webbing")               # woven rattan cane: crossed strands with open octagonal holes
_tc = N.new("ShaderNodeTexCoord")
_w = []
for ang in (0.0, 1.5708, 0.7854, -0.7854):
    mp_ = N.new("ShaderNodeMapping"); mp_.inputs["Rotation"].default_value = (ang, 0, 0) if False else (0, ang, 0)
    L.new(_tc.outputs["Object"], mp_.inputs[0])
    wv = N.new("ShaderNodeTexWave"); wv.wave_profile = 'SIN'; wv.inputs["Scale"].default_value = 70.0
    L.new(mp_.outputs[0], wv.inputs["Vector"])
    _w.append(wv.outputs["Fac"])
mx_ = N.new("ShaderNodeMath"); mx_.operation = 'MAXIMUM'; L.new(_w[0], mx_.inputs[0]); L.new(_w[1], mx_.inputs[1])
mx2 = N.new("ShaderNodeMath"); mx2.operation = 'MAXIMUM'; L.new(_w[2], mx2.inputs[0]); L.new(_w[3], mx2.inputs[1])
mx3 = N.new("ShaderNodeMath"); mx3.operation = 'MAXIMUM'; L.new(mx_.outputs[0], mx3.inputs[0]); L.new(mx2.outputs[0], mx3.inputs[1])
th = N.new("ShaderNodeMath"); th.operation = 'GREATER_THAN'; th.inputs[1].default_value = 0.72
L.new(mx3.outputs[0], th.inputs[0])
cb_ = N.new("ShaderNodeBsdfPrincipled")
cb_.inputs["Base Color"].default_value = (0.62, 0.42, 0.20, 1)
cb_.inputs["Roughness"].default_value = 0.45
cbump = N.new("ShaderNodeBump"); cbump.inputs["Strength"].default_value = 0.5
L.new(mx3.outputs[0], cbump.inputs["Height"]); L.new(cbump.outputs[0], cb_.inputs["Normal"])
cmix = N.new("ShaderNodeMixShader")
L.new(th.outputs[0], cmix.inputs[0])
L.new(N.new("ShaderNodeBsdfTransparent").outputs[0], cmix.inputs[1])
L.new(cb_.outputs[0], cmix.inputs[2])
L.new(cmix.outputs[0], N.new("ShaderNodeOutputMaterial").inputs["Surface"])
boucle = grain_material("Boucle", "Fabric081C", 3.0, rough_mul=1.3, sheen=0.8, normal_strength=2.5)   # nubby upholstery
charred, N, L = fresh("Charred wood")            # shou-sugi-ban log: black, growth rings and soft sheen
_tc = N.new("ShaderNodeTexCoord")
_rg = N.new("ShaderNodeTexWave")
_rg.wave_type, _rg.rings_direction = 'RINGS', 'Z'
_rg.inputs["Scale"].default_value = 40.0
_rg.inputs["Distortion"].default_value = 1.2
_rg.inputs["Detail"].default_value = 3.0
L.new(_tc.outputs["Object"], _rg.inputs["Vector"])
_cb = N.new("ShaderNodeBsdfPrincipled")
_cr = N.new("ShaderNodeMapRange")
_cr.inputs["To Min"].default_value, _cr.inputs["To Max"].default_value = 0.006, 0.022
L.new(_rg.outputs["Fac"], _cr.inputs["Value"])
_cc = N.new("ShaderNodeCombineColor")
for i_ in range(3):
    L.new(_cr.outputs[0], _cc.inputs[i_])
L.new(_cc.outputs[0], _cb.inputs["Base Color"])
_cb.inputs["Roughness"].default_value = 0.9           # matte char: no blue sky sheen (user: pure black)
_cb.inputs["Specular IOR Level"].default_value = 0.25
_cbp = N.new("ShaderNodeBump")
_cbp.inputs["Strength"].default_value = 0.35
_cbp.inputs["Distance"].default_value = 0.002
L.new(_rg.outputs["Fac"], _cbp.inputs["Height"])
L.new(_cbp.outputs[0], _cb.inputs["Normal"])
L.new(_cb.outputs[0], N.new("ShaderNodeOutputMaterial").inputs["Surface"])
cotton = grain_material("Cotton bedding", "Fabric081C", 9.0, rough_mul=1.5, sheen=1.0, normal_strength=0.35)   # soft washed cotton/linen bedding (user: pillows and duvet read as plastic)
_N, _L = cotton.node_tree.nodes, cotton.node_tree.links
_bs = next(n for n in _N if n.type == 'BSDF_PRINCIPLED')
_bs.inputs["Sheen Roughness"].default_value = 0.6
_bs.inputs["Subsurface Weight"].default_value = 0.15
_bs.inputs["Subsurface Radius"].default_value = (0.02, 0.02, 0.02)
_bs.inputs["Specular IOR Level"].default_value = 0.2
_nm = next(n for n in _N if n.type == 'NORMAL_MAP')
_tc = _N.new("ShaderNodeTexCoord")
_wz = _N.new("ShaderNodeTexNoise"); _wz.inputs["Scale"].default_value = 30.0; _wz.inputs["Detail"].default_value = 8.0; _wz.inputs["Distortion"].default_value = 2.0
_L.new(_tc.outputs["Object"], _wz.inputs["Vector"])
_bp = _N.new("ShaderNodeBump"); _bp.inputs["Strength"].default_value = 0.35; _bp.inputs["Distance"].default_value = 0.004
_L.new(_wz.outputs["Fac"], _bp.inputs["Height"]); _L.new(_nm.outputs[0], _bp.inputs["Normal"]); _L.new(_bp.outputs[0], _bs.inputs["Normal"])
velvet, N, L = fresh("Velvet")                    # soft brushed velvet: strong sheen at grazing angles, matte face
_vc = obj_colour(N, L)
_vb = N.new("ShaderNodeBsdfPrincipled")
L.new(_vc, _vb.inputs["Base Color"])
_vb.inputs["Roughness"].default_value = 0.85
_vb.inputs["Specular IOR Level"].default_value = 0.15
_vb.inputs["Sheen Weight"].default_value = 1.0
_vb.inputs["Sheen Roughness"].default_value = 0.35
L.new(_vc, _vb.inputs["Sheen Tint"])
_vt = N.new("ShaderNodeTexCoord"); _vn = N.new("ShaderNodeTexNoise"); _vn.inputs["Scale"].default_value = 60.0; _vn.inputs["Detail"].default_value = 6.0
L.new(_vt.outputs["Object"], _vn.inputs["Vector"])
_vbp = N.new("ShaderNodeBump"); _vbp.inputs["Strength"].default_value = 0.15
L.new(_vn.outputs["Fac"], _vbp.inputs["Height"]); L.new(_vbp.outputs[0], _vb.inputs["Normal"])
L.new(_vb.outputs[0], N.new("ShaderNodeOutputMaterial").inputs["Surface"])
cherry = grain_material("Wood cherry", "Wood030", 1.3, rough_mul=0.75)          # kitchen veneer (10-20 refit)
worktop = grain_material("Travertine worktop", "Travertine009", 0.8, rough_mul=0.7, normal_strength=0.4)

WOOD_KEYS = {"board", "cab", "chair", "table", "worktop", "bed_wood", "mantel", "trunk", "jar_lid", "wood",
             "fence", "fence_end", "log", "log_end", "bamboo", "wicker"}
WOOD_NAMES = ("Posts", "Exterior floor bands", "Wall boards", "Wall core", "Floor", "Subfloor", "Window frames",
              "Purlins", "Rafters", "Roof sheathing", "Tile battens", "Verge boards")
FABRIC_KEYS = {"linen", "rug", "rug_band", "cushion_o", "cushion_red", "dot", "fabric_green", "fabric_green_dk",
               "plaid", "plaid_line", "throw_blue", "throw_line", "duvet", "duvet_band", "pillow", "sheet",
               "lamp_shade", "shade", "arm_tan", "arm_tan_dk"}
GLAZE_KEYS = {"ceramic", "crock", "tile", "enamel"}
IRON_KEYS = {"iron", "hoop", "trunk_metal"}
BRIGHT_KEYS = {"chrome", "alu", "brass", "copper"}
STONE_KEYS = {"stone_a", "stone_b", "stone_c"}
MATTE_KEYS = {"grout", "soil", "cork", "strap", "soot", "paper"}


def house_material(n):
    k = n.split(" - ")[-1]
    if k in ("duvet", "duvet_band", "pillow", "sheet"):
        return cotton
    if k == "velvet":
        return velvet
    if k == "cushion_cream":
        return boucle
    if k == "lamp_cream":
        return gauze
    if k == "cushion_grey":
        return cotton
    if k == "rocker_wood":
        return wood
    if k in ("cab_cherry", "shelf_dark", "walnut"):
        return cherry
    if k.startswith("leather"):
        return leather
    if k in ("navy", "black_lacq"):
        return satin
    if k == "rug_vintage":
        return rugm
    if k == "jute":
        return jute
    if k == "rock_wood":
        return cherry
    if k == "cane":
        return cane
    if k == "brass_lamp":
        return bright
    if k in ("cushion_navy", "cushion_rust"):
        return boucle
    if k == "charred":
        return charred
    if k == "crack":
        return matte
    if k == "blind":
        return wood
    if k in ("tape", "shade_green"):
        return fabric
    if k in ("accent_red", "accent_green", "marble", "glide"):
        return glaze
    if k == "worktop_stone":
        return worktop
    if k in ("tile_finger", "black_glass", "tap"):
        return glaze
    if k == "steel" or n.startswith("Hood vent"):
        return brushed
    if k == "gauze":
        return gauze
    if k == "gauze":
        return fabric
    if k in ("knife_handle", "basket"):
        return wood
    if k == "glass":
        return glass
    if k in WOOD_KEYS or n.startswith(WOOD_NAMES):
        return wood
    if k in FABRIC_KEYS:
        return fabric
    if n.startswith(("Roof tiles", "Ridge caps")):
        return clay
    if k == "terracotta":
        return terracotta
    if k in GLAZE_KEYS:
        return glaze
    if k in IRON_KEYS or n.startswith(("Bolt heads", "Flue wall brackets")):
        return iron
    if k in BRIGHT_KEYS or n.startswith(("Hood vent", "Chimney flashing")):
        return bright
    if k in STONE_KEYS or n.startswith("Chimney flue body"):
        return stone
    if k in MATTE_KEYS:
        return matte
    return None                                    # leaves, books, fruit ... keep the plain colour material


def assign(o, m):
    o.data.materials.clear()
    o.data.materials.append(m)

for o in bpy.data.objects:
    if o.type != 'MESH':
        continue
    n = o.name
    if o.modifiers.get("Scatter") or o.modifiers.get("Twigs") or n.startswith(("Twig ", "Tree source", "G ", "PH ", "Char ")):
        continue                                   # trees and scatter carry their own materials
    if n.startswith(("Mountains mtn_snow", "Mountains mtn_rock", "Front range mtn_snow", "Front range mtn_rock")):
        assign(o, mtn)
    elif n.endswith(("mtn_forest", " hill")):
        assign(o, forest_floor)
    elif n.endswith("hill_rock") or n.startswith(("Boulder", "Lake rock")):
        assign(o, rock)
    elif n.startswith(("Front steps", "Flagstone path", "Plinth", "Chimney stones", "Chimney cap")) or \
            (n.startswith("Lake shore stones") and not n.endswith("reed")):
        assign(o, stone)                           # dressed and natural stone around the house
    elif n == "Floor 1 limestone":
        assign(o, limestone)
    elif n == "Interior pearl white walls":
        assign(o, pearl)
    elif n in ("Ground", "Lake bank"):
        assign(o, ground)
    elif n == "Lake":
        assign(o, water)
    elif n.endswith(" - black_glass"):
        assign(o, black_glass)
    elif o.data.materials and o.data.materials[0] == painted and o.users_collection[0].name[:2] in \
            ("11", "12", "13", "14", "15", "17", "21", "22", "23", "31", "32"):
        hm = house_material(n)
        if hm:
            if hm in (wood, fabric, cherry, worktop, jute, boucle, cotton):
                grain_uv(o)
            assign(o, hm)

# ------------------------------------------------------------------ sky, sun, render
# world (HDRI sky) and sun lamp: see lighting.py, applied at the end as the "noon" baseline

sc.render.engine = 'CYCLES'
try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'METAL'
    prefs.get_devices()
    for d in prefs.devices:
        d.use = True
    sc.cycles.device = 'GPU'
except Exception as e:
    print("GPU not available:", e)
sc.cycles.samples = 128
sc.cycles.use_denoising = True
sc.cycles.max_bounces = 12
sc.cycles.transparent_max_bounces = 16
sc.cycles.diffuse_bounces = 8                    # daylight reaches the back of the rooms by bouncing
sc.view_settings.view_transform = 'AgX'
# 10-20: softer base contrast so sunlit interiors read bright and open (user: the house faces south)
sc.view_settings.look = 'AgX - Base Contrast' if 'AgX - Base Contrast' in [
    l.identifier for l in sc.view_settings.bl_rna.properties['look'].enum_items] else 'None'

# aerial perspective from the mist pass
vl = sc.view_layers[0]
vl.use_pass_mist = True
sc.world.mist_settings.start = 120.0
sc.world.mist_settings.depth = 1600.0
sc.world.mist_settings.falloff = 'LINEAR'
cg = bpy.data.node_groups.get("Aerial perspective") or bpy.data.node_groups.new("Aerial perspective", "CompositorNodeTree")
cg.nodes.clear()
if not cg.interface.items_tree:
    cg.interface.new_socket("Image", in_out='OUTPUT', socket_type='NodeSocketColor')
rl = cg.nodes.new("CompositorNodeRLayers")
haze = cg.nodes.new("ShaderNodeMix")
haze.name = "Haze"                                   # lighting.py sets its colour per time of day
haze.data_type = 'RGBA'
haze.inputs[7].default_value = (0.6, 0.68, 0.78, 1)
amt = cg.nodes.new("ShaderNodeMath")
amt.operation = 'MULTIPLY'
amt.inputs[1].default_value = 0.3
# haze terrain only: the sky (depth ~1e10) keeps the HDRI's own colour
near = cg.nodes.new("ShaderNodeMath")
near.operation = 'LESS_THAN'
near.inputs[1].default_value = 1.0e5
cg.links.new(rl.outputs["Depth"], near.inputs[0])
amt2 = cg.nodes.new("ShaderNodeMath")
amt2.operation = 'MULTIPLY'
cg.links.new(rl.outputs["Mist"], amt.inputs[0])
cg.links.new(amt.outputs[0], amt2.inputs[0])
cg.links.new(near.outputs[0], amt2.inputs[1])
cg.links.new(amt2.outputs[0], haze.inputs["Factor"])
cg.links.new(rl.outputs["Image"], haze.inputs[6])
# 10-20 (user: dark interior vs. blown sun patches): gamma 0.8 on scene-linear values lifts the
# shadows and rolls off the highlights - softer contrast, like a photographer's shadow lift
soft = cg.nodes.new("ShaderNodeGamma")
soft.name = "Soft contrast"
soft.inputs[1].default_value = 0.8
cg.links.new(haze.outputs[2], soft.inputs[0])
go = cg.nodes.new("NodeGroupOutput")
cg.links.new(soft.outputs[0], go.inputs[0])
sc.compositing_node_group = cg
sc.render.use_freestyle = False

import lighting                                       # noqa: E402
lighting.apply(sc, "noon")

bpy.ops.wm.save_mainfile()
print("REAL_MATERIALS_SAVED")
