"""Plans, quotas, manual bKash/Nagad payments, app settings, usage counters."""
import os, sqlite3, time, json, re, uuid, datetime as DT
BASE=os.path.expanduser('~/bangla_bhai'); DBF=BASE+'/data.db'
def _owner():
    try:
        for l in open(os.path.expanduser('~/.secrets/bangla_bhai.env')):
            if l.startswith("BB_USER="): return l.split("=",1)[1].strip().strip('"')
    except Exception: pass
    return None
OWNER=_owner()
PLANS={
 "free":{"name":"Free","price":0,"chat":30,"voice":20,"images":20,"videos":3,"memory":100,"jobs":3,"skills":10,"file_mb":20,"telegram":True},
 "pro":{"name":"Pro","price":299,"chat":500,"voice":200,"images":100,"videos":20,"memory":5000,"jobs":30,"skills":200,"file_mb":200,"telegram":True},
 "business":{"name":"Business","price":1499,"chat":3000,"voice":1000,"images":500,"videos":100,"memory":20000,"jobs":100,"skills":1000,"file_mb":500,"telegram":True},
}
KINDS=("chat","voice","images","videos")
def db():
    c=sqlite3.connect(DBF,timeout=15); c.row_factory=sqlite3.Row; return c
with db() as c:
    c.executescript("""
    create table if not exists subs(user text primary key,plan text,expires real,updated real);
    create table if not exists payments(id text primary key,user text,plan text,method text,trxid text unique,sender text,amount real,status text default 'pending',note text,created real,decided real,months int default 1);
    create table if not exists app_settings(k text primary key,v text);
    create table if not exists usage(user text,day text,kind text,n int default 0,primary key(user,day,kind));
    create table if not exists admin_audit(id integer primary key autoincrement,t real,actor text,action text,detail text,ip text);
    create table if not exists team_members(owner text,email text,user text,status text default 'invited',created real,joined real,primary key(owner,email));""")
def today(): return DT.datetime.now(DT.timezone(DT.timedelta(hours=6))).strftime("%Y-%m-%d")
def is_owner(u): return bool(u) and str(u)==str(OWNER)
# ---- settings ----
DEFAULT_SET={"bkash_number":"","nagad_number":"","pay_note":"","price_pro":"299","price_business":"1499","signups_open":"1"}
def settings():
    with db() as c: d={r["k"]:r["v"] for r in c.execute("select k,v from app_settings")}
    return {**DEFAULT_SET,**d}
def set_setting(k,v):
    if k not in DEFAULT_SET: raise ValueError("unknown setting")
    with db() as c: c.execute("insert or replace into app_settings values(?,?)",(k,str(v)[:300]))
def price(plan):
    s=settings()
    try: return int(s.get("price_"+plan) or PLANS[plan]["price"])
    except Exception: return PLANS.get(plan,{}).get("price",0)
# ---- plan ----
TEAM_MAX=5
def _email_of(u):
    with db() as c: r=c.execute("select email from users where id=?",(u,)).fetchone()
    return (r["email"] or "").lower() if r else ""
def _own_plan(u):
    if is_owner(u): return "business"
    with db() as c: r=c.execute("select plan,expires from subs where user=?",(u,)).fetchone()
    if r and r["plan"] in PLANS and (not r["expires"] or r["expires"]>time.time()): return r["plan"]
    return "free"
def team_owner_of(u):
    """Business owner whose seat this user occupies (joins lazily on next login), else None."""
    if not u or is_owner(u): return None
    e=_email_of(u)
    with db() as c:
        r=c.execute("select owner,status from team_members where user=? or (email=? and email!='') order by status='active' desc limit 1",(u,e)).fetchone()
        if not r or r["owner"]==u: return None
        if r["status"]!="active": c.execute("update team_members set user=?,status='active',joined=? where owner=? and email=?",(u,time.time(),r["owner"],e))
    return r["owner"] if _own_plan(r["owner"])=="business" else None
def quota_user(u): return team_owner_of(u) or u
def team_list(owner):
    with db() as c: return [dict(r) for r in c.execute("select email,status,created,joined from team_members where owner=? order by created",(owner,))]
def team_invite(owner,email):
    email=(email or "").strip().lower()
    if not re.fullmatch(r"[^@\s]{1,64}@[^@\s]{1,190}\.[a-z]{2,}",email): raise ValueError("Enter a valid email")
    if _own_plan(owner)!="business": raise ValueError("Team seats need the Business plan")
    if team_owner_of(owner): raise ValueError("Team members cannot invite others")
    if email==_email_of(owner): raise ValueError("You cannot invite yourself")
    with db() as c:
        tgt=c.execute("select id from users where email=?",(email,)).fetchone()
        if tgt and is_owner(tgt["id"]): raise ValueError("This account cannot be invited")
        if c.execute("select 1 from team_members where email=?",(email,)).fetchone(): raise ValueError("This email is already in a team")
        if c.execute("select count(*) n from team_members where owner=?",(owner,)).fetchone()["n"]>=TEAM_MAX: raise ValueError(f"Team is full (max {TEAM_MAX} members)")
        c.execute("insert into team_members(owner,email,status,created) values(?,?,'invited',?)",(owner,email,time.time()))
def team_remove(owner,email):
    with db() as c: n=c.execute("delete from team_members where owner=? and email=?",(owner,(email or "").strip().lower())).rowcount
    if not n: raise ValueError("not found")
def team_leave(u):
    e=_email_of(u)
    with db() as c: c.execute("delete from team_members where user=? or (email=? and email!='')",(u,e))
def plan_of(u):
    if is_owner(u): return "business"
    if team_owner_of(u): return "business"
    with db() as c: r=c.execute("select plan,expires from subs where user=?",(u,)).fetchone()
    if r and r["plan"] in PLANS and (not r["expires"] or r["expires"]>time.time()): return r["plan"]
    return "free"
def sub_info(u):
    with db() as c: r=c.execute("select plan,expires from subs where user=?",(u,)).fetchone()
    p=plan_of(u); to=team_owner_of(u)
    return {"plan":p,"name":PLANS[p]["name"],"expires":(r["expires"] if r and p!="free" and not to else None),"owner":is_owner(u),"team_member":bool(to)}
def limit(u,kind):
    u=quota_user(u)
    if is_owner(u): return None
    return PLANS[plan_of(u)].get(kind)
def used(u,kind,day=None):
    u=quota_user(u)
    with db() as c: r=c.execute("select n from usage where user=? and day=? and kind=?",(u,day or today(),kind)).fetchone()
    return r["n"] if r else 0
def bump(u,kind,n=1):
    u=quota_user(u)
    with db() as c: c.execute("insert into usage(user,day,kind,n) values(?,?,?,?) on conflict(user,day,kind) do update set n=n+?",(u,today(),kind,n,n))
def take(u,kind):
    """Daily quota check-and-consume. Returns (ok, limit)."""
    lim=limit(u,kind)
    if lim is not None and used(u,kind)>=lim: return False,lim
    bump(u,kind); return True,lim
def quota_msg(kind,lim,lang="en"):
    en=f"Daily {kind} limit reached on your plan ({lim}). Upgrade at /plans or try tomorrow."
    bn=f"আপনার প্ল্যানের আজকের {kind} সীমা শেষ ({lim})। /plans থেকে আপগ্রেড করুন বা কাল চেষ্টা করুন।"
    return bn if lang=="bn" else en
def usage_summary(u):
    return {k:{"used":used(u,k),"limit":limit(u,k)} for k in KINDS}
# ---- payments ----
TRX=re.compile(r"^[A-Za-z0-9]{8,12}$")
def submit_payment(u,plan,method,trxid,sender,amount):
    if plan not in ("pro","business"): raise ValueError("Choose Pro or Business")
    if method not in ("bkash","nagad"): raise ValueError("Choose bKash or Nagad")
    if not settings().get(method+"_number"): raise ValueError("Payments by this method are not open yet")
    trxid=(trxid or "").strip().upper()
    if not TRX.match(trxid): raise ValueError("TrxID looks wrong (8-12 letters/digits)")
    sender=re.sub(r"[^0-9+]","",sender or "")[:15]
    if not re.fullmatch(r"(\+?88)?01[3-9]\d{8}",sender): raise ValueError("Enter the sender mobile number (01XXXXXXXXX)")
    try: amount=float(amount)
    except Exception: raise ValueError("Enter the amount")
    with db() as c:
        if c.execute("select count(*) n from payments where user=? and status='pending'",(u,)).fetchone()["n"]>=3: raise ValueError("You already have pending payments. Please wait for review.")
        if c.execute("select 1 from payments where trxid=?",(trxid,)).fetchone(): raise ValueError("This TrxID was already submitted")
        pid=uuid.uuid4().hex[:12]
        c.execute("insert into payments(id,user,plan,method,trxid,sender,amount,status,created) values(?,?,?,?,?,?,?,'pending',?)",(pid,u,plan,method,trxid,sender,amount,time.time()))
    return pid
def decide_payment(pid,approve,note="",months=1):
    with db() as c:
        p=c.execute("select * from payments where id=?",(pid,)).fetchone()
        if not p: raise ValueError("not found")
        if p["status"]!="pending": raise ValueError("already decided")
        c.execute("update payments set status=?,note=?,decided=?,months=? where id=?",("approved" if approve else "rejected",(note or "")[:300],time.time(),months,pid))
        exp=None
        if approve:
            r=c.execute("select plan,expires from subs where user=?",(p["user"],)).fetchone()
            start=r["expires"] if (r and r["plan"]==p["plan"] and (r["expires"] or 0)>time.time()) else time.time()
            exp=start+30*86400*max(1,int(months))
            c.execute("insert or replace into subs values(?,?,?,?)",(p["user"],p["plan"],exp,time.time()))
    return dict(p),exp
def set_plan(u,plan,days):
    if plan not in PLANS: raise ValueError("bad plan")
    with db() as c:
        if plan=="free": c.execute("delete from subs where user=?",(u,))
        else: c.execute("insert or replace into subs values(?,?,?,?)",(u,plan,time.time()+86400*int(days),time.time()))
def my_payments(u):
    with db() as c: return [dict(r) for r in c.execute("select id,plan,method,trxid,amount,status,note,created,decided from payments where user=? order by created desc limit 20",(u,))]
def admin_log(actor,action,detail="",ip=""):
    with db() as c: c.execute("insert into admin_audit(t,actor,action,detail,ip) values(?,?,?,?,?)",(time.time(),actor,action,json.dumps(detail,ensure_ascii=False)[:1000] if not isinstance(detail,str) else detail[:1000],ip))
