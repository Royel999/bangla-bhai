"""Persistence for ephemeral hosts (Render free): data.db + media_store snapshot to
Cloudflare Workers KV via the domain's Worker (/__bbstore/, auth = X-BB-Edge secret).
  python persist.py restore   # on boot, before uvicorn
  python persist.py loop      # background: push changes every BB_PERSIST_EVERY s
  python persist.py push      # one-shot (SIGTERM / manual)"""
import os, sys, time, gzip, sqlite3, hashlib, tempfile, urllib.request, urllib.parse, json
BASE=os.path.expanduser('~/bangla_bhai'); DB=BASE+'/data.db'; MED=BASE+'/media_store'
URL=os.environ.get('BB_PERSIST_URL','https://banglabhai.dpdns.org/__bbstore').rstrip('/')
def _sec():
    v=os.environ.get('BB_EDGE_SECRET','')
    if not v:
        try:
            for l in open(os.path.expanduser('~/.secrets/bangla_bhai.env')):
                if l.startswith('BB_EDGE_SECRET='): v=l.split('=',1)[1].strip()
        except OSError: pass
    return v
def req(method,key,data=None):
    r=urllib.request.Request(URL+'/'+urllib.parse.quote(key,safe=''),data=data,method=method,
        headers={'X-BB-Edge':_sec(),'User-Agent':'bb-persist'})
    try:
        with urllib.request.urlopen(r,timeout=60) as f: return f.read()
    except urllib.error.HTTPError as e:
        if e.code==404: return None
        raise
def log(*a): print(time.strftime('%F %T'),'[persist]',*a,flush=True)
def snapshot():
    fd,tmp=tempfile.mkstemp(suffix='.db'); os.close(fd)
    src=sqlite3.connect(DB); dst=sqlite3.connect(tmp); src.backup(dst); dst.close(); src.close()
    b=open(tmp,'rb').read(); os.unlink(tmp); return b
def media_files():
    out={}
    for root,_,fs in os.walk(MED):
        for f in fs:
            p=os.path.join(root,f); rel=os.path.relpath(p,MED)
            if os.path.getsize(p)<=20*1024*1024: out[rel]=p
    return out
STATE={'db':None,'media':None}
# ---- backup safety: dated daily snapshots + shrink/corruption guard + size warning ----
STATEF=BASE+'/.persist_state.json'   # local status for /bb/health (no secrets)
KEEP_DAYS=int(os.environ.get('BB_BACKUP_KEEP','14'))
KV_LIMIT=25*1024*1024; KV_WARN=int(os.environ.get('BB_BACKUP_WARN_MB','20'))*1024*1024
DAILY_IDX='db_daily_index'
def _rstate():
    try: return json.load(open(STATEF))
    except Exception: return {}
def _wstate(**k):
    st=_rstate(); st.update(k); tmp=STATEF+'.tmp'
    try:
        with open(tmp,'w') as f: json.dump(st,f)
        os.replace(tmp,STATEF)
    except OSError: pass
def dhaka_day(t=None):
    return time.strftime('%Y%m%d',time.gmtime((t or time.time())+6*3600))
def db_stats(raw):
    """Counts from a DB image (bytes). Returns dict; ok=False if unreadable/corrupt."""
    fd,tmp=tempfile.mkstemp(suffix='.db'); os.close(fd)
    try:
        open(tmp,'wb').write(raw); c=sqlite3.connect(tmp)
        try:
            chk=c.execute('pragma quick_check').fetchone()[0]
            def n(t):
                try: return c.execute(f'select count(*) from {t}').fetchone()[0]
                except sqlite3.Error: return None
            return {'ok':chk=='ok','check':chk[:80],'size':len(raw),'users':n('users'),'messages':n('messages'),'chats':n('chats')}
        finally: c.close()
    except Exception as e: return {'ok':False,'check':type(e).__name__,'size':len(raw)}
    finally:
        try: os.unlink(tmp)
        except OSError: pass
def guard(new,base):
    """Return None if safe to push, else a reason string. base = stats of last good backup."""
    if os.environ.get('BB_PERSIST_ALLOW_SHRINK')=='1': return None
    if not new.get('ok'): return 'integrity check failed: '+str(new.get('check'))
    if new.get('users') is None: return 'users table missing'
    if not base: return None
    bu=base.get('users') or 0; nu=new.get('users') or 0
    if bu>0 and nu==0: return f'users dropped {bu}->0'
    if bu>=4 and nu<bu*0.5: return f'users dropped sharply {bu}->{nu}'
    bs=base.get('size') or 0
    if bs>=64*1024 and new['size']<bs*0.3: return f'db size dropped sharply {bs}->{new["size"]}'
    bm=base.get('messages') or 0; nm=new.get('messages') or 0
    if bm>=50 and nm<bm*0.3: return f'messages dropped sharply {bm}->{nm}'
    return None
def _daily(gz,stats):
    day=dhaka_day()
    if _rstate().get('daily_day')==day: return
    idx=req('GET',DAILY_IDX); days=json.loads(idx) if idx else []
    if day not in days:
        req('PUT','db-'+day,gz); days.append(day); days=sorted(set(days))
        for old in days[:-KEEP_DAYS]:
            try: req('DELETE','db-'+old); log('daily pruned',old)
            except Exception as e: log('prune failed',old,type(e).__name__)
        days=days[-KEEP_DAYS:]; req('PUT',DAILY_IDX,json.dumps(days).encode())
        log('daily snapshot','db-'+day,'kept',len(days))
    _wstate(daily_day=day,daily_count=len(days),daily_last='db-'+day)
def push(force=False):
    _wstate(last_check=time.time())
    if os.path.exists(DB):
        try: b=snapshot()
        except Exception as e:
            log('REFUSED push (backup kept safe): local db unreadable',e); _wstate(last_refused=time.time(),refused_reason='local db unreadable'); return False
        h=hashlib.sha256(b).hexdigest()
        if force or h!=STATE['db']:
            st=db_stats(b); base=_rstate().get('base')
            why=guard(st,base)
            if why:
                log('REFUSED push (backup kept safe):',why)
                _wstate(last_refused=time.time(),refused_reason=why[:200]); return False
            gz=gzip.compress(b)
            if len(gz)>=KV_LIMIT-1024:
                log('REFUSED push: compressed db',len(gz),'bytes exceeds KV 25MB limit')
                _wstate(last_refused=time.time(),refused_reason='db too large for KV',size_warn=True); return False
            warn=len(gz)>=KV_WARN
            if warn: log('WARN compressed db',len(gz),'bytes is near the 25MB KV limit')
            req('PUT','db',gz); STATE['db']=h; log('db pushed',len(b),'gz',len(gz))
            _wstate(last_push=time.time(),last_push_gz=len(gz),size_warn=warn,
                    base={k:st.get(k) for k in ('size','users','messages','chats')})
            try: _daily(gz,st)
            except Exception as e: log('daily snapshot failed',type(e).__name__)
    if STATE['media'] is None:
        idx=req('GET','media_index'); STATE['media']=set(json.loads(idx) if idx else [])
    mf=media_files(); new=[k for k in mf if k not in STATE['media']]
    for k in new:
        req('PUT','m:'+k,open(mf[k],'rb').read()); STATE['media'].add(k)
    if new: req('PUT','media_index',json.dumps(sorted(STATE['media'])).encode()); log('media pushed',len(new))
    return True
def restore():
    b=req('GET','db')
    if not b:
        # rolling key missing: fall back to newest dated snapshot instead of starting empty
        idx=req('GET',DAILY_IDX); days=json.loads(idx) if idx else []
        for d in reversed(days):
            b=req('GET','db-'+d)
            if b: log('rolling db missing; using daily snapshot','db-'+d); break
    if b:
        raw=gzip.decompress(b); open(DB+'.restore','wb').write(raw); os.replace(DB+'.restore',DB)
        for x in ('-wal','-shm'):
            try: os.unlink(DB+x)
            except OSError: pass
        STATE['db']=hashlib.sha256(raw).hexdigest(); log('db restored',len(raw))
        st=db_stats(raw); _wstate(base={k:st.get(k) for k in ('size','users','messages','chats')},restored=time.time())
    else: log('no remote db; starting fresh')
    idx=req('GET','media_index'); keys=json.loads(idx) if idx else []
    n=0
    for k in keys:
        p=os.path.join(MED,k)
        if os.path.exists(p): continue
        d=req('GET','m:'+k)
        if d is None: continue
        os.makedirs(os.path.dirname(p),exist_ok=True); open(p,'wb').write(d); n+=1
    STATE['media']=set(keys); log('media restored',n)
if __name__=='__main__':
    cmd=sys.argv[1] if len(sys.argv)>1 else 'push'
    if cmd=='restore':
        for i in range(5):
            try: restore(); break
            except Exception as e: log('restore failed',e); time.sleep(5)
        else: sys.exit(1)
    elif cmd=='loop':
        time.sleep(30); every=int(os.environ.get('BB_PERSIST_EVERY','120'))
        while True:
            try: push()
            except Exception as e: log('push failed',e)
            time.sleep(every)
    else: push(force=True)
