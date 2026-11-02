/* The Royal Bengal Tiger (v4) — "Royal Court" redesign. Vanilla JS, same APIs as v3 (/bb/api/*, /bb/api/v3/*). Flag: feat_ui_v4. */
'use strict';
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let LANG=localStorage.bbLang==='en'?'en':'bn';
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
    if(!data)continue;let j;try{j=JSON.parse(data)}catch(e){continue}if(ev==='meta'||ev==='done'){model=j.model||model}else if(j.d){txt+=j.d;c.replaceChildren(md(txt));scrollEnd()}}}}
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
async function loadAgents(){const j=await api('/bb/api/v3/agents');ST.agents=j.agents;ST.canTools=j.can_tools;ST.safeTools=j.safe_tools;ST.agentsOff=j.off||''}
const PERML=()=>({ask:T('সব জিজ্ঞেস করে','Asks every time'),safe_auto:T('নিরাপদগুলো নিজে','Safe ones auto'),chat_only:T('শুধু চ্যাট','Chat only')});
const TIERI=()=>({fast:'⚡ '+T('দ্রুত','Fast'),auto:'✨ '+T('অটো','Auto'),deep:'🧠 '+T('গভীর','Deep')});
async function pgAgents(){$('#view').innerHTML=shell(T('এজেন্ট','Agents'),'<div id=agw><div class=skel></div><div class=skel></div></div>');
 try{await loadAgents()}catch(e){$('#agw').innerHTML=`<div class=empty>${esc(e.message)}</div>`;return}
 const sk=id=>ST.skills.find(s=>s.id===id);
 $('#agw').innerHTML=`<p class=sub>${T('নিজের মতো সহকারী বানান — নাম, স্বভাব, মডেল আর স্কিল ঠিক করে দিন। বড় কাজ ধাপে ধাপে করবে, ঝুঁকির কাজে আগে অনুমতি চাইবে।','Build your own assistants — name, personality, model and skills. They work step by step and ask before anything risky.')}</p>
 ${ST.agentsOff?`<div class=note role=status>⏸️ ${esc(ST.agentsOff)}</div>`:`
 <div class=sec style="margin-top:6px"><h2>${T('রেডিমেড টেমপ্লেট','Templates')}</h2></div><div class=tpl>${TPL.map((t,i)=>`<button onclick="editAgent(null,${i})"><span class=e aria-hidden=true>${t.icon}</span><b>${esc(t.name)}</b><span>${esc(t.persona)}</span></button>`).join('')}</div>
 <div class=sec><h2>${T('আমার এজেন্ট','My agents')}</h2><span class="small mut">${num(ST.agents.length)}</span></div>
 <button class=newag onclick="editAgent()"><span class=pl>${svg('plus')}</span><span style="text-align:left"><b style="color:var(--tx)">${T('নতুন এজেন্ট বানান','Create an agent')}</b><div class=small>${T('১ মিনিটেই তৈরি','Ready in a minute')}</div></span></button>`}`+
 ST.agents.map(a=>`<article class=ag><div class=head><div class=em aria-hidden=true>${esc(a.icon)}</div><div class=grow><h3>${esc(a.name)}</h3><div class=tags style="margin-top:4px"><span class="tag blue">${esc(TIERI()[a.model_tier]||a.model_tier)}</span><span class="tag ${a.perm_level==='ask'?'warn':a.perm_level==='chat_only'?'':'ok'}">🔐 ${esc(PERML()[a.perm_level]||a.perm_level)}</span></div></div></div>
  <p class=persona>${esc(a.persona||T('কোনো বিশেষ নির্দেশনা নেই','No special instructions'))}</p><div class=skics>${a.skills.map(i=>sk(i)?`<span title="${esc(sk(i).name_bn)}" aria-label="${esc(sk(i).name_bn)}">${sk(i).icon}</span>`:'').join('')}</div>
  <div class=foot><button class="btn pri grow" onclick="go('/v4/agents/${a.id}')">${svg('play')} ${T('কাজ দিন','Give a task')}</button><button class=btn aria-label="${T('চ্যাট','Chat')}" onclick="chatAgent('${a.id}')">${svg('chat')}</button><button class=btn aria-label="${T('এডিট','Edit')}" onclick="editAgent('${a.id}')">${svg('edit')}</button></div>
  ${a.runs?.length?`<div class=last>${T('শেষ কাজ','Last task')}: ${esc(a.runs[0].goal)} · ${ago(a.runs[0].created)}</div>`:''}</article>`).join('')}
const ICONS=['🤖','🧑‍💼','✍️','🔎','💻','🎓','📈','🕌','⚡','🛡️','🎨','📱'];
const TPL=[{icon:'🔎',name:'গবেষক',persona:'যেকোনো প্রশ্নে ওয়েবে খুঁজে সংক্ষেপে উত্তর দেবে, সবসময় সূত্রের লিংক দেবে।',model_tier:'auto',skills:['research','summarize'],perm_level:'safe_auto'},
 {icon:'📰',name:'খবরের সারাংশ',persona:'আজকের বাংলাদেশ ও বিশ্বের বড় খবর ৫টা পয়েন্টে বাংলায় বলবে, প্রতিটার সূত্র দেবে।',model_tier:'fast',skills:['research','summarize'],perm_level:'safe_auto'},
 {icon:'🎓',name:'পড়াশোনার সাথী',persona:'ধাপে ধাপে সহজ ভাষায় বোঝাবে, শেষে ছোট্ট কুইজ দেবে।',model_tier:'auto',skills:['tutor','summarize'],perm_level:'chat_only'},
 {icon:'✍️',name:'লেখার সহকারী',persona:'চিঠি, পোস্ট, ইমেইল সুন্দর ও ভদ্র বাংলায় লিখে দেবে; পাঠাবে না, শুধু খসড়া দেবে।',model_tier:'auto',skills:['write','mail','translate'],perm_level:'chat_only'},
 {icon:'📈',name:'ব্যবসার পরামর্শক',persona:'ছোট ব্যবসার আইডিয়া, দাম ও মার্কেটিং নিয়ে বাস্তবসম্মত পরামর্শ দেবে; দরকার হলে বাজারদর খুঁজবে।',model_tier:'deep',skills:['biz','research'],perm_level:'ask'}];
function editAgent(id,ti){const a=ST.agents.find(x=>x.id===id)||(ti!=null&&TPL[ti])||{icon:'🤖',name:'',persona:'',model_tier:'auto',skills:['write','summarize'],perm_level:'ask'};const D=JSON.parse(JSON.stringify(a));
 const avail=ST.skills.filter(s=>s.available);D.skills=D.skills.filter(x=>avail.some(s=>s.id===x));
 openSheet(`<h3>${id?T('এজেন্ট এডিট','Edit agent'):T('নতুন এজেন্ট','New agent')}</h3><p class=sub>${T('সব পরে বদলানো যাবে।','You can change everything later.')}</p>
 ${id?'':`<span class=l>${T('রেডিমেড টেমপ্লেট','Templates')}</span><div class=pick>${TPL.map((t,i)=>`<button type=button class="${ti===i?'on':''}" onclick="editAgent(null,${i})">${t.icon} ${esc(t.name)}</button>`).join('')}</div>`}
 <span class=l>${T('আইকন','Icon')}</span><div class=icopick id=ip>${ICONS.map(i=>`<button class="${D.icon===i?'on':''}" data-i="${i}" aria-label="${i}">${i}</button>`).join('')}</div>
 <label class=l for=an>${T('নাম','Name')}</label><input class=fld id=an maxlength=40 placeholder="${T('যেমন: আমার গবেষক','e.g. My researcher')}" value="${esc(D.name)}">
 <label class=l for=ap>${T('স্বভাব ও নির্দেশনা','Personality & instructions')}</label><textarea class=fld id=ap rows=3 placeholder="${T('যেমন: সংক্ষেপে উত্তর দেবে, সবসময় সূত্র দেবে','e.g. short answers, always cite sources')}">${esc(D.persona)}</textarea>
 <span class=l>${T('মডেল','Model')}</span><div class=seg id=at>${Object.entries(TIERI()).map(([k,l])=>`<button data-k="${k}" class="${D.model_tier===k?'on':''}">${l}</button>`).join('')}</div>
 <span class=l>${T('স্কিল','Skills')} (${num(avail.length)})</span><div class=pick id=as>${avail.map(s=>`<button data-s="${s.id}" class="${D.skills.includes(s.id)?'on':''}" aria-pressed="${D.skills.includes(s.id)}">${s.icon} ${esc(T(s.name_bn,s.name_en))}</button>`).join('')}</div>
 <span class=l>${T('অনুমতির ধরন','Permission level')}</span><div class=radio id=al>${[['ask',T('প্রতিটা অ্যাকশনে জিজ্ঞেস করবে','Ask before every action'),T('সবচেয়ে নিরাপদ (প্রস্তাবিত)','Safest (recommended)')],['safe_auto',T('পড়া ও সার্চ নিজে করবে','Read & search on its own'),T('পাঠানো, মোছা, ডিভাইস কন্ট্রোলের আগে সবসময় জিজ্ঞেস করবে','Always asks before sending, deleting or device control')],['chat_only',T('কোনো টুল নয়','No tools'),T('শুধু কথা বলবে','Talk only')]].map(([k,b,s])=>`<button data-l="${k}" class="${D.perm_level===k?'on':''}"><i class=dot></i><span><b>${b}</b><span>${s}</span></span></button>`).join('')}</div>
 <div class=btns style="margin-top:20px">${id?`<button class="btn dan" id=adel>${T('মুছুন','Delete')}</button>`:''}<button class=btn onclick="closeSheet()">${T('বাতিল','Cancel')}</button><button class="btn pri" id=asave>${T('সেভ','Save')}</button></div>`,sh=>{
  $('#ip',sh).onclick=e=>{const b=e.target.closest('[data-i]');if(!b)return;D.icon=b.dataset.i;$$('#ip button',sh).forEach(x=>x.classList.toggle('on',x===b))};
  $('#at',sh).onclick=e=>{const b=e.target.closest('[data-k]');if(!b)return;D.model_tier=b.dataset.k;$$('#at button',sh).forEach(x=>x.classList.toggle('on',x===b))};
  $('#as',sh).onclick=e=>{const b=e.target.closest('[data-s]');if(!b)return;const s=b.dataset.s;D.skills=D.skills.includes(s)?D.skills.filter(x=>x!==s):[...D.skills,s];b.classList.toggle('on');b.setAttribute('aria-pressed',b.classList.contains('on'))};
  $('#al',sh).onclick=e=>{const b=e.target.closest('[data-l]');if(!b)return;D.perm_level=b.dataset.l;$$('#al button',sh).forEach(x=>x.classList.toggle('on',x===b))};
  $('#asave',sh).onclick=async()=>{D.name=$('#an',sh).value.trim()||T('আমার এজেন্ট','My agent');D.persona=$('#ap',sh).value.trim();
   try{await api('/bb/api/v3/agents'+(id?'/'+id:''),{method:id?'PUT':'POST',body:JSON.stringify({icon:D.icon,name:D.name,persona:D.persona,model_tier:D.model_tier,skills:D.skills,perm_level:D.perm_level})});closeSheet();toast(T('সেভ হয়েছে','Saved'));pgAgents()}catch(e){toast(e.message)}};
  if(id)$('#adel',sh).onclick=async()=>{if(!await confirmSheet(T('এজেন্ট মুছবেন?','Delete agent?'),T('এর কাজের ইতিহাস কার্যকলাপে থেকে যাবে।','Its history stays in Activity.'),T('মুছুন','Delete')))return;try{await api('/bb/api/v3/agents/'+id,{method:'DELETE'})}catch(e){toast(e.message)}pgAgents()}},T('এজেন্ট','Agent'))}
async function pgAgent(id){if(!ST.agents.length)try{await loadAgents()}catch(e){}const a=ST.agents.find(x=>x.id===id);if(!a)return go('/v4/agents',true);
 const SL={done:['ok',T('সম্পন্ন','Done')],failed:['red',T('ব্যর্থ','Failed')],running:['warn',T('চলছে','Running')],cancelled:['',T('থামানো','Stopped')]};
 $('#view').innerHTML=topbar(`<div class="who ttl"><div class=em style="width:40px;height:40px;border-radius:13px;display:grid;place-items:center;font-size:21px;background:linear-gradient(135deg,var(--blue),var(--black))" aria-hidden=true>${esc(a.icon)}</div><div><b>${esc(a.name)}</b><small>${esc(PERML()[a.perm_level]||'')}</small></div></div>`,
  `<button class=ib aria-label="${T('ফিরে যান','Back')}" onclick="go('/v4/agents')">${svg('back')}</button>`,`<button class=ib aria-label="${T('এডিট','Edit')}" onclick="editAgent('${a.id}')">${svg('edit')}</button>`)+
 `<div class=page><div class=wrap><div class=card><label class=l for=goal style="margin-top:0">${T('কী করতে হবে?','What should it do?')}</label><textarea class=fld id=goal rows=3 placeholder="${T('যেমন: ঢাকার আজকের আবহাওয়া খুঁজে ৩ লাইনে বলো','e.g. Find today\'s Dhaka weather in 3 lines')}"></textarea>
 <div class=btns><button class="btn red" id=runb>${svg('play')} ${T('শুরু করুন','Start')}</button><button class=btn id=demob title="${T('মডেল ছাড়া UI দেখার জন্য','UI demo without a model')}">${T('ডেমো','Demo')}</button></div><button class="btn full" style="margin-top:8px" onclick="chatAgent('${a.id}')">${svg('chat')} ${T('এই এজেন্টের সাথে চ্যাট','Chat with this agent')}</button>
 ${!ST.canTools?`<p class="small mut">ℹ️ ${T('টুলসহ এজেন্ট এখন চালু নেই — চ্যাটে কথা বলুন।','Tool agents are off now — use chat.')}</p>`:ST.safeTools?`<p class="small mut">🛡️ ${T('এই এজেন্ট শুধু ওয়েব সার্চ ও ওয়েবপেজ পড়তে পারে। পেজ খোলার আগে অনুমতি চাইবে; কিছু পাঠানো/কেনা/ডিলিট করতে পারে না।','This agent can only search and read web pages, asks before opening a page, and can never send, buy or delete.')}</p>`:''}</div>
 <div id=runv></div><div class=sec><h2>${T('আগের কাজ','Past tasks')}</h2></div><div id=hist>${(a.runs||[]).map(r=>{const s=SL[r.status]||['',r.status||'—'];return `<div class=hist><span class="tag ${s[0]}">${esc(s[1])}</span><span class="grow" style="overflow:hidden;white-space:nowrap;text-overflow:ellipsis">${esc(r.goal)}</span><button class="btn sm" onclick="watch('${r.task_id}')">${T('দেখুন','View')}</button></div>`}).join('')||`<p class="small mut">${T('এখনো কোনো কাজ দেননি।','No tasks yet.')}</p>`}</div></div></div>`;
 $('#runb').onclick=async()=>{const g=$('#goal').value.trim();if(!g)return toast(T('কাজটা লিখুন','Describe the task'));try{const r=await api(`/bb/api/v3/agents/${id}/run`,{method:'POST',body:JSON.stringify({goal:g})});watch(r.task,g)}catch(e){toast(e.message)}};
 $('#demob').onclick=()=>demoRun($('#goal').value.trim()||T('ঢাকার আজকের আবহাওয়া খুঁজে ৩ লাইনে বলো','Find today\'s Dhaka weather in 3 lines'))}
const LAB=()=>({plan:['🗺️ '+T('পরিকল্পনা','Plan'),''],think:['💭 '+T('ভাবছি','Thinking'),''],run:['▶️ '+T('চলছে','Running'),'running'],result:['✅ '+T('ফলাফল','Result'),'ok'],error:['❌ '+T('সমস্যা','Error'),'err'],retry:['🔁 '+T('আবার চেষ্টা','Retry'),''],repair:['🛠️ '+T('ঠিক করছি','Repairing'),''],
 auto:['🔓 '+T('নিজে অনুমতি দেওয়া','Auto-approved'),'ok'],blocked:['⛔ '+T('বন্ধ','Blocked'),'err'],final:['🏁 '+T('চূড়ান্ত উত্তর','Final answer'),'ok'],approval:['🔐 '+T('অনুমতি দরকার','Approval needed'),'ask'],resume:['♻️ '+T('আবার শুরু','Resumed'),'']});
const RISK=()=>({high:T('বেশি','High'),medium:T('মাঝারি','Medium'),low:T('কম','Low')});
function stepEl(box,e,tid,demo){if(!box||e.type==='end')return;
 if(e.type==='decision'){const a=$(`[data-aid="${CSS.escape(String(e.id))}"]`,box);if(a){$('.btns',a).innerHTML=e.decision==='yes'?`<span class="tag ok">✅ ${T('অনুমতি দিয়েছেন','Approved')}</span>`:`<span class="tag red">🚫 ${T('অনুমতি দেননি','Declined')}</span>`}return}
 $$('.st.running',box).forEach(x=>x.classList.remove('running'));
 const [lab,cls]=LAB()[e.type]||[e.type,''];const d=document.createElement('div');d.className='st '+cls;
 if(e.type==='approval'){d.innerHTML=`<div class=lab>${lab}</div><div class=appr data-aid="${esc(e.id)}" role=group aria-label="${T('অনুমতি কার্ড','Approval card')}"><div class=t>${svg('shield')} ${T('অনুমতি দেবেন?','Allow this?')}</div>
  <div class="small mut" style="margin-top:4px">${esc(e.capname||'')} · ${T('টুল','tool')} <code>${esc(e.tool)}</code> · ${T('ঝুঁকি','risk')} <span class="tag ${e.risk==='high'?'red':'warn'}">${esc(RISK()[e.risk]||e.risk||'—')}</span></div>
  <pre>${esc(JSON.stringify(e.args,null,1))}</pre><div class=small>${T('কেন','Why')}: ${esc(e.why||'')}</div><div class=btns><button class=btn data-ok=0>🚫 ${T('না','No')}</button><button class="btn pri" data-ok=1>✅ ${T('অনুমতি দিন','Allow')}</button></div></div>`;
  $$('[data-ok]',d).forEach(b=>b.onclick=async()=>{const ok=b.dataset.ok==='1';if(demo)return demo(ok,e.id);try{await api('/bb/api/approvals/'+e.id,{method:'POST',body:JSON.stringify({ok})})}catch(x){toast(x.message)}})}
 else{d.innerHTML=`<div class=lab>${lab}${e.step?' · '+T('ধাপ ','step ')+num(e.step):''}</div><div class=body></div>`;const b=$('.body',d);
  if(e.type==='run')b.innerHTML=`<code>${esc(e.tool)}</code>`;else if(e.type==='result'||e.type==='error'){b.innerHTML='<pre></pre>';$('pre',b).textContent=e.text||''}
  else if(e.type==='final')b.replaceChildren(md(e.text));else b.textContent=e.text||''}
 box.appendChild(d);d.scrollIntoView({block:'nearest',behavior:'smooth'})}
async function watch(tid,goal){const v=$('#runv');if(!v)return;v.innerHTML=`<div class=card style="margin-top:12px"><div class=row><b class=grow>${esc(goal||T('কাজ','Task'))}</b><span class="tag warn" id=rst>${T('চলছে','Running')}</span><button class="btn sm dan" id=cxl aria-label="${T('কাজ থামান','Stop task')}">⏹ ${T('থামান','Stop')}</button></div><div class=tl id=tl aria-live=polite></div></div>`;
 v.scrollIntoView({behavior:'smooth'});
 $('#cxl').onclick=async()=>{if(!await confirmSheet(T('কাজটা থামাবেন?','Stop this task?'),T('থামালে আর আবার চালু হবে না।','A stopped task will not resume.'),T('থামান','Stop')))return;try{await api(`/bb/api/v3/runs/${tid}/cancel`,{method:'POST',body:'{}'});toast(T('থামানো হচ্ছে…','Stopping…'))}catch(e){toast(e.message)}};
 let n=0,idle=0;for(;;){let j;try{j=await api(`/bb/api/v3/runs/${tid}?since=${n}`)}catch(e){if($('#rst'))$('#rst').textContent=e.status===404?T('পাওয়া যায়নি','Not found'):T('ত্রুটি','Error');break}
  if(!$('#tl'))break;n=typeof j.n==='number'?j.n:n+j.events.length;j.events.forEach(e=>stepEl($('#tl'),e,tid));
  if(j.status!=='running'){$('#rst').textContent=j.status==='done'?T('সম্পন্ন','Done'):j.status==='cancelled'?T('থামানো','Stopped'):T('থেমেছে','Ended');$('#rst').className='tag '+(j.status==='done'?'ok':'red');$('#cxl')?.remove();break}
  idle=j.events.length?0:idle+1;await new Promise(r=>setTimeout(r,document.hidden?4000:Math.min(600+idle*250,2500)))}}
async function demoRun(goal){const v=$('#runv');v.innerHTML=`<div class=card style="margin-top:12px"><div class=row><b class=grow>${esc(goal)}</b><span class="tag warn" id=rst>${T('ডেমো · চলছে','Demo · running')}</span></div><div class=tl id=tl></div></div>`;
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
 <div class=group><label class=li><span class=ki aria-hidden=true>💾</span><span class=grow>${T('আমার কথা মনে রাখো (মেমরি)','Remember me (memory)')}</span><input type=checkbox class=tg ${ST.set?.memory!==false?'checked':''} onchange="saveSet({memory:this.checked})" aria-label="${T('মেমরি','Memory')}"></label></div>
 <div class=group>${row('🧠',T('মেমরি','Memory'),'/memory')}${row('⏰',T('শিডিউল','Schedules'),'/schedules')}${row('🔌',T('কানেকশন','Connections'),'/connections')}${row('🎨',T('স্টুডিও','Studio'),'/studio')}${row('🔑',T('নিজের API কী (BYOK)','My API keys (BYOK)'),'/studio#keys')}${row('💳',T('অ্যাকাউন্ট ও প্ল্যান','Account & plan'),'/account')}</div>
 <div class=group>${own?row('🛡️',`<b>${T('অ্যাডমিন ড্যাশবোর্ড','Admin dashboard')}</b>`,'/admin/dash',`<span class="tag warn">${T('মালিক','Owner')}</span>`):''}${row('🗂️',T('আগের ডিজাইন (v3)','Previous design (v3)'),'/v3')}${row('⚙️',T('ক্লাসিক UI ও পুরো সেটিংস','Classic UI & all settings'),'/app?classic=1')}
 <a class=li href="/logout"><span class=ki aria-hidden=true>↩︎</span><span class=grow style="color:var(--red2)">${T('লগআউট','Log out')}</span></a></div>
 <p class="small mut" style="text-align:center;margin-top:14px"><span class=wmi>The Royal Bengal Tiger</span></p>`,null,T('আমি','Me'))}
async function saveSet(p){try{ST.set=await api('/bb/api/settings',{method:'PUT',body:JSON.stringify(p)});if(p.lang){LANG=p.lang==='en'?'en':'bn';document.cookie='bb_lang='+LANG+';path=/;max-age=31536000;samesite=lax';localStorage.bbLang=LANG;document.documentElement.lang=LANG;
  $('#tabs').innerHTML=navHTML();$('.sidenav').innerHTML=navHTML();route()}toast(T('সংরক্ষণ হয়েছে','Saved'));openMe()}catch(e){toast(e.message)}}
/* ---------- boot ---------- */
(async()=>{$('#tabs').innerHTML=navHTML();$('.sidenav').innerHTML=navHTML();
 const [me,set,sk]=await Promise.allSettled([api('/bb/api/me'),api('/bb/api/settings'),api('/bb/api/v3/skills')]);
 if(me.status==='fulfilled')ST.me=me.value;if(set.status==='fulfilled'){ST.set=set.value;const l=ST.set.lang==='en'?'en':'bn';if(l!==LANG){LANG=l;localStorage.bbLang=l;document.documentElement.lang=l;$('#tabs').innerHTML=navHTML();$('.sidenav').innerHTML=navHTML()}}
 if(sk.status==='fulfilled'){ST.skills=sk.value.skills||[];ST.cats=sk.value.categories||[];ST.skillsOff=sk.value.off||''}
 const q=new URLSearchParams(location.search);route();const sh=[q.get('title'),q.get('text'),q.get('url')].filter(Boolean).join('\n');if(sh&&$('#inp')){$('#inp').value=sh;$('#inp').dispatchEvent(new Event('input'))}
 try{const D=await api('/bb/api/activity');ST.approvals=D.approvals?.length||0;paintNav()}catch(e){}
 if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js',{scope:'/'}).catch(()=>{})})();
