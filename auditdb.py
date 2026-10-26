"""Audit events: append to audit.jsonl (as before) AND to the audit_events table in data.db,
so the trail is included in the KV backup and survives Render restarts. Never raises."""
import os, json, time, sqlite3
BASE=os.path.expanduser('~/bangla_bhai'); DB=BASE+'/data.db'; JSONL=BASE+'/audit.jsonl'
KEEP_DAYS=int(os.environ.get('BB_AUDIT_KEEP_DAYS','180'))
_ready=False; _n=0
def _conn():
    global _ready
    c=sqlite3.connect(DB,timeout=5)
    if not _ready:
        c.execute("create table if not exists audit_events(id integer primary key autoincrement,t real,ev text,data text)")
        c.execute("create index if not exists audit_events_t on audit_events(t)")
        c.execute("create index if not exists audit_events_ev on audit_events(ev)")
        c.commit(); _ready=True
    return c
def write(**k):
    global _n
    rec={"t":time.time(),**k}
    line=json.dumps(rec,ensure_ascii=False,default=str)
    try:
        with open(JSONL,'a') as f: f.write(line+"\n")
    except Exception: pass
    try:
        rest={a:b for a,b in k.items() if a!='ev'}
        c=_conn()
        try:
            c.execute("insert into audit_events(t,ev,data) values(?,?,?)",
                      (rec["t"],str(k.get("ev",""))[:60],json.dumps(rest,ensure_ascii=False,default=str)[:2000]))
            _n+=1
            if _n%500==1: c.execute("delete from audit_events where t<?",(time.time()-KEEP_DAYS*86400,))
            c.commit()
        finally: c.close()
    except Exception: pass
def recent(limit=200,ev=None):
    c=_conn(); c.row_factory=sqlite3.Row
    try:
        q="select id,t,ev,data from audit_events"+(" where ev=?" if ev else "")+" order by id desc limit ?"
        return [dict(r) for r in c.execute(q,((ev,limit) if ev else (limit,)))]
    finally: c.close()
