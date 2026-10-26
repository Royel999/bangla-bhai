from urllib.parse import quote
import os, json, time, re, asyncio, hmac, httpx, sqlite3, uuid, io
from fastapi import FastAPI, Request, Form, UploadFile, File, WebSocket
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
BASE=os.path.expanduser('~/bangla_bhai'); S=os.path.expanduser('~/.secrets'); ENVF=S+'/bangla_bhai.env'
def env(f):
    d={}
    for l in open(f):
        if '=' in l: k,v=l.strip().split('=',1); d[k]=v.strip().strip('"')
    return d
CFG=env(ENVF); K={**env(S+'/groq.env'),**env(S+'/gemini.env'),**env(S+'/openrouter.env')}
AUDIT=BASE+'/audit.jsonl'
def audit(**k):
    import auditdb; auditdb.write(**k)
# ---------- DB ----------
DB=BASE+'/data.db'
def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
with db() as c:
    c.executescript("""create table if not exists chats(id text primary key,user text,title text,pinned int default 0,project text,created real,updated real);
create table if not exists messages(id integer primary key autoincrement,chat_id text,role text,content text,model text,advisors text,created real);
create table if not exists settings(user text primary key,data text);
create table if not exists projects(id text primary key,user text,name text,instructions text,created real);""")
DEFAULT_SETTINGS={"theme":"dark","accent":"blue","lang":"en","font":16,"instructions":"","memory":True,"memory_notes":"","model":"auto","council":False}
def get_settings(u):
    with db() as c: r=c.execute("select data from settings where user=?",(u,)).fetchone()
    return {**DEFAULT_SETTINGS,**(json.loads(r["data"]) if r else {})}
# ---------- models ----------
GROQ="https://api.groq.com/openai/v1/chat/completions"; GEM="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"; OR="https://openrouter.ai/api/v1/chat/completions"
MODELS={
 "groq:openai/gpt-oss-120b":("Groq · GPT-OSS 120B",GROQ,K.get("GROQ_API_KEY"),"openai/gpt-oss-120b"),
 "groq:openai/gpt-oss-20b":("Groq · GPT-OSS 20B (দ্রুত)",GROQ,K.get("GROQ_API_KEY"),"openai/gpt-oss-20b"),
 "groq:qwen/qwen3.8-27b":("Groq · Qwen 3.8 27B",GROQ,K.get("GROQ_API_KEY"),"qwen/qwen3.8-27b"),
 "gemini:gemini-3.8-flash":("Google · Gemini 3.8 Flash",GEM,K.get("GEMINI_API_KEY"),"gemini-3.8-flash"),
 "gemini:gemini-3.1-flash-lite":("Google · Gemini 3.1 Flash Lite",GEM,K.get("GEMINI_API_KEY"),"gemini-3.1-flash-lite"),
 "openrouter:openrouter/free":("OpenRouter · Auto Free",OR,K.get("OPENROUTER_API_KEY"),"openrouter/free"),
}
AUTO=["groq:openai/gpt-oss-120b","gemini:gemini-3.8-flash","gemini:gemini-3.1-flash-lite","openrouter:openrouter/free","groq:openai/gpt-oss-20b"]
ADVISORS=["gemini:gemini-3.1-flash-lite","openrouter:openrouter/free","groq:qwen/qwen3.8-27b"]
LANG_NAMES={"en":"English","bn":"Bangla (Bengali)","hi":"Hindi","ar":"Arabic","ur":"Urdu","es":"Spanish","fr":"French","zh":"Chinese (Simplified)"}
_I18N={}
def i18n(lang):
    lang=lang if lang in LANG_NAMES else "en"
    if lang not in _I18N:
        try: _I18N[lang]=json.load(open(os.path.join(BASE,"static","i18n",lang+".json"),encoding="utf-8"))
        except Exception: _I18N[lang]={}
    return _I18N[lang]
def tr(lang,key,**kw):
    s=i18n(lang).get(key) or i18n("en").get(key) or key
    for k,v in kw.items(): s=s.replace("{"+k+"}",str(v))
    return s
def is_owner_uid(uid): return bool(uid) and str(uid)==str(CFG["BB_USER"])
def lang_rule(st):
    name=LANG_NAMES.get(st.get("lang","en"),"English")
    return (f"LANGUAGE: The user's chosen app language is {name}. Reply in {name} by default. "
            "If the user writes their message in a different language, reply in the language they wrote in. "
            "Keep code, commands and proper nouns as-is.")
def addr_rule(uid):
    if is_owner_uid(uid):
        return ("ADDRESS: This user is the owner. Address him as 'Royal' (when replying in Bangla write 'রয়েল'). "
                "Never call him 'আব্বা'/'Abba'.")
    return "ADDRESS: Address the user politely (you / their name). Never call them 'Royal', 'রয়েল' or 'আব্বা'."
def persona(st,proj_instr="",uid=None,mems=None):
    try:
        devs=AG.devices(); dlist=", ".join(f"{d['name']} ({d['id']}, {d['kind']}, {'online' if d.get('online') else 'offline'}, {d['status']})" for d in devs)
    except Exception: dlist="(not loaded)"
    p=("You are 'Bangla Bhai', the real AI agent of Royal Universe — not just a chatbot. "+lang_rule(st)+" "+addr_rule(uid)+" "
       "You have real tools (shell, browse, web_search, screenshot, camera, mic) and paired devices: "+dlist+". "
       "Never claim you cannot run commands on devices or have no tools — when an action is needed the system routes it to the agent loop. "
       "You CAN generate and edit images: when the user attaches a photo and asks to edit it (or asks for a new picture), the system runs a free image model (FLUX Kontext / FLUX.2 / Pollinations) and shows the result. Never say you cannot edit or create images; if an edit failed, ask them to resend the photo with the instruction. When editing a person's photo always keep their face and identity unchanged. "
       "Be concise and honest; use Markdown. Never send, pay or delete without permission.")
    if st.get("instructions"): p+="\n\nOwner's custom instructions:\n"+st["instructions"]
    if st.get("memory") and st.get("memory_notes"): p+="\n\nThings to remember about the user:\n"+st["memory_notes"]
    if mems: p+="\n\nLong-term memory about this user (use naturally when relevant; never mention you have a memory list unless asked):\n"+"\n".join("- "+m for m in mems)
    if proj_instr: p+="\n\nProject instructions:\n"+proj_instr
    return p
def clean(t): return re.sub(r"<think>.*?</think>","",t or "",flags=re.S).strip()
def _mres(mid): return MODELS.get(mid) or _BYOK_CTX.get(mid)
_BYOK_CTX={}
def _spec(mid):
    r=_mres(mid)
    return (mid,(r[0],r[1],r[2],r[3],"oa")) if r else None
async def call(mid,msgs,tries=1,timeout=45):
    sp=_spec(mid)
    if not sp: return None
    try: n,t,_=await RT.complete(msgs,chain=[],extra=[sp],timeout=timeout,tries=max(1,tries)); return n,t
    except RT.ModelError: return None
HARD=re.compile(r"(পরিকল্পনা|plan|কোড|code|বিশ্লেষণ|analy|তুলনা|compare|সিদ্ধান্ত|decide|strategy|কৌশল)",re.I)
# ---------- app ----------
app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None); app.add_middleware(SessionMiddleware,secret_key=CFG["BB_SESSION_SECRET"],https_only=os.environ.get("BB_INSECURE_COOKIE")!="1",same_site="lax",max_age=86400*30)
app.mount("/bb/static",StaticFiles(directory=BASE+"/static"),name="static")
import agent as AG
import router as RT, memory as MEM, actlog as AL, plans as PL
OWNER_EMAIL=os.environ.get("BB_OWNER_EMAIL","skbadol3210@gmail.com").strip().lower()
@app.middleware("http")
async def _sec(request,call_next):
    # M6: anything arriving through the tunnel must carry the Worker's edge secret; box-local calls (no forwarding headers) are allowed.
    _e=CFG.get("BB_EDGE_SECRET","")
    if _e and request.url.path!="/bb/health" and (request.headers.get("x-forwarded-for") or request.headers.get("x-forwarded-host") or request.headers.get("ngrok-skip-browser-warning")) \
       and not hmac.compare_digest(request.headers.get("x-bb-edge",""),_e):
        return Response("Please use https://banglabhai.dpdns.org",403,media_type="text/plain")
    if request.url.path=="/bb/static/install.js" and not FL.on("feat_pwa_install"):
        return Response("/* install disabled by admin */if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(function(){});document.addEventListener('DOMContentLoaded',function(){document.querySelectorAll('[data-install-btn],#installBtn').forEach(function(b){b.style.display='none'})});",media_type="application/javascript",headers={"Cache-Control":"no-cache"})
    r=await call_next(request)
    _p=request.url.path
    if not (_p.startswith("/webui") or _p.startswith(WEBUI_PREFIXES)) or _p.startswith("/admin/panel"):
        r.headers.setdefault("Content-Security-Policy","frame-ancestors 'self'; base-uri 'self'; object-src 'none'; form-action 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://static.cloudflareinsights.com; worker-src 'self'")
    if request.url.path.startswith("/bb/static/shots/"): r.headers["Cache-Control"]="private, no-store"
    elif _p.startswith("/bb/static/") and r.status_code==200 and "cache-control" not in r.headers:
        if _p.endswith("/sw.js"): r.headers["Cache-Control"]="no-cache"
        elif _p.rsplit(".",1)[-1].lower() in ("png","jpg","jpeg","webp","svg","ico","woff","woff2","ttf"): r.headers["Cache-Control"]="public, max-age=604800, stale-while-revalidate=86400"
        else: r.headers["Cache-Control"]="public, max-age=600, stale-while-revalidate=86400"
    r.headers.setdefault("Strict-Transport-Security","max-age=31536000")
    r.headers.setdefault("X-Frame-Options","SAMEORIGIN"); r.headers.setdefault("X-Content-Type-Options","nosniff")
    r.headers.setdefault("Referrer-Policy","strict-origin-when-cross-origin")
    r.headers.setdefault("Permissions-Policy","camera=(self), microphone=(self), geolocation=(self)")
    r.headers.setdefault("Content-Security-Policy","frame-ancestors 'self'; base-uri 'self'; object-src 'none'; form-action 'self'")
    return r
import auth as AU
import flags as FL
def user(r):
    u=r.session.get("u")
    if not u: return None
    if u==CFG["BB_USER"]: return u
    # registered email users
    try:
        import auth as AU
        if AU.user_row(u): return u
    except Exception: pass
    return None
def is_admin(r): return r.session.get("role")=="owner" or r.session.get("u")==CFG["BB_USER"]
CSS="""<meta name=viewport content="width=device-width,initial-scale=1"><link rel=manifest href=/manifest.webmanifest><meta name=theme-color content="#0b1a33"><link rel=icon href=/bb/static/icon-192.png><link rel=stylesheet href=/bb/static/viz.css>
<link href="https://fonts.googleapis.com/css2?family=Hind+Siliguri:wght@400;500;600;700&family=Inter:wght@400;500;600;700&family=Noto+Sans+Bengali:wght@400;500;600;700&display=swap" rel="stylesheet"><style>
:root{--bg:#0b1a33;--panel:#122442;--tx:#eef2f8;--mut:#8b98b0;--acc:#1e6fd9;--gold:#f4b400;--bd:#243a5c;--crimson:#d62839}
body{margin:0;font-family:'Hind Siliguri','Noto Sans Bengali',Inter,system-ui,sans-serif;background:var(--bg);color:var(--tx);min-height:100vh;-webkit-font-smoothing:antialiased}
.box{max-width:400px;margin:8vh auto 0;background:var(--panel);border:1px solid var(--bd);border-radius:16px;padding:28px;box-shadow:0 16px 48px #0006;animation:up .35s ease}
@keyframes up{from{opacity:0;transform:translateY(10px)}}
label{display:block;margin:14px 0 5px;font-size:14px;color:var(--mut)}input{width:100%;box-sizing:border-box;padding:12px;border-radius:10px;border:1px solid var(--bd);background:#0b1a33;color:var(--tx);font-size:16px;font-family:inherit}
input:focus{outline:2px solid var(--acc);border-color:var(--acc)}button{margin-top:16px;width:100%;padding:13px;border:0;border-radius:10px;background:var(--acc);color:#fff;font-size:16px;font-weight:650;cursor:pointer;font-family:inherit;box-shadow:0 2px 12px #1e6fd944}
a{color:#8fb0ff}.lhero{text-align:center;margin-bottom:8px}
.holo{width:120px;height:120px;margin:0 auto;position:relative;border-radius:50%}
.holo::before{content:"";position:absolute;inset:-5px;border-radius:50%;background:conic-gradient(from 210deg,#1e6fd9,#3d8bfd,#f4b400,#1e6fd9,#3d8bfd);box-shadow:0 0 24px #1e6fd955,0 0 40px #f4b40022,0 8px 24px #0005;animation:ringShimmer 4.8s ease-in-out infinite}
.holo-inner{position:absolute;inset:2px;border-radius:50%;background:var(--bg);z-index:1}
.holo img{position:relative;z-index:2;width:100%;height:100%;border-radius:50%;object-fit:contain;display:block}
.holo::after{content:"";position:absolute;inset:2px;border-radius:50%;z-index:3;pointer-events:none;background:radial-gradient(circle at 30% 22%,#fff3,transparent 45%)}
.wmimg{width:220px;max-width:78%;margin-top:12px}
@keyframes ringShimmer{0%,100%{opacity:.75;filter:brightness(1)}50%{opacity:1;filter:brightness(1.1)}}
@media(prefers-reduced-motion:reduce){.holo::before{animation:none}}
.foot{text-align:center;color:var(--mut);font-size:12px;margin-top:20px}
.tabs{display:flex;gap:8px;margin:12px 0 16px}.ton,.toff{flex:1;padding:10px;border-radius:10px;border:1px solid var(--bd);font-size:13px;cursor:pointer;font-family:inherit}
.ton{background:var(--acc);color:#fff;border-color:var(--acc)}.toff{background:#0b1a33;color:var(--mut)}.err{color:#ff7a8a}.ok{color:#7dffa8}h3{margin:0 0 8px;font-weight:650;letter-spacing:-.01em}</style>"""
BR='<div class=lhero><div class=holo><div class=holo-inner></div><img src=/bb/static/logo.png alt="Bangla Bhai"></div><img class=wmimg src=/bb/static/wordmark.svg alt="Bangla Bhai"></div>'
def page(body,lang="en"): return HTMLResponse(f"<!doctype html><html lang={lang} dir={'rtl' if lang in ('ar','ur') else 'ltr'}><head><meta charset=utf-8><title>Bangla Bhai</title>{CSS}</head><body>{body}<script src=/bb/static/i18n.js></script><script src=/bb/static/viz.js></script><script src=/bb/static/install.js defer></script></body></html>")

@app.get("/login")
def login_page(request:Request, e:str="", m:str="", email:str="", lang:str=""):
    L=lang if lang in LANG_NAMES else (request.cookies.get("bb_lang") if request.cookies.get("bb_lang") in LANG_NAMES else "en")
    T=lambda k: tr(L,k)
    import html as _h
    email=_h.escape(email or "")
    err={"otp":T("login.err_otp"),"send":T("login.err_send")}.get(e,"")
    okmsg=T("login.sent") if m=="sent" else _h.escape(m or "")
    return page(f"""<div class=box>
<div style="display:flex;justify-content:flex-end" data-lang-picker></div>
{BR}
<h3 style="text-align:center" data-i18n="login.welcome">{T("login.welcome")}</h3>
<p style="text-align:center;color:var(--mut);font-size:14px;margin:0 0 14px" data-i18n="login.sub">{T("login.sub")}</p>
{'<p class=err>'+err+'</p>' if err else ''}
{'<p class=ok>'+okmsg+'</p>' if okmsg else ''}
<form method=post action=/auth/otp/request>
  <label data-i18n="login.email">{T("login.email")}</label>
  <input name=email type=email required value="{email}" placeholder="you@gmail.com" autocomplete=email>
  <button type=submit data-i18n="login.send">{T("login.send")}</button>
</form>
<form method=post action=/auth/otp/verify style="margin-top:14px">
  <input type=hidden name=email value="{email}">
  <label data-i18n="login.code">{T("login.code")}</label>
  <input name=code inputmode=numeric pattern="[0-9]{{6}}" maxlength=6 placeholder="123456" autocomplete=one-time-code>
  <button type=submit data-i18n="login.login">{T("login.login")}</button>
</form>
<button type=button data-install-btn style="display:none;align-items:center;justify-content:center;gap:8px;width:100%;margin:14px 0 4px;padding:12px;border-radius:10px;border:1px solid #f4b400;background:transparent;color:#f4b400;font-weight:700;font-size:15px;cursor:pointer">📲 <span data-i18n="app.install_btn">Install App</span></button>
<p style="font-size:12px;opacity:.7;margin-top:10px" data-i18n="login.note">{T("login.note")}</p>
<div class=foot><a href=/ data-i18n="nav.home">{T("nav.home")}</a> · <a href=/privacy data-i18n="nav.privacy">{T("nav.privacy")}</a> · ♛ © 2026 Royal Universe · <a href=/admin style="opacity:.45" data-i18n="admin.link">{T("admin.link")}</a></div>
</div>""",L)

ADMIN_CSS="""<style>.abox{border:1px solid #f4b400 !important;box-shadow:0 0 0 1px rgba(244,180,0,.25),0 20px 60px rgba(0,0,0,.5) !important}
.abadge{display:flex;align-items:center;justify-content:center;gap:8px;margin:4px 0 12px;color:#f4b400;font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:13px}
.abadge svg{width:22px;height:22px}.abox button[type=submit]{background:#f4b400 !important;color:#0b1a33 !important;font-weight:700}
.abox input:focus{border-color:#f4b400 !important}.sep{display:flex;align-items:center;gap:10px;color:var(--mut);font-size:12px;margin:18px 0 8px}.sep:before,.sep:after{content:"";flex:1;height:1px;background:var(--bd)}</style>"""
SHIELD='<svg viewBox="0 0 24 24" fill="none" stroke="#f4b400" stroke-width="2"><path d="M12 2l8 3v6c0 5-3.5 9.5-8 11-4.5-1.5-8-6-8-11V5z"/><path d="M9 12l2 2 4-4"/></svg>'
SAFE_NEXT=("/admin/login-requests","/admin/panel","/admin/dev")
@app.get("/admin")
@app.get("/admin/login")
def admin_page(request:Request, e:str="", m:str="", lang:str="", next:str=""):
    if next in SAFE_NEXT: request.session["next"]=next
    if is_admin(request) and not e and not m: return RedirectResponse(request.session.pop("next",None) or "/app",303)
    L=lang if lang in LANG_NAMES else (request.cookies.get("bb_lang") if request.cookies.get("bb_lang") in LANG_NAMES else "en")
    T=lambda k: tr(L,k)
    import html as _h
    err={"1":T("login.err_pw"),"otp":T("login.err_otp"),"send":T("login.err_send")}.get(e,"")
    okmsg=T("login.sent") if m=="sent" else (_h.escape(m) if m else "")
    return page(ADMIN_CSS+f"""<div class="box abox">
<div style="display:flex;justify-content:flex-end" data-lang-picker></div>
{BR}
<div class=abadge>{SHIELD}<span data-i18n="admin.title">{T("admin.title")}</span></div>
<p style="text-align:center;color:var(--mut);font-size:13px;margin:0 0 12px" data-i18n="admin.sub">{T("admin.sub")}</p>
{'<p class=err>'+err+'</p>' if err else ''}{'<p class=ok>'+okmsg+'</p>' if okmsg else ''}
<form method=post action=/login>
  <label for=username data-i18n="login.username">{T("login.username")}</label><input id=username name=username autocomplete=username autocapitalize=none>
  <label for=password data-i18n="login.password">{T("login.password")}</label><input id=password name=password type=password autocomplete=current-password>
  <button type=submit data-i18n="login.admin_btn">{T("login.admin_btn")}</button>
</form>
<div class=sep data-i18n="admin.or">{T("admin.or")}</div>
<form method=post action=/auth/otp/request><input type=hidden name=src value=admin><input type=hidden name=email value="{OWNER_EMAIL}">
  <button type=submit data-i18n="admin.send_owner">{T("admin.send_owner")}</button></form>
<form method=post action=/auth/otp/verify style="margin-top:10px"><input type=hidden name=src value=admin><input type=hidden name=email value="{OWNER_EMAIL}">
  <label data-i18n="login.code">{T("login.code")}</label>
  <input name=code inputmode=numeric pattern="[0-9]{{6}}" maxlength=6 placeholder="123456" autocomplete=one-time-code>
  <button type=submit data-i18n="login.login">{T("login.login")}</button></form>
<button type=button data-install-btn style="display:none;align-items:center;justify-content:center;gap:8px;width:100%;margin:14px 0 4px;padding:12px;border-radius:10px;border:1px solid #f4b400;background:transparent;color:#f4b400;font-weight:700;font-size:15px;cursor:pointer">📲 <span data-i18n="app.install_btn">Install App</span></button>
<div class=foot><a href=/login data-i18n="admin.back">{T("admin.back")}</a> · ♛ Royal Universe</div>
</div>""",L)

@app.post("/login")
def do_login(request:Request,username:str=Form(""),password:str=Form("")):
    if not rate_ok("login:"+cip(request),8,600): audit(ev="login_ratelimited"); return RedirectResponse("/admin?e=1",303)
    ok=hmac.compare_digest(username.strip(),CFG["BB_USER"]) and AU.owner_pw_ok(password,CFG.get("BB_PASSWORD",""))
    audit(ev="login",ok=ok,via="admin")
    if not ok: return RedirectResponse("/admin?e=1",303)
    AU.ensure_owner()
    request.session["u"]=CFG["BB_USER"]; request.session["role"]="owner"
    return RedirectResponse(request.session.pop("next",None) or "/app",303)

@app.post("/auth/otp/request")
async def otp_req(request:Request, email:str=Form(""), src:str=Form("")):
    email=AU.normalize_email(email)
    LP="/admin" if src=="admin" else "/login"
    if not (rate_ok("otp:"+cip(request),5,900) and rate_ok("otpm:"+email,6,900)):
        return RedirectResponse(LP+"?e=send&m="+quote("Too many requests, try later"),303)
    if not FL.on("signups_open") and not AU.may_login(email):
        return RedirectResponse(LP+"?e=send&m="+quote(FL.OFF_MSG["signups_open"]),303)
    try:
        code=AU.create_otp(email)
        ok,via,detail=AU.send_otp_email(email, code)
    except ValueError as e:
        return RedirectResponse(LP+"?e=send&m="+quote(str(e)),303)
    if not ok:
        try:
            with db() as c:
                c.execute("create table if not exists otp_pending(email text primary key,t real)")
                c.execute("insert or replace into otp_pending values(?,?)",(email,time.time()))
            SJ.notify(CFG["BB_USER"],"🔐 Login code not delivered","A user is waiting for a login code. Open /admin/login-requests","/admin/login-requests")
        except Exception: pass
        msg=("We couldn't email your code right now. The admin has been notified and can approve your login — please try again in a few minutes. / "
             "এই মুহূর্তে কোড ইমেইলে পাঠানো যায়নি। অ্যাডমিনকে জানানো হয়েছে, তিনি আপনার লগইন অনুমোদন করতে পারবেন — কয়েক মিনিট পরে আবার চেষ্টা করুন।")
        return RedirectResponse(f"{LP}?e=send&email={quote(email)}&m="+quote(msg),303)
    # never put code in URL
    return RedirectResponse(f"{LP}?m=sent&email={quote(email)}",303)

@app.post("/auth/otp/verify")
async def otp_ver(request:Request, email:str=Form(""), code:str=Form(""), src:str=Form("")):
    LP="/admin" if src=="admin" else "/login"
    if not rate_ok("otpv:"+cip(request),15,900): return RedirectResponse(LP+"?e=otp&m="+quote("Too many attempts"),303)
    ok,uid=AU.verify_otp(email, code)
    if not ok: return RedirectResponse(f"{LP}?e=otp&email={quote(AU.normalize_email(email))}&m="+quote(str(uid)),303)
    if AU.normalize_email(email)==OWNER_EMAIL:
        AU.ensure_owner(); request.session["u"]=CFG["BB_USER"]; request.session["role"]="owner"; audit(ev="owner_email_login"); return RedirectResponse(request.session.pop("next",None) or "/app",303)
    else:
        request.session["u"]=uid; request.session["role"]="user"
    return RedirectResponse("/app",303)

@app.get("/logout")
def logout(request:Request): request.session.clear(); return RedirectResponse("/",303)
@app.get("/change-password")
def cp_page(request:Request,m:str=""):
    if not user(request): return RedirectResponse("/login",303)
    msg={"ok":"<p class=ok>পাসওয়ার্ড বদলানো হয়েছে</p>","bad":"<p class=err>বর্তমান পাসওয়ার্ড ভুল</p>","mm":"<p class=err>নতুন পাসওয়ার্ড দুটো মেলেনি বা ৮ অক্ষরের কম</p>"}.get(m,"")
    return page(f"""<form class=box method=post action=/change-password>{BR}<h3>পাসওয়ার্ড বদলান</h3>{msg}
<label for=current_password>Current Password</label><input id=current_password name=current_password type=password>
<label for=new_password>New Password</label><input id=new_password name=new_password type=password autocomplete=new-password>
<label for=confirm_password>Confirm New Password</label><input id=confirm_password name=confirm_password type=password autocomplete=new-password>
<button type=submit>Change Password</button><p><a href=/app>← চ্যাটে ফিরুন</a></p></form>""")
@app.post("/change-password")
def cp(request:Request,current_password:str=Form(""),new_password:str=Form(""),confirm_password:str=Form("")):
    if not user(request): return RedirectResponse("/login",303)
    if not is_admin(request): return RedirectResponse("/app",303)
    if not rate_ok("cp:"+cip(request),5,600): return RedirectResponse("/change-password?m=bad",303)
    if not AU.owner_pw_ok(current_password,CFG.get("BB_PASSWORD","")): return RedirectResponse("/change-password?m=bad",303)
    if new_password!=confirm_password or len(new_password)<8: return RedirectResponse("/change-password?m=mm",303)
    AU.set_owner_pw(new_password)  # persistent (DB -> KV backup); env file below kept for box tooling
    CFG["BB_PASSWORD"]=new_password
    _tmp=ENVF+".tmp"; _fd=os.open(_tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(_fd,"w") as _f: _f.write("".join(f"{k}={v}\n" for k,v in CFG.items())); _f.flush(); os.fsync(_f.fileno())
    os.replace(_tmp,ENVF)
    audit(ev="password_changed"); return RedirectResponse("/change-password?m=ok",303)
@app.get("/manifest.webmanifest")
def manifest():
    return JSONResponse({"name":"Bangla Bhai — Royal Universe","short_name":"Bangla Bhai","description":"Bangla Bhai — a multilingual, permission-first AI agent. Chat, run tools and control paired devices with your approval.","start_url":"/app?source=pwa","scope":"/","id":"/app","display":"standalone","background_color":"#0b1a33","theme_color":"#0b1a33",
      "icons":[{"src":"/bb/static/icon-192.png","sizes":"192x192","type":"image/png","purpose":"any"},{"src":"/bb/static/icon-512.png","sizes":"512x512","type":"image/png","purpose":"any"},{"src":"/bb/static/icon-192-maskable.png","sizes":"192x192","type":"image/png","purpose":"maskable"},{"src":"/bb/static/icon-512-maskable.png","sizes":"512x512","type":"image/png","purpose":"maskable"}],"display_override":["standalone","window-controls-overlay"],"lang":"en","dir":"ltr","share_target":{"action":"/app","method":"GET","enctype":"application/x-www-form-urlencoded","params":{"title":"title","text":"text","url":"url"}},"shortcuts":[{"name":"New chat","url":"/app","icons":[{"src":"/bb/static/icon-192.png","sizes":"192x192"}]}]},media_type="application/manifest+json")
@app.get("/.well-known/assetlinks.json")
def assetlinks():
    try: return JSONResponse(json.load(open(BASE+"/deploy/assetlinks.json")),headers={"Cache-Control":"public, max-age=3600"})
    except Exception: return JSONResponse([])
APK_URL="https://github.com/Royel999/bangla-bhai/releases/latest/download/bangla-bhai.apk"
_APK_CACHE="/tmp/bangla-bhai.apk"
async def _apk_file():
    if os.path.exists(_APK_CACHE) and os.path.getsize(_APK_CACHE)>100000 and time.time()-os.path.getmtime(_APK_CACHE)<3600: return _APK_CACHE
    try:
        async with httpx.AsyncClient(follow_redirects=True,timeout=60) as c:
            r=await c.get(APK_URL)
        if r.status_code==200 and r.content[:2]==b"PK":
            tmp=_APK_CACHE+".part"; open(tmp,"wb").write(r.content); os.replace(tmp,_APK_CACHE)
    except Exception: pass
    return _APK_CACHE if os.path.exists(_APK_CACHE) else None
@app.api_route("/download/bangla-bhai.apk",methods=["GET","HEAD"])
@app.api_route("/download/android",methods=["GET","HEAD"])
async def apk_dl():
    p=await _apk_file()
    if not p: return RedirectResponse(APK_URL,302)
    return FileResponse(p,media_type="application/vnd.android.package-archive",filename="bangla-bhai.apk",headers={"Cache-Control":"public, max-age=600"})
@app.get("/sw.js")
def sw():
    return FileResponse(BASE+"/static/sw.js",media_type="application/javascript",headers={"Cache-Control":"no-cache","Service-Worker-Allowed":"/"})
@app.get("/")
def landing(request:Request):
    return FileResponse(BASE+"/static/landing.html",headers={"Cache-Control":"no-cache"})
@app.get("/app")
def home(request:Request):
    if not user(request): return RedirectResponse("/login",303)
    return FileResponse(BASE+"/static/index.html",headers={"Cache-Control":"no-cache"})
@app.get("/pricing")
def pricing(): return FileResponse(BASE+"/static/pricing.html",headers={"Cache-Control":"no-cache"})
@app.get("/privacy")
def privacy(): return FileResponse(BASE+"/static/privacy.html",headers={"Cache-Control":"no-cache"})
@app.get("/terms")
def terms(): return FileResponse(BASE+"/static/terms.html",headers={"Cache-Control":"no-cache"})
@app.get("/docs/api")
def api_docs(): return FileResponse(BASE+"/static/api.html",headers={"Cache-Control":"no-cache"})
@app.get("/bb/api/me")
def me(request:Request):
    u=need(request); row=AU.user_row(u) or {"id":u,"role":"owner" if u==CFG["BB_USER"] else "user","email":None,"name":u}
    return {"id":row.get("id") or u,"email":row.get("email"),"name":row.get("name"),"role":row.get("role") or ("owner" if is_admin(request) else "user")}
def need(request):
    u=user(request)
    if not u: raise PermissionError
    return u
class AdminOnly(Exception): pass
class NotFound(Exception): pass
@app.exception_handler(NotFound)
async def _nf(request,exc): return JSONResponse({"error":"not found"},404)
def need_admin(request):
    u=need(request)
    if not is_admin(request): raise AdminOnly
    return u
_RL={}
def SAFE_EXT(e): e=str(e or 'png').lower(); return e if e in('png','jpg','jpeg','webp','gif','mp4','m4a','ogg','wav') else 'png'
def rate_ok(key,n,win):
    now=time.time()
    try:
        with db() as c:
            c.execute("create table if not exists ratelimit(k text, t real)")
            c.execute("delete from ratelimit where t<?",(now-86400,))
            cnt=c.execute("select count(*) from ratelimit where k=? and t>?",(key,now-win)).fetchone()[0]
            if cnt>=n: return False
            c.execute("insert into ratelimit values(?,?)",(key,now)); return True
    except Exception:
        q=[t for t in _RL.get(key,[]) if now-t<win]
        if len(q)>=n: _RL[key]=q; return False
        q.append(now); _RL[key]=q; return True
import hmac as _hm
_EDGE=CFG.get("BB_EDGE_SECRET","")
def cip(r):
    sock=(r.client.host if r.client else "?")
    if _EDGE and _hm.compare_digest(r.headers.get("x-bb-edge",""),_EDGE):
        ip=(r.headers.get("x-bb-client-ip") or "").strip()
        if ip: return ip
    return sock
@app.exception_handler(PermissionError)
async def _pe(request,exc): return JSONResponse({"error":"login required"},401)
@app.exception_handler(AdminOnly)
async def _ao(request,exc): return JSONResponse({"error":"owner only"},403)
# --- API ---
@app.get("/bb/health")
def health():
    out={"ok":True,"node":os.environ.get("BB_NODE","box")}
    try:
        c=sqlite3.connect(DB,timeout=3)
        try: c.execute("select count(*) from users").fetchone(); out["db"]="ok"
        finally: c.close()
    except Exception as e: out["db"]="error:"+type(e).__name__
    try: st=json.load(open(BASE+"/.persist_state.json"))
    except Exception: st={}
    iso=lambda t: time.strftime("%Y-%m-%dT%H:%M:%S+06:00",time.gmtime(t+6*3600)) if t else None
    out["backup"]={"last_push":iso(st.get("last_push")),"last_check":iso(st.get("last_check")),
        "restored":iso(st.get("restored")),"daily_last":st.get("daily_last"),"daily_kept":st.get("daily_count"),
        "size_warn":bool(st.get("size_warn")),
        "refused":({"at":iso(st.get("last_refused"))} if (st.get("last_refused") or 0)>(st.get("last_push") or 0) else None)}
    return out
@app.get("/bb/api/models")
def models(request:Request):
    u=need(request); return [{"id":"auto","name":"Auto (best + backup)"}]+[{"id":k,"name":v[0]} for k,v in MODELS.items()]+MD.byok_chat_list(u)
@app.get("/bb/api/settings")
def gs(request:Request): return get_settings(need(request))
@app.put("/bb/api/settings")
async def ps(request:Request):
    u=need(request); b=await request.json(); st={**get_settings(u),**{k:v for k,v in b.items() if k in DEFAULT_SETTINGS}}
    with db() as c: c.execute("insert or replace into settings values(?,?)",(u,json.dumps(st,ensure_ascii=False)))
    audit(ev="settings_saved"); return st
@app.get("/bb/api/chats")
def list_chats(request:Request,q:str=""):
    u=need(request)
    with db() as c:
        if q: rows=c.execute("select distinct c.* from chats c left join messages m on m.chat_id=c.id where c.user=? and (c.title like ? or m.content like ?) order by pinned desc,updated desc",(u,f"%{q}%",f"%{q}%")).fetchall()
        else: rows=c.execute("select * from chats where user=? order by pinned desc,updated desc",(u,)).fetchall()
    return [dict(r) for r in rows]
@app.post("/bb/api/chats")
async def new_chat(request:Request):
    u=need(request); b=await request.json() if (await request.body()) else {}
    cid=uuid.uuid4().hex[:12]; t=time.time()
    with db() as c:
        proj=b.get("project")
        if proj and not c.execute("select 1 from projects where id=? and user=?",(proj,u)).fetchone(): proj=None
        c.execute("insert into chats values(?,?,?,?,?,?,?)",(cid,u,b.get("title","নতুন চ্যাট"),0,proj,t,t))
    return {"id":cid}
def own(c,u,cid):
    r=c.execute("select * from chats where id=? and user=?",(cid,u)).fetchone()
    if not r: raise NotFound
    return r
@app.get("/bb/api/chats/{cid}")
def get_chat(request:Request,cid:str):
    u=need(request)
    with db() as c:
        ch=own(c,u,cid); ms=c.execute("select id,role,content,model,advisors from messages where chat_id=? order by id",(cid,)).fetchall()
    return {**dict(ch),"messages":[{**dict(m),"advisors":json.loads(m["advisors"] or "[]")} for m in ms]}
@app.patch("/bb/api/chats/{cid}")
async def patch_chat(request:Request,cid:str):
    u=need(request); b=await request.json()
    with db() as c:
        own(c,u,cid)
        for k in ("title","pinned","project"):
            if k in b: c.execute(f"update chats set {k}=? where id=?",(b[k],cid))
    return {"ok":True}
@app.delete("/bb/api/chats/{cid}")
def del_chat(request:Request,cid:str):
    u=need(request)
    with db() as c: own(c,u,cid); c.execute("delete from messages where chat_id=?",(cid,)); c.execute("delete from chats where id=?",(cid,))
    audit(ev="chat_deleted",chat=cid); return {"ok":True}
@app.get("/bb/api/chats/{cid}/export.md")
def export_md(request:Request,cid:str):
    ch=get_chat(request,cid); out=f"# {ch['title']}\n\n_বাংলা ভাই · Royal Universe_\n\n"
    for m in ch["messages"]: out+=("## 🧑 User\n\n" if m["role"]=="user" else f"## 🤖 Bangla Bhai ({m['model']})\n\n")+m["content"]+"\n\n"
    return Response(out,media_type="text/markdown; charset=utf-8",headers={"Content-Disposition":f'attachment; filename="bangla-bhai-{cid}.md"'})
@app.get("/bb/api/projects")
def lp(request:Request):
    u=need(request)
    with db() as c: return [dict(r) for r in c.execute("select * from projects where user=? order by created",(u,))]
@app.post("/bb/api/projects")
async def cpj(request:Request):
    u=need(request); b=await request.json(); pid=uuid.uuid4().hex[:10]
    with db() as c: c.execute("insert into projects values(?,?,?,?,?)",(pid,u,b.get("name","নতুন প্রজেক্ট"),b.get("instructions",""),time.time()))
    return {"id":pid}
@app.patch("/bb/api/projects/{pid}")
async def upj(request:Request,pid:str):
    u=need(request); b=await request.json()
    with db() as c:
        for k in ("name","instructions"):
            if k in b: c.execute(f"update projects set {k}=? where id=? and user=?",(b[k],pid,u))
    return {"ok":True}
@app.delete("/bb/api/projects/{pid}")
def dpj(request:Request,pid:str):
    u=need(request)
    with db() as c: c.execute("delete from projects where id=? and user=?",(pid,u)); c.execute("update chats set project=null where project=? and user=?",(pid,u))
    return {"ok":True}
@app.get("/bb/api/export")
def export_all(request:Request):
    u=need(request)
    with db() as c:
        chats=[dict(r) for r in c.execute("select * from chats where user=?",(u,))]
        for ch in chats: ch["messages"]=[dict(m) for m in c.execute("select role,content,model,created from messages where chat_id=? order by id",(ch["id"],))]
        pr=[dict(r) for r in c.execute("select * from projects where user=?",(u,))]
    audit(ev="data_export")
    return Response(json.dumps({"settings":get_settings(u),"projects":pr,"chats":chats},ensure_ascii=False,indent=1),media_type="application/json",headers={"Content-Disposition":'attachment; filename="bangla-bhai-export.json"'})
@app.delete("/bb/api/data")
def clear_all(request:Request):
    u=need(request)
    with db() as c:
        for (cid,) in c.execute("select id from chats where user=?",(u,)).fetchall(): c.execute("delete from messages where chat_id=?",(cid,))
        c.execute("delete from chats where user=?",(u,)); c.execute("delete from projects where user=?",(u,))
    audit(ev="data_cleared"); return {"ok":True}
UPL_DIR=os.path.join(BASE,"media_store","uploads"); os.makedirs(UPL_DIR,exist_ok=True)
def _keep_upload(request,data):
    try:
        iid=uuid.uuid4().hex; open(os.path.join(UPL_DIR,f"{need(request)}_{iid}"),"wb").write(data); return iid
    except Exception: return None
def _load_upload(u,iid):
    if not iid or not re.fullmatch(r"[0-9a-f]{32}",str(iid)): return None
    f=os.path.join(UPL_DIR,f"{u}_{iid}")
    return open(f,"rb").read() if os.path.exists(f) else None
IMG_EDIT=re.compile(r"(edit|change|remove|replace|background|make (it|me|this)|turn (it|this|me)|convert|add .* to|enhance|retouch|cartoon|anime|style|colou?r|এডিট|সম্পাদনা|বদল|পরিবর্তন|পাল্টা|মুছ|সরিয়ে|সরাও|ব্যাকগ্রাউন্ড|বানাও|বানিয়ে|যোগ কর|লাগাও|কার্টুন|সুন্দর কর|ঠিক কর|রঙ)",re.I)
IMG_GEN=re.compile(r"((generate|create|draw|make|design)\s+(an?\s+)?(image|picture|photo|logo|poster)|(ছবি|ইমেজ|লোগো|পোস্টার)\s*(আঁক|বানা|তৈরি|জেনারেট))",re.I)
FACE_RULE=" Keep the person's face, facial features and identity exactly the same as in the original photo; only change what is asked."
async def _chat_image(u,instr,img,lang):
    import media as MD
    prompt=(instr or "Enhance this photo").strip()[:1500]
    if img is not None: prompt+=FACE_RULE
    m,data=await asyncio.wait_for(MD.image_with_fallback(MD.FALLBACK_EDIT[0] if img is not None else MD.FALLBACK_GEN[0],prompt,img),420)
    r=MD.save(u,"image",m,prompt,data); bn=lang=="bn"
    return (("✅ ছবিটা এডিট করে দিলাম (মুখ একই রাখা হয়েছে)" if bn else "✅ Here is your edited photo (face kept the same)") if img is not None else ("✅ ছবি তৈরি হয়েছে" if bn else "✅ Image created"))+f"\n\n![image]({r['url']})\n\n[⬇️ Download]({r['url']}) · _{m}_",m
@app.post("/bb/api/upload")
async def upload(request:Request,file:UploadFile=File(...)):
    need(request); data=await file.read(); name=file.filename or "file"
    if len(data)>15_000_000: return JSONResponse({"error":"ফাইল ১৫MB-এর বেশি"},400)
    text=""
    try:
        if name.lower().endswith(".pdf") or file.content_type=="application/pdf":
            import ocr as OC; text,how=await asyncio.to_thread(OC.pdf_text,data); audit(ev="ocr_pdf",how=how)
            if not text.strip(): return JSONResponse({"error":"No text found in PDF / PDF-এ কোনো লেখা পাওয়া যায়নি"},400)
            return {"name":name,"kind":"text","text":text[:60000],"chars":len(text),"note":"📄 PDF read ("+how+")"}
        elif (file.content_type or "").startswith("image/"):
            import ocr as OC
            async def _ocr():
                if OC.LOW_MEM: return ""          # Render: the vision model already transcribes text; skip a 2nd call
                try: return await asyncio.to_thread(OC.image_text,data)
                except Exception: return ""
            async def _vis():
                try: return await AG.vision(data,file.content_type)
                except Exception: return "",""
            ot,(m,desc)=await asyncio.gather(_ocr(),_vis())
            if not desc and OC.LOW_MEM: ot=await asyncio.to_thread(OC.cloud_image_text,data,file.content_type)
            audit(ev="vision",name=name,model=m,ocr=len(ot))
            if not (ot or desc): return JSONResponse({"error":"Could not read image / ছবি পড়া যায়নি"},400)
            txt=(f"[Image description — {m}]\n{desc}\n\n" if desc else "")+(f"[OCR text ({'cloud' if OC.LOW_MEM else 'RapidOCR, local'})]\n{ot}" if ot else "")
            iid=_keep_upload(request,data)
            return {"name":name,"kind":"text","text":txt[:60000],"chars":len(txt),"img_id":iid,"note":"🖼️ Image read"+(" + OCR" if ot else "")}
        else: text=data.decode("utf-8","ignore")
    except Exception as e: audit(ev="upload_err",err=str(e)[:200]); return JSONResponse({"error":"ফাইল পড়া যায়নি — অন্য ফরম্যাটে চেষ্টা করুন। / Could not read this file."},400)
    audit(ev="upload",name=name,size=len(data))
    return {"name":name,"kind":"text","text":text[:60000],"chars":len(text)}
@app.post("/bb/api/chats/{cid}/stream")
async def stream(request:Request,cid:str):
    u=need(request); b=await request.json(); st=get_settings(u)
    ok,lim=PL.take(u,"chat")
    if not ok: return JSONResponse({"error":PL.quota_msg("chat",lim,st.get("lang"))},429)
    with db() as c:
        ch=own(c,u,cid); proj=c.execute("select instructions from projects where id=? and user=?",(ch["project"],u)).fetchone() if ch["project"] else None
        if b.get("edit_id"):  # edit a user message: replace it and drop everything after
            c.execute("delete from messages where chat_id=? and id>=?",(cid,int(b["edit_id"]) if str(b["edit_id"]).isdigit() else 10**12))
        if b.get("regenerate"):
            last=c.execute("select id,role from messages where chat_id=? order by id desc limit 1",(cid,)).fetchone()
            if last and last["role"]=="assistant": c.execute("delete from messages where id=?",(last["id"],))
        elif b.get("content") is not None:
            c.execute("insert into messages(chat_id,role,content,created) values(?,?,?,?)",(cid,"user",b["content"],time.time()))
        hist=[{"role":m["role"],"content":m["content"]} for m in c.execute("select role,content from messages where chat_id=? order by id",(cid,)).fetchall()][-24:]
        first=c.execute("select count(*) n from messages where chat_id=?",(cid,)).fetchone()["n"]<=1
    q=hist[-1]["content"] if hist else ""; sel=b.get("model") or "auto"
    # run schedule-detect, memory recall and web grounding in parallel (was serial: saves ~0.5-2s before first token)
    async def _sched():
        if b.get("content") and not b.get("regenerate"):
            xs=SJ.chat_skill(u,q)
            if xs: hist[-1]={"role":"user","content":xs}; return None
            try: return await SJ.chat_schedule(u,q,st.get("lang","en"))
            except Exception: return None
        return None
    async def _mem():
        if not st.get("memory",True): return []
        try: return await asyncio.wait_for(MEM.arecall(u,q),6)
        except Exception: return []
    async def _gr():
        try:
            import ground as GR; return await GR.context(q if b.get("content") is not None or b.get("regenerate") else "")
        except Exception: return ""
    imgs=[x for x in (b.get("images") or []) if x][:1]
    instr=re.split(r"\n\n---\n📄 File:",q)[0] if isinstance(q,str) else ""
    img_data=_load_upload(u,imgs[0]) if imgs else None
    if (b.get("content") is not None or b.get("regenerate")) and ((img_data is not None and (IMG_EDIT.search(instr) or not instr.strip())) or (img_data is None and IMG_GEN.search(instr) and len(instr)<400)):
        lang=st.get("lang","en")
        async def igen():
            yield "event: meta\ndata: "+json.dumps({"model":"Image studio"})+"\n\n"
            yield "event: status\ndata: "+json.dumps({"text":"ছবি তৈরি হচ্ছে, ১-২ মিনিট লাগতে পারে..." if lang=="bn" else "Working on the image, may take 1-2 min..."})+"\n\n"
            t=asyncio.create_task(_chat_image(u,instr,img_data,lang))
            while not t.done():
                await asyncio.sleep(10)
                if not t.done(): yield ": keepalive\n\n"
            try: full,m=t.result()
            except Exception as e:
                audit(ev="chat_image_err",err=str(e)[:200]); m="Image studio"
                full=("⚠️ এখন সব ফ্রি ছবি-মডেল ব্যস্ত, ছবিটা এডিট করা গেল না। একটু পরে আবার পাঠান, বা 🎨 Studio থেকে চেষ্টা করুন।" if lang=="bn" else "⚠️ All free image models are busy right now. Please try again shortly or use 🎨 Studio.")
            with db() as c:
                c.execute("insert into messages(chat_id,role,content,model,advisors,created) values(?,?,?,?,?,?)",(cid,"assistant",full,m,"[]",time.time()))
                c.execute("update chats set updated=? where id=?",(time.time(),cid))
            audit(ev="chat_image",chat=cid,model=m)
            yield "data: "+json.dumps({"d":full})+"\n\n"; yield "event: done\ndata: "+json.dumps({"model":m})+"\n\n"
        return StreamingResponse(igen(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})
    sched_reply,mems,gctx=await asyncio.gather(_sched(),_mem(),_gr())
    msgs=[{"role":"system","content":persona(st,proj["instructions"] if proj else "",uid=u,mems=mems)+("\n\n"+gctx if gctx else "")}]+hist
    if sel.startswith("byok:"):
        res=MD.resolve_chat(u,sel)
        if res: _BYOK_CTX[sel]=res
        else: sel="auto"
    extra=[_spec(sel)] if sel!="auto" and _spec(sel) and sel not in RT.CHAIN else []
    rchain=[sel]+[m for m in RT.DEFAULT if m!=sel] if sel in RT.CHAIN else RT.DEFAULT
    chain=[sel] if extra else rchain
    council=(b.get("council") or (sel=="auto" and HARD.search(q) and len(q)>60)) and FL.on("feat_council")
    async def gen():
        advisors=[]; msgs2=msgs
        if sched_reply:
            yield "event: meta\ndata: "+json.dumps({"model":"Scheduler"})+"\n\n"; yield "data: "+json.dumps({"d":sched_reply})+"\n\n"
            save(sched_reply,"Scheduler",[]); yield "event: done\ndata: "+json.dumps({"model":"Scheduler"})+"\n\n"; return
        if council:
            yield "event: status\ndata: "+json.dumps({"text":("কাউন্সিলের পরামর্শ নিচ্ছি..." if st.get("lang")=="bn" else "Consulting the council...")})+"\n\n"
            res=await asyncio.gather(*[call(a,msgs,1,35) for a in ADVISORS if a!=chain[0]])
            notes=[r for r in res if r]; advisors=[n for n,_ in notes]
            if notes: msgs2=msgs+[{"role":"system","content":"কাউন্সিলের পরামর্শদাতাদের মতামত (মিলিয়ে সেরা উত্তর দাও, তাদের কথা উল্লেখ করার দরকার নেই):\n\n"+"\n\n---\n".join(f"[{n}]\n{t[:2500]}" for n,t in notes)}]
            yield "event: advisors\ndata: "+json.dumps(advisors)+"\n\n"
        full=""; name="none"; bn=st.get("lang")=="bn"
        try:
          try:
            async for kind,val in RT.stream(msgs2,chain=rchain,extra=extra):
                if kind=="meta": name=val; yield "event: meta\ndata: "+json.dumps({"model":val})+"\n\n"
                elif kind=="delta": full+=val; yield "data: "+json.dumps({"d":val})+"\n\n"
                else:
                    what,label=val
                    txt=((f"{label} ব্যস্ত, আবার চেষ্টা করছি..." if bn else f"{label} is busy, retrying...") if what=="retry" else
                         (f"{label} সাড়া দেয়নি, পরের মডেলে যাচ্ছি..." if bn else f"{label} did not respond, switching to the next model..."))
                    yield "event: status\ndata: "+json.dumps({"text":txt})+"\n\n"
          except asyncio.CancelledError: raise
          except Exception: pass
          if not full:
            full=RT.friendly(st.get("lang","en")); yield "data: "+json.dumps({"d":full})+"\n\n"
          elif st.get("memory",True) and b.get("content"):
            asyncio.create_task(MEM.extract(u,b["content"],RT.complete))
        finally:
          save(full or "_(থামানো হয়েছে)_",name,advisors)
        yield "event: done\ndata: "+json.dumps({"model":name})+"\n\n"
    def save(full,name,advisors):
        with db() as c:
            c.execute("insert into messages(chat_id,role,content,model,advisors,created) values(?,?,?,?,?,?)",(cid,"assistant",full,name,json.dumps(advisors),time.time()))
            c.execute("update chats set updated=? where id=?",(time.time(),cid))
            if first and ch["title"]=="নতুন চ্যাট":
                t=re.sub(r"\s+"," ",q)[:40]; c.execute("update chats set title=? where id=?",(t or "নতুন চ্যাট",cid))
        audit(ev="chat",chat=cid,model=name,advisors=advisors)
    return StreamingResponse(gen(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})
# legacy non-stream endpoint (kept)
@app.post("/bb/api/chat")
async def chat(request:Request):
    u=need(request); b=await request.json(); hist=b.get("messages",[])[-20:]; st=get_settings(u)
    ok,lim=PL.take(u,"chat")
    if not ok: return JSONResponse({"error":PL.quota_msg("chat",lim,st.get("lang"))},429)
    try:
        import ground as GR; gctx=await GR.context(hist[-1]["content"] if hist and isinstance(hist[-1].get("content"),str) else "")
    except Exception: gctx=""
    msgs=[{"role":"system","content":persona(st,uid=u)+("\n\n"+gctx if gctx else "")}]+hist; advisors=[]
    if b.get("council") and FL.on("feat_council"):
        notes=[r for r in await asyncio.gather(*[call(a,msgs) for a in ADVISORS]) if r]; advisors=[n for n,_ in notes]
        if notes: msgs+= [{"role":"system","content":"কাউন্সিলের মতামত:\n"+"\n---\n".join(t[:2500] for _,t in notes)}]
    try:
        n,t,_=await RT.complete(msgs); audit(ev="chat",model=n); return {"answer":t,"model":n,"advisors":advisors}
    except RT.ModelError: return {"answer":RT.friendly(st.get("lang","en")),"model":"none","advisors":advisors}

# ---------- agent / link / voice / vision ----------
@app.post("/bb/api/chats/{cid}/note")
async def note(request:Request,cid:str):
    u=need(request); b=await request.json()
    with db() as c:
        own(c,u,cid)
        if b.get("user"): c.execute("insert into messages(chat_id,role,content,created) values(?,?,?,?)",(cid,"user",b["user"],time.time()))
        if b.get("assistant") is not None: c.execute("insert into messages(chat_id,role,content,model,created) values(?,?,?,?,?)",(cid,"assistant",b["assistant"],"বাংলা ভাই এজেন্ট",time.time()))
        c.execute("update chats set updated=?, title=CASE WHEN title='নতুন চ্যাট' THEN ? ELSE title END where id=?",(time.time(),(b.get("user") or "")[:40] or "নতুন চ্যাট",cid))
    return {"ok":True}
@app.post("/bb/api/intent")
async def intent(request:Request):
    need_admin(request); b=await request.json(); r=await AG.classify_intent(b.get("text",""))
    audit(ev="intent",**{k:r.get(k) for k in("action","reason","device_hint","confidence")}); return r
@app.post("/bb/api/agent")
async def ag_start(request:Request):
    u=need_admin(request); b=await request.json(); st=get_settings(u)
    if not FL.on("feat_agent"): return JSONResponse({"error":FL.OFF_MSG["feat_agent"]},403)
    sysx=lang_rule(st)+" "+addr_rule(u)+" Write the JSON 'thought' and 'final' fields in that language."
    return {"id":AG.start_task(b.get("goal",""),sysx,user=u)}
@app.get("/bb/api/agent/{tid}")
def ag_events(request:Request,tid:str,since:int=0):
    need_admin(request); t=AG.get_task(tid)
    if not t: return JSONResponse({"error":"নেই"},404)
    return {"status":t["status"],"events":t["events"][since:],"n":len(t["events"])}
@app.post("/bb/api/agent/{tid}/decide")
async def ag_decide(request:Request,tid:str):
    need_admin(request); b=await request.json(); return {"ok":AG.decide(tid,b["id"],"yes" if b.get("ok") else "no")}
@app.get("/bb/api/devices")
def dv(request:Request): need_admin(request); return {"devices":AG.devices(),"caps":AG.CAPS}
@app.post("/bb/api/devices/{did}/{act}")
async def dv_act(request:Request,did:str,act:str):
    need_admin(request)
    if act in("approve","deny"): AG.pair_decide(did,act=="approve")
    elif act=="perm": b=await request.json(); AG.set_perm(did,b["cap"],b["mode"]) if b["mode"] in AG.MODES and b["cap"] in AG.CAPS else None
    elif act=="remove":
        with AG.db() as c: c.execute("update devices set status='revoked' where id=?",(did,))
        audit(ev="device_revoked",device=did)
    return {"ok":True}
@app.post("/bb/api/revoke-all")
def rv(request:Request): need_admin(request); AG.revoke_all(); return {"ok":True}
@app.post("/bb/link/pair")
async def lk_pair(request:Request):
    if not FL.on("feat_devices"): return JSONResponse({"error":FL.OFF_MSG["feat_devices"]},403)
    if not rate_ok("pair:"+cip(request),5,3600): return JSONResponse({"error":"rate limited"},429)
    b=await request.json(); info=b.get("info",{}) if isinstance(b.get("info"),dict) else {}
    if len(json.dumps(info))>4000: info={}
    did,tok=AG.pair_request(str(b.get("name","device"))[:60],str(b.get("kind","laptop"))[:20],info); return {"device":did,"token":tok}
@app.get("/bb/link/status")
def lk_status(token:str):
    d=AG.dev_by_token(token); return {"status":d["status"] if d else "unknown","perms":{k:AG.get_perm(d["id"],k) for k in AG.CAPS} if d else {}}
@app.get("/bb/link/poll")
async def lk_poll(token:str):
    d=AG.dev_by_token(token)
    if not d or d["status"]!="approved": return JSONResponse({"status":d["status"] if d else "unknown"},403)
    q=AG.LINK_Q.setdefault(d["id"],asyncio.Queue())
    try: job=await asyncio.wait_for(q.get(),25)
    except asyncio.TimeoutError: return {"job":None}
    audit(ev="link_dispatch",device=d["id"],action=job["action"]); return {"job":job}
MAX_RES=12*1024*1024; MAX_IMG=8*1024*1024; MAX_SHOTS=500
_MAGIC={b"\x89PNG":"png",b"\xff\xd8\xff":"jpg",b"GIF8":"gif",b"RIFF":"webp"}
def save_shot(r):
    if not r.get("image_b64"): return
    import base64
    try: data=base64.b64decode(r.pop("image_b64"),validate=False)
    except Exception: raise ValueError("bad image")
    if len(data)>MAX_IMG: raise ValueError("image too large")
    ext=next((e for m,e in _MAGIC.items() if data.startswith(m)),None)
    if not ext and data[4:8]==b"ftyp": ext="mp4"
    if not ext: raise ValueError("unsupported image type")
    sd=BASE+"/static/shots"; os.makedirs(sd,exist_ok=True)
    fs=sorted((os.path.join(sd,x) for x in os.listdir(sd)),key=os.path.getmtime)
    for old in fs[:max(0,len(fs)-MAX_SHOTS+1)]:
        try: os.remove(old)
        except OSError: pass
    fn=f"shots/{uuid.uuid4().hex}.{ext}"; open(BASE+"/static/"+fn,"wb").write(data); r["image"]="/bb/static/"+fn
@app.get("/bb/static/shots/{fn}")
def shot(request:Request,fn:str):
    need(request)
    if not re.fullmatch(r"[0-9a-f]{8,32}\.(png|jpg|jpeg|gif|webp|mp4)",fn): raise NotFound
    fp=BASE+"/static/shots/"+fn
    if not os.path.isfile(fp): raise NotFound
    return FileResponse(fp,headers={"Cache-Control":"private, no-store"})
app.router.routes.insert(0,app.router.routes.pop())
@app.post("/bb/link/result")
async def lk_res(request:Request):
    if int(request.headers.get("content-length") or 0)>MAX_RES: return JSONResponse({"error":"too large"},413)
    raw=await request.body()
    if len(raw)>MAX_RES: return JSONResponse({"error":"too large"},413)
    try: b=json.loads(raw)
    except Exception: return JSONResponse({"error":"bad json"},400)
    d=AG.dev_by_token(b.get("token"))
    if not d or d["status"]!="approved": return JSONResponse({"error":"device not approved"},403)
    if not rate_ok("linkres:"+d["id"],120,3600): return JSONResponse({"error":"rate limited"},429)
    f=AG.LINK_RES.get(b.get("cid")); own_=AG.LINK_OWN.get(b.get("cid"))
    if own_ is not None and own_!=d["id"]: return JSONResponse({"error":"wrong device"},403)
    if f is None: return JSONResponse({"error":"unknown job"},404)
    r=b.get("result") or {}
    if not isinstance(r,dict): r={"result":str(r)[:20000]}
    try: save_shot(r)
    except ValueError as e: return JSONResponse({"error":str(e)},400)
    audit(ev="link_result",device=d["id"],ok=not r.get("error"))
    if f and not f.done(): f.set_result(r)
    return {"ok":True}

@app.websocket("/bb/link/ws")
async def lk_ws(ws: WebSocket):
    from starlette.websockets import WebSocketDisconnect
    await ws.accept(); tok=ws.query_params.get("token"); d=AG.dev_by_token(tok)
    if not d or d["status"]!="approved": await ws.close(code=4403); return
    q=AG.LINK_Q.setdefault(d["id"],asyncio.Queue()); audit(ev="link_ws_open",device=d["id"])
    async def push():
        while True:
            job=await q.get(); await ws.send_json(job); audit(ev="link_dispatch",device=d["id"],action=job["action"],via="ws")
    t=asyncio.create_task(push())
    try:
        while True:
            b=await ws.receive_json(); f=AG.LINK_RES.get(b.get("cid")); r=b.get("result") or {}
            if f is None or AG.LINK_OWN.get(b.get("cid")) not in (None,d["id"]) or not isinstance(r,dict): continue
            if not rate_ok("linkres:"+d["id"],120,3600): continue
            try: save_shot(r)
            except ValueError as e: r={"error":str(e)}
            audit(ev="link_result",device=d["id"],ok=not r.get("error"),via="ws")
            if f and not f.done(): f.set_result(r)
            AG.dev_by_token(tok)  # touch last_seen
    except WebSocketDisconnect: pass
    finally: t.cancel(); audit(ev="link_ws_close",device=d["id"])

@app.get("/bb/link/{fn}")
def lk_file(fn:str):
    if fn not in("royal_link.py","royal_link_termux.sh","royal_link_tray.py","install_termux.sh","README.md","SHIZUKU_BN.md"): return Response(status_code=404)
    return FileResponse(BASE+"/link/"+fn,media_type="text/plain; charset=utf-8")
@app.post("/bb/api/tts")
async def tts(request:Request):
    u=need(request); b=await request.json()
    if not is_owner_uid(u) and not rate_ok("tts:"+u,80,86400): return JSONResponse({"error":"Daily voice limit reached"},429)
    try: return Response(await AG.tts(re.sub(r"[`*#>|_\[\]()]","",b.get("text",""))),media_type="audio/mpeg")
    except Exception as e: return JSONResponse({"error":str(e)[:200]},502)
@app.post("/bb/api/stt")
async def stt(request:Request,file:UploadFile=File(...)):
    u=need(request); data=await file.read(25_000_001)
    if len(data)>AG.STT_MAX_BYTES: return JSONResponse({"error":"Audio too large (max 10MB / 2 min)"},413)
    ok,lim=PL.take(u,"voice")
    if not ok: return JSONResponse({"error":PL.quota_msg("voice",lim,get_settings(u).get("lang"))},429)
    try: t,q=await AG.stt(data,file.content_type); audit(ev="stt",chars=len(t)); return {"text":t,"mode":q}
    except Exception as e: return JSONResponse({"error":str(e)[:200]},502)
# ---- media studio + BYOK ----
import media as MD
MD.H.update(need=need,rate_ok=rate_ok,db=db,audit=audit,is_owner=is_owner_uid,act=AL.log)
import features as FT
FT.setup(app,dict(need=need,need_admin=need_admin,get_settings=get_settings,db=db,audit=audit,page=page,is_owner=is_owner_uid,rate_ok=rate_ok,AG=AG))
app.include_router(MD.router)
import skills_jobs as SJ
SJ.setup(app,dict(need=need,get_settings=get_settings,db=db,audit=audit,is_owner=is_owner_uid,rate_ok=rate_ok,AG=AG,sysx=lambda u:lang_rule(get_settings(u))+" "+addr_rule(u)+" Write the JSON 'thought' and 'final' fields in that language."))
AG.ON_DONE.append(SJ.on_agent_done)
# ---- plans/payments/admin dashboard + Telegram ----
import biz as BZ, tg as TG, ocr as OC
async def _tg_answer(u,text,ctx=""):
    st=get_settings(u)
    try: mems=await MEM.arecall(u,text) if st.get("memory",True) else None
    except Exception: mems=None
    msgs=[{"role":"system","content":persona(st,uid=u,mems=mems)+" You are replying inside Telegram: plain text, no markdown tables."}]
    if ctx: msgs.append({"role":"system","content":"The user uploaded this document; answer questions about it:\n"+ctx[:24000]})
    msgs.append({"role":"user","content":text})
    try: _,t,_=await RT.complete(msgs,timeout=60,tries=2); return clean(t)
    except RT.ModelError: return RT.friendly(st.get("lang","en"))
TG.H.update(answer=_tg_answer,stt=AG.stt,ocr_image=OC.image_text,ocr_pdf=lambda d:OC.pdf_text(d)[0],take=PL.take,quota_msg=PL.quota_msg,audit=audit,sub_info=PL.sub_info)
@app.on_event("startup")
async def _tg_start():
    if os.environ.get('BB_ROLE')=='standby': return
    asyncio.get_running_loop().create_task(TG.run())
import connections as CN
CN.setup(app,dict(need=need,user=user,is_owner=is_owner_uid,db=db,audit=audit,rate_ok=rate_ok))
import vault as VLT
VLT.setup(app,dict(user=user,is_owner=is_owner_uid))
import notebook as NB
NB.setup(app,dict(is_admin=is_admin))
import devagent as DA
DA.setup(app,dict(db=db,audit=audit,need_admin=need_admin,rate_ok=rate_ok,MD=MD))
try:
    import bridge as BRG
    BRG.setup(app,dict(db=db,audit=audit,is_admin=is_admin,rate_ok=rate_ok,notify=SJ.notify,owner=CFG["BB_USER"]))
except Exception as _e: print("bridge setup failed",_e)
BZ.setup(app,dict(need=need,is_admin=is_admin,FT=FT,db=db,cip=cip,RT=RT,AdminOnly=AdminOnly,user=user,rate_ok=rate_ok,audit=audit,notify=SJ.notify,owner=CFG["BB_USER"]))
import admin_dash as ADM
ADM.setup(app,dict(db=db,is_admin=is_admin,AdminOnly=AdminOnly,audit=audit,RT=RT,owner=CFG["BB_USER"],secret=CFG.get("BB_SESSION_SECRET",""),health=health,
    advisors=ADVISORS,caps=AG.CAPS,revoke_all=AG.revoke_all,cip=cip,notify=SJ.notify,redact=AG.redact_secrets))
# ---- Open WebUI proxy ----
UP="http://127.0.0.1:8080"; WEBUI_PREFIXES=("/_app","/api/","/ws","/ollama","/openai","/manifest.json","/favicon","/auth","/c/","/workspace","/admin","/oauth","/assets","/static/","/notes","/channels","/playground","/home","/s/")
client=httpx.AsyncClient(base_url=UP,timeout=120)
async def proxy(request:Request,path:str):
    h={k:v for k,v in request.headers.items() if k.lower() not in("host","content-length","accept-encoding")}
    r=await client.request(request.method,path+("?"+request.url.query if request.url.query else ""),headers=h,content=await request.body())
    rh={k:v for k,v in r.headers.items() if k.lower() not in("content-length","transfer-encoding","content-encoding","connection")}
    return Response(r.content,r.status_code,rh)
@app.api_route("/webui{path:path}",methods=["GET","POST","PUT","DELETE","PATCH"])
async def webui(request:Request,path:str):
    if not is_admin(request): return RedirectResponse("/login",303)
    try: r=await proxy(request,path or "/")
    except Exception: r=None
    if r is None or r.status_code>=500:
        return HTMLResponse(CSS+"<div style='padding:24px'><h2>Open WebUI is offline</h2><p>Advanced WebUI runs only on the box server and isn't available on the 24/7 server right now. Use the main app instead.</p><a href=/app>← Back to app</a> · <a href=/admin/panel>Admin panel</a></div>",503)
    if (path in("","/")) and r.headers.get("content-type","").startswith("text/html"):
        b=r.body.decode().replace("<head>","<head><script>history.replaceState(null,'','/c/');</script>",1)
        return HTMLResponse(b,r.status_code)
    return r
import secrets
# ---- Owner approval for logins when email delivery fails ----
@app.get("/admin/login-requests")
def login_reqs(request:Request):
    if not is_admin(request): return RedirectResponse("/admin?next=/admin/login-requests",303)
    if not request.session.get("csrf"): request.session["csrf"]=secrets.token_urlsafe(24)
    with db() as c:
        c.execute("create table if not exists otp_pending(email text primary key,t real)")
        c.execute("delete from otp_pending where t<?",(time.time()-86400,))
        rows=c.execute("select email,t from otp_pending order by t desc").fetchall()
    import connections as CN, html as _h
    snd=CN.gmail_sender()
    li="".join(f"<li><b>{_h.escape(r['email'])}</b> <small>{time.strftime('%d %b %H:%M',time.localtime(r['t']))}</small> <button onclick=\"ap('{_h.escape(r['email'])}',this)\">Approve → make code</button> <span></span></li>" for r in rows) or "<li>No pending requests / কোনো অনুরোধ নেই</li>"
    st=(f"✅ Login codes are sent from <b>{_h.escape(snd)}</b> (Gmail)." if snd else "⚠️ Sender Gmail not connected — users can't receive codes. <a class=b href='/bb/conn/oauth/gmail/start'>Connect sender Gmail</a> (sign in with the owner Gmail, allow access).")
    page=f"""<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'><title>Login requests</title>
<style>body{{font-family:system-ui;background:#0b1a3a;color:#eef;max-width:640px;margin:auto;padding:16px}}a.b,button{{background:#2a5bd7;color:#fff;border:0;border-radius:8px;padding:8px 12px;text-decoration:none;cursor:pointer}}li{{margin:10px 0}}code{{font-size:1.3em;background:#fff2;padding:2px 6px}}</style>
<h2>🔐 Login requests</h2><p>{st}</p><p>Users whose code email failed. Approve → a 10-minute code appears; send it to the user yourself (WhatsApp/SMS).</p><ul>{li}</ul><p><a href='/admin/panel' style='color:#9bf'>← Admin panel</a></p>
<script>async function ap(e,b){{let r=await fetch('/bb/api/admin/otp-approve',{{method:'POST',headers:{{'Content-Type':'application/json','X-CSRF':'{request.session["csrf"]}'}},body:JSON.stringify({{email:e}})}});let j=await r.json();b.nextElementSibling.innerHTML=j.code?'Code: <code>'+j.code+'</code>':(j.error||'error')}}</script>"""
    return HTMLResponse(page)

@app.post("/bb/api/admin/otp-approve")
async def otp_approve(request:Request):
    if not is_admin(request): return JSONResponse({"error":"forbidden"},403)
    if not hmac.compare_digest(request.headers.get("x-csrf",""),request.session.get("csrf","") or "x"): return JSONResponse({"error":"csrf"},403)
    b=await request.json(); email=AU.normalize_email(b.get("email",""))
    with db() as c:
        c.execute("create table if not exists otp_pending(email text primary key,t real)")
        if not c.execute("select 1 from otp_pending where email=?",(email,)).fetchone(): return JSONResponse({"error":"no pending request"},404)
        c.execute("delete from otp_pending where email=?",(email,))
    code=AU.create_otp(email); audit(ev="otp_owner_approved",email=email)
    return {"ok":True,"code":code}

@app.api_route("/{path:path}",methods=["GET","POST","PUT","DELETE","PATCH"])
async def fallback(request:Request,path:str):
    p="/"+path
    if p.startswith(WEBUI_PREFIXES):
        if not is_admin(request): return JSONResponse({"error":"owner only"},403)
        return await proxy(request,p)
    return RedirectResponse("/",303)
