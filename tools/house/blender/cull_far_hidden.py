"""Cull the hidden middle band (2026-10-21): the forested foothills between the lake-edge pines and
the snow range. From every camera only the crest of the foothill forest shows above the forest-edge
trees; the slope and the ~110k trees below it are hidden. Visitors only ever look from the front (the
overview and the three room views, VIEWS), so this pass keeps the foothill trees that show at least
MIN_PX pixels in one of those cameras, freezes them as
fixed instance points, and deletes the foothill faces none of them can see. The snow mountains, the
front range and the forest-edge trees are left alone.

Run after build_environment:
    Blender -b assets/blender/companion-house.blend --python cull_far_hidden.py
Visibility is conservative: occluders are shrunk cones for the edge and near pines (crowns have gaps),
the house shell (walls, frame, floors, roof, stonework) and the foothill slope itself; window glass,
furniture never count as occluders. Foothill trees hide each other (the front rows of the canopy hide
the rows behind, which is why only two or three rows show); a tree's own cone never hides itself.
"""
import bpy, bmesh, math, os, time
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

FOREST = ("Foothill forest 0 spruce", "Foothill forest 1 spruce", "Foothill forest 2 larch")
HILL = "Foothills hill"
SHELL = ("11_Frame", "12_Walls", "13_Floors", "15_Roof", "16_Stonework", "17_Flues")
CONE_SHRINK = float(os.environ.get("CULL_SHRINK", 0.8))   # edge-pine crowns are not solid; a smaller cone lets rays through the gaps
FRUSTUM_PAD = 1.15       # keep trees just outside the frame (camera shift, lens tweaks)
VIEWS = ("Cam_Overview", "Cam_Side_20deg", "Cam_Room_F1", "Cam_Room_F2", "Cam_Room_F3")   # visitor views;
                         # the detail and yard cameras are modelling checks and may show gaps behind the edge pines
MIN_PX = float(os.environ.get("CULL_MIN_PX", 300))  # visible crown area (pixels, full resolution) a tree needs to stay;
                         # 300 keeps ~460 trees and the overview unchanged; 1000 (~140) lets the snow-range foot show through
CROWN = ((0.95, (0.0,)), (0.8, (-0.5, 0.5)), (0.65, (-0.7, 0.0, 0.7)), (0.5, (-0.8, 0.0, 0.8)),
         (0.35, (-0.85, 0.0, 0.85)), (0.2, (-0.85, 0.0, 0.85)))   # (height, across) samples on the crown

t0 = time.time()
sc = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()
W, H = sc.render.resolution_x, sc.render.resolution_y


# ------------------------------------------------------------------ cameras
def frustum(cam):
    d = cam.data
    fit = d.sensor_fit if d.sensor_fit != 'AUTO' else ('HORIZONTAL' if W >= H else 'VERTICAL')
    if fit == 'HORIZONTAL':
        th = d.sensor_width / 2 / d.lens
        tv = th * H / W
    else:
        tv = d.sensor_height / 2 / d.lens
        th = tv * W / H
    return np.array(cam.matrix_world.inverted()), th * FRUSTUM_PAD, tv * FRUSTUM_PAD, d.clip_end, W / (2 * th)

CAMS = [(c.matrix_world.translation.copy(), *frustum(c)) for c in bpy.data.objects
        if c.name in os.environ.get("CULL_CAMS", ",".join(VIEWS)).split(",")]
print("CULL cameras", len(CAMS))

def in_view(pts, inv, th, tv, clip):
    """Boolean mask of points (N, 3) inside one camera's padded frustum."""
    p = pts @ inv[:3, :3].T + inv[:3, 3]
    z = -p[:, 2]
    return (z > 0.1) & (z < clip) & (np.abs(p[:, 0]) < th * z) & (np.abs(p[:, 1]) < tv * z)


# ------------------------------------------------------------------ occluders
verts, tris = [], []

def add_mesh(o):
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    mw = o.matrix_world
    i0 = len(verts)
    verts.extend(mw @ v.co for v in me.vertices)
    tris.extend(tuple(i0 + i for i in t.vertices) for t in me.loop_triangles)
    ev.to_mesh_clear()

def add_cone(o):
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    x0, x1 = min(v.x for v in bb), max(v.x for v in bb)
    y0, y1 = min(v.y for v in bb), max(v.y for v in bb)
    z0, z1 = min(v.z for v in bb), max(v.z for v in bb)
    cone((x0 + x1) / 2, (y0 + y1) / 2, z0, z1, (x1 - x0 + y1 - y0) / 4)

def cone(cx, cy, z0, z1, r):
    r *= CONE_SHRINK
    base = z0 + 0.15 * (z1 - z0)                  # bare trunk below the crown
    i0 = len(verts)
    verts.append(Vector((cx, cy, z1)))
    for k in range(10):
        a = k / 10 * math.tau
        verts.append(Vector((cx + r * math.cos(a), cy + r * math.sin(a), base)))
    for k in range(10):
        tris.append((i0, i0 + 1 + k, i0 + 1 + (k + 1) % 10))

for o in bpy.data.objects:
    if o.type == 'MESH' and o.name.startswith(("Forest edge tree", "Pine ")) and o.visible_get():
        add_cone(o)
for cn in SHELL:
    for o in bpy.data.collections[cn].all_objects:
        if o.type == 'MESH' and o.visible_get():
            add_mesh(o)
hill = bpy.data.objects[HILL]
add_mesh(hill)
N_STATIC = len(tris)
STATIC = BVHTree.FromPolygons(verts, tris, epsilon=0.0)
print("CULL static occluder tris", N_STATIC)

def visible(pts, bvh, owner=None):
    """Per point: can any camera see it? Frustum test in numpy, then ray casts with early exit.
    owner[i] is the tree id of point i; hits on that tree's own cone are stepped through."""
    pts = np.asarray(pts, dtype=np.float64)
    seen = np.zeros(len(pts), bool)
    for org, inv, th, tv, clip, _ in CAMS:
        todo = np.nonzero(~seen & in_view(pts, inv, th, tv, clip))[0]
        for i in todo:
            seen[i] = clear(org, Vector(pts[i]), bvh, owner[i] if owner is not None else None)
    return seen

def clear(org, p, bvh, own):
    d = p - org
    dist = d.length
    d /= dist
    o_, left = org, dist - 0.05
    while True:
        hit = bvh.ray_cast(o_, d, left)
        if hit[0] is None:
            return True
        ti = hit[2] - N_STATIC
        if own is None or ti < 0 or ti // 10 != own:
            return False
        step = (hit[0] - o_).length + 0.02
        o_, left = hit[0] + d * 0.02, left - step
        if left <= 0:
            return True

def coverage(pts, owner, n, area):
    """Per tree (n samples each, crown area in m2): the largest visible crown area, in pixels, over
    the cameras; visible share = unblocked samples / n."""
    pts = np.asarray(pts, dtype=np.float64)
    best = np.zeros(len(pts) // n)
    for org, inv, th, tv, clip, px_per_m in CAMS:
        inside = in_view(pts, inv, th, tv, clip).reshape(-1, n).any(1)
        z = -(pts[::n] @ inv[:3, :3].T + inv[:3, 3])[:, 2]
        full = area * (px_per_m / np.maximum(z, 0.1)) ** 2
        for t in np.nonzero(inside & (full > best))[0]:
            hits = sum(clear(org, Vector(pts[t * n + k]), TREES, owner[t]) for k in range(n))
            best[t] = max(best[t], full[t] * hits / n)
    return best


# ------------------------------------------------------------------ foothill trees
SRC_BB = {}
def src_size(ob):
    if ob.name not in SRC_BB:
        bb = [Vector(c) for c in ob.bound_box]
        SRC_BB[ob.name] = (max(v.z for v in bb) - min(v.z for v in bb),
                           (max(v.x for v in bb) - min(v.x for v in bb) + max(v.y for v in bb) - min(v.y for v in bb)) / 4)
    return SRC_BB[ob.name]

inst = {n: [] for n in FOREST}
for di in dg.object_instances:
    if di.is_instance and di.parent and di.parent.original.name in inst:
        inst[di.parent.original.name].append((di.matrix_world.copy(), di.object.original))

# every foothill tree becomes a 10-triangle cone after the static occluders; tree id = cone index
tree_id = {}
for name in FOREST:
    ids = []
    for mw, src in inst[name]:
        h0, r0 = src_size(src)
        p, s_ = mw.translation, mw.to_scale().z
        ids.append((len(tris) - N_STATIC) // 10)
        cone(p.x, p.y, p.z, p.z + h0 * s_, r0 * s_)
    tree_id[name] = ids
TREES = BVHTree.FromPolygons(verts, tris, epsilon=0.0)
print("CULL tree cones", (len(tris) - N_STATIC) // 10)

org0 = CAMS[0][0]
total_before = total_after = 0
for name in FOREST:
    o = bpy.data.objects[name]
    rows = inst[name]
    if not rows:
        continue
    src = rows[0][1]
    h0, r0 = src_size(src)
    # samples spread over the crown silhouette as seen along the overview line of sight; the across
    # offset follows the cone, so each sample sits inside the crown at its height
    samples, area = [], []
    for mw, _ in rows:
        p = mw.translation
        s = mw.to_scale().z
        h, r = h0 * s, r0 * s
        side = Vector((-(p.y - org0.y), p.x - org0.x, 0)).normalized()
        for f, across in CROWN:
            w = r * min(1.0, (1 - f) / 0.85)
            samples += [tuple(p + Vector((0, 0, f * h)) + side * a * w) for a in across]
        area.append(0.85 * h * r)
    n = sum(len(a) for _, a in CROWN)
    owner = np.array(tree_id[name])
    px = coverage(samples, owner, n, np.array(area))
    keep = px >= MIN_PX
    print("CULL", name, "visible px quantiles", np.percentile(px[px > 0], [50, 90, 99]).round(0) if (px > 0).any() else 0)
    kept = [rows[i][0] for i in np.nonzero(keep)[0]]
    total_before += len(rows)
    total_after += len(kept)

    # freeze the kept trees: one vertex per tree carrying its rotation and scale
    inv = o.matrix_world.inverted()
    me = bpy.data.meshes.new(f"{name} kept points")
    loc, rot, scl = [], [], []
    for mw in kept:
        l, q, s = (inv @ mw).decompose()
        loc.append(tuple(l)); rot.append(tuple(q.to_euler())); scl.append(tuple(s))
    me.from_pydata(loc, [], [])
    for an, vals in (("rot", rot), ("scl", scl)):
        a = me.attributes.new(an, 'FLOAT_VECTOR', 'POINT')
        a.data.foreach_set("vector", [c for v in vals for c in v])
    old_ng = o.modifiers["Scatter"].node_group
    o.data = me

    ng = bpy.data.node_groups.new(f"Kept {name}", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = ng.nodes
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    info = N.new("GeometryNodeObjectInfo")
    info.inputs["Object"].default_value = src
    info.inputs["As Instance"].default_value = True
    iop = N.new("GeometryNodeInstanceOnPoints")
    ra, sa = N.new("GeometryNodeInputNamedAttribute"), N.new("GeometryNodeInputNamedAttribute")
    for a_, n_ in ((ra, "rot"), (sa, "scl")):
        a_.data_type = 'FLOAT_VECTOR'
        a_.inputs["Name"].default_value = n_
    L = ng.links
    L.new(gi.outputs[0], iop.inputs["Points"])
    L.new(info.outputs["Geometry"], iop.inputs["Instance"])
    L.new(ra.outputs["Attribute"], iop.inputs["Rotation"])
    L.new(sa.outputs["Attribute"], iop.inputs["Scale"])
    L.new(iop.outputs["Instances"], go.inputs[0])
    o.modifiers["Scatter"].node_group = ng          # keeps the "Scatter" name the material passes skip
    if old_ng.users == 0:
        bpy.data.node_groups.remove(old_ng)
    print("CULL", name, len(rows), "->", len(kept))


# ------------------------------------------------------------------ foothill slope
me = hill.data
mw = hill.matrix_world
cent = [tuple(mw @ (p.center + p.normal * 0.5)) for p in me.polygons]
seen = visible(cent, STATIC)                       # trees never hide ground: crowns have gaps
bm = bmesh.new()
bm.from_mesh(me)
bm.faces.ensure_lookup_table()
keep = set(np.nonzero(seen)[0].tolist())
for i in list(keep):                                # one ring of neighbours so no seams open at the cut
    for v in bm.faces[i].verts:
        keep.update(f.index for f in v.link_faces)
drop = [f for f in bm.faces if f.index not in keep]
n_before = len(bm.faces)
bmesh.ops.delete(bm, geom=drop, context='FACES')
bm.to_mesh(me)
bm.free()
print("CULL", HILL, "faces", n_before, "->", len(me.polygons))
print("CULL trees", total_before, "->", total_after, "in", round(time.time() - t0, 1), "s")
bpy.ops.wm.save_mainfile()
print("CULL_SAVED")
