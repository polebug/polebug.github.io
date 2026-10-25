import { getCollection, type CollectionEntry } from 'astro:content';
import { fromHtml } from 'hast-util-from-html';
import { toHtml } from 'hast-util-to-html';
import { toText } from 'hast-util-to-text';
import type { Element, ElementContent, Root } from 'hast';

export type Post = (CollectionEntry<'posts'> | CollectionEntry<'drafts'>) & {
  url: string;
  draft: boolean;
  ymd: { year: string; month: string; day: string };
  excerpt: string;
  summary: string;
};

// The opening of a post for the blog list, formatting kept: whole paragraphs, lists and quotes
// until about SUMMARY_CHARS characters; media, tables and layout blocks are left out.
const SUMMARY_CHARS = 260;
const SUMMARY_BLOCKS = new Set(['p', 'ul', 'ol', 'blockquote', 'h2', 'h3', 'h4', 'h5', 'h6']);
const DROP = new Set(['img', 'video', 'picture', 'iframe', 'style', 'script', 'table', 'figure', 'source']);

function stripMedia(node: Element): Element {
  node.children = node.children
    .filter((c): c is ElementContent => !(c.type === 'element' && DROP.has(c.tagName)))
    .map((c) => (c.type === 'element' ? stripMedia(c) : c));
  delete node.properties.id;
  return node;
}

function summaryOf(html = '', desc?: string | null) {
  if (desc?.trim()) return toHtml({ type: 'element', tagName: 'p', properties: {}, children: [{ type: 'text', value: desc.trim() }] });
  const root = fromHtml(html, { fragment: true });
  const blocks: Element[] = [];
  let chars = 0;
  for (const node of root.children) {
    if (node.type !== 'element' || !SUMMARY_BLOCKS.has(node.tagName)) continue;
    const block = stripMedia(node);
    const text = toText(block).trim();
    if (!text) continue;
    if (/^h\d$/.test(block.tagName)) {
      block.tagName = 'p';
      block.properties = { className: ['summary-heading'] };
    }
    blocks.push(block);
    chars += text.length;
    if (chars >= SUMMARY_CHARS) break;
  }
  return toHtml({ type: 'root', children: blocks } as Root);
}

// Same calendar as the old Hexo site (Beijing time), so /:year/:month/:day/:slug/ stays the same.
export function beijingParts(date: Date) {
  const shifted = new Date(date.getTime() + 8 * 3600_000);
  return {
    year: String(shifted.getUTCFullYear()),
    month: String(shifted.getUTCMonth() + 1).padStart(2, '0'),
    day: String(shifted.getUTCDate()).padStart(2, '0'),
  };
}

export function formatDate(date: Date) {
  const { year, month, day } = beijingParts(date);
  return `${year}-${month}-${day}`;
}

function excerptOf(body = '', desc?: string | null) {
  if (desc?.trim()) return desc.trim();
  const text = body
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/^\s*(?:>|#{1,6}|[-*+]|\d+\.)\s*/gm, '')
    .replace(/[*_`~|]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  return text.length > 120 ? `${text.slice(0, 120)}…` : text;
}

export async function getPosts(): Promise<Post[]> {
  const entries = [
    ...(await getCollection('posts')).map((e) => ({ e, draft: false })),
    ...(import.meta.env.DEV ? (await getCollection('drafts')).map((e) => ({ e, draft: true })) : []),
  ];
  return entries
    .map(({ e, draft }) => {
      const ymd = beijingParts(e.data.date);
      return {
        ...e,
        draft,
        ymd,
        url: `/${ymd.year}/${ymd.month}/${ymd.day}/${e.id}/`,
        excerpt: excerptOf(e.body, e.data.desc),
        summary: summaryOf(e.rendered?.html, e.data.desc),
      } as Post;
    })
    .sort((a, b) => b.data.date.getTime() - a.data.date.getTime());
}

export const PER_PAGE = 10;
