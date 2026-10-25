"""Loading-screen line art (2026-10-22): the overview drawn as hand-drawn lines, plus one mask per region
(mountains, trees, lake, grass, house) so the page can reveal the 3D view region by region.

    Blender -b assets/blender/companion-house.blend --python assets/blender/scripts/loading_lineart.py

Never saves the .blend. Output in assets/renders/loading/:
  mask_regions.png   flat colour per region from the overview camera (Workbench, no anti-aliasing)
  lines_<region>.png Freestyle strokes per region (transparent), pencil-like (wobble, tapered)
  lineart.png        all strokes on paper, for review
"""
import bpy, os, math
import numpy as np

P = '/Users/bugpole/AI/博客陪伴小屋'
OUT = P + '/assets/renders/loading'
sc = bpy.context.scene
sc.camera = bpy.data.objects['Cam_Overview']
W, H = 1672, 941
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100

def col_of(o):
    for c in sc.collection.children_recursive:
        if o.name in c.objects:
            return c.name
    return ''

TREES = ('Pine ', 'Forest edge tree', 'G maple', 'G shrub', 'G fern', 'Mountain forest', 'Front range forest',
         'Foothill forest', 'Twig ', 'Tree source')
REGION = {'sky': (0, 0, 0), 'mountains': (1, 0, 0), 'trees': (0, 1, 0), 'lake': (0, 0, 1),
          'grass': (1, 1, 0), 'house': (1, 0, 1)}
def region(o):
    n, c = o.name, col_of(o)
    if n.startswith(TREES):
        return 'trees'
    if n.startswith(('Lake', 'G lake rock')):
        return 'lake'
    if c == '33_Far':
        return 'mountains'
    if c[:2] in ('11', '12', '13', '14', '15', '16', '17', '21', '22', '23'):
        return 'house'
    return 'grass'

# ---------------------------------------------------------------- region masks (Workbench, flat)
for o in bpy.data.objects:
    if o.type in ('MESH', 'CURVE'):
        o.color = (*REGION[region(o)], 1)
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light, sh.color_type = 'FLAT', 'OBJECT'
sh.show_object_outline = sh.show_cavity = sh.show_shadows = sh.show_specular_highlight = False
sh.background_type = 'VIEWPORT'
sh.background_color = (0, 0, 0)
sc.display.render_aa = 'OFF'
sc.view_settings.view_transform = 'Standard'
sc.view_settings.look = 'None'
sc.render.film_transparent = False
sc.render.use_compositing = False
if os.environ.get('LINE_ONLY'):
    sc.render.filepath = '/tmp/_skip.png'
else:
    sc.render.filepath = OUT + '/mask_regions.png'
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGB'
bpy.ops.render.render(write_still=True)
print('LINE masks')

# finer ids for the drawing: which tree kind, and stones apart from the lawn they sit in
ID = {'pine': (0.2, 1, 0.2), 'maple': (0.2, 0.6, 0.2), 'shrub': (0.6, 1, 0.6), 'forest': (0, 0.4, 0),
      'stone': (1, 0.6, 0), 'turf': (0.6, 0.6, 0)}
def sub(o):
    n = o.name
    if n.startswith('Pine '):
        return 'pine'
    if n.startswith('G maple'):
        return 'maple'
    if n.startswith(('G shrub', 'G fern')):
        return 'shrub'
    if n.startswith(('G boulder', 'G lake rock', 'Lake shore stones')):
        return 'stone'
    if n.startswith(('Ground', 'Lawn', 'Wild flower', 'G path joint')):
        return 'turf'                                   # bare lawn: no strokes belong on it
    if region(o) == 'trees':
        return 'forest'
    return None
TWIG_OWNER = {}
for o in bpy.data.objects:
    if o.type in ('MESH', 'CURVE') and sub(o):
        o.color = (*ID[sub(o)], 1)
# twig sources are shared: colour them by their main user
for name_, k in (('Twig spruce near', 'pine'), ('Twig maple', 'maple'), ('Twig shrub', 'shrub'), ('Lawn patch', 'turf')):
    if bpy.data.objects.get(name_):
        bpy.data.objects[name_].color = (*ID[k], 1)
if os.environ.get('LINE_ONLY', 'none') == 'none':
    sc.render.filepath = OUT + '/mask_ids.png'
    bpy.ops.render.render(write_still=True)
print('LINE ids')

# near pines: hand-drawn tier strokes, computed here (projected to pixels), drawn by loading_compose.py
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
cam = sc.camera
def px(p):
    v = world_to_camera_view(sc, cam, Vector(p))
    return [v.x * W, (1 - v.y) * H]
pines = []
rng = np.random.default_rng(7)
for o in bpy.data.objects:
    if not (o.name.startswith('Pine ') and o.type == 'MESH'):
        continue
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    dg = bpy.context.evaluated_depsgraph_get()
    pts = [i.matrix_world.translation for i in dg.object_instances if i.is_instance and i.parent and i.parent.original == o]
    org = o.matrix_world.translation
    h = max([p.z for p in pts] + [v.z for v in bb]) - org.z
    rad = sorted((p - org).to_2d().length for p in pts) or [h * 0.25]
    R = rad[int(len(rad) * 0.9)]                       # crown radius without stray tips
    camd = (org - cam.location).to_2d().normalized()
    side = Vector((-camd.y, camd.x, 0))
    base, tiers = 0.1, 14
    strokes = []
    def at(f, x):                                       # f: height fraction, x: across in crown radii
        return px(org + side * x + Vector((0, 0, h * f)))
    for sgn in (-1, 1):
        line = [at(1.0, 0)]
        for i in range(1, tiers + 1):
            f = 1 - i / tiers * (1 - base)
            r = R * (1 - f) / (1 - base)
            r *= rng.uniform(0.9, 1.08)
            line.append(at(f + 0.012, sgn * r * 0.84))     # small saw teeth along the cone edge
            line.append(at(f - 0.012, sgn * r))
        strokes.append(line)
        # drooping branch tips: short strokes just inside the edge, every other tier
        for i in range(2, tiers, 2):
            f = 1 - i / tiers * (1 - base)
            r = R * (1 - f) / (1 - base)
            strokes.append([at(f + 0.03, sgn * r * 0.55), at(f + 0.005, sgn * r * 0.78), at(f - 0.01, sgn * r * 0.9)])
    strokes.append([at(0.0, 0), at(base + 0.02, 0)])                  # trunk
    pines.append(strokes)
import json
json.dump({'pines': pines}, open(OUT + '/strokes.json', 'w'))
print('LINE pines', len(pines))

# ---------------------------------------------------------------- Freestyle strokes
# heavy instanced foliage and the lawn would drown the drawing in noise: off for the line pass
HIDE = ('Lawn', 'Wild flowers', 'G path joint', 'G periwinkle', 'G moss', 'Moss') + TREES
for o in bpy.data.objects:
    if o.type in ('MESH', 'CURVE') and o.name.startswith(HIDE):
        o.hide_render = True
sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items} else 'BLENDER_EEVEE_NEXT'
sc.render.use_freestyle = True
sc.render.line_thickness_mode = 'ABSOLUTE'
sc.render.film_transparent = True
vl = sc.view_layers[0]
fs = vl.freestyle_settings
fs.as_render_pass = False
fs.crease_angle = math.radians(115)          # fewer creases: the house read too dark
for ls in list(fs.linesets):
    fs.linesets.remove(ls)

def lineset(name, cols, thick, crease=True, noise=1.0, border=True):
    ls = fs.linesets.new(name)
    ls.select_by_visibility = True
    ls.select_by_edge_types = True
    ls.select_by_collection = False
    ls.select_silhouette = ls.select_external_contour = True
    ls.select_border = border            # terrain is built from loose quads: every face edge is a border
    ls.select_crease = crease
    st = ls.linestyle
    st.color = (0, 0, 0)
    st.thickness = thick
    st.chaining = 'PLAIN'
    st.use_chain_count = False
    st.caps = 'BUTT'
    if noise:
        g = st.geometry_modifiers.new('wobble', 'PERLIN_NOISE_1D')
        g.frequency, g.amplitude, g.octaves = 6.0, 1.2 * noise, 2
        g2 = st.geometry_modifiers.new('overshoot', 'BACKBONE_STRETCHER')
        g2.backbone_length = 3.0
    t = st.thickness_modifiers.new('taper', 'ALONG_STROKE')
    t.mapping = 'CURVE'
    t.blend = 'MULTIPLY'
    cm = t.curve.curves[0]
    cm.points[0].location = (0, 0.35)
    cm.points.new(0.5, 1.0)
    cm.points[-1].location = (1, 0.35)
    return ls

# fine detail that only turns into a dark tangle at this size (10-22, user): blinds and sheers in the
# windows, kitchen tiles, utensils and shelf clutter, the books
CLUTTER = (' - blind', ' - tape', ' - gauze', 'Splashback', 'Knife strip', 'Oil rack', 'Dish shelf - ceramic',
           'Bookcase - b', 'Attic bookshelf - b', 'jar_lid', 'PH Lemon', 'PH Shelf', 'PH Table', 'PH Worktop',
           'PH Desk jug', 'PH Side table jug', 'Saucepan', 'Kitchen downlights', 'Open shelves - basket',
           'Cafe curtain', 'Hood and wall cabinet - steel')

def render_region(name, keep, thick, crease=True, noise=1.0, border=True, pred=None):
    """Only the region's objects are rendered, in flat white (a material override), with black Freestyle
    strokes; the stroke layer is then 'darkness x coverage'. One clean layer per region."""
    for ls in list(fs.linesets):
        fs.linesets.remove(ls)
    lineset(name, None, thick, crease, noise, border)
    saved = {}
    for o in bpy.data.objects:
        if o.type in ('MESH', 'CURVE'):
            saved[o.name] = (o.hide_render, o.is_holdout)
            if (pred(o) if pred else region(o) == keep):
                if pred:
                    o.hide_render = False
                    for m in o.modifiers:
                        if m.name == 'Twigs':
                            saved.setdefault('_twigs', []).append((o.name, m.show_render))
                            m.show_render = False             # branches only
            else:
                o.hide_render = True
            if keep == 'house' and any(k in o.name for k in CLUTTER):
                o.hide_render = True
    tmp = f'{OUT}/_raw_{name}.png'
    sc.render.filepath = tmp
    sc.render.image_settings.color_mode = 'RGBA'
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(tmp)
    px = np.array(im.pixels[:], dtype=np.float32).reshape(H, W, 4)
    bpy.data.images.remove(im)
    os.remove(tmp)
    ink = px[..., 3] * (1 - px[..., :3].mean(-1))
    out = np.zeros((H, W, 4), np.float32)
    out[..., :3] = (0.24, 0.2, 0.17)
    out[..., 3] = np.clip(ink * 1.4, 0, 1)
    o_ = bpy.data.images.new('_ink', W, H, alpha=True)
    o_.pixels.foreach_set(out.ravel())
    o_.filepath_raw = f'{OUT}/lines_{name}.png'
    o_.file_format = 'PNG'
    o_.save()
    bpy.data.images.remove(o_)
    for n, v in saved.items():
        if n == '_twigs':
            for on, sr in v:
                bpy.data.objects[on].modifiers['Twigs'].show_render = sr
            continue
        bpy.data.objects[n].hide_render, bpy.data.objects[n].is_holdout = v
    print('LINE region', name)

white = bpy.data.materials.new('_white')
white.use_nodes = True
nt = white.node_tree
nt.nodes.clear()
em = nt.nodes.new('ShaderNodeEmission')
em.inputs['Color'].default_value = (1, 1, 1, 1)
nt.links.new(em.outputs[0], nt.nodes.new('ShaderNodeOutputMaterial').inputs['Surface'])
vl.material_override = white
sc.world.use_nodes = True
sc.view_settings.view_transform = 'Standard'

if not os.environ.get('LINE_ONLY') or 'maple' in os.environ['LINE_ONLY']:
    render_region('maple', None, 1.3, False, 1.0, False, pred=lambda o: o.name.startswith('G maple'))
if os.environ.get('LINE_ONLY') == 'none':
    raise SystemExit
for name, thick, crease, noise, border in (('house', 1.1, True, 0.8, True), ('mountains', 1.6, False, 1.0, False),
                                           ('lake', 1.4, False, 1.0, True), ('grass', 1.2, True, 1.0, False)):
    if os.environ.get('LINE_ONLY') and name not in os.environ['LINE_ONLY'].split(','):
        continue
    render_region(name, name, thick, crease, noise, border)
