/* Bangla Bhai page i18n: English text is the key. Dicts in /bb/static/i18n/px_<lang>.json */
(function(){
  const LANGS={en:'English',bn:'বাংলা',hi:'हिन्दी',ar:'العربية',ur:'اردو',es:'Español',fr:'Français',zh:'中文'};
  const ck=(document.cookie.match(/(?:^|; )bb_lang=([^;]*)/)||[])[1];
  let L=localStorage.bbLang||localStorage.bb_lang||ck||'en'; if(!LANGS[L])L='en';
  let PX={};
  if(L!=='en'){try{const x=new XMLHttpRequest();x.open('GET','/bb/static/i18n/px_'+L+'.json?v=69',false);x.send();if(x.status===200)PX=JSON.parse(x.responseText)}catch(e){}}
  const h=document.documentElement;h.lang=L;h.dir=(L==='ar'||L==='ur')?'rtl':'ltr';
  window.PXL=L;window.PXLANGS=LANGS;
  window.TT=s=>PX[s]||s;
  window.TX=(en,bn)=>L==='en'?en:(L==='bn'&&bn&&!PX[en])?bn:(PX[en]||(L==='bn'&&bn)||en);
  window.pxSetLang=l=>{if(!LANGS[l])l='en';localStorage.bbLang=l;localStorage.bb_lang=l;document.cookie='bb_lang='+l+';path=/;max-age=31536000;samesite=lax';location.reload()};
  window.pxSelect=()=>'<select class=lang onchange="pxSetLang(this.value)" aria-label="Language" style="width:auto">'+Object.keys(LANGS).map(k=>'<option value='+k+(k===L?' selected':'')+'>'+LANGS[k]+'</option>').join('')+'</select>';
  window.pxApply=root=>{if(L==='en')return;root=root||document.body;
    const w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);let n;
    while(n=w.nextNode()){const s=n.nodeValue.trim();if(s&&PX[s])n.nodeValue=n.nodeValue.replace(s,PX[s])}
    root.querySelectorAll('[placeholder],[title]').forEach(e=>{['placeholder','title'].forEach(a=>{const v=e.getAttribute(a);if(v&&PX[v])e.setAttribute(a,PX[v])})});
    const t=document.title.split(' · ')[0];if(PX[t])document.title=PX[t]+' · Bangla Bhai'};
})();
