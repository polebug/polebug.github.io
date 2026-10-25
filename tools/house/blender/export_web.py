"""Web version of the house scene (2026-10-21): fixed noon light, everything static pre-lit.

    Blender -b assets/blender/companion-house.blend --python assets/blender/scripts/export_web.py

The source .blend is never saved: the work copy goes to assets/web-build/. Output in web/house/assets/:
  house.glb      baked groups (house shell, three floors, yard, landscape, far terrain): meshes with
                 modifiers applied, heavy parts decimated, one atlas per group holding the full Cycles noon
                 lighting (bounce light, shadows, colour) - shown unlit on the web; plus the "live" objects
                 whose look needs transparency (glass, gauze, leaf cards, water) with plain materials, and
                 the visitor cameras
  trees/*.webp   tree impostors: every tree type rendered once from the front with the same light and a
                 transparent background; drawn as camera-facing cards (near pines, maples, shrubs, the
                 forest-edge trees and the three far forests), positions in scene.json
  ground.webp    the yard and lawn seen from straight above (grass, flowers, moss, and the shadows of the
                 house and trees falling on them), laid on the ground
  sky.hdr        the noon HDRI, turned to match and in three.js's equirect convention
  scene.json     placements, sizes and render settings (exposure, haze) for the page
  plants.json    per-twig matrices and colours for plants.glb
Everything is converted to three.js axes in the page (Blender z-up -> y-up).

Env: WEB_RES (atlas px, 2048), WEB_SAMPLES (bake samples, 64), WEB_IMP_RES (impostor px, 512),
     WEB_GROUND_RES (ground px across, 4096), WEB_STAGES (comma list of impostors,ground,bake,export; all),
     WEB_FORCE=1 re-renders cached impostors / ground.
"""
import bpy, bmesh, math, os, json, time
import numpy as np
from mathutils import Vector, Matrix

T0 = time.time()
P = '/Users/bugpole/AI/博客陪伴小屋'
BUILD = P + '/assets/web-build'
OUT = P + '/web/house/assets'
for d in (BUILD, OUT, OUT + '/trees'):
    os.makedirs(d, exist_ok=True)
RES = int(os.environ.get('WEB_RES', 2048))
SAMPLES = int(os.environ.get('WEB_SAMPLES', 64))
IMP_RES = int(os.environ.get('WEB_IMP_RES', 512))
GROUND_RES = int(os.environ.get('WEB_GROUND_RES', 6144))
STAGES = set(os.environ.get('WEB_STAGES', 'impostors,ground,backdrop,lake,bake,export').split(','))
FORCE = os.environ.get('WEB_FORCE') == '1'
DENOISE = os.environ.get('WEB_DENOISE', '1') == '1'
ONLY = set(filter(None, os.environ.get('WEB_GROUPS', '').split(',')))
# WEB_EMPTY=1 (with WEB_STAGES=bake): the rooms' lighting without their furniture, for the page's build
# animation (2026-10-22): the walls, slabs, boards and rugs are baked again on their cached proxies (same
# UVs as house.glb) with every floor's furniture, curtains and pot plants left out, to bake_<g>_empty.png;
# the cache and house.glb are not touched
EMPTY = os.environ.get('WEB_EMPTY') == '1'
# WEB_ON_PROXIES=1 (with WEB_STAGES=bake, WEB_GROUPS=...): the same, furnished: those groups' normal lighting
# baked again on their cached proxies, so only bake_<g>.png changes and house.glb keeps its geometry and UVs
# (10-23: re-lit without the removed shrubs)
ON_PROXIES = os.environ.get('WEB_ON_PROXIES') == '1'
# WEB_PLANTS_ONLY='G shrub' (with WEB_STAGES=plants): bake only the plants whose names start so; the others
# come from the cache (assets/web-build/plants.blend) untouched (10-22: the Searsia shrubs)
PLANTS_ONLY = tuple(filter(None, os.environ.get('WEB_PLANTS_ONLY', '').split(',')))
SHRUB_RES = int(os.environ.get('WEB_SHRUB_RES', 2048))         # px of each Searsia shrub's own light picture
EMPTY_GROUPS = ('house', 'floors', 'boards', 'rugs')
FURNITURE_COLS = ('21_Floor1', '22_Floor2', '23_Floor3')

bpy.ops.wm.save_as_mainfile(filepath=BUILD + '/house-web-work.blend')     # from here on, never the source
sc = bpy.context.scene
try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'METAL'
    prefs.get_devices()
    for d in prefs.devices:
        d.use = True
    sc.cycles.device = 'GPU'
except Exception as e:
    print('WEB GPU not available:', e)

def log(*a):
    print('WEB', f'{time.time() - T0:6.0f}s', *a, flush=True)

# the look of the approved render: film exposure, then the compositor's gamma 0.8 shadow lift, then AgX
EXPOSURE = sc.cycles.film_exposure
GAMMA = 0.8

def save_toned(lin_rgba, w, h, path, fmt='PNG'):
    """Scene-linear RGBA -> exposure, gamma lift, the scene's view transform -> 8-bit file."""
    a = lin_rgba.copy()
    a[..., :3] = np.power(np.clip(a[..., :3] * EXPOSURE, 0, None), GAMMA)
    im = bpy.data.images.new('_tone', w, h, alpha=True, float_buffer=True)
    im.pixels.foreach_set(a.ravel())
    sc.render.image_settings.file_format = fmt
    sc.render.image_settings.color_mode = 'RGBA'
    sc.render.image_settings.color_depth = '8'
    if fmt == 'WEBP':
        sc.render.image_settings.quality = 88
    im.save_render(path, scene=sc)
    bpy.data.images.remove(im)

def denoise(lin_rgba, w, h):
    """OIDN through a throwaway compositor scene; returns the input unchanged if that fails."""
    try:
        src = bpy.data.images.new('_dn_in', w, h, alpha=True, float_buffer=True)
        src.pixels.foreach_set(lin_rgba.ravel())
        ds = bpy.data.scenes.new('_denoise')
        ds.render.resolution_x, ds.render.resolution_y, ds.render.resolution_percentage = w, h, 100
        ds.render.engine = 'CYCLES'
        ds.view_settings.view_transform = 'Standard'
        g = bpy.data.node_groups.new('_dn', 'CompositorNodeTree')
        g.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
        n_in = g.nodes.new('CompositorNodeImage')
        n_in.image = src
        n_dn = g.nodes.new('CompositorNodeDenoise')
        n_out = g.nodes.new('NodeGroupOutput')
        g.links.new(n_in.outputs['Image'], n_dn.inputs['Image'])
        g.links.new(n_dn.outputs['Image'], n_out.inputs[0])
        ds.compositing_node_group = g
        ds.render.use_compositing = True
        path = BUILD + '/_dn.exr'
        ds.render.filepath = path
        ds.render.image_settings.file_format = 'OPEN_EXR'
        ds.render.image_settings.color_depth = '32'
        with bpy.context.temp_override(scene=ds):
            bpy.ops.render.render(write_still=True, scene=ds.name)
        im = bpy.data.images.load(path)
        out = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
        bpy.data.images.remove(im)
        bpy.data.scenes.remove(ds)
        bpy.data.images.remove(src)
        out[..., 3] = lin_rgba[..., 3]
        return out
    except Exception as e:
        log('denoise skipped:', e)
        return lin_rgba

def top_col(o):
    for c in sc.collection.children:
        if o.name in c.all_objects:
            return c.name
    return ''

# ------------------------------------------------------------------ classify
TREE_UNIQUE = ('Pine ',)
PLANTS = ('G maple', 'G shrub', 'G fern')          # yard plants stay real 3D (user, 10-22)
EDGE = 'Forest edge tree'
FOREST = ('Mountain forest', 'Front range forest', 'Foothill forest')
FLAT = ('Lawn', 'Wild flowers', 'G path joint moss')
WATER = ('Lake',)
ALPHA_NODES = {'ShaderNodeBsdfTransparent', 'ShaderNodeBsdfTranslucent', 'ShaderNodeBsdfGlass'}
def is_alpha(m):
    if not m or not m.node_tree:
        return False
    for n in m.node_tree.nodes:
        if n.bl_idname in ALPHA_NODES:
            return True
        if n.bl_idname == 'ShaderNodeBsdfPrincipled' and (n.inputs['Alpha'].is_linked or n.inputs['Alpha'].default_value < 1):
            return True
    return False

renderable = [o for o in sc.objects if o.type == 'MESH' and not o.hide_render and o.visible_get()
              and top_col(o) not in ('00_Reference', '08_Cameras', '39_Scatter_Sources')]
GROUPS = {'house': ('11_Frame', '12_Walls', '14_Windows', '15_Roof', '16_Stonework', '17_Flues'),
          'floors': ('13_Floors',),                  # own atlas: the boards fill the room views
          'floor1': ('21_Floor1',), 'floor2': ('22_Floor2',), 'floor3': ('23_Floor3',),
          'yard': ('31_Yard',), 'land': ('32_Landscape',), 'far': ('33_Far',)}
kind, group_of = {}, {}
for o in renderable:
    n = o.name
    if n.startswith(PLANTS):
        kind[n] = 'plant'
    elif n.startswith(TREE_UNIQUE) or n.startswith(EDGE):
        kind[n] = 'tree'
    elif n.startswith(FOREST) or (top_col(o) == '33_Far' and not n.startswith(EDGE)):
        kind[n] = 'backdrop'                            # mountains, foothills, their forests: one picture
    elif n.startswith(FLAT) or n == 'Ground':
        kind[n] = 'flat'
    elif n == 'Lake':
        kind[n] = 'water'
    elif any(is_alpha(s.material) for s in o.material_slots) or n.startswith('Lake shore stones'):
        kind[n] = 'live'                                # transparency, or thousands of pebbles (atlas margins)
    else:
        kind[n] = 'bake'
        group_of[n] = next((g for g, cols in GROUPS.items() if top_col(o) in cols), 'land')
# Floor boards (floors 2 and 3): their tops get a lightmap laid out from straight above, one continuous
# picture per floor, so the boards keep clean edges and both floors one tone (10-22: hundreds of small
# per-board islands bled their dark sides into the tops). Split here on a copy; the source is untouched.
fb = bpy.data.objects.get('Floor boards')
if fb and fb.name in kind:
    tops = fb.copy(); tops.data = fb.data.copy(); tops.name = 'Floor boards tops'
    rest = fb.copy(); rest.data = fb.data.copy(); rest.name = 'Floor boards sides'
    for o_, keep_top in ((tops, True), (rest, False)):
        for c_ in fb.users_collection:
            c_.objects.link(o_)
        bm_ = bmesh.new(); bm_.from_mesh(o_.data)
        bmesh.ops.delete(bm_, geom=[f for f in bm_.faces if (f.normal.z > 0.7) != keep_top], context='FACES')
        bm_.to_mesh(o_.data); bm_.free()
    fb.hide_render = True
    renderable = [o for o in renderable if o is not fb] + [tops, rest]
    del kind[fb.name]; group_of.pop(fb.name, None)
    kind[tops.name], group_of[tops.name] = 'bake', 'boards'
    kind[rest.name], group_of[rest.name] = 'bake', 'floors'
    GROUPS['boards'] = ()
# the three rugs: their own small atlas, so the page can lay a fine off-white linen weave over the baked
# light (10-22: at the furniture atlas' resolution the weave was gone and they read as flat felt)
for o in renderable:
    if kind.get(o.name) == 'bake' and o.name.endswith(' rug - jute'):
        group_of[o.name] = 'rugs'
GROUPS['rugs'] = ()
_rug = bpy.data.materials.get('Linen rug')
if _rug:                                              # baked smooth: the page supplies the weave
    for n in _rug.node_tree.nodes:
        if n.bl_idname in ('ShaderNodeBump', 'ShaderNodeNormalMap'):
            n.inputs['Strength'].default_value = 0.0
log('classified', {k: sum(1 for v in kind.values() if v == k) for k in set(kind.values())})

def overview_cam():
    return bpy.data.objects['Cam_Overview']

# only what the visitor views can show is kept outdoors: the fixed overview, and the room views looking
# out of the back windows (user, 10-21); a 15 % margin round each frame
VIEWS = ('Cam_Overview', 'Cam_Room_F1', 'Cam_Room_F2', 'Cam_Room_F3')
VIEW_PAD = 1.15
def _frustum(cam):
    d = cam.data
    W, H = sc.render.resolution_x, sc.render.resolution_y
    fit = d.sensor_fit if d.sensor_fit != 'AUTO' else ('HORIZONTAL' if W >= H else 'VERTICAL')
    th = d.sensor_width / 2 / d.lens if fit == 'HORIZONTAL' else d.sensor_height / 2 / d.lens * W / H
    tv = th * H / W
    return np.array(cam.matrix_world.inverted()), th * VIEW_PAD, tv * VIEW_PAD
FRUSTA = [_frustum(bpy.data.objects[n]) for n in VIEWS]
def in_views(pts):
    pts = np.asarray(pts, dtype=np.float64).reshape(-1, 3)
    seen = np.zeros(len(pts), bool)
    for inv, th, tv in FRUSTA:
        p = pts @ inv[:3, :3].T + inv[:3, 3]
        z = -p[:, 2]
        seen |= (z > 0.1) & (np.abs(p[:, 0]) < th * z) & (np.abs(p[:, 1]) < tv * z)
    return seen

# ------------------------------------------------------------------ impostors
def bbox_world(o):
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return Vector([min(v[i] for v in bb) for i in range(3)]), Vector([max(v[i] for v in bb) for i in range(3)])

def dilate(px, steps=12):
    """Spread edge colours into the transparent area, so mipmaps blend leaf into leaf, not into black."""
    rgb, a = px[..., :3].copy(), px[..., 3] > 0.02
    for _ in range(steps):
        acc = np.zeros_like(rgb)
        cnt = np.zeros(a.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sh_a = np.roll(a, (dy, dx), (0, 1))
            acc += np.roll(rgb, (dy, dx), (0, 1)) * sh_a[..., None]
            cnt += sh_a
        grow = ~a & (cnt > 0)
        rgb[grow] = acc[grow] / cnt[grow][:, None]
        a = a | grow
    px[..., :3] = rgb
    return px

CAMERA_ONLY = None      # objects whose camera visibility the in-context renders switch off, with their state
def isolate(keep):
    """Only `keep` is seen by the camera; everything else still casts shadows and bounces light."""
    global CAMERA_ONLY
    if CAMERA_ONLY is None:
        src = set(bpy.data.collections['39_Scatter_Sources'].all_objects)
        CAMERA_ONLY = {o: o.visible_camera for o in sc.objects if o.type in ('MESH', 'CURVE') and o not in src}
    for o in CAMERA_ONLY:
        o.visible_camera = o in keep

def restore_visibility():
    global CAMERA_ONLY
    if CAMERA_ONLY:
        for o, v in CAMERA_ONLY.items():
            o.visible_camera = v
    CAMERA_ONLY = None

def render_linear(cam, w, h, samples, path_exr):
    old = (sc.camera, sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage,
           sc.render.filepath, sc.cycles.samples, sc.render.film_transparent, sc.render.use_compositing,
           sc.cycles.film_exposure, sc.render.image_settings.file_format, sc.render.image_settings.color_mode,
           sc.render.image_settings.color_depth)
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w, h, 100
    sc.cycles.samples = samples
    sc.render.film_transparent = True
    sc.render.use_compositing = False
    sc.cycles.film_exposure = 1.0                       # save_toned applies the scene's exposure
    sc.render.filepath = path_exr
    sc.render.image_settings.file_format = 'OPEN_EXR'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.render.image_settings.color_depth = '32'
    bpy.ops.render.render(write_still=True)
    (sc.camera, sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage,
     sc.render.filepath, sc.cycles.samples, sc.render.film_transparent, sc.render.use_compositing,
     sc.cycles.film_exposure, sc.render.image_settings.file_format, sc.render.image_settings.color_mode,
     sc.render.image_settings.color_depth) = old
    im = bpy.data.images.load(path_exr)
    px = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
    bpy.data.images.remove(im)
    return unpremultiply(px)

def unpremultiply(px):
    """Cycles writes premultiplied colour. Dividing by a tiny edge alpha blows its noise up into bright
    specks (the white fringe on the tree cards): only fairly solid pixels keep their own colour; the
    soft edge takes the colour of the solid pixels next to it (dilate), keeping its alpha."""
    a = px[..., 3]
    solid = a > 0.6
    rgb = np.where(solid[..., None], px[..., :3] / np.maximum(a, 1e-4)[..., None], 0)
    tmp = np.dstack([rgb, solid.astype(np.float32)])
    tmp = dilate(tmp, 16)
    out = px.copy()
    out[..., :3] = tmp[..., :3]
    return out

INST_PTS = None
def instance_points(o):
    global INST_PTS
    if INST_PTS is None:
        INST_PTS = {}
        for inst in bpy.context.evaluated_depsgraph_get().object_instances:
            if inst.is_instance and inst.parent:
                n = inst.parent.original.name
                if n.startswith(TREE_UNIQUE) or n.startswith(EDGE):
                    INST_PTS.setdefault(n, []).append(inst.matrix_world.translation.copy())
    return INST_PTS.get(o.name, [])

def render_impostor(o, name, view_dir, res, samples):
    """Render o in place, in the full scene (sun, sky, the house's shadow, light bounced off the lawn),
    with every other object hidden from the camera only; ortho, looking along view_dir. Returns the card
    size and its centre offset (cx across, cz up) from the object's origin."""
    path = f'{OUT}/trees/{name}.webp'
    meta_path = f'{BUILD}/imp_{name}.json'
    exr = f'{BUILD}/imp_{name}.exr'
    if os.path.exists(path) and os.path.exists(meta_path) and not FORCE:
        if os.environ.get('WEB_REPROCESS') == '1' and os.path.exists(exr):      # re-tone the cached render only
            im = bpy.data.images.load(exr)
            w_, h_ = im.size
            px = unpremultiply(np.array(im.pixels[:], dtype=np.float32).reshape(h_, w_, 4))
            bpy.data.images.remove(im)
            save_toned(px, w_, h_, path, 'WEBP')
        return json.load(open(meta_path))
    isolate({o})
    org = o.matrix_world.translation.copy()
    pts = [o.matrix_world @ Vector(c) for c in o.evaluated_get(bpy.context.evaluated_depsgraph_get()).bound_box]
    pts += instance_points(o)
    d = Vector((view_dir.x, view_dir.y, 0)).normalized()
    side = Vector((-d.y, d.x, 0))
    xs = [(p - org).dot(side) for p in pts]
    zs = [p.z - org.z for p in pts]
    w = (max(xs) - min(xs)) * 1.08 + 0.2
    h = (max(zs) - min(zs)) * 1.06 + 0.2
    cx, cz = (max(xs) + min(xs)) / 2, (max(zs) + min(zs)) / 2
    size = max(w, h)
    cd = bpy.data.cameras.new('_impcam')
    cd.type = 'ORTHO'
    cd.ortho_scale = size
    cd.clip_start, cd.clip_end = 1, 2000
    cam = bpy.data.objects.new('_impcam', cd)
    sc.collection.objects.link(cam)
    cam.location = org + side * cx + Vector((0, 0, cz)) - d * 500
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    px = render_linear(cam, res, res, samples, f'{BUILD}/imp_{name}.exr')
    bpy.data.objects.remove(cam)
    save_toned(px, res, res, path, 'WEBP')
    meta = {'file': f'trees/{name}.webp', 'size': size, 'cx': cx, 'cz': cz}
    json.dump(meta, open(meta_path, 'w'))
    return meta

def safe(n):
    return ''.join(c if c.isalnum() else '_' for c in n)

trees = {'types': {}, 'instances': []}
if 'impostors' in STAGES or 'export' in STAGES:
    cam_pos = overview_cam().matrix_world.translation
    sc.render.use_persistent_data = True
    # every near and forest-edge tree is its own picture, rendered where it stands, seen from the overview
    for o in renderable:
        if not o.name.startswith(TREE_UNIQUE + (EDGE,)):
            continue
        t = safe(o.name)
        edge = o.name.startswith(EDGE)
        trees['types'][t] = render_impostor(o, t, o.matrix_world.translation - cam_pos,
                                            IMP_RES // 2 if edge else IMP_RES * 2, 32 if edge else 96)
        p = o.matrix_world.translation
        trees['instances'].append([t, p.x, p.y, p.z, 1.0])
    restore_visibility()
    log('impostors done')
    n0 = len(trees['instances'])
    pts = []
    for r in trees['instances']:
        t = trees['types'][r[0]]
        pts += [(r[1], r[2], r[3]), (r[1], r[2], r[3] + (t['cz'] + t['size'] / 2) * r[4])]
    vis = in_views(pts).reshape(-1, 2).any(1)
    trees['instances'] = [r for r, v in zip(trees['instances'], vis) if v]
    log('trees', len(trees['types']), 'types', len(trees['instances']), 'of', n0, 'instances in view')

# ------------------------------------------------------------------ ground from above
lawn = bpy.data.objects['Lawn']
glo, ghi = bbox_world(lawn)
# the lawn and, past the lake, the far shore up to and under the forest edge (10-21: it was a flat colour)
GROUND = {'x0': -100.0, 'x1': 100.0, 'y0': glo.y - 2, 'y1': 150.0, 'file': 'ground.webp'}
if 'ground' in STAGES and (FORCE or os.environ.get('WEB_FORCE_GROUND') == '1' or not os.path.exists(OUT + '/ground.webp')):
    gw, gh = GROUND['x1'] - GROUND['x0'], GROUND['y1'] - GROUND['y0']
    flat = {o.name for o in renderable if kind[o.name] == 'flat'}
    saved = {}
    for o in sc.objects:
        if o.type in ('MESH', 'CURVE') and o.name not in flat:
            saved[o.name] = o.visible_camera
            o.visible_camera = False                    # still casts its shadow on the grass
    lake = bpy.data.objects['Lake']                     # the lake cuts a transparent hole: the page's mirror shows
    lake.visible_camera, lake.is_holdout = True, True
    sc.render.film_transparent = True
    cd = bpy.data.cameras.new('_groundcam')
    cd.type = 'ORTHO'
    cd.ortho_scale = max(gw, gh)
    cd.clip_end = 400
    cam = bpy.data.objects.new('_groundcam', cd)
    sc.collection.objects.link(cam)
    cam.location = ((GROUND['x0'] + GROUND['x1']) / 2, (GROUND['y0'] + GROUND['y1']) / 2, 100)
    cam.rotation_euler = (0, 0, 0)
    old = (sc.camera, sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage,
           sc.render.filepath, sc.cycles.samples, sc.world.mist_settings.start)
    sc.camera = cam
    sc.render.resolution_x = GROUND_RES
    sc.render.resolution_y = int(GROUND_RES * gh / gw)
    sc.render.resolution_percentage = 100
    sc.cycles.samples = 64
    sc.world.mist_settings.start = 1e6                    # no aerial haze seen from 100 m above
    sc.render.filepath = OUT + '/ground.webp'
    sc.render.image_settings.file_format = 'WEBP'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.render.image_settings.quality = 85
    bpy.ops.render.render(write_still=True)
    lake.is_holdout = False
    sc.render.film_transparent = False
    (sc.camera, sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage,
     sc.render.filepath, sc.cycles.samples, sc.world.mist_settings.start) = old
    for n, v in saved.items():
        bpy.data.objects[n].visible_camera = v
    bpy.data.objects.remove(cam)
    import sys; sys.path.insert(0, os.path.dirname(__file__))
    from ground_fill import fill                         # the black contact spots under slabs and stones
    fill(OUT + '/ground.webp')
    log('ground', sc.render.resolution_x)

# ------------------------------------------------------------------ backdrop
# Everything past the forest edge (foothills, front range, snow mountains, their forests) and the sky,
# rendered once from the overview camera with a wide lens so the room views looking out of the back
# windows are covered too; the page hangs it far behind the scene. Same look as the approved render,
# haze included.
BACK_HFOV = math.radians(96)
BACK = {'file': 'backdrop.webp', 'hfov': BACK_HFOV, 'aspect': 1.0, 'distance': 700.0}   # square: tall windows too
if 'backdrop' in STAGES and (FORCE or os.environ.get('WEB_FORCE_BACKDROP') == '1' or not os.path.exists(OUT + '/backdrop.webp')):
    keep = {o.name for o in renderable if kind[o.name] == 'backdrop'} | {'Ground'}
    saved = {}
    for o in sc.objects:
        if o.type in ('MESH', 'CURVE') and o.name not in keep and not o.hide_render:
            saved[o.name] = o.hide_render
            o.hide_render = True
    oc = overview_cam()
    cd = bpy.data.cameras.new('_backcam')
    cd.sensor_fit = 'HORIZONTAL'
    cd.sensor_width = 36
    cd.lens = 18 / math.tan(BACK_HFOV / 2)
    cd.clip_end = 6000
    cam = bpy.data.objects.new('_backcam', cd)
    sc.collection.objects.link(cam)
    cam.matrix_world = oc.matrix_world.copy()
    old = (sc.camera, sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage,
           sc.render.filepath, sc.cycles.samples)
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 4096, 4096, 100
    sc.cycles.samples = 96
    sc.render.filepath = OUT + '/backdrop.webp'
    sc.render.image_settings.file_format = 'WEBP'
    sc.render.image_settings.color_mode = 'RGB'
    sc.render.image_settings.quality = 88
    bpy.ops.render.render(write_still=True)
    (sc.camera, sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage,
     sc.render.filepath, sc.cycles.samples) = old
    for n, v in saved.items():
        bpy.data.objects[n].hide_render = v
    bpy.data.objects.remove(cam)
    log('backdrop rendered')
BACK['pos'] = list(overview_cam().matrix_world.translation)
BACK['quat'] = list(overview_cam().matrix_world.to_quaternion())

# ------------------------------------------------------------------ lake
# The lake as Cycles shows it from the overview (reflections, colour, softness), with every other object
# hidden from the camera only, so it is complete behind the house and trees; wide lens for the room
# views. The page projects it onto the lake surface from this camera.
LAKE = {'file': 'lake.webp', 'hfov': math.radians(100), 'aspect': 2.0}
if 'lake' in STAGES and (FORCE or os.environ.get('WEB_FORCE_LAKE') == '1' or not os.path.exists(OUT + '/lake.webp')):
    isolate({bpy.data.objects['Lake']})
    oc = overview_cam()
    cd = bpy.data.cameras.new('_lakecam')
    cd.sensor_fit, cd.sensor_width = 'HORIZONTAL', 36
    cd.lens = 18 / math.tan(LAKE['hfov'] / 2)
    cd.clip_end = 6000
    cam = bpy.data.objects.new('_lakecam', cd)
    sc.collection.objects.link(cam)
    cam.matrix_world = oc.matrix_world.copy()
    px = render_linear(cam, 4096, 2048, 128, BUILD + '/lake.exr')
    bpy.data.objects.remove(cam)
    restore_visibility()
    save_toned(dilate(px, 24), 4096, 2048, OUT + '/lake.webp', 'WEBP')
    log('lake rendered')
LAKE['pos'] = list(overview_cam().matrix_world.translation)
LAKE['quat'] = list(overview_cam().matrix_world.to_quaternion())

# ------------------------------------------------------------------ bake groups
BUDGET = {'rugs': 20000, 'boards': 10 ** 6, 'floors': 10 ** 6, 'house': 120000, 'floor1': 120000, 'floor2': 110000, 'floor3': 110000, 'yard': 90000, 'land': 40000, 'far': 150000}
def water_fill(counts, budget):
    """One cap for the group: objects under it stay whole, only the heaviest are thinned (a uniform ratio
    broke window frames and blinds while the roof tiles kept most of their triangles)."""
    ns = sorted(counts)
    if sum(ns) <= budget:
        return max(ns) if ns else 0
    left, k = budget, len(ns)
    for n in ns:
        if n * k > left:
            return int(left / k)
        left -= n
        k -= 1
    return ns[-1]
ATLAS = {'rugs': 1024}                                # atlas px per group (others RES)
LEAF_CAP = 30000      # only the big potted-plant leaf sets are thinned; gauze, glass and other cards stay whole
def object_mesh(o, cap, cull=False):
    """World-space copy of the evaluated object, decimated to cap triangles. What the materials read from
    the object itself (Object Info colour and random, object-space coordinates) is stored on the mesh,
    so it survives joining: attributes objcol, objrand, objco."""
    # cheaper modifiers first: one bevel segment and no subdivision keep the shapes, unlike decimation
    saved = []
    for m in o.modifiers:
        if m.type == 'BEVEL' and m.segments > 1:
            saved.append((m, 'segments', m.segments)); m.segments = 1
        elif m.type == 'SUBSURF' and m.render_levels > 0 and o.name.startswith(('F', 'Roof', 'Floor')):
            saved.append((m, 'render_levels', m.render_levels)); m.render_levels = max(0, m.render_levels - 1)
            saved.append((m, 'levels', m.levels)); m.levels = max(0, m.levels - 1)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    for m, k, v in saved:
        setattr(m, k, v)
    co = np.zeros(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    me.attributes.new('objco', 'FLOAT_VECTOR', 'POINT').data.foreach_set('vector', co)
    me.attributes.new('objcol', 'FLOAT_COLOR', 'POINT').data.foreach_set('color', np.tile(np.array(o.color, np.float32), len(me.vertices)))
    rnd = (hash(o.name) % 100000) / 100000.0
    me.attributes.new('objrand', 'FLOAT', 'POINT').data.foreach_set('value', np.full(len(me.vertices), rnd, np.float32))
    me.transform(o.matrix_world)
    bm_ = bmesh.new()                                 # weld first: the terrain is built from loose quads,
    bm_.from_mesh(me)                                 # which decimation would tear apart
    bmesh.ops.remove_doubles(bm_, verts=bm_.verts, dist=0.0002)
    if cull:
        bm_.verts.ensure_lookup_table()
        vis = in_views([v.co for v in bm_.verts])
        bmesh.ops.delete(bm_, geom=[f for f in bm_.faces if not any(vis[v.index] for v in f.verts)], context='FACES')
    bm_.to_mesh(me)
    bm_.free()
    return decimate(me, cap)

def decimate(me, cap):
    me.calc_loop_triangles()
    n = len(me.loop_triangles)
    if n > cap:
        tmp = bpy.data.objects.new('_dec', me)
        sc.collection.objects.link(tmp)
        d = tmp.modifiers.new('d', 'DECIMATE')
        d.ratio = cap / n
        me2 = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
        bpy.data.objects.remove(tmp)
        bpy.data.meshes.remove(me)
        me = me2
    return me

def uv_cover(o):
    me_ = o.data
    me_.calc_loop_triangles()
    uv2 = np.zeros(len(me_.loops) * 2)
    me_.uv_layers.active.data.foreach_get('uv', uv2)
    uv2 = uv2.reshape(-1, 2)
    tri = np.array([t.loops[:] for t in me_.loop_triangles])
    a_, b_, c_ = uv2[tri[:, 0]], uv2[tri[:, 1]], uv2[tri[:, 2]]
    return float((0.5 * np.abs((b_[:, 0] - a_[:, 0]) * (c_[:, 1] - a_[:, 1]) - (c_[:, 0] - a_[:, 0]) * (b_[:, 1] - a_[:, 1]))).sum())

baked = {}
baked_cached = {}
if 'bake' in STAGES:
    sc.cycles.samples = SAMPLES
    sc.cycles.use_denoising = False
    sc.render.bake.margin = 6
    # materials read the object attributes stored by object_mesh instead of the (joined) object
    for m in {s_.material for o in renderable if kind[o.name] == 'bake' for s_ in o.material_slots if s_.material}:
        nt = m.node_tree
        if not nt:
            continue
        for n in [n for n in nt.nodes if n.bl_idname in ('ShaderNodeObjectInfo', 'ShaderNodeTexCoord')]:
            for out_name, attr, sock in (('Color', 'objcol', 'Color'), ('Random', 'objrand', 'Fac'), ('Object', 'objco', 'Vector')):
                out = n.outputs.get(out_name)
                if out is None or not out.is_linked or (n.bl_idname == 'ShaderNodeTexCoord') != (out_name == 'Object'):
                    continue
                a = nt.nodes.new('ShaderNodeAttribute')
                a.attribute_type = 'GEOMETRY'
                a.attribute_name = attr
                for l in list(out.links):
                    nt.links.new(a.outputs[sock], l.to_socket)
    gcol = bpy.data.collections.new('_web_baked')
    sc.collection.children.link(gcol)
    for g in (() if EMPTY or ON_PROXIES else GROUPS):
        if ONLY and g not in ONLY:
            continue
        members = [o for o in renderable if kind[o.name] == 'bake' and group_of[o.name] == g]
        if not members:
            continue
        parts = []
        meshes = [(o, object_mesh(o, 10 ** 9, cull=g in ('far', 'land'))) for o in members]   # cheap reductions only
        for _, me in meshes:
            me.calc_loop_triangles()
        cap = water_fill([len(me.loop_triangles) for _, me in meshes], BUDGET[g])
        log('cap', g, cap, 'of', max(len(me.loop_triangles) for _, me in meshes))
        for o, me in meshes:
            me = decimate(me, max(cap, 400))
            po = bpy.data.objects.new('_part', me)
            for i, s in enumerate(o.material_slots):
                if i < len(me.materials):
                    me.materials[i] = s.material
            gcol.objects.link(po)
            parts.append(po)
        bpy.ops.object.select_all(action='DESELECT')
        for po in parts:
            po.select_set(True)
        bpy.context.view_layer.objects.active = parts[0]
        bpy.ops.object.join()
        bo = parts[0]
        bo.name = 'BAKED_' + g
        bm_ = bmesh.new()
        bm_.from_mesh(bo.data)
        bmesh.ops.remove_doubles(bm_, verts=bm_.verts, dist=0.0005)
        bmesh.ops.dissolve_degenerate(bm_, edges=bm_.edges, dist=0.0005)
        bmesh.ops.delete(bm_, geom=[f for f in bm_.faces if f.calc_area() < 1e-7], context='FACES')
        bm_.to_mesh(bo.data)
        bm_.free()
        # the materials keep sampling their own UVs (active for rendering); 'bake' only lays out the atlas
        render_uv = next((u for u in bo.data.uv_layers if u.active_render), None)
        uvl = bo.data.uv_layers.new(name='bake')
        bo.data.uv_layers.active = uvl
        if render_uv:
            render_uv.active_render = True
        if g == 'boards':                             # planar from above: each floor its own band
            me_ = bo.data
            zs = sorted({round(me_.vertices[p_.vertices[0]].co.z, 1) for p_ in me_.polygons})
            co_ = np.array([v.co for v in me_.vertices])
            x0, x1, y0, y1 = co_[:, 0].min(), co_.max(0)[0], co_[:, 1].min(), co_.max(0)[1]
            sc_ = 0.98 / max(x1 - x0, 2 * (y1 - y0) * 1.02)
            for p_ in me_.polygons:
                band = zs.index(round(me_.vertices[p_.vertices[0]].co.z, 1))
                for li in p_.loop_indices:
                    v = me_.vertices[me_.loops[li].vertex_index].co
                    uvl.data[li].uv = (0.01 + (v.x - x0) * sc_, 0.01 + band * 0.5 + (v.y - y0) * sc_)
            baked[g] = bo
            log('group', g, 'planar bands', zs)
            continue
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(89), island_margin=0.0, area_weight=1.0)
        bpy.ops.object.mode_set(mode='OBJECT')
        log('uv after smart', g, uv_cover(bo))
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.uv.select_all(action='SELECT')
        r_ = bpy.ops.uv.pack_islands(rotate=True, margin_method='FRACTION', margin=1.0 / ATLAS.get(g, RES))
        bpy.ops.object.mode_set(mode='OBJECT')
        log('uv after pack', g, uv_cover(bo), r_)
        baked[g] = bo
        bo.data.calc_loop_triangles()
        log('group', g, len(members), 'objects', len(bo.data.loop_triangles), 'tris')
    # the proxies stand in for the originals from now on (shadows and bounce light included)
    # a partial rebake brings the other groups' cached proxies in as occluders and bounce surfaces
    # (their materials read the stored object attributes, which the originals lack)
    if EMPTY:
        # the cached proxies: the ones to bake, and the yard and land as occluders; no furniture
        with bpy.data.libraries.load(BUILD + '/baked.blend') as (src, dst):
            dst.objects = [n for n in src.objects if n.startswith('BAKED_') and not n.startswith('BAKED_floor') or n == 'BAKED_floors']
        for o in dst.objects:
            gcol.objects.link(o)
            g_ = o.name[len('BAKED_'):]
            (baked if g_ in EMPTY_GROUPS and (not ONLY or g_ in ONLY) else baked_cached)[g_] = o
        for o in renderable:
            if top_col(o) in FURNITURE_COLS:
                o.hide_render = True
        log('empty rooms: baking', sorted(baked), 'occluders', sorted(baked_cached))
    elif ON_PROXIES:
        # every cached proxy, furniture included: the ones named in WEB_GROUPS to bake, the rest as occluders
        with bpy.data.libraries.load(BUILD + '/baked.blend') as (src, dst):
            dst.objects = [n for n in src.objects if n.startswith('BAKED_')]
        for o in dst.objects:
            gcol.objects.link(o)
            g_ = o.name[len('BAKED_'):]
            (baked if g_ in ONLY else baked_cached)[g_] = o
        log('on proxies: baking', sorted(baked), 'occluders', sorted(baked_cached))
    elif ONLY and os.path.exists(BUILD + '/baked.blend'):
        with bpy.data.libraries.load(BUILD + '/baked.blend') as (src, dst):
            dst.objects = [n for n in src.objects if n.startswith('BAKED_') and n[len('BAKED_'):] not in baked]
        for o in dst.objects:
            gcol.objects.link(o)
            baked_cached[o.name[len('BAKED_'):]] = o
        log('cached proxies in the bake scene', sorted(baked_cached))
    for o in renderable:
        if kind[o.name] == 'bake':
            o.hide_render = True
    for g, bo in baked.items():
        if g in baked_cached:
            continue
        R_ = ATLAS.get(g, RES)
        img = bpy.data.images.new(f'bake_{g}', R_, R_, alpha=False, float_buffer=True)
        for m in {s.material for s in bo.material_slots if s.material}:
            nt = m.node_tree
            n = nt.nodes.get('_bake') or nt.nodes.new('ShaderNodeTexImage')
            n.name = '_bake'
            n.image = img
            nt.nodes.active = n
        # empty rooms: the floors and boards are baked with no rugs on them (the rugs drop in later)
        rug_ = baked.get('rugs') or baked_cached.get('rugs')
        if EMPTY and rug_:
            rug_.hide_render = g != 'rugs'
        bpy.ops.object.select_all(action='DESELECT')
        bo.select_set(True)
        bpy.context.view_layer.objects.active = bo
        t = time.time()
        if os.environ.get('WEB_DIAG') == 'color':
            bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, margin=6, use_clear=True, uv_layer='bake', target='IMAGE_TEXTURES')
            px_ = np.array(img.pixels[:], dtype=np.float32).reshape(RES, RES, 4)
            log('albedo', g, 'lit texels', float((px_[..., :3].max(-1) > 0.01).mean()))
            save_toned(np.dstack([px_[..., :3] / EXPOSURE ** 1, np.ones((RES, RES, 1), np.float32)]) if False else px_, RES, RES, f'{BUILD}/albedo_{g}.png')
        bpy.ops.object.bake(type='COMBINED', pass_filter={'DIRECT', 'INDIRECT', 'DIFFUSE', 'TRANSMISSION', 'EMIT'},
                            margin=6, use_clear=True, uv_layer='bake', target='IMAGE_TEXTURES')
        px = np.array(img.pixels[:], dtype=np.float32).reshape(R_, R_, 4)
        log('raw', g, 'mean', float(px[..., :3].mean()), 'lit texels', float((px[..., :3].max(-1) > 0.01).mean()))
        uvs = np.zeros(len(bo.data.loops) * 2); bo.data.uv_layers['bake'].data.foreach_get('uv', uvs)
        log('uv bounds', g, uvs.reshape(-1, 2).min(0).round(3), uvs.reshape(-1, 2).max(0).round(3))
        bo.data.calc_loop_triangles()
        uv2 = uvs.reshape(-1, 2)
        tri = np.array([t.loops[:] for t in bo.data.loop_triangles])
        a_, b_, c_ = uv2[tri[:, 0]], uv2[tri[:, 1]], uv2[tri[:, 2]]
        area = 0.5 * np.abs((b_[:, 0] - a_[:, 0]) * (c_[:, 1] - a_[:, 1]) - (c_[:, 0] - a_[:, 0]) * (b_[:, 1] - a_[:, 1]))
        log('uv area', g, float(area.sum()), 'tris', len(tri), 'median tri px', float(np.median(area) * RES * RES))
        if os.environ.get('WEB_DIAG'):
            me_ = bo.data
            uv_ = me_.uv_layers['bake'].data
            stat = {}
            for poly in me_.polygons:
                u = sum(uv_[l].uv.x for l in poly.loop_indices) / poly.loop_total
                v = sum(uv_[l].uv.y for l in poly.loop_indices) / poly.loop_total
                c = px[min(R_ - 1, int(v * R_)), min(R_ - 1, int(u * R_)), :3].mean()
                k = me_.materials[poly.material_index].name if me_.materials[poly.material_index] else '-'
                a_ = stat.setdefault(k, [0, 0.0, 0.0])
                a_[0] += 1; a_[1] += c; a_[2] += poly.area
            for k, (n, c, ar) in sorted(stat.items(), key=lambda kv: -kv[1][2]):
                log('diag', g, f'{k[:34]:34} faces {n:6d} area {ar:8.1f} mean {c / n:.3f}')
        if DENOISE:
            px = denoise(px, R_, R_)
            log('denoised', g, 'mean', float(px[..., :3].mean()))
        px[..., 3] = 1
        save_toned(px, R_, R_, f'{BUILD}/bake_{g}{"_empty" if EMPTY else ""}.png')
        log('baked', g, f'{time.time() - t:.0f}s')

    # keep the proxies: an export-only run (page or material tweaks) then needs no rebake
    baked.update(baked_cached)                        # partial rebake: the rest come from the cache
    if baked and not EMPTY and not ON_PROXIES:
        bpy.data.libraries.write(BUILD + '/baked.blend', set(baked.values()))

# ------------------------------------------------------------------ yard plants, in 3D
# Shrubs and maples are branches plus ~1000 instanced leaf twigs each; ferns are leaf cards. They stay
# real geometry, lit like everything else: the plant with its twigs realised is put in the scene and its
# full Cycles light (sun, sky, shade inside the bush, the house's shadow) is baked to vertex colours.
# Then
#   branches  -> mesh with the baked, toned colour per vertex
#   twigs     -> one source mesh per kind + per-twig matrix and colour (mean of its baked vertices); the
#                page draws them instanced
#   ferns     -> their own mesh and leaf texture, with a per-vertex light factor (baked irradiance)
from mathutils.kdtree import KDTree
PLANT_DATA = {'twigs': {}, 'file': 'plants.glb'}
def tone_colours(lin):
    """Scene-linear radiance (N, 3) -> the displayed sRGB colour, through the same tone path as the bakes."""
    n = len(lin)
    img = np.ones((1, n, 4), np.float32)
    img[0, :, :3] = lin
    save_toned(img, n, 1, BUILD + '/_tone.png')
    im = bpy.data.images.load(BUILD + '/_tone.png')
    out = np.array(im.pixels[:], dtype=np.float32).reshape(1, n, 4)[0, :, :3]
    bpy.data.images.remove(im)
    return out

REALIZE = None
def realized_copy(o):
    global REALIZE
    if REALIZE is None:
        REALIZE = bpy.data.node_groups.new('_realize', 'GeometryNodeTree')
        REALIZE.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        REALIZE.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
        a, b, r = REALIZE.nodes.new('NodeGroupInput'), REALIZE.nodes.new('NodeGroupOutput'), REALIZE.nodes.new('GeometryNodeRealizeInstances')
        REALIZE.links.new(a.outputs[0], r.inputs[0])
        REALIZE.links.new(r.outputs[0], b.inputs[0])
    m = o.modifiers.new('_realize', 'NODES')
    m.node_group = REALIZE
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    o.modifiers.remove(m)
    me.transform(o.matrix_world)
    r_ = bpy.data.objects.new('_bake_' + o.name, me)
    sc.collection.objects.link(r_)
    return r_

def bake_vertex(r_, kind_='COMBINED'):
    ca = r_.data.color_attributes.new('bake', 'FLOAT_COLOR', 'POINT')
    r_.data.color_attributes.active_color = ca
    bpy.ops.object.select_all(action='DESELECT')
    r_.select_set(True)
    bpy.context.view_layer.objects.active = r_
    if kind_ == 'COMBINED':
        bpy.ops.object.bake(type='COMBINED', pass_filter={'DIRECT', 'INDIRECT', 'DIFFUSE', 'TRANSMISSION', 'EMIT', 'GLOSSY'},
                            target='VERTEX_COLORS')
    else:
        bpy.ops.object.bake(type='DIFFUSE', pass_filter={'DIRECT', 'INDIRECT'}, target='VERTEX_COLORS')
    c = np.zeros(len(r_.data.vertices) * 4, np.float32)
    ca.data.foreach_get('color', c)
    return c.reshape(-1, 4)[:, :3]

def upstream_image(sock, depth=6):
    """The first image texture feeding a socket, through mix / hue / gamma nodes."""
    if depth == 0 or not sock.is_linked:
        return None
    n = sock.links[0].from_node
    if n.bl_idname == 'ShaderNodeTexImage':
        return n.image
    for i in n.inputs:
        im = upstream_image(i, depth - 1)
        if im is not None:
            return im
    return None

def tex_mean(m):
    """Mean linear albedo of a material's base colour (its image over the opaque texels, or the colour)."""
    bs = next((n for n in m.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'), None) if m and m.node_tree else None
    if bs is None:
        return np.array([0.7, 0.7, 0.7])
    img = upstream_image(bs.inputs['Base Color'])
    if img is None:
        return np.array(bs.inputs['Base Color'].default_value[:3])
    a_img = upstream_image(bs.inputs['Alpha'])
    px = np.array(img.pixels[:], dtype=np.float32).reshape(-1, 4)[:, :3]
    if img.colorspace_settings.name == 'sRGB' and not img.is_float:
        px = np.where(px <= 0.04045, px / 12.92, ((px + 0.055) / 1.055) ** 2.4)
    if a_img is not None and a_img.size[:] == img.size[:]:
        keep = np.array(a_img.pixels[:], dtype=np.float32).reshape(-1, 4)[:, 0] > 0.5
        px = px[keep]
    return px.mean(0)

plant_objs = []
if 'plants' in STAGES or 'export' in STAGES:
    def is_glass(o):
        return any(sl.material and sl.material.name.startswith('Glass') for sl in o.material_slots)
    plants = [o for o in renderable if kind[o.name] == 'plant' or (kind[o.name] == 'live' and not is_glass(o))]
    for o in plants:
        kind[o.name] = 'plant'                          # not exported again with the live objects
    cache = BUILD + '/plants.blend'
    if 'plants' in STAGES or not os.path.exists(cache):
        sc.cycles.samples = SAMPLES
        for o in plants:
            o.hide_render = True
        twig_rows = {}
        bake_list = plants
        if PLANTS_ONLY:
            # the rest from the cache, minus whatever the plants being baked made last time
            with bpy.data.libraries.load(cache) as (src_, dst_):
                dst_.objects = list(src_.objects)
            for o_ in dst_.objects:
                if o_.name.replace('LIT_', '', 1).replace('BRANCH_', '', 1).startswith(PLANTS_ONLY) or o_.name.startswith('TWIG_'):   # twig sources: made again below
                    bpy.data.objects.remove(o_)
                else:
                    sc.collection.objects.link(o_)
                    o_.hide_render = True
                    plant_objs.append(o_)
            old_ = json.load(open(BUILD + '/plants.json'))
            twig_rows = {k_: v_ for k_, v_ in old_['twigs'].items() if k_ != 'Twig shrub'}
            bake_list = [o for o in plants if o.name.startswith(PLANTS_ONLY)]
            log('plants only', [o.name for o in bake_list], 'kept', len(plant_objs))
        for o in bake_list:
            o.hide_render = False
            r_ = realized_copy(o)
            o.hide_render = True
            t = time.time()
            # leaf cards, gauze, cane, pot plants, stones, and the Searsia shrubs (Poly Haven, like the pot plants)
            if not (o.name.startswith('G maple') or (o.name.startswith('G shrub') and not o.get('searsia'))):
                if o.get('searsia'):
                    # the Searsia shrubs (10-22): their full Cycles light baked to a picture of their own, like the
                    # house (a vertex colour cannot hold a dense bush of cut-out leaf cards). A second UV set
                    # 'bake' lays the cards out; the leaves keep their own UVs for the cut-out, drawn by the page
                    # from searsia_alpha.webp
                    me_ = r_.data
                    leaf_uv = next(u_ for u_ in me_.uv_layers if u_.active_render)
                    buv = me_.uv_layers.new(name='bake')
                    leaf_uv.active_render = True
                    me_.uv_layers.active = buv
                    bpy.ops.object.select_all(action='DESELECT')
                    r_.select_set(True)
                    bpy.context.view_layer.objects.active = r_
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.select_all(action='SELECT')
                    bpy.ops.uv.smart_project(angle_limit=math.radians(89), island_margin=0.0, area_weight=1.0)
                    bpy.ops.uv.select_all(action='SELECT')
                    bpy.ops.uv.pack_islands(rotate=True, margin_method='FRACTION', margin=1.0 / SHRUB_RES)
                    bpy.ops.object.mode_set(mode='OBJECT')
                    img_ = bpy.data.images.new('_shrub_bake', SHRUB_RES, SHRUB_RES, alpha=False, float_buffer=True)
                    for m_ in {m_ for m_ in me_.materials if m_}:
                        n_ = m_.node_tree.nodes.get('_bake') or m_.node_tree.nodes.new('ShaderNodeTexImage')
                        n_.name, n_.image = '_bake', img_
                        m_.node_tree.nodes.active = n_
                    bpy.ops.object.bake(type='COMBINED', pass_filter={'DIRECT', 'INDIRECT', 'DIFFUSE', 'TRANSMISSION', 'EMIT'},
                                        margin=4, use_clear=True, uv_layer='bake', target='IMAGE_TEXTURES')
                    px_ = np.array(img_.pixels[:], dtype=np.float32).reshape(SHRUB_RES, SHRUB_RES, 4)
                    if DENOISE:
                        px_ = denoise(px_, SHRUB_RES, SHRUB_RES)
                    px_[..., 3] = 1
                    num_ = o.name.split()[-1]
                    save_toned(px_, SHRUB_RES, SHRUB_RES, f'{OUT}/shrub_{num_}.webp', 'WEBP')
                    for m_ in {m_ for m_ in me_.materials if m_}:
                        m_.node_tree.nodes.remove(m_.node_tree.nodes['_bake'])
                    bpy.data.images.remove(img_)
                    r_.name = 'LIT_' + o.name
                    plant_objs.append(r_)
                    log('plant', o.name, 'baked picture', f'shrub_{num_}.webp', f'{time.time() - t:.0f}s')
                    continue
                E = bake_vertex(r_, 'DIFFUSE')                       # irradiance at each vertex
                mats = r_.data.materials
                albs = np.array([tex_mean(m) for m in mats]) if len(mats) else np.array([[0.7, 0.7, 0.7]])
                vm = np.zeros(len(r_.data.vertices), int)
                for poly in r_.data.polygons:
                    vm[list(poly.vertices)] = poly.material_index
                alb = albs[np.minimum(vm, len(albs) - 1)]
                f = tone_colours(E * alb) / np.maximum(tone_colours(albs)[np.minimum(vm, len(albs) - 1)], 1e-3)
                f = np.clip(f, 0, 4) ** 2.2                          # the page multiplies in linear light
                ca = r_.data.color_attributes['bake']
                ca.data.foreach_set('color', np.hstack([f, np.ones((len(f), 1), np.float32)]).ravel())
                r_.name = 'LIT_' + o.name
                plant_objs.append(r_)
                log('plant', o.name, len(r_.data.vertices), 'verts', f'{time.time() - t:.0f}s')
                continue
            C = bake_vertex(r_)
            co = np.array([v.co for v in r_.data.vertices])
            kd = KDTree(len(co))
            for i, p_ in enumerate(co):
                kd.insert(p_, i)
            kd.balance()
            # branches: the plant without its twigs, coloured from the nearest baked vertex
            dg = bpy.context.evaluated_depsgraph_get()
            o.hide_render = False
            bme = bpy.data.meshes.new_from_object(o.evaluated_get(dg), depsgraph=dg)
            o.hide_render = True
            bme.transform(o.matrix_world)
            bc = np.array([C[kd.find(v.co)[1]] for v in bme.vertices])
            ca = bme.color_attributes.new('bake', 'FLOAT_COLOR', 'POINT')
            ca.data.foreach_set('color', np.hstack([tone_colours(bc) ** 2.2, np.ones((len(bc), 1), np.float32)]).ravel())
            bo = bpy.data.objects.new('BRANCH_' + o.name, bme)
            sc.collection.objects.link(bo)
            plant_objs.append(bo)
            # twigs: per-instance matrix and mean baked colour
            rows = []
            for inst in dg.object_instances:
                if inst.is_instance and inst.parent and inst.parent.original == o:
                    src = inst.object.original
                    mw = inst.matrix_world.copy()
                    vs = src.data.vertices
                    idx = range(0, len(vs), max(1, len(vs) // 12))
                    cs = [C[kd.find(mw @ vs[i].co)[1]] for i in idx]
                    rows.append((src.name, mw, np.mean(cs, 0)))
            toned = tone_colours(np.array([r[2] for r in rows]))
            for (srcname, mw, _), tc in zip(rows, toned):
                twig_rows.setdefault(srcname, []).append([*[mw[i][j] for i in range(3) for j in range(4)], *map(float, tc)])
            bpy.data.objects.remove(r_)
            log('plant', o.name, len(rows), 'twigs', f'{time.time() - t:.0f}s')
        for o in plants:
            o.hide_render = False
        for srcname in twig_rows:
            src = bpy.data.objects[srcname]
            tw = bpy.data.objects.new('TWIG_' + srcname, src.data.copy())
            sc.collection.objects.link(tw)
            plant_objs.append(tw)
        PLANT_DATA['twigs'] = twig_rows
        json.dump(PLANT_DATA, open(BUILD + '/plants.json', 'w'))
        bpy.data.libraries.write(cache, set(plant_objs))
    else:
        with bpy.data.libraries.load(cache) as (src_, dst_):
            dst_.objects = list(src_.objects)
        plant_objs = list(dst_.objects)
        PLANT_DATA = json.load(open(BUILD + '/plants.json'))
    # plants.glb: branches and ferns in world space, twig sources at their own origin
    ps = bpy.data.scenes.new('WEBPLANTS')
    for o in plant_objs:
        ps.collection.objects.link(o)
    with bpy.context.temp_override(scene=ps, view_layer=ps.view_layers[0]):
        bpy.ops.export_scene.gltf(filepath=OUT + '/plants.glb', export_format='GLB', use_active_scene=True,
                                  export_vertex_color='ACTIVE', export_all_vertex_colors=False,
                                  export_image_format='WEBP', export_image_quality=88, export_yup=True)
    log('plants.glb', os.path.getsize(OUT + '/plants.glb') // 1024, 'KB')

# ------------------------------------------------------------------ export
if 'export' in STAGES and not baked and os.path.exists(BUILD + '/baked.blend'):
    with bpy.data.libraries.load(BUILD + '/baked.blend') as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith('BAKED_')]
    baked = {o.name[len('BAKED_'):]: o for o in dst.objects}
    log('reused baked proxies', sorted(baked))
if 'export' in STAGES:
    ex = bpy.data.scenes.new('WEB')
    ecol = ex.collection
    for g, bo in baked.items():
        img = bpy.data.images.load(f'{BUILD}/bake_{g}.png')
        m = bpy.data.materials.new(f'BAKED_{g}')
        m.use_nodes = True
        tex = m.node_tree.nodes.new('ShaderNodeTexImage')
        tex.image = img
        bs = m.node_tree.nodes['Principled BSDF']
        m.node_tree.links.new(tex.outputs['Color'], bs.inputs['Base Color'])
        bo.data.materials.clear()
        bo.data.materials.append(m)
        for uv in [u for u in bo.data.uv_layers if u.name != 'bake']:
            bo.data.uv_layers.remove(uv)
        bo.data.uv_layers['bake'].active_render = True
        ecol.objects.link(bo)
    # live objects keep their own materials; modifiers applied by the exporter
    for o in renderable:
        if kind[o.name] in ('live', 'water'):
            me = object_mesh(o, LEAF_CAP if o.name.startswith('PH ') else 10 ** 9)   # world space, modifiers applied
            for i, s_ in enumerate(o.material_slots):
                if i < len(me.materials):
                    me.materials[i] = s_.material
            c = bpy.data.objects.new(o.name, me)
            ecol.objects.link(c)
    for cn in VIEWS:
        c = bpy.data.objects[cn].copy()
        c.parent = None
        c.matrix_world = bpy.data.objects[cn].matrix_world
        ecol.objects.link(c)
    with bpy.context.temp_override(scene=ex, view_layer=ex.view_layers[0]):
        bpy.ops.export_scene.gltf(filepath=OUT + '/house.glb', export_format='GLB', use_active_scene=True,
                                  export_apply=True, export_cameras=True, export_lights=False,
                                  export_image_format='WEBP', export_image_quality=88, export_yup=True)
    log('glb', os.path.getsize(OUT + '/house.glb') // 1024, 'KB')

    # sky: the world HDRI turned as in Blender, re-laid in three.js's equirect convention
    env = next(n for n in sc.world.node_tree.nodes if n.bl_idname == 'ShaderNodeTexEnvironment')
    rot = next(n for n in sc.world.node_tree.nodes if n.bl_idname == 'ShaderNodeMapping').inputs['Rotation'].default_value[2]
    src = env.image
    sw, sh = src.size
    spx = np.array(src.pixels[:], dtype=np.float32).reshape(sh, sw, 4)
    shift = int(round((0.5 - rot / (2 * math.pi)) * sw)) % sw
    spx = np.roll(spx, -shift, axis=1)
    sky = bpy.data.images.new('_sky', sw, sh, float_buffer=True)
    sky.pixels.foreach_set(spx.ravel())
    sky.scale(1024, 512)
    sky.filepath_raw = OUT + '/sky.hdr'
    sky.file_format = 'HDR'
    sky.save()

    # ground colour beyond the picture: the mean of the picture's border
    gimg = bpy.data.images.load(OUT + '/ground.webp')
    gw_, gh_ = gimg.size
    gpx = np.array(gimg.pixels[:], dtype=np.float32).reshape(gh_, gw_, 4)
    border = np.concatenate([gpx[:4].reshape(-1, 4), gpx[-4:].reshape(-1, 4), gpx[:, :4].reshape(-1, 4), gpx[:, -4:].reshape(-1, 4)])
    GROUND['outside'] = [float(c) for c in border[:, :3].mean(0)]           # display (sRGB) values
    ms = sc.world.mist_settings
    haze = bpy.data.node_groups['Aerial perspective'].nodes['Haze'].inputs[7].default_value[:3]
    json.dump({'build': int(time.time()), 'trees': trees, 'ground': GROUND, 'skyFile': 'sky.hdr', 'backdrop': BACK, 'lake': LAKE,
               'plants': {'file': PLANT_DATA['file'], 'twigsFile': 'plants.json'},
               'exposure': EXPOSURE, 'gamma': GAMMA,
               'haze': {'start': ms.start, 'depth': ms.depth, 'amount': 0.3, 'colorLinear': list(haze)},
               'sunTo': list(Vector((-0.45, -0.62, 0.64)).normalized())},
              open(OUT + '/scene.json', 'w'))
    # the twig table (2.6 MB) loads with plants.glb, after the first screen (2026-10-22)
    json.dump(PLANT_DATA['twigs'], open(OUT + '/plants.json', 'w'))
    log('done')
