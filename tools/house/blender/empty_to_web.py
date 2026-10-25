"""The empty-room lightmaps (export_web.py, WEB_EMPTY=1) for the page (2026-10-22): bake_<g>_empty.png ->
web/house/assets/empty_<g>.webp, at half size (they only show while the house is being built).

    Blender -b --python assets/blender/scripts/empty_to_web.py
"""
import bpy, os

P = '/Users/bugpole/AI/博客陪伴小屋'
for g in ('house', 'floors', 'boards', 'rugs'):
    src = f'{P}/assets/web-build/bake_{g}_empty.png'
    if not os.path.exists(src):
        print('EMPTY missing', g)
        continue
    im = bpy.data.images.load(src)
    w, h = im.size
    if w > 1024:
        im.scale(w // 2, h // 2)
    out = f'{P}/web/house/assets/empty_{g}.webp'
    im.file_format = 'WEBP'
    im.save(filepath=out, quality=85)
    print('EMPTY', g, im.size[0], os.path.getsize(out) // 1024, 'KB')
