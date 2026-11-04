// Read-only GitHub export + idempotent SQL. Review the report before applying to D1.
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {fromHtml} from 'hast-util-from-html';
import {toText} from 'hast-util-to-text';
const root=new URL('../../',import.meta.url);
const dataDir=new URL('../.data/',import.meta.url);fs.mkdirSync(dataDir,{recursive:true});
const map=JSON.parse(fs.readFileSync(new URL('blog/comments.json',root),'utf8'));
const q=x=>x===null?'NULL':"'"+String(x).replaceAll("'","''")+"'";
const sha=x=>createHash('sha256').update(x).digest('hex');
const date=new Date().toISOString();const sql=[];const docs=[];const issuesToDocs=new Map();
const walk=dir=>fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(path.join(dir,e.name)):[path.join(dir,e.name)]);
function find(node,predicate){if(predicate(node))return node;for(const c of node.children||[]){const r=find(c,predicate);if(r)return r;}}
function addDocument(d,text=''){
  const revision=`rev:${d.id}:${sha(text)}`;
  sql.push(`INSERT INTO documents(id,canonical_path,title,created_at) VALUES(${[d.id,d.path,d.title,date].map(q)}) ON CONFLICT(id) DO UPDATE SET canonical_path=excluded.canonical_path,title=excluded.title;`);
  sql.push(`INSERT OR IGNORE INTO document_aliases(path,document_id) VALUES(${q(d.path)},${q(d.id)});`);
  sql.push(`INSERT OR IGNORE INTO document_revisions(id,document_id,text_sha256,text_content,normalization,created_at) VALUES(${[revision,d.id,sha(text),text,'hast-text-nfc-v1',date].map(q)});`);
  sql.push(`UPDATE documents SET current_revision_id=${q(revision)} WHERE id=${q(d.id)};`);
  sql.push(`INSERT OR IGNORE INTO threads(id,document_id,created_at) VALUES(${q('page:'+d.id)},${q(d.id)},${q(date)});`);
  docs.push(d);
}
for(const file of walk(new URL('blog/dist/',root).pathname).filter(f=>f.endsWith('.html'))){
  const html=fs.readFileSync(file,'utf8'),tree=fromHtml(html);
  const component=find(tree,n=>n.properties?.className?.includes('native-comments'));
  if(!component)continue;
  const id=component.properties.dataDocument;
  const canonical=find(tree,n=>n.tagName==='link'&&n.properties?.rel?.includes('canonical'))?.properties.href;
  const url=new URL(canonical);const d={id,path:decodeURI(url.pathname),title:toText(find(tree,n=>n.tagName==='h1'))};
  const prose=find(tree,n=>n.properties?.className?.includes('prose'));
  const text=toText(prose).normalize('NFC').replaceAll('\r\n','\n');
  addDocument(d,text);
  const issue=map[createHash('md5').update(encodeURI(d.path)).digest('hex')]?.issue;
  if(issue){issuesToDocs.set(issue,d);d.githubIssue=issue;}
}
if(process.argv.includes('--documents-only')) {
  fs.writeFileSync(new URL('documents.sql',dataDir),sql.join('\n')+'\n');
  console.log(JSON.stringify({documents:docs.length,output:'comments/.data/documents.sql'}));
  process.exit(0);
}
for(const item of Object.values(map)){
  if(issuesToDocs.has(item.issue))continue;
  const d={id:`legacy:github:${item.issue}`,path:`/legacy/github/issue-${item.issue}/`,title:item.title,githubIssue:item.issue,archived:true};
  addDocument(d);issuesToDocs.set(item.issue,d);
}
let exported=0;const counts=[];
for(const [issue,d] of issuesToDocs){
  const cache=new URL(`github-${issue}.json`,dataDir);
  let rows;
  if(process.argv.includes('--cached')&&fs.existsSync(cache))rows=JSON.parse(fs.readFileSync(cache,'utf8'));
  else{
    rows=JSON.parse(execFileSync('gh',['api',`repos/polebug/polebug.github.io/issues/${issue}/comments?per_page=100`,'--paginate','--slurp'],{encoding:'utf8',maxBuffer:10*1024*1024})).flat();
    fs.writeFileSync(cache,JSON.stringify(rows,null,2)+'\n');
  }
  for(const c of rows){
    const uid=c.user?.id?`github:${c.user.id}`:`imported:github:${c.id}`;
    const kind=c.user?.id?'github':'imported';const name=c.user?.login||'已注销的 GitHub 用户';
    sql.push(`INSERT OR IGNORE INTO users(id,kind,display_name,created_at) VALUES(${[uid,kind,name,c.created_at].map(q)});`);
    if(c.user?.id)sql.push(`INSERT OR IGNORE INTO identities(provider,subject,user_id) VALUES('github',${q(c.user.id)},${q(uid)});`);
    // Preserve local moderation on re-runs; never overwrite an existing imported comment.
    sql.push(`INSERT OR IGNORE INTO comments(id,thread_id,author_id,author_name,body,status,source,external_id,source_url,created_at,updated_at,published_at)
      VALUES(${[`github:${c.id}`,'page:'+d.id,uid,name,c.body||'','published','github',String(c.id),c.html_url,c.created_at,c.updated_at,c.created_at].map(q)});`);
  }
  exported+=rows.length;counts.push({issue,documentId:d.id,comments:rows.length,archived:!!d.archived});
  console.log(`Issue #${issue}: ${rows.length} comments`);
}
fs.writeFileSync(new URL('import.sql',dataDir),sql.join('\n')+'\n');
const report={generatedAt:date,documents:docs.length,comments:exported,issues:counts};
fs.writeFileSync(new URL('report.json',dataDir),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({documents:docs.length,comments:exported,output:'comments/.data/import.sql'}));
