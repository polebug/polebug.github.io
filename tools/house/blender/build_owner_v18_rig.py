"""Owner avatar v18 (2026-10-21): the approved v17 look turned into one web-ready skinned mesh.

    Blender -b --python assets/blender/scripts/build_owner_v18_rig.py

v17 is ~1M triangles of separate parts with subdivision, curves and solidify. v18:
- applies modifiers at lower levels, converts the seam/glasses curves at low resolution, cuts the
  leg skin hidden inside the jeans and decimates the dense parts (face and hair keep their UVs and
  topology), then joins everything into one mesh "Owner_Body" (materials kept, flat colours need no UVs);
- scales to the in-house size of the old owner (1.443 m including buns), feet on z = 0, facing -Y;
- adds a 24-bone humanoid armature "Owner_Rig" (Mixamo-like hierarchy, +X is her left = .L) with
  weights computed per part from distances to the bone segments (soft blend at the joints; head,
  hair and glasses rigid on Head; iris, pupil and highlight on Eye.L / Eye.R for gaze);
- adds an eyelid sheet per eye and shape keys Blink.L / Blink.R that unroll it over the eye, ending
  in a dark lash line (the face itself never deforms).
Blinking and gaze are driven from the web code (morph target + eye bones); actions only move bones.
Hands are the v12 fists rebuilt with the thumb on the outer side (v12 had mirrored hands), one Hand bone each, turned palms-to-thighs, thumbs forward (PALM_IN).
"""
import bpy, bmesh, math, os, json
import numpy as np
from mathutils import Vector, Matrix

P = '/Users/bugpole/AI/博客陪伴小屋'
SRC = P + '/assets/blender/characters/owner-character-v17.blend'
DST = os.environ.get('V18_DST', P + '/assets/blender/characters/owner-character-v18.blend')
S = 1.443 / (3.119 - 0.027)        # v17 units -> metres (old in-house owner was 1.443 m tall)
Z0 = 0.027                         # v17 sole bottom
PALM_IN = 85.0                     # deg about the wrist-to-knuckle line: palm forward -> palm to the thigh, thumb forward

bpy.ops.wm.open_mainfile(filepath=SRC)
col = bpy.data.collections['Owner_V17']

# ------------------------------------------------------------------ face tone
# The face texture's skin is a saturated orange (linear 0.99 / 0.48 / 0.34) that reads darker than the
# limbs (0.84 / 0.55 / 0.42). Tone the whole texture in linear light so its skin lands FACE_LIGHT
# brighter than the limbs with their hue; blush, brows and eyes shift with it.
FACE_LIGHT = 1.08
face_img = next(n.image for n in bpy.data.materials['head'].node_tree.nodes
                if n.type == 'TEX_IMAGE' and n.image and n.image.colorspace_settings.name == 'sRGB')
fw, fh = face_img.size
fpx = np.array(face_img.pixels[:], dtype=np.float32).reshape(-1, 4)
# Two leftovers of the source face that show on the web: the eye area (both eyes share it) still
# has a pink iris painted inside a black ring, which peeks out round the 3D iris disc - paint it eye
# white; and the mouth's inner faces sample the bright red blobs - darken them so the small mouth
# reads as a line. Pixel coordinates are from the top of the 2048 px image.
yy, xx = np.mgrid[0:fh, 0:fw]
yy = fh - 1 - yy                                     # Blender stores rows bottom-up
painted_eye = ((xx - 1632) / 214.0) ** 2 + ((yy - 372.5) / 235.0) ** 2 < 1
fpx.reshape(fh, fw, 4)[painted_eye, :3] = 1.0
red = (fpx[:, 0] > 0.8) & (fpx[:, 1] < 0.35) & (fpx[:, 2] < 0.35)
fpx[red, :3] = (0.30, 0.11, 0.10)
to_lin = lambda c: np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
to_srgb = lambda c: np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(np.clip(c, 0, None), 1 / 2.4) - 0.055)
limb = np.array(bpy.data.materials['Skin • warm peach'].node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value[:3])
gain = limb * FACE_LIGHT / to_lin(np.median(fpx[:, :3], 0))
fpx[:, :3] = np.clip(to_srgb(np.clip(to_lin(fpx[:, :3]) * gain, 0, 1)), 0, 1)
toned = bpy.data.images.new('head Base Color • toned', fw, fh, alpha=True)
toned.pixels.foreach_set(fpx.ravel())
toned.pack()
for n in bpy.data.materials['head'].node_tree.nodes:
    if n.type == 'TEX_IMAGE' and n.image == face_img:
        n.image = toned

# ------------------------------------------------------------------ hands: thumb on the correct side
# v12 built the fists with the fingers curling forward (palm forward) but put the thumb on the inner
# side, so each hand was the other hand's mirror image. Rebuild both arms exactly as build_owner_v12.py
# does, with the thumb mirrored across the palm centre to the outer side.
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meshkit import Mesh

def tube_mesh(m, pts, rs, seg=24):                  # as in build_owner_v12.py
    pts = [Vector(p) for p in pts]
    start = len(m.v)
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(0, i - 1)]).normalized()
        a = t.cross(Vector((0, 1, 0))).normalized()
        b = t.cross(a)
        for j in range(seg):
            m.v.append(tuple(p + rs[i] * (a * math.cos(j * 2 * math.pi / seg) + b * math.sin(j * 2 * math.pi / seg))))
    for i in range(len(pts) - 1):
        for j in range(seg):
            a = start + i * seg + j
            b = start + i * seg + (j + 1) % seg
            m.f.append([a, b, b + seg, a + seg])
    m.f.append([start + j for j in range(seg)][::-1])
    m.f.append([start + (len(pts) - 1) * seg + j for j in range(seg)])

PALM_X = 0.481
for s in (-1, 1):
    m = Mesh()
    tube_mesh(m, [(s * .395, 0, 1.58), (s * .432, -.005, 1.40), (s * .458, -.025, 1.22), (s * .476, -.035, 1.07)], [.093, .085, .074, .058])
    m.ellipsoid((s * PALM_X, -.039, 1.015), (.067, .046, .098), seg=32, rings=20)
    for j in range(4):
        x = s * (.44 + j * .025)
        z = .965 - .008 * math.sin(j * math.pi / 3)
        tube_mesh(m, [(x, -.038, 1.00), (x, -.047, z), (x, -.065, z - .038)], [.016, .015, .012], 16)
        m.ellipsoid((x, -.065, z - .038), (.012, .013, .014), seg=16, rings=12)
    th = lambda x: s * (2 * PALM_X - x)              # v12 had s*x: the inner side
    tube_mesh(m, [(th(.43), -.048, 1.05), (th(.411), -.076, 1.02), (th(.415), -.087, .983)], [.023, .019, .014], 16)
    old = bpy.data.objects[f'Arm and hand {s}']
    new = m.build('_arm', bpy.context.scene.collection, (0.8, 0.6, 0.5), smooth=True)
    bpy.context.view_layer.objects.active = new
    new.select_set(True)
    for typ, kw in (('REMESH', {'mode': 'VOXEL', 'voxel_size': .007, 'use_smooth_shade': True}),
                    ('SMOOTH', {'factor': .65, 'iterations': 4})):
        q = new.modifiers.new(typ, typ)
        for k, v in kw.items():
            setattr(q, k, v)
        bpy.ops.object.modifier_apply(modifier=q.name)
    new.select_set(False)
    old_me = old.data
    new.data.materials.clear()
    for sl in old.material_slots:
        new.data.materials.append(sl.material)
    new.data.transform(old.matrix_world.inverted())
    old.data = new.data
    bpy.data.objects.remove(new)
    bpy.data.meshes.remove(old_me)

# ------------------------------------------------------------------ trousers: flat front, high crotch
# v12 fused an ellipsoid pelvis with two leg tubes: the ellipsoid stood proud of the legs at the front
# and hung round between them. Rebuild the trousers like tailored ones: a hip block with a flat front
# and rounder seat that ends level at the crotch, and two legs whose tops share that flat front (a
# D-shaped section, flat on the inner side) before rounding out into wide tubes lower down. The legs
# part straight below the hip block, so nothing hangs between them. Fused into one surface; seams and
# pockets are re-seated on the new cloth further down.
from mathutils.bvhtree import BVHTree
CROTCH_Z, Y0 = 0.92, 0.015
FRONT, SEAT = 0.167, 0.172                           # front / seat depth from Y0
def hip_rx(z):
    return float(np.interp(z, [0.86, 0.95, 1.05, 1.15, 1.30], [0.30, 0.315, 0.32, 0.31, 0.27]))
def hip_point(t, z):
    c, sn = math.cos(t), math.sin(t)
    x = hip_rx(z) * math.copysign(abs(c) ** (2 / 3.2), c)
    y = FRONT * abs(sn) ** (2 / 3.6) if sn < 0 else SEAT * abs(sn) ** (2 / 2.3)
    return x, Y0 + (y if sn >= 0 else -y)
def leg_section(z):
    """(x centre, y centre, x half-width, y half-width, superellipse exponent) of one leg at height z."""
    inner = 0.012
    top = ((inner + hip_rx(z)) / 2, Y0 + (SEAT - FRONT) / 2, (hip_rx(z) - inner) / 2, (SEAT + FRONT) / 2, 4.5)
    low = [(0.72, (.205, .012, .18, .18, 2.0)), (0.53, (.211, .008, .187, .187, 2.0)),
           (0.34, (.216, .022, .194, .194, 2.0)), (0.145, (.22, .025, .202, .202, 2.0))]
    if z >= 1.0:
        return top
    if z >= 0.53:                                    # a long, even flare from the hips: no kink at the thigh
        f = (1.0 - z) / 0.47
        f = f * (2 - f) * 0.5 + f * 0.5             # eases out a little towards the knee
        return tuple(a + (b - a) * f for a, b in zip(top, low[1][1]))
    for (z1, s1), (z2, s2) in zip(low[1:-1], low[2:]):
        if z >= z2:
            f = (z1 - z) / (z1 - z2)
            return tuple(a + (b - a) * f for a, b in zip(s1, s2))
    return low[-1][1]
def loft(m, rings):
    start, n = len(m.v), len(rings[0])
    for r in rings:
        m.v.extend(r)
    for k in range(len(rings) - 1):
        for i in range(n):
            a, b = start + k * n + i, start + k * n + (i + 1) % n
            m.f.append([a, b, b + n, a + n])
    m.f.append([start + i for i in range(n)][::-1])
    m.f.append([start + (len(rings) - 1) * n + i for i in range(n)])
jm = Mesh()
NT = 64
loft(jm, [[(*hip_point(2 * math.pi * i / NT, z), z) for i in range(NT)]
          for z in np.linspace(1.30, CROTCH_Z, 16)])
for sd in (-1, 1):
    rings = []
    for z in np.linspace(1.12, 0.145, 48):
        xc, yc, ax, ay, n = leg_section(z)
        ring = []
        for i in range(NT):
            t = 2 * math.pi * i / NT
            c, sn = math.cos(t), math.sin(t)
            ring.append((sd * (xc + ax * math.copysign(abs(c) ** (2 / n), c)), yc + ay * math.copysign(abs(sn) ** (2 / n), sn), z))
        rings.append(ring if sd > 0 else ring[::-1])
    loft(jm, rings)
old_j = bpy.data.objects['Jeans • continuous pelvis and legs']
def world_bvh(me, mw):
    return BVHTree.FromPolygons([mw @ v.co for v in me.vertices], [p.vertices for p in me.polygons])
OLD_JEANS = world_bvh(old_j.data, old_j.matrix_world)
new = jm.build('_jeans', bpy.context.scene.collection, (0.2, 0.3, 0.5), smooth=True)
bpy.context.view_layer.objects.active = new
new.select_set(True)
for typ, kw in (('REMESH', {'mode': 'VOXEL', 'voxel_size': .008, 'use_smooth_shade': True}),
                ('SMOOTH', {'factor': .65, 'iterations': 6})):
    q = new.modifiers.new(typ, typ)
    for k, v in kw.items():
        setattr(q, k, v)
    bpy.ops.object.modifier_apply(modifier=q.name)
new.select_set(False)
NEW_JEANS = world_bvh(new.data, new.matrix_world)
old_me = old_j.data
for sl in old_j.material_slots:
    new.data.materials.append(sl.material)
new.data.transform(old_j.matrix_world.inverted())
old_j.data = new.data
bpy.data.objects.remove(new)
bpy.data.meshes.remove(old_me)
# the fly: a J-stitch down one side that curves in to the centre seam, as on tailored trousers
bpy.data.objects['Jeans fly seam'].data.resolution_u = 4   # keeps its resolution: the J needs the curve
fly_cu = bpy.data.objects['Jeans fly seam'].data
fly_cu.splines.clear()
J_PTS = [(0.05, 1.12), (0.05, 1.03), (0.047, 0.985), (0.03, 0.955), (0.0, 0.945)]
fly = fly_cu.splines.new('BEZIER')
fly.bezier_points.add(len(J_PTS) - 1)
for bp, (x, z) in zip(fly.bezier_points, J_PTS):
    bp.co = (x, -0.3, z)
    bp.handle_left_type = bp.handle_right_type = 'AUTO'

dg = bpy.context.evaluated_depsgraph_get()

# ------------------------------------------------------------------ parts
# prefix: (subsurf levels, decimate ratio, weight group)
PARTS = {
    'Adapted brown iris': (None, 1.0, 'eye'), 'Adapted dark pupil': (None, 0.5, 'eye'),
    'Adapted eye highlight': (None, 1.0, 'eye'),
    'Face •': (None, 1.0, 'face'), 'Hair •': (None, 1.0, 'head'),
    'Round eyeglass rim': (None, 1.0, 'head'), 'Glasses': (None, 1.0, 'head'),
    'Arm and hand': (0, 0.2, 'arm'), 'Neck •': (0, 1.0, 'neck'),
    'Gray T-shirt': (1, 0.5, 'shirt'), 'Short sleeve': (1, 0.6, 'shirt'),
    'Crew-neck rib': (None, 1.0, 'shirt'), 'T-shirt hem stitch': (None, 1.0, 'shirt'),
    'Jeans • continuous': (0, 0.05, 'jeans'), 'Jeans': (None, 1.0, 'jeans'), 'Back pocket': (None, 1.0, 'jeans'),
    'Leg and foot': (0, 0.35, 'leg'), 'Slide padded strap': (1, 0.35, 'foot'), 'Slide sole': (1, 0.6, 'foot'),
}
def part(o):
    for k in sorted(PARTS, key=len, reverse=True):
        if o.name.startswith(k):
            return PARTS[k]
    raise KeyError(o.name)

for o in col.all_objects:
    if o.type == 'CURVE':                            # seams: square tubes; glasses: 8-sided
        glasses = o.name.startswith(('Round eyeglass', 'Glasses'))
        o.data.bevel_resolution = 1 if glasses else 0
        o.data.resolution_u = 2 if glasses else (4 if o.name.startswith('Jeans fly') else 1)
    if o.type in ('MESH', 'CURVE'):
        lv = part(o)[0]
        for m in o.modifiers:
            if m.type == 'SUBSURF' and lv is not None:
                m.levels = m.render_levels = lv

bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
pieces = []
for o in list(col.all_objects):
    if o.type not in ('MESH', 'CURVE'):
        continue
    _, ratio, grp = part(o)
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    me.transform(o.matrix_world)
    if o.type == 'CURVE':
        me.materials.clear()
        for s in o.material_slots:
            me.materials.append(s.material)
    bm = bmesh.new()
    bm.from_mesh(me)
    if o.name.startswith('Face •'):
        # the black arc above each eye is a loose piece of the face mesh (an upper lash strip):
        # removed (user, 10-21). Brows are higher (z > 2.3) and stay.
        img_ = next(n.image for n in bpy.data.materials['head'].node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
        iw_, ih_ = img_.size
        ipx_ = np.array(img_.pixels[:], dtype=np.float32).reshape(ih_, iw_, 4)
        uvl_ = bm.loops.layers.uv.active
        bm.faces.ensure_lookup_table()
        seen_, drop_ = set(), []
        for f in bm.faces:
            if f.index in seen_:
                continue
            isl, st = [], [f]
            seen_.add(f.index)
            while st:
                g = st.pop()
                isl.append(g)
                for e in g.edges:
                    for n in e.link_faces:
                        if n.index not in seen_:
                            seen_.add(n.index)
                            st.append(n)
            cols = [ipx_[min(ih_ - 1, int(l[uvl_].uv.y % 1 * ih_)), min(iw_ - 1, int(l[uvl_].uv.x % 1 * iw_)), :3]
                    for g in isl for l in g.loops]
            cz = sum(g.calc_center_median().z for g in isl) / len(isl)
            if np.mean(cols, 0).max() < 0.3 and 2.0 < cz < 2.3:
                drop_ += isl
        bmesh.ops.delete(bm, geom=drop_, context='FACES')
        print('LASH_ARC_REMOVED faces', len(drop_))
    if o.name.startswith('Leg and foot'):            # skin inside the jeans never shows
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z > 0.30], context='VERTS')
    if part(o)[2] == 'jeans' and not o.name.startswith('Jeans • continuous'):
        # seams, pockets and the fly keep their height above the cloth, measured on the old trousers
        fly_seam = o.name.startswith('Jeans fly')
        for v in bm.verts:
            lo, no, _, _ = OLD_JEANS.find_nearest(v.co)
            ln, nn, _, _ = NEW_JEANS.find_nearest(v.co)
            if lo is None or ln is None:
                continue
            h = 0.003 if fly_seam else (v.co - lo).dot(no)
            v.co = ln + nn * h
    if o.name.startswith('Arm and hand'):
        # turn v17's fists so the palms face the thighs and the thumbs point forward (so a forearm raised
        # forward holds its thumb up), fading the twist up the forearm so the wrist does not pinch
        sg = 1 if sum(v.co.x for v in bm.verts) > 0 else -1
        a, b = Vector((sg * 0.471, -0.032, 1.10)), Vector((sg * 0.478, -0.05, 0.92))
        axis = (b - a).normalized()
        for v in bm.verts:
            f = min(1.0, max(0.0, (1.22 - v.co.z) / (1.22 - 1.06)))
            f = f * f * (3 - 2 * f)
            if f > 0:
                R = Matrix.Rotation(math.radians(PALM_IN * sg * f), 3, axis)
                v.co = a + R @ (v.co - a)
    if ratio < 1.0:
        bm.to_mesh(me)
        bm.free()
        tmp = bpy.data.objects.new('_dec', me)
        bpy.context.scene.collection.objects.link(tmp)
        d = tmp.modifiers.new('d', 'DECIMATE')
        d.ratio = ratio
        d.use_collapse_triangulate = False
        dme = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
        bpy.data.objects.remove(tmp)
        bpy.data.meshes.remove(me)
        me = dme
        for s in o.material_slots:
            if s.material and s.material.name not in me.materials:
                me.materials.append(s.material)
    else:
        bm.to_mesh(me)
        bm.free()
    side = 'L' if sum(v.co.x for v in me.vertices) > 0 else 'R'
    no = bpy.data.objects.new('_' + o.name, me)
    no['grp'], no['side'] = grp, side
    me.calc_loop_triangles()
    bpy.context.scene.collection.objects.link(no)
    pieces.append(no)

# scale to metres, feet on the floor
M = Matrix.Diagonal((S, S, S, 1.0)) @ Matrix.Translation((0, 0, -Z0))
for o in pieces:
    o.data.transform(M)
def J(x, y, z):
    return Vector((x * S, y * S, (z - Z0) * S))

# ------------------------------------------------------------------ armature
# joints measured from v17 centrelines (v17 units); her left (+X) is .L
B = {   # name: (head, tail, parent)
    'Root': (J(0, 0.01, Z0), J(0, 0.25, Z0), None),
    'Hips': (J(0, 0.01, 0.98), J(0, 0.01, 1.15), 'Root'),
    'Spine': (J(0, 0.01, 1.15), J(0, 0.01, 1.40), 'Hips'),
    'Chest': (J(0, 0.01, 1.40), J(0, 0.02, 1.72), 'Spine'),
    'Neck': (J(0, 0.02, 1.72), J(0, 0.02, 1.86), 'Chest'),
    'Head': (J(0, 0.02, 1.86), J(0, 0.02, 2.70), 'Neck'),
}
for s, sg in (('L', 1), ('R', -1)):
    B.update({
        f'Eye.{s}': (J(sg * 0.209, -0.10, 2.138), J(sg * 0.209, -0.33, 2.138), 'Head'),
        f'Shoulder.{s}': (J(sg * 0.07, 0.0, 1.64), J(sg * 0.40, 0.0, 1.56), 'Chest'),
        f'UpperArm.{s}': (J(sg * 0.40, 0.0, 1.56), J(sg * 0.443, -0.014, 1.33), f'Shoulder.{s}'),
        f'ForeArm.{s}': (J(sg * 0.443, -0.014, 1.33), J(sg * 0.471, -0.032, 1.10), f'UpperArm.{s}'),
        f'Hand.{s}': (J(sg * 0.471, -0.032, 1.10), J(sg * 0.478, -0.05, 0.92), f'ForeArm.{s}'),
        f'UpLeg.{s}': (J(sg * 0.18, 0.015, 0.90), J(sg * 0.187, 0.0, 0.52), 'Hips'),
        f'Leg.{s}': (J(sg * 0.187, 0.0, 0.52), J(sg * 0.193, 0.022, 0.19), f'UpLeg.{s}'),
        f'Foot.{s}': (J(sg * 0.193, 0.022, 0.19), J(sg * 0.194, -0.15, 0.07), f'Leg.{s}'),
        f'Toe.{s}': (J(sg * 0.194, -0.15, 0.07), J(sg * 0.194, -0.235, 0.06), f'Foot.{s}'),
    })
arm_d = bpy.data.armatures.new('Owner_Rig')
rig = bpy.data.objects.new('Owner_Rig', arm_d)
out_col = bpy.data.collections.new('Owner_V18')
bpy.context.scene.collection.children.link(out_col)
out_col.objects.link(rig)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='EDIT')
for n, (h, t, par) in B.items():
    eb = arm_d.edit_bones.new(n)
    eb.head, eb.tail = h, t
    eb.roll = 0.0
    if par:
        eb.parent = arm_d.edit_bones[par]
        eb.use_connect = (eb.parent.tail - h).length < 1e-4
    eb.use_deform = n != 'Root'
bpy.ops.object.mode_set(mode='OBJECT')

# ------------------------------------------------------------------ weights
def seg_dist(p, a, b):
    ab = b - a
    t = np.clip(((p - a) @ ab) / (ab @ ab), 0, 1)
    return np.linalg.norm(p - (a + t[:, None] * ab), axis=1)

CAND = {
    'arm': lambda s: [f'Shoulder.{s}', f'UpperArm.{s}', f'ForeArm.{s}', f'Hand.{s}'],
    'shirt': lambda s: ['Hips', 'Spine', 'Chest', 'Shoulder.L', 'Shoulder.R', 'UpperArm.L', 'UpperArm.R'],
    'neck': lambda s: ['Chest', 'Neck', 'Head'],
    'jeans': lambda s: ['Hips', 'Spine', 'UpLeg.L', 'Leg.L', 'UpLeg.R', 'Leg.R'],
    'leg': lambda s: [f'UpLeg.{s}', f'Leg.{s}', f'Foot.{s}', f'Toe.{s}'],
    'foot': lambda s: [f'Foot.{s}', f'Toe.{s}'],
}
SIGMA = 0.012                                       # m; joint blend width
# gaze moves only the pupil inside the iris: the face texture has another eye painted under the
# iris disc, so the iris and its highlight stay on Head
RIGID = {'head': lambda o: 'Head', 'face': lambda o: 'Head',
         'eye': lambda o: f"Eye.{o['side']}" if 'pupil' in o.name else 'Head'}
for o in pieces:
    g, s = o['grp'], o['side']
    co = np.array([v.co for v in o.data.vertices])
    if g in RIGID:
        vg = o.vertex_groups.new(name=RIGID[g](o))
        vg.add(range(len(co)), 1.0, 'REPLACE')
        continue
    names = CAND[g](s)
    D = np.stack([seg_dist(co, np.array(B[n][0]), np.array(B[n][1])) for n in names], 1)
    if g == 'shirt':                                # the sleeves follow the arm, the body the spine
        D[:, 5] += np.where(co[:, 0] > 0, 0, 1)
        D[:, 6] += np.where(co[:, 0] < 0, 0, 1)
        D[:, 3] += np.where(co[:, 0] > 0, 0, 1)
        D[:, 4] += np.where(co[:, 0] < 0, 0, 1)
        if not o.name.startswith('_Short sleeve'):
            # the shirt body hangs from the chest: below the armpit no arm bone may lift its hem
            # (the arms swinging forward to sit or read pulled the side seams up off the jeans)
            below = np.maximum(0.0, (1.50 - Z0) * S - co[:, 2])
            D[:, 3:7] += 1.5 * below[:, None]
    if g == 'jeans':                                # each trouser leg follows its own leg below the crotch
        crotch = (CROTCH_Z - Z0) * S
        low = co[:, 2] < crotch
        D[:, 2:4] += np.where(low & (co[:, 0] < 0), 1, 0)[:, None]
        D[:, 4:6] += np.where(low & (co[:, 0] > 0), 1, 0)[:, None]
        # above the hip joints the cloth (seat, waist, back pockets) belongs to the pelvis: when a
        # thigh lifts to sit, it must not swing the seat up out of the T-shirt
        above = np.maximum(0.0, co[:, 2] - (0.90 - Z0) * S)
        D[:, 2:6] += 1.5 * above[:, None]
    W = np.exp(-(D - D.min(1, keepdims=True)) / SIGMA)
    W[W < 0.02] = 0
    if W.shape[1] > 4:                              # glTF skins carry 4 influences per vertex
        W[W < np.sort(W, 1)[:, -4:-3]] = 0
    W /= W.sum(1, keepdims=True)
    if g == 'jeans':
        # the seat: from the pelvis at the top to the thigh at the gluteal fold, blended evenly over
        # the whole buttock, so a seated bottom rounds over from the back onto the thigh instead of
        # folding at one line (all-pelvis made a box, all-thigh flipped the seat up)
        z_hi, z_lo = 0.46, 0.31                       # m: pelvis above, thigh below
        u = np.clip((z_hi - co[:, 2]) / (z_hi - z_lo), 0, 1)
        u = u * u * (3 - 2 * u)
        back = np.clip((co[:, 1] - 0.0) / 0.035, 0, 1)   # fades in behind the hip joints
        seat = (back > 0) & (co[:, 2] > z_lo - 0.02) & (co[:, 2] < z_hi + 0.02)
        leg = np.where(co[:, 0] >= 0, 2, 4)          # UpLeg.L / UpLeg.R column
        for i in np.nonzero(seat)[0]:
            wl = u[i] * back[i] + W[i, leg[i]] * (1 - back[i])
            row = W[i] * (1 - back[i])
            row[0] += back[i] * (1 - u[i])
            row[leg[i]] = wl
            row[[3, 5]] *= (1 - back[i])
            W[i] = row / row.sum()
    for k, n in enumerate(names):
        vg = o.vertex_groups.new(name=n)
        for i in np.nonzero(W[:, k])[0]:
            vg.add([int(i)], float(W[i, k]), 'REPLACE')

# ------------------------------------------------------------------ painted irises
# In the source the pupil and highlight are separate discs stacked against the curved iris dome, so
# what shows is where they cut through it: seen at an angle or up close the shapes break and slide.
# Paint them into the iris instead: from straight ahead, every texel of a planar map over the iris
# records whether the source showed pupil, highlight or iris there (the look stays as approved), the
# iris gets that image, and the pupil and highlight discs are removed. One surface, nothing to cut.
EYE_RES = 512
_face = next(o for o in pieces if o['grp'] == 'face')
TONED = np.array(toned.pixels[:], dtype=np.float32).reshape(fh, fw, 4)
FACE_UV = np.zeros((len(_face.data.vertices), 2))
_cnt = np.zeros(len(_face.data.vertices))
for l in _face.data.loops:
    FACE_UV[l.vertex_index] += _face.data.uv_layers.active.data[l.index].uv
    _cnt[l.vertex_index] += 1
FACE_UV /= np.maximum(_cnt, 1)[:, None]
import mathutils
_fm = _face.data
_fm.calc_loop_triangles()
FACE_CO = np.array([v.co for v in _fm.vertices])
FACE_TRIS = [(tuple(t.vertices), tuple(tuple(_fm.uv_layers.active.data[l].uv) for l in t.loops)) for t in _fm.loop_triangles]
FACE_TRI_BVH = BVHTree.FromPolygons([v.co.copy() for v in _fm.vertices], [t[0] for t in FACE_TRIS])
FACE_BVH = BVHTree.FromPolygons([v.co.copy() for v in _face.data.vertices], [p.vertices for p in _face.data.polygons])
def face_texel(x, z):
    hit = FACE_TRI_BVH.ray_cast(Vector((x, -1.0, z)), Vector((0, 1, 0)))
    if hit[0] is None:
        return None
    t = FACE_TRIS[hit[2]]
    bary = mathutils.geometry.barycentric_transform(hit[0], *[Vector(FACE_CO[i]) for i in t[0]],
                                                    Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))
    u = sum(t[1][k][0] * bary[k] for k in range(3))
    w = sum(t[1][k][1] * bary[k] for k in range(3))
    return TONED[min(fh - 1, int(w % 1 * fh)), min(fw - 1, int(u % 1 * fw)), :3]
def mat_rgb(name):
    return np.array(bpy.data.materials[name].node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value[:3])
to_srgb8 = lambda c: np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(np.clip(c, 0, None), 1 / 2.4) - 0.055)
for s_ in ('L', 'R'):
    iris_o = next(o for o in pieces if o.name.startswith('_Adapted brown iris') and o['side'] == s_)
    layers = [(iris_o, mat_rgb('Iris • dark brown'))]
    for prefix, mname in (('_Adapted dark pupil', 'Pupil and lashes'), ('_Adapted eye highlight', 'Eye whites')):
        layers.append((next(o for o in pieces if o.name.startswith(prefix) and o['side'] == s_), mat_rgb(mname)))
    verts, tris, owner = [], [], []
    for k, (o, _) in enumerate(layers):
        i0 = len(verts)
        verts += [v.co.copy() for v in o.data.vertices]
        for p in o.data.polygons:
            tris.append([i0 + i for i in p.vertices])
            owner.append(k)
    eb = BVHTree.FromPolygons(verts, tris)
    ic = np.array([v.co for v in iris_o.data.vertices])
    x0, x1, z0, z1 = ic[:, 0].min(), ic[:, 0].max(), ic[:, 2].min(), ic[:, 2].max()
    img_px = np.zeros((EYE_RES, EYE_RES, 4), np.float32)
    img_px[..., 3] = 1
    for r in range(EYE_RES):
        z = z0 + (r + 0.5) / EYE_RES * (z1 - z0)
        for c in range(EYE_RES):
            x = x0 + (c + 0.5) / EYE_RES * (x1 - x0)
            hit = eb.ray_cast(Vector((x, -1.0, z)), Vector((0, 1, 0)))
            img_px[r, c, :3] = layers[owner[hit[2]] if hit[0] is not None else 0][1]
            fc = face_texel(x, z)
            img_px[r, c, 3] = 1.0 if fc is not None and fc[1] > 0.9 and fc[2] > 0.9 else 0.0
    img_px[..., :3] = to_srgb8(img_px[..., :3])
    eye_img = bpy.data.images.new(f'Iris painted {s_}', EYE_RES, EYE_RES)
    eye_img.pixels.foreach_set(img_px.ravel())
    eye_img.pack()
    em = bpy.data.materials.new(f'Iris • painted {s_}')
    em.use_nodes = True
    nt = em.node_tree
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = eye_img
    src = bpy.data.materials['Iris • dark brown'].node_tree.nodes['Principled BSDF']
    bs = nt.nodes['Principled BSDF']
    bs.inputs['Roughness'].default_value = 1.0       # matte: a lamp's own glint would wander over
    bs.inputs['Specular IOR Level'].default_value = 0.0   # the painted eye as the view changes
    nt.links.new(tex.outputs['Color'], bs.inputs['Base Color'])
    rnd = nt.nodes.new('ShaderNodeMath')               # hard-edged mask (glTF alpha MASK)
    rnd.operation = 'ROUND'
    nt.links.new(tex.outputs['Alpha'], rnd.inputs[0])
    nt.links.new(rnd.outputs[0], bs.inputs['Alpha'])
    if hasattr(em, 'blend_method'):
        em.blend_method = 'CLIP'
    me_i = iris_o.data
    me_i.materials.clear()
    me_i.materials.append(em)
    uvl = me_i.uv_layers.new(name='UVMap')
    for l in me_i.loops:
        co = me_i.vertices[l.vertex_index].co
        uvl.data[l.index].uv = ((co.x - x0) / (x1 - x0), (co.z - z0) / (z1 - z0))
    for o, _ in layers[1:]:
        pieces.remove(o)
        bpy.data.objects.remove(o)
    # The source iris is a dome standing in front of the face: from the side it bulged out of the eye.
    # Lay it 1.5 mm in front of the face's eye surface, like a decal; the mask above shows it only
    # over the painted eye white, so its edge follows the eye opening.
    # finer mesh first, so the line where the skin cuts across the iris top is smooth
    bm_i = bmesh.new()
    bm_i.from_mesh(me_i)
    bmesh.ops.subdivide_edges(bm_i, edges=bm_i.edges[:], cuts=1, use_grid_fill=True)
    bm_i.to_mesh(me_i)
    bm_i.free()
    moved = 0
    # Only over the eye white does it come in front; elsewhere (the steep top of the socket, skin) it
    # goes behind the face, so seen from below or the side the skin covers it instead of the iris
    # being stretched over the socket wall.
    for v in me_i.vertices:
        hit = FACE_TRI_BVH.ray_cast(Vector((v.co.x, -1.0, v.co.z)), Vector((0, 1, 0)))
        if hit[0] is not None:
            # share of eye white around the vertex (within 2 mm) eases it from in front to behind,
            # so the skin cuts the iris along a smooth line rather than in steps
            n_w = n_all = 0
            for dx in (-0.002, -0.001, 0, 0.001, 0.002):
                for dz in (-0.002, -0.001, 0, 0.001, 0.002):
                    fc = face_texel(v.co.x + dx, v.co.z + dz)
                    n_all += 1
                    n_w += fc is not None and fc[1] > 0.9 and fc[2] > 0.9
            w_ = min(1.0, n_w / n_all * 2)                 # half white around is already fully in front
            v.co.y = hit[0].y - 0.0015 * w_ + 0.004 * (1 - w_)
            moved += 1
    me_i.update()
    print('IRIS_TUCK', s_, moved, 'of', len(me_i.vertices))

# ------------------------------------------------------------------ eyelids
# Closing the face itself folds the recessed sockets, so each eye gets its own lid: a skin-coloured
# sheet conformed just in front of the face and iris over the eye white. In the basis it is gathered into a thin band tucked behind the skin at the upper lid;
# Blink.<side> unrolls it down to the lower lid. Its vertices are rigid on Head.
from mathutils.bvhtree import BVHTree
surf_v, surf_f = [], []
for o in pieces:
    if o['grp'] in ('face', 'eye'):
        i0 = len(surf_v)
        surf_v += [v.co.copy() for v in o.data.vertices]
        surf_f += [[i0 + i for i in p.vertices] for p in o.data.polygons]
SURF = BVHTree.FromPolygons(surf_v, surf_f)
head_m = next(o for o in pieces if o['grp'] == 'face').data.materials[0]
img = next(n.image for n in head_m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image and n.image.colorspace_settings.name == 'sRGB')
skin_rgb = [0.92 * c ** 2.2 for c in img.pixels[(int(img.size[1] * 0.25) * img.size[0] + int(img.size[0] * 0.25)) * 4:][:3]]
lid_m = bpy.data.materials.new('Eyelid • face skin')
lid_m.use_nodes = True
bs = lid_m.node_tree.nodes['Principled BSDF']
bs.inputs['Base Color'].default_value = (*skin_rgb, 1)
bs.inputs['Roughness'].default_value = 0.6                  # matte: a glossy lid reads as a bubble
NX, NZ = 18, 13
LID_TARGET = {}
for s, sg in (('L', 1), ('R', -1)):
    iris = next(o for o in pieces if o.name.startswith('_Adapted brown iris') and o['side'] == s)
    ic = np.array([v.co for v in iris.data.vertices])
    cx, cz = ic[:, 0].mean(), (ic[:, 2].min() + ic[:, 2].max()) / 2
    # the lid covers the painted eye white, which is larger than the iris (lower and wider):
    # per column, its top and bottom edges from the face texture, with a little overlap
    hx0, hz0 = np.ptp(ic[:, 0]), np.ptp(ic[:, 2])
    zs_ = np.arange(cz - 1.2 * hz0, cz + 1.2 * hz0, 0.0005)
    cols_ = []
    for x in np.arange(cx - 1.2 * hx0, cx + 1.2 * hx0, 0.0005):
        wz = [z for z in zs_ if (lambda c: c is not None and c[1] > 0.9 and c[2] > 0.9)(face_texel(x, z))]
        if wz:
            cols_.append((x, min(wz), max(wz)))
    cols_ = np.array(cols_)
    wx0, wx1 = cols_[:, 0].min() - 0.004, cols_[:, 0].max() + 0.004
    def white_span(x):
        lo = np.interp(x, cols_[:, 0], cols_[:, 1])
        hi = np.interp(x, cols_[:, 0], cols_[:, 2])
        edge = min(1.0, (x - wx0) / 0.003, (wx1 - x) / 0.003)   # close smoothly at the corners
        mid = (lo + hi) / 2
        return mid + (hi + 0.0015 - mid) * edge, mid + (lo - 0.002 - mid) * edge
    full, base, ys = [], [], np.zeros((NZ, NX))
    for j in range(NZ):
        t = j / (NZ - 1)
        for i in range(NX):
            u = -1 + 2 * i / (NX - 1)
            x = wx0 + (wx1 - wx0) * (u + 1) / 2
            zt, zb = white_span(x)
            z = zt + (zb - zt) * t
            hit = SURF.ray_cast(Vector((x, -1.0, z)), Vector((0, 1, 0)))
            ys[j, i] = hit[0].y if hit[0] else -0.15
            ht = SURF.ray_cast(Vector((x, -1.0, zt)), Vector((0, 1, 0)))
            yt = ht[0].y + 0.03 if ht[0] else ys[j, i] + 0.03     # folded deep inside the head while open
            full.append([x, 0.0, z])
            base.append((x, yt, zt))                       # folded flat: nothing left to see
    # keep the sheet in front of everything between the samples too (highlight dots, socket rim):
    # take the frontmost depth around each sample, then smooth it so the lid reads as one soft curve
    pad = np.pad(ys, 1, mode='edge')
    front = np.min([pad[a:a + NZ, b:b + NX] for a in range(3) for b in range(3)], axis=0)
    for _ in range(3):
        pad = np.pad(front, 1, mode='edge')
        front = np.minimum(front, (pad[:-2, 1:-1] + pad[2:, 1:-1] + pad[1:-1, :-2] + pad[1:-1, 2:] + 4 * front) / 8)
    # the upper arc and the eye corners lie on the skin around the opening: there the sheet sinks
    # flush into the face; the lower edge (the lash line) stays in front
    for j in range(NZ):
        for i in range(NX):
            u, t = -1 + 2 * i / (NX - 1), j / (NZ - 1)
            rho = max(abs(u), 1 - t / 0.25)
            rim = np.clip((rho - 0.7) / 0.3, 0, 1) ** 2
            full[j * NX + i][1] = (front[j, i] - 0.003) * (1 - rim) + (ys[j, i] + 0.0004) * rim
    faces = [(j * NX + i, j * NX + i + 1, (j + 1) * NX + i + 1, (j + 1) * NX + i)
             for j in range(NZ - 1) for i in range(NX - 1)]
    lme = bpy.data.meshes.new(f'Eyelid {s}')
    lme.from_pydata(base, [], faces)
    lme.materials.append(lid_m)                       # plain skin, no lash line (user, 10-21)
    lo = bpy.data.objects.new(f'_Eyelid {s}', lme)
    bpy.context.scene.collection.objects.link(lo)
    lo['grp'], lo['side'] = 'lid', s
    lo.vertex_groups.new(name='Head').add(range(len(base)), 1.0, 'REPLACE')
    lo.vertex_groups.new(name=f'_lid_{s}').add(range(len(base)), 1.0, 'REPLACE')
    LID_TARGET[s] = np.array(full)
    pieces.append(lo)

# ------------------------------------------------------------------ join
bpy.ops.object.select_all(action='DESELECT')
for o in pieces:
    o.select_set(True)
body = pieces[[o['grp'] for o in pieces].index('face')]
bpy.context.view_layer.objects.active = body
bpy.ops.object.join()
body.name = body.data.name = 'Owner_Body'
for k in ('grp', 'side'):
    if k in body:
        del body[k]
out_col.objects.link(body)
bpy.context.scene.collection.objects.unlink(body)
me = body.data
for p in me.polygons:
    p.use_smooth = True
# the source textures wire their (all-opaque) alpha into Alpha; glTF then exports BLEND, and the web
# renderer stops writing depth for the face, so the red mouth / cheek faces inside show through
for m in me.materials:
    for l in list(m.node_tree.links) if m and m.node_tree else []:
        if l.to_socket.name == 'Alpha' and l.from_node.type == 'TEX_IMAGE':
            m.node_tree.links.remove(l)
body.parent = rig
mod = body.modifiers.new('Armature', 'ARMATURE')
mod.object = rig

# ------------------------------------------------------------------ blink shape keys
def members(name):
    idx = body.vertex_groups[name].index
    return np.array([v.index for v in me.vertices if any(g.group == idx for g in v.groups)], int)

body.shape_key_add(name='Basis', from_mix=False)
report = {}
for s in ('L', 'R'):
    k = body.shape_key_add(name=f'Blink.{s}', from_mix=False)
    k.value = 0.0                                    # Blender 5 creates new keys at 1.0
    d = np.array([p.co for p in k.data])
    v = members(f'_lid_{s}')                         # join keeps each piece's vertex order
    d[v] = LID_TARGET[s]
    k.data.foreach_set('co', d.ravel())
    report[f'Blink.{s}'] = {'lid_verts': int(len(v))}
for vg in list(body.vertex_groups):
    if vg.name.startswith('_lid_'):
        body.vertex_groups.remove(vg)

# ------------------------------------------------------------------ clean up and save
for o in list(col.all_objects):
    if o.type in ('MESH', 'CURVE', 'EMPTY'):
        bpy.data.objects.remove(o, do_unlink=True)
bpy.data.collections.remove(col)
for c in (bpy.data.meshes, bpy.data.curves, bpy.data.materials):
    for d in list(c):
        if d.users == 0:
            c.remove(d)
body['source'] = ('Head and hair: Cute Chibi Girl by Syed’s Creation (Dawood3D), CC BY 4.0, '
                  'https://sketchfab.com/3d-models/cute-chibi-girl-c42960a64f7c4cd89706e79da4d04de0; '
                  'modified: hair recoloured, registered to an original body; decimated and rigged')
me.calc_loop_triangles()
report.update({'scale': S, 'height_m': round(max(v.co.z for v in me.vertices), 3), 'vertices': len(me.vertices),
               'triangles': len(me.loop_triangles), 'materials': len(me.materials), 'bones': len(arm_d.bones)})
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=DST)
print('OWNER_V18_RIG', json.dumps(report))
