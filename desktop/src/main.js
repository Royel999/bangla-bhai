const {app,BrowserWindow,Tray,Menu,nativeImage,desktopCapturer,screen,ipcMain,shell,session}=require('electron');
const path=require('path');const {Agent}=require('./agent');
const BASE=(process.env.BB_URL||'https://banglabhai.dpdns.org').replace(/\/$/,'');
const APP='The Royal Bengal Tiger';
if(!app.requestSingleInstanceLock()){app.quit();}
let win,tray,overlay,statusWin,media,agent,st={state:'connecting',extra:'',device:null};
const COL={connected:'#006A4E',reconnecting:'#D4AF37',pending:'#D4AF37',offline:'#777',connecting:'#1d4ed8'};
const TXT={connected:'✅ সংযুক্ত / Connected',reconnecting:'🔄 আবার সংযোগ / Reconnecting',pending:'⏳ অনুমোদন দরকার / Needs approval',offline:'⛔ অফলাইন / Offline',connecting:'সংযোগ হচ্ছে… / Connecting…'};
function mainWin(){if(win){win.show();win.focus();return;}
  win=new BrowserWindow({width:1100,height:780,title:APP,icon:path.join(__dirname,'logo.png'),backgroundColor:'#006A4E',autoHideMenuBar:true,webPreferences:{contextIsolation:true}});
  win.loadURL(BASE+'/v4');win.webContents.setWindowOpenHandler(({url})=>{if(url.startsWith(BASE))return{action:'allow'};shell.openExternal(url);return{action:'deny'}});
  win.on('close',e=>{if(!app.isQuitting){e.preventDefault();win.hide();}});}
function statusPage(){if(statusWin){statusWin.show();return;}
  statusWin=new BrowserWindow({width:440,height:520,title:APP+' · Royal Link',icon:path.join(__dirname,'logo.png'),resizable:false,autoHideMenuBar:true,webPreferences:{preload:path.join(__dirname,'preload.js')}});
  statusWin.loadFile(path.join(__dirname,'status.html'));statusWin.on('closed',()=>statusWin=null);}
function mkOverlay(){const {width}=screen.getPrimaryDisplay().workAreaSize;
  overlay=new BrowserWindow({width:420,height:84,x:Math.round(width/2-210),y:16,frame:false,transparent:true,alwaysOnTop:true,skipTaskbar:true,focusable:false,show:false,resizable:false,webPreferences:{preload:path.join(__dirname,'preload.js')}});
  overlay.setAlwaysOnTop(true,'screen-saver');overlay.setIgnoreMouseEvents(true);overlay.loadFile(path.join(__dirname,'overlay.html'));}
function refreshTray(){if(!tray)return;tray.setToolTip((APP+' · '+TXT[st.state]+(st.extra?' '+st.extra:'')).slice(0,127));
  const auto=app.getLoginItemSettings().openAtLogin;
  tray.setContextMenu(Menu.buildFromTemplate([{label:TXT[st.state]+(st.device?'  · '+st.device:''),enabled:false},{type:'separator'},
    {label:'💬 চ্যাট খুলুন / Open chat',click:mainWin},{label:'🖥️ লাইভ ভিউ / Live view',click:()=>{mainWin();win.loadURL(BASE+'/bb/live')}},
    {label:'🔗 ডিভাইস ও অনুমতি / Devices',click:()=>{mainWin();win.loadURL(BASE+'/v4?devices=1')}},{label:'ℹ️ লিংক স্ট্যাটাস / Link status',click:statusPage},
    {type:'separator'},{label:'লগইনে চালু / Start at login',type:'checkbox',checked:auto,click:i=>{app.setLoginItemSettings({openAtLogin:i.checked,args:['--hidden']});refreshTray();}},
    {label:'বন্ধ করুন / Quit',click:()=>{app.isQuitting=true;agent&&(agent.stopped=true);app.quit();}}]));}
const ui={status(s){st=s;refreshTray();statusWin&&statusWin.webContents.send('status',{...st,txt:TXT[st.state],base:BASE});},
  live(text){if(!overlay)return;if(text){overlay.webContents.send('live',text);overlay.showInactive();}else{overlay.webContents.send('live',null);setTimeout(()=>overlay.hide(),600);}},
  async grab(w,q){const d=screen.getPrimaryDisplay();const s=d.size;const h=Math.round(s.height*w/s.width);
    const src=await desktopCapturer.getSources({types:['screen'],thumbnailSize:{width:w,height:h}});return src[0].thumbnail.toJPEG(q).toString('base64');},
  camera(){return mediaCall('camera')},mic(sec){return mediaCall('mic',sec)}};
let mid=0;const pend=new Map();
function mediaCall(kind,arg){if(!media){media=new BrowserWindow({show:false,webPreferences:{preload:path.join(__dirname,'preload.js')}});media.loadFile(path.join(__dirname,'media.html'));}
  return new Promise((res,rej)=>{const id=++mid;pend.set(id,{res,rej});const go=()=>media.webContents.send('media',{id,kind,arg});media.webContents.isLoading()?media.webContents.once('did-finish-load',go):go();setTimeout(()=>{if(pend.has(id)){pend.delete(id);rej(new Error('timeout'))}},30000);});}
ipcMain.on('media-result',(e,{id,b64,error})=>{const p=pend.get(id);if(!p)return;pend.delete(id);error?p.rej(new Error(error)):p.res(b64);});
ipcMain.handle('get-status',()=>({...st,txt:TXT[st.state],base:BASE}));
ipcMain.on('open',(e,w)=>{mainWin();if(w==='devices')win.loadURL(BASE+'/v4?devices=1');});
app.on('second-instance',mainWin);
app.whenReady().then(()=>{app.setAppUserModelId('org.dpdns.banglabhai.rbt');
  session.defaultSession.setPermissionRequestHandler((wc,p,cb)=>cb(['media','notifications','clipboard-read'].includes(p)));
  if(!app.getLoginItemSettings().openAtLogin&&!require('fs').existsSync(path.join(app.getPath('userData'),'.autostart-set'))){app.setLoginItemSettings({openAtLogin:true,args:['--hidden']});require('fs').writeFileSync(path.join(app.getPath('userData'),'.autostart-set'),'1');}
  tray=new Tray(nativeImage.createFromPath(path.join(__dirname,'tray.png')));tray.on('click',mainWin);refreshTray();mkOverlay();
  if(!process.argv.includes('--hidden'))mainWin();
  agent=new Agent(BASE,ui);agent.start();
  try{const fs=require('fs'),SF=path.join(app.getPath('userData'),'rbt-clip.json');const store={get:k=>{try{return JSON.parse(fs.readFileSync(SF,'utf8'))[k]}catch(e){}},set:(k,v)=>{let o={};try{o=JSON.parse(fs.readFileSync(SF,'utf8'))}catch(e){}o[k]=v;fs.writeFileSync(SF,JSON.stringify(o))}};
   require('./clip')(agent,BASE,store);}catch(e){console.error('clip',e)}});
app.on('window-all-closed',e=>{});
