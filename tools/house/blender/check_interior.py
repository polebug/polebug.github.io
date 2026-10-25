"""Clash check for one interior floor: each asset's bounds against the room and the other assets.
Run:  Blender -b assets/blender/companion-house.blend --python check_interior.py -- 21_Floor1 1
Bounding boxes are coarse for rotated or hollow pieces, so every hit is then checked by eye."""
import bpy, sys, os
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from house_spec import *   # noqa
coll, f = sys.argv[-2], int(sys.argv[-1])
zlo, zhi = FLOOR[f], (FLOOR[f + 1] - SLAB if f < 3 else 99)
def bounds(e):
    pts = [o.matrix_world @ Vector(c) for o in e.children for c in o.bound_box]
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]
assets = [(e.name, *bounds(e)) for e in bpy.data.collections[coll].objects if e.type == 'EMPTY']
for n, lo, hi in assets:
    bad = []
    if lo[0] < -IN_X - 0.005 or hi[0] > IN_X + 0.005: bad.append(f"x {lo[0]:.3f}..{hi[0]:.3f}")
    if lo[1] < -0.005 or hi[1] > DEPTH + 0.005: bad.append(f"y {lo[1]:.3f}..{hi[1]:.3f}")
    if lo[2] < zlo - 0.005 or hi[2] > zhi + 0.005: bad.append(f"z {lo[2]:.3f}..{hi[2]:.3f}")
    if f == 3:   # attic: stay under the rafters, and under the purlins where they pass overhead
        xs = (abs(lo[0]), abs(hi[0]))
        top = roof_under(max(xs))
        for px in (0.0, -MID_PX, MID_PX):
            if hi[0] > px - PURLIN / 2 and lo[0] < px + PURLIN / 2:
                top = min(top, roof_under(px) - PURLIN)
        if hi[2] > top + 0.005: bad.append(f"roof: top {hi[2]:.3f} > {top:.3f}")
    if bad: print("ROOM", n, "; ".join(bad))
for i, (n1, l1, h1) in enumerate(assets):
    for n2, l2, h2 in assets[i + 1:]:
        ov = [min(h1[k], h2[k]) - max(l1[k], l2[k]) for k in range(3)]
        if all(v > 0.005 for v in ov):
            print("OVERLAP", n1, "|", n2, [round(v, 3) for v in ov])
