"""Small mesh-building kit shared by the stage-3 interior scripts.

Geometry is collected in a Mesh (one per material), then turned into an object. An Asset groups
the meshes of one piece of furniture under an empty, so every asset can be moved, rotated, hidden
or made clickable as a unit later.
"""
import bpy, bmesh, math
from mathutils import Vector, Matrix


class Mesh:
    def __init__(self):
        self.v, self.f = [], []

    # -------------------------------------------------------------- primitives
    def solid(self, bottom, top):
        """Prism between two vertex loops of equal length."""
        n, i0 = len(bottom), len(self.v)
        self.v += [tuple(p) for p in bottom] + [tuple(p) for p in top]
        self.f.append([i0 + k for k in range(n)][::-1])
        self.f.append([i0 + n + k for k in range(n)])
        for k in range(n):
            a, b = i0 + k, i0 + (k + 1) % n
            self.f.append([a, b, b + n, a + n])

    def box(self, x0, x1, y0, y1, z0, z1):
        self.solid([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)],
                   [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)])

    def cbox(self, c, size):
        """Box by centre and size."""
        (x, y, z), (sx, sy, sz) = c, size
        self.box(x - sx / 2, x + sx / 2, y - sy / 2, y + sy / 2, z - sz / 2, z + sz / 2)

    def beam(self, p1, p2, w, h, side=None, w2=None, h2=None):
        """Rectangular member between end centres, optionally tapering to w2 x h2."""
        p1, p2 = Vector(p1), Vector(p2)
        d = (p2 - p1).normalized()
        side = Vector(side) if side else (Vector((0, 1, 0)) if abs(d.y) < 0.9 else Vector((1, 0, 0)))
        side = (side - d * side.dot(d)).normalized()
        up = d.cross(side)
        w2, h2 = w if w2 is None else w2, h if h2 is None else h2
        sq = lambda ww, hh: [(-ww / 2, -hh / 2), (ww / 2, -hh / 2), (ww / 2, hh / 2), (-ww / 2, hh / 2)]
        self.solid([p1 + side * a + up * b for a, b in sq(w, h)], [p2 + side * a + up * b for a, b in sq(w2, h2)])

    def rod(self, p1, p2, r, seg=12, r2=None):
        p1, p2 = Vector(p1), Vector(p2)
        axis = (p2 - p1).normalized()
        a = axis.orthogonal().normalized()
        b = axis.cross(a)
        r2 = r if r2 is None else r2
        ring = lambda rr, c: [c + (a * math.cos(t) + b * math.sin(t)) * rr
                              for t in (2 * math.pi * k / seg for k in range(seg))]
        self.solid(ring(r, p1), ring(r2, p2))

    def lathe(self, profile, base=(0, 0, 0), axis='z', seg=24, closed=False):
        """Revolve a profile [(radius, height)] about an axis through `base`."""
        bx, by, bz = base
        def pt(r, h, t):
            c, s = r * math.cos(t), r * math.sin(t)
            if axis == 'z':
                return (bx + c, by + s, bz + h)
            if axis == 'y':
                return (bx + c, by + h, bz + s)
            if axis == '-y':
                return (bx + c, by - h, bz + s)
            return (bx + h, by + c, bz + s)
        i0, n = len(self.v), len(profile)
        for k in range(seg):
            t = 2 * math.pi * k / seg
            self.v += [pt(r, h, t) for r, h in profile]
        pairs = [(j, j + 1) for j in range(n - 1)] + ([(n - 1, 0)] if closed else [])
        for k in range(seg):
            k2 = (k + 1) % seg
            for j, j2 in pairs:
                self.f.append([i0 + k * n + j, i0 + k * n + j2, i0 + k2 * n + j2, i0 + k2 * n + j])

    def ellipsoid(self, c, radii, seg=12, rings=8, rot=None):
        c, (rx, ry, rz) = Vector(c), radii
        R = rot if rot is not None else Matrix.Identity(3)
        i0 = len(self.v)
        self.v.append(tuple(c + R @ Vector((0, 0, -rz))))
        for i in range(1, rings):
            ph = -math.pi / 2 + math.pi * i / rings
            for k in range(seg):
                t = 2 * math.pi * k / seg
                p = Vector((rx * math.cos(ph) * math.cos(t), ry * math.cos(ph) * math.sin(t), rz * math.sin(ph)))
                self.v.append(tuple(c + R @ p))
        self.v.append(tuple(c + R @ Vector((0, 0, rz))))
        top = len(self.v) - 1
        for k in range(seg):
            k2 = (k + 1) % seg
            self.f.append([i0, i0 + 1 + k2, i0 + 1 + k])
            for i in range(rings - 2):
                a = i0 + 1 + i * seg
                self.f.append([a + k, a + k2, a + seg + k2, a + seg + k])
            a = i0 + 1 + (rings - 2) * seg
            self.f.append([a + k, a + k2, top])

    def torus(self, c, R, r, seg=24, rseg=8, axis='z'):
        cx, cy, cz = c
        i0 = len(self.v)
        for k in range(seg):
            t = 2 * math.pi * k / seg
            for j in range(rseg):
                p = 2 * math.pi * j / rseg
                rr, hh = R + r * math.cos(p), r * math.sin(p)
                x, y, z = rr * math.cos(t), rr * math.sin(t), hh
                if axis == 'y':
                    y, z = z, y
                elif axis == 'x':
                    x, z = z, x
                self.v.append((cx + x, cy + y, cz + z))
        for k in range(seg):
            for j in range(rseg):
                a, b = i0 + k * rseg + j, i0 + k * rseg + (j + 1) % rseg
                c2, d = i0 + ((k + 1) % seg) * rseg + (j + 1) % rseg, i0 + ((k + 1) % seg) * rseg + j
                self.f.append([a, b, c2, d])

    def surface(self, fn, nu, nv):
        """Open grid surface; fn(u, v) -> point, u, v in 0..1. Give it thickness with solidify."""
        i0 = len(self.v)
        for j in range(nv):
            for i in range(nu):
                self.v.append(tuple(fn(i / (nu - 1), j / (nv - 1))))
        for j in range(nv - 1):
            for i in range(nu - 1):
                a = i0 + j * nu + i
                self.f.append([a, a + 1, a + nu + 1, a + nu])

    # -------------------------------------------------------------- output
    def build(self, name, collection, rgb, bevel=0.0, segments=2, solidify=0.0, parent=None, smooth=False):
        if not self.v:
            return None
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        if smooth:
            for p in me.polygons:
                p.use_smooth = True
        o = bpy.data.objects.new(name, me)
        collection.objects.link(o)
        o.color = (*rgb, 1.0)
        if solidify:
            m = o.modifiers.new("Solidify", 'SOLIDIFY')
            m.thickness, m.offset = solidify, 0.0
        if bevel:
            m = o.modifiers.new("Bevel", 'BEVEL')
            m.width, m.segments, m.limit_method, m.angle_limit = bevel, segments, 'ANGLE', math.radians(40)
            if smooth:
                m.harden_normals = True          # smooth rounded edges, flat faces stay flat
        if parent is not None:
            o.parent = parent
        return o


class Asset:
    """One furniture piece: an empty at (loc, rz) plus one child mesh per material key."""

    def __init__(self, name, collection, palette, loc=(0, 0, 0), rz=0.0):
        self.name, self.col, self.pal = name, collection, palette
        self.loc, self.rz = loc, rz
        self.parts = {}
        self.opts = {}

    def m(self, key, bevel=0.0, segments=2, solidify=0.0, smooth=False):
        if key not in self.parts:
            self.parts[key] = Mesh()
            self.opts[key] = dict(bevel=bevel, segments=segments, solidify=solidify, smooth=smooth)
        return self.parts[key]

    def build(self):
        e = bpy.data.objects.new(self.name, None)
        e.empty_display_type, e.empty_display_size = 'PLAIN_AXES', 0.15
        self.col.objects.link(e)
        e.location, e.rotation_euler = self.loc, (0, 0, self.rz)
        for key, mesh in self.parts.items():
            mesh.build(f"{self.name} - {key}", self.col, self.pal[key], parent=e, **self.opts[key])
        return e
