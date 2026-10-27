// Finds the comment issue of every post that already has one, so utterances opens the same issue.
// Issues created by Gitalk on the old sites carry the label md5(pathname); this writes
// blog/comments.json as { "<md5(pathname)>": { issue, title } }. Needs the GitHub CLI (`gh`).
// Posts without an entry get a new issue, titled with their path, on their first comment.
import { execFileSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';

const repo = 'polebug/polebug.github.io';
const issues = JSON.parse(execFileSync('gh', [
  'issue', 'list', '-R', repo, '--state', 'all', '--label', 'Gitalk', '--limit', '1000', '--json', 'number,title,labels',
], { encoding: 'utf8' }));

const map = {};
for (const { number, title, labels } of issues.sort((a, b) => a.number - b.number)) {
  const id = labels.map((l) => l.name).find((n) => /^[0-9a-f]{32}$/.test(n));
  if (id && !map[id]) map[id] = { issue: number, title };
}
const file = new URL('../blog/comments.json', import.meta.url);
writeFileSync(file, JSON.stringify(map, null, 2) + '\n');
console.log(`${Object.keys(map).length} issues → blog/comments.json`);
