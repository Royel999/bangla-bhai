"""Roadmap 4-5: per-user self-learning Skills (approval before save/improve) and Scheduled jobs with in-app + Web Push notifications."""
import os, re, json, time, uuid, sqlite3, asyncio, datetime as DT
from zoneinfo import ZoneInfo
from croniter import croniter
from fastapi import Request
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
import router as RT, actlog as AL
TZ=ZoneInfo("Asia/Dhaka"); DBF=os.path.expanduser("~/bangla_bhai/data.db"); S=os.path.expanduser("~/.secrets")
LIM={"skills":50,"jobs":5,"min_interval":3600}
def _env(f):
    d={}
    try:
        for l in open(f):
            if "=" in l: k,v=l.strip().split("=",1); d[k]=v
    except Exception: pass
    return d
VAP=_env(f"{S}/vapid.env"); VAPID_PRIV=f"{S}/vapid_private.pem"
def db():
    c=sqlite3.connect(DBF,timeout=15); c.row_factory=sqlite3.Row; return c
with db() as c:
    c.executescript("""
    create table if not exists skills(id text primary key,user text,name text,description text,steps text,inputs text,mode text default 'chat',version int default 1,runs int default 0,created real,updated real);
    create table if not exists skill_props(id text primary key,user text,skill_id text,draft text,source text,status text default 'pending',created real);
    create table if not exists jobs(id text primary key,user text,title text,prompt text,skill_id text,cron text,once_at real,next_run real,enabled int default 1,last_run real,last_status text,last_result text,created real);
    create table if not exists notifs(id integer primary key autoincrement,user text,title text,body text,url text,created real,read int default 0);
    create table if not exists push_subs(endpoint text primary key,user text,sub text,created real);
    create index if not exists ix_jobs_next on jobs(enabled,next_run);""")
J=lambda s,d=None: (json.loads(s) if s else d)
def _skill(r):
    d=dict(r); d["steps"]=J(d["steps"],[]); d["inputs"]=J(d["inputs"],[]); return d
def slug(n): return re.sub(r"\s+","-",(n or "").strip().lower())[:40]
def clean_draft(d):
    d=d if isinstance(d,dict) else {}
    steps=[str(s)[:300] for s in (d.get("steps") or []) if str(s).strip()][:12]
    inputs=[re.sub(r"[^\w\-]","",str(i))[:30] for i in (d.get("inputs") or []) if str(i).strip()][:6]
    return {"name":slug(d.get("name") or "my-skill") or "my-skill","description":str(d.get("description",""))[:300],"steps":steps or ["Do the task"],"inputs":[i for i in inputs if i],"mode":"agent" if d.get("mode")=="agent" else "chat"}
async def llm_json(prompt):
    _,t,_=await RT.complete([{"role":"system","content":"Return only a JSON object."},{"role":"user","content":prompt}],json_mode=True,timeout=45,tries=2)
    t=re.sub(r"<think>.*?</think>","",t,flags=re.S); return json.loads(t[t.find("{"):t.rfind("}")+1])
PROPOSE="""A user's task just succeeded. Turn it into a short reusable skill.
Return JSON: {{"name":"kebab-case-name (2-4 words, English)","description":"one line","steps":["step 1","step 2",...],"inputs":["placeholder names used as {{name}} in steps"]}}.
Steps must be general instructions (use {{input}} placeholders instead of specific values). Max 8 steps. Never include passwords, codes or keys.
TASK: {goal}
RESULT (trimmed): {result}"""
async def propose(u,goal,result,source="chat",mode="chat",skill_id=None,feedback=""):
    if not goal.strip(): return None
    if skill_id:
        with db() as c: r=c.execute("select * from skills where id=? and user=?",(skill_id,u)).fetchone()
        if not r: return None
        s=_skill(r); p=("Improve this skill using the user's feedback. Keep the same name. Return the same JSON shape "
          '{"name","description","steps","inputs"}.\nSKILL: '+json.dumps({k:s[k] for k in("name","description","steps","inputs")},ensure_ascii=False)+"\nFEEDBACK: "+feedback[:600])
    else: p=PROPOSE.format(goal=goal[:1200],result=result[:1500])
    try: d=clean_draft(await llm_json(p))
    except Exception: return None
    d["mode"]=mode
    pid=uuid.uuid4().hex[:10]
    with db() as c:
        c.execute("delete from skill_props where user=? and status='pending' and created<?",(u,time.time()-7*86400))
        c.execute("insert into skill_props values(?,?,?,?,?,?,?)",(pid,u,skill_id,json.dumps(d,ensure_ascii=False),source,"pending",time.time()))
    AL.log(u,"skill","propose",goal[:200],d["name"],task=None); return {"id":pid,"skill_id":skill_id,**d}
def expand(s,vals):
    vals={k:str(v)[:500] for k,v in (vals or {}).items()}
    body="\n".join(f"{i+1}. {st}" for i,st in enumerate(s["steps"]))
    for k in s["inputs"]: body=body.replace("{"+k+"}",vals.get(k) or f"({k})")
    return f"Run my saved skill '{s['name']}': {s['description']}\nFollow these steps:\n{body}"
def find_skill(u,name):
    with db() as c: r=c.execute("select * from skills where user=? and name=?",(u,slug(name))).fetchone()
    return r and _skill(r)
# ---------- schedules ----------
def now(): return time.time()
def next_from(cron,after=None):
    base=DT.datetime.fromtimestamp(after or now(),TZ); return croniter(cron,base).get_next(DT.datetime).timestamp()
def valid_cron(cron):
    try: return croniter.is_valid(cron) and len(cron.split())==5
    except Exception: return False
def interval_ok(cron):
    a=next_from(cron); b=next_from(cron,a); return b-a>=LIM["min_interval"]
PARSE="""Current time in Dhaka (Asia/Dhaka, UTC+6): {now}.
Decide if this message asks to schedule something (a reminder or a recurring task). Return JSON:
{{"schedule":true|false,"title":"short title","prompt":"what to do/say when it fires, in the user's language","cron":"5-field cron in Dhaka time or empty","once_at":"YYYY-MM-DD HH:MM Dhaka time or empty"}}
Use cron for repeating ("every day 8am" -> "0 8 * * *"), once_at for one-off ("in 2 minutes", "tomorrow 9pm"). For a plain reminder the prompt is the reminder text.
MESSAGE: {msg}"""
SCHED_RX=re.compile(r"(every\s+(day|morning|week|monday|tuesday|wednesday|thursday|friday|saturday|sunday|hour)|daily|weekly|remind\s+me|reminder|schedule|in\s+\d+\s*(min|minute|hour)|at\s+\d{1,2}(:\d\d)?\s*(am|pm)|প্রতিদিন|প্রতি\s*(দিন|সপ্তাহ|সকাল|রাত|ঘণ্টা)|মনে\s*করি|রিমাইন্ড|রিমাইন্ডার|শিডিউল|মিনিট\s*পর|ঘণ্টা\s*পর)",re.I)
async def parse_schedule(msg):
    try: d=await llm_json(PARSE.format(now=DT.datetime.now(TZ).strftime("%A %Y-%m-%d %H:%M"),msg=msg[:600]))
    except Exception: return None
    return d if d.get("schedule") else None
def count_jobs(u):
    with db() as c: return c.execute("select count(*) n from jobs where user=? and enabled=1",(u,)).fetchone()["n"]
def create_job(u,owner,title,prompt,cron="",once_at=None,skill_id=None):
    title=str(title or prompt or "Job")[:80]; prompt=str(prompt or "")[:1500]
    if not prompt and not skill_id: raise Oops("Tell me what the job should do.")
    if not owner and count_jobs(u)>=LIM["jobs"]: raise Oops(f"Free plan limit: {LIM['jobs']} active jobs. Delete or pause one first.")
    if cron:
        cron=cron.strip()
        if not valid_cron(cron): raise Oops("That schedule could not be understood.")
        if not owner and not interval_ok(cron): raise Oops("On the free plan a repeating job can run at most once an hour.")
        nxt=next_from(cron); once_at=None
    else:
        if not once_at: raise Oops("Give a time for the job.")
        nxt=float(once_at)
        if nxt<now()-30: raise Oops("That time is already in the past.")
        if nxt>now()+366*86400: raise Oops("Pick a time within a year.")
    jid=uuid.uuid4().hex[:10]
    with db() as c: c.execute("insert into jobs(id,user,title,prompt,skill_id,cron,once_at,next_run,enabled,created) values(?,?,?,?,?,?,?,?,1,?)",(jid,u,title,prompt,skill_id,cron or None,once_at,nxt,now()))
    AL.log(u,"schedule","create",title,(cron or "once")+" next "+fmt(nxt)); return jid,nxt
def parse_local(s):
    s=str(s).strip().replace("T"," ")[:16]
    try: return DT.datetime.strptime(s,"%Y-%m-%d %H:%M").replace(tzinfo=TZ).timestamp()
    except ValueError: raise Oops("That time could not be understood.")
def fmt(ts): return DT.datetime.fromtimestamp(ts,TZ).strftime("%d %b %Y, %I:%M %p")+" (Dhaka)"
# ---------- notifications & push ----------
def notify(u,title,body,url="/schedules"):
    with db() as c: c.execute("insert into notifs(user,title,body,url,created) values(?,?,?,?,?)",(u,title[:120],body[:2000],url,now()))
    return send_push(u,title,body,url)
def send_push(u,title,body,url):
    try: from pywebpush import webpush, WebPushException
    except Exception: return 0
    with db() as c: subs=c.execute("select endpoint,sub from push_subs where user=?",(u,)).fetchall()
    sent=0
    for r in subs:
        try:
            webpush(json.loads(r["sub"]),json.dumps({"title":title[:120],"body":body[:300],"url":url}),vapid_private_key=VAPID_PRIV,vapid_claims={"sub":VAP.get("VAPID_SUB","mailto:admin@example.com")},ttl=3600,timeout=15); sent+=1
        except WebPushException as e:
            code=getattr(getattr(e,"response",None),"status_code",0)
            if code in(404,410):
                with db() as c: c.execute("delete from push_subs where endpoint=?",(r["endpoint"],))
        except Exception: pass
    return sent
# ---------- runner ----------
H={}
class Oops(Exception): pass
class Missing(Exception): pass
NEWS=re.compile(r"news|খবর|সংবাদ|headline|weather|আবহাওয়া|price|দাম",re.I)
async def run_text(u,prompt,lang="en"):
    ctx=""
    if NEWS.search(prompt):
        try: ctx=str(await H["AG"].run_tool("web_search",{"query":prompt[:200]}))[:4000]
        except Exception: ctx=""
    sysm=("Reply in Bangla. " if lang=="bn" else "Reply in the user's language. ")+"You are Bangla Bhai, running a scheduled job for the user. Be short and useful."+(f"\nFresh web results (use them, cite sources briefly):\n{ctx}" if ctx else "")
    _,t,_=await RT.complete([{"role":"system","content":sysm},{"role":"user","content":prompt}],timeout=60,tries=2)
    return re.sub(r"<think>.*?</think>","",t,flags=re.S).strip()
async def run_skill(u,s,vals,owner,lang="en",who="you"):
    goal=expand(s,vals)
    with db() as c: c.execute("update skills set runs=runs+1 where id=?",(s["id"],))
    if s.get("mode")=="agent" and owner:
        tid=H["AG"].start_task(goal,H["sysx"](u),user=u); AL.log(u,"skill","run",s["name"],"agent task "+tid,task=tid); return {"task":tid}
    t=await run_text(u,goal,lang); AL.log(u,"skill","run",s["name"],t[:300]); return {"text":t}
async def fire(j):
    u=j["user"]; owner=H["is_owner"](u); lang=H["get_settings"](u).get("lang","en")
    try:
        if j["skill_id"]:
            with db() as c: r=c.execute("select * from skills where id=? and user=?",(j["skill_id"],u)).fetchone()
            if not r: raise RuntimeError("skill was deleted")
            out=await run_skill(u,_skill(r),{},owner,lang)
            body=out.get("text") or ("Started an agent task. Any risky or device step will ask for your approval on the Activity page." if lang!="bn" else "এজেন্টের কাজ শুরু হয়েছে। ঝুঁকির বা ডিভাইসের ধাপে Activity পেজে অনুমতি চাইবে।")
            url="/activity" if out.get("task") else "/schedules"
        else:
            reminder=not j["cron"] and len(j["prompt"])<160 and not NEWS.search(j["prompt"])
            body=j["prompt"] if reminder else await run_text(u,j["prompt"],lang); url="/schedules"
        st="ok"
    except Exception as e:
        body=("The job could not finish: " if lang!="bn" else "কাজটা শেষ হয়নি: ")+(RT.friendly(lang) if isinstance(e,RT.ModelError) else str(e)[:120]); st="failed"; url="/schedules"
    n=notify(u,"⏰ "+j["title"],body,url)
    AL.log(u,"schedule","run",j["title"],f"{st}; push sent to {n} device(s)",ok=(st=="ok"))
    return st,body
async def tick():
    t=now()
    with db() as c: due=[dict(r) for r in c.execute("select * from jobs where enabled=1 and next_run<=? order by next_run limit 20",(t,)).fetchall()]
    for j in due:
        late=t-j["next_run"]
        # advance first, so a crash never double-fires
        with db() as c:
            if j["cron"]: c.execute("update jobs set next_run=?,last_run=? where id=?",(next_from(j["cron"],t),t,j["id"]))
            else: c.execute("update jobs set enabled=0,last_run=? where id=?",(t,j["id"]))
        if late>6*3600 and j["cron"]:
            with db() as c: c.execute("update jobs set last_status='skipped (server was off)' where id=?",(j["id"],)); continue
        st,body=await fire(j)
        with db() as c: c.execute("update jobs set last_status=?,last_result=? where id=?",(st,body[:2000],j["id"]))
async def scheduler():
    while True:
        try: await tick()
        except Exception as e: H["audit"](ev="sched_err",err=repr(e)[:200])
        await asyncio.sleep(15)
# ---------- chat hook ----------
SKILL_RX=re.compile(r"^\s*(?:/skill|run\s+skill|skill|স্কিল(?:\s*চালাও)?)\s*[:\-]?\s+([\w\-]+)(.*)$",re.I|re.S)
def chat_skill(u,q):
    m=SKILL_RX.match(q or "")
    if not m: return None
    s=find_skill(u,m.group(1))
    if not s: return None
    rest=m.group(2).strip(); vals={}
    for k,v in re.findall(r"(\w+)\s*=\s*(\"[^\"]*\"|\S+)",rest): vals[k]=v.strip('"')
    if s["inputs"] and not vals and rest: vals={s["inputs"][0]:rest}
    with db() as c: c.execute("update skills set runs=runs+1 where id=?",(s["id"],))
    AL.log(u,"skill","run",s["name"],"from chat"); return expand(s,vals)
async def chat_schedule(u,q,lang):
    if not SCHED_RX.search(q or "") or len(q)>600: return None
    d=await parse_schedule(q)
    if not d: return None
    bn=lang=="bn"
    try:
        once=parse_local(d["once_at"]) if d.get("once_at") and not d.get("cron") else None
        jid,nxt=create_job(u,H["is_owner"](u),d.get("title"),d.get("prompt") or q,d.get("cron") or "",once)
    except Oops as e: return ("⚠️ শিডিউল করা গেল না: " if bn else "⚠️ Couldn't schedule that: ")+str(e)[:200]
    rep=("প্রতিবার: `"+d["cron"]+"`" if d.get("cron") else "একবার") if bn else ("repeats: `"+d["cron"]+"`" if d.get("cron") else "one time")
    return (f"✅ শিডিউল হয়েছে: **{d.get('title')}**\n- পরের বার: {fmt(nxt)}\n- {rep}\n\n[Schedules](/schedules) পেজ থেকে দেখা, বন্ধ বা মুছে ফেলা যাবে। ফোনে নোটিফিকেশন পেতে ওখানে 🔔 চালু করুন।" if bn else
            f"✅ Scheduled: **{d.get('title')}**\n- Next run: {fmt(nxt)}\n- {rep}\n\nManage it on the [Schedules](/schedules) page. Turn on 🔔 there to get phone notifications.")
def on_agent_done(tid):
    """called by agent when a task succeeds with real tool results: queue a skill proposal (user must approve)."""
    t=H["AG"].get_task(tid) or {}
    if not t.get("user") or not any(e.get("type")=="result" for e in t.get("events",[])): return
    fin=next((e.get("text","") for e in reversed(t["events"]) if e.get("type")=="final"),"")
    asyncio.get_running_loop().create_task(propose(t["user"],t.get("goal",""),fin,"agent","agent"))
# ---------- HTTP ----------
def setup(app,h):
    H.update(h); need=h["need"]
    import features as FT
    def page(en,bn,js): return HTMLResponse(FT.PAGE.replace("{{T_EN}}",en).replace("{{T_BN}}",bn).replace("{{JS}}",js),headers={"Cache-Control":"no-cache"})
    def own_skill(u,sid):
        with db() as c: r=c.execute("select * from skills where id=? and user=?",(sid,u)).fetchone()
        if not r: raise Missing
        return _skill(r)
    @app.exception_handler(Missing)
    async def _lk(request,exc): return JSONResponse({"error":"not found"},404)
    @app.exception_handler(Oops)
    async def _ve(request,exc): return JSONResponse({"error":str(exc)[:200]},400)
    @app.on_event("startup")
    async def _sched(): asyncio.get_running_loop().create_task(scheduler())
    # skills
    @app.get("/bb/api/skills")
    def sk_list(request:Request):
        u=need(request)
        with db() as c:
            s=[_skill(r) for r in c.execute("select * from skills where user=? order by updated desc",(u,))]
            p=[{"id":r["id"],"skill_id":r["skill_id"],"source":r["source"],"created":r["created"],**J(r["draft"],{})} for r in c.execute("select * from skill_props where user=? and status='pending' order by created desc limit 20",(u,))]
        return {"skills":s,"proposals":p,"limit":None if h["is_owner"](u) else LIM["skills"]}
    @app.post("/bb/api/skills/propose")
    async def sk_propose(request:Request):
        u=need(request); b=await request.json()
        if not h["rate_ok"](f"skprop:{u}",30,3600): return JSONResponse({"error":"Too many requests, try later."},429)
        goal=str(b.get("goal",""))[:1500]; res=str(b.get("result",""))[:2000]
        if b.get("chat_id"):
            with h["db"]() as c:
                if not c.execute("select 1 from chats where id=? and user=?",(b["chat_id"],u)).fetchone(): raise Missing
                ms=c.execute("select role,content from messages where chat_id=? order by id desc limit 2",(b["chat_id"],)).fetchall()
            for m in ms:
                if m["role"]=="assistant" and not res: res=m["content"]
                if m["role"]=="user" and not goal: goal=m["content"]
        p=await propose(u,goal,res,"chat",skill_id=b.get("skill_id"),feedback=str(b.get("feedback",""))[:600])
        return p or JSONResponse({"error":"Couldn't draft a skill right now. Try again."},502)
    @app.post("/bb/api/skills/proposals/{pid}")
    async def sk_decide(request:Request,pid:str):
        u=need(request); b=await request.json()
        with db() as c: r=c.execute("select * from skill_props where id=? and user=? and status='pending'",(pid,u)).fetchone()
        if not r: raise Missing
        if not b.get("ok"):
            with db() as c: c.execute("update skill_props set status='discarded' where id=?",(pid,))
            AL.log(u,"skill","discard",pid,"discarded"); return {"ok":True}
        d=clean_draft({**J(r["draft"],{}),**(b.get("draft") or {})}); t=now()
        with db() as c:
            if r["skill_id"]:
                if not c.execute("select 1 from skills where id=? and user=?",(r["skill_id"],u)).fetchone(): raise Missing
                c.execute("update skills set description=?,steps=?,inputs=?,version=version+1,updated=? where id=?",(d["description"],json.dumps(d["steps"],ensure_ascii=False),json.dumps(d["inputs"]),t,r["skill_id"])); sid=r["skill_id"]
            else:
                if not h["is_owner"](u) and c.execute("select count(*) n from skills where user=?",(u,)).fetchone()["n"]>=LIM["skills"]: raise Oops(f"Limit reached: {LIM['skills']} skills.")
                name=d["name"]; i=2
                while c.execute("select 1 from skills where user=? and name=?",(u,name)).fetchone(): name=f"{d['name']}-{i}"; i+=1
                sid=uuid.uuid4().hex[:10]
                c.execute("insert into skills values(?,?,?,?,?,?,?,1,0,?,?)",(sid,u,name,d["description"],json.dumps(d["steps"],ensure_ascii=False),json.dumps(d["inputs"]),d["mode"] if h["is_owner"](u) else "chat",t,t))
            c.execute("update skill_props set status='approved' where id=?",(pid,))
        AL.log(u,"skill","save",d["name"],"approved by user"); return {"ok":True,"id":sid}
    @app.put("/bb/api/skills/{sid}")
    async def sk_edit(request:Request,sid:str):
        u=need(request); s=own_skill(u,sid); b=await request.json(); d=clean_draft({**s,**b})
        with db() as c:
            if d["name"]!=s["name"] and c.execute("select 1 from skills where user=? and name=? and id!=?",(u,d["name"],sid)).fetchone(): raise Oops("You already have a skill with that name.")
            c.execute("update skills set name=?,description=?,steps=?,inputs=?,mode=?,version=version+1,updated=? where id=?",(d["name"],d["description"],json.dumps(d["steps"],ensure_ascii=False),json.dumps(d["inputs"]),d["mode"] if h["is_owner"](u) else "chat",now(),sid))
        AL.log(u,"skill","edit",d["name"],"edited by user"); return {"ok":True}
    @app.delete("/bb/api/skills/{sid}")
    def sk_del(request:Request,sid:str):
        u=need(request); s=own_skill(u,sid)
        with db() as c: c.execute("delete from skills where id=?",(sid,)); c.execute("update jobs set enabled=0 where skill_id=? and user=?",(sid,u))
        AL.log(u,"skill","delete",s["name"],"deleted"); return {"ok":True}
    @app.post("/bb/api/skills/{sid}/run")
    async def sk_run(request:Request,sid:str):
        u=need(request); s=own_skill(u,sid); b=await request.json()
        if not h["is_owner"](u) and not h["rate_ok"](f"skrun:{u}",40,86400): return JSONResponse({"error":"Daily skill-run limit reached."},429)
        try: return await run_skill(u,s,b.get("inputs") or {},h["is_owner"](u),h["get_settings"](u).get("lang","en"))
        except RT.ModelError: return JSONResponse({"error":RT.friendly()},503)
    # jobs
    @app.get("/bb/api/jobs")
    def jb_list(request:Request):
        u=need(request)
        with db() as c: js=[dict(r) for r in c.execute("select * from jobs where user=? order by enabled desc,next_run",(u,))]
        for j in js: j["next_txt"]=fmt(j["next_run"]) if j["enabled"] else ""
        with db() as c: sk=[{"id":r["id"],"name":r["name"]} for r in c.execute("select id,name from skills where user=? order by name",(u,))]
        return {"jobs":js,"skills":sk,"limit":None if h["is_owner"](u) else LIM["jobs"],"active":count_jobs(u),"vapid":VAP.get("VAPID_PUBLIC",""),"now":fmt(now())}
    @app.post("/bb/api/jobs")
    async def jb_add(request:Request):
        u=need(request); b=await request.json()
        if not h["rate_ok"](f"jobadd:{u}",30,3600): return JSONResponse({"error":"Too many requests"},429)
        if b.get("text"):   # natural language
            d=await parse_schedule(str(b["text"]))
            if not d: raise Oops("I couldn't find a time in that. Try e.g. 'every day 8am Bangla news summary'.")
            b={"title":d.get("title"),"prompt":d.get("prompt") or b["text"],"cron":d.get("cron"),"once_at":d.get("once_at") if not d.get("cron") else None}
        sid=b.get("skill_id") or None
        if sid: own_skill(u,sid)
        once=None
        if b.get("in_minutes"): once=now()+max(1,min(int(b["in_minutes"]),1440))*60
        elif b.get("once_at"): once=parse_local(b["once_at"])
        jid,nxt=create_job(u,h["is_owner"](u),b.get("title"),b.get("prompt",""),(b.get("cron") or "").strip(),once,sid)
        return {"ok":True,"id":jid,"next":fmt(nxt)}
    @app.patch("/bb/api/jobs/{jid}")
    async def jb_upd(request:Request,jid:str):
        u=need(request); b=await request.json()
        with db() as c: j=c.execute("select * from jobs where id=? and user=?",(jid,u)).fetchone()
        if not j: raise Missing
        if "enabled" in b:
            en=1 if b["enabled"] else 0
            if en and not j["enabled"]:
                if not h["is_owner"](u) and count_jobs(u)>=LIM["jobs"]: raise Oops(f"Free plan limit: {LIM['jobs']} active jobs.")
                if not j["cron"] and (j["once_at"] or 0)<now(): raise Oops("This one-time job already ran.")
            with db() as c: c.execute("update jobs set enabled=?,next_run=? where id=?",(en,next_from(j["cron"]) if j["cron"] else j["next_run"],jid))
        return {"ok":True}
    @app.post("/bb/api/jobs/{jid}/run")
    async def jb_run(request:Request,jid:str):
        u=need(request)
        with db() as c: j=c.execute("select * from jobs where id=? and user=?",(jid,u)).fetchone()
        if not j: raise Missing
        if not h["is_owner"](u) and not h["rate_ok"](f"jobrun:{u}",20,86400): return JSONResponse({"error":"Daily limit reached."},429)
        st,body=await fire(dict(j))
        with db() as c: c.execute("update jobs set last_run=?,last_status=?,last_result=? where id=?",(now(),st,body[:2000],jid))
        return {"ok":st=="ok","text":body}
    @app.delete("/bb/api/jobs/{jid}")
    def jb_del(request:Request,jid:str):
        u=need(request)
        with db() as c: n=c.execute("delete from jobs where id=? and user=?",(jid,u)).rowcount
        if not n: raise Missing
        AL.log(u,"schedule","delete",jid,"deleted"); return {"ok":True}
    # notifications + push
    @app.get("/bb/api/notifs")
    def nf_list(request:Request,since:float=0):
        u=need(request)
        with db() as c:
            it=[dict(r) for r in c.execute("select * from notifs where user=? and created>? order by id desc limit 50",(u,since))]
            un=c.execute("select count(*) n from notifs where user=? and read=0",(u,)).fetchone()["n"]
        return {"items":it,"unread":un}
    @app.post("/bb/api/notifs/read")
    def nf_read(request:Request):
        u=need(request)
        with db() as c: c.execute("update notifs set read=1 where user=?",(u,))
        return {"ok":True}
    @app.post("/bb/api/push/subscribe")
    async def ps_sub(request:Request):
        u=need(request); b=await request.json(); ep=str(b.get("endpoint",""))
        if not re.match(r"^https://[\w.\-]+(:\d+)?/",ep) or len(ep)>800 or not (b.get("keys") or {}).get("p256dh"): raise Oops("Bad subscription")
        with db() as c:
            if c.execute("select count(*) n from push_subs where user=?",(u,)).fetchone()["n"]>=10: c.execute("delete from push_subs where user=? and created=(select min(created) from push_subs where user=?)",(u,u))
            c.execute("insert or replace into push_subs values(?,?,?,?)",(ep,u,json.dumps({"endpoint":ep,"keys":b["keys"]}),now()))
        AL.log(u,"push","subscribe",ep.split("/")[2],"ok"); return {"ok":True}
    @app.post("/bb/api/push/unsubscribe")
    async def ps_unsub(request:Request):
        u=need(request); b=await request.json()
        with db() as c: c.execute("delete from push_subs where user=? and endpoint=?",(u,str(b.get("endpoint",""))))
        return {"ok":True}
    @app.post("/bb/api/push/test")
    async def ps_test(request:Request):
        u=need(request)
        if not h["rate_ok"](f"pushtest:{u}",10,3600): return JSONResponse({"error":"Too many tests"},429)
        n=await asyncio.to_thread(notify,u,"🔔 Bangla Bhai","Notifications are working. / নোটিফিকেশন চালু আছে।")
        return {"ok":True,"sent":n}
    def gate(request):
        try: need(request); return None
        except PermissionError: return RedirectResponse("/login",303)
    @app.get("/skills")
    def skills_page(request:Request): return gate(request) or page("Skills","স্কিল",SK_JS)
    @app.get("/schedules")
    def sched_page(request:Request): return gate(request) or page("Schedules","শিডিউল",JOB_JS)
SK_JS=open(os.path.join(os.path.dirname(__file__),"static","skills.js")).read() if os.path.exists(os.path.join(os.path.dirname(__file__),"static","skills.js")) else ""
JOB_JS=open(os.path.join(os.path.dirname(__file__),"static","schedules.js")).read() if os.path.exists(os.path.join(os.path.dirname(__file__),"static","schedules.js")) else ""
