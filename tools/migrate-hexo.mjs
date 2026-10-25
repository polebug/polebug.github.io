// One-off: copy the old Hexo blog into this repo.
//   node tools/migrate-hexo.mjs /path/to/hexo-blog
// Posts are copied byte for byte; each post's asset folder (same name as the .md) comes along.
// Posts the old site never published go to blog/drafts/. The old site's URLs are listed in
// tools/legacy-urls.txt so `npm run check` can confirm every one still exists.
import fs from 'node:fs';
import path from 'node:path';

const hexo = path.resolve(process.argv[2] || '');
const postsSrc = path.join(hexo, 'source/_posts');
const publicDir = path.join(hexo, 'public');
if (!fs.existsSync(postsSrc) || !fs.existsSync(publicDir)) {
  console.error('Usage: node tools/migrate-hexo.mjs <hexo dir with source/_posts and public/>');
  process.exit(1);
}
const repo = path.dirname(path.dirname(new URL(import.meta.url).pathname));
const blog = path.join(repo, 'blog');

function walk(dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p, out);
    else out.push(p);
  }
  return out;
}

const oldPages = walk(publicDir)
  .filter((f) => f.endsWith('index.html') || f.endsWith('atom.xml'))
  .map((f) => '/' + path.relative(publicDir, f).replace(/index\.html$/, ''))
  .filter((u) => !u.startsWith('/slides/') || u === '/slides/ai-transition/')
  .sort();

const report = [];
for (const name of fs.readdirSync(postsSrc).filter((f) => f.endsWith('.md')).sort()) {
  const slug = name.slice(0, -3);
  const published = oldPages.some((u) => u.endsWith(`/${slug}/`) && /^\/\d{4}\/\d{2}\/\d{2}\//.test(u));
  const dest = path.join(blog, published ? 'posts' : 'drafts', slug);
  fs.mkdirSync(dest, { recursive: true });
  // Hexo accepts front-matter without the opening "---"; standard markdown tools need it.
  let md = fs.readFileSync(path.join(postsSrc, name), 'utf8');
  if (!md.startsWith('---')) md = `---\n${md}`;
  fs.writeFileSync(path.join(dest, 'index.md'), md);
  let files = 0;
  const assets = path.join(postsSrc, slug);
  if (fs.existsSync(assets)) {
    for (const f of fs.readdirSync(assets)) {
      if (f === '.DS_Store') continue;
      fs.copyFileSync(path.join(assets, f), path.join(dest, f));
      files++;
    }
  }
  report.push(`${published ? 'post ' : 'draft'}  ${slug}  (${files} files)`);
}

// Slide decks are plain static pages.
fs.cpSync(path.join(hexo, 'source/slides'), path.join(blog, 'public/slides'), {
  recursive: true,
  filter: (src) => path.basename(src) !== '.DS_Store',
});

fs.writeFileSync(path.join(repo, 'tools/legacy-urls.txt'), oldPages.join('\n') + '\n');
console.log(report.join('\n'));
console.log(`\n${oldPages.length} old URLs written to tools/legacy-urls.txt`);
const unused = fs.readdirSync(postsSrc).filter((f) => {
  const p = path.join(postsSrc, f);
  return fs.statSync(p).isDirectory() && !fs.existsSync(p + '.md');
});
if (unused.length) console.log(`Asset folders with no post of the same name (left behind): ${unused.join(', ')}`);
