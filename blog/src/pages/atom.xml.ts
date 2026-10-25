import type { APIRoute } from 'astro';
import { getPosts } from '../lib/posts';
import { SITE } from '../site';

// Atom feed at the same address as the old Hexo feed, so existing subscribers keep receiving posts.
const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

export const GET: APIRoute = async ({ site }) => {
  const posts = (await getPosts()).filter((p) => !p.draft).slice(0, 20);
  const root = site!.toString().replace(/\/$/, '');
  const updated = (posts[0]?.data.date ?? new Date()).toISOString();
  const entries = posts
    .map((p) => {
      const url = root + encodeURI(p.url);
      return `  <entry>
    <title>${esc(p.data.title)}</title>
    <link href="${url}"/>
    <id>${url}</id>
    <published>${p.data.date.toISOString()}</published>
    <updated>${p.data.date.toISOString()}</updated>
    <summary type="html">${esc(p.excerpt)}</summary>
    <content type="html">${esc(p.rendered?.html ?? '')}</content>
  </entry>`;
    })
    .join('\n');
  const xml = `<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>${esc(SITE.title)}</title>
  <link href="${root}/atom.xml" rel="self"/>
  <link href="${root}/"/>
  <updated>${updated}</updated>
  <id>${root}/</id>
  <author><name>${esc(SITE.author)}</name></author>
${entries}
</feed>
`;
  return new Response(xml, { headers: { 'Content-Type': 'application/atom+xml; charset=utf-8' } });
};
