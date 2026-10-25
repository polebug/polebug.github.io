// Small static file server for local preview (no dependencies). Used for home/ in `npm run dev`
// and for the built blog in `npm run check`. Supports Range requests so videos can seek.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';

const TYPES = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8', '.json': 'application/json', '.xml': 'application/xml; charset=utf-8',
  '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp',
  '.gif': 'image/gif', '.ico': 'image/x-icon', '.mp4': 'video/mp4', '.mov': 'video/quicktime', '.webm': 'video/webm',
  '.woff2': 'font/woff2', '.woff': 'font/woff', '.ttf': 'font/ttf', '.txt': 'text/plain; charset=utf-8',
  '.glb': 'model/gltf-binary', '.bin': 'application/octet-stream', '.hdr': 'application/octet-stream', '.wasm': 'application/wasm',
};

/**
 * mounts: [{ prefix: '/', dir }] — longest prefix wins.
 * rewriteHtml(html, req): optional, e.g. to point production links at the other local server.
 */
export function serveStatic({ mounts, port, host, rewriteHtml }) {
  mounts = [...mounts].sort((a, b) => b.prefix.length - a.prefix.length);
  const server = http.createServer((req, res) => {
    let pathname;
    try { pathname = decodeURIComponent(new URL(req.url, 'http://x').pathname); } catch { pathname = '/'; }
    const mount = mounts.find((m) => pathname.startsWith(m.prefix));
    if (!mount) return notFound(res);
    let file = path.join(mount.dir, pathname.slice(mount.prefix.length));
    if (!file.startsWith(mount.dir)) return notFound(res);
    if (fs.existsSync(file) && fs.statSync(file).isDirectory()) {
      if (!pathname.endsWith('/')) { res.writeHead(301, { Location: pathname + '/' }); return res.end(); }
      file = path.join(file, 'index.html');
    }
    if (!fs.existsSync(file)) {
      const fallback = path.join(mounts.at(-1).dir, '404.html');
      return fs.existsSync(fallback) ? send(res, fallback, 404) : notFound(res);
    }
    const type = TYPES[path.extname(file).toLowerCase()] || 'application/octet-stream';
    if (type.startsWith('text/html') && rewriteHtml) {
      const html = rewriteHtml(fs.readFileSync(file, 'utf8'), req);
      res.writeHead(200, { 'Content-Type': type, 'Cache-Control': 'no-cache' });
      return res.end(req.method === 'HEAD' ? undefined : html);
    }
    send(res, file, 200, req);
  });
  return new Promise((resolve) => server.listen(port, host, () => resolve(server)));
}

function send(res, file, status, req) {
  const size = fs.statSync(file).size;
  const type = TYPES[path.extname(file).toLowerCase()] || 'application/octet-stream';
  const range = req?.headers.range?.match(/bytes=(\d*)-(\d*)/);
  if (range && status === 200) {
    const start = range[1] ? Number(range[1]) : size - Number(range[2]);
    const end = range[1] && range[2] ? Number(range[2]) : size - 1;
    res.writeHead(206, { 'Content-Type': type, 'Content-Range': `bytes ${start}-${end}/${size}`, 'Content-Length': end - start + 1, 'Accept-Ranges': 'bytes', 'Cache-Control': 'no-cache' });
    if (req.method === 'HEAD') return res.end();
    return fs.createReadStream(file, { start, end }).pipe(res);
  }
  res.writeHead(status, { 'Content-Type': type, 'Content-Length': size, 'Accept-Ranges': 'bytes', 'Cache-Control': 'no-cache' });
  if (req?.method === 'HEAD') return res.end();
  fs.createReadStream(file).pipe(res);
}

function notFound(res) {
  res.writeHead(404, { 'Content-Type': 'text/plain' });
  res.end('Not found');
}
