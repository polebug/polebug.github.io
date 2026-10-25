"""Procedural conifers for a realistic forest (2026-10-20, after the user's photos IMG_6008/6013/6020).

Structure, as in the photos:
  trunk      straight, tapering, bark-textured; bare below the crown (lower branches self-pruned),
             with a few dead stubs
  whorls     primary branches in whorls up the stem: droop low in the crown, rise near the top
  laterals   secondary branches along each primary, both sides, slightly hanging
  twigs      the foliage: one small twig mesh (a stem with real needle geometry) instanced
             thousands of times along laterals and branch ends

A tree is ONE object: its mesh holds the woody parts plus loose vertices (attribute "twig" = 1)
that mark twig positions; attributes "trot" (euler) and "tscale" orient and size them. A shared
geometry-nodes group instances the species' twig on those vertices. Trees can therefore be
instanced again by the forest scatter (nested instances stay cheap in Cycles).

Species: "spruce" (dark blue-green, dense, narrow spire) and "larch" (bright yellow-green, open,
soft tufts). Detail levels: lod 0 (hero, near the house), 1 (forest edge), 2 (distant slopes).
"""
import bpy, math, random
from mathutils import Vector, Matrix, noise

SPECIES = {
    #            crown radius/h, crown base/h, whorl gap m, branches/whorl, twig len m, needle len m
    "spruce": dict(r=0.20, base=0.28, gap=0.32, nb=(4, 6), twig=0.42, needle=0.02, droop=0.55, lat_hang=0.35,
                   needle_rgb=(0.045, 0.095, 0.060)),
    "larch":  dict(r=0.18, base=0.34, gap=0.45, nb=(3, 5), twig=0.36, needle=0.028, droop=0.25, lat_hang=0.2,
                   needle_rgb=(0.20, 0.28, 0.07)),
}
LOD = {0: dict(twig_step=0.07, lat_gap=0.08, twig_scale=1.0, lat=True, seg=6, jitter=0.12),
       1: dict(twig_step=0.3, lat_gap=0.35, twig_scale=2.2, lat=True, seg=5),
       2: dict(twig_step=0.7, lat_gap=1.0, twig_scale=4.5, lat=False, seg=4)}


# ------------------------------------------------------------------ twig sources (needles as geometry)
def twig_source(species, coll, lite=False, near=False):
    """lite: only the needle-mass strips (no individual needles), for distant trees.
    near: hero trees seen from a few metres: short, dense shoots of needles bristling all round
    (no strips; strips read as fern fronds up close)."""
    name = f"Twig {species}" + (" lite" if lite else "") + (" near" if near else "")
    o = bpy.data.objects.get(name)
    if o:
        return o
    sp = SPECIES[species]
    rr = random.Random(7 if species == "spruce" else 11)
    v, f = [], []
    L, nl = sp["twig"], sp["needle"]
    # stem
    for k in range(6):
        x = L * k / 5
        r = 0.0018 * (1 - 0.6 * k / 5)
        base = len(v)
        for j in range(3):
            t = 2 * math.pi * j / 3
            v.append((x, r * math.cos(t), r * math.sin(t)))
        if k:
            for j in range(3):
                a, b = base - 3 + j, base - 3 + (j + 1) % 3
                f.append([a, b, b + 3, a + 3])
    def needle(p, d, ln, w=0.0028):
        d = d.normalized()
        s = d.orthogonal().normalized() * w
        i0 = len(v)
        v.extend([tuple(p - s), tuple(p + s), tuple(p + d * ln)])
        f.append([i0, i0 + 1, i0 + 2])
    def shoot(p0, d, ln, n_needle, nlen, w):
        """A needled shoot from p0 along d. Under the needles a narrow strip as wide as the needle
        spread stands in for the needles too fine to resolve at viewing distance; the strip's edge
        is notched so a spray reads as feathery, not as a leaf blade."""
        d = d.normalized()
        side = d.orthogonal().normalized()
        up = d.cross(side)
        if up.z < 0:
            up, side = -up, -side
        side = up.cross(d).normalized()                  # strip lies in the shoot's horizontal plane
        if near:
            stem_r = 0.0012
            for k in range(n_needle):
                x = ln * (0.02 + 0.97 * k / n_needle)
                q = p0 + d * x
                a = (k * 2.39996) % (2 * math.pi) + rr.uniform(-0.2, 0.2)   # phyllotaxis: needles all round
                radial = side * math.cos(a) + up * math.sin(a)
                if species == "spruce":
                    dd = d * 0.6 + radial + up * 0.25        # stiff, forward-pointing, a little up-turned
                    needle(q + radial * stem_r, dd, nlen * (0.85 + 0.25 * max(0.0, math.sin(a))) * rr.uniform(0.9, 1.1), w)
                elif k % 10 == 0:
                    for j in range(18):
                        aa = 2 * math.pi * j / 18
                        dd = d * 0.25 + side * math.cos(aa) + up * (math.sin(aa) * 0.6 + 0.55)
                        needle(q, dd, nlen * rr.uniform(0.75, 1.1), w * 0.8)
            return
        i0, ns = len(v), 8
        for k in range(ns + 1):
            x = ln * k / ns
            half = nlen * (0.6 if species == "spruce" else 0.55) * (0.55 + 0.45 * math.sin(math.pi * min(1, 0.15 + k / ns))) * (0.7 if k % 2 else 1.0)
            c = p0 + d * x - up * 0.002
            v.extend([tuple(c - side * half), tuple(c + side * half)])
        for k in range(ns):
            a0 = i0 + 2 * k
            f.append([a0, a0 + 2, a0 + 3, a0 + 1])
        if lite:
            return
        for k in range(n_needle):
            x = ln * (0.03 + 0.95 * k / n_needle)
            q = p0 + d * x
            if species == "spruce":
                a = rr.uniform(0, 2 * math.pi)
                dd = d * 0.55 + side * math.cos(a) + up * (math.sin(a) * 0.8 + 0.3)
                needle(q, dd, nlen * rr.uniform(0.8, 1.1), w)
            else:
                if k % 12 == 0:                       # larch short shoot: a rosette of soft needles
                    for j in range(16):
                        a = 2 * math.pi * j / 16 + rr.uniform(-0.2, 0.2)
                        dd = d * 0.3 + side * math.cos(a) + up * (math.sin(a) * 0.6 + 0.5)
                        needle(q, dd, nlen * rr.uniform(0.7, 1.1), w * 0.8)
    if near:
        # short spruce shoot cluster: leader + 3 pairs of side shoots in a flat, slightly arched fan
        Ln = 0.22 if species == "spruce" else 0.2
        shoot(Vector((0, 0, 0)), Vector((1, 0, 0)), Ln, 110, nl, 0.0011)
        for k in range(3):
            x = Ln * (0.2 + 0.25 * k)
            for sgn in (-1, 1):
                dd = Vector((0.7, sgn * 0.7, -0.04)).normalized()
                shoot(Vector((x, 0, 0)), dd, Ln * (0.55 - 0.12 * k), 55, nl * 0.95, 0.0011)
        me = bpy.data.meshes.new(name)
        me.from_pydata(v, [], f)
        o = bpy.data.objects.new(name, me)
        coll.objects.link(o)
        o.data.materials.append(needle_material(species))
        return o
    # a spray: main axis with alternating side shoots, all in a gently arched plane, as on spruce/larch branchlets
    main = Vector((1, 0, 0))
    shoot(Vector((0, 0, 0)), main, L, 70, nl, 0.0016)
    for k in range(7):
        x = L * (0.12 + 0.11 * k)
        for sgn in (-1, 1):
            d = Vector((0.75, sgn * 0.65, -0.05 * k)).normalized()
            ln = L * 0.42 * (1 - 0.08 * k) * rr.uniform(0.8, 1.1)
            shoot(Vector((x, 0, -0.004 * k)), d, ln, 26, nl * 0.9, 0.0015)
    me = bpy.data.meshes.new(name)
    me.from_pydata(v, [], f)
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    o.data.materials.append(needle_material(species))
    return o


def needle_material(species):
    name = f"Needles {species}"
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    N.clear()
    rgb = SPECIES[species]["needle_rgb"]
    oi = N.new("ShaderNodeObjectInfo")                       # per-instance colour variation
    hsv = N.new("ShaderNodeHueSaturation")
    hsv.inputs["Color"].default_value = (*rgb, 1)
    mr = N.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 0.8, 1.25
    L.new(oi.outputs["Random"], mr.inputs["Value"])
    L.new(mr.outputs[0], hsv.inputs["Value"])
    hr = N.new("ShaderNodeMapRange")
    hr.inputs["To Min"].default_value, hr.inputs["To Max"].default_value = 0.485, 0.515
    L.new(oi.outputs["Random"], hr.inputs["Value"])
    L.new(hr.outputs[0], hsv.inputs["Hue"])
    bs = N.new("ShaderNodeBsdfPrincipled")
    L.new(hsv.outputs[0], bs.inputs["Base Color"])
    bs.inputs["Roughness"].default_value = 0.55
    tr = N.new("ShaderNodeBsdfTranslucent")                  # sun glowing through the needles
    tcol = N.new("ShaderNodeMix")
    tcol.data_type = 'RGBA'
    tcol.inputs["Factor"].default_value = 0.6
    L.new(hsv.outputs[0], tcol.inputs[6])
    tcol.inputs[7].default_value = (0.35, 0.45, 0.05, 1)
    L.new(tcol.outputs[2], tr.inputs["Color"])
    mix = N.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.25
    L.new(bs.outputs[0], mix.inputs[1])
    L.new(tr.outputs[0], mix.inputs[2])
    out = N.new("ShaderNodeOutputMaterial")
    L.new(mix.outputs[0], out.inputs["Surface"])
    return m


# ------------------------------------------------------------------ shared geometry nodes: twigs on marked vertices
def tree_nodes(species, twig_obj, realize=False):
    """One node group per species, with its twig object wired in (modifier object inputs cannot be
    set from Python in this Blender build)."""
    gname = f"Tree twigs {species}" + (" realized" if realize else "")
    ng = bpy.data.node_groups.get(gname)
    if ng:
        return ng
    ng = bpy.data.node_groups.new(gname, "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    sel = N.new("GeometryNodeInputNamedAttribute")
    sel.data_type = 'FLOAT'
    sel.inputs["Name"].default_value = "twig"
    gt = N.new("FunctionNodeCompare")
    gt.data_type = 'FLOAT'
    gt.operation = 'GREATER_THAN'
    gt.inputs[1].default_value = 0.5
    L.new(sel.outputs["Attribute"], gt.inputs[0])
    sep = N.new("GeometryNodeSeparateGeometry")
    sep.domain = 'POINT'
    L.new(gi.outputs[0], sep.inputs["Geometry"])
    L.new(gt.outputs[0], sep.inputs["Selection"])
    oi = N.new("GeometryNodeObjectInfo")
    oi.inputs["As Instance"].default_value = True
    oi.inputs["Object"].default_value = twig_obj
    rot = N.new("GeometryNodeInputNamedAttribute")
    rot.data_type = 'FLOAT_VECTOR'
    rot.inputs["Name"].default_value = "trot"
    sc = N.new("GeometryNodeInputNamedAttribute")
    sc.data_type = 'FLOAT'
    sc.inputs["Name"].default_value = "tscale"
    e2r = N.new("FunctionNodeEulerToRotation")
    L.new(rot.outputs["Attribute"], e2r.inputs[0])
    inst = N.new("GeometryNodeInstanceOnPoints")
    L.new(sep.outputs["Selection"], inst.inputs["Points"])
    L.new(oi.outputs["Geometry"], inst.inputs["Instance"])
    L.new(e2r.outputs[0], inst.inputs["Rotation"])
    L.new(sc.outputs["Attribute"], inst.inputs["Scale"])
    jn = N.new("GeometryNodeJoinGeometry")
    L.new(sep.outputs["Inverted"], jn.inputs[0])
    if realize:
        rz = N.new("GeometryNodeRealizeInstances")
        L.new(inst.outputs[0], rz.inputs[0])
        L.new(rz.outputs[0], jn.inputs[0])
    else:
        L.new(inst.outputs[0], jn.inputs[0])
    L.new(jn.outputs[0], go.inputs[0])
    return ng


# ------------------------------------------------------------------ the tree
def _frame(d, prev=None):
    d = d.normalized()
    a = (prev - d * prev.dot(d)) if prev is not None else d.orthogonal()
    if a.length < 1e-6:
        a = d.orthogonal()
    a.normalize()
    return d, a, d.cross(a)


def build_tree(name, coll, species="spruce", h=12.0, seed=1, lod=0, bark_mat=None, crown_base=None, radius=None):
    """crown_base / radius (fractions of h) override the species values: trees grown in the open
    (by the house) keep live branches almost to the ground and spread wider than forest trees."""
    sp, ld = SPECIES[species], LOD[lod]
    rr = random.Random(seed)
    V, F = [], []                      # woody mesh
    TW, TR, TS = [], [], []            # twig anchors: position, euler, scale

    def tube(pts, radii, seg):
        prev_a = None
        rings = []
        for i, p in enumerate(pts):
            d = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
            d, a, b = _frame(d, prev_a)
            prev_a = a
            base = len(V)
            for k in range(seg):
                t = 2 * math.pi * k / seg
                V.append(tuple(p + (a * math.cos(t) + b * math.sin(t)) * radii[i]))
            rings.append(base)
        for i in range(len(pts) - 1):
            for k in range(seg):
                k2 = (k + 1) % seg
                F.append([rings[i] + k, rings[i] + k2, rings[i + 1] + k2, rings[i + 1] + k])

    def twig(p, d, up, s):
        d = d.normalized()
        z = (up - d * up.dot(d))
        if z.length < 1e-4:
            z = d.orthogonal()
        z.normalize()
        y = z.cross(d)
        M = Matrix((d, y, z)).transposed()
        TW.append(tuple(p))
        TR.append(tuple(M.to_euler()))
        TS.append(s * ld["twig_scale"] * rr.uniform(0.8, 1.15))

    # trunk: slight sweep, taper, root flare
    lean = Vector((rr.uniform(-1, 1), rr.uniform(-1, 1), 0)) * 0.01 * h
    stem = lambda z: Vector((lean.x * (z / h) ** 1.5, lean.y * (z / h) ** 1.5, z))
    r0 = 0.011 * h + 0.04
    zs = [0, 0.15, 0.4] + [h * k / 12 for k in range(1, 13)]
    tube([stem(z) for z in zs], [r0 * (1.6 if z == 0 else 1.25 if z < 0.3 else 1.0) * (1 - z / h * 0.92) + 0.004 for z in zs],
         12 if lod == 0 else 8)
    crown_base = h * (crown_base if crown_base is not None else sp["base"]) * rr.uniform(0.8, 1.15)
    R = (radius if radius is not None else sp["r"]) * h
    def crown_r(t):                         # t: 0 at crown base, 1 at the top
        t = min(max(t, 0), 1)
        return R * (1 - t) ** 0.95 * (0.85 + 0.15 * math.sin(math.pi * min(1, t * 3)))
    # dead stubs on the bare trunk
    if lod == 0:
        z = 1.2
        while z < crown_base:
            for k in range(rr.randint(1, 3)):
                a = rr.uniform(0, 2 * math.pi)
                d = Vector((math.cos(a), math.sin(a), -0.1))
                p0 = stem(z)
                tube([p0, p0 + d * rr.uniform(0.1, 0.45)], [0.012, 0.003], 4)
            z += sp["gap"] * rr.uniform(0.8, 1.6)
    # live crown
    z = crown_base
    w = 0
    while z < h * 0.97:
        t = (z - crown_base) / (h - crown_base)
        nb = rr.randint(*sp["nb"]) + (2 if lod == 0 else 0)          # hero trees: fuller whorls
        ph = rr.uniform(0, 2 * math.pi)
        for b in range(nb):
            if rr.random() < 0.1:
                continue
            a = ph + 2 * math.pi * b / nb + rr.uniform(-0.3, 0.3)
            L = crown_r(t) * rr.uniform(0.75, 1.15)
            if L < 0.25:
                # near the top: short shoots clothe the leader all round (no bare pole showing)
                for k in range(4):
                    aa = a + k * 1.57
                    twig(stem(z), Vector((math.cos(aa), math.sin(aa), 0.5)), Vector((0, 0, 1)), 0.75)
                continue
            d0 = Vector((math.cos(a), math.sin(a), 0))
            rise = 0.55 * t - sp["droop"] * (1 - t) * 0.5            # low branches droop, high ones rise
            n = 6
            pts = []
            for k in range(n + 1):
                u = k / n
                sag = -sp["droop"] * 0.35 * L * math.sin(math.pi * u * 0.9) + 0.15 * L * u ** 3
                pts.append(stem(z) + d0 * (L * u) + Vector((0, 0, L * u * rise + sag)))
            rb = max(0.006, 0.018 * L)
            tube(pts, [rb * (1 - 0.85 * k / n) for k in range(n + 1)], ld["seg"])
            side = Vector((-d0.y, d0.x, 0))
            # laterals every `lat_gap` along the primary (both sides), each covered in sprays every
            # `step`; sprays also sit directly on the primary, above and below
            step, lat_gap = ld["twig_step"], ld["lat_gap"]
            def at(u):
                i = min(int(u * n), n - 1)
                return pts[i].lerp(pts[i + 1], u * n - i), (pts[i + 1] - pts[i]).normalized()
            s_ = 0.12 * L + 0.1
            while s_ < L:
                u = s_ / L
                p, dirp = at(u)
                if lod == 0:                                   # tidy: shoots follow the branch, fanned flat
                    for sgn in (-1, 1):
                        sd = (dirp * 0.8 + side * sgn * 0.6 + Vector((0, 0, -0.08))).normalized()
                        twig(p, sd, Vector((0, 0, 1)), 1.0)
                else:
                    twig(p, dirp + Vector((0, 0, 0.15)), Vector((0, 0, 1)), 1.0)
                    twig(p, dirp + Vector((0, 0, -0.25)), Vector((0, 0, 1)), 0.9)
                s_ += step
            if ld["lat"]:
                s_ = 0.15 * L + 0.15
                sgn = 1
                while s_ < L * 0.93:
                    u = s_ / L
                    p, dirp = at(u)
                    for side_ in (sgn, -sgn) if rr.random() < 0.7 else (sgn,):
                        ll = L * 0.42 * (1 - u) ** 0.35 * rr.uniform(0.7, 1.1)
                        dl = (dirp * 0.5 + side * side_ * 0.85 + Vector((0, 0, -sp["lat_hang"]))).normalized()
                        q = p.copy()
                        k = 0.0
                        while k < ll:
                            q = q + dl * step
                            dl = (dl + Vector((0, 0, -0.06))).normalized()     # laterals hang more toward their tips
                            if lod == 0:
                                for sgn in (-1, 1):            # side shoots fanned flat on the lateral
                                    sd = (dl * 0.75 + side * sgn * 0.55).normalized()
                                    twig(q, sd, Vector((0, 0, 1)), 0.8)
                            else:
                                twig(q, dl, Vector((0, 0, 1)), 0.85)
                            k += step
                    sgn = -sgn
                    s_ += lat_gap * rr.uniform(0.8, 1.2)
            twig(pts[-1], (pts[-1] - pts[-2]), Vector((0, 0, 1)), 1.1)
        w += 1
        z += sp["gap"] * rr.uniform(0.75, 1.25) * (0.45 if t > 0.75 else 1.0)    # whorls crowd toward the top
    # leader
    for k in range(6):
        twig(stem(h * (0.94 + 0.01 * k)), Vector((rr.uniform(-.3, .3), rr.uniform(-.3, .3), 1)), Vector((1, 0, 0)), 0.8)

    # assemble one mesh: woody faces + loose twig vertices
    nv = len(V)
    me = bpy.data.meshes.new(name)
    me.from_pydata(V + TW, [], F)
    me.validate()
    tw = me.attributes.new("twig", 'FLOAT', 'POINT')
    tw.data.foreach_set("value", [0.0] * nv + [1.0] * len(TW))
    tr = me.attributes.new("trot", 'FLOAT_VECTOR', 'POINT')
    flat = [0.0] * (3 * nv)
    for e in TR:
        flat.extend(e)
    tr.data.foreach_set("vector", flat)
    ts = me.attributes.new("tscale", 'FLOAT', 'POINT')
    ts.data.foreach_set("value", [0.0] * nv + TS)
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    if bark_mat:
        me.materials.append(bark_mat)
    mod = o.modifiers.new("Twigs", 'NODES')
    src_coll = bpy.data.collections.get("39_Scatter_Sources") or coll
    if lod == 0:
        mod.node_group = tree_nodes(species + " near", twig_source(species, src_coll, near=True))
    elif lod == 1:
        mod.node_group = tree_nodes(species, twig_source(species, src_coll))
    else:
        # distant trees are scattered by the thousand: bake twigs into one plain mesh so the forest
        # is a single level of instancing (nested instances made Cycles expand ~15 M twig transforms)
        mod.node_group = tree_nodes(species, twig_source(species, src_coll, lite=True), realize=True)
        hidden = src_coll.hide_viewport            # hidden collections are not evaluated: unhide while baking
        src_coll.hide_viewport = False
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
        baked = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=False)
        src_coll.hide_viewport = hidden
        if len(baked.vertices) <= len(V):
            raise RuntimeError(f"{name}: twigs were not baked ({len(baked.vertices)} verts)")
        o.modifiers.remove(mod)
        old = o.data
        o.data = baked
        bpy.data.meshes.remove(old)
        baked.name = name
    o["species"], o["lod"], o["twigs"] = species, lod, len(TW)
    return o


# ------------------------------------------------------------------ broadleaf shrub (2026-10-20)
def leaf_twig_source(coll, name="Twig shrub", rgb=(0.05, 0.13, 0.03)):
    """Short twig with 9 alternate elliptic leaves (real geometry, slightly folded at the midrib)."""
    o = bpy.data.objects.get(name)
    if o:
        return o
    rr = random.Random(23)
    v, f = [], []
    L = 0.16
    for k in range(4):                                    # stem
        for j in range(3):
            t = 2 * math.pi * j / 3
            v.append((L * k / 3, 0.0015 * math.cos(t), 0.0015 * math.sin(t)))
    for k in range(3):
        for j in range(3):
            a, b = k * 3 + j, k * 3 + (j + 1) % 3
            f.append([a, b, b + 3, a + 3])
    for k in range(9):
        x = L * (0.15 + 0.85 * k / 8)
        sgn = 1 if k % 2 else -1
        d = Vector((0.55, sgn * 0.8, 0.25)).normalized()
        ln = rr.uniform(0.045, 0.06) * (0.8 if k == 8 else 1.0)
        w = ln * 0.42
        side = d.cross(Vector((0, 0, 1))).normalized()
        up = side.cross(d).normalized()
        base = Vector((x, 0, 0))
        i0 = len(v)
        v.append(tuple(base))
        for q in range(1, 7):                              # two rows of points along the blade, folded up at the edges
            t = q / 7
            half = w * math.sin(math.pi * t) ** 0.8
            c = base + d * (ln * t) - up * (0.15 * ln * t * t)
            v.append(tuple(c + side * half + up * half * 0.3))
            v.append(tuple(c - side * half + up * half * 0.3))
        v.append(tuple(base + d * ln - up * 0.15 * ln))
        tip = len(v) - 1
        f.append([i0, i0 + 1, i0 + 2])
        for q in range(5):
            a = i0 + 1 + 2 * q
            f.append([a, a + 2, a + 3, a + 1])
        f.append([i0 + 11, tip, i0 + 12])
    me = bpy.data.meshes.new(name)
    me.from_pydata(v, [], f)
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    m = bpy.data.materials.get("Leaves shrub")
    if m is None:
        SPECIES["shrub"] = dict(needle_rgb=rgb)
        m = needle_material("shrub")
        m.name = "Leaves shrub"
        bs = [n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'][0]
        bs.inputs["Roughness"].default_value = 0.35            # glossy evergreen leaves
    me.materials.append(m)
    return o


def build_shrub(name, coll, size=(1.4, 1.2, 1.0), seed=1, bark_mat=None):
    """Multi-stemmed evergreen shrub with an irregular, mounded outline (not a clipped ball): stems
    fan out from the base, fork twice, and carry leaf twigs densely on their outer parts."""
    rr = random.Random(seed)
    sx, sy, sz = size
    V, F, TW, TR, TS = [], [], [], [], []

    def envelope(d):                                       # irregular crown surface distance in direction d
        n = noise.noise(d * 1.6 + Vector((seed, 0.3, 0.7)))
        return 1.0 + 0.28 * n

    def tube(pts, r0, r1, seg=5):
        prev_a = None
        rings = []
        for i, p in enumerate(pts):
            d = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
            d, a, b = _frame(d, prev_a)
            prev_a = a
            r = r0 + (r1 - r0) * i / (len(pts) - 1)
            rings.append(len(V))
            for k in range(seg):
                t = 2 * math.pi * k / seg
                V.append(tuple(p + (a * math.cos(t) + b * math.sin(t)) * r))
        for i in range(len(pts) - 1):
            for k in range(seg):
                k2 = (k + 1) % seg
                F.append([rings[i] + k, rings[i] + k2, rings[i + 1] + k2, rings[i + 1] + k])

    def twig(p, d):
        d = d.normalized()
        z = Vector((0, 0, 1)) - d * d.z
        if z.length < 1e-4:
            z = d.orthogonal()
        z.normalize()
        M = Matrix((d, z.cross(d), z)).transposed()
        TW.append(tuple(p))
        TR.append(tuple(M.to_euler()))
        TS.append(rr.uniform(1.2, 1.7))

    def branch(p0, d, L, r, level):
        n = 5
        pts = [p0]
        dd = d.copy()
        for k in range(n):
            dd = (dd + Vector((rr.uniform(-.25, .25), rr.uniform(-.25, .25), rr.uniform(-.05, .2)))).normalized()
            pts.append(pts[-1] + dd * (L / n))
        tube(pts, r, r * 0.35)
        # leaf twigs on the outer part, pointing outward, densest at the surface
        s_ = 0.35
        while s_ < 1.0:
            i = min(int(s_ * n), n - 1)
            p = pts[i].lerp(pts[i + 1], s_ * n - i)
            out = Vector((p.x / sx, p.y / sy, (p.z - sz * 0.45) / sz)).normalized()
            for k in range(3):
                twig(p, (dd * 0.4 + out + Vector((rr.uniform(-.7, .7), rr.uniform(-.7, .7), rr.uniform(-.4, .2)))))
            s_ += 0.05 / max(L, 0.2)
        if level < 2:
            for k in range(rr.randint(2, 3)):
                f = rr.uniform(0.35, 0.7)
                i = min(int(f * n), n - 1)
                q = pts[i]
                nd = (dd + Vector((rr.uniform(-1, 1), rr.uniform(-1, 1), rr.uniform(-0.2, 0.6)))).normalized()
                lim = envelope(nd) * Vector((nd.x * sx, nd.y * sy, nd.z * sz)).length
                branch(q, nd, max(0.15, min(L * 0.65, lim - (q - Vector((0, 0, sz * 0.2))).length * 0.6)), r * 0.6, level + 1)
        twig(pts[-1], dd)

    for k in range(rr.randint(6, 9)):
        a = rr.uniform(0, 2 * math.pi)
        d = Vector((math.cos(a) * rr.uniform(0.35, 0.8), math.sin(a) * rr.uniform(0.35, 0.8), 1)).normalized()
        lim = envelope(d) * Vector((d.x * sx, d.y * sy, d.z * sz)).length
        branch(Vector((rr.uniform(-.05, .05), rr.uniform(-.05, .05), 0)), d, lim * 0.75, 0.018, 0)

    nv = len(V)
    me = bpy.data.meshes.new(name)
    me.from_pydata(V + TW, [], F)
    me.validate()
    me.attributes.new("twig", 'FLOAT', 'POINT').data.foreach_set("value", [0.0] * nv + [1.0] * len(TW))
    flat = [0.0] * (3 * nv)
    for e in TR:
        flat.extend(e)
    me.attributes.new("trot", 'FLOAT_VECTOR', 'POINT').data.foreach_set("vector", flat)
    me.attributes.new("tscale", 'FLOAT', 'POINT').data.foreach_set("value", [0.0] * nv + TS)
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    if bark_mat:
        me.materials.append(bark_mat)
    src_coll = bpy.data.collections.get("39_Scatter_Sources") or coll
    o.modifiers.new("Twigs", 'NODES').node_group = tree_nodes("shrub", leaf_twig_source(src_coll))
    o["twigs"] = len(TW)
    return o


# ------------------------------------------------------------------ Japanese maple (鸡爪槭), 2026-10-20
def maple_twig_source(coll, name="Twig maple"):
    """Short reddish shoot with 6 palmate, 7-lobed leaves on petioles, held near horizontal."""
    o = bpy.data.objects.get(name)
    if o:
        return o
    rr = random.Random(31)
    v, f = [], []
    L = 0.2
    for k in range(4):
        for j in range(3):
            t = 2 * math.pi * j / 3
            v.append((L * k / 3, 0.0015 * math.cos(t), 0.0015 * math.sin(t)))
    for k in range(3):
        for j in range(3):
            a, b = k * 3 + j, k * 3 + (j + 1) % 3
            f.append([a, b, b + 3, a + 3])
    for k in range(6):
        x = L * (0.2 + 0.8 * k / 5)
        sgn = 1 if k % 2 else -1
        pet = Vector((0.4, sgn * 0.9, 0.15)).normalized() * 0.035
        c = Vector((x, 0, 0)) + pet
        R = rr.uniform(0.035, 0.05)
        rot = math.atan2(pet.y, pet.x)
        i0 = len(v)
        v.append(tuple(c))
        n = 7 * 6                                         # 7 lobes, each pointed, deep sinuses
        for q in range(n):
            t = 2 * math.pi * q / n
            lobe = (q % 6) / 6.0
            r = R * (0.32 + 0.68 * (1 - abs(lobe - 0.5) * 2) ** 1.4)
            if 2 * math.pi * 0.42 < (t % (2 * math.pi)) < 2 * math.pi * 0.58:
                r *= 0.4                                  # gap at the petiole
            a = t + rot
            v.append(tuple(c + Vector((r * math.cos(a), r * math.sin(a), 0.006 * math.sin(3 * t) - 0.004))))
        for q in range(n):
            f.append([i0, i0 + 1 + q, i0 + 1 + (q + 1) % n])
    me = bpy.data.meshes.new(name)
    me.from_pydata(v, [], f)
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    m = bpy.data.materials.get("Leaves maple")
    if m is None:
        SPECIES["maple"] = dict(needle_rgb=(0.17, 0.32, 0.05))
        m = needle_material("maple")
        m.name = "Leaves maple"
    me.materials.append(m)
    return o


def build_maple(name, coll, h=4.2, spread=2.8, seed=1, bark_mat=None, lean=(0.25, 0.0)):
    """Slender leaning trunk forking into 3-5 long limbs that rise and spread; fine branchlets end in
    near-horizontal sprays of palmate leaves, giving the airy, layered crown of a garden maple."""
    rr = random.Random(seed)
    V, F, TW, TR, TS = [], [], [], [], []

    def tube(pts, r0, r1, seg=8):
        prev_a = None
        rings = []
        for i, p in enumerate(pts):
            d = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
            d, a, b = _frame(d, prev_a)
            prev_a = a
            r = r0 + (r1 - r0) * i / (len(pts) - 1)
            rings.append(len(V))
            for k in range(seg):
                t = 2 * math.pi * k / seg
                V.append(tuple(p + (a * math.cos(t) + b * math.sin(t)) * r))
        for i in range(len(pts) - 1):
            for k in range(seg):
                k2 = (k + 1) % seg
                F.append([rings[i] + k, rings[i] + k2, rings[i + 1] + k2, rings[i + 1] + k])

    def spray(p, d):
        d = Vector((d.x, d.y, d.z * 0.25)).normalized()      # leaf sprays lie nearly flat: layered crown
        z = Vector((0, 0, 1)) - d * d.z
        z.normalize()
        M = Matrix((d, z.cross(d), z)).transposed()
        TW.append(tuple(p))
        TR.append(tuple(M.to_euler()))
        TS.append(rr.uniform(1.2, 1.6))

    def limb(p0, d, L, r, level):
        n = 7
        pts = [p0]
        dd = d.copy()
        for k in range(n):
            bend = Vector((rr.uniform(-.18, .18), rr.uniform(-.18, .18), -0.05 * level))
            dd = (dd + bend).normalized()
            pts.append(pts[-1] + dd * (L / n))
        tube(pts, r, r * 0.45, seg=8 if level < 2 else 5)
        if level >= 3 or (level == 2 and L < 0.35):
            s_ = 0.2
            while s_ <= 1.0:                                 # leaf sprays along the outer branchlets
                i = min(int(s_ * n), n - 1)
                p = pts[i].lerp(pts[i + 1], s_ * n - i)
                for sgn in (-1, 1):
                    side = dd.cross(Vector((0, 0, 1))).normalized() * sgn
                    spray(p, dd * 0.6 + side * 0.8)
                s_ += 0.16 / max(L, 0.3)
            spray(pts[-1], dd)
            return
        nk = (rr.randint(3, 4), rr.randint(3, 4), rr.randint(3, 5))[level]
        for k in range(nk):
            f = rr.uniform(0.4, 0.95)
            i = min(int(f * n), n - 1)
            a = rr.uniform(0, 2 * math.pi)
            nd = (dd * 1.0 + Vector((math.cos(a), math.sin(a), 0.1)) * (0.5 + 0.2 * level)).normalized()
            limb(pts[i], nd, L * rr.uniform(0.45, 0.65), r * 0.55, level + 1)
        if level == 2:                                       # a few sprays along the level-2 twigs
            for k in range(2):
                f = rr.uniform(0.5, 1.0)
                i = min(int(f * n), n - 1)
                spray(pts[i], dd + dd.cross(Vector((0, 0, 1))) * rr.choice((-1, 1)))

    base = Vector((0, 0, 0))
    ld = Vector((lean[0], lean[1], 1)).normalized()
    fork = base + ld * h * 0.3
    tube([base, base + ld * h * 0.05, base + ld * h * 0.18, fork], 0.075, 0.06, seg=10)
    for k in range(rr.randint(3, 4)):                       # main limbs rise steeply from the fork
        a = rr.uniform(0, 2 * math.pi)
        d = (Vector((math.cos(a) * 0.3, math.sin(a) * 0.3, 1)) + ld * 0.3).normalized()
        limb(fork, d, h * rr.uniform(0.55, 0.72), 0.045, 0)
    nv = len(V)
    me = bpy.data.meshes.new(name)
    me.from_pydata(V + TW, [], F)
    me.validate()
    me.attributes.new("twig", 'FLOAT', 'POINT').data.foreach_set("value", [0.0] * nv + [1.0] * len(TW))
    flat = [0.0] * (3 * nv)
    for e in TR:
        flat.extend(e)
    me.attributes.new("trot", 'FLOAT_VECTOR', 'POINT').data.foreach_set("vector", flat)
    me.attributes.new("tscale", 'FLOAT', 'POINT').data.foreach_set("value", [0.0] * nv + TS)
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    if bark_mat:
        me.materials.append(bark_mat)
    src_coll = bpy.data.collections.get("39_Scatter_Sources") or coll
    o.modifiers.new("Twigs", 'NODES').node_group = tree_nodes("maple", maple_twig_source(src_coll))
    o["twigs"] = len(TW)
    return o
