/* Bangla Bhai v3 shell (prototype). Vanilla JS, one file, ~no deps besides marked+DOMPurify already used by /app. */
'use strict';
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const bnNum=n=>String(n).replace(/\d/g,d=>'০১২৩৪৫৬৭৮৯'[d]);
const IC={
 chat:'<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/>',
 spark:'<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
 bot:'<rect x="4" y="8" width="16" height="12" rx="3"/><path d="M12 4v4M9 14h.01M15 14h.01"/><path d="M2 13v2M22 13v2"/>',
 list:'<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r="1"/><circle cx="4.5" cy="12" r="1"/><circle cx="4.5" cy="18" r="1"/>',
 user:'<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
 send:'<path d="M5 12h14M13 6l6 6-6 6"/>', stop:'<rect x="6" y="6" width="12" height="12" rx="2"/>',
 plus:'<path d="M12 5v14M5 12h14"/>', mic:'<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
 clip:'<path d="M21 11l-8.5 8.5a5 5 0 0 1-7-7L14 4a3.5 3.5 0 0 1 5 5l-8.5 8.5a2 2 0 0 1-3-3L15 7"/>',
 menu:'<path d="M4 7h16M4 12h16M4 17h10"/>', edit:'<path d="M4 20h4L19 9l-4-4L4 16z"/>', back:'<path d="M15 6l-6 6 6 6"/>',
 moon:'<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>', sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
 search:'<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>', copy:'<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>',
 redo:'<path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7"/>', speaker:'<path d="M4 9v6h4l5 4V5L8 9z"/><path d="M16 9a4 4 0 0 1 0 6"/>', play:'<path d="M7 5l12 7-12 7z"/>',
 shield:'<path d="M12 3l8 3v6c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6z"/>'};
const svg=(n,c='')=>`<svg class="${c}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${IC[n]}</svg>`;
async function api(u,o={}){const r=await fetch(u,{credentials:'same-origin',headers:{'Content-Type':'application/json'},...o});
 if(r.status===401){location.href='/login';throw new Error('login')}let j={};try{j=await r.json()}catch(e){}
 if(!r.ok){const e=new Error(j.hint||j.error||('HTTP '+r.status));e.data=j;e.status=r.status;throw e}return j}
function toast(t){const e=$('#toast');e.textContent=t;e.classList.add('on');clearTimeout(e._t);e._t=setTimeout(()=>e.classList.remove('on'),2400)}
function md(t){const h=window.marked&&window.DOMPurify?DOMPurify.sanitize(marked.parse(t||'')):esc(t).replace(/\n/g,'<br>');const d=document.createElement('div');d.innerHTML=h;d.querySelectorAll('a').forEach(a=>{a.target='_blank';a.rel='noopener'});return d}
const ago=ts=>{const s=Date.now()/1000-ts;if(s<60)return 'এইমাত্র';if(s<3600)return bnNum(Math.floor(s/60))+' মিনিট আগে';if(s<86400)return bnNum(Math.floor(s/3600))+' ঘণ্টা আগে';return bnNum(Math.floor(s/86400))+' দিন আগে'};
/* ---------- state ---------- */
const ST={activeAgent:null,me:{},skills:[],cats:[],agents:[],tiers:{},perms:{},canTools:false,chat:null,activeSkill:null,ctrl:null};
const TABS=[['chat','/v3','চ্যাট'],['spark','/v3/skills','স্কিল'],['bot','/v3/agents','এজেন্ট'],['list','/v3/activity','কার্যকলাপ'],['user','#me','আমি']];
function navHTML(cls){return TABS.map(([i,h,l])=>`<a href="${h}" data-nav="${h}">${svg(i)}<span>${l}</span>${h==='/v3/activity'?'<i class="badge" hidden></i>':''}</a>`).join('')}
function paintNav(){const p=location.pathname.replace(/\/$/,'')||'/v3';$$('[data-nav]').forEach(a=>{const h=a.dataset.nav;a.classList.toggle('on',h===p||(h!=='/v3'&&h!=='#me'&&p.startsWith(h)))})}
document.addEventListener('click',e=>{const a=e.target.closest('a[href]');if(!a)return;const h=a.getAttribute('href');
 if(h==='#me'){e.preventDefault();return openMe()}
 if(h.startsWith('/v3')){e.preventDefault();go(h)}});
function go(h,replace){history[replace?'replaceState':'pushState']({},'',h);route()}
addEventListener('popstate',route);
function route(){const p=location.pathname.replace(/\/$/,'');paintNav();closeSheet();
 if(p==='/v3/skills')return pgSkills();if(p==='/v3/agents')return pgAgents();const m=p.match(/^\/v3\/agents\/(\w+)/);if(m)return pgAgent(m[1]);
 if(p==='/v3/activity')return pgActivity();return pgChat()}
/* ---------- sheet ---------- */
function openSheet(html,after){$('#sheet').innerHTML='<div class=grab></div>'+html;$('#scrim').classList.add('on');after&&after($('#sheet'))}
function closeSheet(){$('#scrim').classList.remove('on')}
$('#scrim').addEventListener('click',e=>{if(e.target.id==='scrim')closeSheet()});
addEventListener('keydown',e=>{if(e.key==='Escape')closeSheet()});
/* ---------- theme ---------- */
function setTheme(t){localStorage.bbTheme=t;document.documentElement.dataset.theme=t==='system'?(matchMedia('(prefers-color-scheme: light)').matches?'light':'dark'):t;
 $('meta[name=theme-color]').content=getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()}
function themeBtn(){const l=document.documentElement.dataset.theme==='light';return `<button class=ib aria-label="থিম বদলান" onclick="setTheme('${l?'dark':'light'}');route()">${svg(l?'moon':'sun')}</button>`}
/* ---------- top bar helpers ---------- */
const topbar=(title,left='',right='')=>`<header class=top>${left}${title}${right}</header>`;
const brand=()=>`<div class=brandmark><img src="/bb/static/logo.png" alt=""><div><b>বাংলা ভাই</b><small>Royal Universe</small></div></div>`;
/* =============== CHAT =============== */
function pgChat(){
 const tier=localStorage.bbTier||'auto';
 $('#view').innerHTML=topbar(brand(),`<button class=ib aria-label="চ্যাটের তালিকা" onclick="openChats()">${svg('menu')}</button>`,
  `<button class=chip-sel onclick="pickTier()" aria-label="মডেল"><i></i>${esc({fast:'দ্রুত',auto:'অটো',deep:'গভীর'}[tier])}</button>${themeBtn()}<button class=ib aria-label="নতুন চ্যাট" onclick="newChat()">${svg('edit')}</button>`)+
  `<div class=page id=chatPage><div class=wrap id=msgs></div></div>
  <div id=composer><div class=ctx id=ctx></div><div class=cbox><div id=pillSlot></div><textarea id=inp rows=1 placeholder="বাংলা ভাইকে কিছু জিজ্ঞেস করুন…" aria-label="মেসেজ"></textarea>
  <div class=crow><button class=ib aria-label="স্কিল বেছে নিন" onclick="pickSkill()">${svg('spark')}</button><button class=ib aria-label="ফাইল যোগ করুন" onclick="toast('ফাইল আপলোড: আসল বিল্ডে /bb/api/upload ব্যবহার হবে')">${svg('clip')}</button>
  <button class=ib aria-label="ভয়েস" onclick="toast('ভয়েস ইনপুট: আসল বিল্ডে /bb/api/stt')">${svg('mic')}</button><span class=grow></span><button id=send aria-label="পাঠান" disabled>${svg('send')}</button></div></div></div>`;
 const inp=$('#inp');inp.addEventListener('input',()=>{inp.style.height='auto';inp.style.height=Math.min(inp.scrollHeight,180)+'px';$('#send').disabled=!inp.value.trim()&&!ST.ctrl});
 inp.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&innerWidth>900){e.preventDefault();send()}});
 $('#send').onclick=()=>ST.ctrl?ST.ctrl.abort():send();
 paintPill();paintCtx();
 if(ST.chat&&ST.chat.messages?.length){$('#msgs').innerHTML='';ST.chat.messages.forEach(addMsg);scrollEnd()}else hello()}
function hello(){const nm=ST.me.role==='owner'?'রয়েল':(ST.me.name||'');const en=ST.skills.filter(s=>s.enabled&&s.available).slice(0,4);
 $('#msgs').innerHTML=`<div class=hello><div class=orb><img src="/bb/static/logo.png" alt=""></div><h2>${nm?'আসসালামু আলাইকুম, '+esc(nm)+'!':'আসসালামু আলাইকুম!'}</h2><p>আজ কী করতে চান? লিখুন, বলুন, বা একটা স্কিল বেছে নিন।</p>
 <div class=qgrid>${en.map(s=>`<button class=q onclick="useSkill('${s.id}')"><span class=ic>${s.icon}</span><b>${esc(s.name_bn)}</b><span>${esc(s.desc_bn)}</span></button>`).join('')}</div></div>`}
function paintCtx(){const c=$('#ctx');if(!c)return;const en=ST.skills.filter(s=>s.enabled&&s.available);c.innerHTML=en.slice(0,8).map(s=>`<button onclick="useSkill('${s.id}')">${s.icon} ${esc(s.name_bn)}</button>`).join('')}
function paintPill(){const s=ST.activeSkill,g=ST.activeAgent;$('#pillSlot').innerHTML=(g?`<span class=skillpill>${esc(g.icon)} ${esc(g.name)}<button aria-label="এজেন্ট সরান" onclick="ST.activeAgent=null;paintPill()">✕</button></span>`:'')+(s?`<span class=skillpill>${s.icon} ${esc(s.name_bn)}<button aria-label="স্কিল সরান" onclick="ST.activeSkill=null;paintPill()">✕</button></span>`:'')}
function chatAgent(id){const a=ST.agents.find(x=>x.id===id);if(!a)return;ST.chat=null;ST.activeAgent=a;go('/v3');setTimeout(()=>{paintPill();toast(a.name+' এর সাথে চ্যাট')},50)}
function useSkill(id){const s=ST.skills.find(x=>x.id===id);if(!s)return;if(location.pathname!=='/v3')go('/v3');ST.activeSkill=s;
 if(s.mode==='agent'){toast('এটা এজেন্ট স্কিল: এজেন্ট পেজ থেকে চালান');go('/v3/agents');return}
 if(s.mode==='media'){location.href='/studio';return}paintPill();$('#inp').focus()}
function pickSkill(){const en=ST.skills.filter(s=>s.available);openSheet(`<h3>স্কিল বেছে নিন</h3><p class="sub">পরের মেসেজটা এই স্কিল দিয়ে চলবে।</p>`+
 en.map(s=>`<button class=list-row style="width:100%;text-align:left" onclick="useSkill('${s.id}');closeSheet()"><span class=ki>${s.icon}</span><span class=grow><b>${esc(s.name_bn)}</b><div class="small mut">${esc(s.desc_bn)}</div></span>${s.enabled?'':'<span class=tag>বন্ধ</span>'}</button>`).join(''))}
function pickTier(){const cur=localStorage.bbTier||'auto';openSheet(`<h3>মডেল</h3><p class=sub>অটো সবসময় সেরা ফ্রি মডেল বেছে নেয়, আটকে গেলে পরেরটায় যায়।</p><div class=radio>`+
 [['fast','দ্রুত','ছোট মডেল, সাথে সাথে উত্তর'],['auto','অটো (প্রস্তাবিত)','সেরা + ব্যাকআপ'],['deep','গভীর চিন্তা','বড় মডেল + কাউন্সিল, একটু সময় লাগে']].map(([k,b,s])=>`<button class="${cur===k?'on':''}" onclick="localStorage.bbTier='${k}';closeSheet();pgChat()"><i class=dot></i><span><b>${b}</b><span>${s}</span></span></button>`).join('')+'</div>')}
async function openChats(){let L=[];try{L=await api('/bb/api/chats')}catch(e){}
 openSheet(`<div class=row><h3 class=grow>চ্যাট</h3><button class="btn sm pri" onclick="newChat();closeSheet()">${svg('plus')} নতুন</button></div><div class=search style="margin-top:10px">${svg('search')}<input class=fld placeholder="খুঁজুন…" oninput="filterChats(this.value)"></div><div id=chl></div>`);
 window._CH=L;filterChats('')}
function filterChats(q){const el=$('#chl');if(!el)return;const L=(window._CH||[]).filter(c=>!q||c.title.toLowerCase().includes(q.toLowerCase())).slice(0,60);
 el.innerHTML=L.map(c=>`<button class=list-row style="width:100%;text-align:left" onclick="openChat('${c.id}')"><span class=ki>${c.pinned?'📌':'💬'}</span><span class=grow style="overflow:hidden;white-space:nowrap;text-overflow:ellipsis">${esc(c.title)}</span><span class="small mut">${ago(c.updated)}</span></button>`).join('')||'<div class=empty>কোনো চ্যাট নেই</div>'}
async function openChat(id){closeSheet();ST.chat=await api('/bb/api/chats/'+id);if(location.pathname!=='/v3')go('/v3');else pgChat()}
function newChat(){ST.chat=null;ST.activeSkill=null;ST.activeAgent=null;pgChat()}
function scrollEnd(){const p=$('#chatPage');if(p)p.scrollTop=p.scrollHeight}
function addMsg(m){$('.hello')?.remove();const w=document.createElement('div');
 if(m.role==='user'){w.className='msg u';w.innerHTML='<div class=bub></div>';w.firstChild.textContent=m.content}
 else{w.className='msg b';w.innerHTML=`<img class=av src="/bb/static/logo.png" alt=""><div class=bub><div class=content></div><div class=meta></div><div class=acts></div></div>`;
  if(m.content!=null){$('.content',w).replaceChildren(md(m.content));meta(w,m.model,m.skill);acts(w,m)}}
 $('#msgs').appendChild(w);return w}
function meta(w,model,skill){$('.meta',w).innerHTML=(skill?`<span class="tag royal">${skill.icon} ${esc(skill.name_bn)}</span>`:'')+(model?`<span class=tag>⚡ ${esc(String(model).split('/').pop())}</span>`:'')}
function acts(w,m){const a=$('.acts',w);a.innerHTML=`<button>${svg('copy')}কপি</button><button>${svg('redo')}আবার</button><button>${svg('speaker')}শুনুন</button>`;
 a.children[0].onclick=()=>{navigator.clipboard?.writeText(m.content);toast('কপি হয়েছে')};a.children[1].onclick=()=>run({regenerate:true});a.children[2].onclick=()=>toast('আসল বিল্ডে /bb/api/tts')}
async function send(){const inp=$('#inp');const t=inp.value.trim();if(!t)return;inp.value='';inp.style.height='auto';
 if(!ST.chat){const r=await api('/bb/api/chats',{method:'POST',body:'{}'});ST.chat={id:r.id,messages:[]}}
 const sk=ST.activeSkill;run({content:t,skill_id:sk?.id,agent_id:ST.activeAgent?.id},sk)}
async function run(body,sk){if(body.content)addMsg({role:'user',content:body.content});
 const w=addMsg({role:'assistant'});const c=$('.content',w);c.innerHTML='<span class=typing><span></span><span></span><span></span></span>';scrollEnd();
 ST.ctrl=new AbortController();const sb=$('#send');sb.disabled=false;sb.classList.add('stop');sb.innerHTML=svg('stop');let txt='',model='';
 try{const r=await fetch(`/bb/api/chats/${ST.chat.id}/stream`,{method:'POST',headers:{'Content-Type':'application/json'},signal:ST.ctrl.signal,
   body:JSON.stringify({...body,model:{fast:'groq:openai/gpt-oss-20b',deep:'auto'}[localStorage.bbTier]||'auto',council:localStorage.bbTier==='deep'})});
  if(!r.ok){const j=await r.json().catch(()=>({}));txt='⚠️ '+(j.error||'সমস্যা হয়েছে')}else{
  const rd=r.body.getReader(),dec=new TextDecoder();let buf='';
  for(;;){const{value,done}=await rd.read();if(done)break;buf+=dec.decode(value,{stream:true});let i;
   while((i=buf.indexOf('\n\n'))>=0){const blk=buf.slice(0,i);buf=buf.slice(i+2);let ev='message',data='';blk.split('\n').forEach(l=>{if(l.startsWith('event:'))ev=l.slice(6).trim();else if(l.startsWith('data:'))data+=l.slice(5).trim()});
    if(!data)continue;const j=JSON.parse(data);if(ev==='meta'||ev==='done'){model=j.model||model}else if(j.d){txt+=j.d;c.replaceChildren(md(txt));scrollEnd()}}}}
 }catch(e){if(e.name==='AbortError')txt+=' _(থামানো হয়েছে)_';else txt+='\n\n⚠️ সংযোগ কেটে গেছে। আবার চেষ্টা করুন।'}
 ST.ctrl=null;sb.classList.remove('stop');sb.innerHTML=svg('send');sb.disabled=true;c.replaceChildren(md(txt));meta(w,model,sk);acts(w,{content:txt});scrollEnd()}
/* =============== SKILLS =============== */
let SKF={q:'',cat:'সব'};
function pgSkills(){const on=ST.skills.filter(s=>s.enabled&&s.available).length;
 $('#view').innerHTML=topbar('<h1>স্কিল</h1>','<span style="width:8px"></span>',themeBtn())+`<div class=page><div class=wrap>
 ${ST.skillsOff?`<div class=card role=status style="margin-bottom:12px">⏸️ ${esc(ST.skillsOff)}</div>`:''}<div class=hero><b style="font-size:16px">বাংলা ভাইয়ের দক্ষতা</b><div class="small mut">যেটা দরকার চালু রাখুন। চালু স্কিল চ্যাটের নিচে শর্টকাট হিসেবে আসবে, এজেন্টকেও দিতে পারবেন।</div>
 <div class=stats><div><b>${bnNum(on)}</b><span>চালু</span></div><div><b>${bnNum(ST.skills.length)}</b><span>মোট</span></div><div><b>${bnNum(ST.skills.filter(s=>s.perms?.length).length)}</b><span>অনুমতি লাগে</span></div></div></div>
 <div class=search>${svg('search')}<input class=fld id=skq placeholder="স্কিল খুঁজুন…" value="${esc(SKF.q)}"></div>
 <div class=chips id=skc></div><div class=sgrid id=skg></div></div></div>`;
 $('#skq').oninput=e=>{SKF.q=e.target.value;paintSkills()};paintSkills()}
function paintSkills(){$('#skc').innerHTML=['সব','চালু',...ST.cats].map(c=>`<button class="chipb ${SKF.cat===c?'on':''}" onclick="SKF.cat='${c}';paintSkills()">${c}</button>`).join('');
 const q=SKF.q.toLowerCase();const L=ST.skills.filter(s=>(SKF.cat==='সব'||(SKF.cat==='চালু'?s.enabled:s.category===SKF.cat))&&(!q||(s.name_bn+s.name_en+s.desc_bn).toLowerCase().includes(q)));
 $('#skg').innerHTML=L.map(s=>{const off=!s.available;const why={admin_off:'অ্যাডমিন বন্ধ রেখেছেন',flag_off:'এই ফিচার এখন বন্ধ'}[s.why_off]||'';
  return `<div class="sk ${s.enabled&&!off?'on':''} ${off?'off':''}"><div class=ico>${s.icon}</div><div class=grow><h4>${esc(s.name_bn)}</h4><p>${esc(s.desc_bn)}</p><div class=tags>
  ${s.mode==='agent'?'<span class="tag royal">🤖 এজেন্ট</span>':s.mode==='media'?'<span class="tag gold">🎨 স্টুডিও</span>':s.mode==='schedule'?'<span class="tag gold">⏰ শিডিউল</span>':'<span class=tag>💬 চ্যাট</span>'}
  ${s.perms?.length?'<span class="tag red">🔐 অনুমতি লাগে</span>':''}${s.owner_only?'<span class="tag gold">♛ শুধু মালিক</span>':''}${off?`<span class=tag>⛔ ${why}</span>`:''}</div>
  ${s.enabled&&!off?`<button class="btn sm use" onclick="useSkill('${s.id}')">${svg('play')} ব্যবহার করুন</button>`:''}</div>
  <button class="sw ${s.enabled&&!off?'on':''}" role="switch" aria-checked="${s.enabled&&!off}" aria-label="${esc(s.name_bn)}" ${off?'disabled':''} onclick="togSkill('${s.id}')"></button></div>`}).join('')||'<div class=empty><div class=big>🔎</div>কিছু পাওয়া যায়নি</div>'}
async function togSkill(id){const s=ST.skills.find(x=>x.id===id);const on=!s.enabled;
 if(on&&s.perms?.length&&!await confirmSheet(`${s.icon} ${s.name_bn} চালু করবেন?`,'এই স্কিল চলার সময় প্রতিটা অ্যাকশনের আগে আপনার অনুমতি চাইবে। যেকোনো সময় বন্ধ করতে পারবেন।','চালু করুন'))return;
 try{await api(`/bb/api/v3/skills/${id}/toggle`,{method:'POST',body:JSON.stringify({on})});s.enabled=on;toast(on?'চালু হয়েছে':'বন্ধ হয়েছে');paintSkills();paintCtx()}catch(e){toast(e.message)}}
function confirmSheet(title,body,ok){return new Promise(res=>{openSheet(`<h3>${esc(title)}</h3><p class=sub>${esc(body)}</p><div class=row><button class="btn grow" id=cno>বাতিল</button><button class="btn pri grow" id=cyes>${esc(ok)}</button></div>`,
 sh=>{$('#cno',sh).onclick=()=>{closeSheet();res(false)};$('#cyes',sh).onclick=()=>{closeSheet();res(true)}})})}
/* =============== AGENTS =============== */
async function loadAgents(){const j=await api('/bb/api/v3/agents');ST.agents=j.agents;ST.tiers=j.tiers;ST.perms=j.perm_levels;ST.canTools=j.can_tools;ST.safeTools=j.safe_tools;ST.agentsOff=j.off||''}
async function pgAgents(){$('#view').innerHTML=topbar('<h1>এজেন্ট</h1>','<span style="width:8px"></span>',themeBtn())+'<div class=page><div class=wrap id=agw><div class=empty>লোড হচ্ছে…</div></div></div>';
 try{await loadAgents()}catch(e){$('#agw').innerHTML=`<div class=empty>${esc(e.message)}</div>`;return}
 const sk=id=>ST.skills.find(s=>s.id===id);
 $('#agw').innerHTML=`<p class=sub>নিজের মতো সহকারী বানান: নাম, স্বভাব, কোন মডেল আর কোন স্কিল ব্যবহার করবে। বড় কাজ ধাপে ধাপে করবে, ঝুঁকির কাজে আগে অনুমতি চাইবে।</p>
 ${ST.agentsOff?`<div class=card role=status style="margin:10px 0">⏸️ ${esc(ST.agentsOff)}</div>`:''}<button class=newag ${ST.agentsOff?'hidden':''} onclick="editAgent()"><span class=ava>${svg('plus')}</span><span style="text-align:left"><b style="color:var(--tx)">নতুন এজেন্ট বানান</b><div class=small>১ মিনিটেই তৈরি</div></span></button>`+
 (ST.agents.map(a=>`<div class=ag><div class=head><div class=ava>${esc(a.icon)}</div><div class=grow><h4>${esc(a.name)}</h4><div class=row style="gap:6px;margin-top:3px;flex-wrap:wrap">
  <span class="tag royal">${esc({fast:'⚡ দ্রুত',auto:'✨ অটো',deep:'🧠 গভীর'}[a.model_tier])}</span><span class="tag ${a.perm_level==='ask'?'gold':a.perm_level==='chat_only'?'':'ok'}">🔐 ${esc({ask:'সব জিজ্ঞেস',safe_auto:'নিরাপদগুলো নিজে',chat_only:'শুধু চ্যাট'}[a.perm_level])}</span></div></div></div>
  <div class=persona>${esc(a.persona||'কোনো বিশেষ নির্দেশনা নেই')}</div><div class=sk-ics>${a.skills.map(i=>sk(i)?`<span title="${esc(sk(i).name_bn)}">${sk(i).icon}</span>`:'').join('')}</div>
  <div class=foot><button class="btn pri grow" onclick="go('/v3/agents/${a.id}')">${svg('play')} কাজ দিন</button><button class=btn onclick="editAgent('${a.id}')">এডিট</button></div>
  ${a.runs.length?`<div class="small mut" style="margin-top:10px">শেষ কাজ: ${esc(a.runs[0].goal)} · ${ago(a.runs[0].created)}</div>`:''}</div>`).join('')||'')}
const ICONS=['🤖','🧑‍💼','✍️','🔎','💻','🎓','📈','🕌','⚡','🛡️','🎨','📱'];
const TPL=[{icon:'🔎',name:'গবেষক',persona:'যেকোনো প্রশ্নে ওয়েবে খুঁজে সংক্ষেপে উত্তর দেবে, সবসময় সূত্রের লিংক দেবে।',model_tier:'auto',skills:['research','summarize'],perm_level:'safe_auto'},
 {icon:'📰',name:'খবরের সারাংশ',persona:'আজকের বাংলাদেশ ও বিশ্বের বড় খবর ৫টা পয়েন্টে বাংলায় বলবে, প্রতিটার সূত্র দেবে।',model_tier:'fast',skills:['research','summarize'],perm_level:'safe_auto'},
 {icon:'🎓',name:'পড়াশোনার সাথী',persona:'ধাপে ধাপে সহজ ভাষায় বোঝাবে, শেষে ছোট্ট কুইজ দেবে।',model_tier:'auto',skills:['tutor','summarize'],perm_level:'chat_only'},
 {icon:'✍️',name:'লেখার সহকারী',persona:'চিঠি, পোস্ট, ইমেইল সুন্দর ও ভদ্র বাংলায় লিখে দেবে; পাঠাবে না, শুধু খসড়া দেবে।',model_tier:'auto',skills:['write','mail','translate'],perm_level:'chat_only'},
 {icon:'📈',name:'ব্যবসার পরামর্শক',persona:'ছোট ব্যবসার আইডিয়া, দাম ও মার্কেটিং নিয়ে বাস্তবসম্মত পরামর্শ দেবে; দরকার হলে বাজারদর খুঁজবে।',model_tier:'deep',skills:['biz','research'],perm_level:'ask'}];
function editAgent(id,ti){const a=ST.agents.find(x=>x.id===id)||(ti!=null&&TPL[ti])||{icon:'🤖',name:'',persona:'',model_tier:'auto',skills:['write','summarize'],perm_level:'ask'};const D=JSON.parse(JSON.stringify(a));
 const avail=ST.skills.filter(s=>s.available);
 openSheet(`<h3>${id?'এজেন্ট এডিট':'নতুন এজেন্ট'}</h3><p class=sub>সব পরে বদলানো যাবে।</p>
 ${id?'':`<label class=l>রেডিমেড টেমপ্লেট</label><div class=pick>${TPL.map((t,i)=>`<button type=button class="${ti===i?'on':''}" onclick="editAgent(null,${i})">${t.icon} ${esc(t.name)}</button>`).join('')}</div>`}
 <label class=l>আইকন</label><div class=icopick id=ip>${ICONS.map(i=>`<button class="${D.icon===i?'on':''}" data-i="${i}">${i}</button>`).join('')}</div>
 <label class=l for=an>নাম</label><input class=fld id=an maxlength=40 placeholder="যেমন: আমার গবেষক" value="${esc(D.name)}">
 <label class=l for=ap>স্বভাব ও নির্দেশনা</label><textarea class=fld id=ap rows=3 placeholder="যেমন: সংক্ষেপে উত্তর দেবে, সবসময় সূত্র দেবে, বাংলায় লিখবে">${esc(D.persona)}</textarea>
 <label class=l>মডেল</label><div class=seg id=at>${[['fast','⚡ দ্রুত'],['auto','✨ অটো'],['deep','🧠 গভীর']].map(([k,l])=>`<button data-k="${k}" class="${D.model_tier===k?'on':''}">${l}</button>`).join('')}</div>
 <label class=l>স্কিল (${bnNum(avail.length)}টা থেকে বেছে নিন)</label><div class=pick id=as>${avail.map(s=>`<button data-s="${s.id}" class="${D.skills.includes(s.id)?'on':''}">${s.icon} ${esc(s.name_bn)}</button>`).join('')}</div>
 <label class=l>অনুমতির ধরন</label><div class=radio id=al>${[['ask','প্রতিটা অ্যাকশনে জিজ্ঞেস করবে','সবচেয়ে নিরাপদ (প্রস্তাবিত)'],['safe_auto','পড়া ও সার্চ নিজে করবে','পাঠানো, মোছা, ডিভাইস কন্ট্রোলের আগে সবসময় জিজ্ঞেস করবে'],['chat_only','কোনো টুল নয়','শুধু কথা বলবে']].map(([k,b,s])=>`<button data-l="${k}" class="${D.perm_level===k?'on':''}"><i class=dot></i><span><b>${b}</b><span>${s}</span></span></button>`).join('')}</div>
 <div class=row style="margin-top:18px">${id?`<button class="btn dan" id=adel>মুছুন</button>`:''}<button class="btn grow" onclick="closeSheet()">বাতিল</button><button class="btn pri grow" id=asave>সেভ</button></div>`,sh=>{
  $('#ip',sh).onclick=e=>{const b=e.target.closest('[data-i]');if(!b)return;D.icon=b.dataset.i;$$('#ip button',sh).forEach(x=>x.classList.toggle('on',x===b))};
  $('#at',sh).onclick=e=>{const b=e.target.closest('[data-k]');if(!b)return;D.model_tier=b.dataset.k;$$('#at button',sh).forEach(x=>x.classList.toggle('on',x===b))};
  $('#as',sh).onclick=e=>{const b=e.target.closest('[data-s]');if(!b)return;const s=b.dataset.s;D.skills=D.skills.includes(s)?D.skills.filter(x=>x!==s):[...D.skills,s];b.classList.toggle('on')};
  $('#al',sh).onclick=e=>{const b=e.target.closest('[data-l]');if(!b)return;D.perm_level=b.dataset.l;$$('#al button',sh).forEach(x=>x.classList.toggle('on',x===b))};
  $('#asave',sh).onclick=async()=>{D.name=$('#an',sh).value.trim()||'আমার এজেন্ট';D.persona=$('#ap',sh).value.trim();
   try{await api('/bb/api/v3/agents'+(id?'/'+id:''),{method:id?'PUT':'POST',body:JSON.stringify(D)});closeSheet();toast('সেভ হয়েছে');pgAgents()}catch(e){toast(e.message)}};
  if(id)$('#adel',sh).onclick=async()=>{if(!await confirmSheet('এজেন্ট মুছবেন?','এর কাজের ইতিহাস কার্যকলাপে থেকে যাবে।','মুছুন'))return;await api('/bb/api/v3/agents/'+id,{method:'DELETE'});pgAgents()}})}
async function pgAgent(id){if(!ST.agents.length)try{await loadAgents()}catch(e){}const a=ST.agents.find(x=>x.id===id);if(!a)return go('/v3/agents',true);
 $('#view').innerHTML=topbar(`<div class=brandmark><div class=ava style="width:34px;height:34px;border-radius:11px;display:grid;place-items:center;background:linear-gradient(135deg,var(--royal),#0b1f55)">${esc(a.icon)}</div><div><b>${esc(a.name)}</b><small>${esc({ask:'প্রতিটা অ্যাকশনে অনুমতি',safe_auto:'নিরাপদ কাজ নিজে',chat_only:'শুধু চ্যাট'}[a.perm_level])}</small></div></div>`,
  `<button class=ib aria-label="ফিরে যান" onclick="go('/v3/agents')">${svg('back')}</button>`,`<button class=ib aria-label="এডিট" onclick="editAgent('${a.id}')">${svg('edit')}</button>`)+
 `<div class=page><div class=wrap><div class=card><label class=l for=goal style="margin-top:0">কী করতে হবে?</label><textarea class=fld id=goal rows=3 placeholder="যেমন: ঢাকার আজকের আবহাওয়া খুঁজে ৩ লাইনে বলো"></textarea>
 <div class=row style="margin-top:10px"><button class="btn pri grow" id=runb>${svg('play')} শুরু করুন</button><button class="btn" id=demob title="মডেল ছাড়া UI দেখার জন্য">ডেমো</button></div><button class="btn" style="width:100%;margin-top:8px" onclick="chatAgent('${a.id}')">💬 এই এজেন্টের সাথে চ্যাট</button>
 ${!ST.canTools?'<div class="small mut" style="margin-top:8px">ℹ️ টুলসহ এজেন্ট এখন চালু নেই — চ্যাটে কথা বলুন।</div>':ST.safeTools?'<div class="small mut" style="margin-top:8px">🛡️ এই এজেন্ট শুধু ওয়েব সার্চ ও ওয়েবপেজ পড়তে পারে। পেজ খোলার আগে আপনার অনুমতি চাইবে; কিছু পাঠানো/কেনা/ডিলিট করতে পারে না।</div>':''}</div>
 <div id=runv></div><h3 style="margin:18px 0 4px;font-size:15px">আগের কাজ</h3><div id=hist>${a.runs.map(r=>`<div class=hist><span class="tag ${r.status==='done'?'ok':r.status==='failed'?'red':'gold'}">${esc({done:'সম্পন্ন',failed:'ব্যর্থ',running:'চলছে'}[r.status]||r.status||'—')}</span><span class=grow style="overflow:hidden;white-space:nowrap;text-overflow:ellipsis">${esc(r.goal)}</span><button class="btn sm" onclick="watch('${r.task_id}')">দেখুন</button></div>`).join('')||'<div class="small mut">এখনো কোনো কাজ দেননি।</div>'}</div></div></div>`;
 $('#runb').onclick=async()=>{const g=$('#goal').value.trim();if(!g)return toast('কাজটা লিখুন');try{const r=await api(`/bb/api/v3/agents/${id}/run`,{method:'POST',body:JSON.stringify({goal:g})});watch(r.task,g)}catch(e){toast(e.message)}};
 $('#demob').onclick=()=>demoRun($('#goal').value.trim()||'ঢাকার আজকের আবহাওয়া খুঁজে ৩ লাইনে বলো')}
const LAB={plan:['🗺️ পরিকল্পনা',''],think:['💭 ভাবছি',''],run:['▶️ চলছে','running'],result:['✅ ফলাফল','ok'],error:['❌ সমস্যা','err'],retry:['🔁 আবার চেষ্টা',''],repair:['🛠️ ঠিক করছি',''],
 auto:['🔓 নিজে অনুমতি দেওয়া','ok'],blocked:['⛔ বন্ধ','err'],final:['🏁 চূড়ান্ত উত্তর','ok'],approval:['🔐 অনুমতি দরকার','ask'],resume:['♻️ আবার শুরু','']};
function stepEl(box,e,tid,demo){   // FIX of live bug: old bb2.js shadowed L() with `const L={...L(..)}` -> ReferenceError on every step
 if(e.type==='end')return;
 if(e.type==='decision'){const a=$(`[data-aid="${e.id}"]`,box);if(a){a.classList.add('done');$('.btns',a).innerHTML=e.decision==='yes'?'<span class="tag ok">✅ অনুমতি দিয়েছেন</span>':'<span class="tag red">🚫 অনুমতি দেননি</span>'}return}
 $$('.st.running',box).forEach(x=>x.classList.remove('running'));
 const [lab,cls]=LAB[e.type]||[e.type,''];const d=document.createElement('div');d.className='st '+cls;
 if(e.type==='approval'){d.innerHTML=`<div class=lab>${lab}</div><div class=appr data-aid="${esc(e.id)}"><div class=t>${svg('shield')} অনুমতি দেবেন?</div>
  <div class="small mut" style="margin-top:4px">${esc(e.capname||'')} · টুল <code>${esc(e.tool)}</code> · ঝুঁকি <span class="tag ${e.risk==='high'?'red':'gold'}">${esc({high:'বেশি',medium:'মাঝারি',low:'কম'}[e.risk]||e.risk||'—')}</span></div>
  <pre>${esc(JSON.stringify(e.args,null,1))}</pre><div class=small>কেন: ${esc(e.why||'')}</div><div class=btns><button class="btn" data-ok=0>🚫 না</button><button class="btn pri" data-ok=1>✅ অনুমতি দিন</button></div></div>`;
  $$('[data-ok]',d).forEach(b=>b.onclick=async()=>{const ok=b.dataset.ok==='1';if(demo)return demo(ok,e.id);try{await api('/bb/api/approvals/'+e.id,{method:'POST',body:JSON.stringify({ok})})}catch(x){toast(x.message)}})}
 else{d.innerHTML=`<div class=lab>${lab}${e.step?' · ধাপ '+bnNum(e.step):''}</div><div class=body></div>`;const b=$('.body',d);
  if(e.type==='run')b.innerHTML=`<code>${esc(e.tool)}</code>`;else if(e.type==='result'||e.type==='error'){b.innerHTML='<pre></pre>';$('pre',b).textContent=e.text||''}
  else if(e.type==='final')b.replaceChildren(md(e.text));else b.textContent=e.text||''}
 box.appendChild(d);d.scrollIntoView({block:'nearest',behavior:'smooth'})}
async function watch(tid,goal){const v=$('#runv');v.innerHTML=`<div class=card style="margin-top:12px"><div class=row><b class=grow>${esc(goal||'কাজ')}</b><span class="tag gold" id=rst>চলছে</span><button class="btn sm" id=cxl style="margin-left:6px" aria-label="কাজ থামান">⏹ থামান</button></div><div class=tl id=tl></div></div>`;
 $('#cxl').onclick=async()=>{if(!confirm('কাজটা থামাবেন?'))return;try{await api(`/bb/api/v3/runs/${tid}/cancel`,{method:'POST',body:'{}'});toast('থামানো হচ্ছে…')}catch(e){toast(e.message)}};
 let n=0,idle=0;for(;;){let j;try{j=await api(`/bb/api/v3/runs/${tid}?since=${n}`)}catch(e){$('#rst').textContent=e.status===404?'পাওয়া যায়নি':'ত্রুটি';break}
  n=typeof j.n==='number'?j.n:n+j.events.length;j.events.forEach(e=>stepEl($('#tl'),e,tid));if(j.status!=='running'){$('#rst').textContent=j.status==='done'?'সম্পন্ন':j.status==='cancelled'?'থামানো':'থেমেছে';$('#rst').className='tag '+(j.status==='done'?'ok':'red');$('#cxl')?.remove();break}
  idle=j.events.length?0:idle+1;await new Promise(r=>setTimeout(r,document.hidden?4000:Math.min(600+idle*250,2500)));if(!$('#tl'))break}}
async function demoRun(goal){const v=$('#runv');v.innerHTML=`<div class=card style="margin-top:12px"><div class=row><b class=grow>${esc(goal)}</b><span class="tag gold" id=rst>ডেমো · চলছে</span></div><div class=tl id=tl></div></div>`;
 const tl=$('#tl');const W=ms=>new Promise(r=>setTimeout(r,ms));
 stepEl(tl,{type:'plan',text:'১) ওয়েবে খুঁজব ২) একটা আবহাওয়া সাইট খুলে পড়ব ৩) ৩ লাইনে সারাংশ দেব'});await W(250);
 stepEl(tl,{type:'think',step:1,text:'প্রথমে ঢাকার আজকের আবহাওয়া সার্চ করি।'});await W(250);
 stepEl(tl,{type:'run',tool:'web_search'});await W(350);stepEl(tl,{type:'result',text:'৫টা ফলাফল: bmd.gov.bd, accuweather.com …'});await W(250);
 const decided=new Promise(res=>stepEl(tl,{type:'approval',id:'demo1',tool:'browse',capname:'🌐 ব্রাউজার নিয়ন্ত্রণ',risk:'medium',args:{url:'https://www.bmd.gov.bd/'},why:'আবহাওয়া অধিদপ্তরের পেজ থেকে সঠিক তথ্য পড়তে'},null,(ok,id)=>{stepEl(tl,{type:'decision',id,decision:ok?'yes':'no'});res(ok)}));
 window._demoDecided=decided;const ok=await decided;
 if(ok){stepEl(tl,{type:'run',tool:'browse'});await W(400);stepEl(tl,{type:'result',text:'সর্বোচ্চ ৩২°, সর্বনিম্ন ২৫°, বিকেলে হালকা বৃষ্টির সম্ভাবনা ৪০%'})}
 stepEl(tl,{type:'final',text:'**ঢাকা, আজ:** দিনে গরম, সর্বোচ্চ ৩২°সে।\n\nবিকেলে হালকা বৃষ্টির সম্ভাবনা ৪০%, ছাতা রাখুন।\n\nরাতে তাপমাত্রা নামবে ২৫°সে-এ। _(ডেমো ডেটা)_'});
 $('#rst').textContent='ডেমো · সম্পন্ন';$('#rst').className='tag ok'}
/* =============== ACTIVITY =============== */
async function pgActivity(){$('#view').innerHTML=topbar('<h1>কার্যকলাপ</h1>','<span style="width:8px"></span>',themeBtn())+'<div class=page><div class=wrap id=acw><div class=empty>লোড হচ্ছে…</div></div></div>';
 let D;try{D=await api('/bb/api/activity')}catch(e){$('#acw').innerHTML=`<div class=empty>${esc(e.message)}</div>`;return}
 const KN={agent:'এজেন্ট',schedule:'শিডিউল',skill:'স্কিল',media:'মিডিয়া',shell:'সার্ভার কমান্ড',approval:'অনুমতি',push:'নোটিফিকেশন',browse:'ব্রাউজার',device:'ডিভাইস'},VB={create:'তৈরি',update:'বদল',edit:'এডিট',delete:'মোছা',run:'চালানো',task:'কাজ',toggle:'চালু/বন্ধ',save:'সেভ',propose:'প্রস্তাব',subscribe:'চালু',shell:'চালানো'};
 const lbl=x=>(KN[x.kind]||x.kind)+' · '+(VB[x.tool]||(x.tool.includes(':')?x.tool.split(':').pop():x.tool));
 const KI={schedule:'⏰',push:'🔔',agent:'🤖',shell:'🖥️',browse:'🌐',device:'📱',media:'🎨',approval:'🔐',skill:'✨'};
 $('#acw').innerHTML=(D.approvals?.length?`<h3 style="font-size:15px">⏳ আপনার অনুমতির অপেক্ষায় (${bnNum(D.approvals.length)})</h3>`+D.approvals.map(a=>`<div class=appr style="margin-bottom:10px"><div class=t>${svg('shield')} ${esc(a.tool)}</div><pre>${esc(a.args)}</pre><div class=btns><button class=btn onclick="dec('${a.id}',0)">🚫 না</button><button class="btn pri" onclick="dec('${a.id}',1)">✅ অনুমতি</button></div></div>`).join(''):'')+
 `<p class=sub>আপনার হয়ে বাংলা ভাই যা যা করেছে, সব এখানে। কিছুই লুকানো নেই।</p>`+
 ((D.items||[]).slice(0,80).map(x=>`<div class=act><span class=ki>${KI[x.kind]||'•'}</span><div class=grow><b>${esc(lbl(x))}</b> <span class="tag ${x.ok?'ok':'red'}">${x.ok?'✓':'✗'}</span><div class="small" style="word-break:break-word">${esc(String(x.input||'').slice(0,140))}</div><div class=small>${ago(x.ts)}</div></div></div>`).join('')||'<div class=empty><div class=big>📋</div>এখনো কিছু নেই</div>');
 const b=$('#nav .badge');if(b){b.hidden=!D.approvals?.length;b.textContent=bnNum(D.approvals?.length||0)}}
async function dec(id,ok){try{await api('/bb/api/approvals/'+id,{method:'POST',body:JSON.stringify({ok:!!ok})})}catch(e){toast(e.message)}pgActivity()}
/* =============== ME =============== */
function openMe(){const t=localStorage.bbTheme||'dark';const own=ST.me.role==='owner';
 openSheet(`<div class=row style="margin-bottom:8px"><img src="/bb/static/logo.png" style="width:48px;height:48px;border-radius:50%;box-shadow:0 0 0 2px var(--gold)" alt=""><div class=grow><b>${esc(own?'রয়েল':(ST.me.name||ST.me.email||''))}</b><div class="small mut">${esc(ST.me.email||'')} ${own?'<span class="tag gold">♛ মালিক</span>':''}</div></div></div>
 <label class=l>থিম</label><div class=seg>${[['dark','🌙 ডার্ক'],['light','☀️ লাইট'],['system','📱 সিস্টেম']].map(([k,l])=>`<button class="${t===k?'on':''}" onclick="setTheme('${k}');openMe();route()">${l}</button>`).join('')}</div>
 <label class=l>ভাষা</label><div class=seg>${[['bn','বাংলা'],['en','English']].map(([k,l])=>`<button class="${(ST.set?.lang||'bn')===k?'on':''}" onclick="saveSet({lang:'${k}'})">${l}</button>`).join('')}</div>
 <label class=list-row style="margin-top:10px"><span class=ki>💾</span><span class=grow>আমার কথা মনে রাখো (মেমরি)</span><input type=checkbox ${ST.set?.memory!==false?'checked':''} onchange="saveSet({memory:this.checked})" style="width:20px;height:20px"></label>
 <div style="margin-top:12px">${[['🧠','মেমরি','/memory'],['⏰','শিডিউল','/schedules'],['🔌','কানেকশন','/connections'],['🎨','স্টুডিও','/studio'],['💳','অ্যাকাউন্ট ও প্ল্যান','/account'],['⚙️','ক্লাসিক UI ও পুরো সেটিংস','/app?classic=1']].map(([i,l,h])=>`<a class=list-row href="${h}"><span class=ki>${i}</span><span class=grow>${l}</span><span class=mut>›</span></a>`).join('')}
 ${own?`<a class=list-row href="/admin/dash"><span class=ki>🛡️</span><span class=grow><b>অ্যাডমিন ড্যাশবোর্ড</b></span><span class="tag gold">মালিক</span></a>`:''}
 <a class=list-row href="/logout"><span class=ki>↩︎</span><span class=grow style="color:var(--red)">লগআউট</span></a></div>`)}
async function saveSet(p){try{ST.set=await api('/bb/api/settings',{method:'PUT',body:JSON.stringify(p)});const l=ST.set.lang||'bn';document.cookie='bb_lang='+l+';path=/;max-age=31536000;samesite=lax';localStorage.bbLang=l;toast('সংরক্ষণ হয়েছে');openMe()}catch(e){toast(e.message)}}
/* ---------- boot ---------- */
(async()=>{$('#nav').innerHTML=navHTML();$('#rail').insertAdjacentHTML('beforeend',navHTML());
 try{ST.me=await api('/bb/api/me')}catch(e){}try{ST.set=await api('/bb/api/settings')}catch(e){}
 try{const j=await api('/bb/api/v3/skills');ST.skills=j.skills;ST.cats=j.categories;ST.skillsOff=j.off||''}catch(e){}
 route();try{const D=await api('/bb/api/activity');const b=$('#nav .badge');if(b&&D.approvals?.length){b.hidden=false;b.textContent=bnNum(D.approvals.length)}}catch(e){}})();
