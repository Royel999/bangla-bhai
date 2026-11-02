"""Royal Link device hub v1 (The Royal Bengal Tiger).
Pure-asyncio helpers used by /bb/link/ws and /bb/link/poll. Backward compatible:
old clients that only send {"cid","result"} keep working.

Protocol additions (all optional for clients):
  server->client {"type":"hello","hb":20,"timeout":60,"resume":true}
  server->client {"type":"ping","t":<ts>}      client->server {"type":"pong","t":<ts>}
  client->server {"type":"ping"}               server->client {"type":"pong"}
  client->server {"type":"step","cid":..,"phase":"thinking|running|screenshot|done|error","text":..}
  server->client job {"cid","action","args","attempt"}; client may send {"type":"ack","cid"}
Pending commands: a job that was sent but not answered when the socket drops is
re-queued (up to MAX_ATTEMPTS) and delivered again on reconnect with the same token,
as long as it is younger than PENDING_TTL. State is in-process memory (survives
disconnects, not a server restart -- the waiting future would be gone anyway).
"""
import asyncio, time, collections
HB_INTERVAL=20; HB_TIMEOUT=60; PENDING_TTL=120; MAX_ATTEMPTS=3; STEP_KEEP=200
PHASES=("thinking","running","screenshot","done","error")
INFLIGHT={}            # did -> {cid: job}
SESSIONS={}            # did -> session id (latest wins)
LAST_BEAT={}           # did -> ts
STEPS=collections.defaultdict(lambda: collections.deque(maxlen=STEP_KEEP))
_audit=lambda **k: None
def set_audit(fn):
    global _audit; _audit=fn
def stamp(job):
    job.setdefault("ts",time.time()); job["attempt"]=job.get("attempt",0)+1; return job
def expired(job): return time.time()-job.get("ts",time.time())>PENDING_TTL
def mark_sent(did,job): INFLIGHT.setdefault(did,{})[job["cid"]]=job
def mark_done(did,cid): INFLIGHT.get(did,{}).pop(cid,None)
def beat(did): LAST_BEAT[did]=time.time()
def online(did,last_seen=None):
    t=max(LAST_BEAT.get(did,0),last_seen or 0); return time.time()-t<HB_TIMEOUT
def open_session(did,sid):
    old=SESSIONS.get(did); SESSIONS[did]=sid; beat(did)
    _audit(ev="link_session",device=did,replaced=bool(old)); return old
def is_current(did,sid): return SESSIONS.get(did)==sid
def close_session(did,sid,q):
    """Re-queue unanswered jobs so a quick reconnect picks them up."""
    if SESSIONS.get(did)==sid: SESSIONS.pop(did,None)
    n=0
    for cid,job in list(INFLIGHT.get(did,{}).items()):
        INFLIGHT[did].pop(cid,None)
        if job.get("attempt",1)<MAX_ATTEMPTS and not expired(job):
            q.put_nowait(job); n+=1
        else: _audit(ev="link_drop",device=did,cid=cid,why="attempts/ttl")
    if n: _audit(ev="link_requeue",device=did,n=n)
    return n
def add_step(did,b):
    ph=b.get("phase")
    if ph not in PHASES: return None
    e={"t":time.time(),"cid":str(b.get("cid",""))[:16],"phase":ph,"text":str(b.get("text",""))[:500]}
    STEPS[did].append(e); return e
def steps(did,since=0): return [e for e in STEPS.get(did,()) if e["t"]>since]
async def next_job(q,did):
    """Get next live job, dropping stale ones."""
    while True:
        job=await q.get()
        if expired(job): _audit(ev="link_drop",device=did,cid=job.get("cid"),why="ttl"); continue
        return stamp(job)

# ---- Phase C: live frames (owner opt-in per device, default OFF) ----
import os, re, base64, uuid
FRAME_DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)),"data","live_frames")
FRAME_MAX=600*1024; FRAME_KEEP=60
LIVE_ON=set()          # device ids where owner turned live frames on (memory; resets to OFF on restart)
WS_SEND={}             # did -> async send_json of current session
def save_frame(did,b64):
    """Write a JPEG/PNG frame to data/live_frames/<did>/, keep newest FRAME_KEEP. Returns file name or None."""
    if not re.fullmatch(r"[0-9a-zA-Z_-]{1,40}",did or ""): return None
    try: data=base64.b64decode(b64,validate=False)
    except Exception: return None
    if len(data)>FRAME_MAX: return None
    ext="jpg" if data.startswith(b"\xff\xd8\xff") else "png" if data.startswith(b"\x89PNG") else None
    if not ext: return None
    d=os.path.join(FRAME_DIR,did); os.makedirs(d,exist_ok=True)
    fs=sorted((os.path.join(d,x) for x in os.listdir(d)),key=os.path.getmtime)
    for old in fs[:max(0,len(fs)-FRAME_KEEP+1)]:
        try: os.remove(old)
        except OSError: pass
    fn=uuid.uuid4().hex+"."+ext; open(os.path.join(d,fn),"wb").write(data); return fn
def frame_path(did,fn):
    if not re.fullmatch(r"[0-9a-zA-Z_-]{1,40}",did or "") or not re.fullmatch(r"[0-9a-f]{32}\.(jpg|png)",fn or ""): return None
    p=os.path.join(FRAME_DIR,did,fn); return p if os.path.isfile(p) else None
