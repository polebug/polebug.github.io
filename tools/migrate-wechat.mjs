// One-off: copy WeChat official-account articles into blog posts, with their images and videos.
//   node tools/migrate-wechat.mjs <slug>=<https://mp.weixin.qq.com/s/...> [...]
// Writes blog/posts/<slug>/index.md plus the downloaded media next to it (media stays out of git;
// run `npm run upload` afterwards). Regular articles keep paragraphs, bold, links, quotes, lists,
// images and videos; image posts (小绿书-style) become their images followed by their text.
import fs from 'node:fs';
import path from 'node:path';
import { fromHtml } from 'hast-util-from-html';
import { POSTS_DIR } from '../blog/lib/media.mjs';

const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36';
const jobs = process.argv.slice(2).map((a) => {
  const i = a.indexOf('=');
  return { slug: a.slice(0, i), url: a.slice(i + 1) };
});
if (!jobs.length || jobs.some((j) => !j.slug || !/^https:\/\/mp\.weixin\.qq\.com\/s\//.test(j.url))) {
  console.error('Usage: node tools/migrate-wechat.mjs <slug>=<https://mp.weixin.qq.com/s/...> ...');
  process.exit(1);
}

// ---------- page data ----------

function jsString(s) {
  return s
    .replace(/\\x([0-9a-fA-F]{2})/g, (_, h) => String.fromCharCode(parseInt(h, 16)))
    .replace(/\\u([0-9a-fA-F]{4})/g, (_, h) => String.fromCharCode(parseInt(h, 16)))
    .replace(/\\(['"\\/])/g, '$1')
    .replace(/\\n/g, '\n');
}
function entities(s) {
  return s.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&nbsp;/g, ' ');
}
function field(html, name) {
  const m = html.match(new RegExp(`${name}\\s*[:=]\\s*(?:htmlDecode\\()?'((?:[^'\\\\]|\\\\.)*)'`)) || html.match(new RegExp(`${name}\\s*[:=]\\s*"((?:[^"\\\\]|\\\\.)*)"`));
  return m ? entities(jsString(m[1])) : '';
}
// The bracketed list that starts at `from` (a "[" in the page's inline JS), quotes respected.
function bracketed(html, from) {
  let depth = 0, quote = null;
  for (let i = from; i < html.length; i++) {
    const c = html[i];
    if (quote) { if (c === '\\') i++; else if (c === quote) quote = null; continue; }
    if (c === "'" || c === '"') quote = c;
    else if (c === '[' || c === '{') depth++;
    else if (c === ']' || c === '}') { if (--depth === 0) return html.slice(from, i + 1); }
  }
  return '';
}

function pictureList(html) {
  const at = html.indexOf('picture_page_info_list: [');
  if (at < 0) return [];
  const list = bracketed(html, html.indexOf('[', at));
  // Each picture is "{ cdn_url: '…', width, height, …}"; nested watermark/cover urls are not first in their object.
  return [...list.matchAll(/(?:\[|\},)\s*\{\s*cdn_url:\s*'([^']+)'\s*,\s*width:\s*'(\d+)'/g)].map((m) => ({ url: entities(jsString(m[1])), width: +m[2] }));
}

function videoSources(html) {
  const at = html.indexOf('video_page_infos: [');
  const list = at < 0 ? '' : bracketed(html, html.indexOf('[', at));
  const out = {};
  for (const block of list.split(/video_id:\s*'/).slice(1)) {
    const vid = block.slice(0, block.indexOf("'"));
    let best = null;
    for (const m of block.matchAll(/width:\s*'(\d+)'[\s\S]*?height:\s*'(\d+)'[\s\S]*?url:\s*'([^']+)'/g)) {
      const area = +m[1] * +m[2];
      if (!best || area > best.area) best = { area, url: entities(entities(jsString(m[3]))).replace(/^http:/, 'https:') };
    }
    if (best) out[vid] = best.url;
  }
  return out;
}

// ---------- article HTML → markdown ----------

const BLOCK = new Set(['p', 'section', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'ul', 'ol', 'li', 'figure', 'figcaption', 'hr', 'table', 'pre', 'center']);
const esc = (s) => s.replace(/</g, '&lt;');

function toMarkdown(root, media) {
  const out = [];
  let buf = '';
  const flush = (prefix = '') => {
    const text = buf.replace(/<(strong|em)>\s*<\/\1>/g, '').replace(/(<br>\s*)+$/g, '').replace(/^(\s*<br>)+/g, '').trim();
    if (text) out.push(prefix + text);
    buf = '';
  };
  const style = (el) => String(el.properties?.style || '');
  const isBold = (el) => el.tagName === 'strong' || el.tagName === 'b' || /font-weight:\s*(bold|[6-9]00)/.test(style(el));

  function walk(node, ctx) {
    if (node.type === 'text') { buf += esc(node.value.replace(/ /g, ' ')); return; }
    if (node.type !== 'element') return;
    const tag = node.tagName;
    const p = node.properties || {};
    if (tag === 'script' || tag === 'style' || /display:\s*none/.test(style(node))) return;
    if (tag === 'img') {
      const src = p.dataSrc || p.src;
      if (!src || /res\.wx\.qq\.com/.test(src)) return;
      flush(ctx.prefix);
      const file = media.image(String(src));
      const w = Number(p.dataW) || 0;
      out.push(`${ctx.prefix}<img src="${file}"${w && w < 680 ? ` width="${w}"` : ''} alt="">`);
      return;
    }
    if (tag === 'iframe') {
      const vid = p.dataMpvid;
      if (!vid) return;
      flush(ctx.prefix);
      const file = media.video(String(vid));
      out.push(file ? `${ctx.prefix}<video src="${file}" controls></video>` : `${ctx.prefix}<!-- 视频 ${vid} 未能下载 -->`);
      return;
    }
    if (tag === 'br') { buf += '<br>'; return; }
    if (tag === 'hr') { flush(ctx.prefix); out.push('---'); return; }
    if (BLOCK.has(tag)) {
      flush(ctx.prefix);
      if (/^h[1-6]$/.test(tag)) {
        // The WeChat editor sometimes marks ordinary paragraphs as headings; real ones are short and not sentences.
        node.children.forEach((c) => walk(c, ctx));
        const plain = buf.replace(/<[^>]+>/g, '').trim();
        if (plain.length > 40 || /[。！？；，…~～]$/.test(plain)) { flush(ctx.prefix); return; }
        buf = plain;
        flush(`${ctx.prefix}## `);
        return;
      }
      if (tag === 'blockquote') { const inner = { prefix: `${ctx.prefix}> ` }; node.children.forEach((c) => walk(c, inner)); flush(inner.prefix); return; }
      if (tag === 'ul' || tag === 'ol') {
        let n = 0;
        for (const li of node.children) {
          if (li.type !== 'element') continue;
          n++;
          li.children.forEach((c) => walk(c, { prefix: '' }));
          const marker = tag === 'ol' ? `${n}. ` : '- ';
          const text = buf.replace(/<br>/g, ' ').trim();
          buf = '';
          if (text) out.push(`${ctx.prefix}${marker}${text}`);
        }
        return;
      }
      node.children.forEach((c) => walk(c, ctx));
      flush(ctx.prefix);
      return;
    }
    if (tag === 'a' && p.href && !String(p.href).startsWith('javascript')) {
      buf += `<a href="${String(p.href).replace(/"/g, '&quot;')}">`;
      node.children.forEach((c) => walk(c, ctx));
      buf += '</a>';
      return;
    }
    if (isBold(node)) { buf += '<strong>'; node.children.forEach((c) => walk(c, ctx)); buf += '</strong>'; return; }
    if (tag === 'em' || tag === 'i') { buf += '<em>'; node.children.forEach((c) => walk(c, ctx)); buf += '</em>'; return; }
    node.children.forEach((c) => walk(c, ctx));
  }

  walk(root, { prefix: '' });
  flush();
  // Section titles are often bold paragraphs rather than heading tags: "四月：…" / "Part 1" become ##,
  // numbered items ("1. …", "1️⃣ DAY 1：…") become ### under those (or ## when the post has no larger sections).
  const MAJOR = /^([一二三四五六七八九十]+月|[一二三四五六七八九十]+、|Part\s*\d|Topic)/i;
  const MINOR = /^(\d+[.、]|\d\uFE0F?\u20E3|DAY\s*\d)/i;
  const titles = out.map((block) => {
    const bare = block.replace(/<br>/g, '').replace(/<\/?strong>/g, (t, i) => t);
    const m = bare.match(/^([\d\uFE0F\u20E3]*)\s*((?:<strong>\s*)+)([\s\S]*?)((?:\s*<\/strong>)+)\s*$/);
    if (!m) return null;
    const text = (m[1] + m[3].replace(/<\/?strong>/g, '')).replace(/\s+/g, ' ').trim();
    if (/<|>/.test(text) || text.length > 40 || /[。！？；，~～]$/.test(text)) return null;
    const lead = text.replace(/^[^\p{L}\p{N}]+/u, ''); // "⚙️ 1. …" counts as "1. …"
    if (MAJOR.test(lead)) return { level: 'major', text };
    if (MINOR.test(text) || MINOR.test(lead)) return { level: 'minor', text };
    return null;
  });
  const hasMajor = titles.some((t) => t?.level === 'major');
  titles.forEach((t, i) => {
    if (t) out[i] = `${t.level === 'major' || !hasMajor ? '##' : '###'} ${t.text}`;
  });

  // Merge consecutive list items / quote lines that belong together; separate everything else by a blank line.
  return out.join('\n\n').replace(/<strong>(\s*)<\/strong>/g, '$1').replace(/<\/strong><strong>/g, '') + '\n';
}

// ---------- downloads ----------

async function download(url, dest) {
  const r = await fetch(url, { headers: { 'User-Agent': UA } });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const buf = Buffer.from(await r.arrayBuffer());
  fs.writeFileSync(dest, buf);
  return buf;
}
function sniffExt(buf, fallback) {
  if (buf[0] === 0xff && buf[1] === 0xd8) return '.jpg';
  if (buf[0] === 0x89 && buf[1] === 0x50) return '.png';
  if (buf.slice(0, 3).toString() === 'GIF') return '.gif';
  if (buf.slice(8, 12).toString() === 'WEBP') return '.webp';
  return fallback;
}

// ---------- main ----------

for (const { slug, url } of jobs) {
  const html = await (await fetch(url, { headers: { 'User-Agent': UA } })).text();
  const title = entities((html.match(/<meta property="og:title" content="([^"]*)"/) || [])[1] || '') || field(html, 'msg_title');
  const ct = Number((html.match(/var ct = "(\d+)"/) || html.match(/create_time:\s*'(\d+)'/) || [])[1]);
  const showType = (html.match(/item_show_type:\s*'(\d+)'/) || [])[1];
  if (!title || !ct) { console.log(`✗ ${slug}: could not read title/date (verification page?)`); continue; }
  const dir = path.join(POSTS_DIR, slug);
  fs.mkdirSync(dir, { recursive: true });

  const pending = [];
  const failures = [];
  let imageNo = 0;
  const videos = videoSources(html);
  const media = {
    image(src) {
      const n = String(++imageNo).padStart(2, '0');
      const fmt = (src.match(/wx_fmt=(\w+)/) || [])[1] || 'jpeg';
      const guess = { jpeg: '.jpg', jpg: '.jpg', png: '.png', gif: '.gif', webp: '.webp' }[fmt] || '.jpg';
      const name = `${n}${guess}`;
      const clean = src.replace(/^http:/, 'https:').replace(/&amp;/g, '&');
      pending.push(download(clean, path.join(dir, name)).then((buf) => {
        const ext = sniffExt(buf, guess);
        if (ext !== guess) {
          fs.renameSync(path.join(dir, name), path.join(dir, `${n}${ext}`));
          renames[name] = `${n}${ext}`;
        }
      }).catch((e) => failures.push(`${name} ← ${clean.slice(0, 80)}: ${e.message}`)));
      return name;
    },
    video(vid) {
      const src = videos[vid];
      if (!src) { failures.push(`video ${vid}: no download address on the page`); return null; }
      const name = `${vid}.mp4`;
      pending.push(download(src, path.join(dir, name)).catch((e) => failures.push(`${name}: ${e.message}`)));
      return name;
    },
  };
  const renames = {};

  let body;
  if (showType === '8') {
    const text = field(html, 'content_noencode');
    const pics = pictureList(html).map((p) => `<img src="${media.image(p.url)}" alt="">`);
    const paras = text.split(/\n{1,}/).map((s) => esc(s.trim())).filter(Boolean);
    body = [...pics, ...paras].join('\n\n') + '\n';
  } else {
    const doc = fromHtml(html);
    let content = null;
    (function find(n) { if (content) return; if (n.properties?.id === 'js_content') content = n; (n.children || []).forEach(find); })(doc);
    if (!content) { console.log(`✗ ${slug}: no article body found`); continue; }
    body = toMarkdown(content, media);
  }
  await Promise.all(pending);
  for (const [from, to] of Object.entries(renames)) body = body.replaceAll(`src="${from}"`, `src="${to}"`);

  const date = new Date(ct * 1000 + 8 * 3600_000).toISOString().slice(0, 16).replace('T', ' ');
  const front = `---\ntitle: ${JSON.stringify(title)}\ndate: ${date}\ndesc:\nsource: ${url}\n---\n\n`;
  fs.writeFileSync(path.join(dir, 'index.md'), front + body);
  const vids = (body.match(/<video /g) || []).length;
  console.log(`${failures.length ? '!' : '✓'} ${slug}  ${date}  ${title}\n    ${imageNo} images, ${vids} videos${showType === '8' ? ' (image post)' : ''}`);
  for (const f of failures) console.log(`    ✗ ${f}`);
}
