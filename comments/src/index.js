const DAY = 86400000;
const json = (data, status = 200, headers = {}) => Response.json(data, { status, headers });
const fail = (status, message) => { throw Object.assign(new Error(message), { status }); };
const now = () => new Date().toISOString();
const uuid = () => crypto.randomUUID();
export const digest = async (s) => [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s)))].map(b => b.toString(16).padStart(2, '0')).join('');
const token = () => uuid() + uuid();
const local = env => env.ENVIRONMENT === 'development';
const cookieName = env => local(env) ? 'polebug_session' : '__Host-polebug_session';
const stateName = env => local(env) ? 'polebug_oauth' : '__Host-polebug_oauth';
const cookie = (name, value, age, env) => `${name}=${value}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${age}${local(env) ? '' : '; Secure'}`;
const readCookie = (req, name) => (req.headers.get('Cookie') || '').split(';').map(x => x.trim()).find(x => x.startsWith(name + '='))?.slice(name.length + 1);
const allowed = (origin, env) => origin === env.BLOG_ORIGIN || origin === env.API_ORIGIN;
const stmt = (env, sql, ...args) => env.DB.prepare(sql).bind(...args);
const one = (env, sql, ...args) => stmt(env, sql, ...args).first();
const many = async (env, sql, ...args) => (await stmt(env, sql, ...args).all()).results;

async function body(req) {
  if (!(req.headers.get('Content-Type') || '').startsWith('application/json')) fail(415, '请使用 JSON 请求。');
  if (Number(req.headers.get('Content-Length')) > 20000) fail(413, '内容太长。');
  const reader = req.body?.getReader();
  if (!reader) fail(400, '缺少请求内容。');
  const chunks = []; let size = 0;
  while (true) {
    const { value, done } = await reader.read(); if (done) break;
    size += value.byteLength;
    if (size > 20000) { await reader.cancel(); fail(413, '内容太长。'); }
    chunks.push(value);
  }
  const bytes = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  try { const data = JSON.parse(new TextDecoder().decode(bytes)); if (!data || typeof data !== 'object' || Array.isArray(data)) throw 0; return data; }
  catch { fail(400, '请求格式不正确。'); }
}

async function session(req, env) {
  const raw = readCookie(req, cookieName(env));
  if (!raw || raw.length > 200) return null;
  const user = await one(env, `SELECT u.*, s.csrf, s.token_hash, i.subject FROM sessions s
    JOIN users u ON u.id = s.user_id LEFT JOIN identities i ON i.user_id = u.id AND i.provider = 'github'
    WHERE s.token_hash = ? AND s.expires_at > ?`, await digest(raw), Date.now());
  if (!user || user.blocked) return null;
  user.admin = user.kind === 'github' && user.subject === env.ADMIN_GITHUB_ID;
  return user;
}
function requireUser(user, req) {
  if (!user) fail(401, '请先登录。');
  if (req.headers.get('X-CSRF-Token') !== user.csrf) fail(403, '登录状态已更新，请刷新后重试。');
}
async function limit(req, env, user, action = 'write') {
  if (!env.RATE_SALT) fail(503, '评论服务尚未配置完成。');
  const ip = req.headers.get('CF-Connecting-IP') || (local(env) ? 'local' : 'unknown');
  // Hashes expire daily; never persist raw IPs or browser fingerprints.
  const ipKey = await digest(`${env.RATE_SALT}|${new Date().toISOString().slice(0,10)}|${ip}`);
  const rules = [[`${action}:ip:${ipKey}`, 60000, 8], [`${action}:hour:${ipKey}`, 3600000, 60]];
  if (user) rules.push([`${action}:user:${user.id}`, 3600000, user.kind === 'github' ? 40 : 10]);
  for (const [key, span, max] of rules) {
    const window = Math.floor(Date.now() / span);
    const r = await one(env, `INSERT INTO rate_limits(key, window, count, expires_at) VALUES(?, ?, 1, ?)
      ON CONFLICT(key, window) DO UPDATE SET count = count + 1 RETURNING count`, key, window, (window + 1) * span);
    if (r.count > max) fail(429, '发送太频繁，请稍后再试。');
  }
}
async function human(req, env, value) {
  if (!env.TURNSTILE_SECRET_KEY) fail(503, '访客评论暂未开放，请使用 GitHub 登录。');
  if (typeof value !== 'string' || !value || value.length > 2048) fail(400, '请完成人机校验。');
  const r = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: AbortSignal.timeout(10000),
    body: JSON.stringify({ secret: env.TURNSTILE_SECRET_KEY, response: value, remoteip: req.headers.get('CF-Connecting-IP') || undefined }),
  });
  const data = await r.json();
  if (!r.ok || !data.success || data.action !== 'comment' || data.hostname !== new URL(env.BLOG_ORIGIN).hostname) fail(400, '人机校验已过期或失败，请重新验证。');
}
const viewUser = u => u ? { id: u.id, name: u.display_name, kind: u.kind, admin: !!u.admin } : null;
function viewComment(c, user, admin = false) {
  const visibleBody = c.status === 'published' || admin || c.author_id === user?.id;
  return {
    id: c.id, threadId: c.thread_id, parentId: c.parent_id, body: c.status === 'deleted' && !admin ? '' : visibleBody ? c.body : '',
    author: { name: c.author_name, kind: c.kind, owner: c.subject === c.admin_subject && c.kind === 'github' },
    createdAt: c.created_at, status: c.status, mine: c.author_id === user?.id,
    source: c.source, sourceUrl: c.source_url,
    ...(admin ? { documentId: c.document_id, title: c.document_title } : {}),
  };
}
const selectComments = `SELECT c.*, u.kind, i.subject, ? AS admin_subject FROM comments c JOIN users u ON u.id=c.author_id
  LEFT JOIN identities i ON i.user_id=u.id AND i.provider='github'`;
function cursorOf(c) { return c ? btoa(JSON.stringify([c.created_at, c.id])) : null; }
function readCursor(value) {
  if (!value) return ['', ''];
  try { const c = JSON.parse(atob(value)); if (!Array.isArray(c) || c.length !== 2 || !c.every(s=>typeof s==='string' && s.length < 100)) throw 0; return c; }
  catch { fail(400, '分页参数不正确。'); }
}
async function documentFor(env, id) {
  const d = await one(env, 'SELECT * FROM documents WHERE id = ?', id || '');
  if (!d) fail(404, '找不到这篇文章的评论。');
  return d;
}
async function feed(url, req, env) {
  const documentId = url.searchParams.get('document') || '';
  const [at, id] = readCursor(url.searchParams.get('cursor'));
  // One D1 round trip for metadata + page; the batch reads a consistent snapshot.
  const [user, result] = await Promise.all([session(req, env), env.DB.batch([
    stmt(env, `SELECT d.comments_enabled,t.id AS thread_id,t.status,
      (SELECT COUNT(*) FROM comments c WHERE c.thread_id=t.id AND c.status='published') AS total
      FROM documents d LEFT JOIN threads t ON t.document_id=d.id AND t.anchor_id IS NULL WHERE d.id=?`, documentId),
    stmt(env, `${selectComments} JOIN threads t ON t.id=c.thread_id
      WHERE t.document_id=? AND t.anchor_id IS NULL AND (c.status='published' OR (c.status='deleted' AND c.published_at IS NOT NULL))
      AND (c.created_at > ? OR (c.created_at = ? AND c.id > ?)) ORDER BY c.created_at,c.id LIMIT 41`, env.ADMIN_GITHUB_ID, documentId, at, at, id),
  ])]);
  const meta = result[0].results[0];
  if (!meta) fail(404, '找不到这篇文章的评论。');
  if (!meta.thread_id || meta.status === 'hidden') fail(404, '评论暂不可用。');
  const rows = result[1].results, page = rows.slice(0,40);
  return json({ comments: page.map(c=>viewComment(c,user)), total: meta.total, nextCursor: rows.length > 40 ? cursorOf(page.at(-1)) : null,
    threadId: meta.thread_id, writable: !!meta.comments_enabled && meta.status === 'open' });
}
async function createComment(req, env) {
  const data = await body(req);
  const user = await session(req, env);
  if (user) requireUser(user, req);
  const text = typeof data.body === 'string' ? data.body.trim() : '';
  if (!text || text.length > 6000) fail(400, '评论需要 1–6000 个字符。');
  if (!/^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(data.requestId || '')) fail(400, '缺少有效的请求编号。');
  const d = await documentFor(env, data.documentId);
  const thread = await one(env, 'SELECT * FROM threads WHERE document_id=? AND anchor_id IS NULL', d.id);
  if (!d.comments_enabled || !thread || thread.status !== 'open') fail(403, '这篇文章暂不接受新评论。');
  const parentId = data.parentId || null;
  if (parentId) {
    const parent = await one(env, "SELECT id FROM comments WHERE id=? AND thread_id=? AND status='published'", parentId, thread.id);
    if (!parent) fail(400, '回复的评论不存在或已隐藏。');
  }
  // A retry of a successful authenticated request returns the original, never duplicates it.
  if (user) {
    const old = await one(env, 'SELECT * FROM comments WHERE author_id=? AND request_key=?', user.id, data.requestId);
    if (old) {
      if (old.body !== text || old.thread_id !== thread.id || old.parent_id !== parentId) fail(409, '请求编号已被使用。');
      return json({ id: old.id, status: old.status, user: viewUser(user), csrf: user.csrf });
    }
  }
  await limit(req, env, user);
  if (!user || user.kind !== 'github') await human(req, env, data.turnstileToken);
  const name = user?.display_name || (typeof data.name === 'string' ? data.name.trim() : '');
  if (!name || name.length > 40 || /[\x00-\x1f<>]/.test(name)) fail(400, '请填写 1–40 字的昵称。');
  const uid = user?.id || `guest:${uuid()}`;
  const status = user?.kind === 'github' ? 'published' : 'pending';
  const created = now(), id = uuid(), raw = user ? null : token(), csrf = user?.csrf || token();
  const batch = [];
  if (!user) {
    batch.push(stmt(env, "INSERT INTO users(id,kind,display_name,created_at) VALUES(?,'guest',?,?)", uid,name,created));
    batch.push(stmt(env, 'INSERT INTO sessions(token_hash,user_id,csrf,expires_at) VALUES(?,?,?,?)',await digest(raw),uid,csrf,Date.now()+30*DAY));
  }
  batch.push(stmt(env, `INSERT INTO comments(id,thread_id,parent_id,author_id,author_name,body,status,request_key,created_at,updated_at,published_at)
    VALUES(?,?,?,?,?,?,?,?,?,?,?)`,id,thread.id,parentId,uid,name,text,status,data.requestId,created,created,status==='published'?created:null));
  await env.DB.batch(batch);
  return json({id,status,user:viewUser(user || {id:uid,display_name:name,kind:'guest'}),csrf},201,
    raw ? {'Set-Cookie':cookie(cookieName(env),raw,30*86400,env)} : {});
}
async function changeComment(req, env, id, adminAction) {
  const user = await session(req, env); requireUser(user,req);
  if (adminAction && !user.admin) fail(403,'需要博主权限。');
  const c = await one(env,'SELECT * FROM comments WHERE id=?',id);
  if (!c) fail(404,'评论不存在。');
  if (!adminAction && c.author_id !== user.id) fail(403,'只能删除自己的评论。');
  const data = adminAction ? await body(req) : {};
  const status = adminAction ? data.status : 'deleted';
  if (!['published','hidden','deleted'].includes(status)) fail(400,'不支持的审核操作。');
  const date = now();
  await env.DB.batch([
    stmt(env,"UPDATE comments SET status=?,updated_at=?,published_at=CASE WHEN ?='published' THEN COALESCE(published_at,?) ELSE published_at END WHERE id=?",status,date,status,date,id),
    stmt(env,'INSERT INTO moderation_events(id,comment_id,actor_id,action,previous_status,next_status,created_at) VALUES(?,?,?,?,?,?,?)',uuid(),id,user.id,adminAction?'moderate':'author_delete',c.status,status,date),
  ]);
  return json({ok:true,status});
}
async function adminFeed(url, req, env) {
  const user = await session(req,env);
  if (!user?.admin) fail(403,'需要博主权限。');
  const status = url.searchParams.get('status') || 'pending';
  if (!['pending','published','hidden','deleted'].includes(status)) fail(400,'状态不正确。');
  const [at,id]=readCursor(url.searchParams.get('cursor'));
  const rows = await many(env,`SELECT c.*,u.kind,i.subject,? AS admin_subject,t.document_id,d.title AS document_title
    FROM comments c JOIN users u ON u.id=c.author_id JOIN threads t ON t.id=c.thread_id JOIN documents d ON d.id=t.document_id
    LEFT JOIN identities i ON i.user_id=u.id AND i.provider='github'
    WHERE c.status=? AND (c.created_at>? OR (c.created_at=? AND c.id>?)) ORDER BY c.created_at,c.id LIMIT 41`,env.ADMIN_GITHUB_ID,status,at,at,id);
  const page=rows.slice(0,40);
  return json({comments:page.map(c=>viewComment(c,user,true)),nextCursor:rows.length>40?cursorOf(page.at(-1)):null});
}
async function login(url, req, env) {
  if (!env.GITHUB_CLIENT_ID || !env.GITHUB_CLIENT_SECRET) fail(503,'GitHub 登录尚未配置。');
  const d = await documentFor(env,url.searchParams.get('document'));
  await limit(req,env,null,'login');
  const state=token(),verifier=token();
  const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(verifier));
  const challenge=btoa(String.fromCharCode(...new Uint8Array(hash))).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
  await stmt(env,'INSERT INTO oauth_states(state_hash,verifier,return_path,expires_at) VALUES(?,?,?,?)',await digest(state),verifier,d.canonical_path,Date.now()+10*60000).run();
  const auth=new URL('https://github.com/login/oauth/authorize');
  auth.search=new URLSearchParams({client_id:env.GITHUB_CLIENT_ID,redirect_uri:`${env.API_ORIGIN}/auth/github/callback`,state,scope:'',code_challenge:challenge,code_challenge_method:'S256'}).toString();
  return new Response(null,{status:302,headers:{Location:auth.href,'Set-Cookie':cookie(stateName(env),state,600,env)}});
}
async function callback(url, req, env) {
  const state=url.searchParams.get('state'),code=url.searchParams.get('code');
  if (!state || state!==readCookie(req,stateName(env)) || state.length>200 || !code || code.length>500) fail(400,'登录验证失败，请重新发起登录。');
  const saved=await one(env,'DELETE FROM oauth_states WHERE state_hash=? AND expires_at>? RETURNING *',await digest(state),Date.now());
  if (!saved) fail(400,'登录请求已过期或使用过，请重试。');
  const r=await fetch('https://github.com/login/oauth/access_token',{method:'POST',headers:{Accept:'application/json','Content-Type':'application/json'},signal:AbortSignal.timeout(15000),
    body:JSON.stringify({client_id:env.GITHUB_CLIENT_ID,client_secret:env.GITHUB_CLIENT_SECRET,code,code_verifier:saved.verifier,redirect_uri:`${env.API_ORIGIN}/auth/github/callback`})});
  const result=await r.json();
  if (!r.ok || !result.access_token) fail(502,'GitHub 登录暂时不可用，请重试。');
  const p=await fetch('https://api.github.com/user',{headers:{Authorization:`Bearer ${result.access_token}`,Accept:'application/vnd.github+json','User-Agent':'polebug-comments'},signal:AbortSignal.timeout(15000)});
  const profile=await p.json();
  if (!p.ok || !Number.isSafeInteger(profile.id) || typeof profile.login!=='string') fail(502,'无法验证 GitHub 身份。');
  // Only the public identity is used. OAuth access tokens are never stored or sent to the browser.
  const uid=`github:${profile.id}`,raw=token(),csrf=token();
  await env.DB.batch([
    stmt(env,"INSERT INTO users(id,kind,display_name,created_at) VALUES(?,'github',?,?) ON CONFLICT(id) DO UPDATE SET display_name=excluded.display_name",uid,profile.login,now()),
    stmt(env,"INSERT INTO identities(provider,subject,user_id) VALUES('github',?,?) ON CONFLICT(provider,subject) DO NOTHING",String(profile.id),uid),
    stmt(env,'INSERT INTO sessions(token_hash,user_id,csrf,expires_at) VALUES(?,?,?,?)',await digest(raw),uid,csrf,Date.now()+30*DAY),
  ]);
  const headers=new Headers({Location:new URL(saved.return_path+'#comments',env.BLOG_ORIGIN).href});
  headers.append('Set-Cookie',cookie(cookieName(env),raw,30*86400,env));
  headers.append('Set-Cookie',cookie(stateName(env),'',0,env));
  return new Response(null,{status:302,headers});
}

export default {
  async fetch(req,env) {
    const origin=req.headers.get('Origin'),url=new URL(req.url);
    let response;
    try {
      if (origin && !allowed(origin,env)) fail(403,'不允许的来源。');
      if (!['GET','HEAD','OPTIONS'].includes(req.method) && !allowed(origin,env)) fail(403,'不允许的来源。');
      if (req.method==='OPTIONS') response=new Response(null,{status:204});
      else if (url.pathname==='/health' && req.method==='GET') { await one(env,'SELECT 1 AS ok'); response=json({ok:true}); }
      else if (url.pathname==='/v1/session' && req.method==='GET') {
        const user=await session(req,env);
        response=json({user:viewUser(user),csrf:user?.csrf || null,githubEnabled:!!(env.GITHUB_CLIENT_ID&&env.GITHUB_CLIENT_SECRET),turnstileSiteKey:env.TURNSTILE_SITE_KEY || null});
      }
      else if (url.pathname==='/v1/comments' && req.method==='GET') response=await feed(url,req,env);
      else if (url.pathname==='/v1/comments' && req.method==='POST') response=await createComment(req,env);
      else if (/^\/v1\/comments\/[^/]+$/.test(url.pathname) && req.method==='DELETE') response=await changeComment(req,env,url.pathname.split('/').at(-1),false);
      else if (url.pathname==='/v1/admin/comments' && req.method==='GET') response=await adminFeed(url,req,env);
      else if (/^\/v1\/admin\/comments\/[^/]+$/.test(url.pathname) && req.method==='PATCH') response=await changeComment(req,env,url.pathname.split('/').at(-1),true);
      else if (url.pathname==='/auth/github' && req.method==='GET') response=await login(url,req,env);
      else if (url.pathname==='/auth/github/callback' && req.method==='GET') response=await callback(url,req,env);
      else if (url.pathname==='/v1/logout' && req.method==='POST') {
        const user=await session(req,env);requireUser(user,req);
        await stmt(env,'DELETE FROM sessions WHERE token_hash=?',user.token_hash).run();
        response=json({ok:true},200,{'Set-Cookie':cookie(cookieName(env),'',0,env)});
      } else fail(404,'接口不存在。');
    } catch(e) {
      if (!e.status) console.error('comments request failed',e.name); // Never log tokens, IPs or request bodies.
      response=json({error:e.status?e.message:'评论服务暂时不可用，请稍后重试。'},e.status || 503);
    }
    const headers=new Headers(response.headers);
    headers.set('Cache-Control','no-store');headers.set('X-Content-Type-Options','nosniff');headers.set('Referrer-Policy','no-referrer');
    if (origin && allowed(origin,env)) {headers.set('Access-Control-Allow-Origin',origin);headers.set('Access-Control-Allow-Credentials','true');headers.set('Vary','Origin');}
    headers.set('Access-Control-Allow-Methods','GET,POST,PATCH,DELETE,OPTIONS');headers.set('Access-Control-Allow-Headers','Content-Type,X-CSRF-Token');
    if (response.status===429) headers.set('Retry-After','60');
    return new Response(response.body,{status:response.status,headers});
  },
  async scheduled(_event,env) {
    await env.DB.batch(['sessions','oauth_states','rate_limits'].map(t=>stmt(env,`DELETE FROM ${t} WHERE expires_at < ?`,Date.now())));
  },
};
