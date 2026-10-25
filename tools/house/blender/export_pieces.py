"""Furniture pieces for the loading build (2026-10-22): one box per item on each floor, in three.js axes.

    Blender -b assets/blender/companion-house.blend --python assets/blender/scripts/export_pieces.py

The web house bakes each floor's furniture into one mesh (BAKED_floor1-3), so the page cannot tell a
chair from a sofa. These boxes let it: every vertex goes to the smallest box that holds it, and each
item then drops into its room on its own, left to right. Parts of one item ("F1 TV console - walnut",
"- iron", ...) share a box. Rugs are left out: the page lays them first from their own mesh.
The yard (2026-10-22) goes the same way after the house: trees, shrubs, ferns, lights, the woodpile, and
each slab of the slate path and each tread of the timber steps on its own (their loose parts); the
periwinkle and ring stones round each maple drop as one cluster per side.
Writes web/house/assets/pieces.json. The source .blend is never saved.
"""
import bpy, bmesh, json, re
from mathutils import Vector

OUT = '/Users/bugpole/AI/博客陪伴小屋/web/house/assets/pieces.json'
FLOORS = {'floor1': '21_Floor1', 'floor2': '22_Floor2', 'floor3': '23_Floor3', 'yard': '31_Yard'}
SPLIT = ('G slate path', 'G timber steps')            # one object, many slabs / treads: a piece each
dg = bpy.context.evaluated_depsgraph_get()

def item(name):
    """'F1 TV console - iron' -> 'F1 TV console'; 'PH Money tree pot ceramic_pot' -> 'PH Money tree'."""
    name = name.split(' - ')[0].strip()
    if name.startswith('PH '):                         # pot plants: the words before the asset's own name
        words = []
        for w in name.split():
            if '_' in w:
                break
            words.append(w)
        name = ' '.join(words)
        if name.endswith(' pot'):
            name = name[:-4]
    return re.sub(r'^(G (periwinkle|ring stone) [LR])\d+$', r'\1', name)   # one cluster each, per maple

def loose_boxes(o):
    """World boxes of an object's loose parts (its evaluated mesh)."""
    ev = o.evaluated_get(dg)
    bm = bmesh.new(); bm.from_mesh(ev.to_mesh()); bm.transform(ev.matrix_world); ev.to_mesh_clear()
    seen, boxes = set(), []
    for v0 in bm.verts:
        if v0.index in seen:
            continue
        stack, part = [v0], []
        seen.add(v0.index)
        while stack:
            v = stack.pop(); part.append(v.co)
            for e in v.link_edges:
                w = e.other_vert(v)
                if w.index not in seen:
                    seen.add(w.index); stack.append(w)
        boxes.append(([min(c[i] for c in part) for i in range(3)], [max(c[i] for c in part) for i in range(3)]))
    bm.free()
    return boxes

out = {}
for g, cn in FLOORS.items():
    boxes = {}
    for o in bpy.data.collections[cn].all_objects:
        if o.type != 'MESH' or o.hide_render or 'rug' in o.name.lower():
            continue
        if o.name.startswith(SPLIT):
            for k, (lo, hi) in enumerate(loose_boxes(o)):
                boxes[f'{item(o.name)} {k}'] = [lo, hi]
            continue
        ev = o.evaluated_get(dg)
        pts = [ev.matrix_world @ Vector(c) for c in ev.bound_box]
        lo = [min(p[i] for p in pts) for i in range(3)]
        hi = [max(p[i] for p in pts) for i in range(3)]
        b = boxes.setdefault(item(o.name), [lo, hi])
        b[0] = [min(a, c) for a, c in zip(b[0], lo)]
        b[1] = [max(a, c) for a, c in zip(b[1], hi)]
    # three axes: (x, z, -y); keep min/max ordered
    out[g] = [{'name': n, 'min': [lo[0], lo[2], -hi[1]], 'max': [hi[0], hi[2], -lo[1]]}
              for n, (lo, hi) in sorted(boxes.items())]
    print('PIECES', g, len(out[g]))
json.dump(out, open(OUT, 'w'))
