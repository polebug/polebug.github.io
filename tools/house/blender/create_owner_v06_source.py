from pathlib import Path
p=Path('/Users/bugpole/AI/博客陪伴小屋/assets/blender/scripts');s=(p/'build_owner_v05.py').read_text()
s=s.replace('Owner_V05','Owner_V06').replace('owner-character-v05','owner-character-v06').replace('character-v05','character-v06').replace('OWNER_V05','OWNER_V06')
a=s.index("for s in [-1,1]:\n ell('Ear '");b=s.index('# Eyes follow',a)
s=s[:a]+'''# Compact ears with a recessed bowl and a softly raised helix, tucked into the head.
for side in [-1,1]:
 m=Mesh();N=64;R=18
 def ep(r,t):
  return (side*(.505+.076*r*math.cos(t)),-.145-.032*math.exp(-((r-.79)/.15)**2)+.015*(1-r)**2,2.25+.107*r*math.sin(t))
 m.v.append(ep(0,0))
 for i in range(1,R+1):
  for j in range(N):m.v.append(ep(i/R,2*math.pi*j/N))
 for j in range(N):m.f.append([0,1+j,1+(j+1)%N])
 for i in range(R-1):
  for j in range(N):
   a=1+i*N+j;b=1+i*N+(j+1)%N;m.f.append([a,b,b+N,a+N])
 mesh('Ear sculpted shell '+str(side),m,skin,1,.025)
 curve('Ear inner fold '+str(side),[ep(.48,t) for t in [.1+i*2.6/16 for i in range(17)]],.0035,skin)
''' +s[b:]
s=s.replace('3.015+(edge(2*math.pi*u)-3.015)*v','3.02+(edge(2*math.pi*u)-3.02)*v')
s=s.replace('ztop=2.97-.02*math.sin(k*.8);zend=edge(target)+.003','ztop=3.019;zend=edge(target)+.003')
s=s.replace('width=.12*math.sin(math.pi*v)**.45+.002','width=.105*math.sin(math.pi*v)**.65+.0003')
s=s.replace('.003+.007*math.sin(math.pi*u)*math.sin(math.pi*v)','.001+.004*math.sin(math.pi*u)*math.sin(math.pi*v)')
a=s.index('# Broad curtain bangs:');b=s.index('# Relaxed gray',a)
s=s[:a]+'''# Two controlled curtain sections per side; roots converge on the actual crown.
def bez(pts,t):
 a,b,c,d=map(Vector,pts);return a*(1-t)**3+b*3*t*(1-t)**2+c*3*t*t*(1-t)+d*t**3
for side in [-1,1]:
 for k in range(2):
  if k==0:
   controls=[(side*.012,.035,3.018),(side*.17,-.36,2.99),(side*.37,-.46,2.64),(side*.595,-.225,2.22)]
  else:
   controls=[(side*.022,.047,3.018),(side*.37,-.29,3.00),(side*.66,-.24,2.46),(side*.61,-.12,1.435)]
  def bang(u,v,controls=controls,k=k):
   p=bez(controls,v)
   tangent=(bez(controls,min(1,v+.001))-bez(controls,max(0,v-.001))).normalized()
   across=Vector((-tangent.z,0,tangent.x)).normalized()
   w=(.002+.10*math.sin(math.pi*v)**.8) if k==0 else (.002+.065*math.sin(math.pi*v)**.7+.017*v)
   p+=across*((u-.5)*2*w)
   p.y-=.014*math.sin(math.pi*u)*math.sin(math.pi*v)
   return p
  m=Mesh();m.surface(bang,17,55);mesh('Swept curtain fringe %s %s'%(side,k),m,hairmat,1,.010)
''' +s[b:]
s=s.replace("[(side*.16,.012,1.10),(side*.176,.015,.93),(side*.184,.012,.72),(side*.19,.008,.53),(side*.195,.022,.34),(side*.195,.025,.19)],[.158,.15,.138,.124,.112,.105]","[(side*.16,.012,1.10),(side*.185,.015,.93),(side*.205,.012,.72),(side*.211,.008,.53),(side*.216,.022,.34),(side*.22,.025,.145)],[.158,.169,.18,.187,.194,.202]")
s=s.replace("[(side*.309,.01,1.07),(side*.323,.015,.94),(side*.319,.012,.72),(side*.312,.008,.53),(side*.305,.022,.34),(side*.297,.025,.21)]","[(side*.309,.01,1.07),(side*.351,.015,.94),(side*.382,.012,.72),(side*.395,.008,.53),(side*.407,.022,.34),(side*.419,.025,.175)]")
s=s.replace('for z in [.208,.217]:','for z in [.172,.181]:')
s=s.replace('(side*.195+.102*math.sin(t),.025+.102*math.cos(t),z)','(side*.22+.198*math.sin(t),.025+.198*math.cos(t),z)')
s=s.replace('Full size 3.16 scene units.','Full size approximately 3.02 scene units.')
(p/'build_owner_v06.py').write_text(s)
s=(p/'export_owner_v05.py').read_text().replace('Owner_V05','Owner_V06').replace('owner-character-v05','owner-character-v06').replace('character-v05','character-v06');(p/'export_owner_v06.py').write_text(s)
