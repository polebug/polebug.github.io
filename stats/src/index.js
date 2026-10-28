// POST /hit {site: "blog" | "home", path} counts a page view and returns
//   { views, visitors, site: { views, visitors } }
// for that page and for polebug.com + blog.polebug.com together. A view is every load; a visitor
// is counted once a day per page (and once a day for the site), recognised by a salted hash of
// IP and browser that is thrown away after a day. Crawlers get the figures without being counted.
const ORIGINS = /^(https:\/\/(blog\.)?polebug\.com|http:\/\/(localhost|127\.0\.0\.1|\d+\.\d+\.\d+\.\d+):\d+)$/;
const SITES = new Set(['blog', 'home']);
const BOTS = /bot|crawl|spider|slurp|preview|headless|lighthouse|facebookexternalhit|curl|wget|python|httpclient/i;

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin') ?? '';
    if (!ORIGINS.test(origin)) return new Response('Forbidden', { status: 403 });
    const cors = { 'Access-Control-Allow-Origin': origin, Vary: 'Origin' };
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: { ...cors, 'Access-Control-Allow-Methods': 'POST', 'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Max-Age': '86400' } });
    }
    if (request.method !== 'POST' || new URL(request.url).pathname !== '/hit') return new Response('Not found', { status: 404, headers: cors });

    let body;
    try { body = await request.json(); } catch { body = {}; }
    const path = normalise(body.path);
    if (!SITES.has(body.site) || !path) return new Response('Bad request', { status: 400, headers: cors });
    const keys = [`${body.site}:${path}`, 'site'];

    const ua = request.headers.get('User-Agent') ?? '';
    const rows = BOTS.test(ua) ? await read(env.DB, keys) : await count(env, keys, request.headers.get('CF-Connecting-IP') ?? '', ua);
    const [page, site] = keys.map((k) => ({ views: rows.get(k)?.views ?? 0, visitors: rows.get(k)?.visitors ?? 0 }));
    return Response.json({ ...page, site }, { headers: { ...cors, 'Cache-Control': 'no-store' } });
  },

  async scheduled(_event, env) {
    await env.DB.prepare('DELETE FROM seen WHERE day < ?').bind(day(-1)).run();
  },
};

// "/2024/05/01/foo/index.html" → "/2024/05/01/foo/"; anything odd → null.
function normalise(path) {
  if (typeof path !== 'string' || !path.startsWith('/') || path.length > 300) return null;
  try { path = decodeURI(path); } catch { return null; }
  return path.replace(/index\.html$/, '');
}

async function count(env, keys, ip, ua) {
  const today = day(0);
  const visitor = await hash(`${env.SALT ?? ''}|${today}|${ip}|${ua}`);
  const seen = await env.DB.batch(keys.map((k) => env.DB.prepare('INSERT OR IGNORE INTO seen (day, key, visitor) VALUES (?, ?, ?)').bind(today, k, visitor)));
  const results = await env.DB.batch(keys.map((k, i) => env.DB
    .prepare('INSERT INTO counts (key, views, visitors) VALUES (?1, 1, ?2) ON CONFLICT (key) DO UPDATE SET views = views + 1, visitors = visitors + ?2 RETURNING key, views, visitors')
    .bind(k, seen[i].meta.changes > 0 ? 1 : 0)));
  return new Map(results.map((r) => [r.results[0].key, r.results[0]]));
}

async function read(db, keys) {
  const { results } = await db.prepare(`SELECT key, views, visitors FROM counts WHERE key IN (${keys.map(() => '?').join(',')})`).bind(...keys).all();
  return new Map(results.map((r) => [r.key, r]));
}

// UTC date, offset by whole days: "2026-10-28".
function day(offset) {
  return new Date(Date.now() + offset * 86400000).toISOString().slice(0, 10);
}

async function hash(text) {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return [...new Uint8Array(digest).slice(0, 12)].map((b) => b.toString(16).padStart(2, '0')).join('');
}
