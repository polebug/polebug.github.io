"""Tileable chunky linen rug (web/house/assets/linen.webp), after the user's photo (10-22): rows of
thick twisted linen cord, the rows parallel to the fringed ends, oat / off-white heather.
Built as a height field and shaded with a soft light from the far side; the page tiles it every
0.24 m and divides by its mean, so the baked light keeps the brightness.
Image y runs across the rows (along the rug's length). Run with any python that has numpy."""
import numpy as np, zlib, struct, sys

N = 512                        # px per 0.24 m tile
ROWS, TWISTS = 20, 18          # 12 mm rows of cord, 13 mm per twist along the row
rng = np.random.default_rng(11)
y, x = np.mgrid[0:N, 0:N].astype(np.float64)

def per_row_noise(n, lo, hi):
    """periodic noise along x, one row per cord"""
    out = np.zeros((n, N))
    for f in range(lo, hi):
        out += rng.normal(0, 1, n)[:, None] / f * np.sin(2 * np.pi * f * np.arange(N)[None] / N + rng.uniform(0, 6.3, n)[:, None])
    return out / out.std()

rp = N / ROWS
r = np.floor(y / rp).astype(int) % ROWS
v = (y / rp) % 1.0                              # across the cord, 0..1
xi = x.astype(int) % N
wob = 0.06 * per_row_noise(ROWS, 1, 6)[r, xi]   # hand-made: rows wander a little
fat = 1 + 0.10 * per_row_noise(ROWS, 1, 10)[r, xi]
d = np.clip(np.abs(v - 0.5 - wob) / (0.47 * fat), 0, 1)
cord = np.sqrt(1 - d * d)                       # round cord across
slant = np.where(r % 2 == 0, 1.0, -1.0)         # alternate rows twist the other way: a knit-like chain
t = x / (N / TWISTS) + slant * (v - 0.5) * 1.9 + rng.uniform(0, 1, ROWS)[r]
strand = 0.5 + 0.5 * np.cos(2 * np.pi * t)      # the plies of the twist
h = cord * (0.62 + 0.38 * strand ** 0.6)
fuzz = np.zeros((N, N))
for f, a in ((128, 0.6), (256, 0.4)):
    fuzz += a * np.kron(rng.normal(0, 1, (f, f)), np.ones((N // f, N // f)))
h = h + 0.025 * fuzz
k = np.array([1, 4, 6, 4, 1], float); k /= k.sum()
for ax in (0, 1):
    h = sum(w * np.roll(h, o - 2, axis=ax) for o, w in enumerate(k))

# shade: normal from the height field, a soft key light from the window side (-y) and above
gy, gx = np.gradient(np.pad(h, 2, mode='wrap'))
gy, gx = gy[2:-2, 2:-2], gx[2:-2, 2:-2]
s = 9.0
nrm = np.dstack([-gx * s, -gy * s, np.ones_like(h)])
nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
L = np.array([0.15, -0.55, 0.82]); L /= np.linalg.norm(L)
diff = np.clip(nrm @ L, 0, 1)
ao = 0.66 + 0.34 * np.clip(h / 0.9, 0, 1)
lum = (0.35 + 0.65 * diff) * ao
tone = 1 + 0.035 * per_row_noise(ROWS, 1, 8)[r, xi] + rng.normal(0, 0.025, ROWS)[r]
lum *= tone
light = np.array([1.0, 0.975, 0.935]); oat = np.array([0.93, 0.885, 0.81])
mixk = np.clip(0.5 + 0.5 * fuzz + 6 * (tone - 1), 0, 1)[..., None]   # heathered yarn: light and oat fibres
rgb = lum[..., None] * (oat + (light - oat) * mixk)
rgb = rgb / rgb.mean() * 0.62                   # the page divides by its mean (0.62 grey)
img = (np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)

def png(path, a):
    raw = b''.join(b'\x00' + a[q].tobytes() for q in range(a.shape[0]))
    ck = lambda t_, d_: struct.pack('>I', len(d_)) + t_ + d_ + struct.pack('>I', zlib.crc32(t_ + d_) & 0xffffffff)
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + ck(b'IHDR', struct.pack('>IIBBBBB', a.shape[1], a.shape[0], 8, 2, 0, 0, 0))
                           + ck(b'IDAT', zlib.compress(raw, 9)) + ck(b'IEND', b''))
png(sys.argv[1], img)
print('mean', (img.reshape(-1, 3).mean(0) / 255).round(3))
