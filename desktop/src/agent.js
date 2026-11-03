// Royal Link agent (hub protocol v1) — Node port of link/royal_link_tray.py
const fs=require('fs'),os=require('os'),path=require('path'),{execFile,exec}=require('child_process'),WebSocket=require('ws');
const CFG=path.join(os.homedir(),'.bangla_bhai_link.json');
class Agent{
  constructor(base,ui){this.base=base.replace(/\/$/,'');this.ui=ui;this.state='connecting';this.dev=null;this.tok=null;this.done=new Set();this.results=new Map();this.liveSrv=false;this.delay=1;this.ws=null;this.stopped=false;}
  async http(m,p,d){const r=await fetch(this.base+p,{method:m,headers:{'Content-Type':'application/json','User-Agent':'RoyalLink/3.0 (RBT Desktop)'},body:d?JSON.stringify(d):undefined,signal:AbortSignal.timeout(35000)});if(!r.ok)throw new Error('HTTP '+r.status);return r.json();}
  set(st,extra=''){this.state=st;this.ui.status({state:st,extra,device:this.dev});}
  async pair(){
    try{const c=JSON.parse(fs.readFileSync(CFG,'utf8'));const s=await this.http('GET','/bb/link/status?token='+c.token);
      if(s.status==='approved'){this.dev=c.device;this.tok=c.token;return;}
      if(s.status==='pending'){this.dev=c.device;this.tok=c.token;return this.waitApprove();}}catch(e){if(String(e).includes('fetch failed'))throw e;}
    const r=await this.http('POST','/bb/link/pair',{name:process.env.COMPUTERNAME||os.hostname(),kind:'laptop',info:{os:process.platform,tray:true,ws:true,app:'rbt-desktop'}});
    fs.writeFileSync(CFG,JSON.stringify({device:r.device,token:r.token}),{mode:0o600});this.dev=r.device;this.tok=r.token;return this.waitApprove();
  }
  async waitApprove(){this.set('pending');for(;;){const s=await this.http('GET','/bb/link/status?token='+this.tok).catch(()=>({}));
    if(s.status==='approved')return; if(s.status==='denied'||s.status==='revoked'){this.set('offline','denied');throw new Error('denied');} await new Promise(r=>setTimeout(r,3000));}}
  async start(){for(;!this.stopped;){try{await this.pair();break;}catch(e){this.set('offline',String(e.message||e));await new Promise(r=>setTimeout(r,10000));}} this.connect();}
  connect(){
    const url=this.base.replace(/^http/,'ws')+'/bb/link/ws?token='+this.tok;const ws=new WebSocket(url,{headers:{'User-Agent':'RoyalLink/3.0'}});this.ws=ws;let hb;
    ws.on('open',()=>{this.delay=1;this.set('connected','WebSocket');hb=setInterval(()=>{try{ws.ping()}catch{}},20000);});
    ws.on('message',m=>this.onMsg(ws,m));
    ws.on('error',()=>{});
    ws.on('close',async()=>{clearInterval(hb);this.ws=null;if(this.stopped)return;
      try{const s=await this.http('GET','/bb/link/status?token='+this.tok);if(s.status==='denied'||s.status==='revoked'){this.set('offline','revoked');return;}}catch{this.set('offline');}
      const w=Math.min(60,this.delay)+Math.random();this.set('reconnecting',Math.round(w)+'s');this.delay=Math.min(60,this.delay*2);setTimeout(()=>this.connect(),w*1000);});
  }
  send(o){try{this.ws&&this.ws.send(JSON.stringify(o))}catch{}}
  onMsg(ws,m){let j;try{j=JSON.parse(m)}catch{return}
    if(j.type==='ping')return this.send({type:'pong',t:j.t});
    if(j.type==='hello'){this.liveSrv=!!j.live;return;} if(j.type==='live'){this.liveSrv=!!j.on;return;} if(j.type==='pong')return;
    const cid=j.cid;if(!cid)return;
    if(this.done.has(cid)){if(this.results.has(cid))this.send({cid,result:this.results.get(cid)});return;}
    this.done.add(cid);this.send({type:'ack',cid});this.runJob(j);}
  async runJob(job){const cid=job.cid,a=job.action||'';this.send({type:'step',cid,phase:'running',text:a});this.ui.live(this.label(a,job.args||{}));
    let t=null;if(this.liveSrv||process.env.BB_LIVE_FRAMES==='1')t=setInterval(async()=>{try{const f=await this.ui.grab(480,40);this.send({type:'step',cid,phase:'screenshot',text:'live',frame_b64:f})}catch{}},3000);
    let r;try{r=await this.act(a,job.args||{})}catch(e){r={error:String(e.message||e)}}finally{clearInterval(t);this.ui.live(null);}
    this.results.set(cid,r);if(this.results.size>50)this.results.delete(this.results.keys().next().value);if(this.done.size>500)this.done.clear();
    this.send({type:'step',cid,phase:r.error?'error':'done',text:String(r.error||'').slice(0,200)});this.send({cid,result:r});}
  label(a,g){return({shell:'শেল চালাচ্ছে: '+String(g.cmd||'').slice(0,60),screenshot:'স্ক্রিন দেখছে',click:`ক্লিক করছে (${g.x}, ${g.y})`,type_text:'টাইপ করছে…',camera_photo:'ক্যামেরা ব্যবহার করছে',mic_record:'মাইক শুনছে'})[a]||('কাজ করছে: '+a);}
  ps(script){return new Promise((res,rej)=>execFile('powershell.exe',['-NoProfile','-NonInteractive','-Command',script],{timeout:60000,windowsHide:true},(e,o,er)=>e?rej(new Error(er||e.message)):res(o)));}
  async act(a,g){
    if(a==='shell')return new Promise(res=>exec(g.cmd,{timeout:60000,windowsHide:true,maxBuffer:8e6},(e,o,er)=>res({text:((o||'')+(er||'')).slice(-4000)||'(খালি)'})));
    if(a==='screenshot'){const b=await this.ui.grab(960,55);return{image_b64:b,ext:'jpg',text:'960w jpeg'};}
    if(a==='click'){const x=parseInt(g.x),y=parseInt(g.y);await this.ps(`Add-Type -MemberDefinition '[DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);[DllImport("user32.dll")] public static extern void mouse_event(int f,int x,int y,int d,int e);' -Name U -Namespace W;[W.U]::SetCursorPos(${x},${y});[W.U]::mouse_event(2,0,0,0,0);[W.U]::mouse_event(4,0,0,0,0)`);return{text:'clicked'};}
    if(a==='type_text'){const s=String(g.text||'').replace(/'/g,"''").replace(/[+^%~(){}\[\]]/g,'{$&}');await this.ps(`Add-Type -AssemblyName System.Windows.Forms;[System.Windows.Forms.SendKeys]::SendWait('${s}')`);return{text:'typed'};}
    if(a==='camera_photo'){const b=await this.ui.camera();return{image_b64:b,ext:'jpg',text:'ছবি'};}
    if(a==='mic_record'){const sec=parseInt(g.seconds||4);const b=await this.ui.mic(sec);return{image_b64:b,ext:'webm',text:sec+'s'};}
    return{error:'অজানা: '+a};}
}
module.exports={Agent,CFG};
