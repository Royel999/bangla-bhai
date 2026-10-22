const $=s=>document.querySelector(s),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const T=(k,f)=>{const v=window.t?t(k):k;return v===k?(f||k):v};
let D,CAT=null,VIEW=null;
const CATS=[['featured','cn.cat.featured','Featured'],['ai','cn.cat.ai','AI models'],['productivity','cn.cat.productivity','Productivity'],['messaging','cn.cat.messaging','Messaging'],['media','cn.cat.media','Image, video & voice'],['developer','cn.cat.developer','Developer'],['custom','cn.cat.custom','Custom']];
async function api(u,o={}){const r=await fetch(u,{credentials:'same-origin',...o,headers:{'Content-Type':'application/json','X-CSRF':D?D.csrf:'',...(o.headers||{})}});let j={};try{j=await r.json()}catch(e){}if(!r.ok)throw new Error(j.error||T('cn.err','Something went wrong'));return j}
function toast(m){const e=$('#toast');e.textContent=m;e.classList.add('on');clearTimeout(e._t);e._t=setTimeout(()=>e.classList.remove('on'),2600)}
function logo(a){const ini=esc(a.name.replace(/^(Custom |Google )/,'')[0]);const ic={mcp:'⚡',webhook:'↯',custom:'⚙'}[a.id];
 if(a.logo)return `<div class="lg${a.logo.endsWith('/ffffff')?' dk':''}"><img src="${a.logo}" alt="" loading=lazy onerror="this.parentNode.classList.add('dk');this.parentNode.textContent='${ini}'"></div>`;
 return `<div class="lg dk">${ic||ini}</div>`}
function btn(a){const s=D.status[a.id];if(a.method==='oauth'&&!s.ready&&!s.added)return `<button class="add need">${T('cn.setup','Admin setup needed')}</button>`;
 return s.added?`<button class="add done">${T('cn.added','Added')}</button>`:`<button class=add>${T('cn.add','Add')}</button>`}
function row(a){const s=D.status[a.id];return `<div class=row data-id="${a.id}">${logo(a)}<div class=mid><div class=nm>${esc(a.name)}</div><div class=ds>${esc(T('cn.d.'+a.id,a.desc))}</div>${s.accounts&&s.accounts.length?`<div class=tags>${s.accounts.slice(0,3).map(x=>`<span>${esc(x)}</span>`).join('')}</div>`:''}</div>${btn(a)}</div>`}
function render(){const q=$('#q').value.trim().toLowerCase();let html='';
 const match=a=>!q||(a.name+' '+a.desc+' '+a.cat).toLowerCase().includes(q);
 const cats=VIEW?CATS.filter(c=>c[0]===VIEW):CAT?CATS.filter(c=>c[0]===CAT):CATS;
 for(const [c,k,f] of cats){let items=D.apps.filter(a=>(c==='featured'?a.featured:a.cat===c)&&match(a));if(q&&c==='featured')continue;if(!items.length)continue;
  const full=VIEW===c;if(!full&&!CAT&&items.length>5)items=items.slice(0,5);
  html+=`<div class=sec><div class=sec-h><span>${T(k,f)}</span>${VIEW?`<button data-back=1>← ${T('cn.back','Back')}</button>`:`<button data-view="${c}">${T('cn.viewall','View all')}</button>`}</div>${items.map(row).join('')}</div>`}
 $('#list').innerHTML=html||`<p class=note style="text-align:center;margin-top:40px">${T('cn.none','No apps found')}</p>`;
 const inst=D.apps.filter(a=>D.status[a.id].added);$('#ninst').textContent=inst.length+' '+T('cn.installed','installed');
 $('#stack').innerHTML=(inst.length?inst:D.apps.filter(a=>a.featured)).slice(0,3).map(a=>a.logo?`<img src="${a.logo}" alt=""${a.logo.endsWith('/ffffff')?' style="background:#183054"':''}>`:`<i style="background:#183054;display:grid;place-items:center;font-style:normal;font-size:13px">${{mcp:'⚡',webhook:'↯'}[a.id]||'⚙'}</i>`).join('')}
$('#list').onclick=e=>{const v=e.target.closest('[data-view]');if(v){VIEW=v.dataset.view;render();scrollTo({top:0,behavior:'smooth'});return}
 if(e.target.closest('[data-back]')){VIEW=null;render();return}const r=e.target.closest('.row');if(r)open(r.dataset.id)};
$('#q').oninput=render;$('#pill').onclick=()=>{$('#q').value='';VIEW=null;CAT=null;const ins=D.apps.filter(a=>D.status[a.id].added);toast(ins.map(a=>a.name).join(', ')||T('cn.none_inst','Nothing connected yet'))};
$('#flt').onclick=()=>{const c=$('#chips');const on=c.style.display==='none';c.style.display=on?'flex':'none';$('#flt').classList.toggle('on',on);
 c.innerHTML=[['',T('cn.all','All')],...CATS.slice(1).map(x=>[x[0],T(x[1],x[2])])].map(([k,n])=>`<button data-c="${k}" class="${(CAT||'')===k?'on':''}">${esc(n)}</button>`).join('');
 c.onclick=e=>{const b=e.target.closest('[data-c]');if(!b)return;CAT=b.dataset.c||null;VIEW=null;c.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x===b));render()}};
function closeSheet(){$('#sheet').classList.remove('on');$('#sheetbg').classList.remove('on')}
$('#sheetbg').onclick=closeSheet;
async function reload(id){D=await api('/bb/api/conn');render();if(id)open(id)}
function open(id){const a=D.apps.find(x=>x.id===id),s=D.status[id];let b='';
 const head=`<div class=grab></div><div class=sh-h>${logo(a)}<div><h2>${esc(a.name)}</h2><div class=note>${esc(T('cn.d.'+a.id,a.desc))}</div></div></div>`;
 if(a.method==='key'){
  b+=(s.keys||[]).map(k=>`<div class=item><span>🔑 ${esc(k.label||a.name)} · <code>${esc(k.hint)}</code></span><button class="btn dan" data-delkey="${k.id}">${T('cn.remove','Remove')}</button></div>`).join('');
  b+=`<label>${T('cn.apikey','API key')}</label><input id=k type=password autocomplete=off placeholder="${T('cn.paste','Paste key')}"><label>${T('cn.label','Label (optional)')}</label><input id=kl maxlength=60>`;
  if(a.id==='custom')b+=`<label>Base URL (https, OpenAI-compatible)</label><input id=kb placeholder="https://api.example.com/v1"><label>${T('cn.models','Model names (comma separated)')}</label><input id=km>`;
  if(a.models.length)b+=`<p class=note>${T('cn.modelsavail','Models you can pick in chat')}: ${a.models.map(esc).join(', ')}</p>`;
  if(a.id==='openrouter')b+=`<p class=note><span class=gold>★</span> ${T('cn.open','Includes open, less-filtered models (Dolphin, Hermes). Illegal or harmful content is still blocked.')}</p>`;
  b+=`<button class="btn w" id=save>${T('cn.savekey','Save key')}</button><p class=note>${T('cn.keynote','Encrypted on the server; only the last 4 characters are ever shown. Also listed in Studio → My API keys.')}</p>`}
 else if(a.method==='oauth'){
  if(s.added)b+=`<div class=item><span>✓ ${esc(s.accounts[0])}</span><button class="btn dan" id=disc>${T('cn.disconnect','Disconnect')}</button></div>`;
  else if(s.ready)b+=`<a class="btn w" href="/bb/conn/oauth/${a.id}/start">${T('cn.signin','Sign in & connect')}</a>`;
  else b+=`<p>${T('cn.setupmsg','The owner has to add OAuth client details once before anyone can connect this app.')}</p>`;
  if(D.owner){const cl={gmail:'google',gdrive:'google',gcal:'google',github:'github',notion:'notion'}[a.id],ad=D.admin[cl];
   b+=`<hr style="border-color:var(--bd);margin:18px 0 6px"><p class=note>👑 ${T('cn.ownersetup','Owner setup')} (${cl}) — redirect URI: <code>${esc(D.redirect_base+a.id+'/callback')}</code></p>
   <label>Client ID</label><input id=cid value="${esc(ad.id)}"><label>Client secret ${ad.secret_set?'(✓ saved)':''}</label><input id=cs type=password autocomplete=off placeholder="${ad.secret_set?'••••••':''}"><button class="btn gh w" id=saveadm data-cl="${cl}">${T('cn.saveadmin','Save OAuth client')}</button>`}}
 else if(a.method==='telegram'){
  b+=`<p>${s.running?'🟢 '+T('cn.tgon','Bot is running')+(s.bot?' · @'+esc(s.bot):''):'⚪ '+T('cn.tgoff','Bot is not running yet')}</p>`;
  if(s.running)b+=s.linked?`<div class=item><span>✓ ${esc(s.accounts[0]||'linked')}</span><button class="btn dan" id=tgun>${T('cn.disconnect','Disconnect')}</button></div>`:`<button class="btn w" id=tglink>${T('cn.tglink','Link my Telegram')}</button><p id=tgcode></p>`;
  if(D.owner)b+=`<label>👑 ${T('cn.tgtoken','Bot token from @BotFather')}</label><input id=tgt type=password autocomplete=off placeholder="123456789:AA…"><button class="btn gh w" id=tgsave>${s.has_token?T('cn.replace','Replace token'):T('cn.savetoken','Save token & start bot')}</button>`}
 else if(a.method==='mcp'){
  b+=(s.servers||[]).map(m=>`<div class=item><span><b>${esc(m.name)}</b>${m.auth?' 🔒':''}<br><code>${esc(m.url)}</code><br><span class=note>${m.tools.length} tools: ${esc(m.tools.slice(0,8).join(', '))}</span></span><span><button class="btn gh" data-ref="${m.id}">↻</button> <button class="btn dan" data-delmcp="${m.id}">✕</button></span></div>`).join('');
  b+=`<label>${T('cn.mcpurl','Server URL (https)')}</label><input id=mu placeholder="https://example.com/mcp"><label>${T('cn.name','Name (optional)')}</label><input id=mn maxlength=40><label>${T('cn.mcptok','Auth token (optional)')}</label><input id=mt type=password autocomplete=off><button class="btn w" id=mcpadd>${T('cn.connect','Connect')}</button><p class=note>${T('cn.mcpnote','The agent can use these tools in tasks. Only public https servers are allowed.')}</p>`}
 else if(a.method==='webhook'){
  b+=(s.hooks||[]).map(h=>`<div class=item><span>${h.dir==='in'?'⬇ '+T('cn.incoming','Incoming'):'⬆ '+T('cn.outgoing','Outgoing')}<br><code>${esc(h.url)}</code>${h.dir==='in'?`<br><span class=note>${h.events.length} events</span>`:''}</span><span>${h.dir==='out'?`<button class="btn gh" data-test="${h.id}">Test</button> `:''}<button class="btn dan" data-delhook="${h.id}">✕</button></span></div>`).join('');
  b+=`<button class="btn gh w" id=hin>+ ${T('cn.newin','New incoming webhook URL')}</button><label>${T('cn.outurl','Outgoing URL (https)')}</label><input id=hu placeholder="https://hooks.example.com/…"><button class="btn w" id=hout>+ ${T('cn.addout','Add outgoing webhook')}</button>`}
 const sh=$('#sheet');sh.innerHTML=head+b;sh.classList.add('on');$('#sheetbg').classList.add('on');
 const go=async(f,msg)=>{try{await f();toast(msg||'✓');await reload(id)}catch(e){toast(e.message)}};const on=(sel,f)=>{const e=sh.querySelector(sel);if(e)e.onclick=f};
 on('#save',()=>go(()=>api('/bb/api/conn/key',{method:'POST',body:JSON.stringify({provider:id,key:$('#k').value,label:$('#kl').value,base_url:($('#kb')||{}).value,models:{chat:(($('#km')||{}).value||'').split(',').map(x=>x.trim()).filter(Boolean)}})}),T('cn.saved','Saved')));
 sh.querySelectorAll('[data-delkey]').forEach(x=>x.onclick=()=>confirm(T('cn.sure','Remove?'))&&go(()=>api('/bb/api/conn/key/'+x.dataset.delkey,{method:'DELETE'})));
 on('#disc',()=>go(()=>api('/bb/api/conn/oauth/'+id,{method:'DELETE'})));
 on('#saveadm',e=>go(()=>api('/bb/api/conn/admin',{method:'POST',body:JSON.stringify({client:e.target.dataset.cl,id:$('#cid').value,secret:$('#cs').value})})));
 on('#tgsave',()=>go(()=>api('/bb/api/conn/telegram',{method:'POST',body:JSON.stringify({token:$('#tgt').value})}),T('cn.tgstarted','Saved — bot starting')));
 on('#tgun',()=>go(()=>api('/bb/api/tg/unlink',{method:'POST'})));
 on('#tglink',async()=>{try{const j=await api('/bb/api/tg/code',{method:'POST'});$('#tgcode').innerHTML=`${T('cn.tgsend','Send this to the bot')}: <b class=gold>/link ${esc(j.code)}</b>`+(j.bot?` → <a style="color:#8fc0ff" href="https://t.me/${esc(j.bot)}" target=_blank>@${esc(j.bot)}</a>`:'')}catch(e){toast(e.message)}});
 on('#mcpadd',()=>{const b=$('#mcpadd');b.disabled=true;b.textContent='…';go(()=>api('/bb/api/conn/mcp',{method:'POST',body:JSON.stringify({url:$('#mu').value,name:$('#mn').value,token:$('#mt').value})}),T('cn.connected','Connected'))});
 sh.querySelectorAll('[data-ref]').forEach(x=>x.onclick=()=>go(()=>api('/bb/api/conn/mcp/'+x.dataset.ref+'/refresh',{method:'POST'})));
 sh.querySelectorAll('[data-delmcp]').forEach(x=>x.onclick=()=>go(()=>api('/bb/api/conn/mcp/'+x.dataset.delmcp,{method:'DELETE'})));
 on('#hin',()=>go(()=>api('/bb/api/conn/hook',{method:'POST',body:JSON.stringify({dir:'in'})})));
 on('#hout',()=>go(()=>api('/bb/api/conn/hook',{method:'POST',body:JSON.stringify({dir:'out',url:$('#hu').value})})));
 sh.querySelectorAll('[data-test]').forEach(x=>x.onclick=async()=>{try{const j=await api('/bb/api/conn/hook/'+x.dataset.test+'/test',{method:'POST'});toast('HTTP '+j.status)}catch(e){toast(e.message)}});
 sh.querySelectorAll('[data-delhook]').forEach(x=>x.onclick=()=>go(()=>api('/bb/api/conn/hook/'+x.dataset.delhook,{method:'DELETE'})))}
(async()=>{window.BB_APP=1;try{await window.bbI18nReady}catch(e){}D=await api('/bb/api/conn').catch(e=>{location.href='/login'});render();
 const p=new URLSearchParams(location.search);if(p.get('ok'))toast('✓ '+p.get('ok'));if(p.get('e'))toast(T('cn.oaerr','Could not connect')+' ('+p.get('e')+')');
 if(location.hash.length>1&&D.status[location.hash.slice(1)])open(location.hash.slice(1));
 document.addEventListener('bb:lang',render)})();
