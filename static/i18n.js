/* বাংলা ভাই — tiny i18n. Default English. Keys in /bb/static/i18n/<lang>.json */
(function(){
  const LANGS={en:{n:'English'},bn:{n:'বাংলা'},hi:{n:'हिन्दी'},ar:{n:'العربية',rtl:1},ur:{n:'اردو',rtl:1},es:{n:'Español'},fr:{n:'Français'},zh:{n:'中文'}};
  const cache={};let D={},EN={},cur='en';
  const ck=n=>(document.cookie.match('(?:^|; )'+n+'=([^;]*)')||[])[1];
  function stored(){const l=localStorage.bbLang||ck('bb_lang');return LANGS[l]?l:null}
  async function load(l){if(cache[l])return cache[l];try{const r=await fetch('/bb/static/i18n/'+l+'.json?v=62');cache[l]=r.ok?await r.json():{}}catch(e){cache[l]={}}return cache[l]}
  function t(k,v){let s=(k in D)?D[k]:(k in EN)?EN[k]:k;if(v)for(const x in v)s=s.split('{'+x+'}').join(v[x]);return s}
  function apply(root){root=root||document;
    root.querySelectorAll('[data-i18n]').forEach(e=>e.textContent=t(e.dataset.i18n));
    root.querySelectorAll('[data-i18n-ph]').forEach(e=>e.placeholder=t(e.dataset.i18nPh));
    root.querySelectorAll('[data-i18n-title]').forEach(e=>e.title=t(e.dataset.i18nTitle));
    root.querySelectorAll('select.bb-lang').forEach(s=>s.value=cur)}
  async function setLang(l,save=true){if(!LANGS[l])l='en';EN=await load('en');D=await load(l);cur=l;
    const h=document.documentElement;h.lang=l;h.dir=LANGS[l].rtl?'rtl':'ltr';
    if(save){localStorage.bbLang=l;document.cookie='bb_lang='+l+';path=/;max-age=31536000;samesite=lax'}
    apply();document.dispatchEvent(new CustomEvent('bb:lang',{detail:l}))}
  function picker(cls){return `<select class="bb-lang ${cls||''}" aria-label="Language" onchange="bbSetLang(this.value)">${Object.entries(LANGS).map(([k,v])=>`<option value="${k}" ${k===cur?'selected':''}>${v.n}</option>`).join('')}</select>`}
  function suggest(){if(stored())return;const b=(navigator.language||'en').slice(0,2).toLowerCase();if(b==='en'||!LANGS[b])return;
    const d=document.createElement('div');d.className='bb-langsug';
    d.innerHTML=`<span>${t('lang.suggest',{lang:LANGS[b].n})}</span><button data-a=y>${LANGS[b].n}</button><button data-a=n>${t('lang.keep')}</button>`;
    d.onclick=e=>{const a=e.target.dataset.a;if(!a)return;setLang(a==='y'?b:'en');d.remove()};document.body.appendChild(d)}
  window.t=t;window.L=(en,bn)=>cur==='bn'?bn:en;window.bbT=t;window.bbSetLang=setLang;window.bbLangPicker=picker;window.bbApplyI18n=apply;window.BB_LANGS=LANGS;
  window.bbLang=()=>cur;
  const st=document.createElement('style');st.textContent=`select.bb-lang{background:var(--panel2,#183054);color:var(--tx,#eef2f8);border:1px solid var(--bd,#243a5c);border-radius:10px;padding:6px 8px;font:inherit;font-size:13px}
.bb-langsug{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:120;display:flex;gap:8px;align-items:center;flex-wrap:wrap;justify-content:center;background:#122442;color:#eef2f8;border:1px solid #243a5c;border-radius:14px;padding:10px 14px;font-size:13px;box-shadow:0 10px 30px #0007;max-width:92vw}
.bb-langsug button{border:1px solid #243a5c;background:#1e6fd9;color:#fff;border-radius:9px;padding:5px 10px;cursor:pointer;font:inherit}.bb-langsug button[data-a=n]{background:transparent}
[dir=rtl] .msg.user{justify-content:flex-start}[dir=rtl] .sug{text-align:right}`;document.head.appendChild(st);
  window.bbI18nReady=setLang(stored()||'en',false).then(()=>{document.querySelectorAll('[data-lang-picker]').forEach(e=>e.innerHTML=picker());apply();if(!window.BB_APP)suggest()});
})();
