// v1 anchor offsets use Unicode code points (Array.from), never JavaScript UTF-16 offsets.
// Prefer exact evidence; repeated or missing quotes are never attached by guesswork.
export function resolveAnchor(anchor, text, sameRevision = false) {
  const chars = Array.from(text);
  const original = chars.slice(anchor.start_offset, anchor.end_offset).join('');
  if (sameRevision && original === anchor.exact) return { status: 'exact', start: anchor.start_offset, end: anchor.end_offset };
  const matches = [];
  for (let at = text.indexOf(anchor.exact); at !== -1; at = text.indexOf(anchor.exact, at + 1)) {
    if (anchor.prefix && !text.slice(0, at).endsWith(anchor.prefix)) continue;
    if (anchor.suffix && !text.slice(at + anchor.exact.length).startsWith(anchor.suffix)) continue;
    const start = Array.from(text.slice(0, at)).length;
    matches.push({ start, end: start + Array.from(anchor.exact).length });
  }
  if (matches.length === 1) return { status: 'relocated', ...matches[0] };
  return { status: matches.length > 1 ? 'ambiguous' : 'orphaned', start: null, end: null };
}
