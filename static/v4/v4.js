/* The Royal Bengal Tiger (v4) — "Royal Court" redesign. Vanilla JS, same APIs as v3 (/bb/api/*, /bb/api/v3/*). Flag: feat_ui_v4. */
'use strict';
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let LANG=localStorage.bbV4Lang==='bn'?'bn':'en';   // v4: English by default; Bangla via Me
const T=(bn,en)=>LANG==='en'&&en!=null?en:bn;
const num=n=>LANG==='en'?String(n):String(n).replace(/\d/g,d=>'০১২৩৪৫৬৭৮৯'[d]);
const IC={
 chat:'<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/>',
 spark:'<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
 bot:'<rect x="4" y="8" width="16" height="12" rx="3"/><path d="M12 4v4M9 14h.01M15 14h.01"/><path d="M2 13v2M22 13v2"/>',
 pulse:'<path d="M3 12h4l3-8 4 16 3-8h4"/>', user:'<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
 send:'<path d="M12 19V5M5 12l7-7 7 7"/>', stop:'<rect x="7" y="7" width="10" height="10" rx="2"/>',
 plus:'<path d="M12 5v14M5 12h14"/>', mic:'<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
 clip:'<path d="M21 11l-8.5 8.5a5 5 0 0 1-7-7L14 4a3.5 3.5 0 0 1 5 5l-8.5 8.5a2 2 0 0 1-3-3L15 7"/>',
 menu:'<path d="M4 7h16M4 12h16M4 17h10"/>', edit:'<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>', back:'<path d="M15 6l-6 6 6 6"/>',
 moon:'<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>', sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
 search:'<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>', copy:'<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>',
 redo:'<path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7"/>', speaker:'<path d="M4 9v6h4l5 4V5L8 9z"/><path d="M16 9a4 4 0 0 1 0 6"/>', play:'<path d="M7 5l12 7-12 7z"/>',
 shield:'<path d="M12 3l8 3v6c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6z"/>', x:'<path d="M6 6l12 12M18 6L6 18"/>', chev:'<path d="M9 6l6 6-6 6"/>'};
const svg=(n,c='')=>`<svg class="${c}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${IC[n]}</svg>`;
async function api(u,o={}){const r=await fetch(u,{credentials:'same-origin',headers:{'Content-Type':'application/json'},...o});
 if(r.status===401){location.href='/login';throw new Error('login')}let j={};try{j=await r.json()}catch(e){}
 if(!r.ok){const e=new Error(j.hint||j.error||('HTTP '+r.status));e.data=j;e.status=r.status;throw e}return j}
function toast(t){const e=$('#toast');e.textContent=t;e.classList.add('on');clearTimeout(e._t);e._t=setTimeout(()=>e.classList.remove('on'),2400)}
function md(t){const h=window.marked&&window.DOMPurify?DOMPurify.sanitize(marked.parse(t||'')):esc(t).replace(/\n/g,'<br>');const d=document.createElement('div');d.innerHTML=h;d.querySelectorAll('a').forEach(a=>{a.target='_blank';a.rel='noopener'});return d}
const ago=ts=>{const s=Date.now()/1000-ts;if(s<60)return T('এইমাত্র','just now');if(s<3600)return num(Math.floor(s/60))+T(' মিনিট আগে','m ago');if(s<86400)return num(Math.floor(s/3600))+T(' ঘণ্টা আগে','h ago');return num(Math.floor(s/86400))+T(' দিন আগে','d ago')};
const LOGO='/bb/static/v4/brand/RBT_seal_512_transparent.png';
const avatar=(c='')=>`<span class="ava ${c}"><img src="${LOGO}" alt="" width="40" height="40"></span>`;
/* ---------- state & router ---------- */
const ST={activeAgent:null,me:{},skills:[],cats:[],agents:[],canTools:false,chat:null,activeSkill:null,ctrl:null,files:[],approvals:0};
const TABS=()=>[['chat','/v4',T('চ্যাট','Chat')],['spark','/v4/skills',T('স্কিল','Skills')],['bot','/v4/agents',T('এজেন্ট','Agents')],['pulse','/v4/activity',T('কার্যকলাপ','Activity')],['user','#me',T('আমি','Me')]];
function navHTML(){return TABS().map(([i,h,l])=>`<a href="${h}" data-nav="${h}" aria-label="${l}"><i class=pip></i>${svg(i)}<span>${l}</span>${h==='/v4/activity'?'<i class=badge hidden></i>':''}</a>`).join('')}
function paintNav(){const p=location.pathname.replace(/\/$/,'')||'/v4';$$('[data-nav]').forEach(a=>{const h=a.dataset.nav;const on=h===p||(h!=='/v4'&&h!=='#me'&&p.startsWith(h));a.classList.toggle('on',on);on?a.setAttribute('aria-current','page'):a.removeAttribute('aria-current')});
 $$('.badge').forEach(b=>{b.hidden=!ST.approvals;b.textContent=num(ST.approvals)})}
document.addEventListener('click',e=>{const a=e.target.closest('a[href]');if(!a)return;const h=a.getAttribute('href');
 if(h==='#me'){e.preventDefault();return openMe()}
 if(h==='/v4'||h.startsWith('/v4/')){e.preventDefault();go(h)}});
function go(h,replace){history[replace?'replaceState':'pushState']({},'',h);route()}
addEventListener('popstate',route);
function route(){const p=location.pathname.replace(/\/$/,'');paintNav();closeSheet();$('#view').classList.remove('chatpage');
 if(p==='/v4/skills')return pgSkills();if(p==='/v4/agents')return pgAgents();const m=p.match(/^\/v4\/agents\/(\w+)/);if(m)return pgAgent(m[1]);
 if(p==='/v4/activity')return pgActivity();return pgChat()}
/* ---------- sheet ---------- */
let lastFocus=null;
function openSheet(html,after,label){lastFocus=document.activeElement;const s=$('#sheet');s.innerHTML='<div class=grab></div>'+html;s.setAttribute('aria-label',label||T('প্যানেল','Panel'));$('#scrim').classList.add('on');
 setTimeout(()=>{(s.querySelector('input,textarea,button:not(.grab)')||s).focus?.()},60);after&&after(s)}
function closeSheet(){const sc=$('#scrim');if(!sc.classList.contains('on'))return;sc.classList.remove('on');lastFocus?.focus?.()}
$('#scrim').addEventListener('click',e=>{if(e.target.id==='scrim')closeSheet()});
addEventListener('keydown',e=>{if(e.key==='Escape')closeSheet()});
/* ---------- theme ---------- */
function setTheme(t){localStorage.bbTheme=t;document.documentElement.dataset.theme=t==='system'?(matchMedia('(prefers-color-scheme: light)').matches?'light':'dark'):t;
 $('meta[name=theme-color]').content=getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()}
function themeBtn(){const l=document.documentElement.dataset.theme==='light';return `<button class=ib aria-label="${T('থিম বদলান','Toggle theme')}" onclick="setTheme('${l?'dark':'light'}');route()">${svg(l?'moon':'sun')}</button>`}
const topbar=(mid,left='',right='')=>`<header class=top>${left}${mid}${right}</header>`;
const shell=(title,body,right='')=>topbar(`<h1>${title}</h1>`,'',right||themeBtn())+`<div class=page><div class=wrap>${body}</div></div>`;
/* =============== CHAT / HOME =============== */
const TIERL=()=>({fast:T('দ্রুত','Fast'),auto:T('অটো','Auto'),deep:T('গভীর','Deep')});
function pgChat(){const tier=localStorage.bbTier||'auto';$('#view').classList.add('chatpage');
 $('#view').innerHTML=topbar(`<div class="who ttl">${avatar()}<div class=wm><small>The Royal Bengal</small><b>TIGER</b></div></div>`,
  `<button class=ib aria-label="${T('চ্যাটের তালিকা','Chat list')}" onclick="openChats()">${svg('menu')}</button>`,
  `<button class=tier onclick="pickTier()" aria-label="${T('মডেল বেছে নিন','Choose model')}: ${TIERL()[tier]}"><i></i>${esc(TIERL()[tier])}</button><button class=ib aria-label="${T('নতুন চ্যাট','New chat')}" onclick="newChat()">${svg('edit')}</button>`)+
  `<div class=page id=chatPage><div class=wrap id=msgs></div></div>
  <div id=composer><div class=ctx id=ctx></div><div class=cbox><div id=pillSlot></div><textarea id=inp rows=1 placeholder="${T('টাইগারকে কিছু জিজ্ঞেস করুন…','Ask the Tiger anything…')}" aria-label="${T('মেসেজ','Message')}"></textarea>
  <div class=crow><button class=ib aria-label="${T('স্কিল বেছে নিন','Pick a skill')}" onclick="pickSkill()">${svg('spark')}</button><button class=ib aria-label="${T('ফাইল যোগ করুন','Attach file')}" onclick="pickFile()">${svg('clip')}</button>
  <button class=ib id=micb aria-label="${T('ভয়েসে বলুন','Voice input')}" onclick="voice()">${svg('mic')}</button><span class=grow></span><button id=send aria-label="${T('পাঠান','Send')}" disabled>${svg('send')}</button></div></div></div>
  <input type=file id=fileIn hidden accept="image/*,.pdf,.txt,.md,.csv,.json" aria-label="${T('ফাইল','File')}">`;
 const inp=$('#inp');inp.addEventListener('input',()=>{inp.style.height='auto';inp.style.height=Math.min(inp.scrollHeight,180)+'px';canSend()});
 inp.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&innerWidth>900){e.preventDefault();send()}});
 $('#send').onclick=()=>ST.ctrl?ST.ctrl.abort():send();$('#fileIn').onchange=upFile;
 paintPill();paintCtx();
 if(ST.chat&&ST.chat.messages?.length){ST.chat.messages.forEach(addMsg);scrollEnd()}else hello()}
function canSend(){const b=$('#send');if(b)b.disabled=!ST.ctrl&&!$('#inp').value.trim()&&!ST.files.length}
function greet(){const h=new Date().getHours();return h<5?T('শুভ রাত্রি','Good night'):h<12?T('শুভ সকাল','Good morning'):h<17?T('শুভ দুপুর','Good afternoon'):h<20?T('শুভ সন্ধ্যা','Good evening'):T('শুভ রাত্রি','Good night')}
async function hello(){const cx=$('#ctx');if(cx)cx.hidden=true;const own=ST.me.role==='owner';const nm=own?T('জাহাঁপনা','Your Majesty'):(ST.me.name||'');const en=ST.skills.filter(s=>s.enabled&&s.available).slice(0,4);
 $('#msgs').innerHTML=`<section class=hero aria-label="${T('স্বাগতম','Welcome')}"><i class=stripe></i><div class=hi>${avatar()}<div><small>${greet()}${nm?', '+esc(nm):''} 👋</small><div class=wm><small>The Royal Bengal</small><b>TIGER</b></div><h2>${T('আসসালামু আলাইকুম! আজ কী করব?','Hello! What shall we do today?')}</h2></div></div>
 <p>${T('লিখুন, বলুন বা ছবি দিন — দ্য রয়্যাল বেঙ্গল টাইগার সেরা ফ্রি AI মডেলগুলো দিয়ে উত্তর দেবে।','Type, talk or share a photo — The Royal Bengal Tiger answers with the best free AI models.')}</p></section>
 ${en.length?`<div class=sec><h2>${T('দ্রুত শুরু','Quick start')}</h2><a href="/v4/skills">${T('সব স্কিল','All skills')} ›</a></div><div class=qrow>${en.map(s=>`<button class=q onclick="useSkill('${s.id}')"><span class=ic aria-hidden=true>${s.icon}</span><b>${esc(T(s.name_bn,s.name_en))}</b><span>${esc(T(s.desc_bn,s.desc_en))}</span></button>`).join('')}</div>`:''}
 <div id=recentBox></div>`;
 try{const L=(await api('/bb/api/chats')).slice(0,4);if(L.length&&$('#recentBox'))$('#recentBox').innerHTML=`<div class=sec><h2>${T('সাম্প্রতিক চ্যাট','Recent chats')}</h2><button onclick="openChats()">${T('সব দেখুন','See all')}</button></div><div class=recent>${L.map(c=>`<button class=li onclick="openChat('${esc(c.id)}')"><span class=ki aria-hidden=true>${c.pinned?'📌':'💬'}</span><span class="grow t">${esc(c.title)}</span><span class="small mut">${ago(c.updated)}</span></button>`).join('')}</div>`}catch(e){}}
function paintCtx(){const c=$('#ctx');if(!c)return;const en=ST.skills.filter(s=>s.enabled&&s.available);c.innerHTML=en.slice(0,8).map(s=>`<button onclick="useSkill('${s.id}')">${s.icon} ${esc(T(s.name_bn,s.name_en))}</button>`).join('')}
function paintPill(){const s=ST.activeSkill,g=ST.activeAgent,el=$('#pillSlot');if(!el)return;
 el.innerHTML=(g?`<span class=pill>${esc(g.icon)} ${esc(g.name)}<button aria-label="${T('এজেন্ট সরান','Remove agent')}" onclick="ST.activeAgent=null;paintPill()">${svg('x')}</button></span>`:'')+
 (s?`<span class=pill>${s.icon} ${esc(T(s.name_bn,s.name_en))}<button aria-label="${T('স্কিল সরান','Remove skill')}" onclick="ST.activeSkill=null;paintPill()">${svg('x')}</button></span>`:'')+
 ST.files.map((f,i)=>`<span class=att>📎 <span>${esc(f.name)}</span><button aria-label="${T('ফাইল সরান','Remove file')}" onclick="ST.files.splice(${i},1);paintPill();canSend()">${svg('x')}</button></span>`).join('');$$('#pillSlot svg').forEach(x=>{x.style.width='14px';x.style.height='14px'})}
function chatAgent(id){const a=ST.agents.find(x=>x.id===id);if(!a)return;ST.chat=null;ST.activeAgent=a;go('/v4');toast(a.name+T(' এর সাথে চ্যাট',' — chat'))}
function useSkill(id){const s=ST.skills.find(x=>x.id===id);if(!s)return;
 if(s.mode==='agent'){toast(T('এটা এজেন্ট স্কিল — এজেন্ট পেজ থেকে চালান','Agent skill — run it from Agents'));go('/v4/agents');return}
 if(s.mode==='media'){location.href='/studio';return}
 ST.activeSkill=s;if(location.pathname.replace(/\/$/,'')!=='/v4')go('/v4');else paintPill();$('#inp')?.focus()}
function pickSkill(){const en=ST.skills.filter(s=>s.available);openSheet(`<h3>${T('স্কিল বেছে নিন','Pick a skill')}</h3><p class=sub>${T('পরের মেসেজটা এই স্কিল দিয়ে চলবে।','Your next message will use this skill.')}</p><div class=group>`+
 en.map(s=>`<button class=li onclick="closeSheet();useSkill('${s.id}')"><span class=ki aria-hidden=true>${s.icon}</span><span class=grow><b>${esc(T(s.name_bn,s.name_en))}</b><div class="small mut">${esc(T(s.desc_bn,s.desc_en))}</div></span>${s.enabled?'':`<span class=tag>${T('বন্ধ','off')}</span>`}</button>`).join('')+'</div>',null,T('স্কিল','Skills'))}
function pickTier(){const cur=localStorage.bbTier||'auto';openSheet(`<h3>${T('মডেল','Model')}</h3><p class=sub>${T('অটো সবসময় সেরা ফ্রি মডেল বেছে নেয়, আটকে গেলে পরেরটায় যায়।','Auto always picks the best free model and falls back if one is busy.')}</p><div class=radio>`+
 [['fast',T('দ্রুত','Fast'),T('ছোট মডেল, সাথে সাথে উত্তর','Small model, instant answers')],['auto',T('অটো (প্রস্তাবিত)','Auto (recommended)'),T('সেরা + ব্যাকআপ','Best + fallbacks')],['deep',T('গভীর চিন্তা','Deep think'),T('বড় মডেল + কাউন্সিল, একটু সময় লাগে','Large models + council, a bit slower')]].map(([k,b,s])=>`<button class="${cur===k?'on':''}" aria-pressed="${cur===k}" onclick="localStorage.bbTier='${k}';closeSheet();pgChat()"><i class=dot></i><span><b>${b}</b><span>${s}</span></span></button>`).join('')+'</div>',null,T('মডেল','Model'))}
async function openChats(){let L=[];try{L=await api('/bb/api/chats')}catch(e){}
 openSheet(`<div class=row><h3 class=grow>${T('আপনার চ্যাট','Your chats')}</h3><button class="btn sm pri" onclick="closeSheet();newChat()">${svg('plus')} ${T('নতুন','New')}</button></div><div class=search style="margin-top:12px">${svg('search')}<input class=fld placeholder="${T('খুঁজুন…','Search…')}" aria-label="${T('চ্যাট খুঁজুন','Search chats')}" oninput="filterChats(this.value)"></div><div class=group id=chl></div>`,null,T('চ্যাট','Chats'));
 window._CH=L;filterChats('')}
function filterChats(q){const el=$('#chl');if(!el)return;const L=(window._CH||[]).filter(c=>!q||c.title.toLowerCase().includes(q.toLowerCase())).slice(0,60);
 el.innerHTML=L.map(c=>`<button class=li onclick="openChat('${esc(c.id)}')"><span class=ki aria-hidden=true>${c.pinned?'📌':'💬'}</span><span class="grow t">${esc(c.title)}</span><span class="small mut">${ago(c.updated)}</span></button>`).join('')||`<div class=empty>${T('কোনো চ্যাট নেই','No chats yet')}</div>`}
async function openChat(id){closeSheet();try{ST.chat=await api('/bb/api/chats/'+id)}catch(e){return toast(e.message)}if(location.pathname.replace(/\/$/,'')!=='/v4')go('/v4');else pgChat()}
function newChat(){ST.chat=null;ST.activeSkill=null;ST.activeAgent=null;ST.files=[];if(location.pathname.replace(/\/$/,'')!=='/v4')go('/v4');else pgChat()}
function scrollEnd(){const p=$('#chatPage');if(p)p.scrollTop=p.scrollHeight}
function addMsg(m){if($('.hero')){$('#msgs').innerHTML='';const cx=$('#ctx');if(cx)cx.hidden=false}const w=document.createElement('div');
 if(m.role==='user'){w.className='msg u';w.innerHTML='<div class=bub></div>';w.firstChild.textContent=String(m.content||'').replace(/^\[📎[\s\S]*?\[\/📎\]\n*/,'📎 ')}
 else{w.className='msg b';w.innerHTML=`${avatar()}<div class=bub><div class=content aria-live=polite></div><div class=meta></div><div class=acts></div></div>`;
  if(m.content!=null){$('.content',w).replaceChildren(md(m.content));meta(w,m.model,m.skill);acts(w,m)}}
 $('#msgs').appendChild(w);return w}
function meta(w,model,skill){$('.meta',w).innerHTML=(skill?`<span class="tag blue">${skill.icon} ${esc(T(skill.name_bn,skill.name_en))}</span>`:'')+(model?`<span class=tag>⚡ ${esc(String(model).split('/').pop())}</span>`:'')}
function acts(w,m){const a=$('.acts',w);a.innerHTML=`<button aria-label="${T('কপি','Copy')}">${svg('copy')}${T('কপি','Copy')}</button><button aria-label="${T('আবার লিখুন','Regenerate')}">${svg('redo')}${T('আবার','Retry')}</button><button aria-label="${T('শুনুন','Listen')}">${svg('speaker')}${T('শুনুন','Listen')}</button>`;
 a.children[0].onclick=()=>{navigator.clipboard?.writeText(m.content);toast(T('কপি হয়েছে','Copied'))};a.children[1].onclick=()=>{w.remove();run({regenerate:true})};a.children[2].onclick=()=>speak(m.content,a.children[2])}
let AUD=null;
async function speak(text,btn){if(AUD){AUD.pause();AUD=null;return}btn.disabled=true;try{const r=await fetch('/bb/api/tts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:String(text||'').slice(0,3000)})});
 if(!r.ok){const j=await r.json().catch(()=>({}));throw new Error(j.error||T('শোনানো যায়নি','Could not play'))}AUD=new Audio(URL.createObjectURL(await r.blob()));AUD.onended=()=>AUD=null;await AUD.play()}catch(e){toast(e.message)}btn.disabled=false}
function pickFile(){$('#fileIn').click()}
async function upFile(e){const f=e.target.files[0];e.target.value='';if(!f)return;toast(T('ফাইল পড়ছি…','Reading file…'));const fd=new FormData();fd.append('file',f);
 try{const r=await fetch('/bb/api/upload',{method:'POST',body:fd});const j=await r.json();if(!r.ok||j.error)throw new Error(j.error||'HTTP '+r.status);ST.files.push(j);paintPill();canSend();toast(j.note||T('যোগ হয়েছে','Attached'))}catch(x){toast(x.message)}}
let REC=null;
async function voice(){const b=$('#micb');if(REC){REC.stop();return}
 if(!navigator.mediaDevices?.getUserMedia)return toast(T('এই ব্রাউজারে মাইক নেই','No microphone in this browser'));
 try{const s=await navigator.mediaDevices.getUserMedia({audio:true});const ch=[];REC=new MediaRecorder(s);REC.ondataavailable=e=>ch.push(e.data);
  REC.onstop=async()=>{s.getTracks().forEach(t=>t.stop());REC=null;b.classList.remove('rec');toast(T('লেখায় রূপান্তর হচ্ছে…','Transcribing…'));
   const fd=new FormData();fd.append('file',new Blob(ch,{type:ch[0]?.type||'audio/webm'}),'voice.webm');
   try{const r=await fetch('/bb/api/stt',{method:'POST',body:fd});const j=await r.json();if(!r.ok||j.error)throw new Error(j.error||'HTTP '+r.status);const i=$('#inp');i.value=(i.value?i.value+' ':'')+j.text;i.dispatchEvent(new Event('input'));i.focus()}catch(x){toast(x.message)}};
  REC.start();b.classList.add('rec');toast(T('বলুন… থামাতে আবার চাপুন','Speak… tap again to stop'))}catch(x){toast(T('মাইকের অনুমতি পাওয়া যায়নি','Microphone permission denied'))}}
async function send(){const inp=$('#inp');let t=inp.value.trim();if(!t&&!ST.files.length)return;
 if(ST.files.length){t=ST.files.map(f=>`[📎 ${f.name}]\n${f.text}\n[/📎]`).join('\n')+'\n\n'+(t||T('এই ফাইলটা দেখে সাহায্য করো।','Please help with this file.'));ST.files=[];paintPill()}
 inp.value='';inp.style.height='auto';
 try{if(!ST.chat){const r=await api('/bb/api/chats',{method:'POST',body:'{}'});ST.chat={id:r.id,messages:[]}}}catch(e){return toast(e.message)}
 const sk=ST.activeSkill;run({content:t,skill_id:sk?.id,agent_id:ST.activeAgent?.id},sk)}
async function run(body,sk){if(body.content)addMsg({role:'user',content:body.content});
 const w=addMsg({role:'assistant'});const c=$('.content',w);c.innerHTML=`<span class=typing aria-label="${T('লিখছে','Typing')}"><span></span><span></span><span></span></span>`;scrollEnd();
 ST.ctrl=new AbortController();const sb=$('#send');sb.disabled=false;sb.classList.add('stop');sb.innerHTML=svg('stop');sb.setAttribute('aria-label',T('থামান','Stop'));let txt='',model='';
 try{const r=await fetch(`/bb/api/chats/${ST.chat.id}/stream`,{method:'POST',headers:{'Content-Type':'application/json'},signal:ST.ctrl.signal,
   body:JSON.stringify({...body,model:{fast:'groq:openai/gpt-oss-20b',deep:'auto'}[localStorage.bbTier]||'auto',council:localStorage.bbTier==='deep'})});
  if(!r.ok){const j=await r.json().catch(()=>({}));txt='⚠️ '+(j.error||T('সমস্যা হয়েছে','Something went wrong'))}else{
  const rd=r.body.getReader(),dec=new TextDecoder();let buf='';
  for(;;){const{value,done}=await rd.read();if(done)break;buf+=dec.decode(value,{stream:true});let i;
   while((i=buf.indexOf('\n\n'))>=0){const blk=buf.slice(0,i);buf=buf.slice(i+2);let ev='message',data='';blk.split('\n').forEach(l=>{if(l.startsWith('event:'))ev=l.slice(6).trim();else if(l.startsWith('data:'))data+=l.slice(5).trim()});
    if(!data)continue;let j;try{j=JSON.parse(data)}catch(e){continue}if(ev==='meta'||ev==='done'){model=j.model||model}else if(ev==='memory'){memCue(w,j)}else if(j.d){txt+=j.d;c.replaceChildren(md(txt));scrollEnd()}}}}
 }catch(e){if(e.name==='AbortError')txt+=T(' _(থামানো হয়েছে)_',' _(stopped)_');else txt+=T('\n\n⚠️ সংযোগ কেটে গেছে। আবার চেষ্টা করুন।','\n\n⚠️ Connection lost. Please try again.')}
 ST.ctrl=null;if(sb.isConnected){sb.classList.remove('stop');sb.innerHTML=svg('send');sb.setAttribute('aria-label',T('পাঠান','Send'));canSend()}
 c.replaceChildren(md(txt));meta(w,model,sk);acts(w,{content:txt});scrollEnd()}
/* =============== SKILLS =============== */
let SKF={q:'',cat:'*'};
function pgSkills(){const on=ST.skills.filter(s=>s.enabled&&s.available).length;
 $('#view').innerHTML=shell(T('স্কিল','Skills'),`<p class=sub>${T('টাইগারের দক্ষতা। যেটা দরকার চালু রাখুন — চালু স্কিল চ্যাটে শর্টকাট হয়ে আসবে।','What the Tiger can do. Turn on what you need — enabled skills appear as chat shortcuts.')}</p>
 ${ST.skillsOff?`<div class=note role=status>⏸️ ${esc(ST.skillsOff)}</div>`:''}
 <div class=stats><div class=stat><b>${num(on)}</b><span>${T('চালু','On')}</span></div><div class=stat><b>${num(ST.skills.length)}</b><span>${T('মোট','Total')}</span></div><div class=stat><b>${num(ST.skills.filter(s=>s.perms?.length).length)}</b><span>${T('অনুমতি লাগে','Need approval')}</span></div></div>
 <div class=search>${svg('search')}<input class=fld id=skq placeholder="${T('স্কিল খুঁজুন…','Search skills…')}" aria-label="${T('স্কিল খুঁজুন','Search skills')}" value="${esc(SKF.q)}"></div>
 <div class=chips id=skc role=tablist></div><div class=sgrid id=skg></div>`);
 $('#skq').oninput=e=>{SKF.q=e.target.value;paintSkills()};paintSkills()}
function paintSkills(){const cats=[['*',T('সব','All')],['+',T('চালু','On')],...ST.cats.map(c=>[c,c])];
 $('#skc').innerHTML=cats.map(([k,l])=>`<button role=tab aria-selected="${SKF.cat===k}" class="chip ${SKF.cat===k?'on':''}" data-c="${esc(k)}">${esc(l)}</button>`).join('');
 $$('#skc [data-c]').forEach(b=>b.onclick=()=>{SKF.cat=b.dataset.c;paintSkills()});
 const q=SKF.q.toLowerCase();const L=ST.skills.filter(s=>(SKF.cat==='*'||(SKF.cat==='+'?s.enabled:s.category===SKF.cat))&&(!q||(s.name_bn+s.name_en+s.desc_bn+s.desc_en).toLowerCase().includes(q)));
 $('#skg').innerHTML=L.map(s=>{const off=!s.available,on=s.enabled&&!off;const why={admin_off:T('অ্যাডমিন বন্ধ রেখেছেন','Turned off by admin'),flag_off:T('এই ফিচার এখন বন্ধ','Feature is off'),owner_only:T('শুধু মালিক','Owner only')}[s.why_off]||'';
  const mode={agent:['blue','🤖 '+T('এজেন্ট','Agent')],media:['warn','🎨 '+T('স্টুডিও','Studio')],schedule:['warn','⏰ '+T('শিডিউল','Schedule')]}[s.mode]||['','💬 '+T('চ্যাট','Chat')];
  return `<article class="sk ${on?'on':''} ${off?'off':''}"><div class=ico aria-hidden=true>${s.icon}</div><div class=grow><h3>${esc(T(s.name_bn,s.name_en))}</h3><p>${esc(T(s.desc_bn,s.desc_en))}</p><div class=tags>
  <span class="tag ${mode[0]}">${mode[1]}</span>${s.perms?.length?`<span class="tag red">🔐 ${T('অনুমতি লাগে','Asks first')}</span>`:''}${s.owner_only?`<span class="tag warn">♛ ${T('মালিক','Owner')}</span>`:''}${off&&why?`<span class=tag>⛔ ${why}</span>`:''}</div>
  ${on?`<button class="btn sm use" onclick="useSkill('${s.id}')">${svg('play')} ${T('ব্যবহার করুন','Use')}</button>`:''}</div>
  <button class="sw ${on?'on':''}" role=switch aria-checked="${on}" aria-label="${esc(T(s.name_bn,s.name_en))}" ${off?'disabled':''} onclick="togSkill('${s.id}')"></button></article>`}).join('')||`<div class=empty><div class=big>🔎</div>${T('কিছু পাওয়া যায়নি','Nothing found')}</div>`}
async function togSkill(id){const s=ST.skills.find(x=>x.id===id);const on=!s.enabled;
 if(on&&s.perms?.length&&!await confirmSheet(`${s.icon} ${T(s.name_bn,s.name_en)} ${T('চালু করবেন?','— turn on?')}`,T('এই স্কিল চলার সময় প্রতিটা অ্যাকশনের আগে আপনার অনুমতি চাইবে। যেকোনো সময় বন্ধ করতে পারবেন।','It will ask before every action. You can turn it off any time.'),T('চালু করুন','Turn on')))return;
 try{await api(`/bb/api/v3/skills/${id}/toggle`,{method:'POST',body:JSON.stringify({on})});s.enabled=on;toast(on?T('চালু হয়েছে','Turned on'):T('বন্ধ হয়েছে','Turned off'));paintSkills();paintCtx()}catch(e){toast(e.message)}}
function confirmSheet(title,body,ok){return new Promise(res=>{openSheet(`<h3>${esc(title)}</h3><p class=sub>${esc(body)}</p><div class=btns><button class=btn id=cno>${T('বাতিল','Cancel')}</button><button class="btn pri" id=cyes>${esc(ok)}</button></div>`,
 sh=>{$('#cno',sh).onclick=()=>{closeSheet();res(false)};$('#cyes',sh).onclick=()=>{closeSheet();res(true)}},title)})}
/* =============== AGENTS =============== */
/* ---- agents: helpers ---- */
const RUNS=()=>({done:['ok',T('সম্পন্ন','Completed')],failed:['red',T('ব্যর্থ','Failed')],running:['warn',T('চলছে','Running')],cancelled:['',T('থামানো','Stopped')]});
function agTools(a){if(a.perm_level==='chat_only'||!ST.canTools)return [];const own=ST.me.role==='owner';
 if(!own)return ST.safeTools||['web_search','browse'];const t=new Set();a.skills.forEach(i=>{const s=ST.skills.find(x=>x.id===i);(s?.tools||[]).forEach(x=>t.add(x))});return [...t]}
const TOOLN=()=>({web_search:'🔎 '+T('ওয়েব সার্চ','Web search'),browse:'🌐 '+T('ওয়েবপেজ পড়া','Read web pages'),image_gen:'🎨 '+T('ছবি','Images'),upload:'📎 '+T('ফাইল','Files'),ocr:'🔤 OCR',jobs:'⏰ '+T('শিডিউল','Schedules')});
function agStatus(a){const r=a.runs?.[0];if(!r)return ['idle',T('প্রস্তুত','Ready')];if(r.status==='running')return ['run',T('কাজ চলছে','Working')];if(r.status==='failed')return ['err',T('শেষ কাজ ব্যর্থ','Last run failed')];return ['ok',T('প্রস্তুত','Ready')]}
async function loadAgents(){const j=await api('/bb/api/v3/agents');ST.agents=j.agents;ST.canTools=j.can_tools;ST.safeTools=j.safe_tools;ST.agentsOff=j.off||'';ST.agLimit=j.limit}
const PERML=()=>({ask:T('সব জিজ্ঞেস করে','Asks every time'),safe_auto:T('নিরাপদগুলো নিজে','Safe steps auto'),chat_only:T('শুধু চ্যাট','Chat only')});
const TIERI=()=>({fast:'⚡ '+T('দ্রুত','Fast'),auto:'✨ '+T('অটো','Auto'),deep:'🧠 '+T('গভীর','Deep')});
const ICONS=['🤖','🐯','🧑‍💼','✍️','🔎','💻','🎓','📈','🕌','⚡','🛡️','🎨','📱','📰','🌾','🏏'];
const TCAT=()=>[['all',T('সব','All')],['research',T('গবেষণা','Research')],['learn',T('শিক্ষা','Learning')],['write',T('লেখা','Writing')],['biz',T('ব্যবসা','Business')]];
const TPL=[
 {cat:'research',icon:'🔎',name:'Researcher',name_bn:'গবেষক',persona:'Searches the web for any question, answers briefly and always links its sources.',persona_bn:'যেকোনো প্রশ্নে ওয়েবে খুঁজে সংক্ষেপে উত্তর দেবে, সবসময় সূত্রের লিংক দেবে।',model_tier:'auto',skills:['research','summarize'],perm_level:'safe_auto',ex:'Compare the 3 best budget phones in Bangladesh right now'},
 {cat:'research',icon:'📰',name:'News brief',name_bn:'খবরের সারাংশ',persona:'Gives today\'s top Bangladesh and world news in 5 points, each with a source.',persona_bn:'আজকের বাংলাদেশ ও বিশ্বের বড় খবর ৫টা পয়েন্টে বলবে, প্রতিটার সূত্র দেবে।',model_tier:'fast',skills:['research','summarize'],perm_level:'safe_auto',ex:'Top 5 Bangladesh headlines today'},
 {cat:'learn',icon:'🎓',name:'Study buddy',name_bn:'পড়াশোনার সাথী',persona:'Explains step by step in simple words, then gives a short quiz.',persona_bn:'ধাপে ধাপে সহজ ভাষায় বোঝাবে, শেষে ছোট্ট কুইজ দেবে।',model_tier:'auto',skills:['tutor','summarize'],perm_level:'chat_only',ex:'Explain photosynthesis for class 8'},
 {cat:'learn',icon:'🌐',name:'Language coach',name_bn:'ভাষা শিক্ষক',persona:'Helps practise English and Bangla: corrects mistakes kindly and explains why.',persona_bn:'ইংরেজি ও বাংলা চর্চায় সাহায্য করবে, ভুল ধরিয়ে কেন ভুল তা বোঝাবে।',model_tier:'auto',skills:['translate','tutor'],perm_level:'chat_only',ex:'Correct my email and explain the grammar'},
 {cat:'write',icon:'✍️',name:'Writing assistant',name_bn:'লেখার সহকারী',persona:'Drafts letters, posts and emails in polished language. Never sends — drafts only.',persona_bn:'চিঠি, পোস্ট, ইমেইল সুন্দর ভাষায় লিখে দেবে; পাঠাবে না, শুধু খসড়া দেবে।',model_tier:'auto',skills:['write','mail','translate'],perm_level:'chat_only',ex:'Write a leave application to my manager'},
 {cat:'biz',icon:'📈',name:'Business advisor',name_bn:'ব্যবসার পরামর্শক',persona:'Practical advice on small-business ideas, pricing and marketing; checks market prices when needed.',persona_bn:'ছোট ব্যবসার আইডিয়া, দাম ও মার্কেটিং নিয়ে বাস্তবসম্মত পরামর্শ দেবে; দরকার হলে বাজারদর খুঁজবে।',model_tier:'deep',skills:['biz','research'],perm_level:'ask',ex:'Plan a home bakery in Dhaka with a 50,000 Tk budget'}];
const tName=t=>T(t.name_bn,t.name),tPers=t=>T(t.persona_bn,t.persona);
let TF='all';
async function pgAgents(){$('#view').innerHTML=shell(T('এজেন্ট','Agents'),'<div id=agw><div class="skel tall"></div><div class=skel></div><div class=skel></div></div>');
 try{await loadAgents()}catch(e){$('#agw').innerHTML=`<div class=empty><div class=big>⚠️</div>${esc(e.message)}<br><button class="btn sm" style="margin-top:12px" onclick="pgAgents()">${T('আবার চেষ্টা','Try again')}</button></div>`;return}
 const runs=ST.agents.flatMap(a=>a.runs||[]),live=runs.filter(r=>r.status==='running').length,done=runs.filter(r=>r.status==='done').length;
 const own=ST.me.role==='owner';
 $('#agw').innerHTML=ST.agentsOff?`<div class=empty><div class=big>⏸️</div>${esc(ST.agentsOff)}</div>`:`
 <section class="aghero"><i class=flagline></i><div><b>${T('আপনার ব্যক্তিগত এজেন্ট দল','Your personal agent team')}</b><p>${T('এজেন্ট ধাপে ধাপে কাজ করে, প্রতিটা ঝুঁকির কাজের আগে আপনার অনুমতি নেয়।','Agents work step by step and ask your permission before anything risky.')}</p></div>
 <div class=stats><div class=stat><b>${num(ST.agents.length)}${ST.agLimit?`<small>/${num(ST.agLimit)}</small>`:''}</b><span>${T('এজেন্ট','Agents')}</span></div><div class=stat><b>${num(live)}</b><span>${T('চলছে','Running')}</span></div><div class=stat><b>${num(done)}</b><span>${T('সম্পন্ন','Completed')}</span></div></div></section>
 <div class=guard>${svg('shield')}<span>${own?T('মালিক মোড: স্কিল অনুযায়ী টুল, প্রতিটা ঝুঁকির কাজে অনুমতি কার্ড।','Owner mode: tools follow skills; every risky step shows an Approve card.'):T('নিরাপত্তা: আপনার এজেন্ট শুধু ওয়েব সার্চ ও ওয়েবপেজ পড়তে পারে। পেজ খোলার আগে সবসময় অনুমতি চাইবে; কিছু পাঠানো, কেনা বা মোছা যায় না।','Safety: your agents can only search the web and read pages. They always ask before opening a page and can never send, buy or delete.')}</span></div>
 <div class=sec><h2>${T('আমার এজেন্ট','My agents')}</h2>${ST.agents.length?`<button onclick="editAgent()">+ ${T('নতুন','New')}</button>`:''}</div>
 <div id=aglist>${ST.agents.length?ST.agents.map(agCard).join(''):`<div class="empty card"><img class=sealsm src="${LOGO}" alt="" width=72 height=72><b style="display:block;color:var(--tx);margin-top:8px">${T('এখনো কোনো এজেন্ট নেই','No agents yet')}</b><p class=small>${T('নিচের একটা টেমপ্লেট বেছে নিন, অথবা শূন্য থেকে বানান।','Start from a template below, or build one from scratch.')}</p><button class="btn red" onclick="editAgent()">${svg('plus')} ${T('প্রথম এজেন্ট বানান','Create your first agent')}</button></div>`}</div>
 <div class=sec><h2>${T('টেমপ্লেট গ্যালারি','Template gallery')}</h2></div><div class=chips id=tcat></div><div class=tgal id=tgal></div>`;
 if(!ST.agentsOff)paintTpl()}
function paintTpl(){$('#tcat').innerHTML=TCAT().map(([k,l])=>`<button class="chip ${TF===k?'on':''}" aria-pressed="${TF===k}" onclick="TF='${k}';paintTpl()">${l}</button>`).join('');
 $('#tgal').innerHTML=TPL.map((t,i)=>[t,i]).filter(([t])=>TF==='all'||t.cat===TF).map(([t,i])=>`<button class=tcard onclick="editAgent(null,${i})"><span class=e aria-hidden=true>${t.icon}</span><span class=grow><b>${esc(tName(t))}</b><span>${esc(tPers(t))}</span><span class=tags style="margin-top:6px"><span class="tag blue">${esc(TIERI()[t.model_tier])}</span><span class="tag ${t.perm_level==='chat_only'?'':'warn'}">${t.perm_level==='chat_only'?'💬 '+T('শুধু চ্যাট','Chat only'):'🌐 '+T('ওয়েব','Web')}</span></span></span><span class=chev>›</span></button>`).join('')}
function agCard(a){const sk=id=>ST.skills.find(s=>s.id===id);const [st,stl]=agStatus(a);const tl=agTools(a);const r=a.runs?.[0];const n=(a.runs||[]).length;
 return `<article class=ag><div class=head><div class=em aria-hidden=true>${esc(a.icon)}<i class="sd ${st}"></i></div><div class=grow><h3>${esc(a.name)}</h3><div class="small mut">${esc(stl)} · ${num(n)} ${T('টি কাজ','runs')}</div></div><button class=ib aria-label="${T('এডিট','Edit')}" onclick="editAgent('${a.id}')">${svg('edit')}</button></div>
  <p class=persona>${esc(a.persona||T('কোনো বিশেষ নির্দেশনা নেই','No special instructions'))}</p>
  <div class=caps><span class="tag blue">${esc(TIERI()[a.model_tier]||a.model_tier)}</span><span class="tag ${a.perm_level==='ask'?'warn':a.perm_level==='chat_only'?'':'ok'}">🔐 ${esc(PERML()[a.perm_level]||a.perm_level)}</span>${tl.length?tl.map(t=>`<span class=tag>${esc(TOOLN()[t]||t)}</span>`).join(''):`<span class=tag>💬 ${T('টুল নেই','No tools')}</span>`}</div>
  <div class=skics>${a.skills.map(i=>sk(i)?`<span title="${esc(T(sk(i).name_bn,sk(i).name_en))}" aria-label="${esc(T(sk(i).name_bn,sk(i).name_en))}">${sk(i).icon}</span>`:'').join('')}</div>
  ${r?`<button class=lastrun onclick="go('/v4/agents/${a.id}')"><span class="tag ${(RUNS()[r.status]||[''])[0]}">${esc((RUNS()[r.status]||['',r.status||'—'])[1])}</span><span class="grow t">${esc(r.goal)}</span><span class="small mut">${ago(r.created)}</span></button>`:''}
  <div class=foot><button class="btn red grow" onclick="go('/v4/agents/${a.id}')">${svg('play')} ${T('কাজ দিন','Run a task')}</button><button class=btn aria-label="${T('চ্যাট','Chat')}" onclick="chatAgent('${a.id}')">${svg('chat')}</button><a class=btn href="/schedules" aria-label="${T('নিয়মিত চালান (শিডিউল)','Schedule')}">⏰</a></div></article>`}
function editAgent(id,ti){const base=ST.agents.find(x=>x.id===id)||(ti!=null&&TPL[ti]&&{...TPL[ti],name:tName(TPL[ti]),persona:tPers(TPL[ti])})||{icon:'🤖',name:'',persona:'',model_tier:'auto',skills:['write','summarize'],perm_level:'ask',lang:LANG};const D=JSON.parse(JSON.stringify(base));D.lang=D.lang||LANG;
 const avail=ST.skills.filter(s=>s.available&&(ST.me.role==='owner'||!(s.perms||[]).length||s.id==='research'));D.skills=D.skills.filter(x=>avail.some(s=>s.id===x));
 if(!id&&ST.agLimit&&ST.agents.length>=ST.agLimit)return toast(T('এজেন্টের সীমা পূর্ণ — একটা মুছে নতুন বানান','Agent limit reached — delete one to add another'));
 openSheet(`<h3>${id?T('এজেন্ট এডিট','Edit agent'):T('নতুন এজেন্ট','New agent')}</h3><p class=sub>${T('সব পরে বদলানো যাবে।','You can change everything later.')}</p>
 <div class=stepper><span class=on>1 ${T('পরিচয়','Identity')}</span><span>2 ${T('দক্ষতা','Skills')}</span><span>3 ${T('নিরাপত্তা','Safety')}</span></div>
 <span class=l>${T('আইকন','Icon')}</span><div class=icopick id=ip>${ICONS.map(i=>`<button class="${D.icon===i?'on':''}" data-i="${i}" aria-label="${i}">${i}</button>`).join('')}</div>
 <label class=l for=an>${T('নাম','Name')}</label><input class=fld id=an maxlength=40 placeholder="${T('যেমন: আমার গবেষক','e.g. My researcher')}" value="${esc(D.name)}">
 <label class=l for=ap>${T('স্বভাব, নির্দেশনা ও মনে রাখার কথা','Personality, instructions & notes to remember')}</label><textarea class=fld id=ap rows=4 maxlength=1200 placeholder="${T('যেমন: সংক্ষেপে উত্তর দেবে, সবসময় সূত্র দেবে। আমি ঢাকায় থাকি।','e.g. Keep answers short, always cite sources. I live in Dhaka.')}">${esc(D.persona)}</textarea><div class="small mut" id=apc style="text-align:right">${num((D.persona||'').length)}/${num(1200)}</div>
 <span class=l>${T('উত্তরের ভাষা','Answer language')}</span><div class=seg id=alg>${[['en','English'],['bn','বাংলা']].map(([k,l])=>`<button data-g="${k}" class="${D.lang===k?'on':''}">${l}</button>`).join('')}</div>
 <span class=l>${T('মডেল','Model')}</span><div class=seg id=at>${Object.entries(TIERI()).map(([k,l])=>`<button data-k="${k}" class="${D.model_tier===k?'on':''}">${l}</button>`).join('')}</div>
 <span class=l>${T('স্কিল','Skills')} (${num(avail.length)})</span><div class=pick id=as>${avail.map(s=>`<button data-s="${s.id}" class="${D.skills.includes(s.id)?'on':''}" aria-pressed="${D.skills.includes(s.id)}">${s.icon} ${esc(T(s.name_bn,s.name_en))}</button>`).join('')}</div>
 <span class=l>${T('অনুমতির ধরন','Permission level')}</span><div class=radio id=al>${[['ask',T('প্রতিটা অ্যাকশনে জিজ্ঞেস করবে','Ask before every action'),T('সবচেয়ে নিরাপদ (প্রস্তাবিত)','Safest (recommended)')],['safe_auto',T('সার্চ নিজে করবে','Search on its own'),T('ওয়েবপেজ খোলা ও যেকোনো ঝুঁকির কাজের আগে সবসময় জিজ্ঞেস করবে','Always asks before opening a page or anything risky')],['chat_only',T('কোনো টুল নয়','No tools'),T('শুধু কথা বলবে','Talk only')]].map(([k,b,s])=>`<button data-l="${k}" class="${D.perm_level===k?'on':''}"><i class=dot></i><span><b>${b}</b><span>${s}</span></span></button>`).join('')}</div>
 <div class=btns style="margin-top:20px">${id?`<button class="btn dan" id=adel>${T('মুছুন','Delete')}</button>`:''}<button class=btn onclick="closeSheet()">${T('বাতিল','Cancel')}</button><button class="btn red" id=asave>${T('সেভ','Save')}</button></div>`,sh=>{
  const sel=(box,attr,key)=>{$(box,sh).onclick=e=>{const b=e.target.closest(`[${attr}]`);if(!b)return;D[key]=b.getAttribute(attr);$$(box+' button',sh).forEach(x=>x.classList.toggle('on',x===b))}};
  sel('#ip','data-i','icon');sel('#at','data-k','model_tier');sel('#al','data-l','perm_level');sel('#alg','data-g','lang');
  $('#ap',sh).oninput=e=>{$('#apc',sh).textContent=num(e.target.value.length)+'/'+num(1200)};
  $('#as',sh).onclick=e=>{const b=e.target.closest('[data-s]');if(!b)return;const s=b.dataset.s;D.skills=D.skills.includes(s)?D.skills.filter(x=>x!==s):[...D.skills,s];b.classList.toggle('on');b.setAttribute('aria-pressed',b.classList.contains('on'))};
  $('#asave',sh).onclick=async()=>{D.name=$('#an',sh).value.trim()||T('আমার এজেন্ট','My agent');D.persona=$('#ap',sh).value.trim();
   try{await api('/bb/api/v3/agents'+(id?'/'+id:''),{method:id?'PUT':'POST',body:JSON.stringify({icon:D.icon,name:D.name,persona:D.persona,model_tier:D.model_tier,skills:D.skills,perm_level:D.perm_level,lang:D.lang})});closeSheet();toast(T('সেভ হয়েছে','Saved'));route()}catch(e){toast(e.message)}};
  if(id)$('#adel',sh).onclick=async()=>{if(!await confirmSheet(T('এজেন্ট মুছবেন?','Delete agent?'),T('এর কাজের ইতিহাস কার্যকলাপে থেকে যাবে।','Its history stays in Activity.'),T('মুছুন','Delete')))return;try{await api('/bb/api/v3/agents/'+id,{method:'DELETE'})}catch(e){toast(e.message)}go('/v4/agents')}},T('এজেন্ট','Agent'))}
async function pgAgent(id){if(!ST.agents.length)try{await loadAgents()}catch(e){}const a=ST.agents.find(x=>x.id===id);if(!a)return go('/v4/agents',true);
 const tl=agTools(a),[st,stl]=agStatus(a);const tp=TPL.find(t=>t.icon===a.icon);const ex=[tp?.ex||T('ঢাকার আজকের আবহাওয়া ৩ লাইনে বলো','Dhaka weather today in 3 lines'),T('এই সপ্তাহের ৩টা টেক খবর সূত্রসহ','3 tech news items this week with sources'),T('ঈদের ছুটিতে কক্সবাজার ট্রিপের বাজেট','Budget for a Cox\'s Bazar trip')];
 $('#view').innerHTML=topbar(`<div class="who ttl"><div class=em style="width:42px;height:42px;font-size:22px" aria-hidden=true>${esc(a.icon)}<i class="sd ${st}"></i></div><div><b>${esc(a.name)}</b><small>${esc(stl)} · ${esc(PERML()[a.perm_level]||'')}</small></div></div>`,
  `<button class=ib aria-label="${T('ফিরে যান','Back')}" onclick="go('/v4/agents')">${svg('back')}</button>`,`<button class=ib aria-label="${T('এডিট','Edit')}" onclick="editAgent('${a.id}')">${svg('edit')}</button>`)+
 `<div class=page><div class=wrap><div class="card taskcard"><label class=l for=goal style="margin-top:0">${T('কী করতে হবে?','What should it do?')}</label><textarea class=fld id=goal rows=3 placeholder="${esc(ex[0])}"></textarea>
 <div class=chips style="padding:8px 0 0">${ex.map(x=>`<button class=chip data-ex="${esc(x)}">${esc(x)}</button>`).join('')}</div>
 <div class=btns><button class="btn red" id=runb ${ST.canTools?'':'disabled'}>${svg('play')} ${T('শুরু করুন','Start task')}</button><button class=btn id=demob title="${T('মডেল ছাড়া UI দেখার জন্য','UI demo without a model')}">${T('ডেমো','Demo')}</button></div>
 <button class="btn full ghost" style="margin-top:8px" onclick="chatAgent('${a.id}')">${svg('chat')} ${T('এই এজেন্টের সাথে চ্যাট','Chat with this agent')}</button></div>
 <div class=capgrid><div class=card><span class=l style="margin-top:0">✅ ${T('যা পারে','Can do')}</span>${(tl.length?tl:['chat']).map(t=>`<div class=small>${esc(t==='chat'?'💬 '+T('কথা বলা, লেখা, বিশ্লেষণ','Talk, write, analyse'):TOOLN()[t]||t)}</div>`).join('')}</div>
 <div class=card><span class=l style="margin-top:0">🚫 ${T('যা পারে না','Never does')}</span><div class=small>${T('কিছু পাঠানো / পোস্ট','Send or post')}</div><div class=small>${T('কেনাকাটা / পেমেন্ট','Buy or pay')}</div><div class=small>${T('ফাইল মোছা','Delete files')}</div>${ST.me.role==='owner'?'':`<div class=small>${T('ডিভাইস / সার্ভার','Devices / server')}</div>`}</div></div>
 <button class="picard slim" onclick="openMemory()"><span class=pib aria-hidden=true>🧠</span><span class=grow><b>${T('পার্সোনাল ইন্টেলিজেন্স','Personal Intelligence')}</b><small>${ST.set?.memory!==false?T('এই এজেন্ট আপনার মেমরি ব্যবহার করে, আর আপনার দেওয়া কাজ থেকে শেখে।','This agent uses your memory and learns from the tasks you give it.'):T('শেখা বন্ধ আছে — চালু করতে ট্যাপ করুন।','Learning is off — tap to turn it on.')}</small></span><span class=chev>›</span></button>
 ${!ST.canTools?`<div class=note>ℹ️ ${T('টুলসহ এজেন্ট এখন চালু নেই — চ্যাটে কথা বলুন।','Tool agents are switched off right now — use chat instead.')}</div>`:''}
 <div id=runv></div>
 <div class=sec><h2>${T('কাজের ইতিহাস','Run history')}</h2><a href="/schedules">⏰ ${T('নিয়মিত চালান','Make it recurring')}</a></div><div class=card style="padding:4px 14px" id=hist>${(a.runs||[]).map(r=>{const s=RUNS()[r.status]||['',r.status||'—'];return `<div class=hist><span class="tag ${s[0]}">${esc(s[1])}</span><span class="grow" style="overflow:hidden;white-space:nowrap;text-overflow:ellipsis">${esc(r.goal)}<div class="small mut">${ago(r.created)}</div></span><button class="btn sm" onclick="watch('${r.task_id}',this.closest('.hist').querySelector('.grow').firstChild.textContent)">${T('দেখুন','View')}</button></div>`}).join('')||`<div class=empty style="padding:22px">🗂️<br>${T('এখনো কোনো কাজ দেননি — উপরে একটা কাজ লিখে শুরু করুন।','No runs yet — describe a task above to start.')}</div>`}</div></div></div>`;
 $$('[data-ex]').forEach(b=>b.onclick=()=>{$('#goal').value=b.dataset.ex;$('#goal').focus()});
 $('#runb').onclick=async()=>{const g=$('#goal').value.trim();if(!g)return toast(T('কাজটা লিখুন','Describe the task first'));$('#runb').disabled=true;try{const r=await api(`/bb/api/v3/agents/${id}/run`,{method:'POST',body:JSON.stringify({goal:g})});watch(r.task,g)}catch(e){toast(e.message)}$('#runb').disabled=false};
 $('#demob').onclick=()=>demoRun($('#goal').value.trim()||ex[0])}
const LAB=()=>({plan:['🗺️ '+T('পরিকল্পনা','Plan'),''],think:['💭 '+T('ভাবছি','Thinking'),''],run:['▶️ '+T('টুল চলছে','Using tool'),'running'],result:['✅ '+T('ফলাফল','Result'),'ok'],error:['❌ '+T('সমস্যা','Error'),'err'],retry:['🔁 '+T('আবার চেষ্টা','Retry'),''],repair:['🛠️ '+T('ঠিক করছি','Repairing'),''],
 auto:['🔓 '+T('নিজে অনুমতি দেওয়া','Auto-approved'),'ok'],blocked:['⛔ '+T('বন্ধ','Blocked'),'err'],final:['🏁 '+T('চূড়ান্ত উত্তর','Final answer'),'ok fin'],approval:['🔐 '+T('আপনার অনুমতি দরকার','Your approval is needed'),'ask'],resume:['♻️ '+T('আবার শুরু','Resumed'),'']});
const RISK=()=>({high:T('বেশি','High'),medium:T('মাঝারি','Medium'),low:T('কম','Low')});
function stepEl(box,e,tid,demo){if(!box||e.type==='end')return;
 if(e.type==='decision'){const a=$(`[data-aid="${CSS.escape(String(e.id))}"]`,box);if(a){a.classList.add('decided');$('.btns',a).innerHTML=e.decision==='yes'?`<span class="tag ok">✅ ${T('অনুমতি দিয়েছেন','You approved')}</span>`:`<span class="tag red">🚫 ${T('অনুমতি দেননি','You declined')}</span>`}return}
 $$('.st.running',box).forEach(x=>x.classList.remove('running'));
 const [lab,cls]=LAB()[e.type]||[e.type,''];const d=document.createElement('div');d.className='st '+cls;const tm=new Date().toLocaleTimeString(LANG==='en'?'en-GB':'bn-BD',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
 if(e.type==='approval'){let host='';try{host=e.args?.url?new URL(e.args.url).hostname:''}catch(x){}
  d.innerHTML=`<div class=lab>${lab}</div><div class="appr risk-${esc(e.risk||'medium')}" data-aid="${esc(e.id)}" role=group aria-label="${T('অনুমতি কার্ড','Approval card')}"><div class=t>${svg('shield')} ${host?T('এই সাইট খুলবে?','Open this site?'):T('অনুমতি দেবেন?','Allow this step?')}</div>
  ${host?`<div class=host>🌐 ${esc(host)}</div>`:''}<div class="small mut" style="margin-top:4px">${esc(e.capname||'')} · ${T('টুল','tool')} <code>${esc(e.tool)}</code> · ${T('ঝুঁকি','risk')} <span class="tag ${e.risk==='high'?'red':'warn'}">${esc(RISK()[e.risk]||e.risk||'—')}</span></div>
  <details><summary>${T('বিস্তারিত','Details')}</summary><pre>${esc(JSON.stringify(e.args,null,1))}</pre></details><div class=small><b>${T('কেন','Why')}:</b> ${esc(e.why||'')}</div><div class=btns><button class=btn data-ok=0>🚫 ${T('না','Deny')}</button><button class="btn pri" data-ok=1>✅ ${T('অনুমতি দিন','Approve')}</button></div></div>`;
  $$('[data-ok]',d).forEach(b=>b.onclick=async()=>{const ok=b.dataset.ok==='1';$$('[data-ok]',d).forEach(x=>x.disabled=true);if(demo)return demo(ok,e.id);try{await api('/bb/api/approvals/'+e.id,{method:'POST',body:JSON.stringify({ok})})}catch(x){toast(x.message);$$('[data-ok]',d).forEach(x=>x.disabled=false)}})}
 else{d.innerHTML=`<div class=lab>${lab}${e.step?' · '+T('ধাপ ','step ')+num(e.step):''}<time>${tm}</time></div><div class=body></div>`;const b=$('.body',d);
  if(e.type==='run')b.innerHTML=`<code>${esc(e.tool)}</code>`;else if(e.type==='result'||e.type==='error'){b.innerHTML='<pre></pre>';$('pre',b).textContent=e.text||''}
  else if(e.type==='final')b.replaceChildren(md(e.text));else b.textContent=e.text||''}
 box.appendChild(d);const pb=box.closest('.runcard')?.querySelector('.prog i');if(pb){const n=$$('.st',box).length;pb.style.width=(e.type==='final'?100:Math.min(92,n*14))+'%'}
 d.scrollIntoView({block:'nearest',behavior:'smooth'})}
function runCard(goal,tag){return `<div class="card runcard" style="margin-top:12px"><div class=row><b class=grow>${esc(goal)}</b><span class="tag warn" id=rst>${tag}</span></div><div class=prog aria-hidden=true><i></i></div><div class=tl id=tl aria-live=polite></div></div>`}
async function watch(tid,goal){const v=$('#runv');if(!v)return;v.innerHTML=runCard(goal||T('কাজ','Task'),T('চলছে','Running'));$('#rst').insertAdjacentHTML('afterend',`<button class="btn sm dan" id=cxl style="margin-left:6px" aria-label="${T('কাজ থামান','Stop task')}">⏹ ${T('থামান','Stop')}</button>`);
 v.scrollIntoView({behavior:'smooth'});
 $('#cxl').onclick=async()=>{if(!await confirmSheet(T('কাজটা থামাবেন?','Stop this task?'),T('থামালে আর আবার চালু হবে না।','A stopped task will not resume.'),T('থামান','Stop')))return;try{await api(`/bb/api/v3/runs/${tid}/cancel`,{method:'POST',body:'{}'});toast(T('থামানো হচ্ছে…','Stopping…'))}catch(e){toast(e.message)}};
 let n=0,idle=0;for(;;){let j;try{j=await api(`/bb/api/v3/runs/${tid}?since=${n}`)}catch(e){if($('#rst'))$('#rst').textContent=e.status===404?T('পাওয়া যায়নি','Not found'):T('ত্রুটি','Error');break}
  if(!$('#tl'))break;n=typeof j.n==='number'?j.n:n+j.events.length;j.events.forEach(e=>stepEl($('#tl'),e,tid));
  if(j.status!=='running'){$('#rst').textContent=(RUNS()[j.status]||['',T('থেমেছে','Ended')])[1];$('#rst').className='tag '+(j.status==='done'?'ok':'red');$('#cxl')?.remove();const pb=$('.runcard .prog i');if(pb)pb.style.width='100%';break}
  idle=j.events.length?0:idle+1;await new Promise(r=>setTimeout(r,document.hidden?4000:Math.min(600+idle*250,2500)))}}
async function demoRun(goal){const v=$('#runv');v.innerHTML=runCard(goal,T('ডেমো · চলছে','Demo · running'));
 const tl=$('#tl');const W=ms=>new Promise(r=>setTimeout(r,ms));
 stepEl(tl,{type:'plan',text:T('১) ওয়েবে খুঁজব ২) একটা আবহাওয়া সাইট খুলে পড়ব ৩) ৩ লাইনে সারাংশ দেব','1) search the web 2) open a weather site 3) summarise in 3 lines')});await W(250);
 stepEl(tl,{type:'think',step:1,text:T('প্রথমে ঢাকার আজকের আবহাওয়া সার্চ করি।','First, search for Dhaka weather today.')});await W(250);
 stepEl(tl,{type:'run',tool:'web_search'});await W(350);stepEl(tl,{type:'result',text:'5 results: bmd.gov.bd, accuweather.com …'});await W(250);
 const decided=new Promise(res=>stepEl(tl,{type:'approval',id:'demo1',tool:'browse',capname:'🌐 '+T('ব্রাউজার নিয়ন্ত্রণ','Browser'),risk:'medium',args:{url:'https://www.bmd.gov.bd/'},why:T('আবহাওয়া অধিদপ্তরের পেজ থেকে সঠিক তথ্য পড়তে','To read accurate data from the Met Department')},null,(ok,id)=>{stepEl(tl,{type:'decision',id,decision:ok?'yes':'no'});res(ok)}));
 window._demoDecided=decided;const ok=await decided;
 if(ok){stepEl(tl,{type:'run',tool:'browse'});await W(400);stepEl(tl,{type:'result',text:T('সর্বোচ্চ ৩২°, সর্বনিম্ন ২৫°, বিকেলে হালকা বৃষ্টির সম্ভাবনা ৪০%','High 32°, low 25°, 40% chance of light rain in the afternoon')})}
 stepEl(tl,{type:'final',text:T('**ঢাকা, আজ:** দিনে গরম, সর্বোচ্চ ৩২°সে।\n\nবিকেলে হালকা বৃষ্টির সম্ভাবনা ৪০%, ছাতা রাখুন।\n\nরাতে তাপমাত্রা নামবে ২৫°সে-এ। _(ডেমো ডেটা)_','**Dhaka today:** hot, high 32°C.\n\n40% chance of light rain in the afternoon.\n\nLow 25°C at night. _(demo data)_')});
 if($('#rst')){$('#rst').textContent=T('ডেমো · সম্পন্ন','Demo · done');$('#rst').className='tag ok'}}
/* =============== ACTIVITY =============== */
async function pgActivity(){$('#view').innerHTML=shell(T('কার্যকলাপ','Activity'),'<div id=acw><div class=skel></div><div class=skel></div><div class=skel></div></div>');
 let D;try{D=await api('/bb/api/activity')}catch(e){$('#acw').innerHTML=`<div class=empty>${esc(e.message)}</div>`;return}
 const KN={agent:T('এজেন্ট','Agent'),schedule:T('শিডিউল','Schedule'),skill:T('স্কিল','Skill'),media:T('মিডিয়া','Media'),shell:T('সার্ভার কমান্ড','Shell'),approval:T('অনুমতি','Approval'),push:T('নোটিফিকেশন','Notification'),browse:T('ব্রাউজার','Browser'),device:T('ডিভাইস','Device')};
 const VB={create:T('তৈরি','created'),update:T('বদল','updated'),edit:T('এডিট','edited'),delete:T('মোছা','deleted'),run:T('চালানো','ran'),task:T('কাজ','task'),toggle:T('চালু/বন্ধ','toggled'),save:T('সেভ','saved'),propose:T('প্রস্তাব','proposed'),subscribe:T('চালু','subscribed'),shell:T('চালানো','ran'),use:T('ব্যবহার','used')};
 const lbl=x=>(KN[x.kind]||x.kind)+' · '+(VB[x.tool]||(String(x.tool||'').includes(':')?x.tool.split(':').pop():x.tool||''));
 const KI={schedule:'⏰',push:'🔔',agent:'🤖',shell:'🖥️',browse:'🌐',device:'📱',media:'🎨',approval:'🔐',skill:'✨'};
 const dayOf=ts=>{const d=new Date(ts*1000),n=new Date();const k=d.toDateString();if(k===n.toDateString())return T('আজ','Today');n.setDate(n.getDate()-1);if(k===n.toDateString())return T('গতকাল','Yesterday');return d.toLocaleDateString(LANG==='en'?'en-GB':'bn-BD',{day:'numeric',month:'long'})};
 ST.approvals=D.approvals?.length||0;paintNav();let lastDay='';
 $('#acw').innerHTML=(ST.approvals?`<div class=sec style="margin-top:4px"><h2>⏳ ${T('আপনার অনুমতির অপেক্ষায়','Waiting for your approval')} (${num(ST.approvals)})</h2></div>`+D.approvals.map(a=>`<div class=appr style="margin-bottom:10px"><div class=t>${svg('shield')} ${esc(a.tool)}</div><pre>${esc(a.args)}</pre><div class=btns><button class=btn onclick="dec('${esc(a.id)}',0)">🚫 ${T('না','No')}</button><button class="btn pri" onclick="dec('${esc(a.id)}',1)">✅ ${T('অনুমতি','Allow')}</button></div></div>`).join(''):'')+
 `<p class=sub>${T('আপনার হয়ে টাইগার যা যা করেছে, সব এখানে। কিছুই লুকানো নেই।','Everything the Tiger did for you. Nothing hidden.')}</p>`+
 ((D.items||[]).slice(0,80).map(x=>{const dd=dayOf(x.ts);const h=dd!==lastDay?`<div class=day>${dd}</div>`:'';lastDay=dd;
  return h+`<div class=act><span class=ki aria-hidden=true>${KI[x.kind]||'•'}</span><div class=grow><div class=row style="gap:6px"><b class=grow>${esc(lbl(x))}</b><span class="tag ${x.ok?'ok':'red'}" aria-label="${x.ok?T('সফল','ok'):T('ব্যর্থ','failed')}">${x.ok?'✓':'✗'}</span></div><div class="small mut" style="word-break:break-word">${esc(String(x.input||'').slice(0,140))}</div><div class="small mut">${ago(x.ts)}</div></div></div>`}).join('')||`<div class=empty><div class=big>📋</div>${T('এখনো কিছু নেই','Nothing yet')}</div>`)}
async function dec(id,ok){try{await api('/bb/api/approvals/'+id,{method:'POST',body:JSON.stringify({ok:!!ok})});toast(ok?T('অনুমতি দেওয়া হয়েছে','Approved'):T('বাতিল করা হয়েছে','Declined'))}catch(e){toast(e.message)}pgActivity()}
/* =============== ME =============== */
function openMe(){const t=localStorage.bbTheme||'dark';const own=ST.me.role==='owner';const row=(i,l,h,x='')=>`<a class=li href="${h}"><span class=ki aria-hidden=true>${i}</span><span class=grow>${l}</span>${x}<span class=chev aria-hidden=true>›</span></a>`;
 openSheet(`<div class=prof>${avatar()}<div class=grow><b style="font-size:17px">${esc(own?T('জাহাঁপনা','Your Majesty'):(ST.me.name||ST.me.email||''))}</b><div><small>${esc(ST.me.email||'')}</small></div>${own?`<span class=tag style="margin-top:6px;background:rgba(255,255,255,.15);color:#fff">♛ ${T('মালিক','Owner')}</span>`:''}</div></div>
 <span class=l>${T('থিম','Theme')}</span><div class=seg role=group aria-label="${T('থিম','Theme')}">${[['dark','🌙 '+T('ডার্ক','Dark')],['light','☀️ '+T('লাইট','Light')],['system','📱 '+T('সিস্টেম','System')]].map(([k,l])=>`<button aria-pressed="${t===k}" class="${t===k?'on':''}" onclick="setTheme('${k}');openMe()">${l}</button>`).join('')}</div>
 <span class=l>${T('ভাষা','Language')}</span><div class=seg role=group aria-label="${T('ভাষা','Language')}">${[['bn','বাংলা'],['en','English']].map(([k,l])=>`<button aria-pressed="${LANG===k}" class="${LANG===k?'on':''}" onclick="saveSet({lang:'${k}'})">${l}</button>`).join('')}</div>
 <button class=picard onclick="openMemory()"><span class=pib aria-hidden=true>🧠</span><span class=grow><b>${T('পার্সোনাল ইন্টেলিজেন্স','Personal Intelligence')}</b><small>${ST.set?.memory!==false?T('চালু · টাইগার আপনার চ্যাট ও কাজ থেকে শিখছে','On · the Tiger learns from your chats and tasks'):T('বন্ধ · নতুন কিছু শিখছে না','Off · not learning anything new')}</small></span><span class="tag ${ST.set?.memory!==false?'ok':''}">${ST.set?.memory!==false?T('চালু','On'):T('বন্ধ','Off')}</span></button>
 <button class=picard onclick="openRoyalLink()"><span class=pib aria-hidden=true>📱</span><span class=grow><b>${T('রয়্যাল লিংক · স্ক্রিন ও SMS','Royal Link · Screen & SMS')}</b><small>${T('Accessibility দিয়ে ফোনের স্ক্রিন পড়া ও SMS খসড়া — প্রতিবার আপনার অনুমতিতে','Read your phone screen & draft SMS via Accessibility — only with your approval')}</small></span><span class=chev aria-hidden=true>›</span></button>
 <div class=group>${row('⏰',T('শিডিউল','Schedules'),'/schedules')}${row('🔌',T('কানেকশন','Connections'),'/connections')}${row('🎨',T('স্টুডিও','Studio'),'/studio')}${row('🔑',T('নিজের API কী (BYOK)','My API keys (BYOK)'),'/studio#keys')}${row('💳',T('অ্যাকাউন্ট ও প্ল্যান','Account & plan'),'/account')}</div>
 <div class=group>${own?row('🛡️',`<b>${T('অ্যাডমিন ড্যাশবোর্ড','Admin dashboard')}</b>`,'/admin/dash',`<span class="tag warn">${T('মালিক','Owner')}</span>`):''}
 <a class=li href="/logout"><span class=ki aria-hidden=true>↩︎</span><span class=grow style="color:var(--red2)">${T('লগআউট','Log out')}</span></a></div>
 <p class="small mut" style="text-align:center;margin-top:14px"><span class=wmi>The Royal Bengal Tiger</span></p>`,null,T('আমি','Me'))}
async function saveSet(p){try{ST.set=await api('/bb/api/settings',{method:'PUT',body:JSON.stringify(p)});if(p.lang){LANG=p.lang==='bn'?'bn':'en';localStorage.bbV4Lang=LANG;document.cookie='bb_lang='+LANG+';path=/;max-age=31536000;samesite=lax';localStorage.bbLang=LANG;document.documentElement.lang=LANG;
  $('#tabs').innerHTML=navHTML();$('.sidenav').innerHTML=navHTML();route()}toast(T('সংরক্ষণ হয়েছে','Saved'));openMe()}catch(e){toast(e.message)}}
/* ---------- boot ---------- */
(async()=>{$('#tabs').innerHTML=navHTML();$('.sidenav').innerHTML=navHTML();
 const [me,set,sk]=await Promise.allSettled([api('/bb/api/me'),api('/bb/api/settings'),api('/bb/api/v3/skills')]);
 if(me.status==='fulfilled')ST.me=me.value;if(set.status==='fulfilled'){ST.set=set.value;}
 if(sk.status==='fulfilled'){ST.skills=sk.value.skills||[];ST.cats=sk.value.categories||[];ST.skillsOff=sk.value.off||''}
 const q=new URLSearchParams(location.search);route();const sh=[q.get('title'),q.get('text'),q.get('url')].filter(Boolean).join('\n');if(sh&&$('#inp')){$('#inp').value=sh;$('#inp').dispatchEvent(new Event('input'))}
 try{const D=await api('/bb/api/activity');ST.approvals=D.approvals?.length||0;paintNav()}catch(e){}
 if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js',{scope:'/'}).catch(()=>{})})();

/* ---------- Personal Intelligence (memory) ---------- */
const MK=()=>({fact:['👤',T('তথ্য','Facts')],preference:['💚',T('পছন্দ','Preferences')],project:['🚀',T('চলমান কাজ','Projects')],note:['📝',T('নোট','Notes')]});
const MSRC=()=>({chat:T('চ্যাট থেকে শেখা','Learned from chat'),agent:T('এজেন্টের কাজ থেকে','Learned from an agent task'),manual:T('আপনি যোগ করেছেন','Added by you')});
function memCue(w,j){const b=document.createElement('button');b.className='memcue';b.setAttribute('aria-label',T('মেমরি ব্যবহার হয়েছে','Memory used'));
 b.innerHTML=`🧠 ${T(`আপনার ${num(j.n)}টা কথা মনে রেখে`,`Remembered ${j.n} thing${j.n>1?'s':''} about you`)}`;
 b.onclick=()=>openSheet(`<h3>🧠 ${T('এই উত্তরে যা মনে রাখা হয়েছে','Used in this answer')}</h3><p class=sub>${T('শুধু আপনার নিজের মেমরি — অন্য কেউ দেখে না।','Only your own memory — nobody else can see it.')}</p>${(j.items||[]).map(x=>`<div class=memi><span class=grow>${esc(x)}</span></div>`).join('')}<div class=btns style="margin-top:16px"><button class="btn pri" onclick="openMemory()">${T('সব মেমরি দেখুন','See all memory')}</button></div>`,null,T('মেমরি','Memory'));
 const c=$('.content',w);c.parentNode.insertBefore(b,c)}
let MF='all';
async function memPending(sh){let P;try{P=await api('/bb/api/memory/pending')}catch(e){return}const it=P.items||[];if(!it.length)return;
 const box=$('#mpend',sh);box.innerHTML=`<div class=group style="padding:10px;border:1px solid var(--gold,#c9a227);border-radius:14px;margin:8px 0"><b>✨ ${T('টাইগার এগুলো মনে রাখতে চায় — আপনি অনুমোদন দিন','The Tiger wants to remember — your approval')} (${num(it.length)})</b>${it.map(p=>`<div class=memi data-pid="${p.id}"><span class=grow><span class=mt>${esc(p.text)}</span><small>${esc(p.kind)} · ${esc(p.source)}${p.why?' · '+esc(p.why):''}</small></span><button class="btn" data-pa>${T('রাখুন','Keep')}</button><button class=ib data-pd aria-label="${T('বাদ','Discard')}">${svg('x')}</button></div>`).join('')}</div>`;
 box.onclick=async e=>{const r=e.target.closest('[data-pid]');if(!r)return;const a=e.target.closest('[data-pa]')?'approve':e.target.closest('[data-pd]')?'discard':null;if(!a)return;try{await api('/bb/api/memory/pending/'+r.dataset.pid,{method:'POST',body:JSON.stringify({action:a})});toast(a==='approve'?T('মনে রাখা হলো','Remembered'):T('বাদ দেওয়া হলো','Discarded'));openMemory()}catch(x){toast(x.message)}}}
async function openMemory(){let D;try{D=await api('/bb/api/memory')}catch(e){return toast(e.message)}
 const on=D.enabled,items=D.items||[],cnt=k=>items.filter(i=>(i.kind||'fact')===k).length;
 const list=items.filter(i=>MF==='all'||(i.kind||'fact')===MF);
 openSheet(`<div class=pihero><i class=flagline></i><div class=pib aria-hidden=true>🧠</div><div class=grow><b>${T('পার্সোনাল ইন্টেলিজেন্স','Personal Intelligence')}</b><small>${T('টাইগার আপনার কথা ও কাজ থেকে শেখে, যাতে প্রতিবার আরও আপনার মতো উত্তর দেয়।','The Tiger learns from what you say and do, so every answer fits you better.')}</small></div></div>
 <div class=group><label class=li><span class=ki aria-hidden=true>✨</span><span class=grow>${T('চ্যাট ও এজেন্টের কাজ থেকে শিখুক','Learn from my chats and agent tasks')}<small style="display:block" class=mut>${T('বন্ধ করলে নতুন কিছু শিখবে না, মনে রাখা কথাও ব্যবহার করবে না।','When off, it learns nothing new and does not use saved memory.')}</small></span><input type=checkbox class=tg id=pion ${on?'checked':''} aria-label="${T('শেখা চালু','Learning on')}"></label></div>
 ${D.usage?`<div class="small mut" style="padding:6px 2px">USER ${num(D.usage.user.items)}/${num(D.usage.user.max_items)} · MEMORY ${num(D.usage.memory.items)}/${num(D.usage.memory.max_items)} ${T('(সীমা পূর্ণ হলে পুরনোটা বাদ যায়)','(oldest drops when full)')}</div>`:''}
 <div id=mpend></div><div class=row style="gap:8px;margin:6px 0"><input class="fld grow" id=msq placeholder="${T('মেমরিতে খুঁজুন','Search memory')}"><button class="btn" id=msqb>${T('খুঁজুন','Search')}</button></div><div id=msr></div>
 <div class=mstats>${Object.entries(MK()).map(([k,[i,l]])=>`<div><b>${i} ${num(cnt(k))}</b><span>${l}</span></div>`).join('')}</div>
 <div class=chips style="padding:10px 0 4px">${[['all',T('সব','All')+' · '+num(items.length)],...Object.entries(MK()).map(([k,[i,l]])=>[k,l])].map(([k,l])=>`<button class="chip ${MF===k?'on':''}" aria-pressed="${MF===k}" data-mf="${k}">${l}</button>`).join('')}</div>
 <div id=mlist>${list.length?list.map(m=>`<div class=memi data-id="${m.id}"><span class=mk aria-hidden=true>${(MK()[m.kind]||MK().fact)[0]}</span><span class=grow><span class=mt>${esc(m.text)}</span><small>${esc(MSRC()[m.source]||MSRC().manual)} · ${ago(m.updated||m.created)}</small></span><button class=ib data-ed aria-label="${T('এডিট','Edit')}">${svg('edit')}</button><button class=ib data-del aria-label="${T('মুছুন','Delete')}">${svg('x')}</button></div>`).join(''):`<div class=empty style="padding:24px 8px">🌱<br><b style="color:var(--tx)">${T('এখনো কিছু শেখেনি','Nothing learned yet')}</b><br><small>${T('নিজের সম্পর্কে বলুন — যেমন "আমি ঢাকায় থাকি, ছোট ব্যবসা করি" — অথবা নিচে নিজে যোগ করুন।','Tell the Tiger about yourself — e.g. "I live in Dhaka and run a small shop" — or add something below.')}</small></div>`}</div>
 <label class=l for=madd>${T('নিজে কিছু যোগ করুন','Add something yourself')}</label><div class=row style="gap:8px"><input class="fld grow" id=madd maxlength=400 placeholder="${T('যেমন: উত্তর ছোট রাখবে','e.g. Keep answers short')}"><select class=fld id=mkind style="width:auto">${Object.entries(MK()).map(([k,[i,l]])=>`<option value="${k}" ${k==='note'?'selected':''}>${i} ${l}</option>`).join('')}</select></div>
 <div class=btns style="margin-top:10px"><button class="btn dan" id=mclr ${items.length?'':'disabled'}>${T('সব মুছুন','Clear all')}</button><button class="btn red" id=maddb>${svg('plus')} ${T('যোগ করুন','Add')}</button></div>
 <p class="small mut" style="margin-top:12px">🔒 ${T('মেমরি শুধু আপনার অ্যাকাউন্টে থাকে, অন্য কোনো ব্যবহারকারী দেখতে বা ব্যবহার করতে পারে না। পাসওয়ার্ড, OTP বা কার্ড নম্বর কখনো মনে রাখা হয় না।','Memory stays in your account only — no other user can see or use it. Passwords, OTPs and card numbers are never saved.')}</p>`,sh=>{
  memPending(sh);
  $('#msqb',sh).onclick=async()=>{const q=$('#msq',sh).value.trim();if(!q)return;try{const r=await api('/bb/api/memory/search?q='+encodeURIComponent(q));$('#msr',sh).innerHTML=(r.items||[]).map(m=>`<div class=memi><span class=grow><span class=mt>${esc(m.text)}</span><small>${esc(m.how)}</small></span></div>`).join('')||`<p class="small mut">${T('কিছু পাওয়া যায়নি','No match')}</p>`}catch(x){toast(x.message)}};
  $('#pion',sh).onchange=async e=>{await saveSet({memory:e.target.checked});openMemory()};
  $$('[data-mf]',sh).forEach(b=>b.onclick=()=>{MF=b.dataset.mf;openMemory()});
  $('#mlist',sh).onclick=async e=>{const r=e.target.closest('.memi');if(!r)return;const id=r.dataset.id;
   if(e.target.closest('[data-del]')){try{await api('/bb/api/memory/'+id,{method:'DELETE'});r.remove();toast(T('মুছে ফেলা হয়েছে','Forgotten'))}catch(x){toast(x.message)}}
   else if(e.target.closest('[data-ed]')){const m=items.find(i=>String(i.id)===id);openSheet(`<h3>${T('মেমরি এডিট','Edit memory')}</h3><textarea class=fld id=met rows=3 maxlength=400>${esc(m.text)}</textarea><span class=l>${T('ধরন','Type')}</span><div class=seg id=mek>${Object.entries(MK()).map(([k,[i,l]])=>`<button data-k="${k}" class="${(m.kind||'fact')===k?'on':''}">${i} ${l}</button>`).join('')}</div><div class=btns style="margin-top:16px"><button class=btn onclick="openMemory()">${T('বাতিল','Cancel')}</button><button class="btn red" id=mes>${T('সেভ','Save')}</button></div>`,s2=>{let k=m.kind||'fact';
     $('#mek',s2).onclick=ev=>{const b=ev.target.closest('[data-k]');if(!b)return;k=b.dataset.k;$$('#mek button',s2).forEach(x=>x.classList.toggle('on',x===b))};
     $('#mes',s2).onclick=async()=>{try{await api('/bb/api/memory/'+id,{method:'PUT',body:JSON.stringify({text:$('#met',s2).value,kind:k})});toast(T('সেভ হয়েছে','Saved'));openMemory()}catch(x){toast(x.message)}}},T('মেমরি','Memory'))}};
  $('#maddb',sh).onclick=async()=>{const t=$('#madd',sh).value.trim();if(!t)return toast(T('কিছু লিখুন','Type something first'));try{await api('/bb/api/memory',{method:'POST',body:JSON.stringify({text:t,kind:$('#mkind',sh).value})});toast(T('মনে রাখলাম','Remembered'));openMemory()}catch(x){toast(x.message)}};
  $('#mclr',sh).onclick=async()=>{if(!await confirmSheet(T('সব মেমরি মুছবেন?','Forget everything?'),T('টাইগার আপনার সম্পর্কে যা শিখেছে সব মুছে যাবে।','Everything the Tiger has learned about you will be deleted.'),T('সব মুছুন','Clear all')))return;try{await api('/bb/api/memory',{method:'DELETE'});toast(T('সব মুছে ফেলা হয়েছে','Memory cleared'))}catch(x){toast(x.message)}openMemory()}},T('মেমরি','Memory'))}

/* ---------- Royal Link · Accessibility permission flow (screen + SMS) ---------- */
const RLCAPS=()=>[['screen','🖥',T('স্ক্রিন পড়া','Read screen'),T('সামনের স্ক্রিনের লেখা; পাসওয়ার্ড ও ব্যাংক অ্যাপ বাদ','Visible text only; passwords & bank apps skipped')],
 ['sms','💬',T('SMS পড়া','Read SMS'),T('ইনবক্স থেকে সাম্প্রতিক মেসেজ','Recent inbox messages')],
 ['sms_send','✉️',T('SMS লেখা','Write SMS'),T('খসড়া SMS অ্যাপে বসায় — Send আপনি চাপবেন, প্রতিবার Approve কার্ড','Fills your SMS app — you tap Send; Approve card every time')]];
async function openRoyalLink(){const own=ST.me.role==='owner';let devs=[];if(own){try{devs=((await api('/bb/api/devices')).devices||[]).filter(d=>/phone|android/i.test(d.kind+' '+d.name))}catch(e){}}
 const d=devs.find(x=>x.status==='approved')||devs[0];const pm=d?.perms||{};
 const step=(n,done,title,body)=>`<div class=memi style="align-items:flex-start;gap:10px"><span class="tag ${done?'ok':'warn'}" style="min-width:28px;justify-content:center">${done?'✓':num(n)}</span><span class=grow><b>${title}</b><br><small class=mut>${body}</small></span></div>`;
 const MODE={ask:T('প্রতিবার জিজ্ঞেস','Ask every time'),always:T('সবসময়','Always'),off:T('বন্ধ','Off')};
 openSheet(`<h3>📱 ${T('রয়্যাল লিংক · স্ক্রিন ও SMS','Royal Link · Screen & SMS')}</h3>
 <p class=sub>${T('আপনার অনুমতিতে টাইগার ফোনের স্ক্রিন পড়ে সাহায্য করবে ও SMS লিখে দেবে। পাঠানোর বাটন সবসময় আপনি চাপবেন।','With your permission the Tiger reads your phone screen to help and drafts SMS for you. You always press Send yourself.')}</p>
 <div class=group style="padding:6px 10px">
 ${step(1,!!d,T('Royal Link অ্যাপ ইনস্টল','Install the Royal Link app'),T('APK (Play Store-এ নয়)। Android 13+: App info → ⋮ → “Allow restricted settings”','Sideloaded APK (not on Play Store). Android 13+: App info → ⋮ → “Allow restricted settings”'))}
 ${step(2,d?.status==='approved',T('ফোন পেয়ার করুন','Pair your phone'),d?esc(d.name)+' · '+esc(d.status)+(d.online?' · 🟢 online':' · ⚪ offline'):T('অ্যাপে দেখানো কোড অনুমতি কেন্দ্রে Approve করুন','Approve the code shown in the app from the Permission center'))}
 ${step(3,false,T('Accessibility চালু করুন','Turn on Accessibility'),T('Settings → Accessibility → Royal Link → On। Android নিজের সতর্কবার্তা দেখাবে; আমরা নিজে চালু করতে পারি না।','Settings → Accessibility → Royal Link → On. Android shows its own warning; we can never switch it on for you.'))}
 ${step(4,false,T('কী কী করতে দেবেন বেছে নিন','Choose what it may do'),T('নিচে প্রতিটা ক্ষমতা আলাদা','Each power below is separate'))}</div>
 <span class=l>${T('অনুমতি','Permissions')}</span><div class=group>${RLCAPS().map(([k,i,n,h])=>`<div class=memi><span class=ki aria-hidden=true>${i}</span><span class=grow><b>${n}</b><br><small class=mut>${h}</small></span><span class="tag ${k==='sms_send'?'red':(pm[k]==='always'?'ok':pm[k]==='off'?'':'warn')}">${k==='sms_send'?'🔐 '+T('সবসময় Approve','Always Approve'):(MODE[pm[k]]||MODE.ask)}</span></div>`).join('')}</div>
 <div class=group style="padding:10px;border:1px solid var(--gold,#c9a227);border-radius:14px;margin:8px 0"><b>🛡 ${T('যা কখনো করে না','Never does')}</b><small class=mut><br>• ${T('নিজে SMS পাঠায় না','Never sends SMS by itself')}<br>• ${T('পাসওয়ার্ড/OTP/ব্যাংক স্ক্রিন পড়ে না','Never reads password, OTP or bank screens')}<br>• ${T('গোপনে চলে না — Android নিজের নোটিফিকেশন দেখায়, সব অডিট লগে','Never hidden — Android shows its indicator; everything is audit-logged')}</small></div>
 <div class=btns>${own?`<a class=btn href="/bb/link/README.md">${T('সেটআপ গাইড','Setup guide')}</a><a class="btn pri" href="/admin/dash">${T('অনুমতি কেন্দ্র','Permission center')}</a>`:`<button class="btn pri" onclick="closeSheet()">${T('ঠিক আছে','OK')}</button>`}</div>
 <p class="small mut">${T('স্ট্যাটাস: স্ক্রিন/SMS টুল ও অনুমতি-কার্ড চালু; Android অ্যাপ এখনো স্ক্যাফোল্ড (APK বানানো বাকি)।','Status: screen/SMS tools and Approve cards are live in the prototype; the Android app is still a scaffold (APK not built yet).')}</p>`,null,T('রয়্যাল লিংক','Royal Link'))}
