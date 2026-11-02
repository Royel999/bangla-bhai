"""Per-user long-term memory. Local only: SQLite + sqlite-vec cosine + local fastembed embeddings (keyword fallback)."""
import os, json, time, re, sqlite3, struct, threading, asyncio
BASE=os.path.expanduser('~/bangla_bhai'); DB=BASE+'/data.db'
MAX_PER_USER=300; DIM=384; EMB_MODEL="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
try:
    import sqlite_vec; HAVE_VEC=True
except Exception: HAVE_VEC=False
def db():
    c=sqlite3.connect(DB,timeout=15); c.row_factory=sqlite3.Row
    if HAVE_VEC:
        try: c.enable_load_extension(True); sqlite_vec.load(c); c.enable_load_extension(False)
        except Exception: pass
    return c
with db() as c:
    c.executescript("""create table if not exists memories(id integer primary key autoincrement,user text not null,text text not null,kind text default 'fact',
 source text,emb blob,created real,updated real);
create index if not exists ix_mem_user on memories(user);""")
    try: c.execute("alter table memories add column cemb blob")
    except Exception: pass
_EMB=None; _LOCK=threading.Lock(); EMB_OK=False if os.environ.get('BB_LOW_MEM')=='1' else None  # Render free 512MB: keyword memory search only
def _embedder():
    global _EMB,EMB_OK
    with _LOCK:
        if _EMB is None and EMB_OK is not False:
            try:
                from fastembed import TextEmbedding
                _EMB=TextEmbedding(EMB_MODEL,cache_dir=BASE+"/.emb_cache",threads=2); EMB_OK=True
            except Exception: EMB_OK=False
    return _EMB
def embed(texts):
    e=_embedder()
    if not e: return [None]*len(texts)
    try: return [struct.pack(f"{DIM}f",*[float(x) for x in v]) for v in e.embed(texts)]
    except Exception: return [None]*len(texts)
# ---- hosted embeddings (Gemini, free tier): same vectors on Render and box, no RAM ----
CDIM=768; _CK=None
def _gkey():
    global _CK
    if _CK is None:
        try: import router as _R; _CK=_R.K.get("GEMINI_API_KEY") or ""
        except Exception: _CK=""
    return _CK
def cembed(texts):
    k=_gkey()
    if not k or not texts: return [None]*len(texts)
    try:
        import httpx
        r=httpx.post("https://generativelanguage.googleapis.com/v1beta/openai/embeddings",headers={"Authorization":"Bearer "+k},
                     json={"model":"gemini-embedding-001","input":[t[:2000] for t in texts],"dimensions":CDIM},timeout=12)
        if r.status_code!=200: return [None]*len(texts)
        return [struct.pack(f"{CDIM}f",*d["embedding"]) for d in sorted(r.json()["data"],key=lambda d:d.get("index",0))]
    except Exception: return [None]*len(texts)
def _backfill(c,u,limit=64):
    rows=c.execute("select id,text from memories where user=? and cemb is null limit ?",(u,limit)).fetchall()
    if not rows: return
    vs=cembed([r["text"] for r in rows])
    for r,v in zip(rows,vs):
        if v is not None: c.execute("update memories set cemb=? where id=?",(v,r["id"]))
async def aembed(texts): return await asyncio.to_thread(embed,texts)
def _words(t): return set(w for w in re.findall(r"\w+",(t or "").lower()) if len(w)>2)
# ---------- CRUD (always scoped by user) ----------
KINDS=("fact","preference","project","note")
def list_(u):
    with db() as c: return [dict(id=r["id"],text=r["text"],kind=r["kind"],source=r["source"],created=r["created"],updated=r["updated"]) for r in c.execute("select id,text,kind,source,created,updated from memories where user=? order by updated desc",(u,))]
def count(u):
    with db() as c: return c.execute("select count(*) n from memories where user=?",(u,)).fetchone()["n"]
def add(u,text,kind="fact",source="manual"):
    text=re.sub(r"\s+"," ",text or "").strip()[:400]
    if not text: return None
    ce=cembed([text])[0]; em=None if ce is not None else embed([text])[0]; now=time.time()
    with db() as c:
        dup=_nearest(c,u,text,em,1,ce)
        if dup and dup[0][1]<0.12:      # near-duplicate: refresh instead of adding
            c.execute("update memories set text=?,emb=?,cemb=?,updated=? where id=? and user=?",(text,em,ce,now,dup[0][0],u)); return dup[0][0]
        cur=c.execute("insert into memories(user,text,kind,source,emb,cemb,created,updated) values(?,?,?,?,?,?,?,?)",(u,text,kind,source,em,ce,now,now))
        n=c.execute("select count(*) n from memories where user=?",(u,)).fetchone()["n"]
        import plans as _PL; cap=_PL.limit(u,"memory") or MAX_PER_USER*100
        if n>cap: c.execute("delete from memories where id in (select id from memories where user=? order by updated asc limit ?)",(u,n-cap))
        return cur.lastrowid
def set_kind(u,mid,kind):
    if kind not in KINDS: return False
    with db() as c: return c.execute("update memories set kind=?,updated=? where id=? and user=?",(kind,time.time(),mid,u)).rowcount>0
def update(u,mid,text):
    text=re.sub(r"\s+"," ",text or "").strip()[:400]
    if not text: return False
    ce=cembed([text])[0]; em=None if ce is not None else embed([text])[0]
    with db() as c: return c.execute("update memories set text=?,emb=?,cemb=?,updated=? where id=? and user=?",(text,em,ce,time.time(),mid,u)).rowcount>0
def delete(u,mid):
    with db() as c: return c.execute("delete from memories where id=? and user=?",(mid,u)).rowcount>0
def clear(u):
    with db() as c: return c.execute("delete from memories where user=?",(u,)).rowcount
def _nearest(c,u,text,em,k,ce=None):
    if ce is not None and HAVE_VEC:
        try:
            _backfill(c,u)
            r=[(r["id"],r["d"],r["text"]) for r in c.execute("select id,text,vec_distance_cosine(cemb,?) d from memories where user=? and cemb is not null order by d limit ?",(ce,u,k))]
            if r: return r
        except Exception: pass
    if em is not None and HAVE_VEC:
        try:
            return [(r["id"],r["d"],r["text"]) for r in c.execute("select id,text,vec_distance_cosine(emb,?) d from memories where user=? and emb is not null order by d limit ?",(em,u,k))]
        except Exception: pass
    q=_words(text); rows=c.execute("select id,text from memories where user=?",(u,)).fetchall()
    sc=sorted(((r["id"],1-len(q&_words(r["text"]))/max(1,len(q|_words(r["text"]))),r["text"]) for r in rows),key=lambda x:x[1])
    return sc[:k]
def recall(u,query,k=6,maxd=0.75,detail=False):
    ce=cembed([query])[0] if query else None
    em=embed([query])[0] if (query and ce is None) else None
    with db() as c:
        hits=[h for h in _nearest(c,u,query,em,k,ce) if h[1]<=maxd]; nrel=len(hits)
        if len(hits)<3:   # always include a few most recent profile facts
            seen={h[0] for h in hits}
            for r in c.execute("select id,text from memories where user=? order by updated desc limit 4",(u,)):
                if r["id"] not in seen and len(hits)<k: hits.append((r["id"],0.99,r["text"]))
    if detail: return {"texts":[h[2] for h in hits],"relevant":[h[2] for h in hits[:nrel]]}
    return [h[2] for h in hits]
async def arecall(u,query,detail=False): return await asyncio.to_thread(recall,u,query,6,0.75,detail)
EXTRACT=("You extract long-term memory about the USER from their latest message. Return JSON {\"facts\":[{\"text\":...,\"kind\":...}]} with 0-3 short, "
 "durable third-person facts. kind is one of: fact (name, job, location, family), preference (likes, how they want answers), project (ongoing goals or work). "
 "Ignore questions, one-off tasks, small talk, anything about the assistant, secrets, passwords, OTP codes, card or ID numbers. "
 "Write each fact in the same language the user used. If nothing durable, return {\"facts\":[]}.")
SECRET=re.compile(r"(password|passwd|otp|pin\b|api[_ -]?key|token|পাসওয়ার্ড|\b\d{6}\b|\b\d{12,}\b)",re.I)
def _norm(f):
    if isinstance(f,str): return f,"fact"
    if isinstance(f,dict) and isinstance(f.get("text"),str): return f["text"],(f.get("kind") if f.get("kind") in KINDS else "fact")
    return "",""
async def extract(u,user_msg,complete,source="chat"):
    """Learn durable, user-scoped facts from the user's OWN words (chat message or agent goal). Never from tool/web output."""
    if not user_msg or len(user_msg)<8: return []
    try:
        _,t,_=await complete([{"role":"system","content":EXTRACT},{"role":"user","content":user_msg[:2000]}],json_mode=True,timeout=30,tries=1)
        j=json.loads(t[t.find("{"):t.rfind("}")+1]); facts=[_norm(f) for f in j.get("facts",[])]
        facts=[(x,k) for x,k in facts if 4<len(x)<300 and not SECRET.search(x)][:3]
    except Exception: return []
    ids=[]
    for f,k in facts: ids.append(await asyncio.to_thread(add,u,f,k,source))
    return ids
# ================= Hermes-style bounded memory + FTS5 + background review (P0) =================
# USER = kind 'preference' (how the user wants things); MEMORY = fact/project/note (what was learned).
# Hard bounds (items AND total chars) so the profile loaded every session stays small.
BOUNDS={"user":{"kinds":("preference",),"items":int(os.environ.get("BB_MEM_USER_ITEMS","40")),"chars":int(os.environ.get("BB_MEM_USER_CHARS","2400"))},
        "memory":{"kinds":("fact","project","note"),"items":int(os.environ.get("BB_MEM_ITEMS","150")),"chars":int(os.environ.get("BB_MEM_CHARS","12000"))}}
def _bucket(kind): return "user" if kind=="preference" else "memory"
def enforce(u):
    """Trim oldest (by updated) per bucket until both item and char limits hold. Returns #deleted."""
    n=0
    with db() as c:
        for b in BOUNDS.values():
            q=",".join("?"*len(b["kinds"]))
            rows=c.execute(f"select id,length(text) l from memories where user=? and kind in ({q}) order by updated desc",(u,*b["kinds"])).fetchall()
            tot=0; drop=[]
            for i,r in enumerate(rows):
                tot+=r["l"]
                if i>=b["items"] or tot>b["chars"]: drop.append(r["id"])
            if drop: c.execute(f"delete from memories where id in ({','.join('?'*len(drop))})",drop); n+=len(drop)
    return n
def usage(u):
    out={}
    with db() as c:
        for name,b in BOUNDS.items():
            q=",".join("?"*len(b["kinds"]))
            r=c.execute(f"select count(*) n,coalesce(sum(length(text)),0) ch from memories where user=? and kind in ({q})",(u,*b["kinds"])).fetchone()
            out[name]={"items":r["n"],"chars":r["ch"],"max_items":b["items"],"max_chars":b["chars"]}
    return out
_add0=add
def add(u,text,kind="fact",source="manual"):
    i=_add0(u,text,kind,source)
    if i: enforce(u)
    return i
# ---- FTS5 full-text search (trigger-synced). Fallback chain: FTS5 -> vector -> keyword ----
HAVE_FTS=False
try:
    with db() as c:
        c.executescript("""create virtual table if not exists memories_fts using fts5(text,content='memories',content_rowid='id',tokenize='unicode61');
create trigger if not exists mem_ai after insert on memories begin insert into memories_fts(rowid,text) values(new.id,new.text); end;
create trigger if not exists mem_ad after delete on memories begin insert into memories_fts(memories_fts,rowid,text) values('delete',old.id,old.text); end;
create trigger if not exists mem_au after update of text on memories begin insert into memories_fts(memories_fts,rowid,text) values('delete',old.id,old.text); insert into memories_fts(rowid,text) values(new.id,new.text); end;""")
        if c.execute("select count(*) from memories_fts").fetchone()[0]==0 and c.execute("select count(*) from memories").fetchone()[0]:
            c.execute("insert into memories_fts(memories_fts) values('rebuild')")
    HAVE_FTS=True
except Exception: HAVE_FTS=False
def search(u,q,k=10):
    """Full-text search over the user's own memories. Returns [{id,text,kind,how}]."""
    toks=[t for t in re.findall(r"\w+",q or "") if len(t)>1][:8]
    if not toks: return []
    if HAVE_FTS:
        try:
            m=" OR ".join('"'+t.replace('"','')+'"*' for t in toks)
            with db() as c:
                r=[dict(id=x["id"],text=x["text"],kind=x["kind"],how="fts5") for x in c.execute(
                    "select m.id,m.text,m.kind from memories_fts f join memories m on m.id=f.rowid where memories_fts match ? and m.user=? order by bm25(memories_fts) limit ?",(m,u,k))]
            if r: return r
        except Exception: pass
    with db() as c: hits=_nearest(c,u,q,None,k,None)
    return [dict(id=i,text=t,kind="",how="keyword") for i,d,t in hits if d<0.95]
# ---- background review: after a chat/agent task, propose memories into a PENDING queue ----
with db() as c:
    c.execute("create table if not exists mem_props(id integer primary key autoincrement,user text,text text,kind text,source text,why text,status text default 'pending',created real)")
REVIEW=("You review a finished conversation turn between a USER and an assistant. Propose 0-3 durable things worth remembering about the USER "
 "(preference = how they like answers/work; project = ongoing goal; fact = stable personal fact). Only from the USER's own words. "
 "Never secrets, passwords, OTPs, card/ID numbers, or web/tool content. Return JSON {\"proposals\":[{\"text\":...,\"kind\":...,\"why\":...}]}.")
def _known(u,text):
    with db() as c: h=_nearest(c,u,text,None,1,None)
    return bool(h) and h[0][1]<0.35
async def review(u,user_msg,answer,complete,source="chat"):
    """Stage proposals (status=pending); the user approves in Personal Intelligence -> pending. Multi-way: LLM review,
    on failure fall back to the regex heuristic below so the queue still gets candidates."""
    if not user_msg or len(user_msg)<12: return []
    props=[]
    try:
        _,t,_=await complete([{"role":"system","content":REVIEW},{"role":"user","content":"USER: "+user_msg[:1500]+"\nASSISTANT: "+(answer or "")[:800]}],json_mode=True,timeout=30,tries=1)
        j=json.loads(t[t.find("{"):t.rfind("}")+1])
        for p in j.get("proposals",[])[:3]:
            x,k=_norm(p); props.append((x,k,str(p.get("why",""))[:160] if isinstance(p,dict) else ""))
    except Exception:
        m=re.search(r"(?:i prefer|i like|always|please keep|আমি চাই|সবসময়|আমার পছন্দ)\s*(.{6,160})",user_msg,re.I)
        if m: props.append((m.group(0).strip(),"preference","heuristic"))
    out=[]
    with db() as c:
        c.execute("delete from mem_props where user=? and status='pending' and created<?",(u,time.time()-14*86400))
        if c.execute("select count(*) from mem_props where user=? and status='pending'",(u,)).fetchone()[0]>=30: return []
    for x,k,why in props:
        x=re.sub(r"\s+"," ",x or "").strip()
        if not (4<len(x)<300) or SECRET.search(x) or _known(u,x): continue
        with db() as c:
            if c.execute("select 1 from mem_props where user=? and text=? and status='pending'",(u,x)).fetchone(): continue
            out.append(c.execute("insert into mem_props(user,text,kind,source,why,created) values(?,?,?,?,?,?)",(u,x,k or "fact",source,why,time.time())).lastrowid)
    return out
def pending(u):
    with db() as c: return [dict(r) for r in c.execute("select id,text,kind,source,why,created from mem_props where user=? and status='pending' order by created desc limit 30",(u,))]
def decide(u,pid,ok,text=None):
    with db() as c:
        r=c.execute("select * from mem_props where id=? and user=? and status='pending'",(pid,u)).fetchone()
        if not r: return None
        c.execute("update mem_props set status=? where id=?",("approved" if ok else "discarded",pid))
    return add(u,text or r["text"],r["kind"],"review") if ok else 0
