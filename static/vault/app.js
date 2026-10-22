/* Royal Vault — all crypto client-side. AES-GCM + PBKDF2-SHA256 (≥600k) for local store;
   ECDH P-256 + HKDF + AES-GCM for server feed. Server never sees plaintext. */
'use strict';
const ITER=600000, DB='rv1', ST=15*60*1000, CLIP=30000;
const $=s=>document.querySelector(s), toast=m=>{const t=$('#toast');t.textContent=m;t.classList.remove('hide');clearTimeout(toast._);toast._=setTimeout(()=>t.classList.add('hide'),2200)};
const b64=a=>btoa(String.fromCharCode(...new Uint8Array(a))), ub64=s=>Uint8Array.from(atob(s),c=>c.charCodeAt(0));
const te=s=>new TextEncoder().encode(s), td=b=>new TextDecoder().decode(b);
async function derive(pw,salt,i=ITER){const base=await crypto.subtle.importKey('raw',te(pw),'PBKDF2',false,['deriveKey']);
  return crypto.subtle.deriveKey({name:'PBKDF2',salt,iterations:i,hash:'SHA-256'},base,{name:'AES-GCM',length:256},false,['encrypt','decrypt']);}
async function aesEnc(key,obj){const iv=crypto.getRandomValues(new Uint8Array(12));
  return{iv:b64(iv),ct:b64(await crypto.subtle.encrypt({name:'AES-GCM',iv},key,te(JSON.stringify(obj))))};}
async function aesDec(key,blob){return JSON.parse(td(await crypto.subtle.decrypt({name:'AES-GCM',iv:ub64(blob.iv)},key,ub64(blob.ct))));}
async function pwEnc(obj,pw){const salt=crypto.getRandomValues(new Uint8Array(16));const key=await derive(pw,salt,ITER);
  return{kdf:'PBKDF2-SHA256',iter:ITER,salt:b64(salt),...(await aesEnc(key,obj))};}
async function pwDec(blob,pw){const key=await derive(pw,ub64(blob.salt),blob.iter||ITER);return aesDec(key,blob);}
async function ecdhGen(){const kp=await crypto.subtle.generateKey({name:'ECDH',namedCurve:'P-256'},true,['deriveBits']);
  const raw=new Uint8Array(await crypto.subtle.exportKey('raw',kp.publicKey));
  const pkcs8=new Uint8Array(await crypto.subtle.exportKey('pkcs8',kp.privateKey));
  const kid=b64(await crypto.subtle.digest('SHA-256',raw)).slice(0,16);
  return{kid,raw:b64(raw),pkcs8:b64(pkcs8)};}
async function feedDec(feed,pkcs8b64){const priv=await crypto.subtle.importKey('pkcs8',ub64(pkcs8b64),{name:'ECDH',namedCurve:'P-256'},false,['deriveBits']);
  const pub=await crypto.subtle.importKey('raw',ub64(feed.epk),{name:'ECDH',namedCurve:'P-256'},false,[]);
  const bits=await crypto.subtle.deriveBits({name:'ECDH',public:pub},priv,256);
  const base=await crypto.subtle.importKey('raw',bits,'HKDF',false,['deriveKey']);
  const key=await crypto.subtle.deriveKey({name:'HKDF',hash:'SHA-256',salt:new Uint8Array(),info:te('royal-vault-feed-v1')},{name:'AES-GCM',length:256},false,['decrypt']);
  return aesDec(key,{iv:feed.iv,ct:feed.ct});}

/* IndexedDB */
function idb(op){return new Promise((res,rej)=>{const r=indexedDB.open(DB,1);r.onupgradeneeded=()=>r.result.createObjectStore('kv');
  r.onsuccess=()=>{const tx=r.result.transaction('kv','readwrite'),s=tx.objectStore('kv');op(s,res,rej);tx.oncomplete=()=>r.result.close()};r.onerror=()=>rej(r.error);});}
const put=(k,v)=>idb((s,res)=>s.put(v,k).onsuccess=()=>res());
const get=k=>idb((s,res)=>{const q=s.get(k);q.onsuccess=()=>res(q.result);});
const del=k=>idb((s,res)=>s.delete(k).onsuccess=()=>res());

let MK=null, DATA={entries:[],meta:{}}, TIMER=null, last=Date.now(), clipT=null;
const touch=()=>{last=Date.now()};
document.addEventListener('pointerdown',touch);document.addEventListener('keydown',touch);
setInterval(()=>{if(MK&&Date.now()-last>ST)lock()},5000);

async function save(){if(!MK)return;await put('vault',await aesEnc(MK,DATA));}
async function unlock(pw){const wrap=await get('wrap');if(!wrap)throw new Error('no vault');
  const w=await pwDec(wrap,pw);MK=await crypto.subtle.importKey('raw',ub64(w.mk),{name:'AES-GCM'},false,['encrypt','decrypt']);
  try{DATA=await aesDec(MK,await get('vault'));}catch{DATA={entries:[],meta:{}};}
  touch();$('#lockb').classList.remove('hide');await pull();render();}
async function create(pw,imported){const mk=crypto.getRandomValues(new Uint8Array(32));
  MK=await crypto.subtle.importKey('raw',mk,{name:'AES-GCM'},false,['encrypt','decrypt']);
  await put('wrap',await pwEnc({mk:b64(mk)},pw));
  DATA=imported||{entries:[],meta:{}};await save();$('#lockb').classList.remove('hide');render();}
function lock(){MK=null;DATA={entries:[],meta:{}};$('#lockb').classList.add('hide');$('#syncb').classList.add('hide');renderGate();}

async function pull(){try{const f=await(await fetch('/vault/api/feed',{cache:'no-store'})).json();
  if(!f||!f.v||!f.ct||!DATA.meta.pkcs8)return;
  if(DATA.meta.feedV===f.v&&DATA.meta.kid===f.kid)return;
  const plain=await feedDec(f,DATA.meta.pkcs8);
  const map=new Map(DATA.entries.map(e=>[e.id,e]));
  for(const e of (plain.entries||[])){const old=map.get(e.id);e._new=!old||old.h!==e.h;map.set(e.id,e);}
  DATA.entries=[...map.values()];DATA.meta.feedV=f.v;DATA.meta.kid=f.kid;await save();
  const n=DATA.entries.filter(e=>e._new).length;$('#syncb').textContent=n?'Updated '+n:'Synced';$('#syncb').classList.remove('hide');
}catch(e){console.warn('pull',e);}}

async function doImport(url,impPw,master){
  const id=(url.match(/\/vault\/import\/([A-Za-z0-9_-]+)/)||[])[1];
  const blob=await(await fetch(url||('/vault/import/'+id),{cache:'no-store'})).json();
  if(blob.error)throw new Error(blob.error);
  const plain=await pwDec(blob,impPw);
  let kp=await ecdhGen();
  const r=await fetch('/vault/api/register',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({register_token:plain.register_token,raw:kp.raw,kid:kp.kid,import_id:id})});
  if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.error||'register failed');}
  const imported={entries:plain.entries||[],meta:{pkcs8:kp.pkcs8,kid:kp.kid,feedV:0}};
  if(MK){ // merging into existing
    const map=new Map(DATA.entries.map(e=>[e.id,e]));
    for(const e of imported.entries)map.set(e.id,e);
    DATA.entries=[...map.values()];DATA.meta={...DATA.meta,...imported.meta};await save();
  }else await create(master,imported);
  await pull();toast('Imported');
}

function copy(v){navigator.clipboard.writeText(v).then(()=>{toast('Copied · clears in 30s');
  clearTimeout(clipT);clipT=setTimeout(()=>{try{navigator.clipboard.writeText('')}catch{}},CLIP);});}

function renderGate(){const a=$('#app');
  get('wrap').then(w=>{a.innerHTML=`<div class="card"><h2>${w?'Unlock':'Set up'} Royal Vault</h2>
  <p class="mut">সব কী · লিংক · পাসওয়ার্ড — শুধু আপনার ফোনে, এনক্রিপ্টেড।</p>
  <label>Master password</label><input id="pw" type="password" autocomplete="current-password">
  ${w?'':'<label>Confirm</label><input id="pw2" type="password">'}
  <div class="row"><button id="go">${w?'Unlock':'Create vault'}</button>
  <button class="ghost" id="imp">Import from setup link</button></div>
  <div id="ibox" class="hide"><hr class="hr">
  <label>Import URL</label><input id="iu" placeholder="https://banglabhai.dpdns.org/vault/import/...">
  <label>Import passphrase</label><input id="ip" type="password">
  ${w?'':'<p class="mut">After import, the master password above becomes your phone lock.</p>'}
  <button id="ido">Import &amp; encrypt</button></div>
  <p id="err" class="err"></p></div>`;
  $('#imp').onclick=()=>$('#ibox').classList.toggle('hide');
  $('#go').onclick=async()=>{try{const p=$('#pw').value;if(p.length<8)throw new Error('Use ≥8 characters');
    if(w)await unlock(p);else{if(p!==$('#pw2').value)throw new Error('Passwords do not match');await create(p);}}
    catch(e){$('#err').textContent=e.message||String(e);}};
  $('#ido').onclick=async()=>{try{const p=$('#pw').value;if(p.length<8)throw new Error('Set a master password first (≥8)');
    if(!w&&p!==$('#pw2').value)throw new Error('Passwords do not match');
    await doImport($('#iu').value.trim(),$('#ip').value,p);render();}
    catch(e){$('#err').textContent=e.message||String(e);}};
  });}

let Q='',CAT='All',EDIT=null;
function cats(){const c=new Set(['All']);DATA.entries.forEach(e=>c.add(e.cat||'Other'));return[...c];}
function render(){if(!MK)return renderGate();const a=$('#app');
  const list=DATA.entries.filter(e=>{
    if(CAT!=='All'&&e.cat!==CAT)return false;
    if(!Q)return true;const hay=(e.name+' '+e.url+' '+e.notes+' '+(e.fields||[]).map(f=>f.k+' '+f.v).join(' ')).toLowerCase();
    return hay.includes(Q.toLowerCase());});
  a.innerHTML=`<div class="row"><input class="grow" id="q" placeholder="Search… খুঁজুন" value="${Q.replace(/"/g,'&quot;')}">
  <button class="ghost sm" id="add">＋</button><button class="ghost sm" id="sync">↻</button>
  <button class="ghost sm" id="exp">Export</button><button class="ghost sm" id="imp2">Import</button></div>
  <div class="chips">${cats().map(c=>`<button class="chip ${c===CAT?'on':''}" data-c="${c}">${c}</button>`).join('')}</div>
  <div id="list"></div>`;
  $('#q').oninput=e=>{Q=e.target.value;render();};$('#q').focus();$('#q').selectionStart=$('#q').value.length;
  a.querySelectorAll('.chip').forEach(b=>b.onclick=()=>{CAT=b.dataset.c;render();});
  $('#add').onclick=()=>editForm(null);$('#sync').onclick=async()=>{await pull();render();toast('Synced');};
  $('#exp').onclick=exportFile;$('#imp2').onclick=importFileUI;
  const L=$('#list');
  if(!list.length)L.innerHTML='<p class="mut">No entries.</p>';
  for(const e of list.sort((a,b)=>(a.cat+a.name).localeCompare(b.cat+b.name))){
    const d=document.createElement('div');d.className='card ent';
    d.innerHTML=`<div class="row"><div class="grow"><div class="cat">${e.cat||''}${e._new?' <span class="pill">NEW</span>':''}${e.src==='user'?' <span class="pill mut">yours</span>':''}</div>
      <h3>${esc(e.name)}</h3>${e.url?`<a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.url)}</a>`:''}</div>
      <button class="ghost sm" data-ed>✎</button>${e.src==='user'?`<button class="ghost sm bad" data-del>×</button>`:''}</div>
      <div class="fields"></div>${e.notes?`<div class="notes">${esc(e.notes)}</div>`:''}`;
    const F=d.querySelector('.fields');
    for(const f of (e.fields||[])){const row=document.createElement('div');row.className='f';
      const mask=!!f.s;row.innerHTML=`<b>${esc(f.k)}</b><code>${mask?'••••••••':esc(f.v)}</code>
        ${mask?`<button class="ghost sm" data-rev>👁</button>`:''}<button class="ghost sm" data-cp>Copy</button>`;
      let shown=false;const code=row.querySelector('code');
      row.querySelector('[data-cp]').onclick=()=>copy(f.v);
      const rev=row.querySelector('[data-rev]');if(rev)rev.onclick=()=>{shown=!shown;code.textContent=shown?f.v:'••••••••';};
      F.appendChild(row);}
    d.querySelector('[data-ed]').onclick=()=>editForm(e);
    const del=d.querySelector('[data-del]');if(del)del.onclick=async()=>{DATA.entries=DATA.entries.filter(x=>x.id!==e.id);await save();render();};
    L.appendChild(d); e._new=false;}}

function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function editForm(e){EDIT=e;const a=$('#app');const f=(e&&e.fields||[]).map(x=>({...x}));
  a.innerHTML=`<div class="card"><h2>${e?'Edit':'Add'} entry</h2>
  <label>Name</label><input id="n" value="${esc(e?e.name:'')}">
  <label>Category</label><input id="c" value="${esc(e?e.cat:'Other')}">
  <label>URL</label><input id="u" value="${esc(e?e.url:'')}">
  <label>Notes</label><textarea id="no">${esc(e?e.notes:'')}</textarea>
  <label>Fields (key · value · secret?)</label><div id="fs"></div>
  <button class="ghost sm" id="af">＋ field</button>
  <div class="row mt12"><button id="sv">Save</button><button class="ghost" id="ca">Cancel</button></div></div>`;
  const draw=()=>{$('#fs').innerHTML=f.map((x,i)=>`<div class="row"><input class="grow" data-k placeholder="Key" value="${esc(x.k)}">
    <input class="grow" data-v placeholder="Value" value="${esc(x.v)}"><label class="mut"><input type="checkbox" data-s ${x.s?'checked':''}> secret</label>
    <button class="ghost sm" data-x>×</button></div>`).join('');
    $('#fs').querySelectorAll('[data-x]').forEach((b,i)=>b.onclick=()=>{f.splice(i,1);draw();});};
  draw();$('#af').onclick=()=>{f.push({k:'',v:'',s:false});draw();};
  $('#ca').onclick=render;$('#sv').onclick=async()=>{
    const rows=[...$('#fs').children].map(r=>({k:r.querySelector('[data-k]').value,v:r.querySelector('[data-v]').value,s:r.querySelector('[data-s]').checked})).filter(x=>x.k||x.v);
    const ent={id:e?e.id:('usr:'+crypto.randomUUID()),src:e&&e.src==='server'?'server':'user',name:$('#n').value,cat:$('#c').value||'Other',url:$('#u').value,notes:$('#no').value,fields:rows,h:''};
    if(e){const i=DATA.entries.findIndex(x=>x.id===e.id);DATA.entries[i]={...DATA.entries[i],...ent};}
    else DATA.entries.push(ent);await save();render();};}

async function exportFile(){const pw=prompt('Export passphrase (remember it):');if(!pw||pw.length<8)return toast('Need ≥8 chars');
  const blob=await pwEnc({entries:DATA.entries,meta:{...DATA.meta,pkcs8:undefined}},pw); // never export private key
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(blob)],{type:'application/json'}));
  a.download='royal-vault-export.json';a.click();}
function importFileUI(){const i=document.createElement('input');i.type='file';i.accept='application/json,.json';
  i.onchange=async()=>{const pw=prompt('Export passphrase:');if(!pw)return;
    try{const blob=JSON.parse(await i.files[0].text());const p=await pwDec(blob,pw);
      const map=new Map(DATA.entries.map(e=>[e.id,e]));for(const e of(p.entries||[]))map.set(e.id,e);
      DATA.entries=[...map.values()];await save();render();toast('File imported');}catch(e){toast(e.message||'Import failed');}};
  i.click();}

$('#lockb').onclick=lock;
if('serviceWorker' in navigator)navigator.serviceWorker.register('/vault/sw.js',{scope:'/vault/'}).catch(()=>{});
renderGate();
