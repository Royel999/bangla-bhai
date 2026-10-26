"""Memory, Activity/approvals, router status pages & APIs."""
import time, json, asyncio, traceback
from fastapi import Request
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
import memory as MEM, actlog as AL, router as RT
def setup(app,H):
    need=H["need"]; need_admin=H["need_admin"]; AG=H["AG"]
    @app.on_event("startup")
    async def _resume():
        try: r=AG.resume_all(); r and H["audit"](ev="tasks_resumed",items=r)
        except Exception as e: H["audit"](ev="resume_err",err=str(e)[:200])
        asyncio.get_running_loop().run_in_executor(None,MEM._embedder)   # warm local embedder
    @app.exception_handler(Exception)
    async def _any(request,exc):
        H["audit"](ev="server_error",path=request.url.path,err=repr(exc)[:300])
        return JSONResponse({"error":"Something went wrong. Please try again. / কিছু একটা ভুল হয়েছে, আবার চেষ্টা করুন।"},500)
    # ---------- memory ----------
    @app.get("/bb/api/memory")
    def mem_list(request:Request):
        u=need(request); st=H["get_settings"](u); return {"enabled":bool(st.get("memory",True)),"items":MEM.list_(u)}
    @app.post("/bb/api/memory")
    async def mem_add(request:Request):
        u=need(request); b=await request.json()
        if not H["rate_ok"](f"mem:{u}",60,3600): return JSONResponse({"error":"Too many changes"},429)
        i=await asyncio.to_thread(MEM.add,u,str(b.get("text",""))[:400],"note","manual")
        return {"ok":bool(i),"id":i}
    @app.put("/bb/api/memory/{mid}")
    async def mem_upd(request:Request,mid:int):
        u=need(request); b=await request.json(); ok=await asyncio.to_thread(MEM.update,u,mid,str(b.get("text",""))[:400])
        return {"ok":ok} if ok else JSONResponse({"error":"not found"},404)
    @app.delete("/bb/api/memory/{mid}")
    def mem_del(request:Request,mid:int):
        u=need(request); ok=MEM.delete(u,mid); return {"ok":ok} if ok else JSONResponse({"error":"not found"},404)
    @app.delete("/bb/api/memory")
    def mem_clear(request:Request):
        u=need(request); return {"ok":True,"deleted":MEM.clear(u)}
    # ---------- activity & approvals ----------
    @app.get("/bb/api/activity")
    def act_list(request:Request,kind:str=""):
        u=need(request); return {"items":AL.list_(u,200,kind or None),"approvals":AL.appr_list(u,"pending"),"tasks":AL.tasks_list(u)}
    @app.delete("/bb/api/activity")
    def act_clear(request:Request):
        u=need(request); return {"ok":True,"deleted":AL.clear(u)}
    @app.post("/bb/api/approvals/{aid}")
    async def appr_decide(request:Request,aid:str):
        u=need(request); b=await request.json(); a=AL.appr_get(aid,u)
        if not a or a["status"]!="pending": return JSONResponse({"error":"This request is no longer waiting."},404)
        ok=AG.decide(a["task"],aid,"yes" if b.get("ok") else "no")
        if not ok: AL.appr_close(aid,"expired"); return JSONResponse({"error":"This request expired."},410)
        return {"ok":True}
    # ---------- router (owner) ----------
    @app.get("/bb/api/router")
    def rt_status(request:Request):
        need_admin(request); now=time.time()
        return {"chain":[{"id":k,"name":v[0],"configured":bool(v[2]),"cooldown":max(0,int(RT.COOL.get(k,0)-now)),"tier":"user" if k in RT.DEFAULT else "dev","flag_on":RT.allowed(k)} for k,v in RT.CHAIN.items()],"stats":RT.STATS}
    @app.post("/bb/api/router/selftest")
    async def rt_test(request:Request):
        """owner-only: simulate failures on chosen providers, run one real call, return the trace."""
        need_admin(request); b=await request.json()
        fail={k:str(v) for k,v in (b.get("fail") or {}).items() if k in("groq","gemini","cf","openrouter")}
        RT.FORCE_FAIL.update(fail); saved=dict(RT.COOL); RT.COOL.clear()
        try:
            n,t,trace=await RT.complete([{"role":"user","content":b.get("prompt") or "Reply with just: OK"}],tries=2,timeout=40)
            return {"ok":True,"model":n,"answer":t[:200],"trace":trace}
        except RT.ModelError as e: return {"ok":False,"error":"all models failed","trace":str(e)[:500]}
        finally:
            for k in fail: RT.FORCE_FAIL.pop(k,None)
            RT.COOL.clear(); RT.COOL.update(saved)
    # ---------- pages ----------
    def shell_page(title_en,title_bn,body_js):
        return HTMLResponse(PAGE.replace("{{T_EN}}",title_en).replace("{{T_BN}}",title_bn).replace("{{JS}}",body_js),headers={"Cache-Control":"no-cache"})
    @app.get("/memory")
    def memory_page(request:Request):
        try: need(request)
        except PermissionError: return RedirectResponse("/login",303)
        return shell_page("Memory","মেমরি",MEM_JS)
    @app.get("/activity")
    def activity_page(request:Request):
        try: need(request)
        except PermissionError: return RedirectResponse("/login",303)
        return shell_page("Activity","কার্যকলাপ",ACT_JS)
PAGE="""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><meta name=theme-color content="#0b1a33">
<link rel=icon href=/bb/static/icon-192.png><title>{{T_EN}} · Bangla Bhai</title><style>
:root{--bg:#0b1a33;--panel:#122442;--tx:#eef2f8;--mut:#8b98b0;--acc:#1e6fd9;--gold:#f4b400;--bd:#243a5c;--red:#e5484d;--ok:#3ecf8e}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.5 Inter,'Hind Siliguri','Noto Sans Bengali',system-ui,sans-serif}
header{display:flex;align-items:center;gap:12px;padding:14px 18px;border-bottom:1px solid var(--bd);position:sticky;top:0;background:var(--bg)}
header nav,header{flex-wrap:wrap}header img{width:34px;height:34px;border-radius:50%}header h1{font-size:18px;margin:0;flex:1}header a,.lang{color:var(--mut);text-decoration:none;font-size:13px;background:none;border:1px solid var(--bd);border-radius:8px;padding:6px 10px;cursor:pointer}
main{max-width:760px;margin:0 auto;padding:18px}.card{background:var(--panel);border:1px solid var(--bd);border-radius:12px;padding:14px;margin:10px 0}
.row{display:flex;gap:10px;align-items:center}.grow{flex:1}.mut{color:var(--mut);font-size:12.5px}
button.b{background:var(--acc);color:#fff;border:0;border-radius:8px;padding:8px 14px;font:inherit;cursor:pointer}button.g{background:transparent;color:var(--tx);border:1px solid var(--bd)}button.r{background:var(--red)}button.ok{background:var(--ok);color:#06210f}
textarea,input,select{width:100%;background:#0b1a33;color:var(--tx);border:1px solid var(--bd);border-radius:8px;padding:9px;font:inherit}
.tag{font-size:11px;padding:2px 8px;border-radius:99px;border:1px solid var(--bd);color:var(--mut)}.high{border-color:var(--red);color:#ff9a9e}.medium{border-color:var(--gold);color:var(--gold)}
.sw{position:relative;width:46px;height:26px;background:var(--bd);border-radius:99px;cursor:pointer;border:0}.sw.on{background:var(--acc)}.sw::after{content:"";position:absolute;top:3px;left:3px;width:20px;height:20px;border-radius:50%;background:#fff;transition:.2s}.sw.on::after{left:23px}
.appr{border-color:var(--gold)}pre{white-space:pre-wrap;word-break:break-word;margin:6px 0;font-size:12.5px;color:#c9d4e6}.empty{color:var(--mut);text-align:center;padding:30px}
.err{color:#ff9a9e}.okc{color:var(--ok)}</style></head><body>
<header><img src=/bb/static/logo.png alt=""><h1 id=ttl></h1><span id=lb></span><a href=/skills id=nsk></a><a href=/schedules id=nsc></a><a href=/memory id=nm></a><a href=/activity id=na></a><a href=/team id=ntm></a><a href=/account id=nac></a><a href=/app id=nb></a></header>
<main id=m></main><script src=/bb/static/px.js></script><script>
const L=PXL;const T=TX;function setL(x){pxSetLang(x)}
function hdr(){document.documentElement.lang=L;ttl.textContent=T('{{T_EN}}','{{T_BN}}');lb.innerHTML=pxSelect();document.title=T('{{T_EN}}','{{T_BN}}')+' · Bangla Bhai';ntm.textContent=T('Team','টিম');nm.textContent=T('Memory','মেমরি');na.textContent=T('Activity','কার্যকলাপ');nb.textContent=T('← App','← অ্যাপ');nsk.textContent=T('Skills','স্কিল');nsc.textContent=T('Schedules','শিডিউল');nac.textContent=T('Account','অ্যাকাউন্ট')}
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function api(u,o={}){const r=await fetch(u,{credentials:'same-origin',headers:{'Content-Type':'application/json'},...o});let j={};try{j=await r.json()}catch(e){};if(!r.ok)throw new Error(j.error||T('Something went wrong','কিছু ভুল হয়েছে'));return j}
const when=t=>new Date(t*1000).toLocaleString({bn:'bn-BD',hi:'hi-IN',ar:'ar',ur:'ur-PK',es:'es',fr:'fr',zh:'zh-CN'}[L]||'en-GB',{dateStyle:'medium',timeStyle:'short'});
{{JS}}
hdr();render();</script></body></html>"""
MEM_JS="""
let D={enabled:true,items:[]};
async function load(){D=await api('/bb/api/memory')}
async function render(){try{await load()}catch(e){m.innerHTML='<div class="card err">'+esc(e.message)+'</div>';return}
m.innerHTML=`<div class=card><div class=row><div class=grow><b>${T('Use memory','মেমরি ব্যবহার করো')}</b><div class=mut>${T('Bangla Bhai remembers facts and preferences from your chats and uses them in new chats. Stored privately on our server, only for you.','বাংলা ভাই আপনার চ্যাট থেকে তথ্য ও পছন্দ মনে রাখে এবং নতুন চ্যাটে ব্যবহার করে। শুধু আপনার জন্য, আমাদের সার্ভারে গোপনে রাখা।')}</div></div><button class="sw ${D.enabled?'on':''}" onclick="tog()" aria-label=toggle></button></div></div>
<div class=card><div class=row><input id=nw class=grow placeholder="${T('Add something to remember…','মনে রাখার মতো কিছু লিখুন…')}"><button class=b onclick=add()>${T('Add','যোগ')}</button></div></div>
<div class="row mut" style="padding:6px 2px"><span class=grow>${D.items.length} ${T('memories','টি স্মৃতি')}</span>${D.items.length?`<button class="b g" onclick=clr()>${T('Delete all','সব মুছুন')}</button>`:''}</div>
${D.items.map(x=>`<div class=card id=c${x.id}><div class=row><div class=grow><div id=t${x.id}>${esc(x.text)}</div><div class=mut>${x.kind==='note'?T('added by you','আপনি যোগ করেছেন'):T('learned from chat','চ্যাট থেকে শেখা')} · ${when(x.updated)}</div></div>
<button class="b g" onclick="ed(${x.id})">${T('Edit','এডিট')}</button><button class="b r" onclick="del(${x.id})">${T('Delete','মুছুন')}</button></div></div>`).join('')||`<div class=empty>${T('Nothing remembered yet.','এখনো কিছু মনে রাখা হয়নি।')}</div>`}`}
async function tog(){await api('/bb/api/settings',{method:'PUT',body:JSON.stringify({memory:!D.enabled})});render()}
async function add(){const v=nw.value.trim();if(!v)return;await api('/bb/api/memory',{method:'POST',body:JSON.stringify({text:v})});render()}
async function del(i){if(!confirm(T('Delete this memory?','এই স্মৃতি মুছবেন?')))return;await api('/bb/api/memory/'+i,{method:'DELETE'});render()}
async function clr(){if(!confirm(T('Delete ALL memories?','সব স্মৃতি মুছবেন?')))return;await api('/bb/api/memory',{method:'DELETE'});render()}
function ed(i){const el=document.getElementById('t'+i);const v=el.textContent;el.innerHTML=`<textarea id=e${i} rows=2>${esc(v)}</textarea><button class=b style="margin-top:6px" onclick="sv(${i})">${T('Save','সেভ')}</button>`}
async function sv(i){await api('/bb/api/memory/'+i,{method:'PUT',body:JSON.stringify({text:document.getElementById('e'+i).value})});render()}
"""
ACT_JS="""
let D={items:[],approvals:[],tasks:[]},F='';
const KN={agent:['Agent task','এজেন্ট কাজ'],shell:['Shell','শেল'],browse:['Browse/search','ব্রাউজ/সার্চ'],device:['Device','ডিভাইস'],media:['Media','মিডিয়া'],approval:['Approval','অনুমতি'],tool:['Tool','টুল']};
const kn=k=>T(...(KN[k]||[k,k]));
async function render(){try{D=await api('/bb/api/activity'+(F?'?kind='+F:''))}catch(e){m.innerHTML='<div class="card err">'+esc(e.message)+'</div>';return}
m.innerHTML=(D.approvals.length?`<h3>${T('Waiting for your approval','আপনার অনুমতির অপেক্ষায়')}</h3>`+D.approvals.map(a=>`<div class="card appr"><div class=row><b class=grow>🔐 ${esc(a.tool)}</b><span class="tag ${a.risk}">${T(a.risk+' risk',{high:'উচ্চ ঝুঁকি',medium:'মাঝারি ঝুঁকি',low:'কম ঝুঁকি'}[a.risk]||a.risk)}</span></div>
<pre>${esc(a.args)}</pre>${a.why?`<div class=mut>${esc(a.why)}</div>`:''}<div class=row style="margin-top:8px"><button class="b ok" onclick="dec('${a.id}',1)">${T('Approve','অনুমতি দিন')}</button><button class="b r" onclick="dec('${a.id}',0)">${T('Deny','বাতিল')}</button><span class=mut>${when(a.created)}</span></div></div>`).join(''):'')+
`<div class=row style="margin:12px 0;gap:6px;flex-wrap:wrap">${['','agent','shell','browse','device','media','approval'].map(k=>`<button class="b ${F===k?'':'g'}" onclick="F='${k}';render()">${k?kn(k):T('All','সব')}</button>`).join('')}<span class=grow></span><button class="b g" onclick=clr()>${T('Clear log','লগ মুছুন')}</button></div>`+
(D.items.map(x=>`<div class=card><div class=row><span class=tag>${kn(x.kind)}</span><b class=grow>${esc(x.tool)}</b><span class="${x.ok?'okc':'err'}">${x.ok?'✓':'✗'}</span><span class=mut>${when(x.ts)}</span></div><pre>${esc(x.input)}</pre>${x.result?`<div class=mut>→ ${esc(x.result)}</div>`:''}</div>`).join('')||`<div class=empty>${T('No activity yet.','এখনো কোনো কার্যকলাপ নেই।')}</div>`)}
async function dec(id,ok){try{await api('/bb/api/approvals/'+id,{method:'POST',body:JSON.stringify({ok:!!ok})})}catch(e){alert(e.message)}render()}
async function clr(){if(!confirm(T('Clear the activity log?','কার্যকলাপের লগ মুছবেন?')))return;await api('/bb/api/activity',{method:'DELETE'});render()}
setInterval(()=>{if(!document.hidden)render()},5000);
"""
