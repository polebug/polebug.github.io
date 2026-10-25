// Post media → R2.
//   npm run media    process new or changed images/videos into blog/.media-cache and update blog/media.json
//   npm run upload   the same, then upload what R2 is missing (and the untouched originals to the backup bucket)
// Options: --post <slug> (only that post), --dry-run (report only)
//
// Images become WebP (long edge ≤ 2000px, EXIF and GPS stripped). Videos become H.264 MP4 with
// faststart and a WebP poster, at the source resolution (up to 4K); quality="1080" or quality="720"
// on the tag scales a video down.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import sharp from 'sharp';
import { POSTS_DIR, MANIFEST_PATH, BLOG_DIR, mediaKind, postRelativeFile, readManifest } from '../blog/lib/media.mjs';

const ROOT = path.dirname(BLOG_DIR);
const CACHE = path.join(BLOG_DIR, '.media-cache');
const args = process.argv.slice(2);
const UPLOAD = args.includes('--upload');
const DRY = args.includes('--dry-run');
const ONLY = args.includes('--post') ? args[args.indexOf('--post') + 1] : null;
// Bump when the video settings change: videos are encoded again under new file names
// (R2 copies are cached as immutable, so a changed file must not reuse an old name).
const VIDEO_ENCODING = 'v2';
const WARN_BYTES = 8 * 1024 ** 3;

loadEnv(path.join(ROOT, '.env'));

// ---------- find what each post uses ----------

function references(md) {
  const refs = new Map(); // file -> { quality }
  for (const m of md.matchAll(/<(img|video|source)\b[^>]*>/gi)) {
    const tag = m[0];
    const quality = (tag.match(/\bquality\s*=\s*["']?(\d{3,4})/i) || [])[1] || null;
    for (const a of tag.matchAll(/\b(?:src|poster)\s*=\s*["']([^"']+)["']/gi)) add(a[1], quality);
  }
  // <source> inherits quality from its <video>
  for (const m of md.matchAll(/<video\b[^>]*quality\s*=\s*["']?(\d{3,4})[^>]*>([\s\S]*?)<\/video>/gi)) {
    for (const a of m[2].matchAll(/\bsrc\s*=\s*["']([^"']+)["']/gi)) add(a[1], m[1]);
  }
  for (const m of md.matchAll(/!\[[^\]]*\]\(\s*<?([^)\s>]+)>?/g)) add(m[1], null);
  return refs;

  function add(src, quality) {
    const file = postRelativeFile(src);
    if (!file || !mediaKind(file)) return;
    const prev = refs.get(file);
    refs.set(file, { quality: quality || prev?.quality || null });
  }
}

// ---------- processing ----------

function safeStem(file) {
  const stem = path.basename(file, path.extname(file)).normalize('NFKC');
  return stem.replace(/[^\p{L}\p{N}._-]+/gu, '-').replace(/^[-.]+|[-.]+$/g, '') || 'file';
}

function sha256(file) {
  const h = crypto.createHash('sha256');
  const fd = fs.openSync(file, 'r');
  const buf = Buffer.alloc(1 << 20);
  let n;
  while ((n = fs.readSync(fd, buf, 0, buf.length, null)) > 0) h.update(buf.subarray(0, n));
  fs.closeSync(fd);
  return h.digest('hex');
}

async function processImage(src, outKey) {
  const out = path.join(CACHE, outKey);
  fs.mkdirSync(path.dirname(out), { recursive: true });
  let input = src;
  let tmp;
  if (/\.(heic|heif)$/i.test(src)) {
    // sharp's prebuilt libvips cannot decode HEIC; macOS can.
    tmp = path.join(os.tmpdir(), `${crypto.randomUUID()}.jpg`);
    execFileSync('sips', ['-s', 'format', 'jpeg', src, '--out', tmp], { stdio: 'ignore' });
    input = tmp;
  }
  const info = await sharp(input, { animated: true, limitInputPixels: false })
    .rotate()
    .resize({ width: 2000, height: 2000, fit: 'inside', withoutEnlargement: true })
    .webp({ quality: 82, effort: 5 })
    .toFile(out);
  if (tmp) fs.rmSync(tmp, { force: true });
  return { width: info.width, height: info.pageHeight || info.height, bytes: info.size };
}

function probe(file) {
  const json = execFileSync('ffprobe', ['-v', 'error', '-print_format', 'json', '-show_format', '-show_streams', file], { encoding: 'utf8' });
  const data = JSON.parse(json);
  const v = data.streams.find((s) => s.codec_type === 'video');
  return { duration: Number(data.format.duration) || 0, width: v?.width, height: v?.height };
}

async function processVideo(src, outKey, posterKey, quality) {
  const out = path.join(CACHE, outKey);
  fs.mkdirSync(path.dirname(out), { recursive: true });
  const { duration, width = 1920, height = 1080 } = probe(src);
  const edge = Math.min(Math.max(width, height), 3840, quality ? Math.round((Number(quality) * 16) / 9) : Infinity);
  const maxrate = edge > 2560 ? '20000k' : edge > 1280 ? '6000k' : '3000k';
  execFileSync('ffmpeg', [
    '-y', '-v', 'error', '-i', src,
    '-map', '0:v:0', '-map', '0:a:0?', '-map_metadata', '-1',
    '-vf', `scale='if(gte(iw,ih),min(iw,${edge}),-2)':'if(gte(iw,ih),-2,min(ih,${edge}))'`,
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '21', '-maxrate', maxrate, '-bufsize', `${parseInt(maxrate) * 2}k`,
    '-profile:v', 'high', '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-b:a', '160k',
    '-movflags', '+faststart',
    out,
  ], { stdio: 'inherit' });
  const outInfo = probe(out);
  const posterPng = path.join(os.tmpdir(), `${crypto.randomUUID()}.png`);
  execFileSync('ffmpeg', ['-y', '-v', 'error', '-ss', String(Math.min(1, duration / 2)), '-i', out, '-frames:v', '1', posterPng]);
  const posterOut = path.join(CACHE, posterKey);
  await sharp(posterPng).webp({ quality: 80 }).toFile(posterOut);
  fs.rmSync(posterPng, { force: true });
  return {
    width: outInfo.width,
    height: outInfo.height,
    duration: Math.round(duration),
    profile: `${Math.min(outInfo.width, outInfo.height)}p`,
    bytes: fs.statSync(out).size,
  };
}

// ---------- R2 ----------

const CONTENT_TYPES = {
  '.webp': 'image/webp', '.mp4': 'video/mp4', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
  '.gif': 'image/gif', '.heic': 'image/heic', '.heif': 'image/heif', '.mov': 'video/quicktime', '.webm': 'video/webm',
  '.avif': 'image/avif', '.m4v': 'video/mp4',
};
const contentType = (f) => CONTENT_TYPES[path.extname(f).toLowerCase()] || 'application/octet-stream';

async function r2() {
  const need = ['R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_BUCKET', 'R2_ORIGINALS_BUCKET'];
  const lacking = need.filter((k) => !process.env[k]);
  if (lacking.length) {
    console.error(`\nUpload needs ${lacking.join(', ')} in .env (see .env.example).`);
    process.exit(1);
  }
  const { S3Client, HeadObjectCommand, PutObjectCommand, ListObjectsV2Command } = await import('@aws-sdk/client-s3');
  const client = new S3Client({
    region: 'auto',
    endpoint: `https://${process.env.R2_ACCOUNT_ID}.r2.cloudflarestorage.com`,
    credentials: { accessKeyId: process.env.R2_ACCESS_KEY_ID, secretAccessKey: process.env.R2_SECRET_ACCESS_KEY },
  });
  return {
    async exists(bucket, key) {
      try { await client.send(new HeadObjectCommand({ Bucket: bucket, Key: key })); return true; }
      catch (e) { if (e.$metadata?.httpStatusCode === 404 || e.name === 'NotFound') return false; throw e; }
    },
    async put(bucket, key, file, cacheControl) {
      await client.send(new PutObjectCommand({
        Bucket: bucket, Key: key, Body: fs.createReadStream(file), ContentLength: fs.statSync(file).size,
        ContentType: contentType(key), CacheControl: cacheControl,
      }));
    },
    async usage(bucket) {
      let bytes = 0, count = 0, token;
      do {
        const r = await client.send(new ListObjectsV2Command({ Bucket: bucket, ContinuationToken: token }));
        for (const o of r.Contents || []) { bytes += o.Size; count++; }
        token = r.IsTruncated ? r.NextContinuationToken : undefined;
      } while (token);
      return { bytes, count };
    },
  };
}

async function processFile(slug, file, local, hash, quality) {
  const kind = mediaKind(file);
  const base = `${slug}/${safeStem(file)}-${hash.slice(0, 8)}`;
  process.stdout.write(`  ${kind} ${slug}/${file} … `);
  let entry;
  if (kind === 'image') {
    const key = `${base}.webp`;
    const r = await processImage(local, key);
    entry = { kind, key, width: r.width, height: r.height, bytes: r.bytes, hash, original: file };
  } else {
    const key = `${base}.${VIDEO_ENCODING}.mp4`;
    const poster = `${base}.${VIDEO_ENCODING}.poster.webp`;
    const r = await processVideo(local, key, poster, quality);
    entry = { kind, key, poster, width: r.width, height: r.height, duration: r.duration, profile: r.profile, quality, encoding: VIDEO_ENCODING, bytes: r.bytes, hash, original: file };
  }
  console.log(`${(entry.bytes / 1024 / 1024).toFixed(1)} MB`);
  return entry;
}

// The processed copy may be gone (another computer, cleared cache); it is only rebuilt if R2 lacks it too.
function queue(entry, source) {
  toUpload.push({ key: entry.key, source });
  if (entry.poster) toUpload.push({ key: entry.poster, source });
}

// ---------- main ----------

const manifest = readManifest();
const problems = [];
const report = [];
const toUpload = []; // { key, source } for the public bucket
const originals = []; // { key, file } for the backup bucket: <slug>/<hash>/<original name>

const slugs = fs.readdirSync(POSTS_DIR).filter((d) => fs.existsSync(path.join(POSTS_DIR, d, 'index.md')) && (!ONLY || d === ONLY)).sort();
if (ONLY && !slugs.length) { console.error(`No post "${ONLY}" in blog/posts`); process.exit(1); }

for (const slug of slugs) {
  const dir = path.join(POSTS_DIR, slug);
  const refs = references(fs.readFileSync(path.join(dir, 'index.md'), 'utf8'));
  let processed = 0, kept = 0;
  for (const [file, { quality }] of refs) {
    const id = `${slug}/${file}`;
    const local = path.join(dir, file);
    const entry = manifest[id];
    if (!fs.existsSync(local)) {
      if (entry) { kept++; continue; } // uploaded earlier, original not on this computer
      problems.push(`${id}: referenced but the file is not in blog/posts/${slug}/`);
      continue;
    }
    const hash = sha256(local);
    const fresh = entry && entry.hash === hash && (entry.quality ?? null) === quality
      && (entry.kind !== 'video' || entry.encoding === VIDEO_ENCODING);
    if (!fresh) {
      if (DRY) { report.push(`  would process ${id}`); continue; }
      manifest[id] = await processFile(slug, file, local, hash, quality);
      processed++;
    }
    queue(manifest[id], { slug, file, local, hash, quality });
    originals.push({ key: `${slug}/${hash.slice(0, 8)}/${file}`, file: local });
  }
  const unused = fs.readdirSync(dir).filter((f) => f !== 'index.md' && f !== '.DS_Store' && !refs.has(f));
  if (refs.size || unused.length) {
    report.push(`${slug}: ${refs.size} referenced${processed ? `, ${processed} processed` : ''}${kept ? `, ${kept} already uploaded (no local copy)` : ''}${unused.length ? `, not used by the post (skipped): ${unused.join(', ')}` : ''}`);
  }
}

function writeManifest() {
  const sorted = Object.fromEntries(Object.entries(manifest).sort(([a], [b]) => a.localeCompare(b)));
  fs.writeFileSync(MANIFEST_PATH, JSON.stringify(sorted, null, 2) + '\n');
}
if (!DRY) writeManifest();
console.log('\n' + report.join('\n'));
if (problems.length) console.log(`\nProblems:\n  ${problems.join('\n  ')}`);

if (UPLOAD && !DRY) {
  const store = await r2();
  const pub = process.env.R2_BUCKET;
  const priv = process.env.R2_ORIGINALS_BUCKET;
  let sent = 0, backed = 0;
  for (const { key, source } of toUpload) {
    if (await store.exists(pub, key)) continue;
    const file = path.join(CACHE, key);
    if (!fs.existsSync(file)) manifest[`${source.slug}/${source.file}`] = await processFile(source.slug, source.file, source.local, source.hash, source.quality);
    await store.put(pub, key, file, 'public, max-age=31536000, immutable');
    console.log(`  ↑ ${key}`);
    sent++;
  }
  for (const { key, file } of originals) {
    if (await store.exists(priv, key)) continue;
    await store.put(priv, key, file, 'private, no-store');
    backed++;
  }
  writeManifest();
  const a = await store.usage(pub);
  const b = await store.usage(priv);
  const total = a.bytes + b.bytes;
  console.log(`\nUploaded ${sent} file(s), backed up ${backed} original(s).`);
  console.log(`R2 usage: ${gb(a.bytes)} shown (${a.count} files) + ${gb(b.bytes)} originals (${b.count}) = ${gb(total)} of the 10 GB free tier.`);
  if (total > WARN_BYTES) console.log('⚠️  Close to the 10 GB free tier: beyond it R2 charges about $0.015 per GB per month.');
}
if (problems.length) process.exit(1);
if (!UPLOAD && !DRY) console.log('\nblog/media.json updated. `npm run upload` sends the files to R2.');

function gb(n) { return `${(n / 1024 ** 3).toFixed(2)} GB`; }

function loadEnv(file) {
  if (!fs.existsSync(file)) return;
  for (const line of fs.readFileSync(file, 'utf8').split('\n')) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/);
    if (m && !(m[1] in process.env)) process.env[m[1]] = m[2].replace(/^["']|["']$/g, '');
  }
}
