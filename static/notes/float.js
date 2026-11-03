/* Floating Royal Notebook bubble (v4 + any page). Draggable; quick note + clipboard. Web can read clipboard only on user action / focus with permission. */
(()=>{'use strict';if(window.__rbtFloat)return;window.__rbtFloat=1;
const H={'Content-Type':'application/json','x-bb-notes':'1'},esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const dev=(/Android/i.test(navigator.userAgent)?'Android':/iPhone|iPad/i.test(navigator.userAgent)?'iPhone':/Windows/i.test(navigator.userAgent)?'Windows':'Web')+' ব্রাউজার';
const api=(u,o={})=>fetch(u,{credentials:'same-origin',...o,headers:{...H,...(o.headers||{})}}).then(async r=>{const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.error||r.status);return j});
const send=(content,kind='text')=>content&&content.trim()&&localStorage.rbtClipPause!=='1'?api('/bb/api/clips',{method:'POST',body:JSON.stringify({content,kind,device:dev})}).catch(()=>{}):Promise.resolve();
const st=document.createElement('style');st.textContent=`#rbtF{position:fixed;z-index:99999;width:54px;height:54px;cursor:grab;filter:drop-shadow(0 4px 6px #0005);touch-action:none;user-select:none}
#rbtF i{display:block;width:64px;height:64px;margin:-5px;background:url(/bb/static/notes/bird.png?v=1) 0 0/384px 64px no-repeat;animation:rbtFlap .5s steps(6) infinite}#rbtF.l i{transform:scaleX(-1)}#rbtF.rest i{animation-duration:1.4s}
@keyframes rbtFlap{to{background-position:-384px 0}}
#rbtP{position:fixed;z-index:99999;width:min(340px,92vw);max-height:70vh;overflow:auto;background:#11264a;color:#eef2fb;border:1px solid #d4af37;border-radius:16px;padding:12px;box-shadow:0 10px 30px #0008;font:14px/1.5 "Noto Sans Bengali",system-ui,sans-serif}
#rbtP textarea{width:100%;height:90px;background:#172f5a;color:inherit;border:1px solid #24406f;border-radius:10px;padding:8px;font:inherit;box-sizing:border-box}
#rbtP button{background:#172f5a;color:inherit;border:1px solid #24406f;border-radius:9px;padding:5px 9px;margin:3px 2px;cursor:pointer;font:inherit}#rbtP .g{background:#ff8c1a;border:0;color:#fff}
#rbtP .c{font-size:12px;padding:6px;border-radius:8px;background:#0b1a33;margin:4px 0;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}#rbtP small{color:#9fb0cf}`;document.head.appendChild(st);
const b=document.createElement('div');b.id='rbtF';b.title='রয়েল নোটবুক';b.innerHTML='<i></i>';document.body.appendChild(b);
const pos=JSON.parse(localStorage.rbtFpos||'null')||{x:innerWidth-70,y:innerHeight-150};const place=()=>{pos.x=Math.max(4,Math.min(innerWidth-58,pos.x));pos.y=Math.max(4,Math.min(innerHeight-58,pos.y));b.style.left=pos.x+'px';b.style.top=pos.y+'px'};place();addEventListener('resize',place);
let drag=null,moved=false;b.addEventListener('pointerdown',e=>{drag={dx:e.clientX-pos.x,dy:e.clientY-pos.y};moved=false;b.setPointerCapture(e.pointerId)});
b.addEventListener('pointermove',e=>{if(!drag)return;const nx=e.clientX-drag.dx,ny=e.clientY-drag.dy;if(Math.abs(nx-pos.x)+Math.abs(ny-pos.y)>3)moved=true;pos.x=nx;pos.y=ny;place()});
b.addEventListener('pointerup',()=>{drag=null;hold=performance.now()+4000;localStorage.rbtFpos=JSON.stringify(pos);if(!moved)toggle()});
/* roaming: wanders the whole viewport, bounces at edges; stops on hover/touch/drag or while panel is open. Toggle via panel link. */
let hold=0,hov=false,ang=Math.random()*6.28,vx=Math.cos(ang),vy=Math.sin(ang),lt=0;const roamOn=()=>localStorage.rbtRoam!=='0';
b.addEventListener('pointerenter',()=>hov=true);b.addEventListener('pointerleave',()=>{hov=false;hold=performance.now()+800});b.addEventListener('touchstart',()=>hold=performance.now()+5000,{passive:true});
b.style.transition='box-shadow .3s';
function roam(t){const dt=Math.min(50,t-(lt||t));lt=t;const sp=(+localStorage.rbtRoamSp||1)*0.09;
 if(roamOn()&&!drag&&!hov&&!P&&t>hold&&!document.hidden&&!matchMedia('(prefers-reduced-motion: reduce)').matches){
  pos.x+=vx*sp*dt;pos.y+=vy*sp*dt;const W=innerWidth-58,H=innerHeight-58;
  if(pos.x<4){pos.x=4;vx=Math.abs(vx)}if(pos.x>W){pos.x=W;vx=-Math.abs(vx)}if(pos.y<4){pos.y=4;vy=Math.abs(vy)}if(pos.y>H){pos.y=H;vy=-Math.abs(vy)}
  if(Math.random()<0.01){ang=Math.atan2(vy,vx)+(Math.random()-.5)*1.2;vx=Math.cos(ang);vy=Math.sin(ang)}
  b.style.left=pos.x+'px';b.style.top=(pos.y+5*Math.sin(t/350))+'px';b.classList.toggle('l',vx<0);b.classList.remove('rest')}else b.classList.add('rest');
 requestAnimationFrame(roam)}
requestAnimationFrame(roam);
let P=null;
async function toggle(){if(P){P.remove();P=null;return}P=document.createElement('div');P.id='rbtP';document.body.appendChild(P);
 P.style.left=Math.max(6,Math.min(innerWidth-350,pos.x-290))+'px';P.style.top=(pos.y>innerHeight/2?Math.max(6,pos.y-420):pos.y+62)+'px';
 P.innerHTML=`<b>📒 দ্রুত নোট</b><textarea id="rbtQ" placeholder="এখানে লিখুন…"></textarea><div><button class=g id="rbtS">💾 রাখুন</button><button id="rbtV">📋 পেস্ট করে রাখুন</button><button onclick="location.href='/notes/'">📖 নোটবুক</button><button onclick="location.href='/notes/?view=clips'">🗂 ক্লিপবোর্ড</button></div>
 <div style="margin-top:6px"><small>সাম্প্রতিক কপি (৩০ দিন রাখা হয়) · <a id="rbtRo" style="color:#d4af37;cursor:pointer">${localStorage.rbtRoam==='0'?'🌀 ঘোরান':'🌀 ঘোরা থামান'}</a> · <a id="rbtSp" style="color:#d4af37;cursor:pointer">⚡ গতি ${({'0.5':'ধীর','1':'মাঝারি','2':'দ্রুত'})[localStorage.rbtRoamSp||'1']}</a> · <a id="rbtPa" style="color:#d4af37;cursor:pointer">${localStorage.rbtClipPause==='1'?'▶ চালু করুন':'⏸ থামান'}</a></small><div id="rbtC"><small>লোড হচ্ছে…</small></div></div>`;
 P.querySelector('#rbtQ').focus();
 P.querySelector('#rbtS').onclick=async()=>{const t=P.querySelector('#rbtQ').value;if(!t.trim())return;try{await api('/bb/api/notes',{method:'POST',body:JSON.stringify({title:t.trim().split('\n')[0].slice(0,60),body:t,folder:'দ্রুত নোট'})});P.querySelector('#rbtQ').value='';P.querySelector('#rbtS').textContent='✓ রাখা হয়েছে'}catch(e){alert(e.message)}};
 P.querySelector('#rbtV').onclick=async()=>{try{const t=await navigator.clipboard.readText();if(!t)return;await send(t);load()}catch(e){alert('ব্রাউজার ক্লিপবোর্ড পড়ার অনুমতি দেয়নি। লেখার বাক্সে চেপে ধরে Paste করুন।')}};
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
