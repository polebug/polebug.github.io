export const SITE = {
  title: '保持思考、等待、斋戒',
  author: 'Polebug',
  description: "Polebug's blog: notes on life, work and AI.",
  homeUrl: 'https://polebug.com/',
  github: 'https://github.com/polebug',
  // Comments are GitHub issues in this repo, found by md5(location.pathname) as on the old site.
  gitalk: {
    clientID: 'ce0ec393e83b9afdd9b6',
    clientSecret: import.meta.env.PUBLIC_GITALK_CLIENT_SECRET as string | undefined,
    repo: 'polebug.github.io',
    owner: 'polebug',
    admin: ['polebug'],
    proxy: 'https://cors-anywhere.azm.workers.dev/https://github.com/login/oauth/access_token',
  },
};
