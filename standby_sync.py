"""Box standby: periodically refresh ~/bangla_bhai/data.db from the KV backup (READ-ONLY from KV).
Never runs on Render. Integrity-checked; keeps data.db.bak (previous copy). If the local DB was written
since the last sync (box served failover traffic), that copy is kept as data.db.standby-<time> first.
Usage: standby_sync.py once | loop   (env BB_STANDBY_SYNC_EVERY seconds, default 900)"""
import os, sys, time, json, gzip, hashlib, shutil, glob
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import persist as P
BASE=P.BASE; DB=P.DB; STF=BASE+'/.standby_sync.json'
def log(*a): print(time.strftime('%Y-%m-%d %H:%M:%S'),'[standby-sync]',*a,flush=True)
def st(): 
    try: return json.load(open(STF))
    except Exception: return {}
def wst(**k):
    s=st(); s.update(k); tmp=STF+'.tmp'; open(tmp,'w').write(json.dumps(s)); os.replace(tmp,STF)
def fhash(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()
PRIMARY=os.environ.get('BB_PRIMARY_HEALTH','https://bangla-bhai-q0x5.onrender.com/bb/health')
def primary_up():
    import urllib.request
    for _ in range(2):
        try:
            with urllib.request.urlopen(PRIMARY,timeout=60) as r:
                if r.status==200 and json.loads(r.read()).get('ok'): return True
        except Exception: time.sleep(5)
    return False
def once():
    if os.environ.get('RENDER') or os.environ.get('BB_NODE')=='render': log('not on Render; skipping'); return False
    wst(last_try=time.time())
    if not primary_up():
        wst(ok=False,note='প্রাইমারি ডাউন — বক্স হয়তো সার্ভ করছে, ওভাররাইট করা হয়নি'); log('primary down; not overwriting local db'); return False
    b=P.req('GET','db')
    if not b: wst(ok=False,note='KV-তে db নেই'); log('no remote db'); return False
    raw=gzip.decompress(b); rh=hashlib.sha256(raw).hexdigest()
    s=st()
    if s.get('remote_hash')==rh and os.path.exists(DB) and s.get('local_hash')==fhash(DB):
        wst(ok=True,last_sync_check=time.time(),note=None); return True
    new=DB+'.sync'; open(new,'wb').write(raw)
    stats=P.db_stats(raw)
    if not stats.get('ok') or not stats.get('users'):
        os.unlink(new); wst(ok=False,note='রিমোট কপি ভাঙা/খালি'); log('REFUSED: remote db failed check',{k:stats.get(k) for k in('ok','users')}); return False
    if os.path.exists(DB):
        lh=fhash(DB)
        if s.get('local_hash') and lh!=s.get('local_hash'):
            keep=DB+'.standby-'+time.strftime('%Y%m%d-%H%M%S'); shutil.copy2(DB,keep); os.chmod(keep,0o600)
            log('local db changed since last sync (failover writes?) -> kept',os.path.basename(keep))
            for old in sorted(glob.glob(DB+'.standby-*'))[:-5]: os.unlink(old)
        shutil.copy2(DB,DB+'.bak'); os.chmod(DB+'.bak',0o600)
    os.chmod(new,0o600); os.replace(new,DB)
    for x in('-wal','-shm'):
        try: os.unlink(DB+x)
        except OSError: pass
    wst(ok=True,last_sync=time.time(),last_sync_check=time.time(),remote_hash=rh,local_hash=fhash(DB),users=stats.get('users'),note=None)
    log('standby db refreshed',len(raw),'users',stats.get('users')); return True
if __name__=='__main__':
    cmd=sys.argv[1] if len(sys.argv)>1 else 'once'
    if cmd=='loop':
        every=int(os.environ.get('BB_STANDBY_SYNC_EVERY','900'))
        while True:
            try: once()
            except Exception as e: wst(ok=False,note=type(e).__name__); log('sync failed',type(e).__name__,str(e)[:120])
            time.sleep(every)
    else: once()
