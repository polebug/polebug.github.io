from pathlib import Path
p=Path('/Users/bugpole/AI/博客陪伴小屋/assets/blender/scripts/build_owner_v02.py')
s=p.read_text()
s=s.replace("(.012,.009,.007),.36,coat=.12","(.009,.0065,.005),.52,coat=.02")
a=s.index('# Eyes recessed');b=s.index("curve('Glasses bridge'",a)
s=s[:a]+'''# Eyes follow the facial surface; shallow domes rather than projecting eyeballs.
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
''' + s[b:]
s=s.replace("[(-.041,-.53,2.39),(0,-.553,2.414),(.041,-.53,2.39)]","[(-.041,-.444,2.39),(0,-.472,2.414),(.041,-.444,2.39)]")
s=s.replace("def bobrad(z):return interp([(1.94,.60),(2.03,.69),(2.22,.755),(2.48,.76),(2.70,.65),(2.88,.43),(3.015,.005)],z)","def bobrad(z):\n return .765*math.sqrt(max(.00005,1-((z-2.47)/.55)**2)) if z>=2.47 else .765-.14*((2.47-z)/.53)**2")
s=s.replace(".009+.018*math.sin(math.pi*u)*math.sin(math.pi*v)",".003+.007*math.sin(math.pi*u)*math.sin(math.pi*v)")
s=s.replace("for j in [-.28,0,.28]:","for j in []:")
s=s.replace("for u in [.25,.45,.65,.8]:","for u in []:")
a=s.index("for s in [-1,1]:\n m=Mesh();tube_mesh(m,[(s*.25");b=s.index("curve('Soft V neckline'",a)
s=s[:a]+'''for s in [-1,1]:
 m=Mesh();N=48
 centers=[(s*.26,0,1.76),(s*.285,0,1.73),(s*.405,0,1.52),(s*.41,0,1.515)]
 direction=Vector((s*.15,0,-.245)).normalized();a=Vector((0,1,0));b=direction.cross(a)
 for ci,c in enumerate(centers):
  rad=[.147,.148,.149,.148][ci]
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
''' +s[b:]
a=s.index("outline=[");b=s.index("curve('Hem seam'",a)
s=s[:a]+'''def pocketpoint(x,z):return (x,-.24*math.sqrt(max(.1,1-(x/.35)**2))-.025,z)
m=Mesh()
def pocket(u,v):
 z=1.015+.22*v;w=.238-.065*v
 return pocketpoint((u-.5)*2*w,z)
m.surface(pocket,21,13);mesh('Kangaroo pocket',m,cloth,1,.009)
curve('Pocket bottom stitch',[pocket(u,.03) for u in [i/20 for i in range(21)]],.0025,seammat)
for u in [0,1]:curve('Pocket opening '+str(u),[pocket(u,v) for v in [0,.3,.6,1]],.005,seammat)
''' +s[b:]
s=s.replace("ground.name='Studio floor';move_to_studio(ground)","ground.name='Studio floor';ground.location.z=.025;move_to_studio(ground)")
s=s.replace("sc.cycles.samples=32","sc.cycles.samples=48")
p.write_text(s)
