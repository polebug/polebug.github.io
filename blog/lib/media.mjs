// Post media: images and videos sit next to each post's index.md on this computer,
// get processed and uploaded to R2 by tools/media.mjs, and are looked up in media.json at build time.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFile, execFileSync } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { promisify } from 'node:util';
import { visit } from 'unist-util-visit';
import rehypeRaw from 'rehype-raw';

export const BLOG_DIR = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
export const POSTS_DIR = path.join(BLOG_DIR, 'posts');
export const DRAFTS_DIR = path.join(BLOG_DIR, 'drafts');
export const MANIFEST_PATH = path.join(BLOG_DIR, 'media.json');
export const CACHE_DIR = path.join(BLOG_DIR, '.media-cache');
export const DEFAULT_MEDIA_BASE = 'https://img.polebug.com';

const IMAGE_EXT = new Set(['.jpg', '.jpeg', '.png', '.webp', '.gif', '.heic', '.heif', '.avif', '.tif', '.tiff']);
const VIDEO_EXT = new Set(['.mov', '.mp4', '.m4v', '.webm', '.avi', '.mkv']);

export function mediaKind(file) {
  const ext = path.extname(file).toLowerCase();
  if (IMAGE_EXT.has(ext)) return 'image';
  if (VIDEO_EXT.has(ext)) return 'video';
  return null;
}

// "IMG_1.jpg", "./a b.png" and "a%20b.png" are post media; URLs, /paths, #anchors and data: are not.
export function postRelativeFile(src) {
  if (!src || /^(?:[a-z][a-z0-9+.-]*:|\/|#)/i.test(src)) return null;
  let file = src.replace(/^\.\//, '').split(/[?#]/)[0];
  try { file = decodeURIComponent(file); } catch {}
  return file.includes('..') ? null : file;
}

export function readManifest() {
  try { return JSON.parse(fs.readFileSync(MANIFEST_PATH, 'utf8')); } catch { return {}; }
}

export function mediaUrl(base, key) {
  return `${base.replace(/\/$/, '')}/${key.split('/').map(encodeURIComponent).join('/')}`;
}

// Which post a markdown file belongs to: blog/posts/<slug>/index.md or blog/drafts/<slug>/index.md
function postOf(filePath) {
  if (!filePath) return null;
  const dir = path.dirname(filePath);
  const root = path.dirname(dir);
  if (root !== POSTS_DIR && root !== DRAFTS_DIR) return null;
  return { slug: path.basename(dir), dir, draft: root === DRAFTS_DIR };
}

/**
 * Resolves the media references of every post.
 * dev: the file on this computer when it is there (served at /__local-media/ below), otherwise the uploaded copy.
 * build: always the uploaded copy; a file that was never uploaded fails the build.
 */
const LOCAL_PREFIX = '/__local-media/';
const LOCAL_TYPES = {
  '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp', '.gif': 'image/gif',
  '.avif': 'image/avif', '.heic': 'image/heic', '.heif': 'image/heif', '.tif': 'image/tiff', '.tiff': 'image/tiff',
  '.mp4': 'video/mp4', '.m4v': 'video/mp4', '.mov': 'video/mp4', '.webm': 'video/webm',
};

const run = promisify(execFile);
const previewConversions = new Map();

async function previewHeic(local) {
  const stat = fs.statSync(local);
  // Replacing or editing a photo must invalidate its preview, even with the same filename.
  const key = createHash('sha256').update(JSON.stringify([local, stat.size, stat.mtimeMs, stat.ctimeMs])).digest('hex');
  const out = path.join(CACHE_DIR, '.preview', `${key}.jpg`);
  if (fs.existsSync(out)) return out;
  if (!previewConversions.has(key)) {
    const conversion = (async () => {
      fs.mkdirSync(path.dirname(out), { recursive: true });
      const tmp = `${out}.${randomUUID()}.jpg`;
      try {
        await run('sips', ['-s', 'format', 'jpeg', local, '--out', tmp]);
        fs.renameSync(tmp, out);
        return out;
      } finally {
        fs.rmSync(tmp, { force: true });
      }
    })().finally(() => previewConversions.delete(key));
    previewConversions.set(key, conversion);
  }
  return previewConversions.get(key);
}

async function serveLocalMedia(req, res, next) {
  if (!req.url?.startsWith(LOCAL_PREFIX)) return next();
  let parts;
  try { parts = req.url.slice(LOCAL_PREFIX.length).split('?')[0].split('/').map(decodeURIComponent); } catch { parts = []; }
  const [group, slug, file] = parts;
  const root = { posts: POSTS_DIR, drafts: DRAFTS_DIR, cache: CACHE_DIR }[group];
  if (!root || parts.length !== 3 || [slug, file].some((p) => !p || p.includes('/') || p === '..')) {
    res.statusCode = 404;
    return res.end();
  }
  let local = path.join(root, slug, file);
  if (!fs.existsSync(local)) {
    res.statusCode = 404;
    return res.end();
  }
  const heic = /\.(heic|heif)$/i.test(file);
  if (heic) {
    try {
      local = await previewHeic(local);
    } catch (error) {
      return next(new Error(`Could not convert HEIC preview for ${file}: ${error.message}`));
    }
  }
  const size = fs.statSync(local).size;
  // .mov from a phone is H.264/HEVC in a QuickTime box; browsers play it when told it is MP4.
  const type = heic ? 'image/jpeg' : LOCAL_TYPES[path.extname(file).toLowerCase()] || 'application/octet-stream';
  const range = req.headers.range?.match(/bytes=(\d*)-(\d*)/);
  res.setHeader('Content-Type', type);
  res.setHeader('Accept-Ranges', 'bytes');
  res.setHeader('Cache-Control', 'no-cache');
  if (range) {
    const start = range[1] ? Number(range[1]) : size - Number(range[2]);
    const end = range[1] && range[2] ? Math.min(Number(range[2]), size - 1) : size - 1;
    res.statusCode = 206;
    res.setHeader('Content-Range', `bytes ${start}-${end}/${size}`);
    res.setHeader('Content-Length', end - start + 1);
    return fs.createReadStream(local, { start, end }).pipe(res);
  }
  res.setHeader('Content-Length', size);
  fs.createReadStream(local).pipe(res);
}

const videoDimensions = new Map();
const failedPosters = new Set();
let hdrFfmpeg;
let nativePosterTool;

function applePosterEncoder() {
  if (nativePosterTool) return nativePosterTool;
  const source = path.join(BLOG_DIR, '..', 'tools', 'video-poster.swift');
  const version = createHash('sha256').update(fs.readFileSync(source)).digest('hex').slice(0, 16);
  const dir = path.join(CACHE_DIR, '.tools');
  const binary = path.join(dir, `video-poster-${version}`);
  if (!fs.existsSync(binary)) {
    fs.mkdirSync(dir, { recursive: true });
    const tmp = `${binary}.${randomUUID()}`;
    try {
      execFileSync('/usr/bin/xcrun', ['swiftc', '-O', '-parse-as-library', '-module-cache-path',
        path.join(dir, 'swift-module-cache'), source, '-o', tmp],
        { timeout: 60000, stdio: ['ignore', 'pipe', 'pipe'] });
      fs.renameSync(tmp, binary);
    } finally {
      fs.rmSync(tmp, { force: true });
    }
  }
  return (nativePosterTool = binary);
}

function hdrPosterEncoder() {
  if (hdrFfmpeg) return hdrFfmpeg;
  for (const candidate of [process.env.FFMPEG_PATH || 'ffmpeg', '/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg', '/usr/local/opt/ffmpeg-full/bin/ffmpeg']) {
    try {
      const filters = execFileSync(candidate, ['-hide_banner', '-filters'], { encoding: 'utf8', timeout: 5000, stdio: ['ignore', 'pipe', 'pipe'] });
      if (/\bzscale\b/.test(filters) && /\btonemap\b/.test(filters)) return (hdrFfmpeg = candidate);
    } catch { /* Try the next installed encoder. */ }
  }
  throw new Error('HDR covers need ffmpeg with zscale and tonemap (brew install ffmpeg-full).');
}

function localVideoPoster(local) {
  const stat = fs.statSync(local);
  const key = createHash('sha256').update(JSON.stringify(['poster-native-v3', process.platform, local, stat.size, stat.mtimeMs, stat.ctimeMs])).digest('hex');
  const name = `${key}.poster.jpg`;
  const out = path.join(CACHE_DIR, '.preview', name);
  if (!fs.existsSync(out)) {
    if (failedPosters.has(key)) return;
    fs.mkdirSync(path.dirname(out), { recursive: true });
    const tmp = `${out}.${randomUUID()}.jpg`;
    try {
      const metadata = JSON.parse(execFileSync('ffprobe', [
        '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=color_transfer', '-of', 'json', local,
      ], { encoding: 'utf8', timeout: 5000, stdio: ['ignore', 'pipe', 'pipe'] }));
      const hdr = ['arib-std-b67', 'smpte2084'].includes(metadata.streams?.[0]?.color_transfer);
      if (hdr && process.platform === 'darwin') {
        execFileSync(applePosterEncoder(), [local, tmp], { timeout: 15000, stdio: ['ignore', 'pipe', 'pipe'] });
      } else {
        const filters = ["thumbnail=30", "scale=w='min(1280,iw)':h=-2"];
        if (hdr) {
          // Tone mapping requires linear-light float RGB. Convert BT.2020 primaries as well as
          // HLG/PQ transfer; write sRGB with the full-range BT.601 matrix expected by JPEG decoders.
          filters.push('zscale=t=linear:npl=100', 'format=gbrpf32le', 'zscale=p=bt709',
            'tonemap=hable:desat=0', 'zscale=t=iec61966-2-1:m=170m:r=full', 'format=yuvj420p');
        }
        // Choose a representative frame from the opening frames instead of a possibly black first frame.
        // ffmpeg also applies the phone's rotation metadata before scaling.
        execFileSync(hdr ? hdrPosterEncoder() : 'ffmpeg', [
          '-nostdin', '-y', '-v', 'error', '-i', local, '-map', '0:v:0',
          '-vf', filters.join(','), '-frames:v', '1',
          '-q:v', '3', '-update', '1', tmp,
        ], { timeout: 15000, stdio: ['ignore', 'pipe', 'pipe'] });
      }
      fs.renameSync(tmp, out);
    } catch (error) {
      failedPosters.add(key);
      console.warn(`[post-media] Cannot create video cover for ${path.basename(local)}: ${error.message}`);
      return;
    } finally {
      fs.rmSync(tmp, { force: true });
    }
  }
  return `${LOCAL_PREFIX}cache/.preview/${name}`;
}

function localVideoDimensions(local) {
  const stat = fs.statSync(local);
  const signature = `${stat.size}:${stat.mtimeMs}:${stat.ctimeMs}`;
  const cached = videoDimensions.get(local);
  if (cached?.signature === signature) return cached.dimensions;
  let dimensions = {};
  try {
    const metadata = JSON.parse(execFileSync('ffprobe', [
      '-v', 'error', '-select_streams', 'v:0',
      '-show_entries', 'stream=width,height:stream_tags=rotate:stream_side_data=rotation',
      '-of', 'json', local,
    ], { encoding: 'utf8', timeout: 5000, stdio: ['ignore', 'pipe', 'pipe'] }));
    const stream = metadata.streams?.[0];
    if (stream?.width > 0 && stream?.height > 0) {
      const rotation = Number(stream.side_data_list?.find(item => item.rotation != null)?.rotation ?? stream.tags?.rotate ?? 0);
      const sideways = Math.abs(rotation % 180) === 90;
      dimensions = { width: sideways ? stream.height : stream.width, height: sideways ? stream.width : stream.height };
    }
  } catch {
    console.warn(`[post-media] Cannot read video dimensions for ${path.basename(local)}. Local video previews need ffprobe (brew install ffmpeg).`);
  }
  videoDimensions.set(local, { signature, dimensions });
  return dimensions;
}

export function createMediaPlugins({ dev, base = process.env.MEDIA_BASE_URL || DEFAULT_MEDIA_BASE }) {
  let manifest = readManifest();
  const missing = new Set();

  function resolve(post, src, file) {
    const local = path.join(post.dir, file);
    if (dev) {
      manifest = readManifest();
      // Videos: play the processed H.264 copy when there is one. Camera and phone originals are
      // often HEVC 10-bit, which browsers cannot play.
      const done = manifest[`${post.slug}/${file}`];
      if (mediaKind(file) === 'video' && done && fs.existsSync(path.join(CACHE_DIR, done.key))) {
        const cached = (key) => `${LOCAL_PREFIX}cache/${key.split('/').map(encodeURIComponent).join('/')}`;
        const variants = Object.fromEntries(Object.entries(done.variants || {}).filter(([, k]) => fs.existsSync(path.join(CACHE_DIR, k))).map(([h, k]) => [h, cached(k)]));
        return { src: cached(done.key), poster: done.poster && cached(done.poster), variants, width: done.width, height: done.height, processed: true };
      }
      if (fs.existsSync(local)) {
        const group = post.draft ? 'drafts' : 'posts';
        const dimensions = mediaKind(file) === 'video' ? localVideoDimensions(local) : { width: done?.width, height: done?.height };
        return { src: `${LOCAL_PREFIX}${group}/${encodeURIComponent(post.slug)}/${encodeURIComponent(file)}`, ...dimensions };
      }
    }
    const entry = manifest[`${post.slug}/${file}`];
    if (entry) {
      return {
        src: mediaUrl(base, entry.key),
        poster: entry.poster && mediaUrl(base, entry.poster),
        variants: Object.fromEntries(Object.entries(entry.variants || {}).map(([h, k]) => [h, mediaUrl(base, k)])),
        width: entry.width,
        height: entry.height,
      };
    }
    // Astro would swallow an error thrown here and publish the post empty, so collect and fail at the end.
    if (!dev && !post.draft) missing.add(`${post.slug}/${file}`); // drafts are never published
    return { src, missing: true };
  }

  function remarkMedia() {
    return (tree, vfile) => {
      const post = postOf(vfile.path);
      if (!post) return;
      visit(tree, 'image', (node) => {
        const file = postRelativeFile(node.url);
        if (file && mediaKind(file)) {
          const r = resolve(post, node.url, file);
          node.url = r.src;
          if (r.width && r.height) {
            node.data ??= {};
            node.data.hProperties = { ...node.data.hProperties, width: r.width, height: r.height, loading: 'lazy', decoding: 'async' };
          }
        }
      });
    };
  }

  function rehypeMedia() {
    // Posts are written with raw <img>/<video> HTML; parse it now so it can be rewritten below.
    const raw = rehypeRaw();
    return (tree, vfile) => {
      const post = postOf(vfile.path);
      tree = raw(tree, vfile) || tree;
      if (!post) return tree;
      visit(tree, 'element', (node, index, parent) => {
        const p = node.properties || {};
        // A Markdown line followed by a photo is one paragraph. Inline image line boxes,
        // together with widow/orphan rules, can otherwise consume two nearly empty columns.
        if (node.tagName === 'p') {
          const photos = node.children.filter(child => child.type === 'element' && child.tagName === 'img');
          if (photos.length === 1) {
            const photo = photos[0];
            const at = node.children.indexOf(photo);
            const trailing = node.children.slice(at + 1);
            if (trailing.every(child => child.type === 'text' && !child.value.trim())) {
              const caption = node.children.slice(0, at);
              const hasCaption = caption.some(child => child.type !== 'text' || child.value.trim());
              node.tagName = 'figure';
              node.properties = { ...p, className: [...(p.className || []), 'media-figure'] };
              node.children = hasCaption
                ? [{ type: 'element', tagName: 'figcaption', properties: {}, children: caption }, photo]
                : [photo];
            }
          }
        }
        if (node.tagName === 'img') {
          const file = postRelativeFile(p.src);
          if (!file) return;
          const r = resolve(post, p.src, file);
          p.src = r.src;
          if (r.width && r.height) {
            // Keep the width the post asked for and give it the image's real proportions.
            const w = Number(p.width) || r.width;
            p.width = w;
            p.height = Math.round((w * r.height) / r.width);
          }
          p.loading ??= 'lazy';
          p.decoding ??= 'async';
          if (r.missing) p.dataMissing = '';
        }
        if (node.tagName === 'video') {
          const sources = [node, ...node.children.filter((c) => c.tagName === 'source')];
          for (const el of sources) {
            const file = postRelativeFile(el.properties?.src);
            if (!file) continue;
            const r = resolve(post, el.properties.src, file);
            el.properties.src = r.src;
            // The full copy and its smaller ones, largest first, for the reader's quality menu;
            // 1080p plays unless the viewer picks another.
            if (el === node && r.variants && Object.keys(r.variants).length) {
              const full = Math.min(r.width, r.height);
              const qualities = [[full, r.src], ...Object.entries(r.variants).map(([h, u]) => [Number(h), u]).sort((a, b) => b[0] - a[0])]
                .map(([h, src]) => ({ label: h >= 2160 ? '4K' : `${h}p`, height: h, src }));
              p.src = (qualities.find((q) => q.height === 1080) ?? qualities[0]).src;
              p.dataQualities = JSON.stringify(qualities);
            }
            if (!dev || r.processed || !r.src.startsWith(LOCAL_PREFIX)) {
              if (el.tagName === 'source') el.properties.type = 'video/mp4';
            }
            p.poster ??= r.poster;
            if (!p.poster && dev && mediaKind(file) === 'video') {
              const local = path.join(post.dir, file);
              if (fs.existsSync(local)) p.poster = localVideoPoster(local);
            }
            // Real proportions, so the player has the right shape before the video loads.
            if (r.width && r.height) {
              const w = Number(p.width) || r.width;
              p.width = w;
              p.height = Math.round((w * r.height) / r.width);
            }
          }
          if (p.poster) {
            const file = postRelativeFile(p.poster);
            if (file) p.poster = resolve(post, p.poster, file).src;
          }
          // Nothing until play: even "metadata" let Chrome stream several MB of each video ahead, and
          // polebug.com shares img.polebug.com's connection (same Cloudflare certificate), so on a slow
          // line a post with ten videos held up the next page by up to a minute. The poster shows meanwhile.
          p.preload ??= 'none';
          p.playsInline = true;
          // A frame for the quality button (see Reader.astro); a span, since the video may sit in a <p>.
          if (p.dataQualities && parent && parent.properties?.className?.[0] !== 'vq') {
            parent.children[index] = { type: 'element', tagName: 'span', properties: { className: ['vq'] }, children: [node] };
          }
        }
      });
      return tree;
    };
  }

  // Fails `astro build` when a post refers to media that was never uploaded;
  // in `astro dev` serves the files next to each post (any file name, with Range for video seeking).
  const integration = {
    name: 'post-media',
    hooks: {
      'astro:server:setup': ({ server }) => server.middlewares.use(serveLocalMedia),
      'astro:build:done': () => {
        if (!missing.size) return;
        throw new Error(
          `${missing.size} media file(s) referenced by posts are not in blog/media.json:\n  ${[...missing].join('\n  ')}\n` +
            'Run `npm run upload` (with the files present locally) and commit blog/media.json.',
        );
      },
    },
  };

  return { remarkMedia, rehypeMedia, integration };
}
