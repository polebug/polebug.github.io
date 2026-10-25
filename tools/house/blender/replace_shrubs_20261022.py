"""The six front-yard shrubs (G shrub 0-5) as Poly Haven's Searsia Lucida (CC0), 2026-10-22.

The user found the procedural shrubs (trees.build_shrub: stems + instanced leaf twigs) "特别假". Each one
is replaced by a cluster of three Searsia Lucida variants (their light LOD2), one large and two smaller
ones overlapping at other angles, so it reads as one dense bush ("太稀疏了，请把灌木做得更茁密", 10-22);
the cluster goes to the same spot, scaled to the old shrub's width and height (squashed by 20 % at
most, so the leaves keep their shape). The new objects keep the
names G shrub 0-5 (the page's build animation and pieces.json go by them) and carry 'searsia' = 1, so
export_web.py treats them like the other Poly Haven plants (leaf cards with a baked light factor).

    Blender -b assets/blender/companion-house.blend --python assets/blender/scripts/replace_shrubs_20261022.py
Saves companion-house.blend (backup first: companion-house.backup-2026-10-22-pre-shrubs.blend).
build_environment.py calls replace() after building the old shrubs, so a rebuild comes out the same.
"""
import bpy, bmesh, os, sys
import numpy as np
from mathutils import Matrix, Vector

P = '/Users/bugpole/AI/博客陪伴小屋'
SRC = P + '/assets/third-party/polyhaven/searsia_lucida'
# shrub -> its cluster: (variant, dx, dy as a share of the main bush's width, turn about z, relative size);
# variants by size a > b > c > d > e > f > g
CHOICE = {
    0: [('b', 0, 0, 0.0, 1.0), ('d', 0.30, 0.08, 2.1, 0.85), ('e', -0.30, -0.10, 4.0, 0.9)],
    1: [('c', 0, 0, 1.9, 1.0), ('d', -0.26, 0.10, 4.4, 0.8), ('e', 0.28, -0.08, 0.6, 0.85)],
    2: [('c', 0, 0, 4.1, 1.0), ('e', 0.28, 0.06, 1.2, 0.9), ('d', -0.24, -0.10, 2.9, 0.75)],
    3: [('c', 0, 0, 0.8, 1.0), ('e', -0.28, 0.08, 3.3, 0.9), ('d', 0.26, -0.10, 5.6, 0.8)],
    4: [('b', 0, 0, 2.7, 1.0), ('e', 0.30, -0.06, 5.0, 0.9), ('d', -0.28, 0.10, 1.4, 0.85)],
    5: [('c', 0, 0, 5.3, 1.0), ('d', 0.26, 0.10, 2.2, 0.8), ('e', -0.26, -0.08, 0.3, 0.9)],
}


def _bounds(o):
    """World bounds of an object with its instances (the old shrubs' twigs are instanced)."""
    dg = bpy.context.evaluated_depsgraph_get()
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for inst in dg.object_instances:
        owner = inst.parent.original if inst.is_instance and inst.parent else inst.object.original
        if owner != o:
            continue
        for c in inst.object.bound_box:
            p = inst.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, p)); hi = Vector(map(max, hi, p))
    return lo, hi


def _materials():
    """Plain Principled materials the exporters understand: the leaves take colour and cut-out from one
    RGBA picture (the photo's colour + its alpha mask), the wood the colour only."""
    rgba_path = SRC + '/textures/searsia_lucida_leaves_rgba_2k.png'
    if not os.path.exists(rgba_path):
        d = bpy.data.images.load(SRC + '/textures/searsia_lucida_diff_2k.jpg')
        a = bpy.data.images.load(SRC + '/textures/searsia_lucida_alpha_2k.png')
        w, h = d.size
        px = np.array(d.pixels[:], np.float32).reshape(h, w, 4)
        px[..., 3] = np.array(a.pixels[:], np.float32).reshape(h, w, 4)[..., 0]
        out = bpy.data.images.new('_sl_rgba', w, h, alpha=True)
        out.pixels.foreach_set(px.ravel())
        out.filepath_raw = rgba_path
        out.file_format = 'PNG'
        out.save()
        for im in (d, a, out):
            bpy.data.images.remove(im)
    img = bpy.data.images.load(rgba_path, check_existing=True)
    img.name = 'searsia_lucida_leaves_rgba'
    mats = {}
    for name, cut in (('G searsia leaves', True), ('G searsia wood', False)):
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
        tx = nt.nodes.new('ShaderNodeTexImage')
        tx.image = img
        nt.links.new(tx.outputs['Color'], bs.inputs['Base Color'])
        nt.links.new(tx.outputs['Alpha'], bs.inputs['Alpha'])   # both: the LOD2 twigs are cut-out cards as well
        bs.inputs['Roughness'].default_value = 0.65
        nt.links.new(bs.outputs[0], out.inputs[0])
        mats[cut] = m
    return mats


def replace():
    old = {k: bpy.data.objects.get(f'G shrub {k}') for k in CHOICE}
    if all(o is not None and o.get('searsia') for o in old.values()):
        print('SHRUBS already Searsia')
        return
    with bpy.data.libraries.load(SRC + '/searsia_lucida_2k.blend', link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n.endswith('_LOD2')]
    variants = {o.name.split('_')[2]: o for o in dst.objects if o is not None}
    mats = _materials()
    for o in variants.values():                          # leaves cut out (slot 0), the rest plain wood (slot 1)
        leaf = [sl is not None and sl.name.startswith('searsia_lucida_leaves') for sl in o.data.materials]
        for poly in o.data.polygons:
            poly.material_index = 0 if leaf[poly.material_index] else 1
        o.data.materials.clear()
        o.data.materials.append(mats[True]); o.data.materials.append(mats[False])
        # the variant's own origin: centre of its base, on the ground
        co = np.array([v.co for v in o.data.vertices])
        lo, hi = co.min(0), co.max(0)
        o.data.transform(Matrix.Translation(Vector((-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]))))
    for k, o in old.items():
        if o is None:
            continue
        lo, hi = _bounds(o)
        cols = list(o.users_collection)
        want_w, want_h = max(hi.x - lo.x, hi.y - lo.y), hi.z - lo.z
        centre = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, 0))
        bpy.data.objects.remove(o, do_unlink=True)
        # the cluster as one mesh, around its own base centre
        main_w = max(variants[CHOICE[k][0][0]].dimensions.x, variants[CHOICE[k][0][0]].dimensions.y)
        me = bpy.data.meshes.new(f'G shrub {k}')
        bm = bmesh.new()
        for v, dx, dy, rz, rs in CHOICE[k]:
            part = variants[v].data.copy()
            part.transform(Matrix.Translation((dx * main_w, dy * main_w, 0)) @ Matrix.Rotation(rz, 4, 'Z') @ Matrix.Scale(rs, 4))
            bm.from_mesh(part)
            bpy.data.meshes.remove(part)
        bm.to_mesh(me)
        bm.free()
        for m in (mats[True], mats[False]):
            me.materials.append(m)
        co = np.array([v.co for v in me.vertices])
        lo_, hi_ = co.min(0), co.max(0)
        me.transform(Matrix.Translation(Vector((-(lo_[0] + hi_[0]) / 2, -(lo_[1] + hi_[1]) / 2, -lo_[2]))))
        dims = Vector(hi_ - lo_)
        s_xy = want_w / max(dims.x, dims.y)
        s_z = min(s_xy, max(0.8 * s_xy, want_h / dims.z))
        n = bpy.data.objects.new(f'G shrub {k}', me)
        for c in cols:
            c.objects.link(n)
        n.location, n.scale = centre, (s_xy, s_xy, s_z)
        n['searsia'] = 1
        print('SHRUB', k, [c[0] for c in CHOICE[k]], 'faces', len(me.polygons), 'scale', round(s_xy, 3), round(s_z, 3),
              'size', [round(d, 2) for d in (dims.x * s_xy, dims.y * s_xy, dims.z * s_z)], 'was', [round(want_w, 2), round(want_h, 2)])
    for o in variants.values():
        bpy.data.objects.remove(o, do_unlink=True)


if __name__ == '__main__':
    path = bpy.data.filepath
    bpy.ops.wm.save_as_mainfile(filepath=path.replace('.blend', '.backup-2026-10-22-pre-shrubs.blend'), copy=True)
    replace()
    bpy.ops.wm.save_as_mainfile(filepath=path)
    print('SHRUBS saved')
