import fs from 'node:fs';
import { randomUUID } from 'node:crypto';
const registry = new URL('../../blog/comment-documents.json', import.meta.url);
const entries = fs.existsSync(registry) ? JSON.parse(fs.readFileSync(registry,'utf8')) : {};
for (const dir of fs.readdirSync(new URL('../../blog/posts/',import.meta.url),{withFileTypes:true})) {
  if (dir.isDirectory() && !entries[dir.name]) entries[dir.name] = randomUUID();
}
fs.writeFileSync(registry,JSON.stringify(entries,null,2)+'\n');
console.log(`Comment document IDs: ${Object.keys(entries).length}`);
