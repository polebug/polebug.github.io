import bpy,os,math,json
P='/Users/bugpole/AI/博客陪伴小屋';OUT=P+'/assets/renders/character-v17';os.makedirs(OUT,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=P+'/assets/blender/characters/owner-character-v16.blend')
col=bpy.data.collections['Owner_V16'];col.name='Owner_V17'
root=bpy.data.objects['Owner_V16_ROOT'];root.name='Owner_V17_ROOT'
hair=next(o for o in col.objects if o.name.startswith('Hair •'))
m=bpy.data.materials.new('Hair accessories • warm brown');m.use_nodes=True;m.diffuse_color=(.14,.055,.022,1)
p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=m.diffuse_color;p.inputs['Roughness'].default_value=.65
hair.data.materials[4]=m
hair['source']=hair['source'].replace('pink ties','brown ties')
for o in col.objects:
 if o.name.startswith('Round eyeglass rim'):
  for sp in o.data.splines:
   for pt in sp.bezier_points:pt.co.y=-.47
 if o.name.startswith('Glasses bridge'):
  for sp in o.data.splines:
   for pt in sp.bezier_points:pt.co.y=-.47
 if o.name.startswith('Glasses temple'):
  s=-1 if o.name.endswith('-1') else 1
  sp=o.data.splines[0]
  if len(sp.bezier_points)<5:sp.bezier_points.add(5-len(sp.bezier_points))
  pts=[(s*.449,-.47,2.36),(s*.515,-.39,2.38),(s*.545,-.14,2.39),(s*.545,-.015,2.38),(s*.53,.035,2.32)]
  for pt,co in zip(sp.bezier_points,pts):pt.co=co;pt.handle_left_type='AUTO';pt.handle_right_type='AUTO'
sc=bpy.context.scene;sc.camera=bpy.data.objects['Camera three-quarter'];sc.cycles.samples=32
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=P+'/assets/blender/characters/owner-character-v17.blend')
for view in ['three-quarter','side','front','back']:
 sc.camera=bpy.data.objects['Camera '+view];sc.render.filepath=OUT+'/'+view+'.png';bpy.ops.render.render(write_still=True)
bpy.ops.object.select_all(action='DESELECT')
for o in col.objects:o.select_set(True)
bpy.context.view_layer.objects.active=hair;bpy.ops.object.convert(target='MESH')
bpy.ops.export_scene.gltf(filepath=P+'/assets/blender/characters/owner-character-v17.glb',export_format='GLB',use_selection=True,export_apply=True,export_animations=False)
print('OWNER_V17_COMPLETE')
