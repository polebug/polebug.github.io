import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {DatabaseSync} from 'node:sqlite';
import worker,{digest} from '../src/index.js';
import {resolveAnchor} from '../src/anchors.js';
const initialMigration=fs.readFileSync(new URL('../migrations/0001_init.sql',import.meta.url),'utf8');
const guestMigration=fs.readFileSync(new URL('../migrations/0002_guest_verification.sql',import.meta.url),'utf8');
const migration=initialMigration+guestMigration;
function db(){
  const sql=new DatabaseSync(':memory:');sql.exec('PRAGMA foreign_keys=ON;'+migration);
  function prepare(query){let values=[];return{bind(...v){values=v;return this;},async first(){return sql.prepare(query).get(...values)||null;},async all(){return{results:sql.prepare(query).all(...values)};},async run(){if(/^\s*SELECT/i.test(query))return this.all();const r=sql.prepare(query).run(...values);return{meta:{changes:r.changes}};}};}
  return{sql,prepare,async batch(list){sql.exec('BEGIN');try{const r=[];for(const p of list)r.push(await p.run());sql.exec('COMMIT');return r;}catch(e){sql.exec('ROLLBACK');throw e;}}};
}
async function fixture(){
  const DB=db();const env={DB,ENVIRONMENT:'development',BLOG_ORIGIN:'http://localhost:4321',API_ORIGIN:'http://localhost:8788',ADMIN_GITHUB_ID:'1',RATE_SALT:'test-only-secret',TURNSTILE_SECRET_KEY:'test'};
  DB.sql.exec(`INSERT INTO documents(id,canonical_path,title,created_at) VALUES('doc','/post/','Post','2026-01-01'),('other','/other/','Other','2026-01-01');
    INSERT INTO threads(id,document_id,created_at) VALUES('thread','doc','2026-01-01'),('other-thread','other','2026-01-01');
    INSERT INTO users(id,kind,display_name,created_at) VALUES('github:1','github','owner','2026-01-01'),('github:2','github','reader','2026-01-01'),('guest','guest','visitor','2026-01-01');
    INSERT INTO identities(provider,subject,user_id) VALUES('github','1','github:1'),('github','2','github:2');`);
  for(const [raw,id]of[['owner','github:1'],['reader','github:2'],['guest','guest']])DB.sql.prepare('INSERT INTO sessions(token_hash,user_id,csrf,expires_at) VALUES(?,?,?,?)').run(await digest(raw),id,'csrf-'+raw,Date.now()+1000000);
  async function req(path,method='GET',data,who=null,extra={}){
    const headers={Origin:env.BLOG_ORIGIN,...(data?{'Content-Type':'application/json'}:{}),...(who?{Cookie:'polebug_session='+who,'X-CSRF-Token':'csrf-'+who}:{}),...extra};
    const r=await worker.fetch(new Request(env.API_ORIGIN+path,{method,headers,body:data?JSON.stringify(data):undefined}),env);
    return{status:r.status,data:await r.json(),headers:r.headers};
  }
  return{env,DB,req};
}
const payload=(body='hello',extra={})=>({documentId:'doc',body,requestId:crypto.randomUUID(),...extra});
test('published feed, CSRF, per-author deletion and idempotent writes',async()=>{
  const {req,DB}=await fixture();const p=payload('<script>alert(1)</script>');
  assert.equal((await req('/v1/comments','POST',p,'reader',{'X-CSRF-Token':'wrong'})).status,403);
  const first=await req('/v1/comments','POST',p,'reader');assert.equal(first.status,201);
  const retry=await req('/v1/comments','POST',p,'reader');assert.equal(retry.data.id,first.data.id);
  assert.equal(DB.sql.prepare('SELECT COUNT(*) n FROM comments').get().n,1);
  assert.equal((await req('/v1/comments','POST',{...p,body:'changed'},'reader')).status,409);
  const feed=await req('/v1/comments?document=doc');assert.equal(feed.data.comments[0].body,p.body);assert.equal(feed.data.total,1);
  assert.equal((await req('/v1/comments/'+first.data.id,'DELETE',null,'owner')).status,403);
  assert.equal((await req('/v1/comments/'+first.data.id,'DELETE',null,'reader')).status,200);
  const deleted=await req('/v1/comments?document=doc');assert.equal(deleted.data.comments[0].body,'');assert.equal(deleted.data.total,0);
});
test('guest comments publish immediately; private moderation states stay protected',async()=>{
  const {req,env,DB}=await fixture();const old=globalThis.fetch;
  try{
    globalThis.fetch=async()=>Response.json({success:true,hostname:'evil.test',action:'comment'});
    assert.equal((await req('/v1/comments','POST',payload('private',{name:'Visitor',turnstileToken:'x'}))).status,400);
    globalThis.fetch=async()=>Response.json({success:true,hostname:'localhost',action:'comment'});
    const r=await req('/v1/comments','POST',payload('private',{name:'Visitor',turnstileToken:'x'}));assert.equal(r.status,201);assert.equal(r.data.status,'published');assert.equal(r.data.verificationRequired,false);
    assert.equal((await req('/v1/comments?document=doc')).data.total,1);
    DB.sql.prepare("UPDATE comments SET status='pending' WHERE id=?").run(r.data.id);
    assert.match(r.headers.get('Set-Cookie'),/HttpOnly/);
    assert.equal((await req('/v1/comments?document=doc')).data.comments.length,0);
    assert.equal((await req('/v1/admin/comments','GET',null,'reader')).status,403);
    assert.equal((await req('/v1/admin/comments?status=pending','GET',null,'owner')).data.comments[0].body,'private');
    assert.equal((await req('/v1/admin/comments/'+r.data.id,'PATCH',{status:'published'},'reader')).status,403);
    assert.equal((await req('/v1/admin/comments/'+r.data.id,'PATCH',{status:'published'},'owner')).status,200);
    assert.equal((await req('/v1/comments?document=doc')).data.total,1);
    assert.equal(DB.sql.prepare('SELECT COUNT(*) n FROM moderation_events').get().n,1);
  }finally{globalThis.fetch=old;}
});
test('cross-document replies and mismatched anchor revisions fail',async()=>{
  const {req,DB}=await fixture();const r=await req('/v1/comments','POST',payload(),'reader');
  assert.equal((await req('/v1/comments','POST',payload('reply',{documentId:'other',parentId:r.data.id}),'reader')).status,400);
  DB.sql.exec("INSERT INTO document_revisions VALUES('r','other','hash','text','v1','2026-01-01');");
  assert.throws(()=>DB.sql.exec("INSERT INTO anchors VALUES('a','doc','r',1,'t','','',0,1,'2026-01-01');"),/FOREIGN KEY/);
  assert.throws(()=>DB.sql.prepare("INSERT INTO comments(id,thread_id,parent_id,author_id,author_name,body,status,created_at,updated_at) VALUES('bad','other-thread',?,'guest','guest','x','pending','x','x')").run(r.data.id),/FOREIGN KEY/);
});
test('origin protection, blocked users and rate limiting',async()=>{
  const {req,DB}=await fixture();
  assert.equal((await req('/v1/comments','POST',payload(),'reader',{Origin:'https://evil.test'})).status,403);
  assert.equal((await req('/v1/comments?document=doc&cursor=invalid')).status,400);
  for(let i=0;i<8;i++)assert.equal((await req('/v1/comments','POST',payload(),'reader')).status,201);
  assert.equal((await req('/v1/comments','POST',payload(),'reader')).status,429);
  DB.sql.exec("UPDATE users SET blocked=1 WHERE id='github:1'");
  assert.equal((await req('/v1/admin/comments','GET',null,'owner')).status,403);
});
test('OAuth state binds browser, is single-use and grants no repo scopes',async()=>{
  const {req,env,DB}=await fixture();env.GITHUB_CLIENT_ID='test-id';env.GITHUB_CLIENT_SECRET='test-secret';
  const r=await worker.fetch(new Request(env.API_ORIGIN+'/auth/github?document=doc'),env);
  assert.equal(r.status,302);const destination=new URL(r.headers.get('Location'));assert.equal(destination.searchParams.get('scope'),'');assert.equal(destination.searchParams.get('code_challenge_method'),'S256');
  const state=destination.searchParams.get('state');
  const bad=await worker.fetch(new Request(`${env.API_ORIGIN}/auth/github/callback?state=${state}&code=x`),env);assert.equal(bad.status,400);
  const old=globalThis.fetch;let calls=0;
  try{
    globalThis.fetch=async()=>Response.json(++calls===1?{access_token:'secret-token'}:{id:2,login:'reader'});
    const request=()=>new Request(`${env.API_ORIGIN}/auth/github/callback?state=${state}&code=x`,{headers:{Cookie:'polebug_oauth='+state}});
    const success=await worker.fetch(request(),env);assert.equal(success.status,302);assert.equal(success.headers.get('Location'),'http://localhost:4321/post/#comments');
    assert.equal((await worker.fetch(request(),env)).status,400);
    assert.equal(DB.sql.prepare('SELECT COUNT(*) n FROM oauth_states').get().n,0);
  }finally{globalThis.fetch=old;}
});
test('pagination with equal timestamps has no missing or duplicated comments',async()=>{
  const {req,DB}=await fixture();
  for(let i=0;i<45;i++)DB.sql.prepare("INSERT INTO comments(id,thread_id,author_id,author_name,body,status,created_at,updated_at,published_at) VALUES(?,'thread','guest','v','x','published','same','same','same')").run(String(i).padStart(3,'0'));
  const first=await req('/v1/comments?document=doc');assert.equal(first.data.comments.length,40);
  const second=await req('/v1/comments?document=doc&cursor='+encodeURIComponent(first.data.nextCursor));assert.equal(second.data.comments.length,5);
  assert.equal(new Set([...first.data.comments,...second.data.comments].map(c=>c.id)).size,45);
});
test('quote anchors survive moves, respect Unicode, and never guess ambiguous matches',()=>{
  const anchor={exact:'你好🌱',prefix:'',suffix:'',start_offset:1,end_offset:4};
  assert.deepEqual(resolveAnchor(anchor,'x你好🌱z',true),{status:'exact',start:1,end:4});
  assert.deepEqual(resolveAnchor(anchor,'前言 x你好🌱z'),{status:'relocated',start:4,end:7});
  assert.equal(resolveAnchor(anchor,'你好🌱 你好🌱').status,'ambiguous');
  assert.equal(resolveAnchor(anchor,'different').status,'orphaned');
  assert.deepEqual(resolveAnchor({...anchor,prefix:'B'},'A你好🌱 B你好🌱'),{status:'relocated',start:6,end:9});
});

test('guest verification is session-bound, expires after 24h, and is not extended by posting',async()=>{
  const {req,DB}=await fixture();const old=globalThis.fetch;let checks=0;
  try {
    globalThis.fetch=async()=>{checks++;return Response.json({success:true,hostname:'localhost',action:'comment'});};
    const firstPayload=payload('first',{name:'Guest',turnstileToken:'single-use'});
    const first=await req('/v1/comments','POST',firstPayload);
    assert.equal(first.status,201);assert.equal(checks,1);
    const headers={Cookie:first.headers.get('Set-Cookie').split(';')[0],'X-CSRF-Token':first.data.csrf};
    const until=first.data.humanVerifiedUntil;
    assert.ok(until>Date.now()+86300000 && until<=Date.now()+86400000);
    assert.equal((await req('/v1/session','GET',null,null,headers)).data.verificationRequired,false);
    const secondPayload=payload('second');
    const second=await req('/v1/comments','POST',secondPayload,null,headers);
    assert.equal(second.status,201);assert.equal(second.data.status,'published');assert.equal(second.data.humanVerifiedUntil,until);assert.equal(checks,1);
    assert.equal((await req('/v1/comments','POST',secondPayload,null,headers)).data.id,second.data.id);
    assert.equal((await req('/v1/comments','POST',payload('CSRF'),null,{...headers,'X-CSRF-Token':'wrong'})).status,403);
    assert.equal((await req('/v1/comments','POST',payload('different browser',{name:'Guest',humanVerifiedUntil:until}))).status,400);
    DB.sql.prepare('UPDATE sessions SET human_verified_until=? WHERE user_id=?').run(Date.now()-1,first.data.user.id);
    assert.equal((await req('/v1/session','GET',null,null,headers)).data.verificationRequired,true);
    assert.equal((await req('/v1/comments','POST',payload('expired'),null,headers)).status,400);
    assert.equal((await req('/v1/comments','POST',payload('verified again',{turnstileToken:'new-token'}),null,headers)).status,201);assert.equal(checks,2);
    assert.equal((await req('/v1/logout','POST',null,null,headers)).status,200);
    assert.equal((await req('/v1/session','GET',null,null,headers)).data.verificationRequired,true);
  } finally {globalThis.fetch=old;}
});
test('guest session migration credits only the original verification day',()=>{
  const sql=new DatabaseSync(':memory:');sql.exec('PRAGMA foreign_keys=ON;'+initialMigration);
  const date=Date.now();sql.exec("INSERT INTO users VALUES('g','guest','Guest',0,'date');");
  sql.prepare('INSERT INTO sessions VALUES(?,?,?,?)').run('recent','g','csrf',date+30*86400000);
  sql.prepare('INSERT INTO sessions VALUES(?,?,?,?)').run('old','g','csrf',date+28*86400000);
  sql.exec(guestMigration);
  assert.equal(sql.prepare("SELECT human_verified_until v FROM sessions WHERE token_hash='recent'").get().v,date+86400000);
  assert.ok(sql.prepare("SELECT human_verified_until v FROM sessions WHERE token_hash='old'").get().v<date);
  sql.close();
});
