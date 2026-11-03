'use strict';
/* Royal Notebook — editable notes: markdown + preview, folders/tags, search, pin/fav, autosave, versions, tasks, files, voice, AI, export, offline. */
const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const bn=n=>String(n).replace(/\d/g,d=>'০১২৩৪৫৬৭৮৯'[d]);
const H={'Content-Type':'application/json','x-bb-notes':'1'};
const S={view:'all',folder:'',tag:'',q:'',list:[],folders:{},tags:{},cur:null,dirty:false,mode:localStorage.nbMode||'edit',timer:null};
const LS={get:(k,d)=>{try{return JSON.parse(localStorage['nb_'+k])??d}catch(e){return d}},set:(k,v)=>{try{localStorage['nb_'+k]=JSON.stringify(v)}catch(e){}}};
function toast(m){const t=$('#toast');t.textContent=m;t.classList.add('on');clearTimeout(t._t);t._t=setTimeout(()=>t.classList.remove('on'),2200)}
async function api(u,o={}){const r=await fetch(u,{credentials:'same-origin',...o,headers:{...H,...(o.headers||{})}});
 if(r.status===401){location.href='/v4?next=/notes/';throw new Error('লগইন দরকার')}
 const j=await r.json().catch(()=>({}));if(!r.ok){const e=new Error(j.error||('ত্রুটি '+r.status));e.status=r.status;e.j=j;throw e}return j}
const ago=t=>{const s=Date.now()/1000-t;if(s<60)return'এইমাত্র';if(s<3600)return bn(Math.floor(s/60))+' মিনিট আগে';if(s<86400)return bn(Math.floor(s/3600))+' ঘণ্টা আগে';
 return new Date(t*1000).toLocaleDateString('bn-BD',{day:'numeric',month:'short',year:'numeric'})};
const today=()=>new Date(Date.now()+6*3600e3).toISOString().slice(0,10);

/* ---------- markdown (safe: escape first) ---------- */
function inl(s){return s.replace(/`([^`]+)`/g,'<code>$1</code>')
 .replace(/!\[([^\]]*)\]\(((?:https?:\/\/|\/bb\/api\/notes\/file\/)[^\s)]+)\)/g,'<img alt="$1" src="$2" loading="lazy">')
 .replace(/\[([^\]]+)\]\(((?:https?:\/\/|\/)[^\s)]+)\)/g,'<a href="$2" target="_blank" rel="noopener">$1</a>')
 .replace(/\*\*([^*]+)\*\*/g,'<b>$1</b>').replace(/(^|[^*])\*([^*\n]+)\*/g,'$1<i>$2</i>').replace(/~~([^~]+)~~/g,'<s>$1</s>')
 .replace(/@(\d{4}-\d{2}-\d{2})/g,(m,d)=>`<span class="due ${d<today()?'late':''}">📅 ${bn(d)}</span>`)
 .replace(/(^|\s)#([\p{L}\p{N}_-]+)/gu,'$1<span class="chip">#$2</span>')}
function md(src){const L=esc(src).split('\n');let o=[],list=null,code=false;
 const close=()=>{if(list){o.push('</'+list+'>');list=null}};
 L.forEach((ln,i)=>{
  if(/^```/.test(ln)){close();o.push(code?'</pre>':'<pre>');code=!code;return}
  if(code){o.push(ln+'\n');return}
  let m;
  if(m=ln.match(/^(#{1,4})\s+(.*)/)){close();o.push(`<h${m[1].length}>${inl(m[2])}</h${m[1].length}>`);return}
  if(m=ln.match(/^\s*[-*]\s+\[( |x|X)\]\s+(.*)/)){if(list!=='ul'){close();o.push('<ul>');list='ul'}o.push(`<li class="task"><input type="checkbox" data-line="${i}" ${m[1]!==' '?'checked':''}>${m[1]!==' '?'<s>'+inl(m[2])+'</s>':inl(m[2])}</li>`);return}
  if(m=ln.match(/^\s*[-*]\s+(.*)/)){if(list!=='ul'){close();o.push('<ul>');list='ul'}o.push('<li>'+inl(m[1])+'</li>');return}
  if(m=ln.match(/^\s*\d+[.)]\s+(.*)/)){if(list!=='ol'){close();o.push('<ol>');list='ol'}o.push('<li>'+inl(m[1])+'</li>');return}
  close();
  if(m=ln.match(/^&gt;\s?(.*)/)){o.push('<blockquote>'+inl(m[1])+'</blockquote>');return}
  if(/^(-{3,}|\*{3,})$/.test(ln.trim())){o.push('<hr>');return}
  o.push(ln.trim()?'<p>'+inl(ln)+'</p>':'')});
 close();if(code)o.push('</pre>');return o.join('')}

/* ---------- offline cache + queue ---------- */
const cache=()=>LS.get('cache',{}),setCache=c=>LS.set('cache',c);
function cachePut(n){const c=cache();c[n.id]={...(c[n.id]||{}),...n};setCache(c)}
const Q={get:()=>LS.get('queue',[]),push(op){const q=Q.get().filter(x=>!(x.id===op.id&&x.t===op.t&&op.t!=='create'));q.push(op);LS.set('queue',q)}};
async function flush(){if(!navigator.onLine)return;let q=Q.get();while(q.length){const op=q[0];
 try{if(op.t==='create')await api('/bb/api/notes',{method:'POST',body:JSON.stringify(op.d)}).catch(e=>{if(e.message!=='exists')throw e});
  else await api('/bb/api/notes/'+op.id,{method:'PUT',body:JSON.stringify({...op.d,force:true})})}catch(e){if(!e.status)return;}
 q=Q.get().slice(1);LS.set('queue',q)}netUI()}
function netUI(){const off=!navigator.onLine,q=Q.get().length;$('#net').className=off?'off':'';$('#net').title=off?'অফলাইন — পরিবর্তন জমা থাকছে':(q?bn(q)+'টি পরিবর্তন পাঠানো বাকি':'অনলাইন')}
addEventListener('online',()=>{flush().then(load)});addEventListener('offline',netUI);

/* ---------- list ---------- */
async function load(){if(S.smart&&S.q&&S.view!=='clips'){try{const j=await api('/bb/api/notes-smart/search?q='+encodeURIComponent(S.q));S.list=j.notes;side();return list()}catch(e){}}
 const p=new URLSearchParams({view:['tasks','clips'].includes(S.view)?'all':S.view,folder:S.folder,tag:S.tag,q:S.q});
 try{const j=await api('/bb/api/notes?'+p);S.list=j.notes;S.folders=j.folders;S.tags=j.tags;LS.set('list',j)}
 catch(e){if(e.status)return toast(e.message);const j=LS.get('list',{notes:[],folders:{},tags:{}});S.list=j.notes;S.folders=j.folders;S.tags=j.tags;
  if(S.q){const t=S.q.toLowerCase();S.list=S.list.filter(n=>(n.title+' '+n.body).toLowerCase().includes(t))}}
 side();S.view==='tasks'?tasks():S.view==='clips'?clips():list()}
function side(){const V=[['all','🗒 সব নোট'],['fav','⭐ প্রিয়'],['tasks','☑ কাজের তালিকা'],['clips','📋 ক্লিপবোর্ড (৩০ দিন)'],['archive','🗄 আর্কাইভ'],['trash','🗑 ট্র্যাশ']];
 $('#views').innerHTML=V.map(([k,l])=>`<a data-v="${k}" class="${S.view===k&&!S.folder&&!S.tag?'act':''}">${l}</a>`).join('');
 $('#folders').innerHTML=Object.entries(S.folders).sort().map(([f,c])=>`<a data-f="${esc(f)}" class="${S.folder===f?'act':''}">📁 ${esc(f)}<small>${bn(c)}</small></a>`).join('')||'<small style="color:var(--mu);padding:0 10px">নেই</small>';
 $('#tags').innerHTML=Object.entries(S.tags).sort((a,b)=>b[1]-a[1]).map(([t,c])=>`<a data-t="${esc(t)}" class="${S.tag===t?'act':''}">#${esc(t)}<small>${bn(c)}</small></a>`).join('')||'<small style="color:var(--mu);padding:0 10px">নেই</small>';
 $('#folderList').innerHTML=Object.keys(S.folders).map(f=>`<option value="${esc(f)}">`).join('')}
function list(){const L=S.list;if(!L.length){$('#list').innerHTML=`<p style="color:var(--mu);text-align:center;margin-top:30px">${S.q?'কিছু পাওয়া যায়নি':'কোনো নোট নেই — ＋ চাপুন'}</p>`;return}
 $('#list').innerHTML=L.map(n=>`<div class="it ${S.cur?.id===n.id?'act':''}" data-id="${n.id}"><b>${n.pinned?'📌 ':''}${n.fav?'⭐ ':''}${esc(n.title||'শিরোনামহীন')}</b>
 <p>${esc((n.body||'').replace(/[#*>`\[\]]/g,'').slice(0,140))}</p><small>${ago(n.updated)}${n.folder?' · 📁 '+esc(n.folder):''}</small> ${(n.tags||[]).map(t=>`<span class="chip">#${esc(t)}</span>`).join('')}</div>`).join('')}
async function tasks(){let T=[];try{T=(await api('/bb/api/notes/tasks')).tasks}catch(e){return toast(e.message)}
 const td=today(),open=T.filter(t=>!t.done);
 const grp=[['⏰ সময় পেরিয়েছে',open.filter(t=>t.due&&t.due<td)],['📌 আজ',open.filter(t=>t.due===td)],['🗓 সামনে',open.filter(t=>t.due&&t.due>td)],['📝 তারিখ ছাড়া',open.filter(t=>!t.due)],['✅ শেষ',T.filter(t=>t.done).slice(0,30)]];
 $('#list').innerHTML=(T.length?'':'<p style="color:var(--mu);text-align:center;margin-top:30px">কোনো কাজ নেই। নোটে "- [ ] কাজ @তারিখ" লিখুন।</p>')+grp.filter(g=>g[1].length).map(([h,a])=>`<h4 style="margin:10px 4px 2px">${h} (${bn(a.length)})</h4>`+a.map(t=>
 `<div class="task-row ${t.done?'done':''}"><input type="checkbox" ${t.done?'checked':''} data-n="${t.note}" data-l="${t.line}"><span data-open="${t.note}" style="cursor:pointer">${esc(t.text)}</span><small>${t.due?bn(t.due):''} · ${esc(t.title||'')}</small></div>`).join('')).join('')}

/* ---------- editor ---------- */
async function open(id){if(S.dirty)await save();let n;
 try{n=await api('/bb/api/notes/'+id);cachePut(n)}catch(e){if(e.status)return toast(e.message);n=cache()[id]||S.list.find(x=>x.id===id);if(!n)return toast('অফলাইনে এই নোট নেই')}
 S.cur=n;S.dirty=false;$('#edPane').classList.remove('empty');$('#title').value=n.title||'';$('#body').value=n.body||'';$('#folder').value=n.folder||'';
 $('#tagIn').value=(n.tags||[]).join(', ');$('#pinB').classList.toggle('on',!!n.pinned);$('#favB').classList.toggle('on',!!n.fav);
 $('#upd').textContent='সম্পাদিত '+ago(n.updated);$('#saveState').textContent=n.trashed?'🗑 ট্র্যাশে':'';files(n.files||[]);render();mode(S.mode);related(id);
 document.querySelectorAll('.it').forEach(e=>e.classList.toggle('act',e.dataset.id===id));history.replaceState({},'','/notes/?id='+id)}
function files(F){$('#files').innerHTML=F.map(f=>`<a href="/bb/api/notes/file/${f.id}" target="_blank">📎 ${esc(f.name)} <small>${bn(Math.ceil(f.size/1024))}KB</small></a>`).join('')}
function render(){const b=$('#body').value;$('#prev').innerHTML=md(b);const w=b.trim()?b.trim().split(/\s+/).length:0;$('#wc').textContent=bn(w)+' শব্দ · '+bn(b.length)+' অক্ষর'}
function mode(m){S.mode=m;localStorage.nbMode=m;const w=$('#edWrap');w.classList.toggle('preview',m==='preview');w.classList.toggle('split',m==='split');
 $('#modeB').textContent={edit:'👁 প্রিভিউ',preview:'✏️ পাশাপাশি',split:'📝 শুধু লেখা'}[m];if(m!=='edit')render()}
function fields(){return{title:$('#title').value,body:$('#body').value,folder:$('#folder').value.trim(),tags:$('#tagIn').value.split(/[,،]/).map(s=>s.trim().replace(/^#/,'')).filter(Boolean)}}
function dirty(){S.dirty=true;$('#saveState').textContent='✍️ লিখছেন…';clearTimeout(S.timer);S.timer=setTimeout(save,900);if(S.mode!=='edit')render();else render()}
async function save(snapshot){if(!S.cur)return;clearTimeout(S.timer);const d=fields(),id=S.cur.id;S.dirty=false;cachePut({id,...d,updated:Date.now()/1000});
 try{const n=await api('/bb/api/notes/'+id,{method:'PUT',body:JSON.stringify({...d,base:S.cur.updated,snapshot:!!snapshot})});S.cur={...S.cur,...n};
  $('#saveState').textContent='✓ সংরক্ষিত';autotag(id,d);$('#upd').textContent='সম্পাদিত এইমাত্র';const it=S.list.find(x=>x.id===id);if(it){Object.assign(it,n);}else S.list.unshift(n);if(S.view!=='tasks')list()}
 catch(e){if(e.status===409){if(confirm('এই নোট অন্য ডিভাইসে বদলানো হয়েছে। আপনার লেখা রাখব? (বাতিল = সার্ভারের লেখা দেখাবে)')){S.cur.updated=e.j.server.updated;return save(true)}else return open(id)}
  if(!e.status){Q.push({t:'put',id,d});$('#saveState').textContent='💾 অফলাইনে জমা';netUI()}else{$('#saveState').textContent='⚠ '+e.message;S.dirty=true}}}
async function create(extra={}){const id=(crypto.randomUUID?crypto.randomUUID():Date.now().toString(36)+Math.random().toString(36).slice(2)).replace(/-/g,'').slice(0,12);
 const d={id,title:'',body:'',folder:S.folder,tags:S.tag?[S.tag]:[],...extra},now=Date.now()/1000;
 try{const n=await api('/bb/api/notes',{method:'POST',body:JSON.stringify(d)});S.list.unshift(n);cachePut(n)}
 catch(e){if(e.status)return toast(e.message);Q.push({t:'create',id,d});const n={...d,created:now,updated:now,pinned:0,fav:0};S.list.unshift(n);cachePut(n);netUI()}
 if(S.view==='tasks'||S.view==='trash'||S.view==='archive')S.view='all';list();await open(id);$('#title').focus()}
function ins(tpl){const t=$('#body'),[a,b='']=tpl.split('|'),s=t.selectionStart,e=t.selectionEnd,sel=t.value.slice(s,e);
 let pre=a;if(/^(## |- |- \[ \] |> )$/.test(a)&&s>0&&t.value[s-1]!=='\n')pre='\n'+a;
 t.setRangeText(pre+sel+b,s,e,'end');if(!sel)t.selectionStart=t.selectionEnd=s+pre.length;t.focus();dirty()}
async function toggleLine(nid,line,on){let body;if(S.cur?.id===nid)body=$('#body').value;else body=(await api('/bb/api/notes/'+nid)).body;
 const L=body.split('\n');if(!L[line])return;L[line]=L[line].replace(/\[( |x|X)\]/,on?'[x]':'[ ]');body=L.join('\n');
 if(S.cur?.id===nid){$('#body').value=body;dirty()}else await api('/bb/api/notes/'+nid,{method:'PUT',body:JSON.stringify({body})})}
async function setFlag(k){if(!S.cur)return;const v=S.cur[k]?0:1;try{const n=await api('/bb/api/notes/'+S.cur.id,{method:'PUT',body:JSON.stringify({[k]:v})});S.cur={...S.cur,...n};
 $('#pinB').classList.toggle('on',!!n.pinned);$('#favB').classList.toggle('on',!!n.fav);load();toast({pinned:v?'📌 পিন করা হলো':'পিন সরানো হলো',fav:v?'⭐ প্রিয়তে যোগ':'প্রিয় থেকে সরানো',archived:v?'🗄 আর্কাইভ হলো':'আর্কাইভ থেকে ফিরল',trashed:v?'🗑 ট্র্যাশে গেল':'♻️ ফিরিয়ে আনা হলো'}[k])}catch(e){toast(e.message)}}

/* ---------- sheets ---------- */
function sheet(h){$('#sheetBody').innerHTML=h;$('#sheet').hidden=false}const unsheet=()=>{$('#sheet').hidden=true};
function aiMenu(){if(!S.cur)return;const A=[['summarize','📋 সারাংশ'],['fix','✅ বানান/ব্যাকরণ ঠিক'],['to_bn','🇧🇩 বাংলায় অনুবাদ'],['to_en','🇬🇧 ইংরেজিতে অনুবাদ'],['todo','☑ কাজের তালিকা বানাও'],['expand','📝 বিস্তারিত করো'],['title','🏷 শিরোনাম দাও']];
 sheet(`<h3>✨ AI দিয়ে নোটে কাজ</h3><small style="color:var(--mu)">কিছু লেখা সিলেক্ট করা থাকলে শুধু সেটুকুর উপর কাজ হবে।</small><div class="row">${A.map(([k,l])=>`<button data-ai="${k}">${l}</button>`).join('')}</div>
 <div class="row"><input id="aiQ" style="flex:1" placeholder="নোট নিয়ে প্রশ্ন করুন…"><button data-ai="ask" style="flex:0">জিজ্ঞাসা</button></div><div id="aiOut"></div>`)}
async function runAI(act){const t=$('#body'),sel=t.value.slice(t.selectionStart,t.selectionEnd),out=$('#aiOut');out.innerHTML='<p>⏳ AI ভাবছে…</p>';
 if(S.dirty)await save();
 try{const j=await api('/bb/api/notes/'+S.cur.id+'/ai',{method:'POST',body:JSON.stringify({action:act,text:sel||undefined,q:$('#aiQ')?.value})});S.ai={act,text:j.text,sel:!!sel,s:t.selectionStart,e:t.selectionEnd};
  out.innerHTML=`<pre>${esc(j.text)}</pre><div class="row">${act==='title'?'<button data-apply="title">শিরোনাম বসাও</button>':`<button data-apply="replace">${sel?'সিলেকশন বদলাও':'পুরো নোট বদলাও'}</button><button data-apply="append">নিচে যোগ করো</button>`}<button data-apply="copy">কপি</button><button data-apply="new">নতুন নোটে</button></div>`}
 catch(e){out.innerHTML='<p>⚠ '+esc(e.message)+'</p>'}}
async function applyAI(how){const a=S.ai,t=$('#body');if(!a)return;
 if(how==='copy'){navigator.clipboard?.writeText(a.text);return toast('কপি হয়েছে')}
 if(how==='new'){unsheet();return create({title:'AI: '+($('#title').value||''),body:a.text})}
 if(how==='title')$('#title').value=a.text.replace(/^["'#\s]+|["'\s]+$/g,'');
 else if(how==='replace'){await save(true);if(a.sel)t.setRangeText(a.text,a.s,a.e,'end');else t.value=a.text}
 else t.value=t.value.replace(/\s*$/,'')+'\n\n'+a.text;
 unsheet();dirty();save(true);toast('✓ যোগ হয়েছে (পুরনো লেখা ইতিহাসে আছে)')}
async function versions(){try{const V=(await api('/bb/api/notes/'+S.cur.id+'/versions')).versions;S.V=V;
 sheet(`<h3>🕘 আগের সংস্করণ</h3>${V.length?V.map((v,i)=>`<div class="ver"><b>${esc(v.title||'শিরোনামহীন')}</b> <small style="color:var(--mu)">${new Date(v.ts*1000).toLocaleString('bn-BD')}</small><p style="color:var(--mu);font-size:13px;margin:4px 0">${esc((v.body||'').slice(0,160))}</p><button data-ver="${i}">↩ এটা ফিরিয়ে আনুন</button></div>`).join(''):'<p>এখনো কোনো আগের সংস্করণ নেই। লেখা বদলালে প্রতি ২ মিনিটে নিজে থেকে জমা হয়।</p>'}`)}catch(e){toast(e.message)}}
function more(){if(!S.cur)return;const c=S.cur;sheet(`<h3>${esc(c.title||'নোট')}</h3><div class="row">
 <button data-m="versions">🕘 আগের সংস্করণ / আনডু</button><button data-m="snap">💾 এখনই সংস্করণ রাখুন</button>
 <button data-m="md">⬇️ Markdown (.md) নামান</button><button data-m="pdf">🖨 PDF / প্রিন্ট</button>
 <button data-m="copy">📋 পুরো লেখা কপি</button><button data-m="dup">🧬 কপি বানান</button>
 <button data-m="archived">${c.archived?'🗄 আর্কাইভ থেকে ফেরান':'🗄 আর্কাইভ'}</button>
 ${c.trashed?'<button data-m="restore">♻️ ট্র্যাশ থেকে ফেরান</button><button data-m="purge">❌ চিরতরে মুছুন</button>':'<button data-m="trash">🗑 ট্র্যাশে ফেলুন</button>'}</div>
 <small style="color:var(--mu)">শর্টকাট: Ctrl+S সংরক্ষণ · Ctrl+K খোঁজা · Ctrl+Alt+N নতুন নোট · Ctrl+B/I</small>`)}
async function moreAct(m){const c=S.cur;unsheet();
 if(m==='versions')return versions();if(m==='snap'){await save(true);return toast('💾 সংস্করণ রাখা হয়েছে')}
 if(m==='md'){await save();location.href='/bb/api/notes/'+c.id+'/export.md';return}
 if(m==='pdf'){await save();mode('preview');setTimeout(()=>print(),300);return}
 if(m==='copy'){navigator.clipboard?.writeText($('#body').value);return toast('কপি হয়েছে')}
 if(m==='dup')return create({...fields(),title:fields().title+' (কপি)'});
 if(m==='archived')return setFlag('archived');if(m==='trash'||m==='restore'){await setFlag('trashed');if(m==='trash')closeEd();return}
 if(m==='purge'){if(!confirm('চিরতরে মুছে যাবে, আর ফেরানো যাবে না। নিশ্চিত?'))return;try{await api('/bb/api/notes/'+c.id,{method:'DELETE'});closeEd();load();toast('মুছে ফেলা হয়েছে')}catch(e){toast(e.message)}}}
function closeEd(){S.cur=null;$('#edPane').classList.add('empty');history.replaceState({},'','/notes/')}

/* ---------- files & voice ---------- */
async function upload(fl){if(!S.cur)return;for(const f of fl){const fd=new FormData();fd.append('file',f);toast('⏫ '+f.name);
 try{const r=await fetch('/bb/api/notes/'+S.cur.id+'/files',{method:'POST',body:fd,credentials:'same-origin',headers:{'x-bb-notes':'1'}});const j=await r.json();if(!r.ok)throw new Error(j.error);
  ins((f.type.startsWith('image/')?'![':'[📎 ')+f.name.replace(/[\[\]]/g,'')+']('+j.url+')|');S.cur.files=[...(S.cur.files||[]),j];files(S.cur.files)}catch(e){toast('⚠ '+(e.message||'আপলোড হয়নি'))}}}
let REC=null;
async function mic(){const b=$('#micB');if(REC){REC.stop();return}
 try{const st=await navigator.mediaDevices.getUserMedia({audio:true});const ch=[];const r=new MediaRecorder(st);REC=r;b.classList.add('rec');b.textContent='⏹';toast('🎤 বলুন… (শেষে ⏹ চাপুন, সর্বোচ্চ ২ মিনিট)');
  const lim=setTimeout(()=>r.state==='recording'&&r.stop(),118000);r.ondataavailable=e=>ch.push(e.data);
  r.onstop=async()=>{clearTimeout(lim);st.getTracks().forEach(t=>t.stop());REC=null;b.classList.remove('rec');b.textContent='🎤';toast('⏳ লেখায় রূপান্তর হচ্ছে…');
   const fd=new FormData();fd.append('file',new Blob(ch,{type:r.mimeType||'audio/webm'}),'v.webm');
   try{const x=await fetch('/bb/api/stt',{method:'POST',body:fd,credentials:'same-origin'});const j=await x.json();if(!x.ok||!j.text)throw new Error(j.error||'বোঝা যায়নি');ins(j.text+' |');toast('✓ যোগ হয়েছে')}catch(e){toast('⚠ '+e.message)}};
  r.start()}catch(e){toast('মাইক্রোফোনের অনুমতি দিন')}}

/* ---------- events ---------- */
document.addEventListener('click',async e=>{const x=e.target.closest('[data-v],[data-f],[data-t],.it,[data-md],[data-ai],[data-apply],[data-ver],[data-m],[data-open]');if(!x)return;
 if(x.dataset.v){S.view=x.dataset.v;S.folder='';S.tag='';$('#side').classList.remove('open');return load()}
 if(x.dataset.f!=null){S.folder=S.folder===x.dataset.f?'':x.dataset.f;S.tag='';S.view='all';$('#side').classList.remove('open');return load()}
 if(x.dataset.t!=null){S.tag=S.tag===x.dataset.t?'':x.dataset.t;S.folder='';S.view='all';$('#side').classList.remove('open');return load()}
 if(x.classList.contains('it'))return open(x.dataset.id);if(x.dataset.open)return open(x.dataset.open);
 if(x.dataset.md)return ins(x.dataset.md);if(x.dataset.ai)return runAI(x.dataset.ai);if(x.dataset.apply)return applyAI(x.dataset.apply);
 if(x.dataset.ver){const v=S.V[+x.dataset.ver];await save(true);$('#title').value=v.title||'';$('#body').value=v.body||'';unsheet();dirty();return toast('↩ ফিরিয়ে আনা হয়েছে')}
 if(x.dataset.m)return moreAct(x.dataset.m)});
document.addEventListener('change',e=>{const c=e.target;if(c.matches('#prev input[type=checkbox]'))toggleLine(S.cur.id,+c.dataset.line,c.checked);
 if(c.matches('.task-row input'))toggleLine(c.dataset.n,+c.dataset.l,c.checked).then(()=>setTimeout(tasks,1200))});
$('#newBtn').onclick=()=>create();$('#menuBtn').onclick=()=>$('#side').classList.toggle('open');$('#backList').onclick=async()=>{if(S.dirty)await save();closeEd();load()};
['#title','#body','#folder','#tagIn'].forEach(s=>$(s).addEventListener('input',dirty));
$('#folder').addEventListener('change',()=>save().then(load));$('#tagIn').addEventListener('change',()=>save().then(load));
$('#pinB').onclick=()=>setFlag('pinned');$('#favB').onclick=()=>setFlag('fav');$('#modeB').onclick=()=>mode({edit:'preview',preview:'split',split:'edit'}[S.mode]);
$('#aiB').onclick=aiMenu;$('#moreB').onclick=more;$('#attB').onclick=()=>$('#file').click();$('#file').onchange=e=>{upload([...e.target.files]);e.target.value=''};$('#micB').onclick=mic;
$('#dueB').onclick=()=>{const d=prompt('কাজের শেষ তারিখ (YYYY-MM-DD):',today());if(d&&/^\d{4}-\d{2}-\d{2}$/.test(d))ins('- [ ] | @'+d)};
$('#sheetX').onclick=unsheet;$('#sheet').onclick=e=>{if(e.target.id==='sheet')unsheet()};
let qt;$('#q').addEventListener('input',e=>{clearTimeout(qt);qt=setTimeout(()=>{S.q=e.target.value.trim();if(S.view==='tasks')S.view='all';load()},S.smart?600:250)});
$('#body').addEventListener('paste',e=>{const f=[...(e.clipboardData?.files||[])];if(f.length){e.preventDefault();upload(f)}});
$('#body').addEventListener('drop',e=>{const f=[...(e.dataTransfer?.files||[])];if(f.length){e.preventDefault();upload(f)}});
$('#body').addEventListener('keydown',e=>{if(e.key==='Enter'){const t=e.target,s=t.selectionStart,ls=t.value.lastIndexOf('\n',s-1)+1,ln=t.value.slice(ls,s),m=ln.match(/^(\s*)([-*] \[[ xX]\] |[-*] |\d+[.)] )/);
 if(m){e.preventDefault();if(ln.trim()===m[2].trim()){t.setRangeText('',ls,s,'end');dirty();return}let nx=m[2].replace(/\[[xX]\]/,'[ ]').replace(/^(\d+)/,n=>+n+1);t.setRangeText('\n'+m[1]+nx,s,s,'end');dirty()}}});
document.addEventListener('keydown',e=>{const k=e.key.toLowerCase(),c=e.ctrlKey||e.metaKey;if(!c)return;
 if(k==='s'){e.preventDefault();save(true).then(()=>toast('💾 সংরক্ষিত'))}else if(k==='k'){e.preventDefault();$('#q').focus()}
 else if(k==='n'&&e.altKey){e.preventDefault();create()}else if(k==='b'&&document.activeElement.id==='body'){e.preventDefault();ins('**|**')}else if(k==='i'&&document.activeElement.id==='body'){e.preventDefault();ins('*|*')}});
addEventListener('beforeunload',e=>{if(S.dirty){save();e.preventDefault();e.returnValue=''}});
document.addEventListener('visibilitychange',()=>{if(document.hidden&&S.dirty)save()});
if('serviceWorker'in navigator)navigator.serviceWorker.register('/notes/sw.js',{scope:'/notes/'}).catch(()=>{});
(async()=>{netUI();await flush();await load();const p=new URLSearchParams(location.search);if(p.get('id'))open(p.get('id'));else if(p.get('new'))create();else if(p.get('view')==='tasks'){S.view='tasks';load()}
 setInterval(()=>{if(!S.dirty&&!document.hidden&&S.view!=='tasks')load()},60000)})();

/* ---------- smart: related, autotag, semantic search ---------- */
const AT=LS.get('autotagged',{});
async function autotag(id,d){if(AT[id]||(d.body||'').trim().length<120)return;AT[id]=1;LS.set('autotagged',AT);
 try{const j=await api('/bb/api/notes/'+id+'/autotag',{method:'POST',body:'{}'});if(j.tags&&S.cur?.id===id){$('#tagIn').value=j.tags.join(', ');if(j.title&&!$('#title').value)$('#title').value=j.title;S.cur.updated=Date.now()/1000+1;toast('🏷 AI ট্যাগ দিল: '+j.tags.join(', '));load()}}catch(e){}}
async function related(id){let el=$('#related');if(!el){el=document.createElement('div');el.id='related';el.style.cssText='font-size:12px;color:var(--mu);padding-top:4px';$('#files').after(el)}el.innerHTML='';
 try{const j=await api('/bb/api/notes/'+id+'/related');if(j.related.length)el.innerHTML='🔗 সম্পর্কিত নোট: '+j.related.map(r=>`<a class="chip" style="cursor:pointer" data-open="${r.id}">${esc(r.title||'শিরোনামহীন')}</a>`).join(' ')}catch(e){}}
(()=>{const q=$('#q');const b=document.createElement('button');b.className='icon';b.title='স্মার্ট খোঁজা (AI সমার্থক শব্দ, বাংলা↔ইংরেজি)';b.textContent='🧠';
 b.onclick=()=>{S.smart=!S.smart;b.classList.toggle('on',S.smart);toast(S.smart?'🧠 স্মার্ট খোঁজা চালু':'সাধারণ খোঁজা');if(S.q)load()};q.after(b)})();
/* ---------- clipboard panel ---------- */
const CAT={link:'🔗 লিংক',phone:'📞 ফোন',email:'✉️ ইমেইল',code:'💻 কোড',date:'📅 তারিখ',bangla:'🇧🇩 বাংলা লেখা',text:'📝 লেখা',image:'🖼 ছবি'};
async function clips(){let j;try{j=await api('/bb/api/clips?limit=200&q='+encodeURIComponent(S.q)+'&cat='+encodeURIComponent(S.ccat||''))}catch(e){return toast(e.message)}S.clips=j.clips;
 $('#list').innerHTML=`<div style="padding:4px"><small style="color:var(--mu)">আপনার ডিভাইসগুলোতে কপি করা জিনিস ৩০ দিন থাকে (📌 পিন করলে সবসময়)। পাসওয়ার্ড/OTP/কার্ড নম্বর রাখা হয় না।</small>
 <div style="margin:6px 0"><button id="cPaste">📋 এখন পেস্ট করে রাখুন</button> <button id="cDig">🌅 আজকের সারাংশ</button> <button id="cClr">🧹 পিন ছাড়া সব মুছুন</button></div>
 <div>${['',...Object.keys(j.cats)].map(c=>`<a class="chip" style="cursor:pointer;${(S.ccat||'')===c?'outline:1px solid var(--gd)':''}" data-cc="${c}">${c?CAT[c]||c:'সব'} ${c?bn(j.cats[c]):''}</a>`).join('')}</div><div id="cDigOut"></div></div>`+
 (j.clips.map((c,i)=>`<div class="it" style="cursor:default"><small>${CAT[c.cat]||c.cat} · ${esc(c.device||'')} · ${ago(c.last)}${c.count>1?' · ×'+bn(c.count):''}${c.pinned?' · 📌':''}</small>
 ${c.kind==='image'?`<img src="${esc(c.content)}" style="max-width:100%;border-radius:8px">`:`<p style="max-height:5em;white-space:pre-wrap">${esc(c.content.slice(0,400))}</p>`}
 <div>${c.kind!=='image'?`<button data-ca="copy" data-i="${i}">📋 কপি</button>`:''}<button data-ca="note" data-i="${i}">📝 নোট</button><button data-ca="pin" data-i="${i}">${c.pinned?'আনপিন':'📌'}</button>
 ${c.cat==='link'?`<button data-ca="open" data-i="${i}">🔗 খুলুন</button>`:''}${c.cat==='phone'?`<button data-ca="call" data-i="${i}">📞</button>`:''}${c.cat==='email'?`<button data-ca="mail" data-i="${i}">✉️</button>`:''}${c.cat==='date'?`<button data-ca="task" data-i="${i}">☑ কাজ</button>`:''}
 <button data-ca="del" data-i="${i}">🗑</button></div><small style="color:var(--gd)">💡 ${esc((c.suggest||[]).join(' · '))}</small></div>`).join('')||'<p style="color:var(--mu);text-align:center">এখনো কোনো ক্লিপ নেই</p>');
 $('#cPaste').onclick=async()=>{try{const t=await navigator.clipboard.readText();if(!t)return toast('ক্লিপবোর্ড খালি');const r=await api('/bb/api/clips',{method:'POST',body:JSON.stringify({content:t,device:'নোটবুক'})});toast(r.skipped==='private'?'🔒 গোপন তথ্য মনে হলো — রাখা হয়নি':'✓ রাখা হয়েছে');clips()}catch(e){toast('ব্রাউজার অনুমতি দেয়নি')}};
 $('#cClr').onclick=async()=>{if(!confirm('পিন ছাড়া সব ক্লিপ মুছবে?'))return;await api('/bb/api/clips/0',{method:'DELETE'});clips()};
 $('#cDig').onclick=async()=>{$('#cDigOut').innerHTML='⏳ …';try{const d=await api('/bb/api/clips/digest');$('#cDigOut').innerHTML=`<div class="md" style="background:var(--pn);padding:8px;border-radius:10px;margin-top:6px">আজ ${bn(d.count)}টি কপি। ${md(d.summary||'')}<button id="cDigN">📝 নোট বানান</button></div>`;$('#cDigN').onclick=()=>create({title:'ক্লিপবোর্ড সারাংশ '+today(),body:d.summary,folder:'দৈনিক সারাংশ'})}catch(e){$('#cDigOut').textContent=e.message}}}
document.addEventListener('click',async e=>{const x=e.target.closest('[data-ca],[data-cc]');if(!x)return;e.stopPropagation();
 if(x.dataset.cc!=null){S.ccat=x.dataset.cc;return clips()}const c=S.clips[+x.dataset.i],a=x.dataset.ca;
 if(a==='copy'){navigator.clipboard?.writeText(c.content);return toast('📋 আবার কপি হলো')}
 if(a==='open')return window.open(c.content.startsWith('http')?c.content:'https://'+c.content,'_blank','noopener');
 if(a==='call')return location.href='tel:'+c.content.replace(/[^\d+]/g,'');if(a==='mail')return location.href='mailto:'+c.content;
 if(a==='note')return create({title:(c.kind==='image'?'ছবি':c.content.split('\n')[0]).slice(0,60),body:c.kind==='image'?`![ছবি](${c.content.startsWith('data:')?'':c.content})`+(c.content.startsWith('data:')?'\n(ছবি ক্লিপবোর্ডে আছে)':''):(c.cat==='code'?'```\n'+c.content+'\n```':c.content),folder:'ক্লিপবোর্ড'});
 if(a==='task')return create({title:'কাজ',body:'- [ ] '+c.content,folder:'ক্লিপবোর্ড'});
 if(a==='pin'){await api('/bb/api/clips/'+c.id,{method:'PUT',body:JSON.stringify({pinned:!c.pinned})});return clips()}
 if(a==='del'){await api('/bb/api/clips/'+c.id,{method:'DELETE'});return clips()}},true);
document.addEventListener('copy',()=>{const t=String(getSelection()||'');if(t.length>1)api('/bb/api/clips',{method:'POST',body:JSON.stringify({content:t,device:'নোটবুক'})}).catch(()=>{})});
if(new URLSearchParams(location.search).get('view')==='clips'){S.view='clips';setTimeout(load,300)}
