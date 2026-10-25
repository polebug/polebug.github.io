"""Owner v18 actions (2026-10-21), keyed by script on Owner_Rig, then exported with the mesh.

    Blender -b assets/blender/characters/owner-character-v18.blend --python assets/blender/scripts/animate_owner_v18.py

Actions (30 fps, bones only, no root motion; the web code moves and turns the character):
  Idle      90 f loop  standing, breathing
  Walk      30 f loop  in place, about 0.55 m per cycle (move the root ~0.55 m/s)
  SitDown   36 f       hop back onto a seat; StandUp 36 f slides off it again
  SitRead  180 f loop  book held in both hands, a page turn at ~4 s (prop "Book", shown by the web code)
  SitType   60 f loop  fists tapping a keyboard about 0.18 m above the seat, 0.27 m in front of the root
  SofaSit  180 f loop  leaning back, legs stretched along the cushion, feet wiggling
  Sleep    150 f loop  lying on the back, breathing; the web code holds Blink.L/R at 1
Seated actions assume a seat 0.44 m high with the root on the floor at the seat's front edge,
facing away from the backrest; for another seat height raise or lower the root by the difference
(sofa 0.38 m: -0.06, desk chair 0.50 m: +0.06). Sleep puts the back on the root plane (mattress).

Angles are written in body axes and converted per bone: X = her left, Y = her back, Z = up.
"""
import bpy, math, os, json
from mathutils import Euler, Matrix, Quaternion, Vector

P = '/Users/bugpole/AI/博客陪伴小屋'
FPS = 30
SEAT = 0.44
rig = bpy.data.objects['Owner_Rig']
body = bpy.data.objects['Owner_Body']
sc = bpy.context.scene
sc.render.fps = FPS
for a in list(bpy.data.actions):                       # re-runnable: drop the previous take
    bpy.data.actions.remove(a)
pb = rig.pose.bones
for b in pb:
    b.rotation_mode = 'QUATERNION'
REST = {b.name: b.bone.matrix_local.to_3x3() for b in pb}

# ------------------------------------------------------------------ pose helpers (body axes, degrees)
def fwd(d):  return (-d, 0, 0)        # limb pointing down swings forward (also elbow / knee forward)
def back(d): return (d, 0, 0)         # limb swings back; for Leg / ForeArm-less joints: knee bend
def lean(d): return (d, 0, 0)         # bone pointing up leans forward (spine, neck, head nod)
def yaw(d):  return (0, 0, d)         # turn to her left
def tilt(d): return (0, d, 0)         # top towards her left shoulder
def abd(side, d): return (0, -d if side == 'L' else d, 0)   # arm / leg out sideways
def twist(side, d): return (0, 0, 0, d if side == 'L' else -d)  # about the bone's own axis (+ is the left hand's clockwise roll seen from the elbow)
def add(*rs): return tuple(sum(r[i] if i < len(r) else 0 for r in rs) for i in range(4))

def to_basis(bone, e):
    q = Euler([math.radians(a) for a in e[:3]], 'XYZ').to_quaternion()
    R = REST[bone]
    b = (R.inverted() @ q.to_matrix() @ R).to_quaternion()
    if len(e) > 3 and e[3]:
        b = b @ Quaternion((0, 1, 0), math.radians(e[3]))
    return b

PREV = {}
def key(frame, pose, hips=(0, 0, 0)):
    """Set every bone (unlisted bones go back to rest) and key it."""
    for b in pb:
        q = to_basis(b.name, pose.get(b.name, (0, 0, 0, 0)))
        if b.name in PREV and PREV[b.name].dot(q) < 0:
            q.negate()                                   # keep quaternions on one hemisphere
        PREV[b.name] = q
        b.rotation_quaternion = q
        b.location = (0, 0, 0)
        b.keyframe_insert('rotation_quaternion', frame=frame)
    h = pb['Hips']
    h.location = REST['Hips'].inverted() @ Vector(hips)
    h.keyframe_insert('location', frame=frame)
    for b in pb:
        if b.name != 'Hips':
            b.keyframe_insert('location', frame=frame)

def action(name, frames):
    PREV.clear()
    a = bpy.data.actions.new(name)
    a.use_fake_user = True
    rig.animation_data_create()
    rig.animation_data.action = a
    for f, pose, hips in frames:
        key(f, pose, hips)
    a.frame_range = (frames[0][0], frames[-1][0])
    a['loop'] = frames[0][0] != frames[-1][0] and name not in ('SitDown', 'StandUp')
    return a

def mirror(pose):
    out = {}
    for n, e in pose.items():
        m = n.replace('.L', '.T').replace('.R', '.L').replace('.T', '.R')
        out[m] = (e[0], -e[1], -e[2]) + tuple(-t for t in e[3:])
    return out

def mix(a, b, t):
    keys = set(a) | set(b)
    pad = lambda e: tuple(e) + (0,) * (4 - len(e))
    return {k: tuple(pad(a.get(k, ()))[i] * (1 - t) + pad(b.get(k, ()))[i] * t for i in range(4)) for k in keys}

# ------------------------------------------------------------------ base poses
REST_ARMS = {'UpperArm.L': abd('L', 4), 'UpperArm.R': abd('R', 4), 'ForeArm.L': fwd(6), 'ForeArm.R': fwd(6)}
STAND = dict(REST_ARMS)
# seated: the hip joints sit 5 cm above a 0.44 m seat (8 cm above their standing height), 5 cm back
HIP_SIT = (0, 0.05, SEAT + 0.05 - 0.407)
SIT = {'UpLeg.L': add(fwd(88), abd('L', 4)), 'UpLeg.R': add(fwd(88), abd('R', 4)),
       'Leg.L': back(84), 'Leg.R': back(84), 'Foot.L': fwd(6), 'Foot.R': fwd(6),
       'Spine': lean(4), 'Chest': lean(2),
       'UpperArm.L': add(fwd(22), abd('L', 2)), 'UpperArm.R': add(fwd(22), abd('R', 2)),
       'ForeArm.L': fwd(38), 'ForeArm.R': fwd(38), 'Hand.L': fwd(-8), 'Hand.R': fwd(-8)}

PELVIS = 14.0
def seated(pose, k=1.0):
    """Sitting tips the pelvis back (as people do); spine and thighs take the angle back, so the
    pose looks the same but the hip bends less and the seat stays round instead of creasing."""
    p = dict(pose)
    d = PELVIS * k
    p['Hips'] = add(p.get('Hips', (0, 0, 0)), lean(-d))
    p['Spine'] = add(p.get('Spine', (0, 0, 0)), lean(d))
    for sd in ('L', 'R'):
        p[f'UpLeg.{sd}'] = add(p.get(f'UpLeg.{sd}', (0, 0, 0)), fwd(-d))
    return p

def loop(n, fn, step=3):
    return [(f, *fn(f / n * math.tau)) for f in range(0, n + 1, step)]


# ------------------------------------------------------------------ Idle
def idle(t):
    b = math.sin(t)
    return ({**STAND, 'Spine': lean(0.6 * b), 'Chest': lean(1.2 * b), 'Neck': lean(-0.6 * b),
             'Head': add(yaw(3 * math.sin(t + 1)), tilt(1.5 * math.sin(2 * t))),
             'UpperArm.L': abd('L', 4 + 0.8 * b), 'UpperArm.R': abd('R', 4 + 0.8 * b)},
            (0, 0, 0.002 * b))
action('Idle', loop(90, idle))

# ------------------------------------------------------------------ Walk (contact L at 0, contact R at 15)
def walk(t):
    s, c = math.sin(t), math.cos(t)
    def leg(side, ph):
        sw = math.cos(ph)                              # +1 = this leg forward (contact)
        lift = max(0.0, math.sin(ph - 0.3))            # knee lifts while the leg swings through
        return {f'UpLeg.{side}': fwd(24 * sw + 10 * lift), f'Leg.{side}': back(6 + 42 * lift + 8 * max(0, -sw)),
                f'Foot.{side}': fwd(-10 * max(0, sw) + 18 * max(0, -sw) * (1 - lift)),
                f'Toe.{side}': fwd(-16 * max(0, -sw) * (1 - lift))}
    pose = {**leg('L', t), **leg('R', t + math.pi),
            'Hips': add(yaw(-5 * c), tilt(3 * s)), 'Spine': add(lean(3), yaw(4 * c)), 'Chest': yaw(2 * c),
            'Neck': yaw(-1 * c), 'Head': add(lean(-2), tilt(-2 * s)),
            'UpperArm.L': add(fwd(-18 * c), abd('L', 6)), 'UpperArm.R': add(fwd(18 * c), abd('R', 6)),
            'ForeArm.L': fwd(18 + 10 * max(0, -c)), 'ForeArm.R': fwd(18 + 10 * max(0, c))}
    return pose, (0, 0, -0.012 + 0.010 * abs(s))       # down at each contact, up when passing
action('Walk', loop(30, walk, step=1))

# ------------------------------------------------------------------ SitDown / StandUp
CROUCH = {**STAND, 'UpLeg.L': fwd(30), 'UpLeg.R': fwd(30), 'Leg.L': back(48), 'Leg.R': back(48),
          'Foot.L': fwd(-14), 'Foot.R': fwd(-14), 'Spine': lean(16), 'Chest': lean(6),
          'UpperArm.L': fwd(-18), 'UpperArm.R': fwd(-18)}
HOP = {'UpLeg.L': fwd(60), 'UpLeg.R': fwd(60), 'Leg.L': back(70), 'Leg.R': back(70),
       'Foot.L': fwd(18), 'Foot.R': fwd(18), 'Spine': lean(8),
       'UpperArm.L': add(fwd(30), abd('L', 14)), 'UpperArm.R': add(fwd(30), abd('R', 14)),
       'ForeArm.L': fwd(30), 'ForeArm.R': fwd(30)}
LAND = {**SIT, 'Leg.L': back(96), 'Leg.R': back(96), 'Spine': lean(-4), 'Chest': lean(-2), 'Head': lean(6),
        'UpperArm.L': add(fwd(30), abd('L', 10)), 'UpperArm.R': add(fwd(30), abd('R', 10))}
action('SitDown', [(0, STAND, (0, 0, 0)), (8, CROUCH, (0, 0.01, -0.05)),
                   (16, seated(HOP, 0.5), (0, 0.05, HIP_SIT[2] + 0.04)), (24, seated(LAND), (0, 0.05, HIP_SIT[2] - 0.006)),
                   (36, seated(SIT), HIP_SIT)])
SCOOT = {**SIT, 'Spine': lean(26), 'Chest': lean(8), 'Head': lean(-10), 'Leg.L': back(70), 'Leg.R': back(70),
         'UpperArm.L': add(fwd(10), abd('L', 18)), 'UpperArm.R': add(fwd(10), abd('R', 18)), 'ForeArm.L': fwd(20), 'ForeArm.R': fwd(20)}
action('StandUp', [(0, seated(SIT), HIP_SIT), (10, seated(SCOOT), (0, 0.03, HIP_SIT[2] + 0.005)),
                   (20, mix(SCOOT, CROUCH, 0.7), (0, -0.01, -0.03)), (28, CROUCH, (0, 0.0, -0.04)),
                   (36, STAND, (0, 0, 0))])

# ------------------------------------------------------------------ SitRead
READ = {**SIT, 'Spine': lean(6), 'Chest': lean(4), 'Neck': lean(6), 'Head': lean(12),
        # forearms level and reaching forward, upper arms turned inward: palm-in fists grip the
        # book's sides with the thumbs on top
        'UpperArm.L': add(fwd(12), abd('L', -2), yaw(-36)), 'UpperArm.R': add(fwd(12), abd('R', -2), yaw(36)),
        'ForeArm.L': fwd(84), 'ForeArm.R': fwd(84),
        'Hand.L': fwd(-4), 'Hand.R': fwd(-4)}
def read(t):
    f = t / math.tau * 180
    b = math.sin(t * 3)                                 # three breaths per loop
    pose = {**READ, 'Chest': lean(4 + 1.0 * b), 'Head': add(lean(12 + 1.5 * math.sin(t)), yaw(2 * math.sin(2 * t)))}
    turn = max(0.0, math.sin(math.pi * (f - 118) / 30)) if 118 <= f <= 148 else 0.0   # page turn
    pose['UpperArm.R'] = add(fwd(12 + 8 * turn), abd('R', -2), yaw(36 + 16 * turn))   # sweeps across the page
    pose['ForeArm.R'] = add(fwd(84 + 10 * turn), twist('R', 40 * turn))
    pose['Hand.R'] = fwd(-4 - 16 * turn)
    return seated(pose), (HIP_SIT[0], HIP_SIT[1], HIP_SIT[2] + 0.002 * b)
action('SitRead', loop(180, read, step=3))

# ------------------------------------------------------------------ SitType
TYPE = {**SIT, 'Spine': lean(12), 'Chest': lean(4), 'Neck': lean(-4), 'Head': lean(6),
        'UpperArm.L': add(fwd(50), abd('L', -8)), 'UpperArm.R': add(fwd(50), abd('R', -8)),
        'ForeArm.L': add(fwd(10), yaw(-14), twist('L', 50)), 'ForeArm.R': add(fwd(10), yaw(14), twist('R', 50)),
        'Hand.L': add(fwd(18), twist('L', 25)), 'Hand.R': add(fwd(18), twist('R', 25))}
def typing(t):
    tapL = max(0.0, math.sin(4 * t)) ** 3              # four taps per hand per loop, alternating
    tapR = max(0.0, math.sin(4 * t + math.pi * 0.85)) ** 3
    pose = {**TYPE, 'ForeArm.L': add(fwd(10 + 7 * tapL), yaw(-14), twist('L', 50)),
            'ForeArm.R': add(fwd(10 + 7 * tapR), yaw(14), twist('R', 50)),
            'Hand.L': add(fwd(18 - 10 * tapL), twist('L', 25)), 'Hand.R': add(fwd(18 - 10 * tapR), twist('R', 25)),
            'Head': add(lean(6 + 1.0 * math.sin(t)), yaw(3 * math.sin(t)))}
    return seated(pose), HIP_SIT
action('SitType', loop(60, typing, step=1))

# ------------------------------------------------------------------ SofaSit
SOFA = {**SIT, 'UpLeg.L': add(fwd(84), abd('L', 6)), 'UpLeg.R': add(fwd(84), abd('R', 6)),
        'Leg.L': back(4), 'Leg.R': back(4), 'Foot.L': fwd(-22), 'Foot.R': fwd(-22),
        'Spine': lean(-14), 'Chest': lean(-6), 'Neck': lean(6), 'Head': lean(8),
        # leaning back 20 deg already swings the hanging arms forward by as much; fists on the thighs
        'UpperArm.L': add(fwd(-4), abd('L', -6)), 'UpperArm.R': add(fwd(-4), abd('R', -6)),
        'ForeArm.L': fwd(36), 'ForeArm.R': fwd(36),
        'Hand.L': fwd(12), 'Hand.R': fwd(12)}
def sofa(t):
    pose = dict(SOFA)
    pose['Foot.L'] = add(fwd(-22 + 12 * math.sin(4 * t)), tilt(6 * math.sin(2 * t)))
    pose['Foot.R'] = add(fwd(-22 + 12 * math.sin(4 * t + 1.6)), tilt(-6 * math.sin(2 * t)))
    pose['Head'] = add(lean(8), tilt(5 * math.sin(t)), yaw(4 * math.sin(t + 0.7)))
    pose['Chest'] = lean(-6 + 1.0 * math.sin(3 * t))
    return seated(pose), (0, 0.06, SEAT + 0.05 - 0.407)
action('SofaSit', loop(180, sofa, step=3))

# ------------------------------------------------------------------ Sleep (on the back, head towards +Y)
LIE = {'Hips': (-90, 0, 0), 'Spine': lean(-2), 'Chest': lean(2), 'Neck': lean(10), 'Head': add(lean(12), tilt(8)),
       'UpLeg.L': abd('L', 5), 'UpLeg.R': abd('R', 5), 'Leg.L': back(6), 'Leg.R': back(6),
       'Foot.L': fwd(-30), 'Foot.R': fwd(-30),
       'UpperArm.L': add(fwd(28), abd('L', -6)), 'UpperArm.R': add(fwd(28), abd('R', -6)),
       'ForeArm.L': add(fwd(70), yaw(-36)), 'ForeArm.R': add(fwd(70), yaw(36))}
# raise the hips so the back of the body (hair and head excluded) rests on the root plane
rig.animation_data.action = None
for b in pb:
    b.rotation_quaternion = to_basis(b.name, LIE.get(b.name, (0, 0, 0)))
    b.location = (0, 0, 0)
bpy.context.view_layer.update()
ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
em = ev.to_mesh()
head_vg = body.vertex_groups['Head'].index
low = min((rig.matrix_world @ v.co).z for v, src in zip(em.vertices, body.data.vertices)
          if not any(g.group == head_vg and g.weight > 0.5 for g in src.groups))
ev.to_mesh_clear()
HIP_LIE = (0, 0, -low)
def sleep(t):
    b = math.sin(t * 2)
    pose = {**LIE, 'Chest': lean(2 + 1.6 * b), 'Spine': lean(-2 + 0.6 * b)}
    return pose, HIP_LIE
action('Sleep', loop(150, sleep, step=3))

# ------------------------------------------------------------------ book prop on the left hand
def book():
    w, h, t = 0.105, 0.15, 0.006
    verts, faces, mats = [], [], []
    def box(cx, cy, cz, sx, sy, sz, rot, mi):
        R = Matrix.Rotation(rot, 3, 'Y')
        i0 = len(verts)
        for dx in (-1, 1):
            for dy in (-1, 1):
                for dz in (-1, 1):
                    verts.append(tuple(R @ Vector((dx * sx, dy * sy, dz * sz)) + Vector((cx, cy, cz))))
        for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            faces.append([i0 + k for k in f])
            mats.append(mi)
    a = math.radians(14)                               # the open book makes a shallow V
    for sg in (-1, 1):
        box(sg * w / 2 * math.cos(a), 0, w / 2 * math.sin(a), w / 2, h / 2, 0.002, sg * a, 0)
        box(sg * (w / 2 - 0.004) * math.cos(a), 0, w / 2 * math.sin(a) + 0.005, w / 2 - 0.006, h / 2 - 0.006, t, sg * a, 1)
    me = bpy.data.meshes.new('Book')
    me.from_pydata(verts, [], faces)
    for f, m in zip(me.polygons, mats):
        f.material_index = m
    for nm, c in (('Book • cover', (0.36, 0.09, 0.07)), ('Book • pages', (0.86, 0.82, 0.72))):
        m = bpy.data.materials.get(nm) or bpy.data.materials.new(nm)
        m.use_nodes = True
        m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*c, 1)
        m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.7
        me.materials.append(m)
    return me

old = bpy.data.objects.get('Book')
if old:
    bpy.data.objects.remove(old)
bk = bpy.data.objects.new('Book', book())
body.users_collection[0].objects.link(bk)
rig.animation_data.action = bpy.data.actions['SitRead']
sc.frame_set(0)
bpy.context.view_layer.update()
hl, hr = (rig.matrix_world @ pb['Hand.L'].tail), (rig.matrix_world @ pb['Hand.R'].tail)
head = rig.matrix_world @ pb['Head'].head
mid = (hl + hr) / 2
up = (head - mid).normalized()                         # pages face the reader
side = (hl - hr).normalized()
W = Matrix.Translation(mid - up * 0.015)        # thumbs rest on the pages, on the reader's side @ Matrix((side, up.cross(side).normalized(), up)).transposed().to_4x4()
bk.parent = rig
bk.parent_type = 'BONE'
bk.parent_bone = 'Hand.L'
bone_m = rig.matrix_world @ pb['Hand.L'].matrix @ Matrix.Translation((0, pb['Hand.L'].bone.length, 0))
bk.matrix_parent_inverse = bone_m.inverted()           # world = bone @ inverse @ basis = basis here
bk.matrix_basis = W

rig.animation_data.action = bpy.data.actions['Idle']
sc.frame_set(0)
bpy.ops.wm.save_mainfile()
print('OWNER_V18_ACTIONS', [(a.name, tuple(int(x) for x in a.frame_range)) for a in bpy.data.actions], 'HIP_LIE', round(HIP_LIE[2], 3))
