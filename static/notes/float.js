/* Royal doyel for the web (v4 + any page): a realistic oriental magpie-robin with a behaviour brain.
   Flies, lands on the page bottom / tops of elements, walks along edges, forages (pecks crumbs/insects), drinks, sings (optional soft chirp),
   bathes & shakes, preens, naps at night (Dhaka time), startles when the mouse rushes at it, approaches a still cursor, flies to new copies,
   shows ⚙ while a device AI job runs. Drag & drop = sits there 30–120s then leaves. Click = animated glass panel (panel.html in an iframe). */
(()=>{'use strict';if(window.__rbtFloat||window.top!==window)return;window.__rbtFloat=1;
const H={'Content-Type':'application/json','x-bb-notes':'1'};
const dev=(/Android/i.test(navigator.userAgent)?'Android':/iPhone|iPad/i.test(navigator.userAgent)?'iPhone':/Windows/i.test(navigator.userAgent)?'Windows':'Web')+' ব্রাউজার';
const api=(u,o={})=>fetch(u,{credentials:'same-origin',...o,headers:{...H,...(o.headers||{})}}).then(async r=>{const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.error||r.status);return j});
const send=(content,kind='text')=>content&&content.trim()&&localStorage.rbtClipPause!=='1'?api('/bb/api/clips',{method:'POST',body:JSON.stringify({content,kind,device:dev})}).then(()=>react('clip')).catch(()=>{}):Promise.resolve();
const st=document.createElement('style');st.textContent=`#rbtF{position:fixed;z-index:99999;width:96px;height:96px;cursor:grab;filter:drop-shadow(0 3px 3px #0004);touch-action:none;user-select:none;-webkit-user-select:none;left:0;top:0}
#rbtF img{width:96px;height:96px;display:block;pointer-events:none;-webkit-user-drag:none}#rbtF b{position:absolute;left:2px;top:0;font-size:12px}
#rbtF .pr{position:absolute;pointer-events:none;border-radius:50%;transition:opacity .4s}
#rbtP{position:fixed;z-index:100000;border:0;width:420px;height:640px;max-width:96vw;max-height:88vh;background:transparent;color-scheme:normal}
@media(max-width:600px){#rbtP{left:2vw!important;width:96vw;bottom:8px!important;top:auto!important;height:78vh}}`;document.head.appendChild(st);
const b=document.createElement('div');b.id='rbtF';b.title=(localStorage.rbtMascot!=='doyel'?'মামণি · ক্লিক = প্যানেল · টেনে বসান · ডাবল-ক্লিক = হেঁটে যাও · রাইট-ক্লিক = দোয়েল':'দোয়েল · ক্লিক = প্যানেল · টেনে বসান · ডাবল-ক্লিক = উড়ে যাও · রাইট-ক্লিক = মামণি');b.innerHTML='<img alt=""><b></b>';document.body.appendChild(b);
const GIRL=localStorage.rbtMascot!=='doyel',D=GIRL?'/bb/static/notes/girl2/':'/bb/static/notes/doyel/',SZ=GIRL?({small:90,medium:150,large:225}[localStorage.rbtSize]||225):96,FOOT=GIRL?Math.round(SZ*296/300):93,KZ=SZ/96,im=b.querySelector('img'),badge=b.querySelector('b'),cache={};
b.style.width=b.style.height=im.style.width=im.style.height=SZ+'px';
(GIRL?['stand0','blink0','look0','wave0','wave1','jump0','squat0','sit0','sleep0','carry0','clap0','walk0','walk1','walk2','walk3','walk4','walk5','run0','run1','run2','run3','skip0','climb0','dance0','dance1','read0','chase0','giggle0','think0','peek0','kick0','surprise0','kiss0']:['fly0','fly1','fly2','fly3','fly4','fly5','fly6','fly7','glide0','perch0','cock0','cock1','look0','preen0','sing0','down0','hop0','hop1','walk0','walk1','walk2','peck0','peck1','drink0','sleep0','shake0'])
 .forEach(p=>(GIRL?['']:['','_L']).forEach(s=>{const i=new Image();i.src=D+p+s+'.png';cache[p+s]=i.src}));
let face=-1,pose='perch0';const GA={perch0:'stand0',shake0:'stand0',cock0:'look0',cock1:'look0',down0:'squat0',peck0:'squat0',peck1:'squat0',sing0:'wave0',preen0:'blink0',glide0:'jump0',hop0:'squat0',hop1:'jump0',drink0:'squat0'};
const show=p=>{if(GIRL){p=p.startsWith('fly')?'carry0':GA[p]||p}pose=p;if(GIRL){im.style.transform=face<0?'scaleX(-1)':'';if(im.dataset.k!==p){im.dataset.k=p;im.src=cache[p]}return}const k=p+(face<0?'_L':'');if(im.dataset.k!==k){im.dataset.k=k;im.src=cache[k]}};
const pos=JSON.parse(localStorage.rbtFpos||'null')||{x:innerWidth-110,y:innerHeight-FOOT-4};
const clampP=()=>{pos.x=Math.max(0,Math.min(innerWidth-SZ,pos.x));pos.y=Math.max(-10,Math.min(innerHeight-FOOT,pos.y))};
const place=(bob=0)=>{b.style.transform=`translate(${pos.x}px,${pos.y+bob}px)`};clampP();place();addEventListener('resize',()=>{clampP();place()});
/* props: crumbs / insect / water / splash */
const EM={heart:['♥','#ff4d7d'],music:['♪','#ffd84a'],flower:['🌸',''],ball:['⚽',''],zzz:['z z','#bcd3ff']};
function props(k){b.querySelectorAll('.pr').forEach(e=>e.remove());if(!k)return;if(EM[k]){const e=document.createElement('i');e.className='pr';e.textContent=EM[k][0];Object.assign(e.style,{left:KZ*(k==='flower'||k==='ball'?(face>0?70:6):k==='zzz'?66:30+Math.random()*30)+'px',top:KZ*(k==='flower'||k==='ball'?76:k==='zzz'?46:4)+'px',color:EM[k][1],fontSize:Math.round(14*Math.sqrt(KZ))+'px',fontWeight:'bold',fontStyle:'normal',borderRadius:0});b.appendChild(e);return}const bx=face>0?84:8,add=(x,y,w,h,c)=>{const e=document.createElement('i');e.className='pr';Object.assign(e.style,{left:x+'px',top:y+'px',width:w+'px',height:h+'px',background:c});b.appendChild(e)};
 if(k==='crumbs')for(let i=0;i<4;i++)add(bx+(Math.random()*16-8)*face,89,3,3,['#c8a165','#a0763d','#e0c68f'][i%3]);
 else if(k==='insect'){add(bx,88,6,3,'#3e7d2c')}else if(k==='water')add(bx-8,89,16,5,'#7ec8f0');
 else if(k==='splash')for(let i=0;i<7;i++)add(48+Math.random()*60-30,50+Math.random()*40-20,3,4,'#9bd6f5')}
/* soft synthesized chirp, off by default */
let ac=null;function chirp(){if(localStorage.rbtSound!=='1')return;try{ac=ac||new AudioContext();const t0=ac.currentTime;for(let n=0;n<3;n++){const o=ac.createOscillator(),g=ac.createGain(),t=t0+n*.14,f=2600+Math.random()*800;
 o.frequency.setValueAtTime(f,t);o.frequency.linearRampToValueAtTime(f+1800,t+.09);g.gain.setValueAtTime(0,t);g.gain.linearRampToValueAtTime(.07,t+.03);g.gain.linearRampToValueAtTime(0,t+.09);o.connect(g).connect(ac.destination);o.start(t);o.stop(t+.1)}}catch(e){}}
/* network → speed; offline = stays perched */
let net=1,mbps=0,busy=0;const probe=async()=>{if(!navigator.onLine){net=null;return}try{const t=performance.now(),r=await fetch(D+(GIRL?'stand0':'fly0')+'.png?p='+Date.now(),{cache:'no-store'}),n=(await r.arrayBuffer()).byteLength,dt=(performance.now()-t)/1000;
 let m=n*8/Math.max(dt,.02)/1e6;const dl=navigator.connection&&navigator.connection.downlink;if(dl)m=(m+dl)/2;mbps=m;net=Math.max(.35,Math.min(2.6,.4+.5*Math.log2(1+m)))}catch(e){net=null}};
probe();setInterval(probe,60000);addEventListener('offline',()=>net=null);addEventListener('online',probe);navigator.connection&&navigator.connection.addEventListener&&navigator.connection.addEventListener('change',probe);
const hubT=async()=>{try{busy=(await api('/bb/link/hub')).device.busy?1:0}catch(e){}};hubT();setInterval(hubT,20000);
const roamOn=()=>localStorage.rbtRoam!=='0',sp0=()=>+localStorage.rbtRoamSp||1;
const hourBD=()=>new Date(Date.now()+6*3600e3).getUTCHours();
let state='perch',until=performance.now()+3000,tgt=null,perchEl=null,perchOff=0,edge=null,seq=[],seqT=0,wing=0,glide=0,lt=0,mood=null,follow=false,tFly=performance.now(),tMouse=performance.now(),mp={x:-999,y:-999,t:0},noStartle=0;
function spots(){const s=[{x:Math.random()*(innerWidth-SZ),y:innerHeight,el:null,a:0,b:innerWidth}];
 document.querySelectorAll('h1,h2,h3,img,button,textarea,table,section,article,header,nav,aside,.card,[class*=card]').forEach(e=>{if(s.length>40||e.closest('#rbtF'))return;const r=e.getBoundingClientRect();
  if(r.width>110&&r.top>70&&r.top<innerHeight-30&&getComputedStyle(e).visibility!=='hidden'){const el=document.elementFromPoint(r.left+r.width/2,r.top+2);if(el&&(el===e||e.contains(el)))s.push({x:r.left+20+Math.random()*(r.width-40)-SZ/2,y:r.top,el:e,a:r.left,b:r.right})}});return s}
function pick(perch,near){if(GIRL)perch=true;if(perch){let s=spots();if(near)s=s.sort((p,q)=>Math.hypot(p.x-near.x,p.y-near.y)-Math.hypot(q.x-near.x,q.y-near.y)).slice(0,3);const c=s.length>1&&Math.random()<.75?s[1+Math.floor(Math.random()*(s.length-1))]:s[0];
  perchEl=c.el;tgt={x:Math.max(0,Math.min(innerWidth-SZ,c.x)),y:c.y-FOOT,perch:1};edge={a:c.a-SZ/2+10,b:c.b-SZ/2-10};if(c.el)perchOff=tgt.x-c.el.getBoundingClientRect().left}
 else{perchEl=null;edge=null;tgt=near?{x:near.x-SZ/2,y:near.y-SZ-10,perch:0}:{x:Math.random()*(innerWidth-SZ),y:Math.random()*(innerHeight*.7),perch:0}}}
const go=(s,d)=>{state=s;seq=[];props(null);until=performance.now()+(d!=null?d:s==='fly'?8000+Math.random()*12000:GIRL?2000+Math.random()*4000:4000+Math.random()*6000)};
const SAY={hi:['আব্বু!','আব্বু, দেখো!','হাই!'],play:['খেলবে?','চলো খেলি!','বল খেলবে?'],happy:['হি হি!','ইয়ে!','কী মজা!'],love:['তোমাকে ভালোবাসি!','আব্বু ❤'],read:['গল্প পড়ছি…','এটা কী লেখা?'],type:['কী লিখছো?','আমিও লিখবো!'],click:['ওমা!','কী হলো?'],think:['হুমম…','ভাবছি…'],sleep:['ঘুম পাচ্ছে…']};
let bub=null;function say(k){if(!GIRL)return;const a=SAY[k]||[k],t=a[Math.floor(Math.random()*a.length)];if(!bub){bub=document.createElement('div');Object.assign(bub.style,{position:'fixed',zIndex:100001,background:'#fff',color:'#333',font:'bold 15px sans-serif',padding:'6px 12px',borderRadius:'14px',boxShadow:'0 2px 8px #0004',pointerEvents:'none',transition:'opacity .3s',whiteSpace:'nowrap'});document.body.appendChild(bub)}
 bub.textContent=t;bub.style.opacity=1;bub.style.left=Math.max(4,Math.min(innerWidth-160,pos.x+SZ*.35))+'px';bub.style.top=Math.max(4,pos.y-6)+'px';clearTimeout(say.t);say.t=setTimeout(()=>bub.style.opacity=0,2200)}
function act(k){const R=Math.random,S=[];const P=(p,d,dx=0,pr=null)=>S.push([p,d,dx,pr]);
 if(GIRL&&!['sleep','curious','fly'].includes(k)){k={cock:'blink',preen:'wave',forage:'flower',drink:'ball',sing:R()<.5?'clap':'wave',bathe:'jump',hop:'jump'}[k]||k;
  const D3=3*KZ;if(k==='idle'){P('stand0',800+R()*1500);P('blink0',140);P('stand0',400+R()*1200)}
  else if(k==='run'){if(R()<.5)face=-face;for(let i=0,n=16+R()*24;i<n;i++)P('run'+i%4,80,9*KZ);P('stand0',400)}
  else if(k==='skip'){if(R()<.5)face=-face;for(let i=0,n=6+R()*8;i<n;i++){P('skip0',220,6*KZ);P('walk'+(i%6),120,4*KZ)}P('giggle0',600);P('stand0',300)}
  else if(k==='dance'){if(R()<.4)say('happy');for(let i=0,n=6+R()*8;i<n;i++){P('dance0',300,0,'music');P('dance1',300,0,'music');if(i%3===2)face=-face}P('giggle0',600);P('stand0',300)}
  else if(k==='chase'){for(let i=0,n=10+R()*14;i<n;i++)P(i%5===4?'chase0':'run'+i%4,i%5===4?350:90,i%5===4?0:7*KZ,'flower');P('jump0',350);P('giggle0',700,0,'heart');P('stand0',300)}
  else if(k==='read'){say('read');P('sit0',400);P('read0',4000+R()*5000);P('think0',800);P('read0',3000+R()*3000);P('stand0',400)}
  else if(k==='peek'){P('peek0',2500+R()*2000);P('giggle0',700);P('wave0',300);P('wave1',300);P('stand0',300)}
  else if(k==='giggle'){say('happy');P('giggle0',900,0,'heart');P('clap0',400);P('giggle0',700);P('stand0',300)}
  else if(k==='kiss'){say('love');P('kiss0',1500,0,'heart');P('wave0',300);P('stand0',300)}
  else if(k==='think'){say('think');P('think0',1800+R()*1500);P('look0',700);P('stand0',300)}
  else if(k==='surprise'){P('surprise0',700);P('look0',600);P('stand0',300)}
  else if(k==='hi'){say(R()<.5?'hi':'play');face=mp.x>pos.x+SZ/2?1:-1;for(let i=0;i<3;i++){P('wave0',280);P('wave1',280)}P('stand0',400)}else if(k==='blink'){P('blink0',130);P('stand0',250);P('blink0',120);P('stand0',1500)}
  else if(k==='look'){P('look0',1000+R()*1200);P('stand0',600);P('blink0',140);P('stand0',600)}
  else if(k==='wave'){for(let i=0,n=2+R()*3;i<n;i++){P('wave0',300);P('wave1',300)}P('stand0',1000)}
  else if(k==='walk'){if(R()<.4)face=-face;for(let i=0,n=12+R()*28;i<n;i++)P('walk'+i%6,110,D3);P('stand0',800)}
  else if(k==='flower'){for(let i=0,n=4+R()*6;i<n;i++)P('walk'+i%6,110,D3);P('squat0',1500+R()*1500,0,'flower');P('look0',1000,0,'flower');P('stand0',600);P('wave0',500);P('stand0',600)}
  else if(k==='ball'){P('squat0',400,0,'ball');P('stand0',300);P('jump0',350,0,'ball');P('stand0',300,0,'ball');P('walk0',110,D3,'ball');P('walk1',110,D3,'ball');P('kick0',500,0,'ball');P('run0',90,8*KZ);P('run1',90,8*KZ);P('clap0',500,0,'heart');P('stand0',800)}
  else if(k==='jump'){P('squat0',200);P('jump0',350,0,'heart');P('stand0',250);P('squat0',150);P('jump0',350,0,'heart');P('stand0',1000)}
  else if(k==='clap'){P('sit0',500);for(let i=0,n=3+R()*4;i<n;i++){P('clap0',350,0,'music');P('sit0',300)}P('stand0',600)}
  else{P('squat0',350);P('sit0',2500+R()*4000);P('clap0',600,0,'music');P('sit0',2000+R()*4000);P('squat0',300);P('stand0',500)}
  seq=S;seqT=0;return}
 if(k==='idle')P('perch0',1500+R()*2500);else if(k==='look'){P('look0',800+R()*1200);P('perch0',600);P('down0',600+R()*900);P('perch0',500)}
 else if(k==='cock'){for(let i=0;i<2;i++){P('cock0',500);P('cock1',400);P('cock0',600);P('perch0',900)}}
 else if(k==='preen'){P('preen0',1500+R()*1500);P('perch0',400);P('preen0',1000+R()*1500);P('shake0',350);P('perch0',800)}
 else if(k==='walk'){if(R()<.4)face=-face;for(let i=0,n=8+R()*16;i<n;i++)P('walk'+i%3,130,3);P('perch0',800)}
 else if(k==='forage'){for(let i=0,n=3+R()*6;i<n;i++)P('walk'+i%3,130,3);for(let j=0,m=2+R()*3;j<m;j++){const pr=R()<.33?'insect':'crumbs';P('down0',400,0,pr);P('peck1',250,0,pr);P('peck0',180,0,pr);P('peck1',180,0,pr);P('peck0',180);P('perch0',500);P('walk1',130,3);P('walk2',130,3)}}
 else if(k==='drink'){P('peck1',500,0,'water');P('peck0',600,0,'water');P('drink0',700,0,'water');P('peck0',600,0,'water');P('drink0',700,0,'water');P('perch0',600)}
 else if(k==='sing'){P('sing0',700,0,'chirp');P('perch0',300);P('sing0',900,0,'chirp');P('cock0',600);P('sing0',700,0,'chirp');P('perch0',1000)}
 else if(k==='bathe'){P('peck0',500,0,'water');for(let i=0;i<3;i++){P('shake0',260,0,'splash');P('perch0',120,0,'splash')}P('preen0',2000);P('perch0',800)}
 else if(k==='hop'){P('hop0',180);P('hop1',250,12);P('perch0',600)}
 else if(k==='sleep'){const h=hourBD();go('sleep',h>=22||h<5?Infinity:60000+R()*180000);show('sleep0');return}
 else if(k==='curious'){pick(true,mp);go('fly',30000);mood='curious';return}
 else if(k==='fly'){pick(R()<.3);go('fly');tFly=performance.now();return}
 seq=S;seqT=0}
function choose(t){if(GIRL){const h=hourBD(),night=h>=22||h<5,onE=edge&&edge.b-edge.a>2*SZ,near=t-tMouse<15000&&Math.hypot(mp.x-pos.x-SZ/2,mp.y-pos.y-SZ/2)<900;
  const w={idle:1,walk:onE?3:0,run:onE?2.5:0,skip:onE?2:0,dance:3,fly:net===null||!roamOn()?0:3,chase:onE?2:0,ball:2,read:1,peek:pos.x<SZ||pos.x>innerWidth-2*SZ?2:.5,hi:near?2.5:.5,giggle:1.5,kiss:.8,think:1,jump:1.5,flower:1.5,clap:1,sit:.8,look:1,curious:near?2:0,sleep:night?20:0};
  let r=Math.random()*Object.values(w).reduce((a,b)=>a+b,0);for(const k in w){if((r-=w[k])<=0)return act(k)}return act('idle')}
 const h=hourBD(),night=h>=22||h<5,morning=h>=5&&h<9,noon=h>=12&&h<15,onEdge=edge&&edge.b-edge.a>160;
 const w={idle:3,look:3,cock:2,preen:2,walk:onEdge?3:0,forage:onEdge?3:1,drink:noon?1.5:.6,sing:morning?3:1,bathe:noon?1.2:.3,hop:1.5,fly:net===null||!roamOn()?0:1+(t-tFly>90000)*2.5,sleep:night?30:.2,
  curious:t-tMouse>20000&&Math.hypot(mp.x-pos.x-48,mp.y-pos.y-48)<700?3:0};
 let r=Math.random()*Object.values(w).reduce((a,b)=>a+b,0);for(const k in w){if((r-=w[k])<=0)return act(k)}act('idle')}
function stepSeq(t){if(!seq.length)return false;if(t<seqT)return true;const [p,d,dx,pr]=seq.shift();seqT=t+d;
 if(dx){let nx=pos.x+dx*face;const a=edge?edge.a:0,bb=edge?edge.b:innerWidth-SZ;if(nx<a||nx>bb){face=-face;nx=pos.x+dx*face}pos.x=nx;if(perchEl)perchOff+=dx*face}
 if(pr==='chirp'){chirp();props(null)}else props(pr);show(p);place(p==='hop1'||p==='jump0'?-11:0);return true}
function react(w){if(state==='sleep'&&w!=='clip')return;if(w==='clip'&&state!=='pinned'&&net!==null&&mp.x>0){pick(false,{x:mp.x+60,y:mp.y});go('fly',6000);mood='visit'}
 else if(w==='happy'&&state!=='fly')act('sing');else if(w==='think'&&state!=='fly'){seq=[];for(let i=0;i<3;i++)seq.push(['look0',800,0,null],['down0',800,0,null])}else if(w==='sad'&&state!=='fly')seq=[['down0',2000,0,null],['perch0',500,0,null]]}
addEventListener('pointermove',e=>{const t=performance.now(),dt=Math.max(t-mp.t,8),vx=(e.clientX-mp.x)/dt*1000,vy=(e.clientY-mp.y)/dt*1000;tMouse=t;
 const cx=pos.x+SZ/2,cy=pos.y+SZ*.54,d=Math.hypot(e.clientX-cx,e.clientY-cy),toward=vx*(cx-e.clientX)+vy*(cy-e.clientY)>0;
 if(mp.t&&Math.hypot(vx,vy)>1800&&toward&&d<220&&state!=='pinned'&&!drag&&net!==null&&t>noStartle&&!P){face=cx>e.clientX?1:-1;perchEl=null;edge=null;tgt={x:Math.max(0,Math.min(innerWidth-SZ,pos.x+face*(250+Math.random()*300))),y:Math.max(0,pos.y-150-Math.random()*200),perch:0};go('fly',6000+Math.random()*5000);mood='startled';noStartle=t+4000;chirp()}
 mp={x:e.clientX,y:e.clientY,t}},{passive:true});
function roam(t){const dt=Math.min(50,t-(lt||t));lt=t;const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
 if(busy&&state!=='fly'&&state!=='pinned'&&mood!=='busy'){pick(true);mood='busy';go('fly',30000)}
 if(drag||document.hidden){}
 else if(state!=='fly'){
  if(state==='sleep'){show('sleep0');if(GIRL&&!b.querySelector('.pr'))props('zzz');const h=hourBD();if(t>until||(h>=5&&h<22&&until===Infinity)){go('perch',2000);show('shake0')}}
  else if(!stepSeq(t)){if(state==='pinned'){if(t>until)pin(false);else act(['idle','look','cock','preen','walk','forage','sing','hop','idle'][Math.floor(Math.random()*9)])}
   else if(busy&&mood==='busy')seq=[['peck1',200,0,null],['peck0',150,0,null],['look0',600,0,null],['perch0',500,0,null]];
   else if(t>until&&!P&&!reduce){until=t+(GIRL?200+Math.random()*600:500+Math.random()*1500);choose(t)}else show('perch0')}
  if(state==='perch'&&perchEl){const r=perchEl.getBoundingClientRect();if(r.top<0||r.top>innerHeight||!r.width)act('fly');else{pos.y=r.top-FOOT;pos.x=r.left+perchOff;place(pose==='hop1'?-9:0)}}
  if(follow&&state==='perch'&&Math.hypot(mp.x-pos.x,mp.y-pos.y)>260){pick(false,{x:mp.x-70,y:mp.y});go('fly',30000)}}
 else if(GIRL)girlMove(t,dt);
 else{const near=Math.hypot(mp.x-pos.x-48,mp.y-pos.y-48)<110;
  if(near&&!tgt.perch&&!mood&&!follow||P){wing=(wing+1)%8;show('fly'+wing)}else{
  if(follow)tgt={x:face>0?mp.x-140:mp.x+20,y:mp.y-100,perch:0};
  else if((net===null||!roamOn()||t>until||reduce)&&!tgt.perch&&mood!=='visit')pick(true);
  const sp=sp0()*.13*(net||.6)*(tgt.perch?1.25:1)*(mood==='startled'?2.4:1)*dt,dx=tgt.x-pos.x,dy=tgt.y-pos.y,d=Math.hypot(dx,dy);
  if(d<sp+1){pos.x=tgt.x;pos.y=tgt.y;place();
   if(follow){wing=(wing+1)%8;show('fly'+wing)}
   else if(tgt.perch){go('perch');mood=mood==='busy'?'busy':null;show('perch0');if(Math.random()<.5)act('look')}
   else if(mood==='visit'){mood=null;edge={a:pos.x-40,b:pos.x+40};go('perch',4000);act('sing')}
   else if(mood==='startled'){mood=null;pick(true)}else pick(false)}
  else{if(Math.abs(dx)>2)face=dx>0?1:-1;pos.x+=dx/d*sp;pos.y+=dy/d*sp;
   if(glide>0){glide--;show('glide0')}else if(t-(roam.f||0)>Math.max(26,55/Math.sqrt(net||.6))/(mood==='startled'?1.6:1)){roam.f=t;wing=(wing+1)%8;show('fly'+wing);if(wing===2&&dy>-.3*Math.abs(dx)&&d>300&&Math.random()<.3&&mood!=='startled')glide=20+Math.random()*30}
   place(glide?0:3*Math.sin(t/60))}}}
 badge.textContent=localStorage.rbtClipPause==='1'?'⏸':state==='pinned'?'📌':busy?'⚙':state==='sleep'?'💤':'';requestAnimationFrame(roam)}
requestAnimationFrame(roam);
/* মামণি: walks along the same edge; squat → jump arc between edges; waves on arrival after a copy */
let arc=null;function girlMove(t,dt){if(P){show('stand0');return}
 if(follow&&t-(girlMove.f||0)>2000){girlMove.f=t;pick(true,mp);until=t+1e9}
 const sp=sp0()*Math.max(.4,net||.5)*(mood==='visit'?2.2:1);
 if(arc){const u=Math.min(1,(t-arc.t0)/arc.T);pos.x=arc.sx+(tgt.x-arc.sx)*u;pos.y=arc.sy+(tgt.y-arc.sy)*u-arc.h*4*u*(1-u);show(u<.15?'squat0':'jump0');place();if(u>=1){arc=null;girlLand()}return}
 const dx=tgt.x-pos.x;if(Math.abs(tgt.y-pos.y)<=4){if(Math.abs(dx)<3){pos.x=tgt.x;girlLand();return}face=dx>0?1:-1;const fr=Math.abs(dx)>3*SZ;pos.x+=face*Math.min(Math.abs(dx),(fr?.16:.07)*KZ*sp*dt);
  if(t-(girlMove.w||0)>(fr?80:105)){girlMove.w=t;wing=(wing+1)%6;show(fr?'run'+wing%4:'walk'+wing)}place()}
 else{face=dx>0?1:-1;const d=Math.hypot(dx,tgt.y-pos.y);show('squat0');arc={sx:pos.x,sy:pos.y,t0:t+180,T:Math.min(1600,550+d*.7)/Math.max(.6,Math.min(1.6,sp)),h:60+Math.max(0,pos.y-tgt.y)*.6+d*.05}}
 if(t>until&&!follow){pos.x=tgt.x;pos.y=tgt.y;place();girlLand()}}
function girlLand(){go('perch');const vis=mood==='visit'||mood==='curious';mood=mood==='busy'?'busy':null;seq=[['squat0',200,0,null],['stand0',300,0,null]];
 if(GIRL&&Math.random()<.3)seq.push(['wave0',300,0,null],['stand0',200,0,null]);if(vis){say('hi');face=mp.x>pos.x+SZ/2?1:-1;for(let i=0;i<3;i++)seq.push(['wave0',300,0,'heart'],['wave1',300,0,null]);seq.push(['stand0',1000,0,null])}}
b.addEventListener('contextmenu',e=>{e.preventDefault();if(confirm(GIRL?'দোয়েল পাখিকে ফিরিয়ে আনবেন?':'মামণিকে আনবেন?'))cmd('mascot',GIRL?'doyel':'girl')});
const pin=on=>{if(on){go('pinned',(GIRL?25000:30000)+Math.random()*(GIRL?65000:90000));perchEl=null;edge={a:pos.x-60,b:pos.x+60};localStorage.rbtFpos=JSON.stringify(pos);if(GIRL)act('sit')}else{pick(false);go('fly',GIRL?120000:undefined);arc=null;tFly=performance.now()}};
let drag=null,moved=false,clickT=0;b.addEventListener('pointerdown',e=>{e.preventDefault();drag={dx:e.clientX-pos.x,dy:e.clientY-pos.y};moved=false;b.setPointerCapture(e.pointerId)});
b.addEventListener('pointermove',e=>{if(!drag)return;const nx=e.clientX-drag.dx,ny=e.clientY-drag.dy;if(Math.abs(nx-pos.x)+Math.abs(ny-pos.y)>3){moved=true;wing=(wing+1)%8;show('fly'+wing);props(null)}pos.x=nx;pos.y=ny;clampP();place()});
b.addEventListener('pointerup',()=>{if(!drag)return;drag=null;if(moved)pin(true);else{if(state==='sleep'){go('perch',3000);show('shake0')}clearTimeout(clickT);clickT=setTimeout(()=>toggle(),280)}});
b.addEventListener('dblclick',e=>{e.preventDefault();clearTimeout(clickT);if(P)toggle(false);pin(false)});
/* glass panel (same panel.html as Windows/Android) — bridge via postMessage */
let P=null;function toggle(on){if(P&&on!==true){P.style.display='none';P=null;return}
 let f=document.getElementById('rbtP');if(!f){f=document.createElement('iframe');f.id='rbtP';f.allow='microphone; clipboard-read; clipboard-write';f.src='/bb/static/notes/panel.html?v=2';document.body.appendChild(f)}
 else{try{f.contentWindow.rbtShow&&f.contentWindow.rbtShow()}catch(e){}}
 f.style.display='block';f.style.left=Math.max(6,Math.min(innerWidth-430,pos.x>innerWidth/2?pos.x-410:pos.x+SZ))+'px';f.style.top=Math.max(6,Math.min(innerHeight-650,pos.y-300))+'px';P=f}
const status=()=>({state:state==='perch'&&seq.length?(pose.startsWith('walk')?'walk':pose.startsWith('peck')?'forage':'perch'):state,net,mbps,speed:sp0(),sound:localStorage.rbtSound==='1',roam:roamOn(),paused:localStorage.rbtClipPause==='1',busy});
function cmd(c,v){if(c==='size'){localStorage.rbtSize=v;location.reload();return}if(GIRL&&['dance','chase','read','peek','run','skip','kiss','giggle','hi'].includes(c)){if(state!=='fly'){go('perch',8000);act(c)}return}if(c==='mascot'){localStorage.rbtMascot=v;location.reload();return}if(GIRL&&c==='forage'){if(state!=='fly')act(['clap','ball','flower','jump'][Math.floor(Math.random()*4)]);return}if(c==='fly'){follow=false;pin(false)}else if(c==='sit'){follow=false;pick(true);go('fly',30000)}else if(c==='follow'){follow=!follow;if(follow)go('fly',1e9);else pick(true)}
 else if(c==='sleep'){if(state==='sleep')go('perch',2000);else act('sleep')}else if(c==='forage'){if(state==='fly')pick(true);else act('forage')}else if(c==='sing'){chirp();if(state!=='fly')act('sing')}
 else if(c==='roam')localStorage.rbtRoam=roamOn()?'0':'1';else if(c==='sound'){localStorage.rbtSound=localStorage.rbtSound==='1'?'0':'1';chirp()}else if(c==='speed')localStorage.rbtRoamSp=String(v);
 else if(c==='pause')localStorage.rbtClipPause=localStorage.rbtClipPause==='1'?'0':'1';else if(c==='hide'){b.style.display='none';setTimeout(()=>b.style.display='',600000)}else react(c)}
addEventListener('message',async e=>{if(e.origin!==location.origin||!e.data||!e.data.rbt)return;const {rbt:fn,args=[],id}=e.data;let v=null;
 if(fn==='token')v='';else if(fn==='bird')cmd(args[0],args[1]);else if(fn==='status')v=status();else if(fn==='close')toggle(false);
 else if(fn==='open'){const u=String(args[0]);if(/^https?:\/\//.test(u))u.startsWith(location.origin)?location.href=u:open(u,'_blank','noopener')}
 else if(fn==='copy'){try{await navigator.clipboard.writeText(args[0])}catch(_){}}
 e.source&&e.source.postMessage({rbtRe:id,v},location.origin)});
addEventListener('keydown',e=>{if(e.key==='Escape'&&P)toggle(false);if(GIRL&&state==='perch'&&!P&&performance.now()-(cmd.k||0)>12000){cmd.k=performance.now();const a=document.activeElement,r=a&&a.getBoundingClientRect&&a.getBoundingClientRect();if(r&&r.width)face=r.left+r.width/2>pos.x+SZ/2?1:-1;seq=[['look0',1200,0,null],['think0',800,0,null],['stand0',300,0,null]];if(Math.random()<.5)say('type')}},true);
document.addEventListener('pointerdown',e=>{if(!GIRL||b.contains(e.target)||state!=='perch'||P||performance.now()-(cmd.c||0)<4000)return;cmd.c=performance.now();face=e.clientX>pos.x+SZ/2?1:-1;if(Math.hypot(e.clientX-pos.x-SZ/2,e.clientY-pos.y-SZ/2)<2.5*SZ){seq=[['surprise0',600,0,null],['giggle0',700,0,null],['stand0',300,0,null]];say('click')}else seq=[['look0',900,0,null],['stand0',300,0,null]]},true);
/* in-page copies are always visible to us */
document.addEventListener('copy',()=>{const s=String(getSelection()||'');if(s.length>1)setTimeout(()=>send(s),50)});
/* on focus: read only if the user already granted clipboard-read (Chrome); never prompts silently */
let last='';addEventListener('focus',async()=>{try{const p=await navigator.permissions.query({name:'clipboard-read'});if(p.state!=='granted')return;const t=await navigator.clipboard.readText();if(t&&t!==last){last=t;send(t)}}catch(e){}});
})();
