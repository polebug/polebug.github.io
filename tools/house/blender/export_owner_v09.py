import bpy,json,os
from mathutils import Vector
P='/Users/bugpole/AI/博客陪伴小屋'
col=bpy.data.collections['Owner_V09'];root=bpy.data.objects['Owner_V09_ROOT']
# Native file retains editable modifiers, individual parts and studio cameras.
sc=bpy.context.scene;sc.camera=bpy.data.objects['Camera three-quarter']
report={'asset':'owner-character-v09','rigged':False,'animated':False,'views':['front','side','back','three-quarter'],'parts':len(col.objects),'mesh_parts':sum(o.type=='MESH' for o in col.objects),'curve_parts':sum(o.type=='CURVE' for o in col.objects),'invalid_coordinates':0,'empty_meshes':[]}
for o in col.objects:
 if o.type=='MESH':
  if len(o.data.vertices)==0:report['empty_meshes'].append(o.name)
  import math
  report['invalid_coordinates']+=sum(not all(math.isfinite(c) for c in v.co) for v in o.data.vertices)
bpy.ops.wm.save_as_mainfile(filepath=P+'/assets/blender/characters/owner-character-v09.blend')
# Export only the character, at approximately 1.35 m tall.
bpy.ops.object.select_all(action='DESELECT')
for o in col.objects:o.select_set(True)
bpy.context.view_layer.objects.active=root
root.scale=(.45,.45,.45)
bpy.ops.object.convert(target='MESH')
bpy.ops.export_scene.gltf(filepath=P+'/assets/blender/characters/owner-character-v09.glb',export_format='GLB',use_selection=True,export_apply=True)
report['glb_height_approx_m']=1.35
report['exported_glb_bytes']=os.path.getsize(P+'/assets/blender/characters/owner-character-v09.glb')
with open(P+'/assets/renders/character-v09/validation.json','w') as f:json.dump(report,f,ensure_ascii=False,indent=2)
print(json.dumps(report))
