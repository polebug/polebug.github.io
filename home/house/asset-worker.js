const CACHE = 'polebug-house-assets-v1';
self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  const assets = new URL('assets/', self.registration.scope);
  // HTML, scripts, and scene.json always retain their normal update behavior.
  if (event.request.method !== 'GET' || url.origin !== assets.origin || !url.pathname.startsWith(assets.pathname) || !url.searchParams.has('v')) return;
  event.respondWith((async () => {
    let cache;
    try {
      cache = await caches.open(CACHE);
      const saved = await cache.match(event.request);
      if (saved) return saved;
    } catch { /* Storage unavailable: use the network. */ }
    const response = await fetch(event.request);
    if (cache && response.ok) {
      // Await persistence so a completed load is immediately detectable on reload.
      try { await cache.put(event.request, response.clone()); } catch { /* Quota: still display the network response. */ }
    }
    return response;
  })());
});
