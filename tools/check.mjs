// npm run check                 build the blog as production does, then verify it
// npm run check -- --local-media  use the processed files in blog/.media-cache instead of R2 (before uploading)
// npm run check -- --serve        keep the built site running on http://localhost:4400 to look at
//
// Verifies: every image and video in every post loads, every internal link and asset exists,
// and every URL of the old Hexo site (tools/legacy-urls.txt) still exists.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { serveStatic } from './serve-static.mjs';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const BLOG = path.join(ROOT, 'blog');
const DIST = path.join(BLOG, 'dist');
const PORT = 4400;
const localMedia = process.argv.includes('--local-media');
const keepServing = process.argv.includes('--serve');
const mediaBase = localMedia ? `http://localhost:${PORT}/__media` : process.env.MEDIA_BASE_URL || 'https://img.polebug.com';

console.log(`Building blog (media from ${mediaBase}) …`);
try {
  execFileSync('npx', ['astro', 'build', '--force'], { cwd: BLOG, stdio: ['ignore', 'ignore', 'inherit'], env: { ...process.env, MEDIA_BASE_URL: mediaBase } });
} catch {
  console.error('\n✗ Build failed (see above).');
  process.exit(1);
}

const server = await serveStatic({
  mounts: [
    { prefix: '/', dir: DIST },
    ...(localMedia ? [{ prefix: '/__media/', dir: path.join(BLOG, '.media-cache') }] : []),
  ],
  port: PORT,
  host: '127.0.0.1',
});

function walk(dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    e.isDirectory() ? walk(p, out) : out.push(p);
  }
  return out;
}

function existsInDist(pathname) {
  let p = path.join(DIST, decodeURIComponent(pathname));
  if (pathname.endsWith('/')) p = path.join(p, 'index.html');
  return fs.existsSync(p) && fs.statSync(p).isFile() || fs.existsSync(path.join(p, 'index.html'));
}

const mediaChecks = new Map(); // url -> Promise<string|null error>
async function checkMedia(url, kind) {
  if (!mediaChecks.has(url)) {
    mediaChecks.set(url, (async () => {
      try {
        const r = await fetch(url, { headers: { Range: 'bytes=0-1023' } });
        if (r.status !== 200 && r.status !== 206) return `HTTP ${r.status}`;
        const type = r.headers.get('content-type') || '';
        if (!type.startsWith(kind === 'video' ? 'video/' : 'image/')) return `unexpected type ${type}`;
        await r.arrayBuffer();
        return null;
      } catch (e) {
        return e.cause?.code || e.message;
      }
    })());
  }
  return mediaChecks.get(url);
}

const pages = walk(DIST).filter((f) => f.endsWith('.html'));
const broken = [];
const rows = [];
for (const file of pages) {
  const pageUrl = '/' + path.relative(DIST, file).replace(/index\.html$/, '');
  const html = fs.readFileSync(file, 'utf8');
  const prose = html.match(/<div class="prose"[^>]*>([\s\S]*?)<\/div>\s*<\/article>/)?.[1];
  let images = 0, videos = 0, failed = 0;

  for (const m of html.matchAll(/<(img|video|source|a|link|script)\b[^>]*>/gi)) {
    const tag = m[1].toLowerCase();
    for (const a of m[0].matchAll(/\b(src|href|poster)="([^"]*)"/gi)) {
      const attr = a[1].toLowerCase();
      const raw = a[2].replace(/&amp;/g, '&');
      if (!raw || raw.startsWith('#') || /^(mailto|javascript|data):/i.test(raw)) continue;
      const url = new URL(raw, `http://localhost:${PORT}${encodeURI(pageUrl)}`);
      const inPost = prose?.includes(a[0]);
      const isMedia = (tag === 'img' || tag === 'video' || tag === 'source') && attr !== 'href';
      if (isMedia && raw.startsWith(mediaBase)) {
        const kind = tag === 'img' || attr === 'poster' ? 'image' : 'video';
        const err = await checkMedia(url.href, kind);
        if (inPost) attr === 'poster' ? 0 : kind === 'image' ? images++ : videos++;
        if (err) { failed++; broken.push(`${pageUrl}  ${kind} ${raw}  → ${err}`); }
      } else if (url.host === `localhost:${PORT}`) {
        if (!existsInDist(url.pathname)) { failed++; broken.push(`${pageUrl}  ${tag} ${attr}=${raw}  → missing`); }
      } else if (isMedia && inPost) {
        // Post media must come from R2; anything else (a stray relative path, another host) is reported.
        broken.push(`${pageUrl}  ${tag} ${raw}  → not served from ${mediaBase}`);
        failed++;
      }
    }
  }
  if (prose !== undefined) rows.push({ pageUrl, images, videos, failed });
}

const legacy = fs.readFileSync(path.join(ROOT, 'tools/legacy-urls.txt'), 'utf8').split('\n').filter(Boolean);
const legacyMissing = legacy.filter((u) => !existsInDist(u));

console.log('\nPosts');
for (const r of rows.sort((a, b) => a.pageUrl.localeCompare(b.pageUrl))) {
  console.log(`  ${r.failed ? '✗' : '✓'} ${decodeURI(r.pageUrl).padEnd(52)} ${String(r.images).padStart(3)} images  ${r.videos} videos${r.failed ? `  ${r.failed} broken` : ''}`);
}
const totalImages = rows.reduce((n, r) => n + r.images, 0);
const totalVideos = rows.reduce((n, r) => n + r.videos, 0);
console.log(`\n${pages.length} pages, ${rows.length} posts, ${totalImages} images, ${totalVideos} videos checked.`);
console.log(`Old Hexo URLs: ${legacy.length - legacyMissing.length}/${legacy.length} present.`);
for (const u of legacyMissing) broken.push(`old URL ${decodeURI(u)} → missing`);

if (broken.length) {
  console.log(`\n✗ ${broken.length} problem(s):\n  ${broken.map(decodeURI).join('\n  ')}`);
} else {
  console.log('\n✓ Everything loads.');
}
if (keepServing) {
  console.log(`\nServing the built site on http://localhost:${PORT}/ (Ctrl+C to stop)`);
} else {
  server.close();
  process.exit(broken.length ? 1 : 0);
}
