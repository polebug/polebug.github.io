import bpy,bmesh,os,json
from mathutils import Vector
P='/Users/bugpole/AI/博客陪伴小屋';OUT=P+'/assets/renders/character-v16';os.makedirs(OUT,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=P+'/assets/blender/characters/owner-character-v12.blend')
col=bpy.data.collections['Owner_V12'];col.name='Owner_V16'

root=bpy.data.objects['Owner_V12_ROOT'];root.name='Owner_V16_ROOT'
for ob in list(col.objects):
 if ob.name.startswith('Hair •'):bpy.data.objects.remove(ob,do_unlink=True)
with bpy.data.libraries.load(P+'/assets/third-party/chibi-models/cute-chibi-girl/editable.blend',link=False) as (a,b):b.objects=['character']
original=b.objects[0];col.objects.link(original);bpy.context.view_layer.update()
bm=bmesh.new();bm.from_mesh(original.data)
bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.material_index not in {4,5}],context='FACES')
bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
for v in bm.verts:
 q=original.matrix_world@v.co
 # Identical registration to the source head already in the avatar. No haircut or restyling.
 v.co=(q.y*.94*.85,-(q.x+.04)*.95*.85,1.84+(q.z-2.9252839)*.96*.85)
me=bpy.data.meshes.new('Original source hairstyle and accessories');bm.to_mesh(me);bm.free()
ob=bpy.data.objects.new('Hair • original Cute Chibi Girl design',me);col.objects.link(ob)
for m in original.data.materials:me.materials.append(m)
black=bpy.data.materials['Hair • soft black']
me.materials[5]=black
for f in me.polygons:f.use_smooth=True
ob.parent=root
ob['source']='Cute Chibi Girl by Syed’s Creation (Dawood3D), CC BY 4.0; original hair geometry and pink ties; hair recolored black, full unmodified hairstyle topology and UVs; registered to existing head'
bpy.data.objects.remove(original,do_unlink=True)
sc=bpy.context.scene;sc.camera=bpy.data.objects['Camera three-quarter'];sc.cycles.samples=32
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=P+'/assets/blender/characters/owner-character-v16.blend')
for view in ['three-quarter','front','side','back']:
 sc.camera=bpy.data.objects['Camera '+view];sc.render.filepath=OUT+'/'+view+'.png';bpy.ops.render.render(write_still=True)
bpy.ops.object.select_all(action='DESELECT')
for o in col.objects:
 o.select_set(True)
bpy.context.view_layer.objects.active=ob
bpy.ops.object.convert(target='MESH')
bpy.ops.export_scene.gltf(filepath=P+'/assets/blender/characters/owner-character-v16.glb',export_format='GLB',use_selection=True,export_apply=True,export_animations=False)
report={'hair_vertices':len(me.vertices),'hair_faces':len(me.polygons),'source_material_indices':sorted(set(f.material_index for f in me.polygons)),'base_version':'v12','rigged':False,'images_missing':[im.name for im in bpy.data.images if im.source=='FILE' and im.size[0]==0]}
open(OUT+'/validation.json','w').write(json.dumps(report,indent=2))
print('OWNER_V16_COMPLETE',report)
