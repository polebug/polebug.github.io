import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

// Dates are written as Beijing time ("2025-6-21 21:51"). YAML turns full timestamps into UTC Dates,
// so their UTC fields are read back as Beijing time too.
function beijing(value: unknown): Date {
  if (value instanceof Date) {
    return new Date(value.getTime() - 8 * 3600_000);
  }
  const m = String(value).trim().match(/^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?$/);
  if (!m) throw new Error(`Unrecognised date "${value}" (expected YYYY-MM-DD HH:mm)`);
  const [, y, mo, d, h = '0', mi = '0', s = '0'] = m;
  return new Date(Date.UTC(+y, +mo - 1, +d, +h - 8, +mi, +s));
}

const schema = z.object({
  title: z.string(),
  date: z.union([z.date(), z.string()]).transform(beijing),
  desc: z.string().nullish(),
  tags: z.array(z.string()).nullish(),
  comments: z.boolean().default(true),
  // Where the post first appeared (e.g. the WeChat article it was copied from).
  source: z.string().url().nullish(),
});

const posts = defineCollection({
  loader: glob({ pattern: '*/index.md', base: './posts', generateId: ({ entry }) => entry.split('/')[0] }),
  schema,
});

// Drafts show up in `npm run dev` only.
const drafts = defineCollection({
  loader: glob({ pattern: '*/index.md', base: './drafts', generateId: ({ entry }) => entry.split('/')[0] }),
  schema,
});

export const collections = { posts, drafts };
