/* Royal Tiger voice orb (prototype). Floating Seal-C orb -> talk overlay.
 REAL: mic -> /bb/api/stt -> existing chat send() -> reply -> /bb/api/tts playback (loop "hands-free").
 REAL (permission-gated): "See my screen" uses getDisplayMedia (desktop/Chromium; one frame, user picks what to share) -> /bb/api/upload (OCR) -> attached to the next question.
 SMS: drafts text with the AI, then opens the phone's own SMS app via sms: link — the user presses Send (Sentinel: we never send silently).
 STUB: background screen reading on Android / direct SMS sending need the native Royal Bengal Tiger app; those go through the agent's sms_send/screenshot tools which ALWAYS raise an Approve card. */
(function(){
const L=(b,e)=>{try{return T(b,e)}catch(_){return e}}, $=s=>document.querySelector(s);
const css=`#rbtOrb{position:fixed;right:18px;bottom:96px;z-index:9990;transition:opacity .2s;width:62px;height:62px;border-radius:50%;border:2px solid #c9a227;background:radial-gradient(circle at 50% 45%,#0b7a5a,#006A4E 60%,#033b2c);box-shadow:0 0 0 0 rgba(218,41,28,.5),0 8px 24px rgba(0,0,0,.45);cursor:pointer;padding:0;animation:rbtPulse 3s infinite;touch-action:none}
#rbtOrb img{width:100%;height:100%;border-radius:50%;object-fit:cover}
@keyframes rbtPulse{0%{box-shadow:0 0 0 0 rgba(218,41,28,.45),0 8px 24px #0008}70%{box-shadow:0 0 0 16px rgba(218,41,28,0),0 8px 24px #0008}100%{box-shadow:0 0 0 0 rgba(218,41,28,0),0 8px 24px #0008}}
#rbtVo{position:fixed;inset:0;z-index:9999;background:radial-gradient(circle at 50% 38%,#0d3b2e 0,#0D0D12 70%);color:#f3eee0;display:none;flex-direction:column;align-items:center;justify-content:center;gap:18px;font-family:inherit;padding:24px;text-align:center}
#rbtVo.on{display:flex}#rbtVo .big{width:180px;height:180px;border-radius:50%;border:3px solid #c9a227;position:relative;transition:transform .2s}
#rbtVo .big img{width:100%;height:100%;border-radius:50%}#rbtVo .ring{position:absolute;inset:-14px;border-radius:50%;border:3px solid #DA291C;opacity:0}
#rbtVo.listen .ring{animation:rbtR 1.2s infinite}#rbtVo.think .big{animation:rbtSpin 2.4s linear infinite}#rbtVo.speak .big{animation:rbtTalk .5s infinite alternate}
@keyframes rbtR{0%{transform:scale(.9);opacity:.9}100%{transform:scale(1.25);opacity:0}}@keyframes rbtSpin{to{transform:rotate(360deg)}}@keyframes rbtTalk{to{transform:scale(1.06)}}
#rbtVo .st{font-size:18px;min-height:26px}#rbtVo .tx{max-width:520px;opacity:.85;font-size:15px;max-height:30vh;overflow:auto}
#rbtVo .row{display:flex;gap:10px;flex-wrap:wrap;justify-content:center}#rbtVo button.c{border:1px solid #c9a22788;background:#ffffff10;color:#f3eee0;border-radius:24px;padding:10px 16px;font:inherit}
#rbtVo button.mic{width:72px;height:72px;border-radius:50%;background:#DA291C;border:0;color:#fff;font-size:28px}#rbtVo .x{position:absolute;top:16px;right:16px}
#rbtVo .flag{position:absolute;top:0;left:0;right:0;height:4px;background:linear-gradient(90deg,#006A4E 0 70%,#DA291C 70%)}
body:has(#scrim.on) #rbtOrb{opacity:0;pointer-events:none}
body:has(#app):has(#tabs) #rbtOrb{display:none!important}
@media (prefers-reduced-motion:reduce){#rbtOrb,#rbtVo *{animation:none!important}}`;
const st=document.createElement('style');st.textContent=css;document.head.appendChild(st);
const seal='/bb/static/v4/brand/RBT_seal_512_transparent.png';
const orb=document.createElement('button');orb.id='rbtOrb';orb.setAttribute('aria-label',L('টাইগারের সাথে কথা বলুন','Talk to the Tiger'));orb.innerHTML=`<img src="${seal}" alt="">`;
const vo=document.createElement('div');vo.id='rbtVo';vo.setAttribute('role','dialog');
vo.innerHTML=`<i class=flag></i><button class="c x" id=rbtX aria-label="Close">✕</button><div class=big><i class=ring></i><img src="${seal}" alt=""></div>
<div class=st id=rbtSt></div><div class=tx id=rbtTx></div>
<button class=mic id=rbtMic aria-label="Mic">🎙</button>
<div class=row><button class=c id=rbtScr>🖥 ${L('স্ক্রিন দেখাও','See my screen')}</button><button class=c id=rbtSms>✉️ ${L('SMS লিখে দাও','Help write SMS')}</button><button class=c id=rbtHf>🔁 ${L('হ্যান্ডস-ফ্রি: বন্ধ','Hands-free: off')}</button></div>
<small style="opacity:.6;max-width:460px">🔒 ${L('স্ক্রিন শুধু আপনি অনুমতি দিলে, একবারের জন্য। কিছু পাঠানো/পোস্ট করার আগে সবসময় আপনার Approve লাগবে।','Screen only when you allow it, one frame at a time. Nothing is sent or posted without your Approve.')}</small>`;
const isV4=!!document.getElementById('app')&&!!document.getElementById('tabs');
if(isV4){document.body.append(vo)}
else{
document.body.append(orb,vo);
// draggable orb
let drag=null;orb.addEventListener('pointerdown',e=>{drag={x:e.clientX,y:e.clientY,m:false};orb.setPointerCapture(e.pointerId)});
orb.addEventListener('pointermove',e=>{if(!drag)return;if(Math.abs(e.clientX-drag.x)+Math.abs(e.clientY-drag.y)>8)drag.m=true;if(drag.m){orb.style.right=Math.max(4,innerWidth-e.clientX-31)+'px';orb.style.bottom=Math.max(4,innerHeight-e.clientY-31)+'px'}});
orb.addEventListener('pointerup',()=>{const m=drag&&drag.m;drag=null;if(!m)open()});
}
const S=(cls,txt)=>{vo.className='on '+(cls||'');$('#rbtSt').textContent=txt||''};
let rec=null,hf=false,audio=null,pendingFile=null,mode='ask';
function open(){S('',L('মাইক চাপুন ও বলুন','Tap the mic and speak'));$('#rbtTx').textContent=''}
function close(){vo.className='';rec&&rec.stop();audio&&audio.pause()}
$('#rbtX').onclick=close;
$('#rbtHf').onclick=e=>{hf=!hf;e.target.textContent='🔁 '+(hf?L('হ্যান্ডস-ফ্রি: চালু','Hands-free: on'):L('হ্যান্ডস-ফ্রি: বন্ধ','Hands-free: off'))};
$('#rbtMic').onclick=()=>rec?rec.stop():listen();
async function listen(){audio&&audio.pause();
 if(!navigator.mediaDevices?.getUserMedia)return S('',L('এই ব্রাউজারে মাইক নেই','No microphone here'));
 let s;try{s=await navigator.mediaDevices.getUserMedia({audio:true})}catch(e){return S('',L('মাইকের অনুমতি দিন','Please allow the microphone'))}
 const ch=[];rec=new MediaRecorder(s);rec.ondataavailable=e=>ch.push(e.data);S('listen',L('শুনছি… থামাতে আবার চাপুন','Listening… tap to stop'));
 // auto-stop after silence-ish timeout (12s cap)
 const cap=setTimeout(()=>rec&&rec.stop(),12000);
 rec.onstop=async()=>{clearTimeout(cap);s.getTracks().forEach(t=>t.stop());rec=null;S('think',L('বুঝছি…','Understanding…'));
  const fd=new FormData();fd.append('file',new Blob(ch,{type:ch[0]?.type||'audio/webm'}),'voice.webm');
  try{const r=await fetch('/bb/api/stt',{method:'POST',body:fd});const j=await r.json();if(!r.ok||j.error)throw new Error(j.error||r.status);
   if(!j.text?.trim())return S('',L('কিছু শুনিনি, আবার বলুন','Didn\'t catch that'));$('#rbtTx').textContent='“'+j.text+'”';await ask(j.text)}catch(x){S('',String(x.message||x))}};
 rec.start()}
async function ask(q){
 let t=q;if(mode==='sms'){t=L('এই বিষয়ে একটা ছোট, ভদ্র SMS লিখে দাও। শুধু মেসেজের লেখাটা দাও: ','Write a short polite SMS about this. Reply with only the message text: ')+q}
 if(pendingFile){t=`[📎 ${pendingFile.name}]\n${pendingFile.text}\n[/📎]\n\n`+t;pendingFile=null}
 const inp=$('#inp');if(!inp||typeof window.send!=='function'){return S('',L('চ্যাট পাওয়া যায়নি','Chat not ready'))}
 const before=document.querySelectorAll('.msg.b .content').length;inp.value=t;inp.dispatchEvent(new Event('input'));S('think',L('ভাবছি…','Thinking…'));
 await window.send();const ans=await waitReply(before);$('#rbtTx').textContent=ans.slice(0,600);
 if(mode==='sms'){mode='ask';S('','');const row=document.createElement('div');row.className='row';
  row.innerHTML=`<button class=c id=rbtSmsGo>📲 ${L('SMS অ্যাপে খুলুন (আপনি Send চাপবেন)','Open in SMS app (you press Send)')}</button>`;$('#rbtTx').appendChild(row);
  $('#rbtSmsGo').onclick=()=>{location.href='sms:?&body='+encodeURIComponent(ans.trim())};S('',L('খসড়া তৈরি','Draft ready'))}
 await say(ans);if(hf&&vo.classList.contains('on'))listen()}
function waitReply(before){return new Promise(res=>{let last='',same=0,n=0;const iv=setInterval(()=>{n++;const all=document.querySelectorAll('.msg.b .content');const el=all[all.length-1];
 const txt=(all.length>before&&el)?el.innerText.trim():'';if(txt&&txt===last)same++;else same=0;last=txt;if((txt&&same>=3)||n>120){clearInterval(iv);res(txt||'')}},500)})}
async function say(text){if(!text)return S('','');S('speak',L('বলছি…','Speaking…'));
 try{const r=await fetch('/bb/api/tts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:text.slice(0,1500)})});if(!r.ok)throw 0;
  audio=new Audio(URL.createObjectURL(await r.blob()));await new Promise(ok=>{audio.onended=ok;audio.onerror=ok;audio.play().catch(ok)})}
 catch(e){ // fallback 2: browser speechSynthesis (free, offline-capable)
  if('speechSynthesis' in window){await new Promise(ok=>{const u=new SpeechSynthesisUtterance(text.slice(0,800));u.onend=ok;u.onerror=ok;speechSynthesis.speak(u)})}}
 S('',L('আবার বলতে মাইক চাপুন','Tap the mic to talk again'))}
$('#rbtScr').onclick=async()=>{
 if(!navigator.mediaDevices?.getDisplayMedia)return S('',L('এই ফোনের ব্রাউজার স্ক্রিন দিতে পারে না — The Royal Bengal Tiger অ্যাপ দিয়ে এজেন্ট স্ক্রিনশট নেবে (Approve কার্ডসহ)','This browser can\'t share the screen — use The Royal Bengal Tiger app; the agent will ask Approve first'));
 try{const s=await navigator.mediaDevices.getDisplayMedia({video:true});const v=document.createElement('video');v.srcObject=s;v.muted=true;await v.play();await new Promise(r=>setTimeout(r,400));
  const c=document.createElement('canvas');c.width=v.videoWidth;c.height=v.videoHeight;c.getContext('2d').drawImage(v,0,0);s.getTracks().forEach(t=>t.stop());
  const blob=await new Promise(r=>c.toBlob(r,'image/png'));const fd=new FormData();fd.append('file',blob,'screen.png');S('think',L('স্ক্রিন পড়ছি…','Reading the screen…'));
  const r=await fetch('/bb/api/upload',{method:'POST',body:fd});const j=await r.json();if(!r.ok||j.error)throw new Error(j.error||r.status);pendingFile=j;
  S('',L('স্ক্রিন দেখা হয়েছে। এখন প্রশ্ন বলুন।','Got the screen. Now ask your question.'))}catch(x){S('',L('স্ক্রিন শেয়ার বাতিল','Screen share cancelled'))}};
$('#rbtSms').onclick=()=>{mode='sms';S('',L('কাকে কী লিখতে চান বলুন','Say who and what to write'));listen()};
// hide the orb while any bottom sheet/dialog is open

window.RBTOrb={open,close};
})();
