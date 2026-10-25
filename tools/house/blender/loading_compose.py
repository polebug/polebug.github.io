"""Compose the loading line art (2026-10-22) from loading_lineart.py's layers:
each region's strokes kept only where that region is in front (the masks give the occlusion the
separate Freestyle layers lack), tree outlines traced from the tree mask, all on warm paper.

    Blender -b --python assets/blender/scripts/loading_compose.py
Writes lines_trees.png (pines, forest), lines_maple.png (front-yard maples and shrubs) and
lineart.png next to the layers. The region layers are overwritten with occlusion applied, so a
second run must set COMPOSE_TREES_ONLY=1: it redraws the tree layers and reuses the saved rest.
"""
import os
import bpy
import numpy as np

OUT = '/Users/bugpole/AI/博客陪伴小屋/assets/renders/loading'
INK = np.array((0.24, 0.2, 0.17), np.float32)
PAPER = np.array((0.965, 0.945, 0.9), np.float32)

def load(name):
    im = bpy.data.images.load(f'{OUT}/{name}')
    w, h = im.size
    a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1]      # top row first
    bpy.data.images.remove(im)
    return a

def save(name, a):
    h, w = a.shape[:2]
    im = bpy.data.images.new('_o', w, h, alpha=a.shape[2] == 4)
    im.pixels.foreach_set(a[::-1].ravel())
    im.filepath_raw = f'{OUT}/{name}'
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)

def blur(m, r):
    k = 2 * r + 1
    c = np.cumsum(np.pad(m, ((0, 0), (r + 1, r)), mode='edge'), 1)
    m = (c[:, k:] - c[:, :-k]) / k
    c = np.cumsum(np.pad(m, ((r + 1, r), (0, 0)), mode='edge'), 0)
    return (c[k:] - c[:-k]) / k

def grow(m, r):
    return blur(m.astype(np.float32), r) > 1e-3

import json

def stroke_layer(polys, w=1.3):
    """Anti-aliased polylines (pixel coords) as an ink coverage map."""
    ink = np.zeros((H, W), np.float32)
    for line in polys:
        for (x0, y0), (x1, y1) in zip(line[:-1], line[1:]):
            lx0, lx1 = int(max(0, min(x0, x1) - 3)), int(min(W, max(x0, x1) + 4))
            ly0, ly1 = int(max(0, min(y0, y1) - 3)), int(min(H, max(y0, y1) + 4))
            if lx1 <= lx0 or ly1 <= ly0:
                continue
            yy, xx = np.mgrid[ly0:ly1, lx0:lx1] + 0.5
            dx, dy = x1 - x0, y1 - y0
            L2 = dx * dx + dy * dy or 1e-6
            t = np.clip(((xx - x0) * dx + (yy - y0) * dy) / L2, 0, 1)
            d = np.hypot(xx - (x0 + t * dx), yy - (y0 + t * dy))
            ink[ly0:ly1, lx0:lx1] = np.maximum(ink[ly0:ly1, lx0:lx1], np.clip(w / 2 + 0.5 - d, 0, 1))
    return ink

def outline(m, r, thr, w=1.0):
    """Outline of a mask, its shape first rounded (blur r, threshold) so it reads as one drawn form."""
    t = blur(m.astype(np.float32), r) > thr
    e = t & ~(np.roll(t, 1, 0) & np.roll(t, -1, 0) & np.roll(t, 1, 1) & np.roll(t, -1, 1))
    return np.clip(blur(e.astype(np.float32), 1) * 2.2 * w, 0, 1)

def lighten_dense(a, r=5, target=0.16, floor=0.3):
    """Where strokes crowd (blinds, bookshelves, leaves) fade them, so the drawing stays light."""
    dens = blur(a, r)
    return a * np.clip(target / np.maximum(dens, 1e-4), floor, 1)

mask = load('mask_regions.png')[..., :3]
H, W = mask.shape[:2]
CODE = {'mountains': (1, 0, 0), 'trees': (0, 1, 0), 'lake': (0, 0, 1), 'grass': (1, 1, 0), 'house': (1, 0, 1)}
region = {k: np.all(np.abs(mask - np.array(v)) < 0.2, -1) for k, v in CODE.items()}
ids = load('mask_ids.png')[..., :3]
IDS = {'pine': (0.2, 1, 0.2), 'maple': (0.2, 0.6, 0.2), 'shrub': (0.6, 1, 0.6), 'forest': (0, 0.4, 0),
       'stone': (1, 0.6, 0), 'turf': (0.6, 0.6, 0)}
srgb = lambda c: np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)   # object colours are linear
idm = {k: np.all(np.abs(ids - srgb(np.array(v))) < 0.05, -1) for k, v in IDS.items()}
print('COMPOSE id pixels', {k: int(v.sum()) for k, v in idm.items()})

# ---- trees, drawn: pine tiers from strokes.json, maple trunks and limbs, rounded canopies and shrubs
S = json.load(open(f'{OUT}/strokes.json'))
# pines: their own silhouette (branch tiers show as a jagged edge), plus drawn drooping tips inside
pine_edge = outline(idm['pine'] & ~idm['forest'], 2, 0.45)
tips = stroke_layer([l for p in S['pines'] for l in p if 3 <= len(l) <= 4], 1.2) * idm['pine']
pine_ink = np.maximum(pine_edge, tips * 0.8)
# maples like the pines: the silhouette only, crisp leaf edges, no inner branches (user, 10-22)
def fill_holes(m):
    """Background reachable from the frame edge stays background; enclosed gaps in a canopy fill in."""
    bg = np.zeros_like(m)
    bg[0, :], bg[-1, :], bg[:, 0], bg[:, -1] = ~m[0, :], ~m[-1, :], ~m[:, 0], ~m[:, -1]
    free = ~m
    for _ in range(4000):
        nb = bg | (free & (np.roll(bg, 1, 0) | np.roll(bg, -1, 0) | np.roll(bg, 1, 1) | np.roll(bg, -1, 1)))
        if (nb == bg).all():
            break
        bg = nb
    return ~bg

def thin(m, r, thr):
    """A fine 1 px outline: the front-yard plants are drawn lighter than the pines (user, 10-22)."""
    t = blur(m.astype(np.float32), r) > thr
    e = t & ~(np.roll(t, 1, 0) & np.roll(t, -1, 0) & np.roll(t, 1, 1) & np.roll(t, -1, 1))
    return np.clip(blur(e.astype(np.float32), 1) * 1.6, 0, 0.85)

# maples: one rounded silhouette per tree, leaf gaps filled so no specks draw inside the crown
maple_fill = fill_holes(blur(idm['maple'].astype(np.float32), 2) > 0.3)
maple_can = thin(maple_fill, 1, 0.5)
shrub_ink = thin(idm['shrub'], 4, 0.4)
forest_ink = outline(idm['forest'], 4, 0.5, 0.8)
yard_ink = np.maximum(maple_can, shrub_ink)
# the yard plants are drawn opaque: nothing behind them shows, and the house's heavy edge
# no longer traces around their leaves
behind = ~(blur((maple_fill | (blur(idm['shrub'].astype(np.float32), 4) > 0.4)).astype(np.float32), 1) > 0.5)
tree_ink = np.maximum.reduce([pine_ink, forest_ink]) * behind

def layer(a):
    lay = np.zeros((H, W, 4), np.float32)
    lay[..., :3] = INK
    lay[..., 3] = a
    return lay
save('lines_trees.png', layer(tree_ink))
save('lines_maple.png', layer(yard_ink))

# the mulch ring under each maple drew as a dense scribble: keep only its outline
def thin_rings(a):
    near = grow(idm['maple'], 80)
    dense = grow((blur(a, 6) > 0.2) & near, 3)
    return np.where(grow(dense, 3), thin(dense, 2, 0.5), a)

# paper, then each region's ink where that region is in front (a 2 px margin keeps its outline);
# no strokes on bare lawn: the stones' buried halves drew huge ovals there
rng = np.random.default_rng(3)
grain = blur(rng.random((H, W)).astype(np.float32), 1)
out = np.ones((H, W, 3), np.float32) * PAPER * (0.985 + 0.03 * grain[..., None])
total = np.zeros((H, W), np.float32)
bare = idm['turf'] & ~grow(~idm['turf'], 2)
crowns = blur((idm['pine'] | idm['maple']).astype(np.float32), 4) > 0.25
if os.environ.get('COMPOSE_TREES_ONLY'):
    for name in ('mountains', 'lake', 'grass', 'house'):
        a = load(f'lines_{name}.png')[..., 3] * behind
        if name == 'grass':
            a = thin_rings(a)
        save(f'lines_{name}.png', layer(a))
        total = np.maximum(total, a)
else:
    for name in ('mountains', 'lake', 'grass', 'house'):
        a = load(f'lines_{name}.png')[..., 3] * grow(region[name], 2)
        if name in ('grass', 'lake'):
            a = a * ~bare
        if name != 'house':
            a = a * ~crowns
        if name == 'house':
            a = lighten_dense(a, 5, 0.14, 0.15)
        if name == 'grass':
            a = thin_rings(a)
        a = a * behind
        save(f'lines_{name}.png', layer(a))          # occlusion applied: the page uses these layers as they are
        total = np.maximum(total, a)
    house_edge = outline(region['house'], 1, 0.5, 1.4) * behind   # the house's silhouette, drawn heavier
    total = np.maximum(total, house_edge)
    lh = load('lines_house.png'); lh[..., 3] = np.maximum(lh[..., 3], house_edge); save('lines_house.png', lh)
total = np.maximum.reduce([total, tree_ink, yard_ink])
out = out * (1 - total[..., None]) + INK * total[..., None]
save('lineart.png', np.dstack([out, np.ones((H, W, 1), np.float32)]))
print('COMPOSE done')
