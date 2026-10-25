"""Render chosen cameras with the stage-5 look (EEVEE + Freestyle) to assets/renders/<folder>/.
Run:  Blender -b assets/blender/companion-house.blend --python render_final.py -- <folder> [Cam_A Cam_B ...]
Without camera names it renders the overview only."""
import bpy, os, sys
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
folder = args[0] if args else "materials"
cams = args[1:] or ["Cam_Overview"]
ROOT = os.path.abspath(os.path.join(os.path.dirname(bpy.data.filepath), "..", ".."))
OUT = os.path.join(ROOT, "assets", "renders", folder)
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
for c in cams:
    sc.camera = bpy.data.objects[c]
    sc.render.filepath = os.path.join(OUT, c.replace("Cam_", "").lower().replace("_", "-") + ".png")
    bpy.ops.render.render(write_still=True)
    print("RENDERED", sc.render.filepath)
