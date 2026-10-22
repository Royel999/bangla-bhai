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
_EMB=None; _LOCK=threading.Lock(); EMB_OK=None
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
async def aembed(texts): return await asyncio.to_thread(embed,texts)
def _words(t): return set(w for w in re.findall(r"\w+",(t or "").lower()) if len(w)>2)
# ---------- CRUD (always scoped by user) ----------
def list_(u):
    with db() as c: return [dict(id=r["id"],text=r["text"],kind=r["kind"],created=r["created"],updated=r["updated"]) for r in c.execute("select id,text,kind,created,updated from memories where user=? order by updated desc",(u,))]
def count(u):
    with db() as c: return c.execute("select count(*) n from memories where user=?",(u,)).fetchone()["n"]
def add(u,text,kind="fact",source="manual"):
    text=re.sub(r"\s+"," ",text or "").strip()[:400]
    if not text: return None
    em=embed([text])[0]; now=time.time()
    with db() as c:
        dup=_nearest(c,u,text,em,1)
        if dup and dup[0][1]<0.12:      # near-duplicate: refresh instead of adding
            c.execute("update memories set text=?,emb=?,updated=? where id=? and user=?",(text,em,now,dup[0][0],u)); return dup[0][0]
        cur=c.execute("insert into memories(user,text,kind,source,emb,created,updated) values(?,?,?,?,?,?,?)",(u,text,kind,source,em,now,now))
        n=c.execute("select count(*) n from memories where user=?",(u,)).fetchone()["n"]
        import plans as _PL; cap=_PL.limit(u,"memory") or MAX_PER_USER*100
        if n>cap: c.execute("delete from memories where id in (select id from memories where user=? order by updated asc limit ?)",(u,n-cap))
        return cur.lastrowid
def update(u,mid,text):
    text=re.sub(r"\s+"," ",text or "").strip()[:400]
    if not text: return False
    em=embed([text])[0]
    with db() as c: return c.execute("update memories set text=?,emb=?,updated=? where id=? and user=?",(text,em,time.time(),mid,u)).rowcount>0
def delete(u,mid):
    with db() as c: return c.execute("delete from memories where id=? and user=?",(mid,u)).rowcount>0
def clear(u):
    with db() as c: return c.execute("delete from memories where user=?",(u,)).rowcount
def _nearest(c,u,text,em,k):
    if em is not None and HAVE_VEC:
        try:
            return [(r["id"],r["d"],r["text"]) for r in c.execute("select id,text,vec_distance_cosine(emb,?) d from memories where user=? and emb is not null order by d limit ?",(em,u,k))]
        except Exception: pass
    q=_words(text); rows=c.execute("select id,text from memories where user=?",(u,)).fetchall()
    sc=sorted(((r["id"],1-len(q&_words(r["text"]))/max(1,len(q|_words(r["text"]))),r["text"]) for r in rows),key=lambda x:x[1])
    return sc[:k]
def recall(u,query,k=6,maxd=0.75):
    em=embed([query])[0] if query else None
    with db() as c:
        hits=[h for h in _nearest(c,u,query,em,k) if h[1]<=maxd]
        if len(hits)<3:   # always include a few most recent profile facts
            seen={h[0] for h in hits}
            for r in c.execute("select id,text from memories where user=? order by updated desc limit 4",(u,)):
                if r["id"] not in seen and len(hits)<k: hits.append((r["id"],0.99,r["text"]))
    return [h[2] for h in hits]
async def arecall(u,query): return await asyncio.to_thread(recall,u,query)
EXTRACT=("You extract long-term memory about the USER from their latest message. Return JSON {\"facts\":[...]} with 0-3 short, "
 "durable third-person facts or preferences (name, job, location, family, goals, likes, how they want answers, projects). "
 "Ignore questions, one-off tasks, small talk, anything about the assistant, secrets, passwords, OTP codes, card or ID numbers. "
 "Write each fact in the same language the user used. If nothing durable, return {\"facts\":[]}.")
SECRET=re.compile(r"(password|passwd|otp|pin\b|api[_ -]?key|token|পাসওয়ার্ড|\b\d{6}\b|\b\d{12,}\b)",re.I)
async def extract(u,user_msg,complete):
    if not user_msg or len(user_msg)<8: return []
    try:
        _,t,_=await complete([{"role":"system","content":EXTRACT},{"role":"user","content":user_msg[:2000]}],json_mode=True,timeout=30,tries=1)
        j=json.loads(t[t.find("{"):t.rfind("}")+1]); facts=[f for f in j.get("facts",[]) if isinstance(f,str) and 4<len(f)<300 and not SECRET.search(f)][:3]
    except Exception: return []
    ids=[]
    for f in facts: ids.append(await asyncio.to_thread(add,u,f,"fact","chat"))
    return ids
