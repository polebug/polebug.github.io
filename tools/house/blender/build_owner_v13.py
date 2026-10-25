import bpy,math,json,os
from mathutils import Vector,Matrix
P='/Users/bugpole/AI/博客陪伴小屋';OUT=P+'/assets/renders/character-v13';os.makedirs(OUT,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=P+'/assets/blender/characters/owner-character-v12.blend')
col=bpy.data.collections['Owner_V12'];col.name='Owner_V13';root=bpy.data.objects['Owner_V12_ROOT'];root.name='Owner_V13_ROOT'
# Apply the static hierarchy and mesh modifiers to a separate riggable version.
for o in list(col.objects):
 if o.type in {'MESH','CURVE'}:
  bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
  bpy.ops.object.convert(target='MESH');world=o.matrix_world.copy();o.parent=None;o.matrix_world=world
  bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
for o in list(col.objects):
 if o.name.startswith(('Arm and hand','Leg and foot')):bpy.data.objects.remove(o,do_unlink=True)
source=P+'/assets/third-party/chibi-models/polyone-base/editable.blend'
with bpy.data.libraries.load(source,link=False) as (a,b):b.objects=['SM_Chibi_Body','BaseMesh_Chibi']
body,rig=b.objects
for o in [body,rig]:col.objects.link(o)
bpy.context.view_layer.update()
source_heads={b.name:rig.matrix_world@b.head_local for b in rig.data.bones}
source_parents={b.name:b.parent.name if b.parent else None for b in rig.data.bones}
# Target landmarks match the retained clothing and the slim owner proportions.
T={
'Hips':((0,.01,1.02),(0,.01,1.17)),
'Spine':((0,.01,1.17),(0,.01,1.36)),
'Spine1':((0,.01,1.36),(0,.01,1.55)),
'Spine2':((0,.01,1.55),(0,.015,1.78)),
'Neck':((0,.015,1.78),(0,.015,1.91)),
'Head':((0,.015,1.91),(0,.015,2.72)),
'HeadTop_End':((0,.015,2.72),(0,.015,2.86))}
for prefix,s in [('Right',-1),('Left_',1)]:
 T[prefix+'Shoulder']=((s*.08,0,1.72),(s*.31,0,1.68))
 T[prefix+'Arm']=((s*.31,0,1.68),(s*.437,-.005,1.37))
 T[prefix+'ForeArm']=((s*.437,-.005,1.37),(s*.477,-.035,1.095))
 T[prefix+'Hand']=((s*.477,-.035,1.095),(s*.48,-.045,1.015))
 T[prefix+'HandIndex1']=((s*.48,-.045,1.015),(s*.482,-.055,.969))
 T[prefix+'HandIndex2']=((s*.482,-.055,.969),(s*.483,-.06,.938))
 T[prefix+'HandIndex3']=((s*.437,-.04,1.045),(s*.416,-.06,1.008))
 T[prefix+'HandIndex2.001']=((s*.416,-.06,1.008),(s*.416,-.074,.982))
 T[prefix+'UpLeg']=((s*.18,.015,1.015),(s*.20,.008,.57))
 T[prefix+'Leg']=((s*.20,.008,.57),(s*.195,.027,.155))
 T[prefix+'Foot']=((s*.195,.027,.155),(s*.195,-.15,.116))
 T[prefix+'ToeBase']=((s*.195,-.15,.116),(s*.195,-.23,.112))
# Correct FBX display axes using successive joint heads as anatomical segments.
child={}
for key in T:
 if key in ['Hips','Spine','Spine1','Spine2','Neck','Head']:
  child[key]={'Hips':'Spine','Spine':'Spine1','Spine1':'Spine2','Spine2':'Neck','Neck':'Head','Head':'HeadTop_End'}[key]
for p in ['Right','Left_']:
 for a,b in [('Shoulder','Arm'),('Arm','ForeArm'),('ForeArm','Hand'),('Hand','HandIndex1'),('HandIndex1','HandIndex2'),('HandIndex3','HandIndex2.001'),('UpLeg','Leg'),('Leg','Foot'),('Foot','ToeBase')]:child[p+a]=p+b
maps={}
for name,(ah,bh) in T.items():
 a=source_heads[name]
 if name in child:b=source_heads[child[name]]
 elif 'Index2.001' in name:b=a+(a-source_heads[name.replace('HandIndex2.001','HandIndex3')])*.7
 elif 'Index2' in name:b=a+(a-source_heads[name.replace('Index2','Index1')])*.7
 elif 'ToeBase' in name:b=a+Vector((0,-.02,0))
 else:b=a+Vector((0,0,.03))
 d=b-a;target=Vector(bh)-Vector(ah);unit=d.normalized()
 transverse=4.8
 if 'Hand' in name:transverse=2.3
 if 'Leg' in name or 'Foot' in name or 'Toe' in name:transverse=2.5
 if name in ['Hips','Spine','Spine1','Spine2','Neck']:transverse=4.5
 R=unit.rotation_difference(target.normalized()).to_matrix()
 stretch=Matrix.Identity(3)*transverse
 outer=Matrix([[unit[i]*unit[j] for j in range(3)] for i in range(3)])
 stretch+=outer*(target.length/max(d.length,1e-6)-transverse)
 maps[name]=(a,Vector(ah),R@stretch)
# Remap actual downloaded body vertices using its authored skin weights.
old_world=body.matrix_world.copy();names={g.index:g.name for g in body.vertex_groups}
oldz=[]
for v in body.data.vertices:
 q=old_world@v.co;oldz.append(q.z);co=Vector();total=0
 for g in v.groups:
  name=names[g.group]
  if name in maps:
   a,b,M=maps[name];co+=(b+M@(q-a))*g.weight;total+=g.weight
 # Reshape proportion through anatomical landmarks, not weighted stretch matrices.
 ax=abs(q.x);side=1 if q.x>=0 else -1
 if ax>.062 and q.z>.125:
  if ax<.1054:
   t=max(0,min(1,(ax-.0616)/(.1054-.0616)));start=Vector((side*.31,0,1.68));end=Vector((side*.437,-.005,1.37));width=3.6
  elif ax<.13525:
   t=(ax-.1054)/(.13525-.1054);start=Vector((side*.437,-.005,1.37));end=Vector((side*.477,-.035,1.095));width=3.3
  else:
   t=min(1.1,(ax-.13525)/(.211-.13525));start=Vector((side*.477,-.035,1.095));end=Vector((side*.48,-.055,.94));width=2.15
  tangent=(end-start).normalized();normal=Vector((-side*tangent.z,0,side*tangent.x))
  v.co=start.lerp(end,t)+normal*((q.z-.1758)*width)+Vector((0,(q.y-.002)*width,0))
 elif q.z<.067:
  if q.z>.0396:z=.57+(q.z-.0396)/(.0607-.0396)*.445
  elif q.z>.0196:z=.155+(q.z-.0196)/(.0396-.0196)*.415
  else:z=.095+(q.z-.006)*4.0
  v.co=(side*.195+(q.x-side*.0451)*2.6,q.y*3.7,z)
 else:
  z=1.06+(q.z-.0774)/(.19-.0774)*.70
  v.co=(max(-.275,min(.275,q.x*3.6)),max(-.135,min(.135,q.y*2.3)),max(.96,min(1.80,z)))
# Remove original head and neck; keep the selected girl's head and existing clean neckline.
import bmesh
bm=bmesh.new();bm.from_mesh(body.data);bm.verts.ensure_lookup_table()
bmesh.ops.delete(bm,geom=[v for v in bm.verts if oldz[v.index]>.19],context='VERTS');bm.to_mesh(body.data);bm.free()
body.parent=None;body.matrix_world=Matrix.Identity(4);body.name='Body • adapted PolyOne weighted mesh'
body.data.materials.clear();body.data.materials.append(bpy.data.materials['Skin • warm peach'])
for f in body.data.polygons:f.material_index=0;f.use_smooth=True
body.modifiers.clear()
q=body.modifiers.new('Smooth body surface','SUBSURF');q.levels=1;q.render_levels=2
visible=body.vertex_groups.new(name='Clothing visibility')
for v in body.data.vertices:
 if (abs(v.co.x)>.305 and v.co.z>1.00) or v.co.z<.23 or (abs(v.co.x)>.38 and v.co.z>.90):visible.add([v.index],1,'REPLACE')
mask=body.modifiers.new('Hide skin beneath clothing (disable to edit full body)','MASK');mask.vertex_group=visible.name
# Refit the downloaded armature, retaining its names and parent hierarchy.
rig.parent=None;rig.matrix_world=Matrix.Identity(4);rig.name='Owner_V13_RIG'
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT')
for b in rig.data.edit_bones:
 b.use_connect=False;b.head,b.tail=T[b.name];b.roll=0
bpy.ops.object.mode_set(mode='OBJECT');rig.show_in_front=True;rig.data.display_type='OCTAHEDRAL'
for b in rig.data.bones:b.use_deform=b.name!='HeadTop_End'
def bind(o):
 m=o.modifiers.new('Owner skeleton deformation','ARMATURE');m.object=rig;m.use_deform_preserve_volume=True
 o.parent=rig
bind(body)
# Smooth garment weights sampled along the appropriate limb or torso chain.
def smoothweights(z,items):
 items=sorted(items)
 if z<=items[0][0]:return {items[0][1]:1}
 if z>=items[-1][0]:return {items[-1][1]:1}
 for (a,n),(b,m) in zip(items,items[1:]):
  if a<=z<=b:
   t=(z-a)/(b-a);t=t*t*(3-2*t);return {n:1-t,m:t}
def weights(o,v):
 x,y,z=v.co;name=o.name;p='Left_' if x>=0 else 'Right'
 if name.startswith(('Face','Hair','Adapted','Round eyeglass','Glasses')):return {'Head':1}
 if name.startswith('Neck'):return smoothweights(z,[(1.73,'Spine2'),(1.87,'Neck'),(1.95,'Head')])
 if name.startswith(('Slide',)):return {p+'Foot':1}
 if name.startswith(('Jeans','Denim','Back pocket')):
  if z>1.02:return {'Hips':1}
  return smoothweights(z,[(.35,p+'Leg'),(.78,p+'UpLeg'),(1.04,'Hips')])
 if name.startswith('Short sleeve'):
  t=min(1,max(0,(abs(x)-.16)/.16));return {'Spine2':1-t,p+'Arm':t}
 return smoothweights(z,[(1.12,'Hips'),(1.28,'Spine'),(1.46,'Spine1'),(1.68,'Spine2')])
for o in list(col.objects):
 if o.type!='MESH' or o==body:continue
 o.vertex_groups.clear()
 groups={n:o.vertex_groups.new(name=n) for n in T if n!='HeadTop_End'}
 for v in o.data.vertices:
  for n,w in weights(o,v).items():
   if w>0:groups[n].add([v.index],w,'REPLACE')
 bind(o)
rig['source']='Adapted from PolyOne Studio Free Pack Chibi Base Mesh (Rigged), CC BY 4.0'
rig['status']='Refitted FK skeleton; body, garments, head and accessories weighted; no IK controls or production animation'
root['status']='Rigged hybrid adaptation; 31-bone FK rig; see source/license notes'
sc=bpy.context.scene;sc.cycles.samples=24
sc.camera=bpy.data.objects['Camera three-quarter'];bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=P+'/assets/blender/characters/owner-character-v13.blend')
for view in ['three-quarter','front','side','back']:
 sc.camera=bpy.data.objects['Camera '+view];sc.render.filepath=OUT+'/'+view+'.png';bpy.ops.render.render(write_still=True)
# A temporary pose verifies actual skin deformation; delivered file stays neutral.
sc.camera=bpy.data.objects['Camera three-quarter']
for name,axis,angle in [('Left_Arm',2,-22),('Left_ForeArm',0,-55),('RightForeArm',0,-25),('Left_UpLeg',0,-22),('Left_Leg',0,35),('Head',2,8)]:
 b=rig.pose.bones[name];b.rotation_mode='XYZ';b.rotation_euler[axis]=math.radians(angle)
sc.render.filepath=OUT+'/pose-check.png';bpy.ops.render.render(write_still=True)
for b in rig.pose.bones:b.rotation_euler=(0,0,0)
bpy.context.view_layer.update()
report={'rig_bones':len(rig.data.bones),'source_body_vertices':len(body.data.vertices),'bound_meshes':sum(o.type=='MESH' for o in col.objects),'unweighted_vertices':{}}
for o in col.objects:
 if o.type=='MESH':
  count=sum(sum(g.weight for g in v.groups if o.vertex_groups[g.group].name in T)<.99 for v in o.data.vertices)
  if count:report['unweighted_vertices'][o.name]=count
open(OUT+'/validation.json','w').write(json.dumps(report,indent=2))
# Export rigged model without destructive conversion of the armature.
bpy.ops.object.select_all(action='DESELECT')
for o in col.objects:
 if o.type in {'MESH','ARMATURE'}:o.select_set(True)
bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=P+'/assets/blender/characters/owner-character-v13.glb',export_format='GLB',use_selection=True,export_apply=True,export_animations=False)
print('OWNER_V13_COMPLETE',report,flush=True)
