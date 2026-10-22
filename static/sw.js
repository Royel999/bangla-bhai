const CACHE='bb-v64';
// Only static assets are precached. Pages (/, /login, /app) are network-first so auth redirects never get cached.
const ASSETS=['/bb/static/bb2.css','/bb/static/bb2.js','/bb/static/viz.css','/bb/static/viz.js','/bb/static/i18n.js','/bb/static/i18n/en.json','/bb/static/logo.png','/bb/static/wordmark.svg','/bb/static/icon-192.png'];
const OFFLINE='<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><body style="margin:0;background:#0b1a33;color:#eef2f8;font-family:system-ui;display:grid;place-items:center;min-height:100vh;text-align:center"><div><img src="/bb/static/logo.png" width=96 style="border-radius:50%"><h2>Bangla Bhai is offline</h2><p style="color:#8b98b0">Check your connection. Retrying in 15s…</p><script>setTimeout(()=>location.reload(),15000)</script></div>';
self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE).then(c=>Promise.all(ASSETS.map(a=>c.add(a).catch(()=>{})))).then(()=>self.skipWaiting()))});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});
self.addEventListener('fetch',e=>{
  const r=e.request; if(r.method!=='GET')return;
  const u=new URL(r.url); if(u.origin!==location.origin)return;
  if(r.mode==='navigate'){ // network-first, offline page fallback
    e.respondWith(fetch(r).catch(()=>new Response(OFFLINE,{status:503,headers:{'Content-Type':'text/html; charset=utf-8'}})));return}
  if(!u.pathname.startsWith('/bb/static/'))return; // APIs and everything else: straight to network
  e.respondWith(caches.match(r).then(hit=>{
    const net=fetch(r).then(res=>{if(res.ok&&!res.redirected){const c=res.clone();caches.open(CACHE).then(x=>x.put(r,c))}return res});
    return hit||net;
  }));
});
