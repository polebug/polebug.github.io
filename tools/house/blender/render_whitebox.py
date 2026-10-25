"""Render the whitebox cameras and a 50 % overlay of the overview on the target image.

Run:  Blender -b assets/blender/companion-house.blend --python render_whitebox.py
Output: assets/renders/whitebox/
"""
import bpy, os, numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(bpy.data.filepath), "..", ".."))
OUT = os.path.join(ROOT, "assets", "renders", "whitebox")
TARGET = os.path.join(ROOT, "assets", "concepts", "home-interior-refined-2026-10-19.png")
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene

def render(cam, name):
    sc.camera = bpy.data.objects[cam]
    sc.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    return sc.render.filepath

for cam, name in (("Cam_Overview", "overview"), ("Cam_Side_20deg", "side-20deg"),
                  ("Cam_Room_F1", "room-f1"), ("Cam_Room_F2", "room-f2"), ("Cam_Room_F3", "room-f3"),
                  ("Cam_Back_Check", "back-check")):
    render(cam, name)
sc.camera = bpy.data.objects["Cam_Overview"]

def load(path):
    im = bpy.data.images.load(path, check_existing=False)
    w, h = im.size
    return np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4), w, h

a, w, h = load(os.path.join(OUT, "overview.png"))
b, w2, h2 = load(TARGET)
assert (w, h) == (w2, h2), ((w, h), (w2, h2))
mix = a * 0.5 + b * 0.5
mix[..., 3] = 1
o = bpy.data.images.new("overlay", w, h, alpha=True)
o.pixels = mix.ravel()
o.filepath_raw = os.path.join(OUT, "overview-overlay.png")
o.file_format = 'PNG'
o.save()
print("RENDERED", OUT)
