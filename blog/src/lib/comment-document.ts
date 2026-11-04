import registry from '../../comment-documents.json';
export function commentDocument(slug: string) {
  const id = (registry as Record<string,string>)[slug];
  if (!id) throw new Error(`Missing stable comment document ID for ${slug}. Run npm run comments:register; when renaming a post, move its existing registry entry instead.`);
  return id;
}
