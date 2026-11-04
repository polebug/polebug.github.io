export {};
interface User { id: string; name: string; kind: string; admin: boolean }
interface Comment { id: string; parentId: string | null; body: string; author: {name: string; kind: string; owner: boolean}; createdAt: string; status: string; mine: boolean; sourceUrl?: string; title?: string }
interface Session { user: User | null; csrf: string | null; githubEnabled: boolean; turnstileSiteKey: string | null }
interface Feed { comments: Comment[]; total: number; nextCursor: string | null; writable: boolean }
interface Turnstile { render(el: HTMLElement, options: Record<string,unknown>): string; reset(id: string): void }
declare global { interface Window { turnstile?: Turnstile } }
const root = document.querySelector<HTMLElement>('.native-comments');
if (root) init(root);
function init(root: HTMLElement) {
  const api = root.dataset.api!, documentId = root.dataset.document!;
  const el = <T extends HTMLElement = HTMLElement>(s: string) => root.querySelector<T>(s)!;
  const form = el<HTMLFormElement>('.comment-form');
  const input = form.elements.namedItem('body') as HTMLTextAreaElement;
  const name = form.elements.namedItem('name') as HTMLInputElement;
  const submit = el<HTMLButtonElement>('.submit-comment');
  const formStatus = el('.form-status'), feedStatus = el('.feed-status');
  let auth: Session = {user:null,csrf:null,githubEnabled:false,turnstileSiteKey:null};
  let nextCursor: string | null = null, adminCursor: string | null = null, parentId: string | null = null;
  let widget: string | undefined, challenge = '', challengeLoad: Promise<void> | null = null;
  let sending = false, writable = false;
  let requestId = crypto.randomUUID();
  const comments = new Map<string,Comment>();
  const draftKey = `comment-draft:${documentId}`;
  try { input.value = sessionStorage.getItem(draftKey) || ''; } catch {}
  input.addEventListener('input',()=>{requestId=crypto.randomUUID();try{sessionStorage.setItem(draftKey,input.value);}catch{}});
  async function request<T>(path:string, options:RequestInit = {}):Promise<T> {
    const headers = new Headers(options.headers);
    if (options.body) headers.set('Content-Type','application/json');
    if (options.method && options.method!=='GET' && auth.csrf) headers.set('X-CSRF-Token',auth.csrf);
    const response = await fetch(api+path,{...options,headers,credentials:'include',signal:AbortSignal.timeout(12000)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || '暂时无法加载，请稍后重试。');
    return data;
  }
  const errorText=(e:unknown)=>e instanceof Error && e.name==='Error' ? e.message : '连接超时或网络不可用，请稍后重试。';
  function showSession() {
    el('.identity').textContent=auth.user ? `${auth.user.name}${auth.user.kind==='guest'?' · 访客':''}` : '访客评论';
    el('.github-login').hidden=!auth.githubEnabled || auth.user?.kind==='github';
    el('.logout').hidden=!auth.user;
    el('.guest-name').hidden=!!auth.user;
    el('.guest-notice').hidden=auth.user?.kind==='github';
    el('.human-check').hidden=auth.user?.kind==='github';
    el('.show-admin').hidden=!auth.user?.admin;
  }
  let sessionLoaded=false;
  async function loadSession(){auth=await request<Session>('/v1/session');sessionLoaded=true;showSession();}
  const sessionReady=loadSession().catch(e=>{formStatus.textContent=errorText(e);});
  async function ensureSession(){await sessionReady;if(!sessionLoaded)await loadSession();}
  function action(label:string,run:()=>Promise<void>|void) {
    const b=document.createElement('button');b.type='button';b.textContent=label;
    b.addEventListener('click',async()=>{b.disabled=true;try{await run();}catch(e){formStatus.textContent=errorText(e);el('.admin-status').textContent=errorText(e);}finally{b.disabled=false;}});
    return b;
  }
  function render(c:Comment,admin=false) {
    const li=document.createElement('li');li.className='comment-item';
    const by=document.createElement('div');by.className='comment-byline';
    const author=document.createElement('strong');author.textContent=c.author.name;
    const badge=document.createElement('span');badge.className='comment-badge';badge.textContent=c.author.owner?'博主':c.author.kind==='guest'?'访客':c.author.kind==='github'?'GitHub':'历史评论';
    const time=document.createElement('time');time.dateTime=c.createdAt;time.textContent=new Date(c.createdAt).toLocaleString('zh-CN',{year:'numeric',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
    by.append(author,badge,time);li.append(by);
    if(c.title){const title=document.createElement('p');title.textContent=c.title;title.className='parent-label';li.append(title);}
    if(c.parentId){const reply=document.createElement('p');reply.className='parent-label';reply.textContent=comments.has(c.parentId)?`回复 ${comments.get(c.parentId)!.author.name}`:'回复较早的评论';li.append(reply);}
    const content=document.createElement('p');content.className='comment-body';content.textContent=c.status==='deleted'&&!admin?'这条评论已删除。':c.body;li.append(content);
    const actions=document.createElement('div');actions.className='comment-actions';
    if(!admin&&c.status==='published'&&writable)actions.append(action('回复',()=>{parentId=c.id;requestId=crypto.randomUUID();el('.reply-to').hidden=false;el('.reply-to span').textContent=`回复 ${c.author.name}`;input.focus();}));
    if(!admin&&c.mine&&c.status!=='deleted')actions.append(action('删除',async()=>{await request(`/v1/comments/${c.id}`,{method:'DELETE'});await loadFeed();}));
    if(admin){
      if(c.status!=='published')actions.append(action('发布',async()=>{await moderate(c,'published');}));
      if(c.status!=='hidden')actions.append(action('隐藏',async()=>{await moderate(c,'hidden');}));
      if(c.status!=='deleted')actions.append(action('删除',async()=>{await moderate(c,'deleted');}));
    }
    if(c.sourceUrl?.startsWith('https://github.com/polebug/polebug.github.io/issues/')){const a=document.createElement('a');a.className='comment-source';a.textContent='原评论';a.href=c.sourceUrl;a.target='_blank';a.rel='noopener noreferrer';actions.append(a);}
    li.append(actions);return li;
  }
  async function loadFeed(more=false) {
    el('.feed-retry').hidden=true;el<HTMLButtonElement>('.load-more').disabled=true;
    try {
      const data=await request<Feed>(`/v1/comments?document=${encodeURIComponent(documentId)}${more&&nextCursor?`&cursor=${encodeURIComponent(nextCursor)}`:''}`);
      writable=data.writable;submit.disabled=!writable;
      if(!more){el('.comment-list').replaceChildren();comments.clear();}
      for(const c of data.comments)comments.set(c.id,c);
      for(const c of data.comments)el('.comment-list').append(render(c));
      nextCursor=data.nextCursor;el('.load-more').hidden=!nextCursor;
      el('.native-count').textContent=String(data.total);
      document.querySelectorAll('.comment-count').forEach(node=>node.textContent=String(data.total));
      feedStatus.textContent=data.total?'':'还没有评论，来聊聊吧。';
      if(!writable)formStatus.textContent='这篇文章暂不接受新评论。';
    } catch(e){feedStatus.textContent=errorText(e);el('.feed-retry').hidden=false;}
    finally{el<HTMLButtonElement>('.load-more').disabled=false;}
  }
  async function ensureChallenge() {
    await ensureSession();
    if(auth.user?.kind==='github'||widget!==undefined)return;
    if(!auth.turnstileSiteKey){formStatus.textContent='访客评论暂不可用，请使用 GitHub 登录。';return;}
    if(!challengeLoad)challengeLoad=new Promise<void>((resolve,reject)=>{
      if(window.turnstile){resolve();return;}
      const script=document.createElement('script');script.src='https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';script.async=true;
      script.onload=()=>resolve();script.onerror=()=>{script.remove();challengeLoad=null;reject(new Error('人机校验未能加载，请重试或使用 GitHub 登录。'));};document.head.append(script);
    });
    await challengeLoad;
    if(widget!==undefined)return;
    widget=window.turnstile!.render(el('.human-check'),{sitekey:auth.turnstileSiteKey,action:'comment',size:'flexible',theme:'auto',callback:(value:string)=>{challenge=value;},'expired-callback':()=>{challenge='';},'error-callback':()=>{challenge='';formStatus.textContent='人机校验未完成，请重试或使用 GitHub 登录。';}});
  }
  input.addEventListener('focus',()=>{ensureChallenge().catch(e=>{formStatus.textContent=errorText(e);});});
  el('.cancel-reply').addEventListener('click',()=>{parentId=null;requestId=crypto.randomUUID();el('.reply-to').hidden=true;});
  form.addEventListener('submit',async event=>{
    event.preventDefault();if(sending||!writable)return;
    sending=true;submit.disabled=true;formStatus.textContent='';
    try{
      await ensureSession();
      if(auth.user?.kind!=='github'){await ensureChallenge();if(!challenge)throw new Error('请先完成人机校验，再发送评论。');}
      const data=await request<{status:string;user:User;csrf:string}>('/v1/comments',{method:'POST',body:JSON.stringify({documentId,body:input.value,name:name.value,parentId,requestId,turnstileToken:challenge})});
      auth.user=data.user;auth.csrf=data.csrf;showSession();input.value='';parentId=null;el('.reply-to').hidden=true;requestId=crypto.randomUUID();
      try{sessionStorage.removeItem(draftKey);}catch{}
      formStatus.textContent=data.status==='pending'?'已收到，审核后会公开显示。':'评论已发布。';
      await loadFeed();
    }catch(e){formStatus.textContent=errorText(e);}
    finally{sending=false;submit.disabled=!writable;challenge='';if(widget!==undefined)window.turnstile?.reset(widget);}
  });
  el('.logout').addEventListener('click',async()=>{try{await request('/v1/logout',{method:'POST'});auth.user=null;auth.csrf=null;showSession();el('.admin-list').replaceChildren();el('.public-panel').hidden=false;el('.admin-panel').hidden=true;await loadFeed();}catch(e){formStatus.textContent=errorText(e);}});
  el('.feed-retry').addEventListener('click',()=>{loadFeed();if(!sessionLoaded)loadSession().catch(e=>{formStatus.textContent=errorText(e);});});
  el('.load-more').addEventListener('click',()=>{loadFeed(true);});
  async function loadAdmin(more=false){
    const status=el<HTMLSelectElement>('.moderation-filter').value;
    el('.admin-status').textContent='正在读取…';
    try{
      const data=await request<{comments:Comment[];nextCursor:string|null}>(`/v1/admin/comments?status=${status}${more&&adminCursor?`&cursor=${encodeURIComponent(adminCursor)}`:''}`);
      if(!more)el('.admin-list').replaceChildren();
      for(const c of data.comments)el('.admin-list').append(render(c,true));adminCursor=data.nextCursor;el('.admin-more').hidden=!adminCursor;
      el('.admin-status').textContent=el('.admin-list').children.length?'':'没有这类评论。';
    }catch(e){el('.admin-status').textContent=errorText(e);}
  }
  async function moderate(c:Comment,status:string){await request(`/v1/admin/comments/${c.id}`,{method:'PATCH',body:JSON.stringify({status})});await loadAdmin();await loadFeed();}
  el('.show-admin').addEventListener('click',()=>{el('.public-panel').hidden=true;el('.admin-panel').hidden=false;el('.show-admin').classList.add('selected');el('.show-public').classList.remove('selected');loadAdmin();});
  el('.show-public').addEventListener('click',()=>{el('.public-panel').hidden=false;el('.admin-panel').hidden=true;el('.show-admin').classList.remove('selected');el('.show-public').classList.add('selected');});
  el('.moderation-filter').addEventListener('change',()=>{loadAdmin();});el('.admin-more').addEventListener('click',()=>{loadAdmin(true);});
  // A single direct API request warms the list; opening/closing the drawer never rebuilds it.
  loadFeed();
  if(location.hash==='#comments')requestAnimationFrame(()=>document.querySelector<HTMLButtonElement>('.talk-open')?.click());
}
