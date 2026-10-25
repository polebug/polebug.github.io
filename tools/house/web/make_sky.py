"""Blue sky with white clouds for the house page (web/house/assets/sky.webp), user 10-22 ("天空能不能蓝一点，
现在有点雾蒙蒙的。这种蓝天白云的样子"): a real photographed sky, Poly Haven's
kloofendal_48d_partly_cloudy_puresky (CC0, assets/blender/textures/hdri/), projected straight onto the
backdrop's frame (square, 96 deg across, overview camera looking level along +y, horizon on the middle row)
and graded a little deeper blue. The page hangs it behind the backdrop, whose sky is transparent.
Only the sky is swapped: the house lighting keeps the clear-sky HDRI it was baked with.

    Blender -b --factory-startup --python web/tools/make_sky.py -- <hdri> <out.png> [centre_u] [px]

centre_u picks the part of the panorama that faces the house (0..1 across the HDRI, default 0.22: the
clear blue side with cumulus, away from the sun's glare)."""
import bpy, numpy as np, sys, math

args = sys.argv[sys.argv.index('--') + 1:]
src, out = args[0], args[1]
CU = float(args[2]) if len(args) > 2 else 0.22
N = int(args[3]) if len(args) > 3 else 2048
HFOV = math.radians(96)

im = bpy.data.images.load(src)
w, h = im.size
pan = np.array(im.pixels[:], np.float32).reshape(h, w, 4)[..., :3]      # row 0 = bottom

# directions of the plate's pixels (Blender axes: x right, y forward, z up); plate row 0 = top
t = math.tan(HFOV / 2)
j, i = np.mgrid[0:N, 0:N].astype(np.float64)
dx = ((i + 0.5) / N - 0.5) * 2 * t
dz = (0.5 - (j + 0.5) / N) * 2 * t
dy = np.ones_like(dx)
az = np.arctan2(dx, dy)                                    # 0 straight ahead, + to the right
el = np.arctan2(dz, np.hypot(dx, dy))
u = (CU + az / (2 * math.pi)) % 1.0
v = 0.5 + el / math.pi                                     # from the bottom, as the pixels are stored
# bilinear lookup
x = u * w - 0.5; y = v * h - 0.5
x0 = np.floor(x).astype(int); y0 = np.clip(np.floor(y).astype(int), 0, h - 2)
fx = (x - x0)[..., None]; fy = np.clip(y - y0, 0, 1)[..., None]
x0 %= w; x1 = (x0 + 1) % w
c = (pan[y0, x0] * (1 - fx) + pan[y0, x1] * fx) * (1 - fy) + (pan[y0 + 1, x0] * (1 - fx) + pan[y0 + 1, x1] * fx) * fy

# grade: blue sky to ~0.3 linear, clouds rolled off softly so their shading survives, then a deeper,
# cleaner blue (less of the pale haze the photo carries near the horizon)
sky_ref = np.median(c[(el > math.radians(15)) & (el < math.radians(40))].reshape(-1, 3), axis=0)
c = c / sky_ref.mean() * 0.24
lum = c @ np.array([0.2126, 0.7152, 0.0722])
k = 1.6
c = c * (((lum * k) / (1 + lum * k)) / np.maximum(lum, 1e-6) * (1 + 1 / k) / 1.6)[..., None]
lum = c @ np.array([0.2126, 0.7152, 0.0722])
blueness = np.clip((c[..., 2] - c[..., 0]) / np.maximum(c[..., 2], 1e-6) * 2.2, 0, 1)   # sky vs cloud
sat = 1 + 0.45 * blueness
c = lum[..., None] + (c - lum[..., None]) * sat[..., None]
c = c * (1 - 0.18 * blueness)[..., None]                # deeper blue, clouds untouched
srgb = np.where(c <= 0.0031308, 12.92 * c, 1.055 * np.power(np.clip(c, 0, None), 1 / 2.4) - 0.055)
srgb = np.clip(srgb, 0, 1)[::-1]                           # Blender images store bottom row first
img = bpy.data.images.new('sky', N, N)
img.pixels.foreach_set(np.dstack([srgb, np.ones((N, N, 1))]).astype(np.float32).ravel())
img.filepath_raw = out
img.file_format = 'PNG'
img.save()
print('SKY ok', out, 'ref', sky_ref)
