"""Realistic garden pieces (2026-10-20): granite boulders, terracotta pots and real plants.

Every object made here is named "G ..." and carries its own physically based material, so the
older material passes leave it alone. Plants are built leaf by leaf (geometry, not cards).

  rock(...)          weathered granite: flat fracture faces, rounded edges, sunk into the ground
  pot(...)           terracotta pot with rolled rim and foot, soil surface
  geranium(...)      pelargonium: scalloped, cupped leaves on petioles + umbels of red flowers
  lavender(...)      grey-green leafy base, many stems with purple flower spikes
  boxwood(...)       clipped evergreen mound: twiggy frame + thousands of small glossy leaves
  grass_clump(...)   arching ornamental grass
  fern(...)          crown of pinnate fronds
"""
import bpy, math, random, os
from mathutils import Vector, Matrix, noise
from meshkit import Mesh

TEX = None


def _mat(name, build):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    L.new(build(N, L), out.inputs["Surface"])
    return m


def leaf_mat(name, rgb, trans=0.3, rough=0.45):
    def b(N, L):
        oi = N.new("ShaderNodeObjectInfo")
        hs = N.new("ShaderNodeHueSaturation")
        hs.inputs["Color"].default_value = (*rgb, 1)
        mr = N.new("ShaderNodeMapRange")
        mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 0.85, 1.15
        L.new(oi.outputs["Random"], mr.inputs["Value"])
        L.new(mr.outputs[0], hs.inputs["Value"])
        bs = N.new("ShaderNodeBsdfPrincipled")
        L.new(hs.outputs[0], bs.inputs["Base Color"])
        bs.inputs["Roughness"].default_value = rough
        tr = N.new("ShaderNodeBsdfTranslucent")
        L.new(hs.outputs[0], tr.inputs["Color"])
        mx = N.new("ShaderNodeMixShader")
        mx.inputs["Fac"].default_value = trans
        L.new(bs.outputs[0], mx.inputs[1])
        L.new(tr.outputs[0], mx.inputs[2])
        return mx.outputs[0]
    return _mat(name, b)


def plain_mat(name, rgb, rough=0.6, sss=0.0):
    def b(N, L):
        bs = N.new("ShaderNodeBsdfPrincipled")
        bs.inputs["Base Color"].default_value = (*rgb, 1)
        bs.inputs["Roughness"].default_value = rough
        if sss:
            bs.inputs["Subsurface Weight"].default_value = sss
        return bs.outputs[0]
    return _mat(name, b)


def terracotta_mat():
    def b(N, L):
        tc = N.new("ShaderNodeTexCoord")
        nz = N.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 18.0
        nz.inputs["Detail"].default_value = 6.0
        L.new(tc.outputs["Object"], nz.inputs["Vector"])
        cr = N.new("ShaderNodeValToRGB")
        cr.color_ramp.elements[0].color = (0.33, 0.11, 0.05, 1)
        cr.color_ramp.elements[1].color = (0.52, 0.2, 0.09, 1)
        L.new(nz.outputs["Fac"], cr.inputs[0])
        sep = N.new("ShaderNodeSeparateXYZ")                     # weathering: paler, chalky low down
        L.new(tc.outputs["Object"], sep.inputs[0])
        wr = N.new("ShaderNodeMapRange")
        wr.inputs["From Min"].default_value, wr.inputs["From Max"].default_value = 0.12, 0.0
        L.new(sep.outputs["Z"], wr.inputs["Value"])
        mx = N.new("ShaderNodeMix")
        mx.data_type = 'RGBA'
        L.new(wr.outputs[0], mx.inputs["Factor"])
        L.new(cr.outputs[0], mx.inputs[6])
        mx.inputs[7].default_value = (0.45, 0.33, 0.25, 1)
        bs = N.new("ShaderNodeBsdfPrincipled")
        L.new(mx.outputs[2], bs.inputs["Base Color"])
        bs.inputs["Roughness"].default_value = 0.85
        bump = N.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.15
        L.new(nz.outputs["Fac"], bump.inputs["Height"])
        L.new(bump.outputs[0], bs.inputs["Normal"])
        return bs.outputs[0]
    return _mat("G terracotta", b)


def textured_mat(name, folder, scale, tint):
    def b(N, L):
        tc, mp = N.new("ShaderNodeTexCoord"), N.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (scale, scale, scale)
        L.new(tc.outputs["Object"], mp.inputs[0])
        def img(kind, cs):
            im = N.new("ShaderNodeTexImage")
            im.image = bpy.data.images.load(os.path.join(TEX, folder, f"{folder}_2K-JPG_{kind}.jpg"), check_existing=True)
            im.image.colorspace_settings.name = cs
            im.projection, im.projection_blend = 'BOX', 0.3
            L.new(mp.outputs[0], im.inputs[0])
            return im
        t = N.new("ShaderNodeMix")
        t.data_type, t.blend_type = 'RGBA', 'MULTIPLY'
        t.inputs["Factor"].default_value = 1.0
        t.inputs[7].default_value = (*tint, 1)
        L.new(img("Color", "sRGB").outputs[0], t.inputs[6])
        bs = N.new("ShaderNodeBsdfPrincipled")
        L.new(t.outputs[2], bs.inputs["Base Color"])
        L.new(img("Roughness", "Non-Color").outputs[0], bs.inputs["Roughness"])
        nm = N.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = 1.4
        L.new(img("NormalGL", "Non-Color").outputs[0], nm.inputs["Color"])
        L.new(nm.outputs[0], bs.inputs["Normal"])
        return bs.outputs[0]
    return _mat(name, b)


def _obj(name, mesh, coll, mats, loc=(0, 0, 0), rz=0.0, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata(mesh.v, [], mesh.f)
    me.validate()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    for m in mats:
        me.materials.append(m)
    o.location, o.rotation_euler = loc, (0, 0, rz)
    return o


def _multi(name, parts, coll, loc=(0, 0, 0), rz=0.0):
    """parts: [(Mesh, material)] -> one object with one material slot per part."""
    me_all = Mesh()
    idx = []
    for k, (m, _) in enumerate(parts):
        off = len(me_all.v)
        me_all.v += m.v
        me_all.f += [[i + off for i in f] for f in m.f]
        idx += [k] * len(m.f)
    o = _obj(name, me_all, coll, [mat for _, mat in parts], loc, rz)
    o.data.polygons.foreach_set("material_index", idx)
    return o


# ------------------------------------------------------------------ leaf geometry
def leaf(m, base, d, up, L, W, n=7, cup=0.25, scallop=0.0, round_tip=False):
    """Leaf blade from base along d; up = leaf normal side. Fan of triangles around a midrib."""
    d = Vector(d).normalized()
    up = Vector(up)
    side = d.cross(up).normalized()
    up = side.cross(d).normalized()
    i0 = len(m.v)
    m.v.append(tuple(base + d * (L * 0.35) + up * (L * cup * 0.15)))
    outline = []
    steps = 2 * n
    for k in range(steps + 1):
        a = 2 * math.pi * k / steps
        x = 0.5 - 0.5 * math.cos(a)                 # 0 at base, 1 at tip
        y = math.sin(a)
        w = W * (math.sin(math.pi * x) ** (0.6 if round_tip else 0.9))
        if scallop:
            w *= 1 + scallop * math.cos(10 * a)
        bend = -0.12 * L * x * x                   # tip droops
        c = base + d * (L * x) + side * (y * w * 0.5) + up * (bend + cup * W * 0.5 * y * y)
        outline.append(c)
    m.v += [tuple(p) for p in outline]
    for k in range(steps):
        m.f.append([i0, i0 + 1 + k, i0 + 2 + k])


def round_leaf(m, c, up, R, scallop=0.08, cup=0.25, n=14):
    """Kidney/round leaf (geranium): disc with scalloped rim, cupped."""
    up = Vector(up).normalized()
    a = up.orthogonal().normalized()
    b = up.cross(a)
    i0 = len(m.v)
    m.v.append(tuple(c))
    for k in range(n):
        t = 2 * math.pi * k / n
        r = R * (1 + scallop * math.cos(7 * t)) * (0.85 if abs(t - math.pi) < 0.3 else 1.0)
        p = c + (a * math.cos(t) + b * math.sin(t)) * r + up * (cup * R)
        m.v.append(tuple(p))
    for k in range(n):
        m.f.append([i0, i0 + 1 + k, i0 + 1 + (k + 1) % n])


# ------------------------------------------------------------------ rocks
def rock(name, coll, loc, size, seed, sink=0.3, rz=0.0, mat=None):
    """Weathered granite: an ellipsoid chipped by random fracture planes (flat faces), then slightly
    rounded and roughened; the bottom sinks below ground so the boulder sits in the soil."""
    import bmesh
    rr = random.Random(seed)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=5, radius=1.0)
    sx, sy, sz = size
    planes = []
    for k in range(rr.randint(7, 11)):
        n = Vector((rr.uniform(-1, 1), rr.uniform(-1, 1), rr.uniform(-0.3, 1))).normalized()
        planes.append((n, rr.uniform(0.62, 0.86)))
    off = Vector((seed * 1.3, seed * 0.7, seed * 2.1))
    for v in bm.verts:
        p = v.co.copy()
        p = p * (1 + 0.18 * noise.noise(p * 0.9 + off))
        for n, dd in planes:                         # fracture faces
            e = p.dot(n) - dd
            if e > 0:
                p -= n * e * 0.92
        p = p * (1 + 0.025 * noise.noise(p * 6 + off) + 0.01 * noise.noise(p * 18 + off))
        v.co = Vector((p.x * sx, p.y * sy, p.z * sz))
    for v in bm.verts:
        v.co.z += sz * (1 - sink) - sz              # bottom below ground
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    o.location, o.rotation_euler = loc, (0, 0, rz)
    if mat:
        me.materials.append(mat)
    return o


def pebbles(name, coll, center, radius, count, seed, mat):
    rr = random.Random(seed)
    m = Mesh()
    for k in range(count):
        a, r = rr.uniform(0, 2 * math.pi), radius * math.sqrt(rr.random())
        s = rr.uniform(0.025, 0.09)
        c = Vector((center[0] + r * math.cos(a), center[1] + r * math.sin(a), s * 0.15))
        m.ellipsoid(c, (s * rr.uniform(1, 1.5), s, s * 0.5), seg=8, rings=5, rot=Matrix.Rotation(rr.uniform(0, 6.3), 3, 'Z'))
    return _obj(name, m, coll, [mat])


# ------------------------------------------------------------------ pots
def pot(name, coll, loc, r, h, mat_pot, mat_soil):
    """Classic terracotta pot: tapered wall, rolled rim, foot ring; open top with soil."""
    m = Mesh()
    t = 0.022 * r / 0.2 + 0.01
    prof = [(0.0, 0.0), (r * 0.66, 0.0), (r * 0.68, 0.015), (r * 0.66, 0.03), (r * 0.9, h * 0.8),
            (r * 0.92, h * 0.8), (r * 1.0, h * 0.82), (r * 1.02, h * 0.9), (r * 1.0, h), (r * 1.0 - t, h),
            (r * 0.88 - t, h * 0.82), (r * 0.66 - t, 0.05), (0.0, 0.05)]
    m.lathe(prof, seg=48, closed=False)
    s = Mesh()
    s.lathe([(0, h * 0.86), (r * 0.9 - t, h * 0.86), (r * 0.9 - t, h * 0.87), (0, h * 0.875)], seg=48)
    return _multi(name, [(m, mat_pot), (s, mat_soil)], coll, loc), h * 0.87


# ------------------------------------------------------------------ plants
def geranium(name, coll, loc, scale, seed, mats):
    """mats: leaf, petal, stem."""
    rr = random.Random(seed)
    lf, pe, st = Mesh(), Mesh(), Mesh()
    S = scale
    for k in range(int(70 * S / 0.3) + 20):               # leaves on petioles forming a full mound
        a = rr.uniform(0, 2 * math.pi)
        rad = S * rr.uniform(0.1, 0.95)
        hgt = S * (0.35 + 0.45 * (1 - (rad / S) ** 2)) * rr.uniform(0.85, 1.1)
        tip = Vector((rad * math.cos(a), rad * math.sin(a), hgt))
        st.rod((0, 0, 0), tip, 0.004, seg=5, r2=0.003)
        up = (Vector((math.cos(a), math.sin(a), 0)) * 0.5 + Vector((0, 0, 1))).normalized()
        round_leaf(lf, tip, up, S * rr.uniform(0.13, 0.18), scallop=0.09, cup=0.22)
    for k in range(int(10 * S / 0.3) + 4):                # flower umbels held above the leaves
        a = rr.uniform(0, 2 * math.pi)
        rad = S * rr.uniform(0.0, 0.6)
        top = Vector((rad * math.cos(a), rad * math.sin(a), S * rr.uniform(0.95, 1.2)))
        st.rod((rad * 0.5 * math.cos(a), rad * 0.5 * math.sin(a), S * 0.5), top, 0.003, seg=5)
        for j in range(22):                                # individual 5-petal flowers on short pedicels
            d = Vector((rr.uniform(-1, 1), rr.uniform(-1, 1), rr.uniform(0.1, 1))).normalized()
            fc = top + d * S * 0.09
            st.rod(top, fc, 0.0012, seg=4)
            for p in range(5):
                t = 2 * math.pi * p / 5
                a_ = d.orthogonal().normalized()
                b_ = d.cross(a_)
                pd = (a_ * math.cos(t) + b_ * math.sin(t))
                R = Matrix((pd, d.cross(pd), d)).transposed()     # petal lies across the flower axis
                pe.ellipsoid(fc + pd * S * 0.03, (S * 0.032, S * 0.022, S * 0.004), seg=8, rings=3, rot=R)
    return _multi(name, [(lf, mats[0]), (pe, mats[1]), (st, mats[2])], coll, loc, rr.uniform(0, 6.3))


def lavender(name, coll, loc, scale, seed, mats):
    """mats: foliage, flower, stem."""
    rr = random.Random(seed)
    lf, fl, st = Mesh(), Mesh(), Mesh()
    S = scale
    for k in range(int(900 * S / 0.5)):                   # dense grey-green base mound: narrow leaves
        a = rr.uniform(0, 2 * math.pi)
        r = S * 0.4 * math.sqrt(rr.random())
        base = Vector((r * math.cos(a), r * math.sin(a), S * 0.32 * (1 - (r / (S * 0.4)) ** 2) * rr.uniform(0.3, 1.0)))
        d = Vector((math.cos(a) * 0.6, math.sin(a) * 0.6, 1)).normalized()
        leaf(lf, base, d, Vector((math.cos(a), math.sin(a), 0)), S * rr.uniform(0.08, 0.13), S * 0.016, n=3, cup=0.0)
    for k in range(int(70 * S / 0.5)):                    # flowering stems, splayed, with spikes
        a = rr.uniform(0, 2 * math.pi)
        r0 = S * 0.12 * rr.random()
        lean = rr.uniform(0.15, 0.55)
        L = S * rr.uniform(0.8, 1.1)
        b = Vector((r0 * math.cos(a), r0 * math.sin(a), S * 0.15))
        top = b + Vector((math.cos(a) * lean, math.sin(a) * lean, 1)).normalized() * L
        st.rod(b, top, 0.0015, seg=4)
        d = (top - b).normalized()
        for j in range(9):                                 # whorls of tiny flowers along the spike
            c = top - d * (S * 0.11 * j / 9)
            fl.ellipsoid(c, (S * 0.012, S * 0.012, S * 0.018), seg=6, rings=4)
    return _multi(name, [(lf, mats[0]), (fl, mats[1]), (st, mats[2])], coll, loc, rr.uniform(0, 6.3))


def boxwood(name, coll, loc, size, seed, mats):
    """mats: leaf, wood. A clipped mound: dense outer shell of small leaves over a dark twig core."""
    rr = random.Random(seed)
    lf, wd = Mesh(), Mesh()
    sx, sy, sz = size
    for k in range(18):                                    # visible twig frame inside
        a = rr.uniform(0, 2 * math.pi)
        tip = Vector((sx * 0.7 * math.cos(a), sy * 0.7 * math.sin(a), sz * rr.uniform(0.5, 1.4)))
        wd.rod((0, 0, 0), tip, 0.012, seg=5, r2=0.004)
    core = Mesh()
    core.ellipsoid((0, 0, sz * 0.75), (sx * 0.88, sy * 0.88, sz * 0.84), seg=20, rings=12)    # dark inner foliage mass
    for i, p in enumerate(core.v):
        q = Vector(p)
        core.v[i] = tuple(q * (1 + 0.05 * noise.noise(q * 5 + Vector((seed, 1, 2)))))
    n = int(22000 * sx * sy * sz / 0.06)
    for k in range(min(max(n, 4000), 26000)):
        u, v_ = rr.random(), rr.random()
        th, ph = 2 * math.pi * u, math.acos(1 - 1.8 * v_)
        d = Vector((math.sin(ph) * math.cos(th), math.sin(ph) * math.sin(th), math.cos(ph)))
        jit = 1 + 0.07 * noise.noise(d * 3 + Vector((seed, 0, 0))) + rr.uniform(-0.05, 0.02)
        c = Vector((d.x * sx * jit, d.y * sy * jit, sz * 0.75 + d.z * sz * jit))
        if c.z < 0.02:
            continue
        tang = d.orthogonal().normalized()
        tang.rotate(Matrix.Rotation(rr.uniform(0, 6.3), 3, d))
        leaf(lf, c - tang * 0.008, tang, d, rr.uniform(0.016, 0.024), 0.011, n=3, cup=0.1, round_tip=True)
    return _multi(name, [(lf, mats[0]), (wd, mats[1]), (core, mats[2] if len(mats) > 2 else mats[0])], coll, loc, rr.uniform(0, 6.3))


def grass_clump(name, coll, loc, scale, seed, mat):
    rr = random.Random(seed)
    m = Mesh()
    S = scale
    for k in range(int(160 * S / 0.6)):
        a = rr.uniform(0, 2 * math.pi)
        r0 = S * 0.08 * math.sqrt(rr.random())
        L = S * rr.uniform(0.6, 1.1)
        out = rr.uniform(0.25, 0.8)
        w = 0.006 * S / 0.6 + 0.002
        prev = None
        n = 7
        dirh = Vector((math.cos(a), math.sin(a), 0))
        side = Vector((-dirh.y, dirh.x, 0))
        i0 = len(m.v)
        for j in range(n + 1):
            t = j / n
            c = Vector((r0 * math.cos(a), r0 * math.sin(a), 0)) + dirh * (L * out * t * t) + Vector((0, 0, L * (t - 0.45 * out * t * t)))
            ww = w * (1 - t) + 0.0005
            m.v += [tuple(c - side * ww), tuple(c + side * ww)]
        for j in range(n):
            q = i0 + 2 * j
            m.f.append([q, q + 1, q + 3, q + 2])
    return _obj(name, m, coll, [mat], loc, rr.uniform(0, 6.3))


def fern(name, coll, loc, scale, seed, mat):
    rr = random.Random(seed)
    m = Mesh()
    S = scale
    for k in range(rr.randint(7, 11)):
        a = 2 * math.pi * k / 9 + rr.uniform(-0.2, 0.2)
        L = S * rr.uniform(0.75, 1.0)
        dirh = Vector((math.cos(a), math.sin(a), 0))
        pts = [Vector((0, 0, 0)) + dirh * (L * 0.75 * t) + Vector((0, 0, L * (0.7 * t - 0.55 * t * t))) for t in [j / 12 for j in range(13)]]
        m.rod(pts[0], pts[-1], 0.002, seg=4)
        side = Vector((-dirh.y, dirh.x, 0))
        for j in range(1, 12):
            t = j / 12
            p = pts[j]
            pl = L * 0.2 * math.sin(math.pi * min(1, 0.15 + t)) * (1 - 0.4 * t)
            for sgn in (-1, 1):
                d = (side * sgn + dirh * 0.35).normalized()
                leaf(m, p, d, Vector((0, 0, 1)), pl, pl * 0.28, n=4, cup=0.1)
    return _obj(name, m, coll, [mat], loc, rr.uniform(0, 6.3))


# ------------------------------------------------------------------ Chinese front court (2026-10-20)
def bamboo(name, coll, loc, radius, height, seed, mats, n=26):
    """Clump of Phyllostachys-style bamboo. mats: culm, leaf. Culms with nodes, leaning out slightly;
    leafy branch fans on the upper two thirds."""
    rr = random.Random(seed)
    cm, lf = Mesh(), Mesh()
    for k in range(n):
        a, r = rr.uniform(0, 2 * math.pi), radius * math.sqrt(rr.random())
        base = Vector((r * math.cos(a), r * math.sin(a), 0))
        H = height * rr.uniform(0.7, 1.05)
        lean = Vector((math.cos(a), math.sin(a), 0)) * rr.uniform(0.05, 0.18)
        top = base + (Vector((0, 0, 1)) + lean).normalized() * H
        rad = 0.012 + 0.012 * H / height
        nodes = 9
        prev = base
        for j in range(1, nodes + 1):
            t = j / nodes
            p = base + (top - base) * t + Vector((0, 0, 0)) - lean * H * 0.15 * t * t
            cm.rod(prev, p, rad * (1 - 0.5 * t), seg=8, r2=rad * (1 - 0.5 * t) * 0.97)
            cm.torus(tuple(p), rad * (1 - 0.5 * t) * 1.05, rad * 0.12, seg=10, rseg=4)   # node ring
            if t > 0.35:                                   # branch with a fan of slender leaves
                ba = rr.uniform(0, 2 * math.pi)
                bd = Vector((math.cos(ba), math.sin(ba), 0.35)).normalized()
                bl = 0.25 + 0.35 * (1 - t)
                bt = p + bd * bl
                cm.rod(p, bt, 0.003, seg=4)
                for q in range(7):
                    d = (bd + Vector((rr.uniform(-.6, .6), rr.uniform(-.6, .6), -0.5))).normalized()
                    leaf(lf, bt + bd * (-bl * q / 9), d, Vector((0, 0, 1)), rr.uniform(0.1, 0.16), 0.018, n=4, cup=0.05)
            prev = p
        for q in range(10):                                # leaf tuft at the tip
            d = (Vector((rr.uniform(-1, 1), rr.uniform(-1, 1), rr.uniform(-0.4, 0.6)))).normalized()
            leaf(lf, top, d, Vector((0, 0, 1)), rr.uniform(0.1, 0.16), 0.018, n=4, cup=0.05)
    return _multi(name, [(cm, mats[0]), (lf, mats[1])], coll, loc, rr.uniform(0, 6.3))


def broadleaf_tree(name, coll, loc, height, crown_r, seed, mats):
    """Small evergreen broadleaf (osmanthus): short trunk forking into 3-4 limbs, a rounded, slightly
    lumpy crown of thousands of elliptic leaves over a dark inner mass. mats: bark, leaf, core."""
    rr = random.Random(seed)
    bk, lf, core = Mesh(), Mesh(), Mesh()
    fork = Vector((0, 0, height * 0.35))
    bk.rod((0, 0, 0), fork, 0.07, seg=10, r2=0.055)
    cc = Vector((0, 0, height - crown_r * 0.95))
    for k in range(4):
        a = k * 1.57 + rr.uniform(-0.3, 0.3)
        tip = cc + Vector((math.cos(a) * crown_r * 0.5, math.sin(a) * crown_r * 0.5, rr.uniform(-0.2, 0.3) * crown_r))
        bk.rod(fork, tip, 0.045, seg=8, r2=0.015)
    core.ellipsoid(cc, (crown_r * 0.9, crown_r * 0.9, crown_r * 0.82), seg=20, rings=12)
    for i, p in enumerate(core.v):
        q = Vector(p) - cc
        core.v[i] = tuple(cc + q * (1 + 0.12 * noise.noise(q * 1.8 + Vector((seed, 0, 0)))))
    for k in range(9000):
        u, v_ = rr.random(), rr.random()
        th, ph = 2 * math.pi * u, math.acos(1 - 1.85 * v_)
        d = Vector((math.sin(ph) * math.cos(th), math.sin(ph) * math.sin(th), math.cos(ph) * 0.92))
        jit = 1 + 0.12 * noise.noise(d * 1.8 + Vector((seed, 0, 0))) + rr.uniform(-0.06, 0.04)
        c = cc + d * crown_r * jit
        tang = d.orthogonal().normalized()
        tang.rotate(Matrix.Rotation(rr.uniform(0, 6.3), 3, d))
        leaf(lf, c - tang * 0.02, (tang + d * 0.4).normalized(), d, rr.uniform(0.06, 0.09), 0.026, n=4, cup=0.12)
    return _multi(name, [(bk, mats[0]), (lf, mats[1]), (core, mats[2])], coll, loc, rr.uniform(0, 6.3))


def mondo_grass(name, coll, x0, x1, y0, y1, seed, mat, density=40):
    """Low dense ophiopogon ground cover: arching dark strap leaves in tufts."""
    rr = random.Random(seed)
    m = Mesh()
    n = int((x1 - x0) * (y1 - y0) * density)
    for k in range(n):
        c = Vector((rr.uniform(x0, x1), rr.uniform(y0, y1), 0))
        for j in range(9):
            a = rr.uniform(0, 2 * math.pi)
            L = rr.uniform(0.12, 0.22)
            d = Vector((math.cos(a), math.sin(a), 0))
            side = Vector((-d.y, d.x, 0)) * 0.0022
            i0 = len(m.v)
            for q in range(5):
                t = q / 4
                p = c + d * (L * 0.6 * t * t) + Vector((0, 0, L * (t - 0.55 * t * t)))
                m.v += [tuple(p - side), tuple(p + side)]
            for q in range(4):
                b = i0 + 2 * q
                m.f.append([b, b + 1, b + 3, b + 2])
    return _obj(name, m, coll, [mat])


def paving(name, coll, x0, x1, y0, y1, seed, mat, joint_mat, size=(0.6, 0.4)):
    """Running-bond rectangular bluestone slabs, slightly irregular, with a mossy joint bed."""
    rr = random.Random(seed)
    s, j = Mesh(), Mesh()
    j.box(x0, x1, y0, y1, -0.02, 0.008)
    y = y0
    row = 0
    while y < y1 - 0.05:
        h = size[1] * rr.uniform(0.85, 1.15)
        x = x0 - (size[0] * 0.5 if row % 2 else 0)
        while x < x1:
            w = size[0] * rr.uniform(0.8, 1.3)
            a, b = max(x, x0) + 0.008, min(x + w, x1) - 0.008
            c, d = y + 0.008, min(y + h, y1) - 0.008
            if b - a > 0.08 and d - c > 0.08:
                zt = 0.03 + rr.uniform(-0.004, 0.004)
                s.box(a, b, c, d, -0.03, zt)
            x += w
        y += h
        row += 1
    return _multi(name, [(s, mat), (j, joint_mat)], coll)


def water_basin(name, coll, loc, mats):
    """Round carved stone water basin on a low plinth. mats: stone, water."""
    st, wa = Mesh(), Mesh()
    st.lathe([(0, 0), (0.22, 0), (0.22, 0.12), (0.16, 0.14), (0.3, 0.16), (0.32, 0.48), (0.3, 0.52),
              (0.25, 0.52), (0.24, 0.24), (0, 0.22)], seg=40)
    wa.lathe([(0, 0.46), (0.25, 0.46)], seg=40)
    return _multi(name, [(st, mats[0]), (wa, mats[1])], coll, loc)


def stone_stool(name, coll, loc, mat):
    """Drum-shaped stone stool (石鼓凳)."""
    st = Mesh()
    st.lathe([(0, 0), (0.15, 0), (0.18, 0.06), (0.2, 0.22), (0.18, 0.38), (0.16, 0.42), (0, 0.42)], seg=36)
    return _obj(name, st, coll, [mat], loc)


# ------------------------------------------------------------------ moss garden after the user's reference (10-20)
def moss_mat():
    def b(N, L):
        tc = N.new("ShaderNodeTexCoord")
        nz = N.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 60.0
        nz.inputs["Detail"].default_value = 8.0
        L.new(tc.outputs["Object"], nz.inputs["Vector"])
        big = N.new("ShaderNodeTexNoise")
        big.inputs["Scale"].default_value = 2.5
        L.new(tc.outputs["Object"], big.inputs["Vector"])
        cr = N.new("ShaderNodeValToRGB")
        cr.color_ramp.elements[0].color = (0.025, 0.07, 0.008, 1)
        cr.color_ramp.elements[1].color = (0.17, 0.33, 0.02, 1)
        big.inputs["Scale"].default_value = 9.0
        big.inputs["Detail"].default_value = 6.0
        L.new(big.outputs["Fac"], cr.inputs[0])
        bs = N.new("ShaderNodeBsdfPrincipled")
        L.new(cr.outputs[0], bs.inputs["Base Color"])
        bs.inputs["Roughness"].default_value = 0.95
        bs.inputs["Sheen Weight"].default_value = 0.6
        bs.inputs["Sheen Tint"].default_value = (0.5, 0.8, 0.2, 1)
        bump = N.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 1.0
        bump.inputs["Distance"].default_value = 0.01
        L.new(nz.outputs["Fac"], bump.inputs["Height"])
        L.new(bump.outputs[0], bs.inputs["Normal"])
        return bs.outputs[0]
    return _mat("G moss", b)


def wood_mat(name="G timber", rgb=(0.32, 0.16, 0.07)):
    def b(N, L):
        tc = N.new("ShaderNodeTexCoord")
        mp = N.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (1.0, 18.0, 1.0)
        L.new(tc.outputs["Object"], mp.inputs[0])
        wv = N.new("ShaderNodeTexWave")
        wv.wave_type = 'RINGS'
        wv.inputs["Scale"].default_value = 3.0
        wv.inputs["Distortion"].default_value = 6.0
        wv.inputs["Detail"].default_value = 4.0
        L.new(mp.outputs[0], wv.inputs["Vector"])
        cr = N.new("ShaderNodeValToRGB")
        cr.color_ramp.elements[0].color = (rgb[0] * 0.65, rgb[1] * 0.6, rgb[2] * 0.6, 1)
        cr.color_ramp.elements[1].color = (*rgb, 1)
        L.new(wv.outputs["Fac"], cr.inputs[0])
        bs = N.new("ShaderNodeBsdfPrincipled")
        L.new(cr.outputs[0], bs.inputs["Base Color"])
        bs.inputs["Roughness"].default_value = 0.55
        bump = N.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.15
        L.new(wv.outputs["Fac"], bump.inputs["Height"])
        L.new(bump.outputs[0], bs.inputs["Normal"])
        return bs.outputs[0]
    return _mat(name, b)


def wooden_steps(name, coll, x0, x1, steps, mat):
    """steps: [(y_front, y_back, top_z)] -> open-tread timber steps: board treads on side stringers."""
    m = Mesh()
    for yf, yb, zt in steps:
        n = int((yb - yf) / 0.14)
        for k in range(n):                               # tread boards along x, 5 mm gaps
            a = yf + (yb - yf) * k / n + 0.003
            b = yf + (yb - yf) * (k + 1) / n - 0.003
            m.box(x0 - 0.03, x1 + 0.03, a, b, zt - 0.04, zt)
        m.box(x0, x1, yf, yf + 0.03, 0.0, zt - 0.04)          # riser board
    for yf, yb, zt in steps:                                 # hidden support under each tread
        for x in (x0, (x0 + x1) / 2 - 0.03, x1 - 0.06):
            m.box(x, x + 0.06, yf + 0.03, yb, 0.0, zt - 0.04)
    return _obj(name, m, coll, [mat], smooth=False)


SLABS = []      # footprints of the last slate path, for keeping moss to the joints


def slate_path(name, coll, x0, x1, y0, y1, seed, mat):
    """Long cleft slate slabs laid lengthwise in two or three staggered columns, wide joints."""
    rr = random.Random(seed)
    m = Mesh()
    ncol = 2
    cw = (x1 - x0) / ncol
    joints = []
    for c in range(ncol):
        y = y0 - rr.uniform(0, 0.4)
        while y < y1:
            L = rr.uniform(0.55, 1.15)
            ya, yb = max(y, y0) + 0.04, min(y + L, y1) - 0.04
            xa = x0 + c * cw + 0.04 + rr.uniform(-0.03, 0.03)
            xb = x0 + (c + 1) * cw - 0.04 + rr.uniform(-0.03, 0.03)
            if yb - ya > 0.2:
                pts = [(xa + rr.uniform(0, .04), ya + rr.uniform(0, .05)), (xb - rr.uniform(0, .04), ya + rr.uniform(0, .05)),
                       (xb - rr.uniform(0, .05), yb - rr.uniform(0, .05)), (xa + rr.uniform(0, .05), yb - rr.uniform(0, .05))]
                zt = 0.035 + rr.uniform(-0.006, 0.006)
                m.solid([(x, y_, -0.04) for x, y_ in pts], [(x, y_, zt) for x, y_ in pts])
                SLABS.append((min(p[0] for p in pts), max(p[0] for p in pts), min(p[1] for p in pts), max(p[1] for p in pts)))
            joints.append(y + L)
            y += L
    return _obj(name, m, coll, [mat], smooth=False)


def creeper(name, coll, x0, x1, y0, y1, seed, mats, density=260):
    """Creeping ground cover (dichondra / sedum-like): tiny round leaves in drifts, with a few
    small yellow flowers. mats: leaf, flower."""
    rr = random.Random(seed)
    lf, fl = Mesh(), Mesh()
    n = int((x1 - x0) * (y1 - y0) * density)
    for k in range(n):
        c = Vector((rr.uniform(x0, x1), rr.uniform(y0, y1), rr.uniform(0.01, 0.035)))
        up = Vector((rr.uniform(-.3, .3), rr.uniform(-.3, .3), 1)).normalized()
        round_leaf(lf, c, up, rr.uniform(0.008, 0.014), scallop=0.0, cup=0.2, n=8)
        if rr.random() < 0.03:
            fl.ellipsoid(c + Vector((0, 0, 0.012)), (0.005, 0.005, 0.002), seg=6, rings=3)
    return _multi(name, [(lf, mats[0]), (fl, mats[1])], coll)


def moss_bed(name, coll, outline, height, seed, mat):
    """Moss carpet: a gently mounded surface over a 2D outline (list of (x, y)), edges at ground."""
    rr = random.Random(seed)
    cx = sum(p[0] for p in outline) / len(outline)
    cy = sum(p[1] for p in outline) / len(outline)
    m = Mesh()
    rings = 7
    n = len(outline)
    for r in range(rings + 1):
        f = 1 - r / rings
        for (x, y) in outline:
            px, py = cx + (x - cx) * f, cy + (y - cy) * f
            hz = height * (1 - f ** 2) * (1 + 0.25 * noise.noise(Vector((px * 0.8, py * 0.8, seed)))) + 0.006
            m.v.append((px, py, hz))
    for r in range(rings):
        for k in range(n):
            a, b = r * n + k, r * n + (k + 1) % n
            m.f.append([a, b, b + n, a + n])
    return _obj(name, m, coll, [mat])


def scholar_rock(name, coll, loc, size, seed, mat, rz=0.0):
    """Upright grey landscape stone (景观石): many fracture planes and deep pitting."""
    rr = random.Random(seed)
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=5, radius=1.0)
    sx, sy, sz = size
    planes = [(Vector((rr.uniform(-1, 1), rr.uniform(-1, 1), rr.uniform(-0.4, 1))).normalized(), rr.uniform(0.5, 0.85))
              for _ in range(rr.randint(10, 15))]
    off = Vector((seed * 1.7, seed * 0.3, seed * 2.9))
    for v in bm.verts:
        p = v.co.copy()
        p = p * (1 + 0.25 * noise.noise(p * 1.1 + off))
        for n, dd in planes:
            e = p.dot(n) - dd
            if e > 0:
                p -= n * e * 0.95
        pit = noise.noise(p * 3.5 + off)
        p = p * (1 - 0.09 * max(0.0, pit) ** 1.5 * 3 + 0.02 * noise.noise(p * 12 + off))
        v.co = Vector((p.x * sx, p.y * sy, p.z * sz + sz * 0.75))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    o.location, o.rotation_euler = loc, (0, 0, rz)
    me.materials.append(mat)
    return o


def hosta(name, coll, loc, scale, seed, mats):
    """Heuchera / hosta clump: broad heart-shaped leaves on arching petioles. mats: leaf, stem."""
    rr = random.Random(seed)
    lf, st = Mesh(), Mesh()
    for k in range(int(22 * scale / 0.3) + 6):
        a = rr.uniform(0, 2 * math.pi)
        r = scale * rr.uniform(0.25, 0.85)
        tip = Vector((r * math.cos(a), r * math.sin(a), scale * rr.uniform(0.3, 0.6)))
        st.rod((0, 0, 0.02), tip, 0.004, seg=5)
        up = (Vector((math.cos(a), math.sin(a), 0)) * 0.6 + Vector((0, 0, 1))).normalized()
        round_leaf(lf, tip, up, scale * rr.uniform(0.18, 0.26), scallop=0.12, cup=0.3, n=16)
    return _multi(name, [(lf, mats[0]), (st, mats[1])], coll, loc, rr.uniform(0, 6.3))


def garden_light(name, coll, loc, mats):
    """Low black path light: post + conical hat + warm lamp underneath. mats: metal, glow."""
    mt, gl = Mesh(), Mesh()
    mt.lathe([(0, 0), (0.035, 0), (0.035, 0.02), (0.012, 0.03), (0.012, 0.42), (0, 0.42)], seg=16)
    mt.lathe([(0.0, 0.47), (0.13, 0.41), (0.125, 0.4), (0.0, 0.455)], seg=24, closed=True)
    gl.lathe([(0, 0.4), (0.03, 0.4), (0.03, 0.43), (0, 0.43)], seg=12)
    return _multi(name, [(mt, mats[0]), (gl, mats[1])], coll, loc)


def stone_bowl(name, coll, loc, seed, mats, r=0.42, h=0.34):
    """Hollowed granite boulder bowl with water, lily pads and water lettuce.
    mats: stone, water, pad, lettuce."""
    rr = random.Random(seed)
    st, wa, pd, wl = Mesh(), Mesh(), Mesh(), Mesh()
    prof = [(0.0, 0.0), (r * 0.6, 0.0), (r * 0.92, h * 0.25), (r, h * 0.6), (r * 0.94, h * 0.92), (r * 0.82, h),
            (r * 0.74, h * 0.97), (r * 0.7, h * 0.6), (r * 0.5, h * 0.35), (0.0, h * 0.3)]
    st.lathe(prof, seg=48)
    off = Vector((seed, 0.5, 1.2))
    for i, p in enumerate(st.v):
        q = Vector(p)
        n = noise.noise(Vector((q.x * 2.5, q.y * 2.5, q.z * 2.5)) + off)
        st.v[i] = (q.x * (1 + 0.12 * n), q.y * (1 + 0.08 * n), q.z)
    wz = h * 0.88
    wa.lathe([(0, wz), (r * 0.72, wz)], seg=48)
    for k in range(3):                                   # lily pads with the notch
        a, rad = rr.uniform(0, 6.3), rr.uniform(0.0, r * 0.35)
        c = Vector((rad * math.cos(a), rad * math.sin(a), wz + 0.003))
        R = rr.uniform(0.07, 0.1)
        i0 = len(pd.v)
        pd.v.append(tuple(c))
        n = 20
        nr = rr.uniform(0, 6.3)
        for j in range(n + 1):
            t = nr + 0.25 + (2 * math.pi - 0.5) * j / n
            pd.v.append(tuple(c + Vector((R * math.cos(t), R * math.sin(t), 0.002))))
        for j in range(n):
            pd.f.append([i0, i0 + 1 + j, i0 + 2 + j])
    for k in range(6):                                   # water lettuce rosettes
        a, rad = rr.uniform(0, 6.3), rr.uniform(r * 0.2, r * 0.6)
        c = Vector((rad * math.cos(a), rad * math.sin(a), wz))
        for j in range(8):
            t = 2 * math.pi * j / 8 + rr.uniform(-.2, .2)
            d = Vector((math.cos(t), math.sin(t), 0.6)).normalized()
            leaf(wl, c, d, Vector((0, 0, 1)), 0.04, 0.03, n=4, cup=0.3, round_tip=True)
    return _multi(name, [(st, mats[0]), (wa, mats[1]), (pd, mats[2]), (wl, mats[3])], coll, loc, rr.uniform(0, 6.3))


def stone_mat(name, rgb, scale=6.0, speckle=0.0, rough=0.8, bump=0.4):
    """Procedural natural stone without the moss of the Rock063 photo set: mottled base colour,
    optional granite speckle, fine bump."""
    def b(N, L):
        tc = N.new("ShaderNodeTexCoord")
        nz = N.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = scale
        nz.inputs["Detail"].default_value = 10.0
        nz.inputs["Roughness"].default_value = 0.6
        L.new(tc.outputs["Object"], nz.inputs["Vector"])
        cr = N.new("ShaderNodeValToRGB")
        cr.color_ramp.elements[0].color = (rgb[0] * 0.6, rgb[1] * 0.6, rgb[2] * 0.6, 1)
        cr.color_ramp.elements[1].color = (min(1, rgb[0] * 1.25), min(1, rgb[1] * 1.25), min(1, rgb[2] * 1.25), 1)
        L.new(nz.outputs["Fac"], cr.inputs[0])
        col = cr.outputs[0]
        if speckle:
            vr = N.new("ShaderNodeTexVoronoi")
            vr.inputs["Scale"].default_value = 260.0
            L.new(tc.outputs["Object"], vr.inputs["Vector"])
            mx = N.new("ShaderNodeMix")
            mx.data_type, mx.blend_type = 'RGBA', 'MULTIPLY'
            mr = N.new("ShaderNodeMapRange")
            mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 1 - speckle, 1.0
            L.new(vr.outputs["Distance"], mr.inputs["Value"])
            mx.inputs["Factor"].default_value = 1.0
            L.new(col, mx.inputs[6])
            cm = N.new("ShaderNodeCombineColor")
            L.new(mr.outputs[0], cm.inputs[0]); L.new(mr.outputs[0], cm.inputs[1]); L.new(mr.outputs[0], cm.inputs[2])
            L.new(cm.outputs[0], mx.inputs[7])
            col = mx.outputs[2]
        bs = N.new("ShaderNodeBsdfPrincipled")
        L.new(col, bs.inputs["Base Color"])
        bs.inputs["Roughness"].default_value = rough
        fine = N.new("ShaderNodeTexNoise")
        fine.inputs["Scale"].default_value = scale * 12
        fine.inputs["Detail"].default_value = 6.0
        L.new(tc.outputs["Object"], fine.inputs["Vector"])
        bp = N.new("ShaderNodeBump")
        bp.inputs["Strength"].default_value = bump
        L.new(fine.outputs["Fac"], bp.inputs["Height"])
        L.new(bp.outputs[0], bs.inputs["Normal"])
        return bs.outputs[0]
    return _mat(name, b)


def moss_tufts(name, coll, outline_obj, seed, mat, density=900):
    """Fuzzy moss: thousands of tiny tufts scattered over a moss bed's surface (faces of outline_obj)."""
    rr = random.Random(seed)
    me = outline_obj.data
    m = Mesh()
    for poly in me.polygons:
        cnt = int(poly.area * density)
        vs = [Vector(me.vertices[i].co) for i in poly.vertices]
        for k in range(cnt):
            a, b_ = rr.random(), rr.random()
            p = vs[0].lerp(vs[1], a).lerp(vs[3].lerp(vs[2], a), b_) if len(vs) == 4 else vs[0]
            p = p + Vector(outline_obj.location)
            for j in range(4):
                t = rr.uniform(0, 6.3)
                d = Vector((math.cos(t) * 0.5, math.sin(t) * 0.5, 1)).normalized()
                tip = p + d * rr.uniform(0.008, 0.016)
                s = d.orthogonal().normalized() * 0.0012
                i0 = len(m.v)
                m.v += [tuple(p - s), tuple(p + s), tuple(tip)]
                m.f.append([i0, i0 + 1, i0 + 2])
    return _obj(name, m, coll, [mat])


# ------------------------------------------------------------------ CC0 scanned models (Poly Haven), 10-20
MODELS = None   # set by the caller: folder holding <asset>/<asset>_2k.blend


def load_model(asset, names, coll):
    """Append objects from a Poly Haven .blend into `coll` (hidden source collection), with their
    materials; image paths are made absolute so they survive the append."""
    path = os.path.join(MODELS, asset, f"{asset}_2k.blend")
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = [n for n in names if n in src.objects]
    out = {}
    for o in dst.objects:
        coll.objects.link(o)
        o.location, o.rotation_euler = (0, 0, 0), (0, 0, 0)
        out[o.name] = o
    for im in bpy.data.images:
        if im.filepath and not os.path.isabs(bpy.path.abspath(im.filepath)) or (im.filepath and not os.path.exists(bpy.path.abspath(im.filepath))):
            cand = os.path.join(MODELS, asset, "textures", os.path.basename(im.filepath))
            if os.path.exists(cand):
                im.filepath = cand
    return out


def place(src, name, coll, loc, scale=1.0, rz=0.0):
    """Linked copy of a source model (shares mesh and materials)."""
    o = bpy.data.objects.new(name, src.data)
    coll.objects.link(o)
    o.location, o.rotation_euler, o.scale = loc, (0, 0, rz), (scale, scale, scale)
    return o


def moss_clump(strands, coll, seed, n=40, r=0.035):
    """Join many real moss strands into one small clump mesh (one source for scattering)."""
    rr = random.Random(seed)
    import bmesh
    bm = bmesh.new()
    uv_name = None
    for k in range(n):
        s = rr.choice(strands)
        tmp = s.data.copy()
        M = (Matrix.Translation((r * math.sqrt(rr.random()) * math.cos(a := rr.uniform(0, 6.3)),
                                 r * math.sqrt(rr.random()) * math.sin(a), 0.0))
             @ Matrix.Rotation(rr.uniform(0, 6.3), 4, 'Z') @ Matrix.Scale(rr.uniform(0.8, 1.3), 4))
        tmp.transform(M)
        bm.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
    me = bpy.data.meshes.new("Moss clump")
    bm.to_mesh(me)
    bm.free()
    mat = strands[0].data.materials[0]
    for n in mat.node_tree.nodes:                       # the scan's colour group: neutral hue, brighter
        if n.type == 'GROUP' and "Hue" in n.inputs:
            n.inputs["Hue"].default_value = 0.49
            n.inputs["Value"].default_value = 1.15
            n.inputs["Saturation"].default_value = 1.1
    me.materials.append(mat)
    o = bpy.data.objects.new("Moss clump", me)
    coll.objects.link(o)
    return o


def tree_ring(name, coll, center, radius, seed, mats, n=None):
    """Stone surround at a tree's foot (树池): a ring of rounded field stones, each slightly flattened
    and sunk, set close together; inside, a low mound of dark bark mulch. mats: stone, mulch."""
    rr = random.Random(seed)
    st, mu = Mesh(), Mesh()
    cx, cy = center
    n = int(2 * math.pi * radius / 0.2) if n is None else n
    for k in range(n):
        t = 2 * math.pi * k / n + rr.uniform(-0.05, 0.05)
        s = rr.uniform(0.1, 0.16)
        c = Vector((cx + radius * math.cos(t), cy + radius * math.sin(t), s * 0.35))
        i0 = len(st.v)
        st.ellipsoid(c, (s * rr.uniform(1.0, 1.25), s * 0.85, s * 0.7), seg=12, rings=8,
                     rot=Matrix.Rotation(t + math.pi / 2 + rr.uniform(-.2, .2), 3, 'Z'))
        off = Vector((seed + k, k * 0.37, 1.1))
        for i in range(i0, len(st.v)):                    # lumpy, not egg-smooth
            p = Vector(st.v[i])
            q = p - c
            n1 = noise.noise(q * 7 + off)
            # flat-ish fractured faces + lumps: clamp the radius on a few random planes
            q = q * (1 + 0.22 * n1)
            for pn in (Vector((0.6, 0.2, 0.8)), Vector((-0.5, 0.7, 0.4)), Vector((0.1, -0.8, 0.5))):
                e = q.normalized().dot(pn.normalized()) - 0.55
                if e > 0:
                    q = q * (1 - 0.35 * e)
            st.v[i] = tuple(c + q)
    rings = 6
    for r_ in range(rings + 1):                           # mulch mound
        f = 1 - r_ / rings
        for k in range(32):
            t = 2 * math.pi * k / 32
            mu.v.append((cx + (radius - 0.05) * f * math.cos(t), cy + (radius - 0.05) * f * math.sin(t),
                         0.015 + 0.05 * (1 - f ** 2)))
    for r_ in range(rings):
        for k in range(32):
            a, b = r_ * 32 + k, r_ * 32 + (k + 1) % 32
            mu.f.append([a, b, b + 32, a + 32])
    return _multi(name, [(st, mats[0]), (mu, mats[1])], coll)


def mask_under(ng, obj):
    """Drop scatter points that lie under obj (seen from above) before they are instanced: the lawn
    grows right up to and between the path slabs without blades poking through them (10-21)."""
    N, L = ng.nodes, ng.links
    iop = next(n for n in N if n.bl_idname == 'GeometryNodeInstanceOnPoints')
    src = iop.inputs['Points'].links[0].from_socket
    info = N.new('GeometryNodeObjectInfo')
    info.inputs['Object'].default_value = obj
    info.transform_space = 'RELATIVE'
    pos = N.new('GeometryNodeInputPosition')
    up = N.new('ShaderNodeVectorMath')
    up.operation = 'ADD'
    up.inputs[1].default_value = (0, 0, 1)
    L.new(pos.outputs[0], up.inputs[0])
    rc = N.new('GeometryNodeRaycast')
    rc.inputs['Ray Direction'].default_value = (0, 0, -1)
    rc.inputs['Ray Length'].default_value = 2.0
    L.new(info.outputs['Geometry'], rc.inputs['Target Geometry'])
    L.new(up.outputs[0], rc.inputs['Source Position'])
    dl = N.new('GeometryNodeDeleteGeometry')
    dl.domain = 'POINT'
    L.new(src, dl.inputs['Geometry'])
    L.new(rc.outputs['Is Hit'], dl.inputs['Selection'])
    L.new(dl.outputs['Geometry'], iop.inputs['Points'])
