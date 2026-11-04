// Generate subsets from rendered public pages, never drafts or markdown source markup.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fromHtml } from 'hast-util-from-html';
import { toText } from 'hast-util-to-text';
import { getFontBundle, FONT_CACHE_DIR, fontSourceDigest } from '../blog/lib/fonts.mjs';
const root = fileURLToPath(new URL('../', import.meta.url));
const require = createRequire(import.meta.url);
const python = process.env.FONT_PYTHON || 'python3';
try { execFileSync(python, ['-c', 'import fontTools, brotli'], { stdio: 'pipe' }); }
catch { throw new Error('Install tools/fonts/requirements.txt in a Python virtual environment and set FONT_PYTHON to its python executable.'); }
execFileSync('npm', ['run', 'build'], { cwd: root, stdio: 'inherit', env: { ...process.env, FONT_SUBSETS_DISABLE: '1' } });
const dist = path.join(root, 'blog/dist');
function htmlFiles(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap(e => e.isDirectory() ? htmlFiles(path.join(dir,e.name)) : e.name.endsWith('.html') ? [path.join(dir,e.name)] : []);
}
function stripNonText(node) {
  if (!node.children) return;
  node.children = node.children.filter(c => !['script','style','template'].includes(c.tagName));
  node.children.forEach(stripNonText);
}
function uiCharacters(dir) {
  return fs.readdirSync(dir,{withFileTypes:true}).flatMap(entry => {
    const file=path.join(dir,entry.name);
    if(entry.isDirectory()) return uiCharacters(file);
    if(!/\.(astro|ts|js)$/.test(file)) return [];
    // Include runtime UI labels (comments, validation, menus), not just static HTML.
    return fs.readFileSync(file,'utf8').match(/[\p{Script=Han}⌘…]/gu) || [];
  });
}
const uiText = [...new Set(uiCharacters(path.join(root,'blog/src')))].join('');
const pages = htmlFiles(dist).sort().map(file => {
  const tree = fromHtml(fs.readFileSync(file, 'utf8'));
  const body = tree.children.find(e=>e.tagName==='html')?.children.find(e=>e.tagName==='body');
  if (!body) throw new Error(`No body in ${file}`);
  stripNonText(body);
  const relative = path.relative(dist,file).split(path.sep).join('/');
  const route = '/' + relative.replace(/(^|\/)index\.html$/, '$1');
  return { route, text: toText(body), article: /^\/\d{4}\/\d{2}\/\d{2}\//.test(route) };
});
fs.mkdirSync(FONT_CACHE_DIR,{recursive:true});
const input = path.join(FONT_CACHE_DIR,'input.json');
fs.writeFileSync(input, JSON.stringify({ pages, uiText, sourceDigest:fontSourceDigest(), sourceCss:require.resolve('@fontsource/noto-serif-sc/400.css'), lato:require.resolve('@fontsource/lato/files/lato-latin-400-normal.woff2'), output:FONT_CACHE_DIR, commonFile:path.join(root,'blog/font-common.txt'), refreshCommon:process.argv.includes('--refresh-common') }));
execFileSync(python, [path.join(root,'tools/fonts/subset.py'),input], { stdio:'inherit' });
console.log('Local subsets ready. Run npm run fonts:upload before committing the published subset manifest.');
