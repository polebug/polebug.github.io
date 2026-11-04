// Finds the comment issue of every post that already has one, so utterances opens the same issue.
// Issues created by Gitalk on the old sites carry the label md5(pathname); this writes
// blog/comments.json as { "<md5(pathname)>": { issue, title } }. Needs the GitHub CLI (`gh`).
// Posts without an entry get a new issue, titled with their path, on their first comment.
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';

const repo = 'polebug/polebug.github.io';
const issues = JSON.parse(execFileSync('gh', [
  'issue', 'list', '-R', repo, '--state', 'all', '--limit', '1000', '--json', 'number,title,labels',
], { encoding: 'utf8' }));

// Preserve explicit aliases (for posts whose URLs changed) when refreshing the map.
const file = new URL('../blog/comments.json', import.meta.url);
const map = JSON.parse(readFileSync(file, 'utf8'));
for (const { number, title, labels } of issues.sort((a, b) => a.number - b.number)) {
  const legacyId = labels.map((l) => l.name).find((n) => /^[0-9a-f]{32}$/.test(n));
  // utterances titles new threads with the article path, without Gitalk's labels.
  const id = legacyId ?? (/^\/\d{4}\/\d{2}\/\d{2}\/[^/]+\/$/.test(title)
    ? createHash('md5').update(encodeURI(decodeURI(title))).digest('hex') : null);
  if (id && !map[id]) map[id] = { issue: number, title };
}
writeFileSync(file, JSON.stringify(map, null, 2) + '\n');
console.log(`${Object.keys(map).length} issues → blog/comments.json`);
