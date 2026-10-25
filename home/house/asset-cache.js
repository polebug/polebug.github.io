const CACHE = 'polebug-house-assets-v1';
const houseFiles = cfg => ['intro.json', 'intro.bin', 'owner.glb', 'house.glb', 'pieces.json', 'linen.webp',
  ...['house', 'floors', 'boards', 'rugs'].map(n => `empty_${n}.webp`),
  cfg.skyFile, cfg.ground.file, cfg.lake?.file, cfg.backdrop?.file,
  cfg.plants.file, cfg.plants.twigsFile, ...Object.values(cfg.trees.types).map(t => t.file)].filter(Boolean);
const fileUrl = (file, version) => new URL('assets/' + file + version, location.href).href;

// Check real cached responses, not a visit flag; a new build naturally gets new keys.
export async function hasCachedHouse(cfg, version) {
  if (!cfg.build || !('serviceWorker' in navigator) || !('caches' in window)) return false;
  try {
    await navigator.serviceWorker.register('./asset-worker.js', { scope: './' });
    if (!navigator.serviceWorker.controller) {
      await new Promise(resolve => {
        const finish = () => { clearTimeout(timer); navigator.serviceWorker.removeEventListener('controllerchange', finish); resolve(); };
        const timer = setTimeout(finish, 3000);
        navigator.serviceWorker.addEventListener('controllerchange', finish);
        if (navigator.serviceWorker.controller) finish();
      });
    }
    if (!navigator.serviceWorker.controller) return false;
    const cache = await caches.open(CACHE);
    const matches = await Promise.all(houseFiles(cfg).map(file => cache.match(fileUrl(file, version))));
    return matches.every(response => response?.ok);
  } catch {
    // Storage restrictions or registration failures must never block the house.
    return false;
  }
}

// The page no longer waits for the worker, so a first visit's early downloads can miss its cache:
// store whatever is missing once the house is in (from the browser's HTTP cache, not the network).
export async function fillHouseCache(cfg, version) {
  if (!cfg.build || !('caches' in window)) return;
  try {
    const cache = await caches.open(CACHE);
    for (const file of houseFiles(cfg)) {
      const url = fileUrl(file, version);
      if (!(await cache.match(url))) await cache.add(url);
    }
  } catch { /* Storage unavailable or quota: the next visit simply builds again. */ }
}
