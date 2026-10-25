"""Standalone owner rebuild. Never opens or overwrites the house file.
Run in factory-startup Blender. Coordinates: Z up, character front -Y.
"""
import bpy, math, os, sys, json
from mathutils import Vector
sys.path.insert(0, os.path.dirname(__file__))
from meshkit import Mesh
P='/Users/bugpole/AI/博客陪伴小屋'
OUT=P+'/assets/renders/character-v02'
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
sc=bpy.context.scene
col=bpy.data.collections.new('Owner_V02'); sc.collection.children.link(col)
root=bpy.data.objects.new('Owner_V02_ROOT',None); col.objects.link(root)

def material(name,color,rough=.5,sss=0,coat=0):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
 p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough
 p.inputs['Subsurface Weight'].default_value=sss;p.inputs['Subsurface Radius'].default_value=(.10,.045,.025);p.inputs['Coat Weight'].default_value=coat
 return m
skin=material('Skin • warm peach',(.73,.405,.255),.48,.12)
hairmat=material('Hair • soft black',(.009,.0065,.005),.52,coat=.02)
hairmat.node_tree.nodes.get('Principled BSDF').inputs['Specular IOR Level'].default_value=.23
hairline=material('Hair • subtle strand relief',(.017,.012,.009),.4)
cloth=material('Hoodie • charcoal cotton',(.014,.014,.017),.86)
seammat=material('Cotton seams',(.023,.022,.025),.85)
cream=material('Slides • warm ivory',(.81,.74,.60),.64)
white=material('Eye whites',(.92,.89,.83),.28)
iris=material('Iris • dark brown',(.065,.024,.009),.24,coat=.25)
black=material('Pupil and lashes',(.003,.002,.002),.25)
frame=material('Glasses • chestnut',(.20,.075,.025),.27,coat=.25)
lip=material('Gentle smile',(.23,.065,.038),.55)
inner=material('Ear inner',(.63,.27,.17),.58,.1)
# Low-amplitude cotton surface; no geometry noise on the face.
n=cloth.node_tree.nodes;l=cloth.node_tree.links;p=n.get('Principled BSDF')
tex=n.new('ShaderNodeTexNoise');tex.inputs['Scale'].default_value=220
b=n.new('ShaderNodeBump');b.inputs['Strength'].default_value=.12;b.inputs['Distance'].default_value=.001
l.new(tex.outputs['Fac'],b.inputs['Height']);l.new(b.outputs['Normal'],p.inputs['Normal'])

def mesh(name,m,mat,sub=0,solid=0):
 o=m.build(name,col,tuple(mat.diffuse_color[:3]),smooth=True,parent=root)
 o.data.materials.append(mat)
 if solid:
  q=o.modifiers.new('Tailored thickness','SOLIDIFY');q.thickness=solid
 if sub:
  q=o.modifiers.new('Surface refinement','SUBSURF');q.levels=sub;q.render_levels=sub
 return o

def ell(name,c,r,mat,seg=48,rings=32):
 m=Mesh();m.ellipsoid(c,r,seg=seg,rings=rings);return mesh(name,m,mat)
def curve(name,pts,r,mat,cyclic=False):
 cu=bpy.data.curves.new(name,'CURVE');cu.dimensions='3D';cu.resolution_u=16;cu.bevel_depth=r;cu.bevel_resolution=3
 s=cu.splines.new('BEZIER');s.bezier_points.add(len(pts)-1)
 for b,p in zip(s.bezier_points,pts):b.co=p;b.handle_left_type='AUTO';b.handle_right_type='AUTO'
 s.use_cyclic_u=cyclic;o=bpy.data.objects.new(name,cu);col.objects.link(o);o.parent=root;cu.materials.append(mat);return o

def interp(knots,t):
 for i in range(len(knots)-1):
  a,v=knots[i];b,w=knots[i+1]
  if t<=b:
   f=max(0,(t-a)/(b-a));f=f*f*(3-2*f);return v*(1-f)+w*f
 return knots[-1][1]

def fuse(o,size=.012):
 bpy.context.view_layer.objects.active=o;o.select_set(True)
 q=o.modifiers.new('Continuous organic surface','REMESH');q.mode='VOXEL';q.voxel_size=size;q.use_smooth_shade=True
 bpy.ops.object.modifier_apply(modifier=q.name)
 q=o.modifiers.new('Gentle surface relaxation','SMOOTH');q.factor=.65;q.iterations=4
 bpy.ops.object.modifier_apply(modifier=q.name)
 q=o.modifiers.new('Final smoothness','SUBSURF');q.levels=1
 o.select_set(False)

def tube_mesh(m,pts,rs,seg=24):
 pts=[Vector(p) for p in pts];start=len(m.v)
 for i,p in enumerate(pts):
  t=(pts[min(i+1,len(pts)-1)]-pts[max(0,i-1)]).normalized();a=t.cross(Vector((0,1,0))).normalized();b=t.cross(a)
  for j in range(seg):m.v.append(tuple(p+rs[i]*(a*math.cos(j*2*math.pi/seg)+b*math.sin(j*2*math.pi/seg))))
 for i in range(len(pts)-1):
  for j in range(seg):
   a=start+i*seg+j;b=start+i*seg+(j+1)%seg;m.f.append([a,b,b+seg,a+seg])
 m.f.append([start+j for j in range(seg)][::-1]);m.f.append([start+(len(pts)-1)*seg+j for j in range(seg)])

# Head: one continuous rounded face, wide cheeks and a soft small chin.
m=Mesh()
def headpoint(u,v):
 ph=-math.pi/2+math.pi*v;z=math.sin(ph);r=math.cos(ph);th=2*math.pi*u
 cheek=1+.08*math.exp(-((z+.35)/.3)**2)
 x=.535*r*math.sin(th)*cheek
 # Broad flattened facial arc rather than a sphere with appliqued features.
 y=-.435*r*math.copysign(abs(math.cos(th))**.63,math.cos(th))
 if y>0:y*=1.03
 return (x,y,2.39+.55*z)
m.surface(headpoint,97,65)
head=mesh('Face • continuous cheeks and chin',m,skin,1)
ell('Neck',(0,.035,1.87),(.095,.10,.19),skin)
for s in [-1,1]:
 ell('Ear '+str(s),(s*.53,-.225,2.23),(.105,.075,.14),skin)
 ell('Ear concha '+str(s),(s*.575,-.282,2.24),(.044,.018,.078),inner)
# Eyes follow the facial surface; shallow domes rather than projecting eyeballs.
def face_y(x,z):
 rz=(z-2.39)/.55;r=math.sqrt(max(.001,1-rz*rz));cheek=1+.08*math.exp(-((rz+.35)/.3)**2)
 xn=max(-.999,min(.999,x/(.535*r*cheek)))
 return -.435*r*(1-xn*xn)**.315

def eye_patch(name,cx,cz,rx,rz,mat,lift):
 m=Mesh();N=64;R=16
 m.v.append((cx,face_y(cx,cz)-lift,cz))
 for i in range(1,R+1):
  r=i/R
  for j in range(N):
   t=2*math.pi*j/N;x=cx+rx*r*math.cos(t);z=cz+rz*r*math.sin(t)
   m.v.append((x,face_y(x,z)-lift-.012*(1-r*r),z))
 for j in range(N):m.f.append([0,1+j,1+(j+1)%N])
 for i in range(R-1):
  for j in range(N):
   a=1+i*N+j;b=1+i*N+(j+1)%N;m.f.append([a,b,b+N,a+N])
 return mesh(name,m,mat)
for s in [-1,1]:
 x=s*.245;z=2.36
 eye_patch('Eye white '+str(s),x,z,.154,.178,white,.010)
 eye_patch('Iris '+str(s),x,z-.005,.112,.142,iris,.025)
 eye_patch('Pupil '+str(s),x,z-.005,.081,.115,black,.031)
 ell('Eye glint '+str(s),(x-.034,face_y(x-.034,z+.06)-.047,z+.06),(.022,.004,.025),white,24,16)
 ell('Eye small glint '+str(s),(x+.03,face_y(x+.03,z-.06)-.046,z-.06),(.007,.003,.008),white,16,12)
 pts=[]
 for k in range(21):
  t=math.pi*k/20;xx=x+.155*math.cos(t);zz=z+.178*math.sin(t);pts.append((xx,face_y(xx,zz)-.015,zz))
 curve('Upper eyelid '+str(s),pts,.008,black)
 for j in range(2):
  xx=s*(.245+.142);zz=z+.065+j*.027;yy=face_y(xx,zz)-.012
  curve('Outer eyelash '+str(s),[(xx,yy,zz),(xx+s*.024,yy+.008,zz+.025)],.005,black)
 curve('Eyebrow '+str(s),[(s*.13,face_y(s*.13,2.62)-.007,2.62),(s*.22,face_y(s*.22,2.648)-.007,2.648),(s*.32,face_y(s*.32,2.625)-.007,2.625)],.010,hairmat)
 pts=[(x+.204*math.cos(t),-.480+.052*abs(math.cos(t)),z+.214*math.sin(t)) for t in [2*math.pi*k/64 for k in range(64)]]
 curve('Round eyeglass rim '+str(s),pts,.013,frame,True)
 curve('Glasses temple '+str(s),[(s*.449,-.428,2.39),(s*.505,-.35,2.40),(s*.535,-.06,2.36),(s*.53,.00,2.31)],.009,frame)
curve('Glasses bridge',[(-.041,-.444,2.39),(0,-.472,2.414),(.041,-.444,2.39)],.012,frame)
ell('Small nose',(0,-.442,2.245),(.037,.037,.028),skin)
curve('Closed smile',[(x,face_y(x,z)-.004,z) for x,z in [(-.066,2.135),(-.034,2.12),(0,2.117),(.034,2.12),(.066,2.135)]],.005,lip)

# Bob foundation: continuously rounded silhouette, inward-turning hem.
def bobrad(z):
 return .765*math.sqrt(max(.00005,1-((z-2.47)/.55)**2)) if z>=2.47 else .765-.14*((2.47-z)/.53)**2
def edge(th):
 a=abs((th+math.pi)%(2*math.pi)-math.pi)
 return interp([(0,2.96),(.25,2.88),(.55,2.65),(.86,2.28),(1.12,2.00),(1.4,1.96),(math.pi,1.97)],a)
def hairpos(th,z,lift=0):
 r=bobrad(z)+lift
 return Vector((r*math.sin(th),.065-r*(.77 if math.cos(th)<0 else .74)*math.cos(th),z))
m=Mesh()
m.surface(lambda u,v:hairpos(2*math.pi*u,3.015+(edge(2*math.pi*u)-3.015)*v),129,65)
mesh('Hair • continuous rounded bob foundation',m,hairmat,1,.025)
# Low-profile swept panels lying against the foundation. No cylindrical strands.
for s in [-1,1]:
 for k in range(10):
  target=1.10+(math.pi-1.10)*(k/9)
  start=.16+(math.pi-.32)*(k/9)
  ztop=2.97-.05*math.sin(k*.8);zend=1.95+.035*math.sin(k*1.7)
  def panel(u,v,s=s,target=target,start=start,ztop=ztop,zend=zend,k=k):
   z=ztop+(zend-ztop)*v
   t=start+(target-start)*math.sin(v*math.pi/2)
   width=.12*math.sin(math.pi*v)**.45+.002
   t+= (u-.5)*2*width
   # Lift only a few millimeters with a tapered sculpted ridge.
   p=hairpos(s*t,z,.003+.007*math.sin(math.pi*u)*math.sin(math.pi*v))
   p.z+=.018*(abs(u-.5)*2)**2*v**6
   return p
  m=Mesh();m.surface(panel,11,38);mesh('Hair swept panel %s %02d'%(s,k),m,hairmat,1,.004)
  for j in []:
   pts=[panel(.5+j,v) for v in [.08+i*.85/22 for i in range(23)]]
   curve('Fine hair flow %s %s %s'%(s,k,j),pts,.0013,hairline)
# Broad curtain bangs: shaped as curved leaf-like surfaces, generous continuous flow.
def bez(pts,t):
 a,b,c,d=map(Vector,pts);return a*(1-t)**3+b*3*t*(1-t)**2+c*3*t*t*(1-t)+d*t**3
for s in [-1,1]:
 for k in range(3):
  controls=[(s*(.015+.035*k),-.12,2.965-.012*k),(s*(.30+.025*k),-.48,2.94),(s*(.43+.04*k),-.47,2.48),(s*(.57+.025*k),-.25,2.20-.065*k)]
  def bang(u,v,controls=controls,s=s,k=k):
   p=bez(controls,v);t=(bez(controls,min(1,v+.001))-bez(controls,max(0,v-.001))).normalized()
   across=Vector((-t.z,0,t.x)).normalized()
   w=(.025+.11*math.sin(math.pi*v)**.65)*(1-.35*k)
   p+=across*((u-.5)*2*w)
   p.y-=.022*math.sin(math.pi*u)*math.sin(math.pi*v)
   return p
  m=Mesh();m.surface(bang,13,40);mesh('Curtain fringe %s %s'%(s,k),m,hairmat,1,.018)
  for u in []:curve('Fringe flow %s %s %.2f'%(s,k,u),[bang(u,.07+i*.86/25)+Vector((0,-.002,0)) for i in range(26)],.0012,hairline)
# One curved cowlick, with a tapered end.
pts=[(0,.015,2.94),(0,.015,2.99),(.035,.01,3.10),(.13,.015,3.16),(.22,.015,3.12),(.26,.012,3.07)]
m=Mesh();tube_mesh(m,pts,[.025,.025,.023,.018,.009,.001],12);mesh('Single curved cowlick',m,hairmat,2)

# Dress: hollow tailored shell with clear hem, no cone apex.
prof=[(.79,.385,.245),(.81,.392,.25),(.91,.38,.245),(1.15,.347,.235),(1.43,.315,.215),(1.68,.305,.195),(1.79,.265,.165),(1.87,.135,.105)]
m=Mesh();N=64
for z,rx,ry in prof:
 for j in range(N):
  t=2*math.pi*j/N
  fold=.006*math.sin(t*7+.4)*math.sin(math.pi*(z-.79)/1.08)
  m.v.append(((rx+fold)*math.sin(t),-(ry+fold)*math.cos(t),z))
for k in range(len(prof)-1):
 for j in range(N):a=k*N+j;b=k*N+(j+1)%N;m.f.append([a,b,b+N,a+N])
mesh('Hoodie dress • shaped shell',m,cloth,2,.018)
for s in [-1,1]:
 m=Mesh();N=48
 centers=[(s*.155,0,1.755),(s*.265,0,1.73),(s*.405,0,1.52),(s*.41,0,1.515)]
 direction=Vector((s*.15,0,-.245)).normalized();a=Vector((0,1,0));b=direction.cross(a)
 for ci,c in enumerate(centers):
  rad=[.106,.146,.149,.148][ci]
  for j in range(N):m.v.append(tuple(Vector(c)+rad*(a*math.cos(2*math.pi*j/N)+b*math.sin(2*math.pi*j/N))))
 for k in range(3):
  for j in range(N):q=k*N+j;r=k*N+(j+1)%N;m.f.append([q,r,r+N,q+N])
 mesh('Short sleeve '+str(s),m,cloth,2,.014)
# Closed, softly compressed hood resting against the upper back.
m=Mesh()
for j in range(33):
 v=j/32;z=1.86-.40*v
 width=.225*math.sin(math.pi*(.12+.88*v))**.7+.008
 depth=.062*math.sin(math.pi*v)**.7+.015
 for k in range(48):
  t=2*math.pi*k/48;m.v.append((width*math.cos(t),.20+depth*math.sin(t),z))
for j in range(32):
 for k in range(48):a=j*48+k;b=j*48+(k+1)%48;m.f.append([a,b,b+48,a+48])
m.f.extend([list(range(48))[::-1],[32*48+k for k in range(48)]])
mesh('Hood • soft closed drape',m,cloth,2)
curve('Hood central seam',[(0,.22,1.85),(0,.277,1.68),(0,.224,1.48)],.003,seammat)
curve('Soft V neckline',[(-.20,.04,1.86),(-.17,-.11,1.86),(-.10,-.17,1.80),(0,-.175,1.745),(.10,-.17,1.80),(.17,-.11,1.86),(.20,.04,1.86)],.030,cloth)
for s in [-1,1]:
 curve('Drawstring '+str(s),[(s*.085,-.20,1.78),(s*.085,-.24,1.62),(s*.095,-.26,1.49)],.008,seammat)
 ell('Drawstring round end '+str(s),(s*.095,-.26,1.48),(.022,.018,.026),cloth,24,16)
# Kangaroo pocket follows the torso's curved front, open angled sides.
def pocketpoint(x,z):return (x,-.24*math.sqrt(max(.1,1-(x/.35)**2))-.025,z)
m=Mesh()
def pocket(u,v):
 z=1.015+.22*v;w=.238-.065*v
 return pocketpoint((u-.5)*2*w,z)
m.surface(pocket,21,13);mesh('Kangaroo pocket',m,cloth,1,.009)
curve('Pocket bottom stitch',[pocket(u,.03) for u in [i/20 for i in range(21)]],.0025,seammat)
for u in [0,1]:curve('Pocket opening '+str(u),[pocket(u,v) for v in [0,.3,.6,1]],.005,seammat)
curve('Hem seam',[(.386*math.sin(t),-.247*math.cos(t),.82) for t in [2*math.pi*k/72 for k in range(72)]],.004,seammat,True)
# Limbs and individual relaxed fingers, fused only within each limb.
for s in [-1,1]:
 m=Mesh();tube_mesh(m,[(s*.395,0,1.58),(s*.432,-.005,1.40),(s*.458,-.025,1.22),(s*.476,-.035,1.07)],[.093,.085,.074,.058])
 m.ellipsoid((s*.481,-.039,1.015),(.067,.046,.098),seg=32,rings=20)
 for j in range(4):
  x=s*(.44+j*.025);z=.965-.008*math.sin(j*math.pi/3)
  tube_mesh(m,[(x,-.038,1.00),(x,-.047,z),(x,-.065,z-.038)],[.016,.015,.012],16)
  m.ellipsoid((x,-.065,z-.038),(.012,.013,.014),seg=16,rings=12)
 tube_mesh(m,[(s*.43,-.048,1.05),(s*.411,-.076,1.02),(s*.415,-.087,.983)],[.023,.019,.014],16)
 o=mesh('Arm and hand '+str(s),m,skin);fuse(o,.007)
 m=Mesh();tube_mesh(m,[(s*.174,.02,.88),(s*.181,.012,.70),(s*.187,-.005,.53),(s*.191,.02,.37),(s*.195,.027,.145)],[.115,.107,.087,.079,.054],32)
 m.ellipsoid((s*.195,-.065,.132),(.078,.155,.061),seg=32,rings=20)
 for j in range(5):m.ellipsoid((s*.195-.055+j*.027,-.20,.115),(.017,.035,.026),seg=20,rings=14)
 o=mesh('Leg and foot '+str(s),m,skin);fuse(o,.007)
 # Rounded sole built from a capsule outline, retaining width after smoothing.
 m=Mesh();N=64
 for z,scale in [(.027,.94),(.035,1),(.075,1),(.084,.95)]:
  for j in range(N):
   t=2*math.pi*j/N;m.v.append((s*.195+.108*math.sin(t)*scale,-.065+.213*math.cos(t)*scale,z))
 for k in range(3):
  for j in range(N):a=k*N+j;b=k*N+(j+1)%N;m.f.append([a,b,b+N,a+N])
 m.f+=[list(range(N))[::-1],[3*N+j for j in range(N)]]
 mesh('Slide sole '+str(s),m,cream,2)
 m=Mesh()
 def strap(u,v):
  t=math.pi*u;return(s*.195+.103*math.cos(t),-.135+.105*v,.087+.118*math.sin(t)**.7)
 m.surface(strap,33,9);mesh('Slide padded strap '+str(s),m,cream,2,.021)

# Studio and orthographic cameras; separate collection from character.
studio=bpy.data.collections.new('Studio');sc.collection.children.link(studio)
def move_to_studio(o):
 for c in list(o.users_collection):c.objects.unlink(o)
 studio.objects.link(o)
bpy.ops.mesh.primitive_plane_add(size=200);ground=bpy.context.object;ground.name='Studio floor';ground.location.z=.025;move_to_studio(ground)
ground.data.materials.append(material('Warm studio background',(.76,.69,.59),.82))
world=bpy.data.worlds.new('Soft studio world');sc.world=world;world.use_nodes=True;world.node_tree.nodes.get('Background').inputs[0].default_value=(.85,.80,.72,1);world.node_tree.nodes.get('Background').inputs[1].default_value=.35
for name,loc,power,size,color in [('Key',(-3,-4,6),500,4,(1,.84,.68)),('Fill',(3,-2,4),320,3,(.78,.88,1)),('Rim',(1,3,5),650,3,(1,.9,.76))]:
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;d.color=color
 o=bpy.data.objects.new(name,d);studio.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,1.5))-o.location).to_track_quat('-Z','Y').to_euler()
for name,loc in [('front',(0,-8,1.65)),('three-quarter',(4,-8,2.7)),('side',(8,0,1.65)),('back',(0,8,1.65))]:
 d=bpy.data.cameras.new(name);d.type='ORTHO';d.ortho_scale=3.65
 o=bpy.data.objects.new('Camera '+name,d);studio.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,1.6))-o.location).to_track_quat('-Z','Y').to_euler()
sc.camera=bpy.data.objects['Camera three-quarter']
sc.render.engine='CYCLES';sc.cycles.samples=64;sc.cycles.use_denoising=True
sc.render.resolution_x=960;sc.render.resolution_y=1200;sc.render.resolution_percentage=100
sc.view_settings.view_transform='AgX';sc.render.image_settings.file_format='PNG'
# Useful opening view and selection.
bpy.ops.object.select_all(action='DESELECT');head.select_set(True);bpy.context.view_layer.objects.active=head
for screen in bpy.data.screens:
 for a in screen.areas:
  if a.type=='VIEW_3D':
   a.spaces.active.region_3d.view_distance=5;a.spaces.active.region_3d.view_location=(0,0,1.6)
   a.spaces.active.region_3d.view_rotation=sc.camera.rotation_euler.to_quaternion();a.spaces.active.shading.type='MATERIAL'
root['design_reference']='owner-character-3d-v01.png / owner-character-3d-side-back-v01.png'
root['status']='Static editable model; no rig or animation; full size 3.16 scene units.'
bpy.ops.wm.save_as_mainfile(filepath=P+'/assets/blender/characters/owner-character-v02.blend')
for name in ['three-quarter','front','side','back']:
 sc.camera=bpy.data.objects['Camera '+name];sc.render.filepath=OUT+'/'+name+'.png';bpy.ops.render.render(write_still=True)
print('OWNER_V02_COMPLETE',flush=True)
