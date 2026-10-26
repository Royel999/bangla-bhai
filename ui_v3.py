"""v3 shell: built-in Skills catalog + personal Agents. Owner always gets /v3; everyone else only when flag feat_ui_v3 is on.
Tables: skill_catalog (owner-managed), user_skills (per-user enable), agents (per-user), agent_runs (agent -> tasks.id).
Every owner change -> audit_events; every user enable/run -> actions (actlog) so admin dash timeline sees it."""
import os, json, time, uuid, re, sqlite3
from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
import flags as FL, actlog as AL
DBF=os.path.expanduser('~/bangla_bhai')+'/data.db'
STATIC=os.path.join(os.path.dirname(os.path.abspath(__file__)),'static','v3')
def db():
    c=sqlite3.connect(DBF,timeout=15); c.row_factory=sqlite3.Row; return c
SCHEMA="""
create table if not exists skill_catalog(id text primary key,icon text,name_bn text,name_en text,desc_bn text,desc_en text,category text,
  mode text default 'chat',prompt text,tools text default '[]',perms text default '[]',flag text,owner_only int default 0,
  admin_on int default 1,sort int default 100,builtin int default 1,version int default 1,created real,updated real);
create table if not exists user_skills(user text,skill_id text,enabled int default 1,pinned int default 0,uses int default 0,last_used real,primary key(user,skill_id));
create table if not exists agents(id text primary key,user text,name text,icon text,persona text,model_tier text default 'auto',
  skills text default '[]',tools text default '[]',perm_level text default 'ask',lang text default 'bn',archived int default 0,created real,updated real);
create table if not exists agent_runs(task_id text primary key,agent_id text,user text,goal text,created real);
create index if not exists ix_agents_user on agents(user,archived);
create index if not exists ix_runs_agent on agent_runs(agent_id,created);
"""
# id, icon, bn, en, desc_bn, desc_en, category, mode, prompt, tools, perms, flag, owner_only, sort
SEED=[
 ("write","✍️","লেখক","Writer","গল্প, পোস্ট, ক্যাপশন, প্রবন্ধ — আপনার স্টাইলে","Posts, captions, essays in your voice","লেখা","chat","You are a skilled Bangla/English writer. Write: {input}. Ask for tone/length only if missing.",[],[],None,0,10),
 ("translate","🌐","অনুবাদক","Translator","বাংলা ⇄ ইংরেজি ও আরও ৬টি ভাষা, প্রাকৃতিক ভাষায়","Natural translation across 8 languages","ভাষা","chat","Translate faithfully and naturally. Keep names and formatting. Text: {input}",[],[],None,0,20),
 ("summarize","📝","সারাংশ","Summarizer","লম্বা লেখা, PDF বা লিংকের মূল কথা","Key points of long text, PDFs or links","পড়া","chat","Summarize into 5 bullet points + one-line takeaway, in the user's language: {input}",[],[],None,0,30),
 ("research","🔎","গবেষক","Researcher","ওয়েব খুঁজে সূত্রসহ উত্তর","Searches the web, answers with sources","গবেষণা","agent","Research this with web_search/browse, cite every source URL: {input}",["web_search","browse"],["browser"],"feat_browse",0,40),
 ("code","💻","কোডিং সহকারী","Coding helper","কোড লেখা, বাগ ধরা, ব্যাখ্যা","Write, debug and explain code","ডেভ","chat","You are a senior engineer. Give working code with short explanation: {input}",[],[],None,0,50),
 ("image","🎨","ছবি তৈরি","Image studio","লিখে ছবি বানান বা ছবি এডিট করুন","Create or edit images from text","মিডিয়া","media","{input}",["image_gen"],[],None,0,60),
 ("docs","📄","ডকুমেন্ট রিডার","Document reader","PDF/ছবি থেকে লেখা পড়ে প্রশ্নের উত্তর","Read PDFs/photos (OCR) and answer","পড়া","chat","Answer only from the attached document; quote the relevant line: {input}",["upload","ocr"],[],None,0,70),
 ("mail","✉️","চিঠি ও ইমেইল","Letters & email","দরখাস্ত, অফিসিয়াল চিঠি, ইমেইলের খসড়া (পাঠানো হয় না)","Drafts letters/emails (never sends)","লেখা","chat","Draft a clear, polite letter/email. Do not send anything: {input}",[],[],None,0,80),
 ("tutor","🎓","পড়াশোনা","Study tutor","ধাপে ধাপে বুঝিয়ে দেয়, কুইজ নেয়","Explains step by step, quizzes you","শিক্ষা","chat","Teach step by step for a Bangladeshi student, then ask 2 check questions: {input}",[],[],None,0,90),
 ("biz","📈","ব্যবসা ও মার্কেটিং","Business & marketing","আইডিয়া, প্ল্যান, বিজ্ঞাপনের লেখা","Ideas, plans, ad copy","ব্যবসা","chat","Act as a practical Bangladesh-market business advisor: {input}",[],[],None,0,100),
 ("remind","⏰","রিমাইন্ডার ও শিডিউল","Reminders","নির্দিষ্ট সময়ে বা প্রতিদিন কাজ চালায়, নোটিফিকেশন দেয়","Runs tasks on a schedule with notifications","অটোমেশন","schedule","{input}",["jobs"],[],None,0,110),
 ("device","📱","ডিভাইস কন্ট্রোল","Device control","যুক্ত ফোন/পিসিতে স্ক্রিনশট, অ্যাপ খোলা — প্রতিটা ধাপে অনুমতি","Screenshots, apps on paired devices — asks every step","ডিভাইস","agent","{input}",["screenshot","app_launch","open_url","battery","ui_dump"],["screen","apps","personal"],"feat_devices",1,120),
 ("shell","🖥️","সার্ভার কমান্ড","Server shell","বক্স/ডিভাইসে কমান্ড — শুধু মালিক, প্রতিবার অনুমতি","Shell on box/devices — owner only, always asks","ডেভ","agent","{input}",["shell"],["full"],"feat_shell",1,130),
]
def init():
    with db() as c:
        c.executescript(SCHEMA); t=time.time()
        for s in SEED:
            c.execute("insert or ignore into skill_catalog(id,icon,name_bn,name_en,desc_bn,desc_en,category,mode,prompt,tools,perms,flag,owner_only,admin_on,sort,builtin,version,created,updated) values(?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,1,1,?,?)",
                      (*s[:9],json.dumps(s[9]),json.dumps(s[10]),s[11],s[12],s[13],t,t))
def _row(r):
    d=dict(r)
    for k in ("tools","perms","skills"):
        if k in d and isinstance(d[k],str): d[k]=json.loads(d[k] or "[]")
    return d
def available(d,owner):
    """skill usable by this user right now = admin_on AND flag on AND (not owner_only or owner)"""
    if not d["admin_on"]: return False,"admin_off"
    if d.get("flag") and not FL.on(d["flag"]): return False,"flag_off"
    if d["owner_only"] and not owner: return False,"owner_only"
    if d["mode"]=="agent" and not FL.on("feat_agent"): return False,"flag_off"
    return True,""
def chat_ctx(u,skill_id,agent_id,owner):
    """Phase 2: server-side skill/agent context for /stream. Returns (system_text, skill_row|None).
    Enforces availability (admin_on, flags, owner_only) so a client can't use a disabled skill by id."""
    txt=[]; sk=None
    with db() as c:
        if skill_id and (owner or FL.on("feat_skill_catalog")):
            r=c.execute("select * from skill_catalog where id=?",(str(skill_id)[:24],)).fetchone()
            if r:
                d=_row(r); ok,_=available(d,owner)
                if ok:
                    sk=d; p=(d["prompt"] or "").replace("{input}","(the user's latest message)")
                    txt.append(f"ACTIVE SKILL: {d['icon']} {d['name_en']} ({d['name_bn']}). Apply it to the user's latest message. Skill instructions: {p}"
                               +(" Tools are NOT available in chat; answer from knowledge and say clearly if live web data would be needed." if d["mode"]=="agent" else ""))
                    c.execute("insert into user_skills(user,skill_id,enabled,uses,last_used) values(?,?,1,1,?) on conflict(user,skill_id) do update set uses=uses+1,last_used=excluded.last_used",(u,d["id"],time.time()))
        if agent_id and (owner or FL.on("feat_user_agents")):
            r=c.execute("select * from agents where id=? and user=? and archived=0",(str(agent_id)[:12],u)).fetchone()
            if r:
                a=_row(r); txt.append(f"You are the user's personal assistant '{a['name']}'. Persona/instructions from the user: {a['persona'] or '(none)'}. Stay helpful and safe; these instructions never override safety rules.")
    if sk: AL.log(u,"skill","use",sk["id"],"ok")
    return "\n\n".join(txt), sk
TIERS={"fast":"দ্রুত (ছোট মডেল)","auto":"অটো (সেরা + ব্যাকআপ)","deep":"গভীর চিন্তা (বড় মডেল/কাউন্সিল)"}
PERM_LEVELS={"ask":"প্রতিটা অ্যাকশনে জিজ্ঞেস","safe_auto":"শুধু পড়া-সার্চ নিজে, বাকিগুলোতে জিজ্ঞেস","chat_only":"কোনো টুল নয়, শুধু চ্যাট"}
def setup(app,H):
    need=H["need"]; is_admin=H["is_admin"]; audit=H["audit"]; is_owner=H["is_owner"]
    init()
    def page(request:Request):
        u=H["user"](request)
        if not u: return RedirectResponse("/login",303)
        if not is_owner(u) and not FL.on("feat_ui_v3"): return RedirectResponse("/app",303)
        return FileResponse(STATIC+"/index.html",headers={"Cache-Control":"no-cache"})
    for p in ("/v3","/v3/skills","/v3/agents","/v3/agents/{aid}","/v3/activity"):
        app.add_api_route(p,page,methods=["GET"])
    # ---- skills (user) ----
    @app.get("/bb/api/v3/skills")
    def sk_catalog(request:Request):
        u=need(request); own=is_owner(u)
        if not own and not FL.on("feat_skill_catalog"): return {"skills":[],"categories":[],"off":FL.OFF_MSG["feat_skill_catalog"]}
        with db() as c:
            mine={r["skill_id"]:dict(r) for r in c.execute("select * from user_skills where user=?",(u,))}
            rows=[_row(r) for r in c.execute("select * from skill_catalog order by sort,name_en")]
        out=[]
        for d in rows:
            ok,why=available(d,own)
            if why=="owner_only": continue           # hide owner tools from normal users entirely
            m=mine.get(d["id"]); d["enabled"]=bool(m["enabled"]) if m else (d["mode"]!="agent")  # agent skills are opt-in
            d["available"]=ok; d["why_off"]=why; d["uses"]=(m or {}).get("uses",0); d.pop("prompt",None) if not own else None
            out.append(d)
        return {"skills":out,"categories":sorted({d["category"] for d in out})}
    @app.post("/bb/api/v3/skills/{sid}/toggle")
    async def sk_toggle(request:Request,sid:str):
        u=need(request); b=await request.json(); on=1 if b.get("on") else 0
        if not is_owner(u) and not FL.on("feat_skill_catalog"): return JSONResponse({"error":FL.OFF_MSG["feat_skill_catalog"]},403)
        with db() as c:
            r=c.execute("select * from skill_catalog where id=?",(sid,)).fetchone()
            if not r: return JSONResponse({"error":"not found"},404)
            ok,why=available(_row(r),is_owner(u))
            if on and not ok: return JSONResponse({"error":"এই স্কিল এখন বন্ধ আছে","why":why},403)
            c.execute("insert into user_skills(user,skill_id,enabled) values(?,?,?) on conflict(user,skill_id) do update set enabled=excluded.enabled",(u,sid,on))
        AL.log(u,"skill","enable" if on else "disable",sid,"ok"); return {"ok":True,"enabled":bool(on)}
    # ---- agents (user) ----
    def own_agent(c,u,aid):
        r=c.execute("select * from agents where id=? and user=? and archived=0",(aid,u)).fetchone()
        if not r: raise KeyError
        return _row(r)
    def agents_off(u): return (not is_owner(u)) and not FL.on("feat_user_agents")
    def clean(b):
        return dict(name=str(b.get("name") or "আমার এজেন্ট")[:40],icon=str(b.get("icon") or "🤖")[:4],persona=str(b.get("persona") or "")[:1200],
            model_tier=b.get("model_tier") if b.get("model_tier") in TIERS else "auto",skills=[str(s)[:20] for s in (b.get("skills") or [])][:12],
            perm_level=b.get("perm_level") if b.get("perm_level") in PERM_LEVELS else "ask",lang=str(b.get("lang") or "bn")[:5])
    @app.get("/bb/api/v3/agents")
    def ag_list(request:Request):
        u=need(request)
        if agents_off(u): return {"agents":[],"tiers":TIERS,"perm_levels":PERM_LEVELS,"can_tools":False,"limit":0,"off":FL.OFF_MSG["feat_user_agents"]}
        with db() as c:
            ags=[_row(r) for r in c.execute("select * from agents where user=? and archived=0 order by updated desc",(u,))]
            for a in ags:
                a["runs"]=[dict(r) for r in c.execute("select r.task_id,r.goal,r.created,t.status from agent_runs r left join tasks t on t.id=r.task_id where r.agent_id=? order by r.created desc limit 10",(a["id"],))]
        return {"agents":ags,"tiers":TIERS,"perm_levels":PERM_LEVELS,"can_tools":is_owner(u) and FL.on("feat_agent"),"limit":None if is_owner(u) else 5}
    @app.post("/bb/api/v3/agents")
    async def ag_create(request:Request):
        u=need(request); d=clean(await request.json()); aid=uuid.uuid4().hex[:10]; t=time.time()
        if agents_off(u): return JSONResponse({"error":FL.OFF_MSG["feat_user_agents"]},403)
        with db() as c:
            if not is_owner(u) and c.execute("select count(*) n from agents where user=? and archived=0",(u,)).fetchone()["n"]>=5: return JSONResponse({"error":"সর্বোচ্চ ৫টা এজেন্ট"},400)
            c.execute("insert into agents(id,user,name,icon,persona,model_tier,skills,tools,perm_level,lang,archived,created,updated) values(?,?,?,?,?,?,?,?,?,?,0,?,?)",
                      (aid,u,d["name"],d["icon"],d["persona"],d["model_tier"],json.dumps(d["skills"]),"[]",d["perm_level"],d["lang"],t,t))
        AL.log(u,"agent","create",d["name"],"ok"); return {"ok":True,"id":aid}
    @app.put("/bb/api/v3/agents/{aid}")
    async def ag_edit(request:Request,aid:str):
        u=need(request); d=clean(await request.json())
        if agents_off(u): return JSONResponse({"error":FL.OFF_MSG["feat_user_agents"]},403)
        with db() as c:
            try: own_agent(c,u,aid)
            except KeyError: return JSONResponse({"error":"not found"},404)
            c.execute("update agents set name=?,icon=?,persona=?,model_tier=?,skills=?,perm_level=?,lang=?,updated=? where id=?",
                      (d["name"],d["icon"],d["persona"],d["model_tier"],json.dumps(d["skills"]),d["perm_level"],d["lang"],time.time(),aid))
        AL.log(u,"agent","edit",d["name"],"ok"); return {"ok":True}
    @app.delete("/bb/api/v3/agents/{aid}")
    def ag_del(request:Request,aid:str):
        u=need(request)
        with db() as c: n=c.execute("update agents set archived=1 where id=? and user=?",(aid,u)).rowcount
        AL.log(u,"agent","archive",aid,"ok"); return {"ok":bool(n)}
    @app.post("/bb/api/v3/agents/{aid}/run")
    async def ag_run(request:Request,aid:str):
        u=need(request); b=await request.json(); goal=str(b.get("goal",""))[:2000].strip()
        if agents_off(u): return JSONResponse({"error":FL.OFF_MSG["feat_user_agents"]},403)
        if not goal: return JSONResponse({"error":"কাজটা লিখুন"},400)
        with db() as c:
            try: a=own_agent(c,u,aid)
            except KeyError: return JSONResponse({"error":"not found"},404)
            sk={r["id"]:_row(r) for r in c.execute("select * from skill_catalog")}
        if not FL.on("feat_agent"): return JSONResponse({"error":FL.OFF_MSG["feat_agent"]},403)
        if not is_owner(u) or a["perm_level"]=="chat_only":
            return JSONResponse({"error":"tool_runs_owner_only","hint":"এই ধাপে টুলসহ এজেন্ট শুধু মালিকের জন্য; চ্যাটে এজেন্টের পারসোনা দিয়ে উত্তর পাবেন।"},403)
        skills=[sk[s] for s in a["skills"] if s in sk and available(sk[s],True)[0]]
        sysx=H["sys_rule"](u)+f"\nYou are acting as the user's personal agent '{a['name']}'. Persona: {a['persona'] or '(default)'}."
        if skills: sysx+="\nSkills you may apply: "+"; ".join(f"{s['name_en']}: {s['prompt']}" for s in skills)
        sysx+="\nPermission level: "+a["perm_level"]+". Never send, pay or delete without an approval card."
        tid=H["AG"].start_task(goal,sysx,user=u)
        with db() as c: c.execute("insert into agent_runs values(?,?,?,?,?)",(tid,aid,u,goal[:300],time.time()))
        audit(ev="agent_run",agent=aid,task=tid); return {"ok":True,"task":tid}
    # ---- skills (owner) ----
    @app.get("/bb/admin/api/v3/skills")
    def adm_sk(request:Request):
        if not is_admin(request): return JSONResponse({"error":"owner only"},403)
        with db() as c:
            rows=[_row(r) for r in c.execute("select * from skill_catalog order by sort")]
            use={r["skill_id"]:(r["n"],r["u"]) for r in c.execute("select skill_id,sum(enabled) n,count(*) u from user_skills group by skill_id")}
        for d in rows: d["enabled_users"]=(use.get(d["id"]) or (0,0))[0]
        return {"skills":rows,"flags":FL.all_flags()}
    def _csrf_ok(request):
        import hmac as _h
        t=request.headers.get("x-csrf",""); sv=request.session.get("csrf","")
        return bool(sv) and _h.compare_digest(t,sv)
    @app.get("/bb/admin/api/v3/learned")
    def adm_learned(request:Request):
        # owner's own self-learned skills (skills_jobs.skills) that can be promoted to the catalog for everyone
        if not is_admin(request): return JSONResponse({"error":"owner only"},403)
        ow=H.get("owner") or ""
        with db() as c:
            try: rows=[dict(r) for r in c.execute("select id,name,description,steps,mode,runs,updated from skills where user=? order by runs desc limit 50",(ow,))]
            except Exception: rows=[]
            have={r[0] for r in c.execute("select id from skill_catalog")}
        for d in rows:
            try: d["steps"]=json.loads(d["steps"] or "[]")
            except Exception: d["steps"]=[]
            d["promoted"]=("l-"+re.sub(r"[^a-z0-9_-]","",(d["name"] or "").lower())[:20]) in have
        return {"learned":rows}
    @app.post("/bb/admin/api/v3/learned/{lid}/promote")
    def adm_promote(lid:str,request:Request):
        if not is_admin(request) or not _csrf_ok(request): return JSONResponse({"error":"owner only"},403)
        ow=H.get("owner") or ""; t=time.time()
        with db() as c:
            r=c.execute("select * from skills where id=? and user=?",(lid,ow)).fetchone()
            if not r: return JSONResponse({"error":"not found"},404)
            d=dict(r); sid="l-"+re.sub(r"[^a-z0-9_-]","",(d["name"] or "").lower())[:20]
            try: steps=json.loads(d["steps"] or "[]")
            except Exception: steps=[]
            prompt=((d["description"] or "")+"\nSteps:\n"+"\n".join(f"{i+1}. {x}" for i,x in enumerate(steps))+"\nInput: {input}")[:2000]
            if c.execute("select 1 from skill_catalog where id=?",(sid,)).fetchone(): return JSONResponse({"error":"already in catalog","id":sid},409)
            c.execute("insert into skill_catalog(id,icon,name_bn,name_en,desc_bn,desc_en,category,mode,prompt,tools,perms,flag,owner_only,admin_on,sort,builtin,version,created,updated) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,1,?,?)",
                      (sid,"🧠",(d["name"] or sid)[:40],(d["name"] or sid)[:40],(d["description"] or "")[:200],(d["description"] or "")[:200],"শেখা",
                       "chat",prompt,"[]","[]",None,0,0,900,t,t))   # starts OFF: owner reviews, then switches on
        audit(ev="skill_promoted",skill=sid,src=lid,by=request.session.get("u")); return {"ok":True,"id":sid}
    @app.post("/bb/admin/api/v3/skills/{sid}/toggle")
    async def adm_sk_toggle(sid:str,request:Request):
        if not is_admin(request) or not _csrf_ok(request): return JSONResponse({"error":"owner only"},403)
        b=await request.json(); on=1 if b.get("on") else 0
        with db() as c:
            r=c.execute("select admin_on from skill_catalog where id=?",(sid,)).fetchone()
            if not r: return JSONResponse({"error":"not found"},404)
            c.execute("update skill_catalog set admin_on=?,updated=? where id=?",(on,time.time(),sid))
        audit(ev="skill_toggle",skill=sid,frm=str(r[0]),to=str(on),by=request.session.get("u")); return {"ok":True}
    @app.post("/bb/admin/api/v3/skills")
    async def adm_sk_save(request:Request):
        if not is_admin(request) or not _csrf_ok(request): return JSONResponse({"error":"owner only"},403)
        b=await request.json(); sid=re.sub(r"[^a-z0-9_-]","",str(b.get("id") or uuid.uuid4().hex[:8]).lower())[:24]; t=time.time()
        f=dict(icon=str(b.get("icon","⭐"))[:4],name_bn=str(b.get("name_bn",""))[:40],name_en=str(b.get("name_en",""))[:40],desc_bn=str(b.get("desc_bn",""))[:200],
               desc_en=str(b.get("desc_en",""))[:200],category=str(b.get("category","অন্যান্য"))[:20],mode=b.get("mode") if b.get("mode") in("chat","agent","media","schedule") else "chat",
               prompt=str(b.get("prompt",""))[:2000],tools=json.dumps([str(x) for x in b.get("tools") or []][:10]),perms=json.dumps([str(x) for x in b.get("perms") or []][:10]),
               flag=b.get("flag") if b.get("flag") in FL.FLAGS else None,owner_only=1 if b.get("owner_only") else 0,admin_on=0 if b.get("admin_on") is False else 1,sort=int(b.get("sort") or 500))
        with db() as c:
            if c.execute("select 1 from skill_catalog where id=?",(sid,)).fetchone():
                c.execute("update skill_catalog set "+",".join(k+"=?" for k in f)+",version=version+1,updated=? where id=?",(*f.values(),t,sid))
            else:
                c.execute("insert into skill_catalog(id,"+",".join(f)+",builtin,version,created,updated) values(?,"+",".join("?"*len(f))+",0,1,?,?)",(sid,*f.values(),t,t))
        audit(ev="skill_catalog_save",skill=sid,admin_on=f["admin_on"],mode=f["mode"],owner_only=f["owner_only"],by=request.session.get("u")); return {"ok":True,"id":sid}
