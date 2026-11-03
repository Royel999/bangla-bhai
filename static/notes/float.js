/* Floating Royal Notebook bubble (v4 + any page). Draggable; quick note + clipboard. Web can read clipboard only on user action / focus with permission. */
(()=>{'use strict';if(window.__rbtFloat)return;window.__rbtFloat=1;
const H={'Content-Type':'application/json','x-bb-notes':'1'},esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const dev=(/Android/i.test(navigator.userAgent)?'Android':/iPhone|iPad/i.test(navigator.userAgent)?'iPhone':/Windows/i.test(navigator.userAgent)?'Windows':'Web')+' ব্রাউজার';
const api=(u,o={})=>fetch(u,{credentials:'same-origin',...o,headers:{...H,...(o.headers||{})}}).then(async r=>{const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.error||r.status);return j});
const send=(content,kind='text')=>content&&content.trim()&&localStorage.rbtClipPause!=='1'?api('/bb/api/clips',{method:'POST',body:JSON.stringify({content,kind,device:dev})}).catch(()=>{}):Promise.resolve();
const st=document.createElement('style');st.textContent=`#rbtF{position:fixed;z-index:99999;width:96px;height:96px;cursor:grab;filter:drop-shadow(0 3px 3px #0004);touch-action:none;user-select:none;-webkit-user-select:none}
#rbtF img{width:96px;height:96px;display:block;pointer-events:none;-webkit-user-drag:none}#rbtF b{position:absolute;left:4px;top:2px;font-size:11px}
#rbtP{position:fixed;z-index:99999;width:min(340px,92vw);max-height:70vh;overflow:auto;background:#11264a;color:#eef2fb;border:1px solid #d4af37;border-radius:16px;padding:12px;box-shadow:0 10px 30px #0008;font:14px/1.5 "Noto Sans Bengali",system-ui,sans-serif}
#rbtP textarea{width:100%;height:90px;background:#172f5a;color:inherit;border:1px solid #24406f;border-radius:10px;padding:8px;font:inherit;box-sizing:border-box}
#rbtP button{background:#172f5a;color:inherit;border:1px solid #24406f;border-radius:9px;padding:5px 9px;margin:3px 2px;cursor:pointer;font:inherit}#rbtP .g{background:#ff8c1a;border:0;color:#fff}
#rbtP .c{font-size:12px;padding:6px;border-radius:8px;background:#0b1a33;margin:4px 0;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}#rbtP small{color:#9fb0cf}`;document.head.appendChild(st);
const b=document.createElement('div');b.id='rbtF';b.title='রয়েল নোটবুক · ক্লিক = নোট · টেনে বসান = পিন · ডাবল-ক্লিক = উড়ে যাও';b.innerHTML='<img alt=""><b></b>';document.body.appendChild(b);
/* realistic doyel (oriental magpie-robin): flies → lands on page bottom / tops of elements → idle fidgets → takes off. Speed follows internet speed. */
const D='/bb/static/notes/doyel/',SZ=96,FOOT=93,im=b.querySelector('img'),badge=b.querySelector('b'),cache={};
const POSES=['fly0','fly1','fly2','fly3','fly4','fly5','fly6','fly7','glide0','perch0','cock0','cock1','look0','preen0','sing0','down0','hop0','hop1'];
POSES.forEach(p=>['','_L'].forEach(s=>{const i=new Image();i.src=D+p+s+'.png';cache[p+s]=i.src}));
let face=-1,pose='perch0';const show=p=>{pose=p;const k=p+(face<0?'_L':'');if(im.dataset.k!==k){im.dataset.k=k;im.src=cache[k]}};
const pos=JSON.parse(localStorage.rbtFpos||'null')||{x:innerWidth-110,y:innerHeight-FOOT-4};
const clampP=()=>{pos.x=Math.max(0,Math.min(innerWidth-SZ,pos.x));pos.y=Math.max(-10,Math.min(innerHeight-FOOT,pos.y))};
const place=(bob=0)=>{b.style.left=pos.x+'px';b.style.top=(pos.y+bob)+'px'};clampP();place();addEventListener('resize',()=>{clampP();place()});
/* internet speed → flight speed (Network Information API + a timed small fetch every 60s); offline → stays perched */
let net=1,mbps=0;const probe=async()=>{if(!navigator.onLine){net=null;return}try{const t=performance.now(),r=await fetch(D+'fly0.png?p='+Date.now(),{cache:'no-store'}),n=(await r.arrayBuffer()).byteLength,dt=(performance.now()-t)/1000;
 let m=n*8/Math.max(dt,.02)/1e6;const dl=navigator.connection&&navigator.connection.downlink;if(dl)m=(m+dl)/2;mbps=m;net=Math.max(.35,Math.min(2.6,.4+.5*Math.log2(1+m)))}catch(e){net=null}};
probe();setInterval(probe,60000);addEventListener('offline',()=>net=null);addEventListener('online',probe);navigator.connection&&navigator.connection.addEventListener&&navigator.connection.addEventListener('change',probe);
const roamOn=()=>localStorage.rbtRoam!=='0';
let state=localStorage.rbtPin==='1'?'pinned':'perch',until=performance.now()+3000,tgt=null,perchEl=null,perchOff=0,nextF=0,wing=0,glide=0,lt=0,hov=false,hold=0;
function spots(){const s=[{x:Math.random()*(innerWidth-SZ),y:innerHeight,el:null}];
 document.querySelectorAll('h1,h2,h3,img,button,textarea,table,section,article,header,nav,aside,.card,[class*=card]').forEach(e=>{if(s.length>40||e.closest('#rbtF,#rbtP'))return;const r=e.getBoundingClientRect();
  if(r.width>110&&r.top>70&&r.top<innerHeight-30&&getComputedStyle(e).visibility!=='hidden'){const el=document.elementFromPoint(r.left+r.width/2,r.top+2);if(el&&(el===e||e.contains(el)))s.push({x:r.left+20+Math.random()*(r.width-40)-SZ/2,y:r.top,el:e})}});return s}
function pick(perch){if(perch){const s=spots(),c=s.length>1&&Math.random()<.75?s[1+Math.floor(Math.random()*(s.length-1))]:s[0];perchEl=c.el;tgt={x:Math.max(0,Math.min(innerWidth-SZ,c.x)),y:c.y-FOOT,perch:1};if(c.el)perchOff=tgt.x-c.el.getBoundingClientRect().left}
 else{perchEl=null;tgt={x:Math.random()*(innerWidth-SZ),y:Math.random()*(innerHeight*.7),perch:0}}}
function fidget(t){const r=Math.random();let p='perch0',d=700+Math.random()*1900;
 if(r<.08){face=-face}else if(r<.28)p=Math.random()<.6?'cock0':'cock1';else if(r<.42)p='look0';else if(r<.52){p='preen0';d+=1200}else if(r<.58)p='sing0';else if(r<.68)p='down0';
 else if(r<.76){show('hop0');setTimeout(()=>{show('hop1');pos.y-=8;place()},150);setTimeout(()=>{pos.y+=8;pos.x+=12*face;clampP();place();show('perch0')},400);nextF=t+1500+Math.random()*1000;return}
 show(p);nextF=t+d}
function roam(t){const dt=Math.min(50,t-(lt||t));lt=t;const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
 if(drag||document.hidden){}else if(state!=='fly'){if(t>nextF)fidget(t);
  if(state==='perch'&&perchEl){const r=perchEl.getBoundingClientRect();if(r.top<0||r.top>innerHeight||!r.width){until=0}else{pos.x=r.left+perchOff;pos.y=r.top-FOOT;place()}}
  if(state==='perch'&&t>until&&roamOn()&&net!==null&&!P&&!reduce&&!hov){pick(Math.random()<.3);state='fly';until=t+14000+Math.random()*24000}}
 else{ if(hov&&!tgt.perch||P){wing=(wing+1)%8;show('fly'+wing)}else{
  if((net===null||!roamOn()||t>until||reduce)&&!tgt.perch)pick(true);
  const sp=(+localStorage.rbtRoamSp||1)*.13*(net||.6)*(tgt.perch?1.25:1)*dt,dx=tgt.x-pos.x,dy=tgt.y-pos.y,d=Math.hypot(dx,dy);
  if(d<sp+1){pos.x=tgt.x;pos.y=tgt.y;place();if(tgt.perch){state='perch';until=t+5000+Math.random()*9000;nextF=0;show('perch0')}else pick(false)}
  else{if(Math.abs(dx)>2)face=dx>0?1:-1;pos.x+=dx/d*sp;pos.y+=dy/d*sp;
   if(glide>0){glide--;show('glide0')}else if(t-(roam.f||0)>Math.max(30,55/Math.sqrt(net||.6))){roam.f=t;wing=(wing+1)%8;show('fly'+wing);if(wing===2&&dy>-.3*Math.abs(dx)&&d>300&&Math.random()<.3)glide=20+Math.random()*30}
   place(glide?0:3*Math.sin(t/60))}}}
 badge.textContent=state==='pinned'?'📌':'';requestAnimationFrame(roam)}
requestAnimationFrame(roam);
const pin=on=>{if(on){state='pinned';perchEl=null;localStorage.rbtPin='1';localStorage.rbtFpos=JSON.stringify(pos);nextF=0}else{localStorage.rbtPin='0';pick(false);state='fly';until=performance.now()+20000}};
let drag=null,moved=false,clickT=0;b.addEventListener('pointerdown',e=>{e.preventDefault();drag={dx:e.clientX-pos.x,dy:e.clientY-pos.y};moved=false;b.setPointerCapture(e.pointerId)});
b.addEventListener('pointermove',e=>{if(!drag)return;const nx=e.clientX-drag.dx,ny=e.clientY-drag.dy;if(Math.abs(nx-pos.x)+Math.abs(ny-pos.y)>3){moved=true;show('fly0')}pos.x=nx;pos.y=ny;clampP();place()});
b.addEventListener('pointerup',()=>{if(!drag)return;drag=null;if(moved)pin(true);else{clearTimeout(clickT);clickT=setTimeout(toggle,280)}});
b.addEventListener('dblclick',e=>{e.preventDefault();clearTimeout(clickT);if(P)toggle();if(state==='pinned')pin(false);else toggle()});
b.addEventListener('pointerenter',()=>hov=true);b.addEventListener('pointerleave',()=>hov=false);
let P=null;
async function toggle(){if(P){P.remove();P=null;return}P=document.createElement('div');P.id='rbtP';document.body.appendChild(P);
 P.style.left=Math.max(6,Math.min(innerWidth-350,pos.x-260))+'px';P.style.top=(pos.y>innerHeight/2?Math.max(6,pos.y-400):pos.y+96)+'px';
 P.innerHTML=`<b>📒 দ্রুত নোট</b><textarea id="rbtQ" placeholder="এখানে লিখুন…"></textarea><div><button class=g id="rbtS">💾 রাখুন</button><button id="rbtV">📋 পেস্ট করে রাখুন</button><button onclick="location.href='/notes/'">📖 নোটবুক</button><button onclick="location.href='/notes/?view=clips'">🗂 ক্লিপবোর্ড</button></div>
 <div style="margin-top:6px"><small>সাম্প্রতিক কপি (৩০ দিন রাখা হয়) · <a id="rbtFly" style="color:#d4af37;cursor:pointer">${state==='pinned'?'🕊 উড়ে যাও':'🪵 কোথাও বসো'}</a> · <a id="rbtRo" style="color:#d4af37;cursor:pointer">${localStorage.rbtRoam==='0'?'🌀 ঘোরান':'🌀 ঘোরা থামান'}</a> · <a id="rbtSp" style="color:#d4af37;cursor:pointer">⚡ নেট ${net===null?'অফলাইন':mbps.toFixed(1)+' Mbps'} · গতি ${({'0.5':'ধীর','1':'মাঝারি','2':'দ্রুত'})[localStorage.rbtRoamSp||'1']}</a> · <a id="rbtPa" style="color:#d4af37;cursor:pointer">${localStorage.rbtClipPause==='1'?'▶ চালু করুন':'⏸ থামান'}</a></small><div id="rbtC"><small>লোড হচ্ছে…</small></div></div>`;
 P.querySelector('#rbtQ').focus();
 P.querySelector('#rbtS').onclick=async()=>{const t=P.querySelector('#rbtQ').value;if(!t.trim())return;try{await api('/bb/api/notes',{method:'POST',body:JSON.stringify({title:t.trim().split('\n')[0].slice(0,60),body:t,folder:'দ্রুত নোট'})});P.querySelector('#rbtQ').value='';P.querySelector('#rbtS').textContent='✓ রাখা হয়েছে'}catch(e){alert(e.message)}};
 P.querySelector('#rbtV').onclick=async()=>{try{const t=await navigator.clipboard.readText();if(!t)return;await send(t);load()}catch(e){alert('ব্রাউজার ক্লিপবোর্ড পড়ার অনুমতি দেয়নি। লেখার বাক্সে চেপে ধরে Paste করুন।')}};
 P.querySelector('#rbtFly').onclick=()=>{if(state==='pinned')pin(false);else{pick(true);state='fly'}toggle()};
 P.querySelector('#rbtRo').onclick=()=>{localStorage.rbtRoam=localStorage.rbtRoam==='0'?'1':'0';toggle();toggle()};
 P.querySelector('#rbtSp').onclick=()=>{localStorage.rbtRoamSp={'0.5':'1','1':'2','2':'0.5'}[localStorage.rbtRoamSp||'1'];toggle();toggle()};
 P.querySelector('#rbtPa').onclick=()=>{localStorage.rbtClipPause=localStorage.rbtClipPause==='1'?'0':'1';toggle();toggle()};
 load()}
async function load(){if(!P)return;try{const j=await api('/bb/api/clips?limit=6');P.querySelector('#rbtC').innerHTML=j.clips.map(c=>`<div class=c data-t="${esc(c.kind==='image'?'':c.content.slice(0,2000))}" title="কপি করুন">${c.kind==='image'?'🖼 ছবি':esc(c.content.slice(0,90))}</div>`).join('')||'<small>এখনো কিছু নেই</small>';
 P.querySelectorAll('.c').forEach(e=>e.onclick=()=>{navigator.clipboard?.writeText(e.dataset.t);e.style.outline='1px solid #d4af37'})}catch(e){P.querySelector('#rbtC').innerHTML='<small>লগইন দরকার</small>'}}
/* in-page copies are always visible to us */
document.addEventListener('copy',()=>{const s=String(getSelection()||'');if(s.length>1)setTimeout(()=>send(s),50)});
/* on focus: read only if the user already granted clipboard-read (Chrome); never prompts silently */
let last='';addEventListener('focus',async()=>{try{const p=await navigator.permissions.query({name:'clipboard-read'});if(p.state!=='granted')return;const t=await navigator.clipboard.readText();if(t&&t!==last){last=t;send(t)}}catch(e){}});
})();
