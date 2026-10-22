/* বাংলা ভাই — viz helpers (CSS/SVG/vanilla JS, lightweight) */
(function(){
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

  function ensureBg(){
    if(document.querySelector('.bb-bg')) return;
    const bg=document.createElement('div');bg.className='bb-bg';bg.setAttribute('aria-hidden','true');
    bg.innerHTML='<div class="grid"></div><div class="stars"></div>';
    document.body.prepend(bg);
    if(reduce) return;
    const stars=bg.querySelector('.stars');
    const n = innerWidth<700?28:48;
    for(let i=0;i<n;i++){
      const s=document.createElement('i');s.className='star';
      s.style.left=(Math.random()*100)+'%';
      s.style.top=(Math.random()*100)+'%';
      s.style.setProperty('--t',(2.8+Math.random()*4)+'s');
      s.style.setProperty('--d',(Math.random()*4)+'s');
      stars.appendChild(s);
    }
  }

  function observeReveals(root=document){
    const els=[...root.querySelectorAll('.reveal:not(.in)')];
    if(!els.length) return;
    if(reduce){els.forEach(e=>e.classList.add('in'));return}
    if(!('IntersectionObserver' in window)){els.forEach(e=>e.classList.add('in'));return}
    const io=new IntersectionObserver((ents)=>{
      ents.forEach(en=>{if(en.isIntersecting){en.target.classList.add('in');io.unobserve(en.target)}});
    },{threshold:.12,rootMargin:'0px 0px -8% 0px'});
    els.forEach(e=>io.observe(e));
  }

  function thinkHTML(label){label=label||(window.t?t('app.thinking'):'Thinking...');
    return `<div class="status think"><span class="think-orb" aria-hidden="true"></span><span class="think-bars" aria-hidden="true"><i></i><i></i><i></i><i></i></span><span class="think-lab">${label||'ভাবছি...'}</span></div>`;
  }

  // Patch chat thinking indicator if present
  function patchThinking(){
    // expose helper
    window.bbThinkHTML = thinkHTML;
  }

  async function refreshLivebar(){
    const bar=document.getElementById('livebar');
    if(!bar || typeof api!=='function') return;
    try{
      const [devs, models, me] = await Promise.all([
        api('/bb/api/devices').catch(()=>({devices:[]})),
        api('/bb/api/models').catch(()=>[]),
        api('/bb/api/me').catch(()=>({}))
      ]);
      const online=(devs.devices||[]).filter(d=>d.online && d.status==='approved').length;
      const pending=(devs.devices||[]).filter(d=>d.status==='pending').length;
      const total=(devs.devices||[]).filter(d=>d.status!=='revoked'&&d.status!=='denied').length;
      const mcount=Array.isArray(models)?models.length:0;
      const role=me.role||'user';
      bar.innerHTML =
        `<span class="pill"><span class="d ${online?'on':''}"></span>${t('live.online',{n:'<b>'+online+'</b>'})}${pending?' · '+t('live.pending',{n:pending}):''}</span>`+
        `<span class="pill"><span class="d on"></span>${t('live.models',{n:'<b>'+mcount+'</b>'})}</span>`+
        `<span class="pill"><span class="d ${role==='owner'?'on':'warn'}"></span><b>${role==='owner'?t('app.owner'):t('live.user')}</b> · ${t('live.devices',{n:total})}</span>`;
    }catch(e){}
  }

  function dashHTML(stats){
    const chats=stats.chats||0, msgs=stats.msgs||0, online=stats.online||0, total=stats.devices||0;
    const pct = total? Math.round((online/total)*100) : 0;
    const r=22, c=2*Math.PI*r, off=c*(1-pct/100);
    const bars=[.35,.55,.8,.45,.7,.9,.5,.65].map((h,i)=>`<span style="height:${Math.round(h*100)}%;animation-delay:${i*.05}s"></span>`).join('');
    return `<div class="dash">
      <div class="dcard"><div class="k">${t('dash.chats')}</div><div class="v">${chats}</div><div class="s">${t('dash.chats_s')}</div></div>
      <div class="dcard"><div class="k">${t('dash.msgs')}</div><div class="v">${msgs}</div><div class="s">${t('dash.msgs_s')}</div>
        <div class="bars" aria-hidden="true">${bars}</div></div>
      <div class="dcard"><div class="k">${t('dash.devices')}</div><div class="v">${online}<span style="font-size:13px;color:var(--mut);font-weight:500"> / ${total}</span></div>
        <div class="ringstat" title="অনলাইন">
          <svg viewBox="0 0 54 54"><circle class="track" cx="27" cy="27" r="${r}"/><circle class="val" cx="27" cy="27" r="${r}" stroke-dasharray="${c}" stroke-dashoffset="${off}"/></svg>
          <b>${pct}%</b>
        </div></div>
      <div class="dcard"><div class="k">${t('dash.perms')}</div><div class="v">${stats.perms||0}</div><div class="s">${t('dash.perms_s')}</div></div>
    </div>`;
  }

  async function buildDash(){
    try{
      const [chats, devs] = await Promise.all([
        api('/bb/api/chats?q=').catch(()=>[]),
        api('/bb/api/devices').catch(()=>({devices:[],caps:{}}))
      ]);
      const list=Array.isArray(chats)?chats:[];
      let msgs=0;
      // lightweight: use list length only; avoid N+1
      msgs = list.reduce((a,c)=>a+(c.msg_count||c.messages?.length||0),0) || list.length*2;
      const devices=(devs.devices||[]).filter(d=>d.status!=='revoked'&&d.status!=='denied');
      const online=devices.filter(d=>d.online&&d.status==='approved').length;
      let perms=0;
      devices.forEach(d=>{if(d.perms) Object.values(d.perms).forEach(m=>{if(m&&m!=='off'&&m!=='ask')perms++})});
      return dashHTML({chats:list.length,msgs,online,devices:devices.length,perms});
    }catch(e){return dashHTML({})}
  }

  window.bbBuildDash = buildDash;
  window.bbRefreshLivebar = refreshLivebar;
  window.bbObserveReveals = observeReveals;

  // Enhance agent steps: mark running
  const _stepEl = window.stepEl;
  // will patch after bb2 loads — see boot

  function boot(){
    ensureBg();
    observeReveals();
    patchThinking();
    // livebar under composer top? insert above #comp if app shell
    if(document.getElementById('main') && !document.getElementById('livebar')){
      const lb=document.createElement('div');lb.id='livebar';
      const scroll=document.getElementById('scroll');
      if(scroll) scroll.parentNode.insertBefore(lb, scroll.nextSibling);
      else document.getElementById('comp')?.before(lb);
      refreshLivebar();
      setInterval(refreshLivebar, 12000);
    }
    // patch thinking HTML used in run()
    if(typeof window!=='undefined'){
      const origRun = window.run;
      // can't easily wrap without replacing — index uses inline string; expose replace helper used via MutationObserver
      const mo=new MutationObserver(muts=>{
        muts.forEach(m=>m.addedNodes.forEach(n=>{
          if(n.nodeType!==1)return;
          const st=n.querySelector?.('.status:not(.think)')||(n.classList?.contains('status')&&!n.classList.contains('think')?n:null);
          if(st && st.querySelector('.dots') && !st.classList.contains('think')){
            const lab=st.querySelector('span:last-child')?.textContent||t('app.thinking');
            st.outerHTML=thinkHTML(lab);
          }
          if(n.classList?.contains('st')||n.querySelector?.('.st')){
            // timeline already CSS-animated
          }
        }));
      });
      const root=document.getElementById('msgs')||document.body;
      mo.observe(root,{childList:true,subtree:true});
    }
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot);
  else boot();
})();
