// Count this view (stats/, the visitor counter) and fill in the site's figures. Without an answer
// they stay hidden. Same as the blog's (blog/src/layouts/Base.astro).
(() => {
  const stats = location.hostname.endsWith('polebug.com') ? 'https://stats.polebug.com' : `http://${location.hostname}:8787`;
  fetch(`${stats}/hit`, { method: 'POST', body: JSON.stringify({ site: 'home', path: location.pathname }) })
    .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
    .then((n) => {
      const figures = { views: n.views, visitors: n.visitors, 'site-views': n.site.views, 'site-visitors': n.site.visitors };
      document.querySelectorAll('[data-stat]').forEach((el) => {
        const k = figures[el.dataset.stat];
        el.textContent = `${k.toLocaleString('en')} ${el.dataset.unit}${k === 1 ? '' : 's'}`;
      });
      document.querySelectorAll('[data-stats]').forEach((el) => { el.hidden = false; });
    })
    .catch(() => {});
})();
