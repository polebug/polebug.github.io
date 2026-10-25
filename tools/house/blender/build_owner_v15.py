import bpy,bmesh,math,os,json,sys
from mathutils import Vector,Matrix
P='/Users/bugpole/AI/博客陪伴小屋';OUT=P+'/assets/renders/character-v15';os.makedirs(OUT,exist_ok=True)
sys.path.insert(0,P+'/assets/blender/scripts');from meshkit import Mesh
bpy.ops.wm.open_mainfile(filepath=P+'/assets/blender/characters/owner-character-v14.blend')
col=bpy.data.collections['Owner_V14'];col.name='Owner_V15';rig=bpy.data.objects['Owner_V14_RIG'];rig.name='Owner_V15_RIG'
# Keep only glasses and the already-designed trousers; replace all anatomy with original girl.
kept=[]
for ob in list(col.objects):
 if ob.type=='MESH':
  if ob.name.startswith(('Round eyeglass','Glasses','Adapted','Jeans','Back pocket')):
   world=ob.matrix_world.copy();ob.parent=None;ob.matrix_world=world
   for m in list(ob.modifiers):
    if m.type=='ARMATURE':ob.modifiers.remove(m)
   ob.vertex_groups.clear();kept.append(ob)
   for v in ob.data.vertices:
    if ob.name.startswith(('Round eyeglass','Glasses','Adapted')):
     v.co.x*=.7/(.94*.85);v.co.y=v.co.y*.7/(.95*.85)+.028;v.co.z=(v.co.z+.5470316624)*.7/(.96*.85)
    else:v.co.x*=.68
  else:bpy.data.objects.remove(ob,do_unlink=True)
with bpy.data.libraries.load(P+'/assets/third-party/chibi-models/cute-chibi-girl/editable.blend',link=False) as (a,b):b.objects=['character']
original=b.objects[0];col.objects.link(original);bpy.context.view_layer.update();world=original.matrix_world.copy()
bm=bmesh.new();bm.from_mesh(original.data)
bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.material_index==3],context='FACES')
bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
for v in bm.verts:
 q=world@v.co;v.co=(q.y*.7,-q.x*.7,q.z*.7)
# Capture the actual open wrist rings to bridge missing forearms without touching hands.
loops=[];remaining={e for e in bm.edges if e.is_boundary}
while remaining:
 seed=remaining.pop();vs=set(seed.verts);todo=list(seed.verts)
 while todo:
  v=todo.pop()
  for e in v.link_edges:
   if e in remaining:remaining.remove(e);w=e.other_vert(v);vs.add(w);todo.append(w)
 center=sum((v.co for v in vs),Vector())/len(vs)
 if abs(center.x)>.5 and 1.25<center.z<1.5:
  loops.append((center,[v.co.copy() for v in vs]))
me=bpy.data.meshes.new('Original girl anatomy and hairstyle');bm.to_mesh(me);bm.free()
body=bpy.data.objects.new('Original girl • head hands legs shoes hair',me);col.objects.link(body)
for m in original.data.materials:me.materials.append(m)
for f in me.polygons:f.use_smooth=True
bpy.data.objects.remove(original,do_unlink=True)
body['source']='Cute Chibi Girl, Syed’s Creation / Dawood3D, CC BY 4.0'
body['geometry_preservation']='All source non-clothing vertices retained without anatomical deformation; only rigid rotation and uniform scale 0.7'
# Supplement only missing under-sleeve anatomy; original hands are unchanged.
skin=me.materials[1];cloth=bpy.data.materials['T-shirt • soft gray cotton'];seam=bpy.data.materials['Gray cotton seams']
def mesh(name,m,mat,sub=1,solid=0):
 o=m.build(name,col,tuple(mat.diffuse_color[:3]),smooth=True);o.data.materials.append(mat)
 if solid:q=o.modifiers.new('Fabric thickness','SOLIDIFY');q.thickness=solid
 if sub:q=o.modifiers.new('Soft surface','SUBSURF');q.levels=sub;q.render_levels=sub
 return o
for center,pts in loops:
 s=1 if center.x>0 else -1;shoulder=Vector((s*.24,.025,1.87));axis=(shoulder-center).normalized();u=Vector((0,1,0));v=axis.cross(u).normalized()
 pts.sort(key=lambda p:math.atan2((p-center).dot(v),(p-center).dot(u)))
 m=Mesh();n=len(pts)
 for t,w in [(0,1),(.04,1.03),(.22,1.16),(.5,1.35),(.75,1.52),(1,1.62)]:
  c=center.lerp(shoulder,t)
  for p in pts:m.v.append(tuple(c+(p-center)*w))
 for k in range(5):
  for j in range(n):a=k*n+j;b=k*n+(j+1)%n;m.f.append([a,b,b+n,a+n])
 m.f.append([5*n+j for j in range(n)])
 mesh('Supplemental arm '+str(s),m,skin,2)
# Plain round-neck short-sleeved T-shirt fitted to original shoulder/hand pose.
m=Mesh();N=64
prof=[(1.08,.251,.16),(1.10,.255,.164),(1.30,.245,.155),(1.60,.255,.20),(1.80,.28,.20),(1.88,.24,.18),(1.95,.11,.11),(1.96,.105,.10)]
for z,rx,ry in prof:
 for j in range(N):
  a=2*math.pi*j/N;dip=.045*max(0,math.cos(a))**2*max(0,(z-1.83)/.13)
  m.v.append((rx*math.sin(a),.02-ry*math.cos(a),z-dip))
for k in range(len(prof)-1):
 for j in range(N):a=k*N+j;b=k*N+(j+1)%N;m.f.append([a,b,b+N,a+N])
mesh('Gray short sleeve tee • original proportions',m,cloth,2,.012)
for s in [-1,1]:
 a=Vector((s*.14,.02,1.86));b=Vector((s*.43,.016,1.69));axis=(b-a).normalized();u=Vector((0,1,0));v=axis.cross(u).normalized();m=Mesh();n=48
 for t,r in [(0,.14),(.25,.135),(.9,.102),(1,.102)]:
  c=a.lerp(b,t)
  for j in range(n):m.v.append(tuple(c+r*(u*math.cos(2*math.pi*j/n)+v*math.sin(2*math.pi*j/n))))
 for k in range(3):
  for j in range(n):a1=k*n+j;b1=k*n+(j+1)%n;m.f.append([a1,b1,b1+n,a1+n])
 mesh('Gray short sleeve '+str(s),m,cloth,2,.012)
# Refit FK rig to the original anatomy; no mesh pose is baked into hands or legs.
T={'Hips':((0,.02,1.04),(0,.02,1.2)),'Spine':((0,.02,1.2),(0,.02,1.44)),'Spine1':((0,.02,1.44),(0,.02,1.68)),'Spine2':((0,.02,1.68),(0,.02,1.94)),'Neck':((0,.02,1.94),(0,.02,2.07)),'Head':((0,.02,2.07),(0,.02,2.82)),'HeadTop_End':((0,.02,2.82),(0,.02,3.14))}
for p,s in [('Right',-1),('Left_',1)]:
 wrist=next((c for c,ps in loops if c.x*s>0),Vector((s*.67,.02,1.37)))
 T[p+'Shoulder']=((s*.07,.02,1.88),(s*.24,.02,1.87));T[p+'Arm']=((s*.24,.02,1.87),(s*.46,.02,1.63));T[p+'ForeArm']=((s*.46,.02,1.63),tuple(wrist));T[p+'Hand']=(tuple(wrist),(s*.82,.02,1.19))
 for k,offset in [('HandIndex1',0),('HandIndex2',.035),('HandIndex3',-.02),('HandIndex2.001',.015)]:T[p+k]=((s*(.80+offset),.02,1.22-offset),(s*(.83+offset),.02,1.18-offset))
 T[p+'UpLeg']=((s*.135,.04,1.04),(s*.135,.015,.59));T[p+'Leg']=((s*.135,.015,.59),(s*.135,.02,.16));T[p+'Foot']=((s*.135,.02,.16),(s*.135,-.10,.075));T[p+'ToeBase']=((s*.135,-.10,.075),(s*.135,-.19,.06))
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT')
for b in rig.data.edit_bones:b.use_connect=False;b.head,b.tail=T[b.name];b.roll=0
bpy.ops.object.mode_set(mode='OBJECT')
def blends(z,lo,hi,a,b):
 t=max(0,min(1,(z-lo)/(hi-lo)));t=t*t*(3-2*t);return {a:1-t,b:t}
def weights(o,v):
 x,y,z=v.co;p='Left_' if x>=0 else 'Right'
 if o.name.startswith(('Round eyeglass','Glasses','Adapted')):return {'Head':1}
 if o==body:
  if z>2.05:return {'Head':1}
  if abs(x)>.55:return {p+'Hand':1}
  if z>1.70:return blends(z,1.86,2.05,'Spine2','Head')
  if z<.19:return {p+'Foot':1}
 if o.name.startswith('Gray short sleeve ') and not o.name.startswith('Gray short sleeve tee'):return {p+'Arm':1}
 if o.name.startswith('Supplemental arm'):return blends(z,1.49,1.74,p+'ForeArm',p+'Arm')
 if z<1.05:return blends(z,.40,.79,p+'Leg',p+'UpLeg') if z<.95 else blends(z,.95,1.05,p+'UpLeg','Hips')
 return blends(z,1.14,1.85,'Hips','Spine2')
for o in col.objects:
 if o.type!='MESH':continue
 o.vertex_groups.clear();groups={n:o.vertex_groups.new(name=n) for n in T}
 for v in o.data.vertices:
  for n,w in weights(o,v).items():
   if w>0:groups[n].add([v.index],w,'REPLACE')
 mod=o.modifiers.new('Original anatomy skeleton','ARMATURE');mod.object=rig;mod.use_deform_preserve_volume=True;o.parent=rig
# Keep original covered skin in the file; hide it reversibly under the outfit.
visible=body.vertex_groups.new(name='Visible original skin and accessories')
keep=set()
for f in body.data.polygons:
 if f.material_index!=1:keep.update(f.vertices)
for v in body.data.vertices:
 if abs(v.co.x)>.5 or v.co.z>1.94 or v.co.z<.17:keep.add(v.index)
visible.add(list(keep),1,'REPLACE')
mask=body.modifiers.new('Covered source skin (disable to inspect original)','MASK');mask.vertex_group=visible.name
sc=bpy.context.scene;sc.cycles.samples=32;sc.camera=bpy.data.objects['Camera three-quarter'];sc.camera.data.ortho_scale=3.8
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=P+'/assets/blender/characters/owner-character-v15.blend')
for view in ['three-quarter','front','side','back']:
 sc.camera=bpy.data.objects['Camera '+view];sc.camera.data.ortho_scale=3.8;sc.render.filepath=OUT+'/'+view+'.png';bpy.ops.render.render(write_still=True)
bpy.ops.object.select_all(action='DESELECT')
for o in col.objects:
 if o.type in {'MESH','ARMATURE'}:o.select_set(True)
bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=P+'/assets/blender/characters/owner-character-v15.glb',export_format='GLB',use_selection=True,export_apply=True,export_animations=False)
open(OUT+'/validation.json','w').write(json.dumps({'original_nonclothing_vertices':len(me.vertices),'wrist_loops':[(list(c),len(ps)) for c,ps in loops],'source_hand_deformation':'none; rigid rotation + uniform scale only','bones':len(rig.data.bones)},indent=2))
print('V15_COMPLETE')
