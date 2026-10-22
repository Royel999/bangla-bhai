import os, json, time, asyncio, uuid, re, hashlib, secrets, httpx, sqlite3, base64
BASE=os.path.expanduser('~/bangla_bhai'); S=os.path.expanduser('~/.secrets')
def env(f):
    d={}
    try:
        for l in open(f):
            if '=' in l: k,v=l.strip().split('=',1); d[k]=v.strip().strip('"')
    except Exception: pass
    return d
K={}
for f in ("groq","gemini","openrouter","deepgram","cartesia","assemblyai"): K.update(env(f"{S}/{f}.env"))
AUDIT=BASE+'/audit.jsonl'
def audit(**k): open(AUDIT,'a').write(json.dumps({"t":time.time(),**k},ensure_ascii=False)+"\n")
DB=BASE+'/data.db'
def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
with db() as c:
    c.executescript("""create table if not exists devices(id text primary key,name text,kind text,token_hash text,status text,created real,last_seen real,info text);
create table if not exists perms(device text,cap text,mode text,primary key(device,cap));""")
CAPS={"camera":"📷 ক্যামেরা","mic":"🎙️ মাইক্রোফোন","screen":"🖥️ স্ক্রিন দেখা ও নিয়ন্ত্রণ","browser":"🌐 ব্রাউজার নিয়ন্ত্রণ","sms":"💬 এসএমএস পড়া","sms_send":"✉️ এসএমএস পাঠানো","call":"📞 কল","personal":"📒 ব্যক্তিগত তথ্য (কল লগ/কন্টাক্ট/নোটিফ/ব্যাটারি)","location":"📍 লোকেশন ও সেন্সর","settings_ctl":"⚙️ ফোন সেটিংস (ওয়াইফাই/ব্লুটুথ/ভলিউম ইত্যাদি)","apps":"📱 অ্যাপ নিয়ন্ত্রণ","full":"🛠️ পূর্ণ ডিভাইস নিয়ন্ত্রণ (শেল, ফাইল, অ্যাপ)"}
MODES=("ask","once","always","off")
def get_perm(dev,cap):
    with db() as c: r=c.execute("select mode from perms where device=? and cap=?",(dev,cap)).fetchone()
    return r["mode"] if r else "ask"
def set_perm(dev,cap,mode):
    with db() as c: c.execute("insert or replace into perms values(?,?,?)",(dev,cap,mode))
    audit(ev="perm_set",device=dev,cap=cap,mode=mode)
def revoke_all():
    with db() as c:
        c.execute("delete from perms"); c.execute("update devices set status='revoked' where status='approved'")
    for d in list(LINK_Q): LINK_Q[d]=asyncio.Queue()
    audit(ev="revoke_all")
def devices():
    with db() as c: rows=[dict(r) for r in c.execute("select id,name,kind,status,created,last_seen,info from devices order by created")]
    out=[{"id":"box","name":"বাংলা ভাই সার্ভার (বক্স)","kind":"server","status":"approved","last_seen":time.time(),"online":True}]
    for r in rows: r["online"]=bool(r["last_seen"] and time.time()-r["last_seen"]<40); out.append(r)
    for d in out: d["perms"]={k:get_perm(d["id"],k) for k in CAPS}
    return out
# ---------------- Royal Link ----------------
LINK_Q={}; LINK_RES={}; LINK_OWN={}
def pair_request(name,kind,info):
    did=uuid.uuid4().hex[:10]; tok=secrets.token_urlsafe(32)
    with db() as c: c.execute("insert into devices values(?,?,?,?,?,?,?,?)",(did,name[:60],kind[:20],hashlib.sha256(tok.encode()).hexdigest(),"pending",time.time(),None,json.dumps(info)[:500]))
    audit(ev="pair_request",device=did,name=name,kind=kind); return did,tok
def pair_decide(did,ok):
    with db() as c: c.execute("update devices set status=? where id=?",("approved" if ok else "denied",did))
    audit(ev="pair_"+("approved" if ok else "denied"),device=did)
def dev_by_token(tok):
    h=hashlib.sha256((tok or "").encode()).hexdigest()
    with db() as c:
        r=c.execute("select * from devices where token_hash=?",(h,)).fetchone()
        if r: c.execute("update devices set last_seen=? where id=?",(time.time(),r["id"]))
    return dict(r) if r else None
async def device_call(did,action,args,timeout=120):
    q=LINK_Q.setdefault(did,asyncio.Queue()); cid=uuid.uuid4().hex[:8]; fut=asyncio.get_running_loop().create_future(); LINK_RES[cid]=fut; LINK_OWN[cid]=did
    await q.put({"cid":cid,"action":action,"args":args})
    try: return await asyncio.wait_for(fut,timeout)
    finally: LINK_RES.pop(cid,None); LINK_OWN.pop(cid,None)
# ---------------- tools ----------------
TOOLS={
 "web_search":("browser","ইন্টারনেটে খোঁজা",{"query":"str"}),
 "mcp_call":("browser","Connections-এ যুক্ত MCP সার্ভারের টুল চালানো",{"server":"name","tool":"str","args":"json object"}),
 "browse":("browser","হেডলেস ব্রাউজারে ওয়েবপেজ খোলা ও পড়া (স্ক্রিনশটসহ)",{"url":"str"}),
 "shell":("full","ডিভাইসে শেল কমান্ড চালানো",{"device":"box বা device id","cmd":"str"}),
 "screenshot":("screen","ডিভাইসের স্ক্রিনশট নেওয়া",{"device":"device id"}),
 "click":("screen","মাউস ক্লিক",{"device":"id","x":"int","y":"int"}),
 "type_text":("screen","কীবোর্ডে লেখা",{"device":"id","text":"str"}),
 "camera_photo":("camera","ক্যামেরায় ছবি তোলা",{"device":"id"}),
 "mic_record":("mic","মাইকে কয়েক সেকেন্ড রেকর্ড",{"device":"id","seconds":"int"}),
 "sms_list":("sms","এসএমএস ইনবক্স পড়া",{"device":"id","limit":"int"}),
 "sms_send":("sms_send","এসএমএস পাঠানো (সবসময় অনুমতি কার্ড)",{"device":"id","number":"str","text":"str"}),
 "call_make":("call","কল করা",{"device":"id","number":"str"}),
 "call_control":("call","কল answer/end/reject",{"device":"id","do":"answer|end|reject"}),
 "call_log":("personal","কল লগ",{"device":"id","limit":"int"}),
 "contacts":("personal","কন্টাক্ট তালিকা",{"device":"id"}),
 "notifications":("personal","নোটিফিকেশন তালিকা",{"device":"id"}),
 "battery":("personal","ব্যাটারি স্ট্যাটাস",{"device":"id"}),
 "location":("location","লোকেশন",{"device":"id"}),
 "sensor":("location","সেন্সর পড়া",{"device":"id","name":"str"}),
 "clipboard":("personal","ক্লিপবোর্ড পড়া/লেখা",{"device":"id","set":"str"}),
 "settings_ctl":("settings_ctl","ওয়াইফাই/ব্লুটুথ/ব্রাইটনেস/ভলিউম/টর্চ/এয়ারপ্লেন/DND/settings put-get",{"device":"id","what":"wifi|bluetooth|brightness|volume|torch|airplane|dnd|put|get","value":"str"}),
 "app_list":("apps","ইনস্টলড অ্যাপ তালিকা (pm list)",{"device":"id"}),
 "app_launch":("apps","অ্যাপ খোলা",{"device":"id","package":"str"}),
 "app_stop":("apps","অ্যাপ force-stop",{"device":"id","package":"str"}),
 "open_url":("apps","ফোনে URL খোলা",{"device":"id","url":"str"}),
 "ui_dump":("screen","স্ক্রিনের UI পড়া (uiautomator dump)",{"device":"id"}),
 "keyevent":("screen","কীইভেন্ট (BACK/HOME/ENTER ইত্যাদি)",{"device":"id","key":"str"}),
 "swipe":("screen","সোয়াইপ",{"device":"id","x1":"int","y1":"int","x2":"int","y2":"int","ms":"int"}),
 "am_start":("full","অ্যাপ খোলা (am start)",{"device":"id","component":"str"}),
 "list_devices":(None,"সংযুক্ত ডিভাইসের তালিকা",{}),
}
import shutil as _sh, ipaddress as _ip, socket as _so
from urllib.parse import urlparse as _up
SECRETS_DIR=os.path.expanduser("~/.secrets")
def _shell_argv(cmd):
    # bubblewrap: hide ~/.secrets (tmpfs overlay); fallback refuses secret paths
    if _sh.which("bwrap"):
        return ["bwrap","--dev-bind","/","/","--tmpfs",SECRETS_DIR,"--die-with-parent","--","/bin/bash","-c",cmd]
    if re.search(r"\.secrets|\.env\b|bangla_bhai\.env",cmd): raise RuntimeError("গোপন ফাইলে প্রবেশ নিষিদ্ধ")
    return None
def _url_ok(u):
    try: p=_up(u)
    except Exception: return False
    if p.scheme not in ("http","https") or not p.hostname: return False
    h=p.hostname.strip("[]").lower()
    if h in("localhost",) or h.endswith(".localhost") or h.endswith(".local") or h.endswith(".internal"): return False
    try: infos=_so.getaddrinfo(h,None)
    except Exception: return False
    for i in infos:
        a=_ip.ip_address(i[4][0].split("%")[0])
        if getattr(a,"ipv4_mapped",None): a=a.ipv4_mapped
        if a in _ip.ip_network("198.18.0.0/15"): continue  # box egress fake-IP DNS (public hosts)
        if a.is_loopback or a.is_private or a.is_link_local or a.is_reserved or a.is_multicast or a.is_unspecified: return False
    return True
async def _shell_box(cmd):
    av=_shell_argv(cmd)
    if av: p=await asyncio.create_subprocess_exec(*av,cwd=BASE+"/sandbox",stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT)
    else: p=await asyncio.create_subprocess_shell(cmd,cwd=BASE+"/sandbox",stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT)
    try: out,_=await asyncio.wait_for(p.communicate(),60)
    except asyncio.TimeoutError: p.kill(); raise RuntimeError("৬০ সেকেন্ডে শেষ হয়নি (timeout)")
    o=out.decode("utf-8","ignore")[-4000:]
    if p.returncode: raise RuntimeError(f"exit {p.returncode}: {o}")
    return o or "(কোনো আউটপুট নেই)"
_PW=None
async def _browser():
    global _PW
    if not _PW:
        from playwright.async_api import async_playwright
        pw=await async_playwright().start(); _PW=await pw.chromium.launch(headless=True)
    return _PW
async def run_tool(name,a):
    if name=="mcp_call":
        import connections as CN
        return await CN.mcp_call((TASKS.get(t_id_ctx.get()) or {}).get("user"),a)
    if name=="list_devices": return json.dumps([{k:d[k] for k in ("id","name","kind","status","online")} for d in devices()],ensure_ascii=False)
    if name=="web_search":
        import ground as GR
        r=await GR.search(a["query"],6)
        if not r: raise RuntimeError("কোনো ফলাফল পাওয়া যায়নি")
        return r
    if name=="browse":
        if not _url_ok(a.get("url","")): raise RuntimeError("এই URL ব্লক করা (লোকাল/প্রাইভেট/file নিষিদ্ধ)")
        b=await _browser(); pg=await b.new_page(viewport={"width":1200,"height":800})
        async def _guard(route):
            if _url_ok(route.request.url): await route.continue_()
            else: await route.abort()
        await pg.route("**/*",_guard)
        try:
            await pg.goto(a["url"],timeout=30000)
            if not _url_ok(pg.url): raise RuntimeError("রিডাইরেক্ট ব্লক করা")
            fn=f"shots/{uuid.uuid4().hex}.png"; await pg.screenshot(path=BASE+"/static/"+fn)
            t=await pg.inner_text("body"); return {"text":f"শিরোনাম: {await pg.title()}\n{t[:3500]}","image":"/bb/static/"+fn}
        finally: await pg.close()
    dev=a.get("device","box")
    if dev=="box":
        if name=="shell": return await _shell_box(a.get("cmd") or a.get("command") or "echo ok")
        raise RuntimeError("বক্সে ক্যামেরা/মাইক/স্ক্রিন নেই — একটা যুক্ত ডিভাইস বেছে নাও")
    # phone/laptop shell etc → device_call below
    d=[x for x in devices() if x["id"]==dev]
    if not d or d[0]["status"]!="approved": raise RuntimeError(f"ডিভাইস '{dev}' যুক্ত/অনুমোদিত নয়")
    if not d[0]["online"]: raise RuntimeError(f"ডিভাইস '{d[0]['name']}' অফলাইন")
    r=await device_call(dev,name,a)
    if r.get("error"): raise RuntimeError(r["error"])
    return r

def redact_secrets(text):
    if not text: return text
    t=re.sub(r'(?i)(OTP|one[ -]?time|verification code|কোড|পিন|PIN)([^0-9]{0,24})([0-9]{4,8})', r'\1\2****', text)
    t=re.sub(r'(?i)(\bis\s+)([0-9]{4,8})(\s+for)', r'\1****\3', t)
    return t
# ---------- intent ----------
ACTION_KW=re.compile(r"(ফোন|মোবাইল|ডিভাইস|ল্যাপটপ|কম্পিউটার|বক্স|চালাও|চালান|খোলো|খুলে|স্ক্রিনশট|screenshot|ক্যামেরা|মাইক|ব্রাউজ|সার্চ|খুঁজে|ডাউনলোড|ইনস্টল|shell|uname|df|termux|কমান্ড|command|tap|swipe|NEXG|ডিভাইসে|ফোনে|মেসেজ|ইনবক্স|sms|এসএমএস|পাঠাও|কল\s*কর|কল\s*লগ|ডায়াল|কন্টাক্ট|পরিচিতি|নোটিফ|ব্যাটারি|battery|পড়ে|পড়ো|ওয়াইফাই|wifi|ব্লুটুথ|ব্রাইটনেস|ভলিউম|টর্চ|এয়ারপ্লেন|লোকেশন|location|ক্লিপবোর্ড|অ্যাপ|app|খোল)",re.I)
async def classify_intent(text:str)->dict:
    """Return {action:bool, reason, goal, device_hint}"""
    t=(text or "").strip()
    if not t: return {"action":False,"reason":"empty","goal":t,"device_hint":None}
    phone=bool(re.search(r"(ফোন|মোবাইল|অ্যান্ড্রয়েড|android|NEXG|termux)",t,re.I))
    box=bool(re.search(r"(বক্স|সার্ভার|laptop|ল্যাপটপ|কম্পিউটার)",t,re.I))
    kw=bool(ACTION_KW.search(t))
    # paired phone id if any
    ph=next((d for d in devices() if d["status"]=="approved" and d["kind"] in("android","phone") and d["id"]!="box"),None)
    hint=(ph["id"] if ph and phone else ("box" if box else (ph["id"] if ph and kw and not box else None)))
    if kw:
        return {"action":True,"reason":"keyword","goal":t,"device_hint":hint,"confidence":0.9}
    # LLM tie-break for ambiguous
    try:
        _,j=await llm_json([
          {"role":"system","content":'Classify user message. JSON only: {"action":true/false,"reason":"...","device_hint":"phone"|"box"|null}. action=true if they want you to DO something on a device, browse, search the live web, take photo/screenshot, run a command — not if they only want an explanation/tutorial.'},
          {"role":"user","content":t[:1500]}])
        act=bool(j.get("action"))
        dh=j.get("device_hint")
        if dh=="phone" and ph: hint=ph["id"]
        elif dh=="box": hint="box"
        return {"action":act,"reason":j.get("reason") or "llm","goal":t,"device_hint":hint,"confidence":0.7}
    except Exception as e:
        return {"action":False,"reason":f"llm-fail:{e}","goal":t,"device_hint":hint,"confidence":0.2}

def pick_device(hint=None, goal=""):
    ds=[d for d in devices() if d["status"]=="approved"]
    phones=[d for d in ds if d["id"]!="box" and d.get("kind") in("android","phone")]
    phone=next((d for d in phones if d.get("online")), phones[0] if phones else None)
    if hint and hint!="box":
        d=next((x for x in ds if x["id"]==hint),None)
        if d: return d["id"]
    if hint=="box" and not re.search(r"(ফোন|মোবাইল|NEXG|android)",goal or "",re.I): return "box"
    if phone and re.search(r"(ফোন|মোবাইল|অ্যান্ড্রয়েড|android|NEXG|termux|চালাও|কমান্ড|shell|uname|df|স্ক্রিন|ক্যামেরা|মেসেজ|ইনবক্স|sms|এসএমএস|পাঠাও|কল|কন্টাক্ট|নোটিফ|ব্যাটারি|ওয়াইফাই|ব্লুটুথ|ভলিউম|টর্চ|লোকেশন|ক্লিপবোর্ড|অ্যাপ)",goal or "",re.I):
        return phone["id"]
    return "box"


# ---------------- agent loop ----------------
TASKS={}
SYS="""তুমি 'বাংলা ভাই' — Royal Universe-এর আসল এজেন্ট। মালিক 'রয়েল'। তোমার হাতে আসল টুল আছে; কখনো বলো না যে ডিভাইসে কমান্ড চালাতে পারো না। অনুমতি নিয়ে টুল চালাও।
টুল: {tools}
ডিভাইস: {devs}
নিয়ম:
- ফোন/মোবাইল/অ্যান্ড্রয়েড/NEXG বললে device = সেই paired ফোনের id (বক্স নয়)।
- ল্যাপটপ/কম্পিউটার/বক্স না বললে এবং ফোন অনলাইন থাকলে শেল/স্ক্রিন/ক্যামেরা/মাইকের জন্য ফোন বেছে নাও।
- shell টুল: args={{"device":"<id>","cmd":"..."}} — কখনো tool=none নয়।
- প্রতি ধাপে শুধু একটা JSON:
{{"thought":"সংক্ষিপ্ত বাংলা ভাবনা","alternatives":["বিকল্প ১","বিকল্প ২"],"action":{{"tool":"shell|web_search|browse|list_devices|screenshot|camera_photo|mic_record|sms_list|sms_send|call_make|call_control|call_log|contacts|notifications|battery|location|sensor|clipboard|settings_ctl|app_list|app_launch|app_stop|open_url|ui_dump|keyevent|click|type_text|swipe|am_start","args":{{...}}}},"why":"কেন"}}
- টুলের আসল ফলাফল পাওয়ার আগে final দিও না এবং কল্পিত uname/df আউটপুট লিখো না।
- শেষ: {{"thought":"...","final":"রয়েলের জন্য বাংলা Markdown উত্তর"}}
- টুল ব্যর্থ হলে রিপেয়ার করে অন্য পথ চেষ্টা করো। মালিক 'না' বললে সেই কাজ আর করবে না।
"""
import router as RT, actlog as AL
async def llm_json(msgs):
    try: m,t,_=await RT.complete(msgs,json_mode=True,timeout=60,tries=2)
    except RT.ModelError: raise RuntimeError("model_unavailable")
    t=re.sub(r"<think>.*?</think>","",t,flags=re.S)
    try: return m,json.loads(t[t.find("{"):t.rfind("}")+1])
    except Exception: return m,{"thought":"","final":t.strip()[:3000]}
FRIENDLY={"model_unavailable":"এই মুহূর্তে কোনো মডেল সাড়া দিচ্ছে না — একটু পরে আবার চেষ্টা করুন।"}
def friendly(e):
    s=str(e) or type(e).__name__
    if s in FRIENDLY: return FRIENDLY[s]
    s=s.splitlines()[0] if s else s
    return re.sub(r"(/home/\S+|File \".*?\"|Traceback.*)","",s)[:200] or "অপ্রত্যাশিত সমস্যা হয়েছে।"
def ev(t,**k):
    k.update(type=t,ts=time.time()); tid=t_id_ctx.get(); T=TASKS[tid]; T["events"].append(k)
    try: AL.task_save(tid,T.get("user"),T.get("goal"),T.get("sysx",""),T["status"],T["events"][-300:])
    except Exception: pass
ON_DONE=[]
import contextvars; t_id_ctx=contextvars.ContextVar("tid")
def start_task(goal,sysx="",user=None,tid=None,resume=None):
    tid=tid or uuid.uuid4().hex[:10]
    TASKS[tid]={"events":list((resume or {}).get("events",[])),"pending":{},"status":"running","goal":goal,"user":user,"sysx":sysx}
    AL.task_save(tid,user,goal,sysx,"running",TASKS[tid]["events"],resumes=(resume or {}).get("resumes"))
    async def runner():
        t_id_ctx.set(tid); st="done"
        try:
            if resume: ev("resume",text="সার্ভার রিস্টার্টের পর কাজটা আবার চালু করছি...")
            await loop(tid,goal,sysx,resume_ctx=(resume or {}).get("ctx"))
        except Exception as e:
            st="failed"; ev("error",text="এজেন্ট থেমে গেছে: "+friendly(e))
        TASKS[tid]["status"]=st; ev("end")
        if st=="done":
            for f in ON_DONE:
                try: f(tid)
                except Exception: pass
    asyncio.create_task(runner()); audit(ev="agent_task",task=tid,goal=goal[:200])
    AL.log(user,"agent","task",goal[:200],"resumed" if resume else "started",task=tid); return tid
def resume_all():
    """called once at startup: resume interrupted tasks once, otherwise mark failed."""
    AL.appr_expire_all(); out=[]
    for t in AL.tasks_running():
        evs=t["events"]
        if t["resumes"]>=1 or time.time()-t["updated"]>3600:
            evs.append({"type":"error","text":"সার্ভার রিস্টার্টে কাজটা থেমে গেছে; আবার চালাতে নতুন করে বলুন।","ts":time.time()}); evs.append({"type":"end","ts":time.time()})
            AL.task_save(t["id"],t["user"],t["goal"],t["sysx"],"failed",evs); AL.log(t["user"],"agent","task",t["goal"][:200],"failed after restart",ok=False,task=t["id"]); out.append((t["id"],"failed")); continue
        done=[e for e in evs if e.get("type")=="result"][-5:]
        ctx="\n".join(f"- {e.get('tool')}: {str(e.get('text',''))[:400]}" for e in done)
        start_task(t["goal"],t["sysx"] or "",t["user"],tid=t["id"],resume={"events":evs,"resumes":t["resumes"]+1,"ctx":ctx}); out.append((t["id"],"resumed"))
    return out
def get_task(tid):
    t=TASKS.get(tid)
    if t: return t
    d=AL.task_get(tid)
    return d and {"events":d["events"],"status":d["status"],"goal":d["goal"],"user":d["user"],"pending":{}}
async def ask(tid,tool,args,why,cap):
    aid=uuid.uuid4().hex[:8]; f=asyncio.get_running_loop().create_future(); TASKS[tid]["pending"][aid]=f
    rk=AL.risk(tool,args); AL.appr_open(aid,TASKS[tid].get("user"),tid,tool,args,why,rk)
    ev("approval",id=aid,tool=tool,args=args,why=why,cap=cap,capname=CAPS.get(cap,""),risk=rk)
    try: d=await asyncio.wait_for(f,600)
    except asyncio.TimeoutError: d="timeout"
    TASKS[tid]["pending"].pop(aid,None); AL.appr_close(aid,{"yes":"approved","no":"denied"}.get(d,d)); AL.log(TASKS[tid].get("user"),"approval",tool,args,d,ok=(d=="yes"),task=tid); ev("decision",id=aid,decision=d); audit(ev="agent_decision",task=tid,tool=tool,decision=d); return d
def decide(tid,aid,d):
    f=TASKS.get(tid,{}).get("pending",{}).get(aid)
    if f and not f.done(): f.set_result(d); return True
    return False
async def loop(tid,goal,sysx="",resume_ctx=None):
    devs=", ".join(f"{d['id']}={d['name']}({'অনলাইন' if d['online'] else 'অফলাইন'})" for d in devices() if d["status"]=="approved")
    tools="; ".join(f"{n}{list(v[2])}: {v[1]}" for n,v in TOOLS.items())
    try:
        import connections as CN; _mp=CN.mcp_prompt((TASKS.get(tid) or {}).get("user"))
        if _mp: tools+="\n"+_mp
    except Exception: pass
    hint=pick_device(None,goal)
    msgs=[{"role":"system","content":SYS.format(tools=tools,devs=devs)+f"\nডিফল্ট টার্গেট ডিভাইস id: {hint} (ফোনের কাজ হলে এটাই use করো।)"+("\n\nOVERRIDES (highest priority): "+sysx if sysx else "")},{"role":"user","content":goal}]+([{"role":"user","content":"(সার্ভার রিস্টার্টের আগে এই ধাপগুলো হয়ে গেছে, আবার করবে না; বাকিটা শেষ করো:)\n"+resume_ctx}] if resume_ctx else [])
    ev("plan",text="লক্ষ্য বুঝে পরিকল্পনা করছি...")
    fails=0; ran_ok=bool(resume_ctx)
    for step in range(10):
        model,j=await llm_json(msgs); msgs.append({"role":"assistant","content":json.dumps(j,ensure_ascii=False)})
        ev("think",text=j.get("thought",""),alternatives=j.get("alternatives",[]),model=model,step=step+1)
        fin=j.get("final"); act=j.get("action")
        needs_tool=not ran_ok and bool(re.search(r"(চালাও|চালান|uname|df\s*-h|স্ক্রিনশট|ক্যামেরা|shell|কমান্ড|ফোনে|ডিভাইসে|ব্রাউজ|সার্চ|মেসেজ|ইনবক্স|sms|এসএমএস|পাঠাও|কল|কন্টাক্ট|নোটিফ|ব্যাটারি|ওয়াইফাই|অ্যাপ|পড়)",goal,re.I))
        if fin and not act:
            if needs_tool and step<6:
                msgs.append({"role":"user","content":"তুমি টুল চালাওনি। কল্পিত ফলাফল নিষিদ্ধ। এখনই action JSON দাও — shell দিয়ে আসল কমান্ড চালাও (device=ফোনের id)।"}); ev("repair",text="টুল ছাড়া উত্তর বাতিল — আসল টুল চাই"); continue
            ev("final",text=fin); return
        if not act and not fin: msgs.append({"role":"user","content":"action বা final — একটা JSON দাও।"}); ev("repair",text="খালি উত্তর — আবার"); continue
        if not act:
            if needs_tool and step<6:
                msgs.append({"role":"user","content":"আগে tool action লাগবে। final এখন নয়।"}); ev("repair",text="final বাতিল — টুল চাই"); continue
            ev("final",text=fin or j.get("thought","")); return
        a=j["action"]; tool=a.get("tool"); args=a.get("args") or {}
        if not tool or tool in("none","null","N/A"): msgs.append({"role":"user","content":f"টুলের নাম দাও। তালিকা: {', '.join(TOOLS)}"}); ev("repair",text="টুলের নাম নেই — আবার"); continue
        if tool in("shell","bash","cmd") and not (args.get("cmd") or args.get("command")):
            cmd=None
            m=re.search(r"`([^`]+)`",goal)
            if m: cmd=m.group(1).strip()
            if not cmd:
                # "uname -a আর df -h চালিয়ে" / "run: foo"
                m=re.search(r"(uname\s+-a(?:\s*(?:আর|,|and|&|&&)\s*df\s*-h(?:\s*/?)?)|(?:df\s*-h(?:\s*/?)?)\s*(?:আর|,|and|&|&&)\s*uname\s+-a)",goal,re.I)
                if m: cmd=re.sub(r"\s*(?:আর|,|and)\s*"," && ",m.group(1),flags=re.I)
            if not cmd:
                m=re.search(r"(?:চালাও|চালান|run|execute)\s*[:\-]?\s*(.+)$",goal,re.I)
                if m and len(m.group(1))<200: cmd=m.group(1).strip()
            if not cmd: cmd="uname -a && df -h" if re.search(r"uname|df\s*-h",goal,re.I) else "echo ok"
            args={"device":args.get("device") or "box","cmd":cmd}
        
        alias={"bash":"shell","cmd":"shell","terminal":"shell","search":"web_search","open":"browse","navigate":"browse"}
        tool=alias.get(tool,tool)
        if tool not in TOOLS: msgs.append({"role":"user","content":f"'{tool}' নামে কোনো টুল নেই। তালিকা: {', '.join(TOOLS)}"}); ev("repair",text=f"অজানা টুল '{tool}' — ঠিক করছি"); continue
        cap=TOOLS[tool][0]
        if tool=="shell" or cap not in(None,"browser"):
            raw=args.get("device")
            if not raw or raw in("phone","android","mobile","ফোন") or (raw=="box" and re.search(r"(ফোন|মোবাইল|NEXG|android)",goal,re.I)):
                args["device"]=pick_device(raw if raw not in("phone","android","mobile","ফোন",None,"") else None, goal)
            dev=args.get("device","box")
        else:
            dev="box"
        mode=get_perm(dev,cap) if cap else "always"
        force_card = tool in("sms_send","call_make") or (tool=="shell" and args.get("device","box")=="box") or AL.risk(tool,args)=="high"  # destructive/outgoing: always confirm  # outgoing + box shell: always confirm
        if mode=="off": d="no"; ev("blocked",text=f"{CAPS[cap]} এই ডিভাইসে বন্ধ (অনুমতি কেন্দ্র)")
        elif (mode=="always" and not force_card) or tool=="list_devices": d="yes"; cap and ev("auto",text=f"'সবসময় অনুমতি' দেওয়া আছে — {CAPS[cap]}")
        else:
            d=await ask(tid,tool,args,j.get("why",""),cap)
            if mode=="once" and d=="yes": set_perm(dev,cap,"ask")
        if d!="yes":
            msgs.append({"role":"user","content":f"মালিক এই কাজের অনুমতি দেননি ({d})। এটা করবে না; বিকল্প বা চূড়ান্ত উত্তর দাও।"}); continue
        for attempt in range(2):
            ev("run",tool=tool,args=args,attempt=attempt+1)
            try:
                out=await run_tool(tool,args); img=None
                if isinstance(out,dict): img=out.get("image"); out=out.get("text") or json.dumps({k:v for k,v in out.items() if k!="image"},ensure_ascii=False)[:3000]
                ran_ok=True; out_s=redact_secrets(str(out)); ev("result",tool=tool,text=out_s[:1500],image=img); audit(ev="agent_tool",task=tid,tool=tool,args=args,ok=True); AL.log(TASKS[tid].get("user"),"device" if args.get("device") not in(None,"box") else ("shell" if tool=="shell" else ("browse" if tool in("browse","web_search") else "tool")),tool,args,out_s,True,tid)
                msgs.append({"role":"user","content":f"টুল ফলাফল ({tool}):\n{out_s[:3500]}\n(সারাংশ বাংলায়; OTP পূর্ণ নয়)"}); break
            except Exception as e:
                er=str(e)[:800]; audit(ev="agent_tool",task=tid,tool=tool,args=args,ok=False,err=er[:200]); AL.log(TASKS[tid].get("user"),"shell" if tool=="shell" else "tool",tool,args,friendly(er),False,tid)
                transient=any(w in er.lower() for w in("timeout","connect","temporar","503","502"))
                if transient and attempt==0: ev("retry",text=f"সাময়িক সমস্যা ({er[:120]}) — ২ সেকেন্ড পর আবার চেষ্টা"); await asyncio.sleep(2); continue
                fails+=1; ev("error",tool=tool,text=er)
                ev("repair",text="ভুলটা বিশ্লেষণ করে বিকল্প পথ খুঁজছি...")
                msgs.append({"role":"user","content":f"টুল ব্যর্থ ({tool}): {er}\nকারণ বিশ্লেষণ করো এবং অন্য বিকল্প পথে চেষ্টা করো।"}); break
        if fails>=4: ev("final",text="রয়েল, কয়েকবার চেষ্টা করেও কাজটা শেষ করতে পারিনি। বিস্তারিত উপরের ধাপগুলোতে আছে।"); return
    ev("final",text="ধাপের সীমা (১০) শেষ হয়েছে।")
# ---------------- voice & vision ----------------
VOICE="910fb75e-1d20-4840-ac63-ac6b26a71bdc"
async def tts(text):
    async with httpx.AsyncClient(timeout=60) as c:
        r=await c.post("https://api.cartesia.ai/tts/bytes",headers={"X-API-Key":K.get("CARTESIA_API_KEY",""),"Cartesia-Version":"2025-04-16"},
          json={"model_id":"sonic-3","transcript":text[:2500],"voice":{"mode":"id","id":VOICE},"language":"bn","output_format":{"container":"mp3","bit_rate":128000,"sample_rate":44100}})
    if r.status_code!=200: raise RuntimeError(f"Cartesia {r.status_code}: {r.text[:200]}")
    return r.content
STT_MAX_BYTES=10_000_000; STT_MAX_SEC=120
async def stt(data,ctype):
    if not data: raise RuntimeError("Empty audio / অডিও খালি")
    if len(data)>STT_MAX_BYTES: raise RuntimeError("Audio too large (max 10MB / 2 min) / অডিও খুব বড়")
    ct=(ctype or "audio/webm").split(";")[0]
    ext={"audio/webm":"webm","audio/ogg":"ogg","audio/mpeg":"mp3","audio/mp4":"m4a","audio/wav":"wav","audio/x-wav":"wav"}.get(ct,"webm")
    async with httpx.AsyncClient(timeout=60) as c:
        if K.get("GROQ_API_KEY"):
            try:
                r=await c.post("https://api.groq.com/openai/v1/audio/transcriptions",headers={"Authorization":"Bearer "+K["GROQ_API_KEY"]},
                    files={"file":("voice."+ext,data,ct)},data={"model":"whisper-large-v3-turbo","response_format":"verbose_json"})
                if r.status_code==200:
                    j=r.json()
                    if float(j.get("duration") or 0)>STT_MAX_SEC+5: raise RuntimeError("Audio longer than 2 minutes / ২ মিনিটের বেশি")
                    if (j.get("text") or "").strip(): return j["text"].strip(),"groq-whisper"
            except RuntimeError: raise
            except Exception: pass
        if K.get("DEEPGRAM_API_KEY"):
            for q in ("model=nova-3&language=bn","model=nova-2&detect_language=true"):
                try:
                    r=await c.post("https://api.deepgram.com/v1/listen?smart_format=true&"+q,headers={"Authorization":"Token "+K["DEEPGRAM_API_KEY"],"Content-Type":ct},content=data)
                    if r.status_code==200:
                        t=r.json()["results"]["channels"][0]["alternatives"][0]["transcript"]
                        if t: return t,"deepgram"
                except Exception: pass
        if K.get("ASSEMBLYAI_API_KEY"):
            try:
                h={"authorization":K["ASSEMBLYAI_API_KEY"]}
                up=(await c.post("https://api.assemblyai.com/v2/upload",headers=h,content=data)).json()["upload_url"]
                tid=(await c.post("https://api.assemblyai.com/v2/transcript",headers=h,json={"audio_url":up,"language_detection":True})).json()["id"]
                for _ in range(40):
                    await asyncio.sleep(1.5); j=(await c.get("https://api.assemblyai.com/v2/transcript/"+tid,headers=h)).json()
                    if j.get("status")=="completed" and j.get("text"): return j["text"],"assemblyai"
                    if j.get("status")=="error": break
            except Exception: pass
    raise RuntimeError("Could not hear anything / কিছু শোনা যায়নি")
async def vision(data,ctype,prompt="এই ছবিতে কী আছে বাংলায় বিস্তারিত বলো; কোনো লেখা থাকলে হুবহু তুলে দাও।"):
    url="data:"+(ctype or "image/png")+";base64,"+base64.b64encode(data).decode()
    msg=[{"role":"user","content":[{"type":"text","text":prompt},{"type":"image_url","image_url":{"url":url}}]}]
    async with httpx.AsyncClient(timeout=90) as c:
        for u,k,m in (("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",K.get("GEMINI_API_KEY"),"gemini-3.1-flash-lite"),
                      ("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",K.get("GEMINI_API_KEY"),"gemini-3.8-flash"),
                      ("https://openrouter.ai/api/v1/chat/completions",K.get("OPENROUTER_API_KEY"),"openrouter/free")):
            try:
                r=await c.post(u,headers={"Authorization":f"Bearer {k}"},json={"model":m,"messages":msg})
                if r.status_code==200: return m,r.json()["choices"][0]["message"]["content"]
            except Exception: pass
    raise RuntimeError("ভিশন মডেল সাড়া দেয়নি")
