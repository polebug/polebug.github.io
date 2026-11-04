import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url);
export const FONT_ORIGIN = 'https://img.polebug.com';
export const FONT_CACHE_CONTROL = 'public, max-age=31536000, immutable';
export const FONT_MANIFEST = new URL('../fonts.json', import.meta.url);
const sources = ['@fontsource/lato/400.css', '@fontsource/lato/700.css', '@fontsource/noto-serif-sc/400.css'];
let bundle;
export function getFontBundle() {
  if (bundle) return bundle;
  const assets = new Map();
  const styles = sources.map(source => {
    const file = require.resolve(source);
    return fs.readFileSync(file, 'utf8').replace(/src:[^;]+;/g, declaration => {
      const match = declaration.match(/url\(([^)]+\.woff2)\)/);
      if (!match) throw new Error(`Missing WOFF2 source in ${source}`);
      const filename = path.resolve(path.dirname(file), match[1]);
      const bytes = fs.readFileSync(filename);
      const hash = crypto.createHash('sha256').update(bytes).digest('hex').slice(0, 24);
      const key = `fonts/${path.basename(filename, '.woff2')}.${hash}.woff2`;
      const url = `${FONT_ORIGIN}/${key}`;
      assets.set(key, { key, url, filename, bytes: bytes.length });
      return `src: url("${url}") format("woff2");`;
    });
  });
  const css = styles.join('\n');
  const latinCss = styles.slice(0, 2).join('\n');
  const chineseCss = styles[2];
  const preloads = ['lato-latin-400-normal'].map(stem => {
    const asset = [...assets.values()].find(a => path.basename(a.filename) === `${stem}.woff2`);
    if (!asset) throw new Error(`Missing preload: ${stem}`);
    return asset.url;
  });
  return bundle = { css, latinCss, chineseCss, assets: [...assets.values()], preloads };
}
export function fontCdnPlugin() {
  return {
    name: 'blog-font-cdn',
    configureServer(server) {
      server.middlewares.use((req,res,next) => {
        const url = req.url?.split('?')[0] || '';
        if (!url.startsWith('/__font-subsets/')) return next();
        const name = url.slice('/__font-subsets/'.length);
        if (!/^noto-[a-z]+\.[a-f0-9]{24}\.woff2$/.test(name)) { res.statusCode=404; return res.end(); }
        const filename = path.join(FONT_CACHE_DIR,name);
        if (!fs.existsSync(filename)) { res.statusCode=404; return res.end(); }
        res.setHeader('Content-Type','font/woff2');
        res.setHeader('Cache-Control',FONT_CACHE_CONTROL);
        fs.createReadStream(filename).pipe(res);
      });
    },
    buildStart() {
      const published = new Set(JSON.parse(fs.readFileSync(FONT_MANIFEST, 'utf8')).keys);
      const subsets = readSubsetManifest();
      const assets = [...getFontBundle().assets, ...(subsets ? [subsets.shared, ...Object.values(subsets.pages).map(p=>p.font)].filter(Boolean) : [])];
      for (const { key } of assets) {
        if (!published.has(key)) throw new Error('Font files changed. Run npm run fonts:upload before building.');
      }
    },
    resolveId(id) {
      if (id === 'virtual:blog-fonts.css') return '\0blog-fonts.css';
      if (id === 'virtual:blog-font-subsets') return '\0blog-font-subsets';
    },
    load(id) {
      if (id === '\0blog-fonts.css') return getFontBundle().latinCss;
      if (id === '\0blog-font-subsets') return `export default ${JSON.stringify(readSubsetManifest())};`;
    },
  };
}

// Append page subsets after the original faces in the same family: overlapping
// ranges use the last face, so pending subsets do not download fallback webfonts.
// Newly added characters still use the original unicode-range shards.
export const FONT_CACHE_DIR = fileURLToPath(new URL('../.font-cache/', import.meta.url));
export const SUBSET_MANIFEST = new URL('../font-subsets.json', import.meta.url);
export function fontSourceDigest() {
  return crypto.createHash('sha256').update(getFontBundle().assets.map(a=>a.key).join('\n')).digest('hex');
}
export function readSubsetManifest({ pending = false } = {}) {
  const file = pending ? path.join(FONT_CACHE_DIR,'subsets.json') : SUBSET_MANIFEST;
  if (!fs.existsSync(file)) return null;
  const data = JSON.parse(fs.readFileSync(file,'utf8'));
  return data.sourceDigest === fontSourceDigest() ? data : null;
}
export function getPageFontStyles(route, { dev = false, published = null } = {}) {
  const fallback = getFontBundle().chineseCss;
  if (process.env.FONT_SUBSETS_DISABLE === '1') return fallback;
  const local = dev && readSubsetManifest({pending:true});
  const manifest = local || published;
  if (!manifest) return fallback;
  const normalized = route.endsWith('.html') ? route : `${route.replace(/\/$/,'')}/`;
  const fonts = [manifest.shared, manifest.pages[normalized]?.font].filter(Boolean);
  // Exclude covered characters explicitly: browsers must not fetch an original
  // shard while a replacement face is loading, even for synthetic bold text.
  const covered = new Set(fonts.flatMap(font => [...unicodePoints(font.unicodeRange)]));
  const remaining = fallback.replace(/@font-face\s*\{[^}]+\}/g, face => {
    const match = face.match(/unicode-range:\s*([^;]+);/);
    if (!match) return face;
    const stem = face.match(/noto-serif-sc-[a-z0-9-]+(?=\.[a-f0-9]{24}\.woff2)/)?.[0];
    // Fontsource ranges can advertise emoji/combining characters not actually
    // present in their cmap. Skip those faces and let the system render them.
    const range = manifest.fallbackRanges?.[stem] ?? match[1];
    const points = [...unicodePoints(range)].filter(cp => !covered.has(cp));
    return points.length ? face.replace(match[0], `unicode-range:${unicodeRange(points)};`) : '';
  });
  return remaining + '\n' + fonts.map(font => {
    const url = local ? `/__font-subsets/${path.basename(font.key)}` : `${FONT_ORIGIN}/${font.key}`;
    return `@font-face{font-family:"Noto Serif SC";font-style:normal;font-weight:400;font-display:swap;src:url("${url}") format("woff2");unicode-range:${font.unicodeRange}}`;
  }).join('\n');
}

function unicodePoints(range) {
  const points = new Set();
  for (const part of range.split(',').filter(Boolean)) {
    const [start, end = start] = part.trim().replace(/^U\+/i, '').split('-').map(n => parseInt(n,16));
    for (let cp = start; cp <= end; cp++) points.add(cp);
  }
  return points;
}
function unicodeRange(points) {
  const ranges = [];
  for (const cp of points.sort((a,b)=>a-b)) {
    const last = ranges.at(-1);
    if (last && cp === last[1]+1) last[1] = cp;
    else ranges.push([cp,cp]);
  }
  return ranges.map(([a,b])=>a===b ? `U+${a.toString(16)}` : `U+${a.toString(16)}-${b.toString(16)}`).join(',');
}
