const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('rbt',{onStatus:f=>ipcRenderer.on('status',(e,s)=>f(s)),getStatus:()=>ipcRenderer.invoke('get-status'),
 onLive:f=>ipcRenderer.on('live',(e,t)=>f(t)),open:w=>ipcRenderer.send('open',w),
 onMedia:f=>ipcRenderer.on('media',(e,r)=>f(r)),mediaResult:r=>ipcRenderer.send('media-result',r)});
