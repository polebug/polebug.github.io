from pathlib import Path
p=Path('/Users/bugpole/AI/博客陪伴小屋/assets/blender/scripts')
s=(p/'build_owner_v02.py').read_text().replace('Owner_V02','Owner_V03').replace('owner-character-v02','owner-character-v03').replace('character-v02','character-v03').replace('OWNER_V02','OWNER_V03')
s=s.replace("cloth=material('Hoodie • charcoal cotton',(.014,.014,.017),.86)","cloth=material('T-shirt • soft gray cotton',(.29,.30,.315),.88)")
s=s.replace("seammat=material('Cotton seams',(.023,.022,.025),.85)","seammat=material('Gray cotton seams',(.24,.25,.265),.88)\ndenim=material('Jeans • indigo denim',(.035,.105,.22),.87)\nstitch=material('Jeans • muted ochre stitching',(.34,.23,.105),.85)\ndenimedge=material('Denim seam',(.025,.065,.135),.9)")
a=s.index('# Dress:');b=s.index('for s in [-1,1]:\n m=Mesh();N=48',a)
s=s[:a]+'''# Relaxed gray crew-neck tee, ending over the jeans waistband.
prof=[(1.115,.343,.218),(1.13,.347,.222),(1.20,.34,.22),(1.40,.32,.215),(1.68,.305,.195),(1.79,.265,.165),(1.865,.128,.103),(1.875,.125,.102)]
m=Mesh();N=64
for z,rx,ry in prof:
 for j in range(N):
  t=2*math.pi*j/N
  fold=.005*math.sin(t*7+.4)*math.sin(math.pi*(z-1.115)/.76)
  m.v.append(((rx+fold)*math.sin(t),-(ry+fold)*math.cos(t),z))
for k in range(len(prof)-1):
 for j in range(N):a=k*N+j;b=k*N+(j+1)%N;m.f.append([a,b,b+N,a+N])
mesh('Gray T-shirt • relaxed body',m,cloth,2,.015)
''' +s[b:]
a=s.index('# Closed, softly compressed hood');b=s.index('# Limbs and individual',a)
s=s[:a]+'''# Bound round collar and quiet double hem stitch, without hood or drawstrings.
curve('Crew-neck rib binding',[(.127*math.sin(t),-.105*math.cos(t),1.87-.022*max(0,math.cos(t))) for t in [2*math.pi*k/64 for k in range(64)]],.012,seammat,True)
for z in [1.135,1.144]:
 curve('T-shirt hem stitch '+str(z),[(.346*math.sin(t),-.222*math.cos(t),z) for t in [2*math.pi*k/72 for k in range(72)]],.0018,seammat,True)
# Jeans: connected pelvis and two softly tapered full-length legs.
m=Mesh();m.ellipsoid((0,.01,1.055),(.302,.185,.235),seg=64,rings=40)
for side in [-1,1]:
 tube_mesh(m,[(side*.16,.012,1.10),(side*.176,.015,.93),(side*.184,.012,.72),(side*.19,.008,.53),(side*.195,.022,.34),(side*.195,.025,.19)],[.158,.15,.138,.124,.112,.105],40)
o=mesh('Jeans • continuous pelvis and legs',m,denim);fuse(o,.008)
# Fine woven texture is subtle at the intended camera scale.
n=denim.node_tree.nodes;l=denim.node_tree.links;bs=n.get('Principled BSDF')
noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=260;noise.inputs['Detail'].default_value=2
bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.17;bump.inputs['Distance'].default_value=.0008
l.new(noise.outputs['Fac'],bump.inputs['Height']);l.new(bump.outputs['Normal'],bs.inputs['Normal'])
for side in [-1,1]:
 # Long outer leg seam and cuff follow the trouser profile.
 curve('Jeans outer seam '+str(side),[(side*.309,.01,1.07),(side*.323,.015,.94),(side*.319,.012,.72),(side*.312,.008,.53),(side*.305,.022,.34),(side*.297,.025,.21)],.0025,denimedge)
 for z in [.208,.217]:
  curve('Jeans cuff '+str(side)+' '+str(z),[(side*.195+.102*math.sin(t),.025+.102*math.cos(t),z) for t in [2*math.pi*k/48 for k in range(48)]],.0018,stitch,True)
 # Front curved hand-pocket openings below the tee.
 curve('Jeans front pocket '+str(side),[(side*.14,-.179,1.105),(side*.21,-.164,1.055),(side*.27,-.115,1.00)],.0025,stitch)
 # Five-sided rear patch pocket, following the curved seat.
 pts=[(side*.08,.181,1.09),(side*.235,.151,1.09),(side*.232,.15,.98),(side*.153,.183,.942),(side*.083,.183,.98)]
 m=Mesh();m.v=pts;m.f=[list(range(5))];mesh('Jeans back pocket '+str(side),m,denim,0,.005)
 curve('Back pocket stitch '+str(side),pts,.002,stitch,True)
curve('Jeans fly seam',[(0,-.187,1.11),(0,-.189,1.05),(.025,-.18,.98)],.002,denimedge)
''' +s[b:]
(p/'build_owner_v03.py').write_text(s)
s=(p/'export_owner_v02.py').read_text().replace('Owner_V02','Owner_V03').replace('owner-character-v02','owner-character-v03').replace('character-v02','character-v03')
(p/'export_owner_v03.py').write_text(s)
