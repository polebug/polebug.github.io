"""Light first-screen data for the "building the house" loading scene (2026-10-22).

    Blender -b assets/blender/companion-house.blend --python assets/blender/scripts/export_intro.py

While house.glb is still downloading the page shows the landscape, the owner at work on the lawn, and
the house as a pale blueprint that turns solid as the download goes on. This writes, in three.js axes:
  web/house/assets/intro.bin   float32 / uint32 blocks (offsets in intro.json)
  web/house/assets/intro.json  overview camera, lake water mesh, blueprint lines (the shell's feature
                               edges) and faces, the house's height range
The source .blend is never saved.
"""
import bpy, bmesh, json, math, os
import numpy as np

P = '/Users/bugpole/AI/博客陪伴小屋'
OUT = P + '/web/house/assets'
SHELL = ('11_Frame', '12_Walls', '13_Floors', '14_Windows', '15_Roof', '16_Stonework', '17_Flues')
# parts left out of the drawing: per-tile, per-board and per-stone detail would fill it in solid
SKIP = ('Bolt heads', 'Roof tiles', 'Tile battens', 'Floor boards', 'Plinth facing stones', 'Window glass')
ANGLE = math.radians(float(os.environ.get('INTRO_ANGLE', 35)))     # crease angle for a drawn edge

def t(v):                                     # Blender z-up -> three y-up
    return (v[0], v[2], -v[1])

def mesh_of(o):
    """The modelled mesh without its modifiers: bevels would double every drawn edge."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.transform(o.matrix_world)
    return bm

lines, fpos, fidx = [], [], []
for cn in SHELL:
    for o in bpy.data.collections[cn].all_objects:
        if o.type != 'MESH' or o.hide_render or o.name.startswith(SKIP):
            continue
        bm = mesh_of(o)
        bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(2), verts=bm.verts, edges=bm.edges)
        for e in bm.edges:
            if len(e.link_faces) != 2 or e.calc_face_angle(0) > ANGLE:
                lines += [t(e.verts[0].co), t(e.verts[1].co)]
        bmesh.ops.triangulate(bm, faces=bm.faces)
        base = len(fpos)
        fpos += [t(v.co) for v in bm.verts]
        bm.verts.index_update()
        fidx += [base + v.index for f in bm.faces for v in f.verts]
        bm.free()
        print('INTRO', o.name, len(lines) // 2, 'lines', len(fidx) // 3, 'tris')

lake = bpy.data.objects['Lake']
bm = mesh_of(lake)
bmesh.ops.triangulate(bm, faces=bm.faces)
bm.verts.index_update()
lpos = [t(v.co) for v in bm.verts]
lidx = [v.index for f in bm.faces for v in f.verts]
bm.free()

cam = bpy.data.objects['Cam_Overview']
q = cam.matrix_world.to_quaternion()
blocks, buf = {}, bytearray()
def put(name, arr, dtype):
    a = np.asarray(arr, dtype).ravel()
    blocks[name] = {'offset': len(buf), 'count': int(a.size), 'type': 'f32' if dtype == np.float32 else 'u32'}
    buf.extend(a.tobytes())
put('lines', lines, np.float32)
put('facePos', fpos, np.float32)
put('faceIdx', fidx, np.uint32)
put('lakePos', lpos, np.float32)
put('lakeIdx', lidx, np.uint32)
ys = np.asarray(fpos, np.float32)[:, 1]
info = {
    'camera': {'pos': list(t(cam.matrix_world.translation)), 'quat': [q.w, q.x, q.y, q.z],   # Blender w,x,y,z, z-up
               'hfov': cam.data.angle},
    'house': {'yMin': float(ys.min()), 'yMax': float(ys.max())},
    'blocks': blocks,
}
open(OUT + '/intro.bin', 'wb').write(buf)
json.dump(info, open(OUT + '/intro.json', 'w'), indent=1)
print('INTRO', len(lines) // 2, 'lines', len(fidx) // 3, 'tris', len(lidx) // 3, 'lake tris', len(buf) // 1024, 'KB')
