// Clipboard watcher + always-on-top floating notebook bubble (Electron). Same privacy filter as link/royal_clip.py.
const {clipboard,BrowserWindow,screen,ipcMain,shell}=require('electron');const path=require('path'),crypto=require('crypto');
const SENS=[/\b\d{4,8}\b.{0,40}\b(otp|code|কোড|পিন|pin|verification)\b/i,/\b(otp|code|কোড|pin|verification)\b.{0,40}\b\d{4,8}\b/i,/^\s*\d{4,8}\s*$/,/(password|passwd|pwd|পাসওয়ার্ড)\s*[:=]/i,/-----BEGIN [A-Z ]*PRIVATE KEY/,/\b(sk|pk|ghp|gho|xox[bpa]|AKIA)[-_A-Za-z0-9]{16,}/];
const luhn=s=>{const d=s.replace(/\D/g,'').split('').reverse().map(Number);return d.length>=13&&d.length<=19&&d.reduce((a,x,i)=>a+(i%2?(x*2>9?x*2-9:x*2):x),0)%10===0};
function sensitive(t){if(SENS.some(r=>r.test(t)))return true;if((t.match(/(?:\d[ -]?){13,19}/g)||[]).some(luhn))return true;const s=t.trim();
 return !s.includes(' ')&&s.length>=8&&s.length<=64&&!/^(http|www)/.test(s)&&!s.includes('@')&&[/[a-z]/,/[A-Z]/,/\d/,/[^\w]/].filter(r=>r.test(s)).length>=3}
module.exports=function start(agent,BASE,store){let last=null,paused=store.get('clipPaused')===true,bub=null;
 const send=(kind,content)=>agent.tok&&fetch(BASE+'/bb/link/clip',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:agent.tok,kind,content})}).catch(()=>{});
 setInterval(()=>{if(paused)return;const t=clipboard.readText();let h,kind='text',c=t;
  if(t){h=crypto.createHash('sha1').update(t).digest('hex')}else{const im=clipboard.readImage();if(im.isEmpty())return;const s=im.getSize();const r=s.width>1280?im.resize({width:1280}):im;c='data:image/jpeg;base64,'+r.toJPEG(70).toString('base64');kind='image';h=crypto.createHash('sha1').update(c.slice(0,200000)).digest('hex')}
  if(h===last)return;const first=last===null;last=h;if(first)return;if(kind==='text'&&(!t.trim()||t.length>200000||sensitive(t)))return;send(kind,c)},1200);
 const {width,height}=screen.getPrimaryDisplay().workAreaSize;const p=store.get('bubblePos')||[width-80,Math.round(height/2)];
 bub=new BrowserWindow({width:60,height:60,x:p[0],y:p[1],frame:false,transparent:true,alwaysOnTop:true,skipTaskbar:true,resizable:false,webPreferences:{preload:path.join(__dirname,'preload.js')}});
 bub.setAlwaysOnTop(true,'floating');bub.loadFile(path.join(__dirname,'bubble.html'));bub.on('moved',()=>store.set('bubblePos',bub.getPosition()));
 let mini=null;ipcMain.on('bubble',(e,a)=>{if(a==='pause'){paused=!paused;store.set('clipPaused',paused);bub.webContents.send('paused',paused);return}
  if(a==='open'){if(mini&&!mini.isDestroyed())return mini.focus();const [x,y]=bub.getPosition();mini=new BrowserWindow({width:380,height:560,x:Math.max(0,x-390),y:Math.max(0,y-250),alwaysOnTop:true,autoHideMenuBar:true,title:'রয়েল নোটবুক'});mini.loadURL(BASE+'/notes/?view=clips')}});
 return {isPaused:()=>paused}};
