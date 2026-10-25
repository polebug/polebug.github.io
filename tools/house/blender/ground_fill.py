"""Fill the near-black spots in ground.webp (2026-10-22).

Objects lying on the lawn (path slabs, stones, shrub bases) are hidden from the top-down ground camera
but still block all light where they touch the grass, so the picture is black under them. Once house.glb
is in, the objects cover those spots; while it downloads the page shows the bare picture, so the spots
are filled with the lawn around them (push-pull: averaged down until covered, then blended back up).

    Blender -b --python assets/blender/scripts/ground_fill.py            (fixes web/house/assets/ground.webp)
export_web.py calls fill() right after rendering the ground.
"""
import bpy
import numpy as np

GROUND = '/Users/bugpole/AI/博客陪伴小屋/web/house/assets/ground.webp'
BLACK = 14 / 255                     # brightest channel below this, on opaque ground: a contact spot

def _down(c, w):
    h, wd = c.shape[0] // 2 * 2, c.shape[1] // 2 * 2
    c, w = c[:h, :wd], w[:h, :wd]
    cw = (c * w[..., None]).reshape(h // 2, 2, wd // 2, 2, -1).sum((1, 3))
    ws = w.reshape(h // 2, 2, wd // 2, 2).sum((1, 3))
    return cw / np.maximum(ws, 1e-6)[..., None], np.minimum(ws, 1)

def _fill(c, w):
    """Colour c (h, w, 3) known where w = 1: the gaps get the push-pull average of their surroundings."""
    if min(c.shape[:2]) < 2 or w.min() > 0.999:
        return c
    lc, lw = _down(c, w)
    lc = _fill(lc, lw)
    up = np.repeat(np.repeat(lc, 2, 0), 2, 1)
    up = np.pad(up, ((0, c.shape[0] - up.shape[0]), (0, c.shape[1] - up.shape[1]), (0, 0)), mode='edge')
    return c * w[..., None] + up * (1 - w[..., None])

def fill(path=GROUND, quality=85):
    im = bpy.data.images.load(path)
    W, H = im.size
    px = np.empty(W * H * 4, np.float32)
    im.pixels.foreach_get(px)
    px = px.reshape(H, W, 4)
    hole = (px[..., :3].max(-1) < BLACK) & (px[..., 3] > 0.5)
    ys, xs = np.nonzero(hole)
    if len(ys):
        m = 64                                            # work in the spots' bounding box plus a margin
        y0, y1, x0, x1 = max(0, ys.min() - m), min(H, ys.max() + m), max(0, xs.min() - m), min(W, xs.max() + m)
        sub = px[y0:y1, x0:x1]
        hs = hole[y0:y1, x0:x1]
        hs = np.maximum.reduce([np.roll(hs, d, a) for d in (-2, -1, 0, 1, 2) for a in (0, 1)])   # their dark rims too
        known = (~hs & (sub[..., 3] > 0.5)).astype(np.float32)
        sub[..., :3] = _fill(sub[..., :3].copy(), known)
        px[y0:y1, x0:x1] = sub
        im.pixels.foreach_set(px.ravel())
        im.file_format = 'WEBP'
        im.save(filepath=path, quality=quality)
    print('GROUND_FILL', int(hole.sum()), 'px filled')
    bpy.data.images.remove(im)

if __name__ == '__main__':
    fill()
