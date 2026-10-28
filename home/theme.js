// Dark / light scheme, shared with blog.polebug.com: the choice lives in a cookie on polebug.com
// (localStorage is per subdomain), with localStorage as the fallback. Loaded in <head> so the
// scheme is set before the first paint; the house iframe keeps its own look.
(() => {
  const root = document.documentElement;
  const saved = () => {
    const m = document.cookie.match(/(?:^|; )theme=(light|dark)/);
    if (m) return m[1];
    try { return localStorage.getItem('theme'); } catch { return null; }
  };
  if (saved() === 'light') root.dataset.theme = 'light';
  const save = (theme) => {
    const domain = location.hostname.endsWith('polebug.com') ? '; domain=polebug.com' : '';
    document.cookie = `theme=${theme}; path=/; max-age=31536000; samesite=lax${domain}`;
    try { localStorage.setItem('theme', theme); } catch {}
  };
  addEventListener('DOMContentLoaded', () => {
    document.querySelector('.theme-toggle')?.addEventListener('click', () => {
      const theme = root.dataset.theme === 'light' ? 'dark' : 'light';
      root.dataset.theme = theme;
      save(theme);
    });
  });
})();
