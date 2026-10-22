const $=s=>document.querySelector(s);let M={},P={},TAB='image';
const esc=s=>(s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function toast(t){const e=$('#toast');e.textContent=t;e.classList.add('on');clearTimeout(e._t);e._t=setTimeout(()=>e.classList.remove('on'),3000)}
async function api(u,o){const r=await fetch(u,o);if(r.status===401){location.href='/login';throw 0}const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.error||('Error '+r.status));return j}
function fillModels(){const edit=TAB==='edit';const im=M.image.filter(m=>edit?m.edit:m.gen!==false);$('#m-image').innerHTML=im.map(m=>`<option value="${esc(m.id)}">${esc(m.name)}</option>`).join('');
 $('#m-video').innerHTML=M.video.length?M.video.map(m=>`<option value="${esc(m.id)}">${esc(TT(m.name))}</option>`).join(''):'<option value="">'+TT('No video model yet')+'</option>';
 $('#vnote').textContent=TT(M.free_video_note)+' · '+TT('Free videos today')+': '+(M.quota.video>999?'∞':M.quota.video);$('#quota').textContent=TT('Free images today')+': '+(M.quota.image>999?'∞':M.quota.image)}
async function load(){M=await api('/bb/api/media/models');fillModels();loadGal();loadKeys()}
function tab(t){TAB=t;document.querySelectorAll('.st-tabs button').forEach(b=>b.classList.toggle('on',b.dataset.t===t));
 $('#t-gen').style.display=(t==='image'||t==='edit')?'':'none';$('#t-video').style.display=t==='video'?'':'none';$('#t-keys').style.display=t==='keys'?'':'none';
 $('#uplab').style.display=$('#f-img').style.display=t==='edit'?'':'none';if(t!=='edit'){$('#prev').style.display='none'}
 $('#go-image').textContent=t==='edit'?TT('Edit photo'):TT('Generate');$('#p-image').placeholder=t==='edit'?TT('What should change? e.g. "make the sky sunset orange"'):TT('Describe the image…');if(M.image)fillModels();history.replaceState(null,'','#'+t)}
document.querySelectorAll('.st-tabs button').forEach(b=>b.onclick=()=>tab(b.dataset.t));
$('#f-img').onchange=()=>{const f=$('#f-img').files[0];if(f){$('#prev').src=URL.createObjectURL(f);$('#prev').style.display=''}};
async function run(kind){const b=$('#go-'+kind),fd=new FormData();fd.append('prompt',$('#p-'+kind).value);fd.append('model',$('#m-'+kind).value);
 const f=kind==='image'?(TAB==='edit'?$('#f-img').files[0]:null):$('#f-vid').files[0];if(kind==='image'&&TAB==='edit'&&!f)return toast(TT('Choose a photo first'));if(f)fd.append('file',f);
 const old=b.textContent;b.disabled=true;b.textContent=TT('Working…');try{let R=await api('/bb/api/media/'+kind,{method:'POST',body:fd});if(R.job){const t0=Date.now();while(R.status==='running'&&Date.now()-t0<900000){await new Promise(r=>setTimeout(r,4000));R=await fetch('/bb/api/media/job/'+R.job).then(r=>r.json())}if(R.status!=='done')throw new Error(TT(R.error||'Failed'))}toast(R.note?TT(R.note):TT('Done ✓'));load()}catch(e){toast(e.message||TT('Failed'))}finally{b.disabled=false;b.textContent=old}}
$('#go-image').onclick=()=>run('image');$('#go-video').onclick=()=>run('video');
async function loadGal(){const g=await api('/bb/api/media');$('#gal').innerHTML=g.length?g.map(x=>`<figure>${x.kind==='video'?`<video src="${x.url}" controls preload=metadata></video>`:`<a href="${x.url}" target=_blank><img src="${x.url}" loading=lazy alt=""></a>`}<figcaption><span title="${esc(x.prompt)}">${esc(x.prompt)}</span><a href="${x.url}" download>⬇</a><button data-d="${x.id}">🗑</button></figcaption></figure>`).join(''):'<p class=mut>'+TT('Nothing yet.')+'</p>';
 $('#gal').querySelectorAll('[data-d]').forEach(b=>b.onclick=async()=>{if(confirm(TT('Delete this?'))){await api('/bb/api/media/'+b.dataset.d,{method:'DELETE'});loadGal()}})}
async function loadKeys(){const j=await api('/bb/api/keys');P=j.providers;if(!$('#k-prov').options.length)$('#k-prov').innerHTML=Object.entries(P).map(([k,v])=>`<option value=${k}>${esc(v.name)}</option>`).join('');
 $('#k-list').innerHTML=j.keys.length?j.keys.map(k=>`<div class=krow><span>🔑 <b>${esc(k.label||P[k.provider].name)}</b> · <code>${esc(k.hint)}</code></span><button class="btn dan" data-k="${k.id}">${TT('Remove')}</button></div>`).join(''):'<p class=mut>'+TT('No keys yet. Free models are used by default.')+'</p>';
 $('#k-list').querySelectorAll('[data-k]').forEach(b=>b.onclick=async()=>{if(confirm(TT('Remove this key?'))){await api('/bb/api/keys/'+b.dataset.k,{method:'DELETE'});load()}})}
$('#k-prov').onchange=()=>{$('#k-custom').style.display=$('#k-prov').value==='custom'?'':'none'};
const sp=s=>s.split(',').map(x=>x.trim()).filter(Boolean);
$('#k-add').onclick=async()=>{try{await api('/bb/api/keys',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider:$('#k-prov').value,label:$('#k-label').value,key:$('#k-key').value,base_url:$('#k-base').value,models:{chat:sp($('#k-chat').value),image:sp($('#k-img').value),video:sp($('#k-vid').value)}})});
 $('#k-key').value='';toast(TT('Key saved ✓'));load()}catch(e){toast(e.message)}};
pxApply();tab((location.hash.slice(1))||'image');load();
