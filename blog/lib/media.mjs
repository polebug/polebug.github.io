// Post media: images and videos sit next to each post's index.md on this computer,
// get processed and uploaded to R2 by tools/media.mjs, and are looked up in media.json at build time.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
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

function serveLocalMedia(req, res, next) {
  if (!req.url?.startsWith(LOCAL_PREFIX)) return next();
  let parts;
  try { parts = req.url.slice(LOCAL_PREFIX.length).split('?')[0].split('/').map(decodeURIComponent); } catch { parts = []; }
  const [group, slug, file] = parts;
  const root = { posts: POSTS_DIR, drafts: DRAFTS_DIR, cache: CACHE_DIR }[group];
  if (!root || parts.length !== 3 || [slug, file].some((p) => !p || p.includes('/') || p === '..')) {
    res.statusCode = 404;
    return res.end();
  }
  const local = path.join(root, slug, file);
  if (!fs.existsSync(local)) {
    res.statusCode = 404;
    return res.end();
  }
  const size = fs.statSync(local).size;
  // .mov from a phone is H.264/HEVC in a QuickTime box; browsers play it when told it is MP4.
  const type = LOCAL_TYPES[path.extname(file).toLowerCase()] || 'application/octet-stream';
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
        return { src: cached(done.key), poster: done.poster && cached(done.poster), width: done.width, height: done.height, processed: true };
      }
      if (fs.existsSync(local)) {
        const group = post.draft ? 'drafts' : 'posts';
        return { src: `${LOCAL_PREFIX}${group}/${encodeURIComponent(post.slug)}/${encodeURIComponent(file)}` };
      }
    }
    const entry = manifest[`${post.slug}/${file}`];
    if (entry) {
      return {
        src: mediaUrl(base, entry.key),
        poster: entry.poster && mediaUrl(base, entry.poster),
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
        if (file && mediaKind(file)) node.url = resolve(post, node.url, file).src;
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
      visit(tree, 'element', (node) => {
        const p = node.properties || {};
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
            if (!dev || r.processed || !r.src.startsWith(LOCAL_PREFIX)) {
              if (el.tagName === 'source') el.properties.type = 'video/mp4';
              if (r.poster) p.poster ??= r.poster;
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
          p.preload ??= 'metadata';
          p.playsInline = true;
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
