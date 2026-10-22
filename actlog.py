"""Per-user action log, persistent approvals and persistent agent tasks (SQLite)."""
import os, json, time, sqlite3, re
BASE=os.path.expanduser('~/bangla_bhai'); DB=BASE+'/data.db'
def db():
    c=sqlite3.connect(DB,timeout=15); c.row_factory=sqlite3.Row; return c
with db() as c:
    c.executescript("""create table if not exists actions(id integer primary key autoincrement,user text not null,ts real,kind text,tool text,
 input text,result text,ok int,task text,status text);
create index if not exists ix_act_user on actions(user,ts);
create table if not exists approvals(id text primary key,user text not null,task text,tool text,args text,why text,risk text,status text,created real,decided real);
create table if not exists tasks(id text primary key,user text,goal text,sysx text,status text,events text,resumes int default 0,created real,updated real);""")
SECRETISH=re.compile(r"((?:key|token|secret|password|passwd|authorization)[\"'=: ]+)\S+",re.I)
def _sum(x,n=300):
    s=x if isinstance(x,str) else json.dumps(x,ensure_ascii=False)
    return SECRETISH.sub(r"\1***",s)[:n]
def log(user,kind,tool,inp,result,ok=True,task=None,status="done"):
    if not user: return
    with db() as c: c.execute("insert into actions(user,ts,kind,tool,input,result,ok,task,status) values(?,?,?,?,?,?,?,?,?)",
        (str(user),time.time(),kind,tool,_sum(inp),_sum(result,500),1 if ok else 0,task,status))
def list_(user,limit=200,kind=None):
    q="select * from actions where user=?"+(" and kind=?" if kind else "")+" order by id desc limit ?"
    with db() as c: return [dict(r) for r in c.execute(q,(str(user),kind,limit) if kind else (str(user),limit))]
def clear(user):
    with db() as c: return c.execute("delete from actions where user=?",(str(user),)).rowcount
# ---------- risk ----------
DESTRUCT=re.compile(r"\b(rm|rmdir|del|format|mkfs|dd|shutdown|reboot|poweroff|kill|pkill|killall|chmod|chown|mv|truncate|drop|delete|uninstall|pm\s+uninstall|wipe|reset)\b|>\s*/|sudo",re.I)
def risk(tool,args):
    a=json.dumps(args or {},ensure_ascii=False)
    if tool=="shell": return "high" if DESTRUCT.search(a) else "medium"
    if tool in("sms_send","call_make","settings_ctl","app_stop","am_start","type_text","click","swipe","keyevent","call_control"): return "high"
    if tool in("camera_photo","mic_record","sms_list","contacts","call_log","location","clipboard","notifications","screenshot","ui_dump"): return "medium"
    return "low"
# ---------- approvals ----------
def appr_open(aid,user,task,tool,args,why,rk):
    with db() as c: c.execute("insert or replace into approvals values(?,?,?,?,?,?,?,?,?,?)",(aid,str(user),task,tool,_sum(args,800),(why or "")[:300],rk,"pending",time.time(),None))
def appr_close(aid,status):
    with db() as c: c.execute("update approvals set status=?,decided=? where id=? and status='pending'",(status,time.time(),aid))
def appr_list(user,status=None):
    with db() as c:
        q="select * from approvals where user=?"+(" and status=?" if status else "")+" order by created desc limit 100"
        return [dict(r) for r in c.execute(q,(str(user),status) if status else (str(user),))]
def appr_get(aid,user):
    with db() as c: r=c.execute("select * from approvals where id=? and user=?",(aid,str(user))).fetchone()
    return dict(r) if r else None
def appr_expire_all():
    with db() as c: c.execute("update approvals set status='expired',decided=? where status='pending'",(time.time(),))
# ---------- tasks ----------
def task_save(tid,user,goal,sysx,status,events,resumes=None):
    with db() as c:
        if c.execute("select 1 from tasks where id=?",(tid,)).fetchone():
            c.execute("update tasks set status=?,events=?,updated=?"+(",resumes=?" if resumes is not None else "")+" where id=?",
                      (status,json.dumps(events,ensure_ascii=False),time.time())+((resumes,) if resumes is not None else ())+(tid,))
        else: c.execute("insert into tasks values(?,?,?,?,?,?,?,?,?)",(tid,str(user),goal,sysx,status,json.dumps(events,ensure_ascii=False),resumes or 0,time.time(),time.time()))
def task_get(tid):
    with db() as c: r=c.execute("select * from tasks where id=?",(tid,)).fetchone()
    if not r: return None
    d=dict(r); d["events"]=json.loads(d["events"] or "[]"); return d
def tasks_running():
    with db() as c: return [dict(r)|{"events":json.loads(r["events"] or "[]")} for r in c.execute("select * from tasks where status='running'")]
def tasks_list(user,limit=30):
    with db() as c: return [dict(id=r["id"],goal=r["goal"],status=r["status"],created=r["created"],updated=r["updated"],resumes=r["resumes"]) for r in c.execute("select * from tasks where user=? order by created desc limit ?",(str(user),limit))]
