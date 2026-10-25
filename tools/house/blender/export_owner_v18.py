"""Export owner v18 (rig, body, book prop, all actions) to GLB and check what landed in the file.

    Blender -b assets/blender/characters/owner-character-v18.blend --python assets/blender/scripts/export_owner_v18.py
"""
import bpy, json, os, struct

P = '/Users/bugpole/AI/博客陪伴小屋'
OUT = P + '/assets/blender/characters/owner-character-v18.glb'
rig = bpy.data.objects['Owner_Rig']
rig.animation_data.action = bpy.data.actions['Idle']
bpy.context.scene.frame_set(0)
bpy.ops.object.select_all(action='DESELECT')
for n in ('Owner_Rig', 'Owner_Body', 'Book'):
    bpy.data.objects[n].select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.export_scene.gltf(
    filepath=OUT, export_format='GLB', use_selection=True,
    export_apply=False,                     # applying modifiers would drop the Blink shape keys
    export_skins=True, export_morph=True, export_morph_normal=True,
    export_animations=True, export_animation_mode='ACTIONS', export_force_sampling=True,
    export_frame_step=1, export_optimize_animation_size=True, export_anim_single_armature=True,
    export_yup=True)

# read the GLB's JSON chunk back
with open(OUT, 'rb') as f:
    f.read(12)
    n, _ = struct.unpack('<II', f.read(8))
    g = json.loads(f.read(n))
mesh = next(m for m in g['meshes'] if m['name'] == 'Owner_Body')
report = {
    'bytes': os.path.getsize(OUT),
    'animations': {a['name']: len(a['channels']) for a in g.get('animations', [])},
    'joints': len(g['skins'][0]['joints']),
    'morph_targets': mesh.get('extras', {}).get('targetNames'),
    'primitives': len(mesh['primitives']),
    'nodes': [nd['name'] for nd in g['nodes'] if nd.get('name') in ('Book', 'Owner_Body', 'Owner_Rig', 'Hand.L')],
}
print('OWNER_V18_GLB', json.dumps(report, ensure_ascii=False))
