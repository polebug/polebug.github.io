export {};
interface User { id: string; name: string; kind: string; admin: boolean }
interface Comment { id: string; parentId: string | null; body: string; author: {name: string; kind: string; owner: boolean}; createdAt: string; status: string; mine: boolean; sourceUrl?: string; title?: string }
interface Session { user: User | null; csrf: string | null; githubEnabled: boolean; turnstileSiteKey: string | null; verificationRequired: boolean; humanVerifiedUntil: number }
interface Feed { comments: Comment[]; total: number; nextCursor: string | null; writable: boolean }
interface Turnstile { render(el: HTMLElement, options: Record<string,unknown>): string; remove(id: string): void }
declare global { interface Window { turnstile?: Turnstile } }
const root = document.querySelector<HTMLElement>('.native-comments');
if (root) init(root);
function init(root: HTMLElement) {
  const api = root.dataset.api!, documentId = root.dataset.document!;
  const el = <T extends HTMLElement = HTMLElement>(s: string) => root.querySelector<T>(s)!;
  const form = el<HTMLFormElement>('.comment-form');
  const composerHome = el('.composer-home');
  const input = form.elements.namedItem('body') as HTMLTextAreaElement;
  const name = form.elements.namedItem('name') as HTMLInputElement;
  const submit = el<HTMLButtonElement>('.submit-comment');
  const formStatus = el('.form-status'), feedStatus = el('.feed-status');
  let auth: Session = {user:null,csrf:null,githubEnabled:false,turnstileSiteKey:null,verificationRequired:true,humanVerifiedUntil:0};
  let nextCursor: string | null = null, adminCursor: string | null = null, parentId: string | null = null;
  let widget: string | undefined, challengeLoad: Promise<void> | null = null;
  let sending = false, writable = false;
  let requestId = crypto.randomUUID();
  const comments = new Map<string,Comment>();
  const draftKey = `comment-draft:${documentId}`;
  const replyDraftKey = `${draftKey}:reply`;
  try { input.value = sessionStorage.getItem(draftKey) || ''; } catch {}
  function feedback(message='',tone='') { formStatus.textContent=message;formStatus.dataset.tone=tone; }
  function updateComposer() {
    submit.disabled=sending||!writable||!input.value.trim();
    el('.submit-label').textContent=sending?'发送中…':parentId?'发送回复':'发送评论';
    form.setAttribute('aria-busy',String(sending));
    el<HTMLButtonElement>('.logout').disabled=sending;
    el<HTMLAnchorElement>('.github-login').setAttribute('aria-disabled',String(sending));
    const count=el('.character-count');count.hidden=input.value.length<5400;
    count.textContent=`${input.value.length} / 6000`;
    el('.keyboard-hint').hidden=!count.hidden;
    // The drawer may be closed when data arrives; resize again when it opens.
    if(input.getClientRects().length){input.style.height='auto';input.style.height=`${Math.min(parseFloat(getComputedStyle(input).maxHeight),input.scrollHeight)}px`;}
  }
  function placeComposer() {
    const target = !el('.public-panel').hidden && parentId
      ? Array.from(el('.comment-list').querySelectorAll<HTMLElement>('.comment-item')).find(node=>node.dataset.commentId===parentId)
      : null;
    if(target) target.insertBefore(form,target.querySelector(':scope > .comment-replies'));
    else composerHome.append(form);
    composerHome.hidden=!!target;
    form.classList.toggle('inline-reply',!!target);
  }
  function focusComposer() {
    input.focus({preventScroll:true});
    form.scrollIntoView({block:'nearest'});
  }
  function setReply(c:Pick<Comment,'id'|'author'|'body'>|null,save=true) {
    parentId=c?.id??null;requestId=crypto.randomUUID();
    el('.reply-to').hidden=!c;
    el('.reply-name').textContent=c?`回复 ${c.author.name}`:'';
    el('.reply-excerpt').textContent=c?.body.replace(/\s+/g,' ').slice(0,180)??'';
    input.placeholder=c?`回复 ${c.author.name}…`:'聊聊你的想法…';
    if(save)try{if(c)sessionStorage.setItem(replyDraftKey,JSON.stringify({id:c.id,author:c.author,body:c.body.slice(0,180)}));else sessionStorage.removeItem(replyDraftKey);}catch{}
    placeComposer();feedback();updateComposer();
  }
  // OAuth navigation or a refresh must not silently turn a reply draft into a new thread.
  try {
    const draft=JSON.parse(sessionStorage.getItem(replyDraftKey)||'null');
    if(draft&&typeof draft.id==='string'&&typeof draft.author?.name==='string'&&typeof draft.body==='string')setReply(draft,false);
  } catch {}
  input.addEventListener('input',()=>{requestId=crypto.randomUUID();feedback();updateComposer();try{sessionStorage.setItem(draftKey,input.value);}catch{}});
  name.addEventListener('input',()=>{requestId=crypto.randomUUID();feedback();});
  input.addEventListener('keydown',event=>{if(!event.isComposing&&(event.metaKey||event.ctrlKey)&&event.key==='Enter'){event.preventDefault();if(!submit.disabled)form.requestSubmit();}});
  el('.github-login').addEventListener('click',event=>{if(sending)event.preventDefault();});
  new ResizeObserver(()=>{if(input.getClientRects().length)updateComposer();}).observe(form);
  updateComposer();
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
    el('.identity').textContent=auth.user ? `${auth.user.name}${auth.user.kind==='guest'?' · 访客':''}` : '访客';
    el('.identity').hidden=!auth.user;
    el('.identity-avatar').textContent=Array.from(auth.user?.name||'访')[0].toUpperCase();
    el('.github-login').hidden=!auth.githubEnabled || auth.user?.kind==='github';
    el('.logout').hidden=!auth.user;
    el('.logout').textContent=auth.user?.kind==='guest'?'换个昵称':'退出登录';
    el('.guest-name').hidden=!!auth.user;
    el('.guest-notice').hidden=auth.user?.kind==='github';
    if(!auth.verificationRequired)clearChallenge();
    el('.show-admin').hidden=!auth.user?.admin;
  }
  let sessionLoaded=false;
  async function loadSession(){auth=await request<Session>('/v1/session');sessionLoaded=true;showSession();}
  const sessionReady=loadSession().catch(e=>{feedback(errorText(e),'error');});
  async function ensureSession(){await sessionReady;if(!sessionLoaded)await loadSession();}
  function action(label:string,run:()=>Promise<void>|void) {
    const b=document.createElement('button');b.type='button';b.textContent=label;
    b.addEventListener('click',async()=>{if(sending)return;b.disabled=true;try{await run();}catch(e){feedback(errorText(e),'error');el('.admin-status').textContent=errorText(e);}finally{b.disabled=false;}});
    return b;
  }
  function render(c:Comment,admin=false) {
    const li=document.createElement('li');li.className='comment-item';li.dataset.commentId=c.id;
    const avatar=document.createElement('span');avatar.className=`comment-avatar${c.author.owner?' owner':''}`;avatar.textContent=Array.from(c.author.name)[0]?.toUpperCase()||'访';avatar.setAttribute('aria-hidden','true');li.append(avatar);
    const by=document.createElement('div');by.className='comment-byline';
    const author=document.createElement('strong');author.textContent=c.author.name;
    const badge=document.createElement('span');badge.className=`comment-badge${c.author.owner?' owner':''}`;badge.textContent=c.author.owner?'博主':c.author.kind==='guest'?'访客':c.author.kind==='github'?'GitHub':'历史评论';
    const time=document.createElement('time');time.dateTime=c.createdAt;time.textContent=new Date(c.createdAt).toLocaleString('zh-CN',{year:'numeric',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
    by.append(author,badge);li.append(by,time);
    if(c.title){const title=document.createElement('p');title.textContent=c.title;title.className='parent-label';li.append(title);}
    if(c.parentId){const reply=document.createElement('p');reply.className='parent-label';reply.textContent=comments.has(c.parentId)?`回复 ${comments.get(c.parentId)!.author.name}`:'回复较早的评论';li.append(reply);}
    const content=document.createElement('p');content.className='comment-body';content.textContent=c.status==='deleted'&&!admin?'这条评论已删除。':c.body;li.append(content);
    const actions=document.createElement('div');actions.className='comment-actions';
    if(!admin&&c.status==='published'&&writable)actions.append(action('回复',()=>{if(sending)return;setReply(c);focusComposer();}));
    if(!admin&&c.mine&&c.status!=='deleted')actions.append(action('删除',async()=>{await request(`/v1/comments/${c.id}`,{method:'DELETE'});await loadFeed();}));
    if(admin){
      if(c.status!=='published')actions.append(action('发布',async()=>{await moderate(c,'published');}));
      if(c.status!=='hidden')actions.append(action('隐藏',async()=>{await moderate(c,'hidden');}));
      if(c.status!=='deleted')actions.append(action('删除',async()=>{await moderate(c,'deleted');}));
    }
    if(c.sourceUrl?.startsWith('https://github.com/polebug/polebug.github.io/issues/')){const a=document.createElement('a');a.className='comment-source';a.textContent='原评论';a.href=c.sourceUrl;a.target='_blank';a.rel='noopener noreferrer';actions.append(a);}
    li.append(actions);return li;
  }
  function renderThreads() {
    // Keep every conversation together, with one indentation level even for replies to replies.
    const threads=new Map<string,{root:Comment;replies:Comment[]}>();
    for(const c of comments.values()) {
      let first=c;
      const seen=new Set([c.id]);
      while(first.parentId&&comments.has(first.parentId)) {
        if(seen.has(first.parentId)){first=c;break;}
        seen.add(first.parentId);first=comments.get(first.parentId)!;
      }
      if(!threads.has(first.id))threads.set(first.id,{root:first,replies:[]});
      if(c.id!==first.id)threads.get(first.id)!.replies.push(c);
    }
    const fragment=document.createDocumentFragment();
    for(const {root:parent,replies} of threads.values()) {
      const thread=render(parent);
      if(replies.length) {
        const list=document.createElement('ol');list.className='comment-replies';
        list.setAttribute('aria-label',`回复 ${parent.author.name} 的讨论`);
        for(const reply of replies)list.append(render(reply));
        thread.append(list);
      }
      fragment.append(thread);
    }
    // Move the existing form out before replacing the list: preserve its draft,
    // event handlers and verification widget through feed refreshes.
    composerHome.append(form);
    el('.comment-list').replaceChildren(fragment);
    placeComposer();
  }
  async function loadFeed(more=false) {
    el('.feed-retry').hidden=true;el<HTMLButtonElement>('.load-more').disabled=true;
    try {
      const data=await request<Feed>(`/v1/comments?document=${encodeURIComponent(documentId)}${more&&nextCursor?`&cursor=${encodeURIComponent(nextCursor)}`:''}`);
      writable=data.writable;updateComposer();
      if(!more)comments.clear();
      for(const c of data.comments)comments.set(c.id,c);
      const scrollTop=el('.public-panel').scrollTop;
      renderThreads();
      el('.public-panel').scrollTop=scrollTop;
      nextCursor=data.nextCursor;el('.load-more').hidden=!nextCursor;
      el('.native-count').textContent=String(data.total);
      document.querySelectorAll('.comment-count').forEach(node=>node.textContent=String(data.total));
      feedStatus.textContent=data.total?'':'还没有评论，来聊聊吧。';
      if(!writable)formStatus.textContent='这篇文章暂不接受新评论。';
    } catch(e){feedStatus.textContent=errorText(e);el('.feed-retry').hidden=false;}
    finally{el<HTMLButtonElement>('.load-more').disabled=false;}
  }
  function clearChallenge() {
    if(widget!==undefined)window.turnstile?.remove(widget);
    widget=undefined;el('.human-check').hidden=true;
  }
  async function verifyGuest():Promise<string> {
    if(!auth.verificationRequired)return '';
    if(!auth.turnstileSiteKey)throw new Error('访客评论暂不可用，请使用 GitHub 登录。');
    feedback('正在验证，完成后自动发送…');
    if(!challengeLoad)challengeLoad=new Promise<void>((resolve,reject)=>{
      if(window.turnstile){resolve();return;}
      const script=document.createElement('script');script.src='https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';script.async=true;
      const failed=()=>{clearTimeout(timer);script.remove();challengeLoad=null;reject(new Error('人机校验未能加载，请重试或使用 GitHub 登录。'));};
      const timer=setTimeout(failed,15000);
      script.onload=()=>{clearTimeout(timer);resolve();};script.onerror=failed;document.head.append(script);
    });
    await challengeLoad;
    clearChallenge();el('.human-check').hidden=false;
    return new Promise<string>((resolve,reject)=>{
      let settled=false;
      const finish=(value:string,error?:string)=>{if(settled)return;settled=true;clearTimeout(timer);error?reject(new Error(error)):resolve(value);};
      const timer=setTimeout(()=>finish('','验证超时，请重新发送或使用 GitHub 登录。'),90000);
      try {
        widget=window.turnstile!.render(el('.human-check'),{
          sitekey:auth.turnstileSiteKey,action:'comment',size:'flexible',theme:'auto',appearance:'interaction-only',
          retry:'never','refresh-expired':'manual','refresh-timeout':'manual',
          callback:(value:string)=>finish(value),
          'expired-callback':()=>finish('','验证已过期，请重新发送。'),
          'timeout-callback':()=>finish('','验证超时，请重新发送。'),
          'error-callback':()=>finish('','人机校验未完成，请重试或使用 GitHub 登录。'),
        });
      } catch { finish('','人机校验未能加载，请重新发送。'); }
    });
  }
  el('.cancel-reply').addEventListener('click',()=>{if(sending)return;setReply(null);focusComposer();});
  form.addEventListener('submit',async event=>{
    event.preventDefault();if(sending||!writable||!input.value.trim())return;
    if(sessionLoaded&&!auth.user&&!name.value.trim()){feedback('先填一个昵称吧。','error');name.focus();return;}
    const wasReply=!!parentId;
    sending=true;updateComposer();input.disabled=true;name.disabled=true;el<HTMLButtonElement>('.cancel-reply').disabled=true;feedback();
    try{
      await ensureSession();
      await loadSession();
      if(!auth.user && !name.value.trim())throw new Error('请先填写昵称。');
      const challenge=await verifyGuest();
      feedback('正在发送…');
      const data=await request<{id:string;status:string;user:User;csrf:string;verificationRequired:boolean;humanVerifiedUntil:number}>('/v1/comments',{method:'POST',body:JSON.stringify({documentId,body:input.value,name:name.value,parentId,requestId,turnstileToken:challenge})});
      auth.user=data.user;auth.csrf=data.csrf;auth.verificationRequired=data.verificationRequired;auth.humanVerifiedUntil=data.humanVerifiedUntil;showSession();input.value='';setReply(null);
      try{sessionStorage.removeItem(draftKey);}catch{}
      await loadFeed();
      feedback('✓ 已发布，谢谢你的分享。','success');
      const posted=Array.from(el('.comment-list').querySelectorAll<HTMLElement>('.comment-item')).find(node=>node.dataset.commentId===data.id);
      posted?.classList.add('just-posted');
      if(wasReply&&posted){posted.tabIndex=-1;posted.focus({preventScroll:true});posted.scrollIntoView({block:'nearest'});}
      else{formStatus.focus({preventScroll:true});formStatus.scrollIntoView({block:'nearest'});}
    }catch(e){feedback(errorText(e),'error');}
    finally{sending=false;input.disabled=false;name.disabled=false;el<HTMLButtonElement>('.cancel-reply').disabled=false;clearChallenge();updateComposer();if(!auth.user&&!name.value.trim())name.focus();}
  });
  function showPanel(admin:boolean) {
    el('.public-panel').hidden=admin;el('.admin-panel').hidden=!admin;
    placeComposer();updateComposer();
    el('.show-admin').classList.toggle('selected',admin);el('.show-public').classList.toggle('selected',!admin);
    el('.show-admin').setAttribute('aria-pressed',String(admin));el('.show-public').setAttribute('aria-pressed',String(!admin));
  }
  el('.logout').addEventListener('click',async()=>{if(sending)return;const guestName=auth.user?.kind==='guest'?auth.user.name:null;try{await request('/v1/logout',{method:'POST'});auth.user=null;auth.csrf=null;auth.verificationRequired=true;auth.humanVerifiedUntil=0;clearChallenge();showSession();feedback();el('.admin-list').replaceChildren();showPanel(false);if(guestName!==null){name.value=guestName;name.focus({preventScroll:true});name.select();}await loadFeed();}catch(e){feedback(errorText(e),'error');}});
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
  el('.show-admin').addEventListener('click',()=>{showPanel(true);loadAdmin();});
  el('.show-public').addEventListener('click',()=>{showPanel(false);});
  el('.moderation-filter').addEventListener('change',()=>{loadAdmin();});el('.admin-more').addEventListener('click',()=>{loadAdmin(true);});
  // A single direct API request warms the list; opening/closing the drawer never rebuilds it.
  loadFeed();
  if(location.hash==='#comments')requestAnimationFrame(()=>document.querySelector<HTMLButtonElement>('.talk-open')?.click());
}
