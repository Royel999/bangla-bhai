"""Connections hub: app catalog, OAuth scaffolding, API keys (reuses encrypted BYOK), Telegram, custom MCP servers, webhooks.
Per-user storage; owner-only OAuth client config. Secrets are Fernet-encrypted (bb_byok.key) and never returned in full."""
import os, json, time, uuid, secrets, re, asyncio, httpx
from urllib.parse import urlencode, urlparse
from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
import media as MD
S=os.path.expanduser('~/.secrets'); BASE=os.path.expanduser('~/bangla_bhai'); DOMAIN="https://banglabhai.dpdns.org"
H={}
SI="https://cdn.simpleicons.org/"
# id: (name, category, description, method, logo, extra)
OAUTH={
 "gmail":{"auth":"https://accounts.google.com/o/oauth2/v2/auth","token":"https://oauth2.googleapis.com/token","scope":"openid email https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.compose","client":"google"},
 "gdrive":{"auth":"https://accounts.google.com/o/oauth2/v2/auth","token":"https://oauth2.googleapis.com/token","scope":"openid email https://www.googleapis.com/auth/drive.file","client":"google"},
 "gcal":{"auth":"https://accounts.google.com/o/oauth2/v2/auth","token":"https://oauth2.googleapis.com/token","scope":"openid email https://www.googleapis.com/auth/calendar.events","client":"google"},
 "github":{"auth":"https://github.com/login/oauth/authorize","token":"https://github.com/login/oauth/access_token","scope":"repo read:user","client":"github"},
 "notion":{"auth":"https://api.notion.com/v1/oauth/authorize","token":"https://api.notion.com/v1/oauth/token","scope":"","client":"notion"},
}
APPS=[
 # featured / productivity (OAuth)
 ("gmail","Gmail","productivity","Read, search and draft your email","oauth",SI+"gmail",1),
 ("gdrive","Google Drive","productivity","Find and create files in your Drive","oauth",SI+"googledrive",1),
 ("gcal","Google Calendar","productivity","See and add calendar events","oauth",SI+"googlecalendar",0),
 ("notion","Notion","productivity","Search and write Notion pages","oauth",SI+"notion/ffffff",0),
 ("github","GitHub","developer","Repos, issues and pull requests","oauth",SI+"github/ffffff",1),
 ("telegram","Telegram","messaging","Chat with Bangla Bhai from Telegram","telegram",SI+"telegram",1),
 ("mcp","Custom MCP server","custom","Connect any MCP server by URL and use its tools","mcp","",1),
 ("webhook","Webhooks","custom","Send events out or receive them in","webhook","",0),
 ("openrouter","OpenRouter","ai","300+ models incl. open, uncensored-style ones","key",SI+"openrouter/ffffff",1),
 ("openai","OpenAI","ai","GPT-5, GPT-image and Sora with your key","key",SI+"openai/ffffff",0),
 ("anthropic","Anthropic Claude","ai","Claude Sonnet, Opus and Haiku","key",SI+"anthropic/ffffff",0),
 ("gemini","Google Gemini","ai","Gemini Pro, Nano Banana and Veo (paid key)","key",SI+"googlegemini",0),
 ("groq","Groq","ai","Ultra-fast Llama, Qwen and GPT-OSS","key","",0),
 ("mistral","Mistral AI","ai","Mistral Large, Medium and Codestral","key",SI+"mistralai",0),
 ("deepseek","DeepSeek","ai","DeepSeek V3 chat and R1 reasoning","key","",0),
 ("xai","xAI","ai","Grok models with your own key","key",SI+"x/ffffff",0),
 ("together","Together AI","ai","Open models: Llama, Qwen, DeepSeek","key","",0),
 ("huggingface","Hugging Face","ai","Inference router for open models","key",SI+"huggingface",0),
 ("replicate","Replicate","media","FLUX, Nano Banana, Veo, Kling","key",SI+"replicate/ffffff",0),
 ("fal","fal.ai","media","Fast image and video generation","key","",0),
 ("stability","Stability AI","media","Stable Image Core, Ultra and SD 3.5","key","",0),
 ("pollinations","Pollinations","media","Image models with your Pollen key","key","",0),
 ("luma","Luma Dream Machine","media","Photon images and Ray video","key","",0),
 ("runway","Runway","media","Gen-4 video","key","",0),
 ("elevenlabs","ElevenLabs","media","Natural voices and text-to-speech","key",SI+"elevenlabs/ffffff",0),
 ("cartesia","Cartesia","media","Low-latency realtime voices","key","",0),
 ("custom","Custom AI endpoint","custom","Any OpenAI-compatible API","key","",0),
]
NEW_PROV={
 "groq":{"name":"Groq","base":"https://api.groq.com/openai/v1","chat":["llama-3.3-70b-versatile","openai/gpt-oss-120b","qwen/qwen3-32b"],"image":[],"video":[]},
 "mistral":{"name":"Mistral AI","base":"https://api.mistral.ai/v1","chat":["mistral-large-latest","mistral-medium-latest","codestral-latest"],"image":[],"video":[]},
 "deepseek":{"name":"DeepSeek","base":"https://api.deepseek.com/v1","chat":["deepseek-chat","deepseek-reasoner"],"image":[],"video":[]},
 "xai":{"name":"xAI","base":"https://api.x.ai/v1","chat":["grok-4","grok-4-fast","grok-3-mini"],"image":[],"video":[]},
 "together":{"name":"Together AI","base":"https://api.together.xyz/v1","chat":["meta-llama/Llama-3.3-70B-Instruct-Turbo","Qwen/Qwen2.5-72B-Instruct-Turbo","deepseek-ai/DeepSeek-V3"],"image":[],"video":[]},
 "huggingface":{"name":"Hugging Face","base":"https://router.huggingface.co/v1","chat":["meta-llama/Llama-3.3-70B-Instruct","Qwen/Qwen3-32B","deepseek-ai/DeepSeek-V3-0324"],"image":[],"video":[]},
 "elevenlabs":{"name":"ElevenLabs","base":"https://api.elevenlabs.io/v1","chat":[],"image":[],"video":[],"voice":True},
 "cartesia":{"name":"Cartesia","base":"https://api.cartesia.ai","chat":[],"image":[],"video":[],"voice":True},
 "pollinations":{"name":"Pollinations","base":"https://gen.pollinations.ai/v1","chat":["openai","mistral"],"image":[],"video":[]},
}
for k,v in NEW_PROV.items(): MD.PROV.setdefault(k,v)
# open / uncensored-style models on OpenRouter (user selects; minimal legal safeguards still apply)
for m in ["cognitivecomputations/dolphin-mistral-24b-venice-edition:free","nousresearch/hermes-4-405b","nousresearch/hermes-3-llama-3.1-405b","sao10k/l3.3-euryale-70b"]:
    if m not in MD.PROV["openrouter"]["chat"]: MD.PROV["openrouter"]["chat"].append(m)
KEYFMT={"openai":r"^sk-[A-Za-z0-9_\-]{20,}$","anthropic":r"^sk-ant-[A-Za-z0-9_\-]{20,}$","openrouter":r"^sk-or-[A-Za-z0-9_\-]{20,}$","groq":r"^gsk_[A-Za-z0-9]{20,}$","huggingface":r"^hf_[A-Za-z0-9]{20,}$","replicate":r"^r8_[A-Za-z0-9]{20,}$"}
TG_RE=re.compile(r"^\d{6,12}:[A-Za-z0-9_-]{30,50}$")
def db():
    c=H["db"]()
    c.executescript("""create table if not exists conn_oauth(id text primary key,user text,app text,account text,enc text,created real);
    create table if not exists conn_mcp(id text primary key,user text,name text,url text,enc text,tools text,created real);
    create table if not exists conn_hooks(id text primary key,user text,dir text,url text,token text,events text,created real);
    create table if not exists conn_admin(k text primary key,v text);""")
    return c
enc=lambda s:MD.FER.encrypt(s.encode()).decode()
dec=lambda s:MD.FER.decrypt(s.encode()).decode()
def _hint(k):
    try: return mask(MD.dec(k))
    except MD.KeyInvalid: return "⚠️ বাতিল — আবার যোগ করুন"
def admin_get(k):
    with db() as c: r=c.execute("select v from conn_admin where k=?",(k,)).fetchone()
    return r["v"] if r else ""
def client_of(app):
    cl=OAUTH[app]["client"]; cid=admin_get(cl+"_id"); cs=admin_get(cl+"_secret")
    return (cid,dec(cs)) if cid and cs else (None,None)
def gmail_sender():
    """Owner-connected Gmail (gmail.compose scope allows send). Returns account email or ''."""
    own=os.environ.get("BB_OWNER_EMAIL","skbadol3210@gmail.com").strip().lower()
    try:
        with db() as c: r=c.execute("select account from conn_oauth where app='gmail' and lower(account)=? order by created desc limit 1",(own,)).fetchone()
        return r["account"] if r else ""
    except Exception: return ""
def gmail_send(to,subject,body):
    """Send mail via the owner's connected Gmail (OAuth). Returns (ok, detail). Never logs tokens."""
    import base64
    from email.message import EmailMessage
    own=os.environ.get("BB_OWNER_EMAIL","skbadol3210@gmail.com").strip().lower()
    try:
        with db() as c: r=c.execute("select id,enc from conn_oauth where app='gmail' and lower(account)=? order by created desc limit 1",(own,)).fetchone()
        if not r: return False,"gmail_not_connected"
        j=json.loads(dec(r["enc"])); cid,cs=client_of("gmail")
        def _send(tok):
            m=EmailMessage(); m["To"]=to; m["From"]=f"Bangla Bhai <{own}>"; m["Subject"]=subject; m.set_content(body)
            raw=base64.urlsafe_b64encode(m.as_bytes()).decode()
            return httpx.post("https://gmail.googleapis.com/gmail/v1/users/me/messages/send",headers={"Authorization":"Bearer "+tok},json={"raw":raw},timeout=20)
        x=_send(j.get("access_token",""))
        if x.status_code==401 and j.get("refresh_token") and cid:
            t=httpx.post(OAUTH["gmail"]["token"],data={"grant_type":"refresh_token","refresh_token":j["refresh_token"],"client_id":cid,"client_secret":cs},timeout=20).json()
            if not t.get("access_token"): return False,"gmail_refresh_failed"
            j["access_token"]=t["access_token"]
            with db() as c: c.execute("update conn_oauth set enc=? where id=?",(enc(json.dumps(j)),r["id"]))
            x=_send(j["access_token"])
        return (x.status_code==200), f"gmail_api {x.status_code}"
    except Exception as e: return False,"gmail_api "+type(e).__name__
def csrf(request):
    t=request.session.get("csrf")
    if not t: t=secrets.token_urlsafe(24); request.session["csrf"]=t
    return t
def chk(request):
    import hmac
    if not hmac.compare_digest(request.headers.get("x-csrf",""),request.session.get("csrf","") or "x"): raise PermissionError
def mask(s): return (s[:4]+"…"+s[-4:]) if len(s)>12 else "••••"
# ---------- MCP (streamable HTTP, JSON or SSE replies) ----------
async def _rpc(url,hdr,method,params,sid=None,rid=1):
    h={"Content-Type":"application/json","Accept":"application/json, text/event-stream","MCP-Protocol-Version":"2025-06-18",**hdr}
    if sid: h["Mcp-Session-Id"]=sid
    body={"jsonrpc":"2.0","method":method,"params":params}
    if rid is not None: body["id"]=rid
    async with httpx.AsyncClient(timeout=30,follow_redirects=False) as c:
        r=await c.post(url,headers=h,json=body)
    if r.status_code>=400: raise RuntimeError(f"MCP server answered HTTP {r.status_code}")
    sid=r.headers.get("mcp-session-id") or sid
    if rid is None: return None,sid
    t=r.text
    if "text/event-stream" in r.headers.get("content-type",""):
        js=[l[5:].strip() for l in t.splitlines() if l.startswith("data:")]
        for x in js:
            try:
                j=json.loads(x)
                if j.get("id")==rid: break
            except Exception: continue
        else: raise RuntimeError("No reply from MCP server")
    else: j=r.json()
    if j.get("error"): raise RuntimeError(str(j["error"].get("message","MCP error"))[:200])
    return j.get("result"),sid
async def mcp_session(url,hdr):
    _,sid=await _rpc(url,hdr,"initialize",{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"bangla-bhai","version":"1.0"}})
    try: await _rpc(url,hdr,"notifications/initialized",{},sid,rid=None)
    except Exception: pass
    return sid
def _url_safe(u):
    import agent as AG
    p=urlparse(u); return p.scheme=="https" and AG._url_ok(u)
def _hdr(tok): return {"Authorization":("Bearer "+tok) if tok and not tok.lower().startswith(("bearer ","basic ")) else tok} if tok else {}
async def mcp_tools(url,tok):
    hdr=_hdr(tok); sid=await mcp_session(url,hdr); res,_=await _rpc(url,hdr,"tools/list",{},sid,rid=2)
    return [{"name":t["name"][:80],"description":(t.get("description") or "")[:300],"schema":t.get("inputSchema",{})} for t in (res or {}).get("tools",[])][:100]
def mcp_list(u):
    with db() as c: return [dict(r) for r in c.execute("select * from conn_mcp where user=? order by created",(u,))]
async def mcp_call(u,a):
    """agent tool: {server: name or id, tool, args}"""
    srv=str(a.get("server","")); rows=mcp_list(u)
    r=next((x for x in rows if x["id"]==srv or x["name"].lower()==srv.lower()),rows[0] if len(rows)==1 and not srv else None)
    if not r: return "No such MCP server. Connected: "+", ".join(x["name"] for x in rows) if rows else "No MCP server connected (Connections page)."
    if not _url_safe(r["url"]): return "Blocked: server URL is not public"
    hdr=_hdr(dec(r["enc"]) if r["enc"] else ""); sid=await mcp_session(r["url"],hdr)
    args=a.get("args") or {}
    if isinstance(args,str):
        try: args=json.loads(args)
        except Exception: args={"query":args}
    res,_=await _rpc(r["url"],hdr,"tools/call",{"name":a.get("tool"),"arguments":args},sid,rid=3)
    out=[x.get("text","") for x in (res or {}).get("content",[]) if x.get("type")=="text"]
    return ("\n".join(out) or json.dumps(res,ensure_ascii=False))[:6000]
def mcp_prompt(u):
    rows=mcp_list(u) if u else []
    if not rows: return ""
    return "Connected MCP servers (use tool mcp_call with server, tool, args): "+"; ".join(f"{r['name']}: "+", ".join(t["name"] for t in json.loads(r["tools"] or "[]")[:25]) for r in rows)
# ---------- status ----------
def status(u,owner):
    import tg as TG
    keys=MD.keys_for(u)
    with db() as c:
        oa={r["app"]:r for r in c.execute("select app,account,id from conn_oauth where user=?",(u,))}
        hooks=[dict(r) for r in c.execute("select id,dir,url,token,events,created from conn_hooks where user=?",(u,))]
    mcps=mcp_list(u); out={}
    for a in APPS:
        i,m=a[0],a[4]; st={"added":False,"accounts":[]}
        if m=="oauth":
            st["ready"]=bool(client_of(i)[0])
            if i in oa: st.update(added=True,accounts=[oa[i]["account"] or "connected"])
        elif m=="key":
            ks=[k for k in keys if k["provider"]==i]
            st.update(added=bool(ks),accounts=[(k["label"] or MD.PROV[i]["name"]) for k in ks],keys=[{"id":k["id"],"label":k["label"],"hint":_hint(k)} for k in ks])
        elif m=="telegram":
            lk=TG.link_of(u); st.update(bot=TG.STATE.get("bot"),running=bool(TG.STATE.get("running")),linked=bool(lk),has_token=bool(TG.token()))
            st.update(added=bool(lk) or (owner and bool(TG.token())),accounts=(["@"+lk["username"]] if lk and lk.get("username") else (["linked"] if lk else [])))
        elif m=="mcp":
            st.update(added=bool(mcps),accounts=[r["name"] for r in mcps],servers=[{"id":r["id"],"name":r["name"],"url":r["url"],"auth":bool(r["enc"]),"tools":[t["name"] for t in json.loads(r["tools"] or "[]")]} for r in mcps])
        elif m=="webhook":
            st.update(added=bool(hooks),accounts=[h["dir"] for h in hooks],hooks=[{"id":h["id"],"dir":h["dir"],"url":(h["url"] if h["dir"]=="out" else f"{DOMAIN}/bb/hook/{h['token']}"),"events":json.loads(h["events"] or "[]")[-10:]} for h in hooks])
        out[i]=st
    return out
def setup(app,HH):
    H.update(HH); need=H["need"]; is_owner=H["is_owner"]
    @app.get("/connections")
    def page(request:Request):
        if not H["user"](request): return RedirectResponse("/login",303)
        return FileResponse(BASE+"/static/connections.html",headers={"Cache-Control":"no-store"})
    @app.get("/bb/api/conn")
    def catalog(request:Request):
        u=need(request); own=is_owner(u)
        r={"csrf":csrf(request),"owner":own,"apps":[{"id":a[0],"name":a[1],"cat":a[2],"desc":a[3],"method":a[4],"logo":a[5],"featured":bool(a[6]),"models":MD.PROV.get(a[0],{}).get("chat",[])[:12] if a[4]=="key" else []} for a in APPS],"status":status(u,own)}
        if own: r["admin"]={cl:{"id":admin_get(cl+"_id"),"secret_set":bool(admin_get(cl+"_secret"))} for cl in("google","github","notion")}; r["redirect_base"]=DOMAIN+"/bb/conn/oauth/"
        return r
    # ----- keys (shared with Studio BYOK) -----
    @app.post("/bb/api/conn/key")
    async def add_key(request:Request):
        u=need(request); chk(request); b=await request.json()
        if not H["rate_ok"](f"keys:{u}",20,3600): return JSONResponse({"error":"Too many changes"},429)
        p=b.get("provider"); k=(b.get("key") or "").strip()
        if p not in MD.PROV or p=="custom" and not b.get("base_url"): return JSONResponse({"error":"Unknown provider"},400)
        if not (8<=len(k)<=400) or re.search(r"\s",k): return JSONResponse({"error":"That key looks invalid"},400)
        if p in KEYFMT and not re.match(KEYFMT[p],k): return JSONResponse({"error":"That doesn't look like a "+MD.PROV[p]["name"]+" key"},400)
        base=(b.get("base_url") or "").strip() if p=="custom" else ""
        if p=="custom" and not _url_safe(base): return JSONResponse({"error":"Base URL must be a public https URL"},400)
        if len(MD.keys_for(u))>=20: return JSONResponse({"error":"Max 20 keys"},400)
        ms={kk:[str(x).strip()[:120] for x in (b.get("models") or {}).get(kk,[]) if str(x).strip()][:20] for kk in("chat","image","video")}
        if p=="custom" and not any(ms.values()): return JSONResponse({"error":"Add at least one model name"},400)
        kid=uuid.uuid4().hex[:12]
        with MD._db() as c: c.execute("insert into user_keys values(?,?,?,?,?,?,?,?)",(kid,u,p,(b.get("label") or "")[:60],MD.FER.encrypt(k.encode()).decode(),base or None,json.dumps(ms),time.time()))
        H["audit"](ev="conn_key_add",provider=p); return {"ok":True,"id":kid,"hint":mask(k)}
    @app.delete("/bb/api/conn/key/{kid}")
    def del_key(request:Request,kid:str):
        u=need(request); chk(request)
        with MD._db() as c: n=c.execute("delete from user_keys where id=? and user=?",(kid,u)).rowcount
        H["audit"](ev="conn_key_del"); return {"ok":bool(n)}
    # ----- Telegram -----
    @app.post("/bb/api/conn/telegram")
    async def tg_set(request:Request):
        import tg as TG
        u=need(request); chk(request); b=await request.json(); t=(b.get("token") or "").strip()
        if not is_owner(u): return JSONResponse({"error":"Only the owner can set the bot token. Use 'Link my Telegram' instead."},403)
        if not TG_RE.match(t): return JSONResponse({"error":"Bot token format is 123456789:AA… (from @BotFather)"},400)
        if b.get("check",True):
            try:
                async with httpx.AsyncClient(timeout=15) as c: j=(await c.get(f"https://api.telegram.org/bot{t}/getMe")).json()
            except Exception: j={}
            if not j.get("ok"): return JSONResponse({"error":"Telegram rejected this token"},400)
        if b.get("validate_only"): return {"ok":True,"valid":True}
        f=S+"/telegram.env"; fd=os.open(f,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,"w") as fh: fh.write(f"BB_TELEGRAM_TOKEN={t}\n")
        if not TG.STATE.get("running"): asyncio.get_running_loop().create_task(TG.run())
        H["audit"](ev="conn_tg_token"); return {"ok":True}
    # ----- OAuth -----
    @app.post("/bb/api/conn/admin")
    async def admin_set(request:Request):
        u=need(request); chk(request)
        if not is_owner(u): return JSONResponse({"error":"owner only"},403)
        b=await request.json(); cl=b.get("client")
        if cl not in("google","github","notion"): return JSONResponse({"error":"bad client"},400)
        cid=(b.get("id") or "").strip()[:300]; cs=(b.get("secret") or "").strip()[:300]
        with db() as c:
            c.execute("insert or replace into conn_admin values(?,?)",(cl+"_id",cid))
            if cs: c.execute("insert or replace into conn_admin values(?,?)",(cl+"_secret",enc(cs)))
            if not cid: c.execute("delete from conn_admin where k=?",(cl+"_secret",))
        H["audit"](ev="conn_admin_oauth",client=cl); return {"ok":True}
    @app.get("/bb/conn/oauth/{a}/start")
    def oa_start(request:Request,a:str):
        u=need(request)
        if a not in OAUTH: return JSONResponse({"error":"unknown app"},404)
        cid,_=client_of(a)
        if not cid: return RedirectResponse("/connections?e=setup",303)
        st=secrets.token_urlsafe(24); request.session["oa"]={"s":st,"a":a,"t":time.time()}
        q={"client_id":cid,"redirect_uri":f"{DOMAIN}/bb/conn/oauth/{a}/callback","response_type":"code","state":st}
        if OAUTH[a]["scope"]: q["scope"]=OAUTH[a]["scope"]
        if OAUTH[a]["client"]=="google": q.update(access_type="offline",prompt="consent",include_granted_scopes="true")
        if a=="notion": q["owner"]="user"
        return RedirectResponse(OAUTH[a]["auth"]+"?"+urlencode(q),303)
    @app.get("/bb/conn/oauth/{a}/callback")
    async def oa_cb(request:Request,a:str,code:str="",state:str=""):
        import hmac
        u=need(request); s=request.session.pop("oa",None) or {}
        if a not in OAUTH or s.get("a")!=a or not hmac.compare_digest(s.get("s",""),state or "x") or time.time()-s.get("t",0)>900 or not code:
            return RedirectResponse("/connections?e=state",303)
        cid,cs=client_of(a); data={"grant_type":"authorization_code","code":code,"redirect_uri":f"{DOMAIN}/bb/conn/oauth/{a}/callback"}
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                if a=="notion": r=await c.post(OAUTH[a]["token"],json=data,auth=(cid,cs))
                else: r=await c.post(OAUTH[a]["token"],data={**data,"client_id":cid,"client_secret":cs},headers={"Accept":"application/json"})
                j=r.json()
        except Exception: j={}
        if not j.get("access_token"): return RedirectResponse("/connections?e=token",303)
        acct=""
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                if OAUTH[a]["client"]=="google": acct=(await c.get("https://openidconnect.googleapis.com/v1/userinfo",headers={"Authorization":"Bearer "+j["access_token"]})).json().get("email","")
                elif a=="github": acct=(await c.get("https://api.github.com/user",headers={"Authorization":"Bearer "+j["access_token"]})).json().get("login","")
                elif a=="notion": acct=j.get("workspace_name","")
        except Exception: pass
        with db() as c:
            c.execute("delete from conn_oauth where user=? and app=?",(u,a))
            c.execute("insert into conn_oauth values(?,?,?,?,?,?)",(uuid.uuid4().hex[:12],u,a,str(acct)[:120],enc(json.dumps(j)),time.time()))
        H["audit"](ev="conn_oauth",app=a); return RedirectResponse("/connections?ok="+a,303)
    @app.delete("/bb/api/conn/oauth/{a}")
    def oa_del(request:Request,a:str):
        u=need(request); chk(request)
        with db() as c: c.execute("delete from conn_oauth where user=? and app=?",(u,a))
        return {"ok":True}
    # ----- MCP -----
    @app.post("/bb/api/conn/mcp")
    async def mcp_add(request:Request):
        u=need(request); chk(request); b=await request.json()
        if not H["rate_ok"](f"mcp:{u}",20,3600): return JSONResponse({"error":"Too many tries"},429)
        url=(b.get("url") or "").strip(); tok=(b.get("token") or "").strip(); name=(b.get("name") or urlparse(url).hostname or "mcp")[:40]
        if len(url)>500 or not _url_safe(url): return JSONResponse({"error":"URL must be a public https address"},400)
        if len(mcp_list(u))>=10: return JSONResponse({"error":"Max 10 MCP servers"},400)
        try: tools=await mcp_tools(url,tok)
        except Exception as e: return JSONResponse({"error":"Could not connect: "+str(e)[:160]},400)
        mid=uuid.uuid4().hex[:12]
        with db() as c: c.execute("insert into conn_mcp values(?,?,?,?,?,?,?)",(mid,u,name,url,enc(tok) if tok else "",json.dumps(tools),time.time()))
        H["audit"](ev="conn_mcp_add",host=urlparse(url).hostname); return {"ok":True,"id":mid,"tools":[t["name"] for t in tools]}
    @app.post("/bb/api/conn/mcp/{mid}/refresh")
    async def mcp_ref(request:Request,mid:str):
        u=need(request); chk(request); r=next((x for x in mcp_list(u) if x["id"]==mid),None)
        if not r: return JSONResponse({"error":"not found"},404)
        try: tools=await mcp_tools(r["url"],dec(r["enc"]) if r["enc"] else "")
        except Exception as e: return JSONResponse({"error":str(e)[:160]},400)
        with db() as c: c.execute("update conn_mcp set tools=? where id=? and user=?",(json.dumps(tools),mid,u))
        return {"ok":True,"tools":[t["name"] for t in tools]}
    @app.delete("/bb/api/conn/mcp/{mid}")
    def mcp_del(request:Request,mid:str):
        u=need(request); chk(request)
        with db() as c: c.execute("delete from conn_mcp where id=? and user=?",(mid,u))
        return {"ok":True}
    # ----- webhooks -----
    @app.post("/bb/api/conn/hook")
    async def hook_add(request:Request):
        u=need(request); chk(request); b=await request.json(); d=b.get("dir")
        with db() as c:
            if c.execute("select count(*) from conn_hooks where user=?",(u,)).fetchone()[0]>=10: return JSONResponse({"error":"Max 10 webhooks"},400)
        url=(b.get("url") or "").strip()
        if d=="out" and (len(url)>500 or not _url_safe(url)): return JSONResponse({"error":"URL must be a public https address"},400)
        if d not in("in","out"): return JSONResponse({"error":"bad type"},400)
        hid=uuid.uuid4().hex[:12]; tk=secrets.token_urlsafe(24) if d=="in" else ""
        with db() as c: c.execute("insert into conn_hooks values(?,?,?,?,?,?,?)",(hid,u,d,url if d=="out" else "",tk,"[]",time.time()))
        return {"ok":True,"id":hid}
    @app.post("/bb/api/conn/hook/{hid}/test")
    async def hook_test(request:Request,hid:str):
        u=need(request); chk(request)
        with db() as c: r=c.execute("select * from conn_hooks where id=? and user=? and dir='out'",(hid,u)).fetchone()
        if not r or not _url_safe(r["url"]): return JSONResponse({"error":"not found"},404)
        try:
            async with httpx.AsyncClient(timeout=10,follow_redirects=False) as c: rr=await c.post(r["url"],json={"event":"test","source":"bangla-bhai","t":time.time()})
            return {"ok":rr.status_code<400,"status":rr.status_code}
        except Exception as e: return JSONResponse({"error":str(e)[:120]},400)
    @app.delete("/bb/api/conn/hook/{hid}")
    def hook_del(request:Request,hid:str):
        u=need(request); chk(request)
        with db() as c: c.execute("delete from conn_hooks where id=? and user=?",(hid,u))
        return {"ok":True}
    @app.post("/bb/hook/{tk}")
    async def hook_in(request:Request,tk:str):
        if not (20<=len(tk)<=64) or not H["rate_ok"]("hookin:"+tk[:12],60,3600): return JSONResponse({"error":"no"},429)
        body=(await request.body())[:4000].decode("utf-8","ignore")
        with db() as c:
            r=c.execute("select id,events from conn_hooks where token=? and dir='in'",(tk,)).fetchone()
            if not r: return JSONResponse({"error":"not found"},404)
            ev=(json.loads(r["events"] or "[]")+[{"t":time.time(),"body":body[:1000]}])[-20:]
            c.execute("update conn_hooks set events=? where id=?",(json.dumps(ev),r["id"]))
        return {"ok":True}
