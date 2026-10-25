"""Apply the 10-21 yard changes (user) to the current companion-house.blend without a full rebuild;
build_environment.py carries the same changes for future rebuilds.

    Blender -b assets/blender/companion-house.blend --python assets/blender/scripts/yard_edit_20261021.py

- the three boulders on the front lawn and their gravel go; the lawn grows where they stood
- the lily bowl goes
- the path joints are the lawn itself: the separate moss strip goes, the lawn scatter grows through the
  path and drops the points under the slabs (garden.mask_under)
- the slate slabs get a real dark stone texture (Rock035, box-mapped)
"""
import bpy, math, os, sys
from mathutils import Vector, noise
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import garden as G
G.TEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'textures')

OB = bpy.data.objects
front = [o for o in OB if o.name.startswith('G boulder ') and not o.name.startswith('G boulder gravel')
         and o.matrix_world.translation.y < 0]
holes = []
for o in front:
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    x0, x1 = min(v.x for v in bb), max(v.x for v in bb)
    y0, y1 = min(v.y for v in bb), max(v.y for v in bb)
    holes.append(((x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2 + 0.3, (y1 - y0) / 2 + 0.3))
    gravel = OB.get('G boulder gravel ' + o.name.split()[-1])
    if gravel:
        OB.remove(gravel)
    OB.remove(o)
if OB.get('G water bowl'):
    p = OB['G water bowl'].matrix_world.translation
    holes.append((p.x, p.y, 0.55, 0.55))
    OB.remove(OB['G water bowl'])

# lawn where the boulders and the bowl stood (same density rule as build_environment.density)
lawn = OB['Lawn'].data
at = lawn.attributes['dens']
filled = 0
for v in lawn.vertices:
    x, y = v.co.x, v.co.y
    if at.data[v.index].value == 0 and any(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 < 1 for cx, cy, rx, ry in holes):
        at.data[v.index].value = 0.55 + 0.45 * (noise.noise(Vector((x * 0.3, y * 0.3, 0))) * 0.5 + 0.5)
        filled += 1

# path joints: the lawn itself, none under the slabs
for n in ('G path joint moss', 'G path joint bed'):
    if OB.get(n):
        OB.remove(OB[n])
PATH = (-0.75, 0.75, -5.6, -1.0)
for v in lawn.vertices:
    x, y = v.co.x, v.co.y
    if PATH[0] - 0.4 < x < PATH[1] + 0.4 and PATH[2] - 0.4 < y < PATH[3] and at.data[v.index].value == 0:
        at.data[v.index].value = 0.55 + 0.45 * (noise.noise(Vector((x * 0.3, y * 0.3, 0))) * 0.5 + 0.5)
G.mask_under(OB['Lawn'].modifiers['Scatter'].node_group, OB['G slate path'])

# dark slate with a real stone texture
slate = G.textured_mat('G slate dark', 'Rock035', 1.0, (2.2, 2.2, 2.1))
for s in OB['G slate path'].material_slots:
    s.material = slate

OB['G slate path'].location.z = -0.03                 # slabs set into the lawn, ~1 cm proud
bpy.ops.wm.save_mainfile()
print('YARD_EDIT removed', len(front), 'boulders + bowl; lawn verts filled', filled)
