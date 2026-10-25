"""The page's first picture (2026-10-22): the landscape from the overview camera, without the house and
the yard, rendered with the approved Cycles look.

    Blender -b assets/blender/companion-house.blend --python assets/blender/scripts/render_poster.py

It is plain HTML, so it shows long before three.js and the 3D assets arrive; the live scene fades in
over it. The camera keeps its horizontal angle on every screen, so the page lays the picture at the
full window width, centred vertically, and it lines up with the 3D view whatever the window's shape.
It is tall (POSTER_W x POSTER_H) so that portrait phones are covered as well.
Writes web/house/assets/poster.webp. The source .blend is never saved.
"""
import bpy, os

OUT = '/Users/bugpole/AI/博客陪伴小屋/web/house/assets/poster.webp'
W = int(os.environ.get('POSTER_W', 1600))
H = int(os.environ.get('POSTER_H', 2800))
HIDE = ('11_Frame', '12_Walls', '13_Floors', '14_Windows', '15_Roof', '16_Stonework', '17_Flues',
        '21_Floor1', '22_Floor2', '23_Floor3', '31_Yard')

sc = bpy.context.scene
try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'METAL'
    prefs.get_devices()
    for d in prefs.devices:
        d.use = True
    sc.cycles.device = 'GPU'
except Exception as e:
    print('POSTER GPU not available:', e)
# by the collections each scene object sits in (the collections' all_objects missed some of them)
for o in sc.objects:
    if any(c.name in HIDE for c in o.users_collection) or (o.parent and o.parent.hide_render):
        o.hide_render = True
for o in sc.objects:                                   # children of hidden parents, in any order
    p = o.parent
    while p:
        if p.hide_render:
            o.hide_render = True
            break
        p = p.parent
sc.camera = bpy.data.objects['Cam_Overview']
sc.camera.data.sensor_fit = 'HORIZONTAL'
sc.camera.data.shift_x = sc.camera.data.shift_y = 0.0      # the page's camera has no lens shift (glTF has none)
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
sc.cycles.samples = int(os.environ.get('POSTER_SAMPLES', 96))
sc.cycles.use_denoising = True
sc.render.filepath = OUT
sc.render.image_settings.file_format = 'WEBP'
sc.render.image_settings.color_mode = 'RGB'
sc.render.image_settings.quality = int(os.environ.get('POSTER_Q', 80))
left = [o.name for o in sc.objects if not o.hide_render and o.type == 'MESH' and any(c.name in HIDE for c in o.users_collection)]
print('POSTER still visible from hidden collections:', left[:10])
bpy.ops.render.render(write_still=True)
print('POSTER', W, H, os.path.getsize(OUT) // 1024, 'KB')
