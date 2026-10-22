(()=>{const $=s=>document.querySelector(s),E=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const TABS=[['admin','Admin access','অ্যাডমিন অ্যাক্সেস'],['user','User access','ইউজার অ্যাক্সেস'],['apps','Connected apps','সংযুক্ত অ্যাপ ও অ্যাকাউন্ট'],['dir','Directory','ডিরেক্টরি'],['pend','Pending','বাকি কাজ']];
let D=null,cur=location.hash.slice(1)||'admin',VALS=[];
function toast(t){const e=$('#toast');e.textContent=t;e.classList.add('s');setTimeout(()=>e.classList.remove('s'),1300)}
async function copy(t){try{await navigator.clipboard.writeText(t)}catch(e){const a=document.createElement('textarea');a.value=t;document.body.appendChild(a);a.select();document.execCommand('copy');a.remove()}toast('Copied / কপি হয়েছে')}
function field(f){const i=VALS.push(f.v)-1,m=f.s?'•'.repeat(Math.min(16,Math.max(8,String(f.v).length))):E(f.v);
return `<div class="f"><span class="k">${E(f.k)}</span><span class="v" data-i="${i}" data-m="${f.s?1:0}">${m}</span>${f.s?`<button data-r="${i}" title="Reveal">👁</button>`:''}<button data-c="${i}" title="Copy">📋</button></div>`}
function card(e){const fs=(e.fields||[]).slice();if(e.url)fs.unshift({k:'Link / লিংক',v:e.url,s:false});
return `<div class="card ${e.pend?'pend':''}" data-s="${E((e.name+' '+(e.notes||'')+' '+(e.cat||'')).toLowerCase())}"><div class="t">${E(e.name)}${e.url&&/^https?:/.test(e.url)?`<a href="${E(e.url)}" target="_blank" rel="noopener noreferrer">Open ↗</a>`:''}</div>${fs.map(field).join('')}${e.notes?`<div class="n">${E(e.notes)}</div>`:''}</div>`}
function render(){VALS=[];document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('on',b.dataset.t===cur));
const t=TABS.find(x=>x[0]===cur)||TABS[0],sec=(D.pages||{})[t[0]]||[];let h=`<h2>${t[1]}<small>${t[2]}</small></h2>`,g='';
for(const e of sec){if(e.group&&e.group!==g){g=e.group;h+=`<h3>${E(g)}</h3>`}h+=card(e)}
$('#main').innerHTML=h||'<div class=mut>Empty</div>';filter()}
function filter(){const q=$('#search').value.trim().toLowerCase();document.querySelectorAll('.card').forEach(c=>c.style.display=!q||c.dataset.s.includes(q)||c.textContent.toLowerCase().includes(q)?'':'none')}
document.addEventListener('click',ev=>{const b=ev.target.closest('button');if(!b)return;
if(b.dataset.t){cur=b.dataset.t;history.replaceState(null,'','#'+cur);render();scrollTo(0,0)}
else if(b.dataset.c)copy(VALS[+b.dataset.c]);
else if(b.dataset.r){const v=document.querySelector(`.v[data-i="${b.dataset.r}"]`),hid=v.dataset.m==='1';v.textContent=hid?VALS[+b.dataset.r]:'•'.repeat(12);v.dataset.m=hid?'0':'1';b.textContent=hid?'🙈':'👁'}});
$('#search').addEventListener('input',filter);
$('#tabs').innerHTML=TABS.map(t=>`<button data-t="${t[0]}">${t[1]} · ${t[2]}</button>`).join('');
fetch('/notebook/api/data',{headers:{'X-BB-NB':'1'},credentials:'same-origin',cache:'no-store'}).then(async r=>{if(r.status===401){location.href='/admin?next=/notebook';return}
if(!r.ok)throw new Error((await r.json()).error||r.status);D=await r.json();$('#foot').textContent='Updated / আপডেট: '+new Date(D.ts*1000).toLocaleString('en-GB',{timeZone:'Asia/Dhaka'})+' (Dhaka) · v'+D.v;render()})
.catch(e=>$('#main').innerHTML='<div class="card">Error: '+E(e.message)+'</div>')})();
