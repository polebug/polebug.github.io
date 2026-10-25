"""Render every camera in 08_Cameras to assets/renders/architecture/, plus a 50 % overlay of the
overview on the target image.  Run:  Blender -b assets/blender/companion-house.blend --python render_architecture.py
"""
import bpy, os, sys, numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(bpy.data.filepath), "..", ".."))
OUT = os.path.join(ROOT, "assets", "renders", sys.argv[-1] if sys.argv[-1].isidentifier() else "architecture")
TARGET = os.path.join(ROOT, "assets", "concepts", "home-interior-refined-2026-10-19.png")
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
for cam in sorted((o for o in bpy.data.collections["08_Cameras"].objects if o.type == "CAMERA"), key=lambda o: o.name):
    sc.camera = cam
    name = cam.name.replace("Cam_", "").lower().replace("_", "-")
    sc.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
sc.camera = bpy.data.objects["Cam_Overview"]

def load(path):
    im = bpy.data.images.load(path, check_existing=False)
    w, h = im.size
    return np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4), w, h
a, w, h = load(os.path.join(OUT, "overview.png"))
b, _, _ = load(TARGET)
mix = a * 0.5 + b * 0.5
mix[..., 3] = 1
o = bpy.data.images.new("overlay", w, h, alpha=True)
o.pixels = mix.ravel()
o.filepath_raw = os.path.join(OUT, "overview-overlay.png")
o.file_format = 'PNG'
o.save()
print("RENDERED", OUT)
