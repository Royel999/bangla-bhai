const BB_PUBLIC=window.BB_PUBLIC||'https://banglabhai.dpdns.org';
// ===== বাংলা ভাই v0.3 add-ons: modals, agent, voice, camera, permission center =====
let AGENT=localStorage.bbAgent==='1';
function dlg(html){return new Promise(res=>{const d=document.createElement('div');d.className='dlg';d.innerHTML=`<div class=card>${html}</div>`;document.body.appendChild(d);
 const done=v=>{d.remove();res(v)};d.onclick=e=>{if(e.target===d)done(null)};d._done=done;
 d.querySelectorAll('[data-v]').forEach(b=>b.onclick=()=>done(b.dataset.v==='__in'?d.querySelector('.fld').value:b.dataset.v));
 const f=d.querySelector('.fld');if(f){f.focus();f.select?.();f.onkeydown=e=>{if(e.key==='Enter'&&f.tagName==='INPUT'){e.preventDefault();done(f.value)}if(e.key==='Escape')done(null)}}})}
const HD=t=>`<h3><img src="/bb/static/logo.png" alt="">${esc(t)}</h3>`;
function uiPrompt(msg,def=''){const long=(def||'').length>60||/নির্দেশনা|এডিট|instruction|edit/i.test(msg);
 return dlg(HD(msg.split('\n')[0])+(msg.includes('\n')?`<p>${esc(msg.split('\n').slice(1).join('\n'))}</p>`:'')+(long?`<textarea class=fld rows=5>${esc(def)}</textarea>`:`<input class=fld value="${esc(def)}">`)+`<div class=btns><button class=btn data-v="">${L('Cancel','বাতিল')}</button><button class="btn pri" data-v="__in">${L('OK','ঠিক আছে')}</button></div>`).then(v=>v===''?null:v)}
function uiConfirm(msg){return dlg(HD(L('Please confirm','নিশ্চিত করুন'))+`<p>${esc(msg)}</p><div class=btns><button class=btn data-v="0">${L('No','না')}</button><button class="btn dan" data-v="1">${L('Yes, do it','হ্যাঁ, করুন')}</button></div>`).then(v=>v==='1')}
function setAgent(v){AGENT=v;localStorage.bbAgent=v?'1':'0';$('#agentT').classList.toggle('on',v);$('#inp').placeholder=t(v?'app.ph_agent':'app.ph');if(v)toast(t('app.agent_on'));if(window.bbRefreshLivebar)bbRefreshLivebar()}
// ---- agent ----
async function agentSend(){const inp=$('#inp');let t=inp.value.trim().replace(/^(এজেন্ট|Agent):\s*/i,'');if(!t)return;inp.value='';autoGrow();
 if(!CH){const r0=await api('/bb/api/chats',{method:'POST',body:JSON.stringify({project:curProject})});CH={id:r0.id,title:t.slice(0,40),messages:[]};$('#ttl').textContent=CH.title}
 addMsg({role:'user',content:'🤖 '+t});const w=addMsg({role:'assistant'});const c=w.querySelector('.content'),meta=w.querySelector('.meta');
 const box=document.createElement('div');box.className='steps';c.appendChild(box);setMeta(meta,L('Bangla Bhai agent','বাংলা ভাই এজেন্ট'),[]);
 const r=await api('/bb/api/agent',{method:'POST',body:JSON.stringify({goal:t})});let n=0,end=false,final='';
 $('#send').classList.add('stop');$('#send').textContent='■';
 while(!end){const j=await api(`/bb/api/agent/${r.id}?since=${n}`);
  if(typeof j.n==='number') n=j.n; else n+=j.events.length;
  for(const e of j.events){try{if(e.type==='end'){end=true;continue}if(e.type==='final')final=e.text;stepEl(box,e,r.id)}catch(err){console.error(err);box.insertAdjacentHTML('beforeend',`<div class="st err"><div class=lab>UI</div>${esc(String(err))}</div>`)}}
  scrollEnd();if(!end)await new Promise(z=>setTimeout(z,700)); if(j.status==='done')end=true}
 $('#send').classList.remove('stop');$('#send').textContent='➤';
 const acts=w.querySelector('.acts');setActs(acts,{content:final});
 try{await api('/bb/api/chats/'+CH.id+'/note',{method:'POST',body:JSON.stringify({user:t,assistant:final||L('(agent)','(এজেন্ট)')})});loadChats()}catch(e){}}
function stepEl(box,e,tid){const d=document.createElement('div');const L={plan:[L('🗺️ Plan','🗺️ পরিকল্পনা'),''],think:[L('💭 Thinking · step ','💭 ভাবনা · ধাপ ')+e.step,''],run:[L('▶️ Running','▶️ চালানো হচ্ছে'),''],result:[L('✅ Result','✅ ফলাফল'),'ok'],error:[L('❌ Error','❌ সমস্যা'),'err'],retry:[L('🔁 Retry','🔁 আবার চেষ্টা'),'retry'],repair:[L('🛠️ Repair','🛠️ রিপেয়ার'),'repair'],decision:['',''],auto:[L('🔓 Auto-approved','🔓 স্বয়ংক্রিয় অনুমতি'),'ok'],blocked:[L('⛔ Blocked','⛔ বন্ধ'),'err'],final:[L('🏁 Final answer','🏁 চূড়ান্ত উত্তর'),'ok'],approval:[L('🔐 Permission needed','🔐 অনুমতি দরকার'),'ask']}[e.type]||[e.type,''];
 if(e.type==='decision'){const a=box.querySelector(`[data-aid="${e.id}"]`);if(a){a.classList.add('done');a.querySelector('.btns').innerHTML=e.decision==='yes'?L('✅ Approved','✅ অনুমতি দিয়েছেন'):L('🚫 Denied','🚫 অনুমতি দেননি')}return}
 d.className='st '+L[1]+(e.type==='run'?' running':'');d.innerHTML=`<div class=lab>${L[0]}</div>`;const b=document.createElement('div');
 if(e.type==='result'||e.type==='error'||e.type==='final'){box.querySelectorAll('.st.running').forEach(x=>x.classList.remove('running'))}
 if(e.type==='think'){b.textContent=e.text;if(e.alternatives?.length){const u=document.createElement('ul');u.className='alts';u.innerHTML=L('<b style="font-size:12px">Alternatives:</b>','<b style="font-size:12px">বিকল্প চিন্তা:</b>');e.alternatives.forEach(x=>{const li=document.createElement('li');li.textContent=x;u.appendChild(li)});b.appendChild(u)}const m=document.createElement('div');m.style.cssText='font-size:11px;color:var(--mut)';m.textContent='🧠 '+e.model;b.appendChild(m)}
 else if(e.type==='run'){b.innerHTML=`<code>${esc(e.tool)}</code> ${e.attempt>1?L('(attempt ','(চেষ্টা ')+e.attempt+')':''}`}
 else if(e.type==='result'||e.type==='error'){const p=document.createElement('pre');p.textContent=e.text;b.appendChild(p);if(e.image){const i=document.createElement('img');i.src=e.image;b.appendChild(i)}}
 else if(e.type==='final'){b.replaceChildren(md(e.text))}
 else if(e.type==='approval'){d.innerHTML='';const a=document.createElement('div');a.className='appr';a.dataset.aid=e.id;
  a.innerHTML=`<div class=ttl>🔐 ${L('Allow?','অনুমতি দিন?')} — ${esc(e.capname||'')}</div><div>${L('Tool','টুল')}: <code>${esc(e.tool)}</code></div><pre>${esc(JSON.stringify(e.args,null,1))}</pre><div style="font-size:13px;color:var(--mut)">${L('Why','কেন')}: ${esc(e.why||'')}</div><div class=btns><button class="btn yes">✅ ${L('Allow','অনুমতি দিন')}</button><button class="btn no">🚫 ${L('Deny','না')}</button></div>`;
  const send=ok=>api(`/bb/api/agent/${tid}/decide`,{method:'POST',body:JSON.stringify({id:e.id,ok})});a.querySelector('.yes').onclick=()=>send(true);a.querySelector('.no').onclick=()=>send(false);
  d.appendChild(a);box.appendChild(d);return}
 else b.textContent=e.text||'';d.appendChild(b);box.appendChild(d)}
// ---- live indicator ----
function live(on,txt,stop){let l=$('#live');if(!l){l=document.createElement('div');l.id='live';document.body.appendChild(l)}
 l.classList.toggle('on',on);if(on){l.innerHTML=`<i></i><span>${txt}</span><button>${L('Stop','বন্ধ করুন')}</button>`;l.querySelector('button').onclick=stop}}
// ---- voice ----
let REC=null;
async function toggleMic(){if(REC){REC.stop();return}
 try{const st=await navigator.mediaDevices.getUserMedia({audio:true});const ch=[];REC=new MediaRecorder(st);REC.ondataavailable=e=>ch.push(e.data);
  REC.onstop=async()=>{st.getTracks().forEach(t=>t.stop());REC=null;$('#micB').classList.remove('rec');live(false);toast(L('⏳ Listening...','⏳ শুনছি...'));
   const fd=new FormData();fd.append('file',new Blob(ch,{type:ch[0]?.type||'audio/webm'}),'voice.webm');const r=await fetch('/bb/api/stt',{method:'POST',body:fd}).then(r=>r.json());
   if(r.text){$('#inp').value+=(($('#inp').value?' ':'')+r.text);autoGrow();toast(L('✓ Transcribed','✓ লেখা হয়েছে'))}else toast('⚠️ '+(r.error||L('Couldn’t understand','বোঝা যায়নি')))};
  REC.start();setTimeout(()=>REC&&REC.state==="recording"&&REC.stop(),120000);$('#micB').classList.add('rec');live(true,L('🎙️ Mic on — recording','🎙️ মাইক চালু — রেকর্ড হচ্ছে'),()=>REC&&REC.stop())}catch(e){toast(L('Microphone permission denied','মাইকের অনুমতি পাওয়া যায়নি'))}}
let AUD=null;async function speak(text,btn){if(AUD){AUD.pause();AUD=null;btn.textContent='🔊';return}btn.textContent='⏳';
 const r=await fetch('/bb/api/tts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});
 if(!r.ok){btn.textContent='🔊';return toast(L('⚠️ Voice failed','⚠️ ভয়েস তৈরি হয়নি'))}
 AUD=new Audio(URL.createObjectURL(await r.blob()));btn.textContent='⏹';AUD.onended=()=>{AUD=null;btn.textContent='🔊'};try{await AUD.play()}catch(e){btn.textContent='🔊';toast(L('Audio failed to play','অডিও চালু হয়নি'))}}
// ---- camera ----
async function openCam(){let st;try{st=await navigator.mediaDevices.getUserMedia({video:{facingMode:'environment'}})}catch(e){return toast(L('Camera permission denied','ক্যামেরার অনুমতি পাওয়া যায়নি'))}
 const stop=()=>{st.getTracks().forEach(t=>t.stop());live(false);d.remove()};live(true,L('📷 Camera on','📷 ক্যামেরা চালু'),()=>stop());
 const d=document.createElement('div');d.className='dlg';d.innerHTML=`<div class=card>${HD(L('Camera','ক্যামেরা'))}<video autoplay playsinline style="width:100%;border-radius:12px"></video><div class=btns><button class=btn>${L('Cancel','বাতিল')}</button><button class="btn pri">📸 ${L('Capture & send','ছবি তুলে পাঠান')}</button></div></div>`;document.body.appendChild(d);
 const v=d.querySelector('video');v.srcObject=st;d.querySelector('.btn').onclick=stop;
 d.querySelector('.pri').onclick=()=>{const c=document.createElement('canvas');c.width=v.videoWidth;c.height=v.videoHeight;c.getContext('2d').drawImage(v,0,0);stop();
  c.toBlob(async b=>{toast(L('🖼️ Reading image...','🖼️ ছবি পড়ছি...'));const fd=new FormData();fd.append('file',b,'camera.jpg');const j=await fetch('/bb/api/upload',{method:'POST',body:fd}).then(r=>r.json());if(j.error)return toast(j.error);FILES.push(j);renderAtt();toast(j.note||'✓')},'image/jpeg',.85)}}
// ---- permission center ----
const MODEL={ask:L('Ask every time','প্রতিবার জিজ্ঞেস'),once:L('Allow once','একবার অনুমতি'),always:L('Always allow','সবসময় অনুমতি'),off:L('Off','বন্ধ')};
function permCenter(){return `<div class=row style="display:block"><div style="display:flex;justify-content:space-between;align-items:center;gap:6px;flex-wrap:wrap"><b>${t('set.perm')}</b><button class="btn dan" onclick="revokeAll()">${t('set.revoke_all')}</button></div>
<p style="font-size:12.5px;color:var(--mut);margin:6px 0">${t('set.perm_d')}</p><div id=perms>${t('set.loading')}</div>
<div class=pm><h4>➕ ${L('Add a new device (Royal Link)','নতুন ডিভাইস যুক্ত করুন (Royal Link)')}</h4><div style="font-size:12.5px;line-height:1.7">
<b>${L('Laptop','ল্যাপটপ')} (Windows/Mac/Linux):</b><pre style="white-space:pre-wrap;font-size:11.5px">curl -fsSL ${BB_PUBLIC}/bb/link/royal_link.py -o royal_link.py && python3 royal_link.py</pre>
<b>Android (Termux + Shizuku):</b><pre style="white-space:pre-wrap;font-size:11.5px">curl -fsSL ${BB_PUBLIC}/bb/link/install_termux.sh | bash -s -- ${BB_PUBLIC}</pre><div style="font-size:12px;color:var(--mut);margin-top:4px">${L('The pairing code shows in Termux — approve it here. For screen/tap keep Shizuku rish running.','পেয়ার কোড টার্মউক্সে দেখাবে — এখানে Approve করুন। স্ক্রিন/ট্যাপ: Shizuku-এর rish চালু রাখুন।')}</div>
${L('After running, the device appears here as pending — it connects only after you approve.','চালানোর পর ডিভাইসটা এখানে "অপেক্ষমাণ" হিসেবে আসবে — আপনি অনুমোদন দিলে তবেই যুক্ত হবে।')} <a href="/bb/link/README.md" target=_blank>${L('Details','বিস্তারিত')}</a></div></div></div>`}
async function loadPerms(){const j=await api('/bb/api/devices');const el=$('#perms');if(!el)return;el.innerHTML='';
 j.devices.filter(d=>d.status!=='revoked'&&d.status!=='denied').forEach(d=>{const x=document.createElement('div');x.className='pm';
  x.innerHTML=`<h4><span><span class="dot ${d.online?'on':''}"></span>${esc(d.name)} <small style="color:var(--mut)">(${esc(d.kind)})</small></span>${d.status==='pending'?`<span><button class="btn pri" data-a=approve>✅ ${L('Approve','যুক্ত করুন')}</button> <button class="btn dan" data-a=deny>✕</button></span>`:d.id!=='box'?`<button class=btn data-a=remove>${L('Disconnect','সংযোগ বাতিল')}</button>`:''}</h4>`+
  (d.status==='approved'?Object.entries(j.caps).filter(([k])=>d.id!=='box'||k==='full'||k==='browser').map(([k,n])=>`<div class=r><span>${n}</span><select data-c=${k}>${Object.entries(MODEL).map(([m,l])=>`<option value=${m} ${d.perms[k]===m?'selected':''}>${l}</option>`).join('')}</select></div>`).join(''):L('<div style="font-size:12.5px;color:var(--gold)">⏳ Awaiting approval</div>','<div style="font-size:12.5px;color:var(--gold)">⏳ অনুমোদনের অপেক্ষায়</div>'));
  x.querySelectorAll('[data-a]').forEach(b=>b.onclick=async()=>{if(b.dataset.a!=='approve'&&!await uiConfirm(L('Disconnect this device?','এই ডিভাইসের সংযোগ বাতিল করবেন?')))return;await api(`/bb/api/devices/${d.id}/${b.dataset.a}`,{method:'POST'});loadPerms();toast('✓')});
  x.querySelectorAll('select').forEach(s=>s.onchange=async()=>{await api(`/bb/api/devices/${d.id}/perm`,{method:'POST',body:JSON.stringify({cap:s.dataset.c,mode:s.value})});toast(L('✓ Permission updated','✓ অনুমতি আপডেট'))});el.appendChild(x)})}
async function revokeAll(){if(!await uiConfirm(L('All devices and permissions will be revoked now. Sure?','সব ডিভাইসের সংযোগ আর সব অনুমতি এখনই বাতিল হবে। নিশ্চিত?')))return;await api('/bb/api/revoke-all',{method:'POST'});loadPerms();toast(L('⛔ All permissions revoked','⛔ সব অনুমতি বাতিল'))}
function aboutHTML(){return `<div class=row style="display:block"><b>${t('set.about')}</b><div class=about><div class="holo md" style="margin:0 auto"><div class="holo-inner"></div><img src="/bb/static/logo.png" alt=""></div><img class=wm src="/bb/static/wordmark.svg" alt="Bangla Bhai" style="margin-top:10px"><div class=byru>♛ by <b>Royal Universe</b></div><small>${t('set.about_d')}<br>© 2026 Royal Universe. All rights reserved.</small></div></div>`}
setTimeout(()=>setAgent(AGENT),300);setInterval(()=>{if($('#perms')&&$('#mset').classList.contains('on'))loadPerms()},8000);
