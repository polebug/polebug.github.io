"""Rebuild the floor-2/3 boards with wide planks (user, 10-22) in the current companion-house.blend;
build_architecture.py carries the same width for future rebuilds.

    Blender -b assets/blender/companion-house.blend --python assets/blender/scripts/floor_boards_wide_20261022.py

Only the board mesh changes: material, colour, bevel and the per-board grain UV are kept.
"""
import bpy, bmesh, os, sys, random
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from house_spec import *       # noqa: F401,F403
from meshkit import Mesh

src = open(os.path.join(HERE, 'build_architecture.py')).read()
ns = {'rng': random.Random(20261022)}
exec(src[src.index('def floor_boards('):src.index('# 10-20: the fireplace')], ns)
gsrc = open(os.path.join(HERE, 'build_materials_real.py')).read()
g = {'bmesh': bmesh, 'random': random, 'np': np}
exec(gsrc[gsrc.index('def grain_uv('):gsrc.index('wood = grain_material(')], g)

m = Mesh()
ns['floor_boards'](m, FLOOR[2], -IN_X, IN_X, TRUSS_Y, DEPTH)
ns['floor_boards'](m, FLOOR[3], -IN_X, IN_X, TRUSS_Y, DEPTH)
o = bpy.data.objects['Floor boards']
old = o.data
new = bpy.data.meshes.new('Floor boards')
new.from_pydata(m.v, [], m.f)
for mat in old.materials:
    new.materials.append(mat)
bm = bmesh.new(); bm.from_mesh(new)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(new); bm.free()
o.data = new
bpy.data.meshes.remove(old)
g['grain_uv'](o, set())
print('FLOOR boards', len(new.polygons) // 6)
bpy.ops.wm.save_mainfile()
