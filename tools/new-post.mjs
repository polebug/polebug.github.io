// npm run new <slug> ["Title"]  →  blog/drafts/<slug>/index.md (drafts stay on this computer)
// When it is ready, move the folder to blog/posts/, run `npm run upload`, then commit and push.
import fs from 'node:fs';
import path from 'node:path';
import { DRAFTS_DIR, POSTS_DIR } from '../blog/lib/media.mjs';

const [slug, title = slug] = process.argv.slice(2);
if (!slug || !/^[\p{L}\p{N}_-]+$/u.test(slug)) {
  console.error('Usage: npm run new <slug> ["Title"]   (slug: letters, numbers, - and _; it becomes the URL)');
  process.exit(1);
}
if (fs.existsSync(path.join(POSTS_DIR, slug)) || fs.existsSync(path.join(DRAFTS_DIR, slug))) {
  console.error(`"${slug}" already exists`);
  process.exit(1);
}
const now = new Date(Date.now() + 8 * 3600_000).toISOString().slice(0, 16).replace('T', ' ');
const dir = path.join(DRAFTS_DIR, slug);
fs.mkdirSync(dir, { recursive: true });
fs.writeFileSync(path.join(dir, 'index.md'), `---\ntitle: ${title}\ndate: ${now}\ndesc:\n---\n\n`);
console.log(`Created blog/drafts/${slug}/index.md — put its images and videos in the same folder.`);
