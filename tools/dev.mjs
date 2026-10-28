// npm run dev            blog on http://localhost:4321, homepage on http://localhost:8000,
//                        visitor counter on http://localhost:8787 (local database in stats/.wrangler)
// npm run dev -- --host  the same, reachable from a phone on the same Wi-Fi
// Links between the two point at the local servers instead of blog.polebug.com / polebug.com.
import { execFileSync, spawn } from 'node:child_process';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { serveStatic } from './serve-static.mjs';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const lan = process.argv.includes('--host');
const host = lan ? '0.0.0.0' : '127.0.0.1';
const BLOG_PORT = 4321;
const HOME_PORT = 8000;
const STATS_PORT = 8787;

await serveStatic({
  mounts: [{ prefix: '/', dir: path.join(ROOT, 'home') }],
  port: HOME_PORT,
  host,
  rewriteHtml: (html, req) => {
    const hostname = (req.headers.host || 'localhost').split(':')[0];
    return html.replaceAll('https://blog.polebug.com/', `http://${hostname}:${BLOG_PORT}/`);
  },
});

// Both servers listen on the same IPv4 address, so links work whether the page was opened as localhost or 127.0.0.1.
const astro = spawn('npx', ['astro', 'dev', '--force', '--port', String(BLOG_PORT), '--host', host], {
  cwd: path.join(ROOT, 'blog'),
  stdio: 'inherit',
});
astro.on('exit', (code) => process.exit(code ?? 0));

// The visitor counter (stats/), on a local copy of its database; pages find it on port 8787 of their own host.
const wrangler = ['--yes', 'wrangler@4.152.0'];
const STATS = path.join(ROOT, 'stats');
execFileSync('npx', [...wrangler, 'd1', 'migrations', 'apply', 'polebug-stats', '--local'], { cwd: STATS, stdio: 'ignore' });
const stats = spawn('npx', [...wrangler, 'dev', '--port', String(STATS_PORT), '--ip', host, '--test-scheduled'], { cwd: STATS, stdio: 'ignore' });

for (const sig of ['SIGINT', 'SIGTERM']) process.on(sig, () => { astro.kill(sig); stats.kill(sig); });

const address = lan ? Object.values(os.networkInterfaces()).flat().find((i) => i?.family === 'IPv4' && !i.internal)?.address : 'localhost';
console.log(`\n  Blog  http://${address}:${BLOG_PORT}/   (drafts included)\n  Home  http://${address}:${HOME_PORT}/\n  Stats http://${address}:${STATS_PORT}/\n`);
