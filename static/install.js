/* Bangla Bhai — PWA install helper (login, admin, landing, app menu) */
(function(){
var W=window,D=document,deferred=null;
var standalone=function(){return (W.matchMedia&&matchMedia('(display-mode: standalone)').matches)||navigator.standalone===true||D.referrer.indexOf('android-app://')===0};
var bn=(D.documentElement.lang||'').indexOf('bn')===0;
var t=function(en,b){return bn?b:en};
if('serviceWorker' in navigator){navigator.serviceWorker.register('/sw.js').catch(function(){})}
W.addEventListener('beforeinstallprompt',function(e){e.preventDefault();deferred=e;});
W.addEventListener('appinstalled',function(){deferred=null;hide();});
function hide(){D.querySelectorAll('[data-install-btn],#installBtn').forEach(function(b){b.style.display='none'})}
var ios=/iphone|ipad|ipod/i.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
var android=/android/i.test(navigator.userAgent);
function sheet(){
 var o=D.getElementById('bbInstSheet');if(o){o.style.display='flex';return}
 o=D.createElement('div');o.id='bbInstSheet';
 o.style.cssText='position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,.6);display:flex;align-items:flex-end;justify-content:center';
 var steps=ios?
  '<li>'+t('Open this page in <b>Safari</b>','এই পাতাটা <b>Safari</b>-তে খুলুন')+'</li><li>'+t('Tap <b>Share</b> (□↑)','<b>Share</b> (□↑) চাপুন')+'</li><li>'+t('Tap <b>Add to Home Screen</b> → Add','<b>Add to Home Screen</b> → Add চাপুন')+'</li>':
  '<li>'+t('Open in <b>Chrome</b> (or Edge)','<b>Chrome</b> (বা Edge)-এ খুলুন')+'</li><li>'+t('Tap the <b>⋮</b> menu','<b>⋮</b> মেনু চাপুন')+'</li><li>'+t('Tap <b>Install app</b> / <b>Add to Home screen</b>','<b>Install app</b> / <b>Add to Home screen</b> চাপুন')+'</li>';
 o.innerHTML='<div role=dialog aria-modal=true style="background:#122442;color:#eef2f8;border:1px solid #243a5c;border-radius:18px 18px 0 0;max-width:460px;width:100%;padding:22px 22px 28px;box-sizing:border-box;font-family:inherit">'+
  '<div style="display:flex;align-items:center;gap:12px;margin-bottom:10px"><img src="/bb/static/icon-192.png" width=48 height=48 style="border-radius:12px" alt=""><div><b style="font-size:17px">Bangla Bhai</b><div style="font-size:13px;color:#8b98b0">'+t('Install the app','অ্যাপ ইনস্টল করুন')+'</div></div></div>'+
  (ios?'':'<a href="/download/bangla-bhai.apk" download style="display:block;text-align:center;background:#1e6fd9;color:#fff;text-decoration:none;padding:13px;border-radius:12px;font-weight:600;margin:8px 0">🤖 '+t('Download Android app (APK)','Android অ্যাপ ডাউনলোড (APK)')+'</a>')+
  '<div style="font-size:13px;color:#8b98b0;margin-top:10px">'+t('Or install from the browser:','অথবা ব্রাউজার থেকে ইনস্টল করুন:')+'</div><ol style="margin:8px 0 0 18px;padding:0;line-height:1.8;font-size:14px">'+steps+'</ol>'+
  (ios?'':'<div style="font-size:12px;color:#8b98b0;margin-top:10px">'+t('APK: if Android asks, allow “Install unknown apps” for your browser.','APK: Android জিজ্ঞেস করলে ব্রাউজারের জন্য “Install unknown apps” অনুমতি দিন।')+'</div>')+
  '<button type=button id=bbInstClose style="margin-top:16px;width:100%;padding:12px;border-radius:12px;border:1px solid #243a5c;background:transparent;color:#eef2f8;font-size:15px;cursor:pointer">'+t('Close','বন্ধ')+'</button></div>';
 o.addEventListener('click',function(e){if(e.target===o||e.target.id==='bbInstClose')o.style.display='none'});
 D.body.appendChild(o);
}
W.BBInstall={open:function(){
 if(deferred){var d=deferred;deferred=null;d.prompt();d.userChoice&&d.userChoice.then(function(r){if(r&&r.outcome==='dismissed')deferred=d;});return}
 sheet();},standalone:standalone};
W.installApp=W.BBInstall.open;
function wire(){
 if(standalone()){hide();return}
 D.querySelectorAll('[data-install-btn],#installBtn').forEach(function(b){b.style.display=b.getAttribute('data-install-display')||'flex';b.onclick=function(e){e.preventDefault();W.BBInstall.open()}});
}
if(D.readyState==='loading')D.addEventListener('DOMContentLoaded',wire);else wire();
})();
