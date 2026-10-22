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
def push(force=False):
    if os.path.exists(DB):
        b=snapshot(); h=hashlib.sha256(b).hexdigest()
        if force or h!=STATE['db']:
            req('PUT','db',gzip.compress(b)); STATE['db']=h; log('db pushed',len(b))
    if STATE['media'] is None:
        idx=req('GET','media_index'); STATE['media']=set(json.loads(idx) if idx else [])
    mf=media_files(); new=[k for k in mf if k not in STATE['media']]
    for k in new:
        req('PUT','m:'+k,open(mf[k],'rb').read()); STATE['media'].add(k)
    if new: req('PUT','media_index',json.dumps(sorted(STATE['media'])).encode()); log('media pushed',len(new))
def restore():
    b=req('GET','db')
    if b:
        raw=gzip.decompress(b); open(DB+'.restore','wb').write(raw); os.replace(DB+'.restore',DB)
        for x in ('-wal','-shm'):
            try: os.unlink(DB+x)
            except OSError: pass
        STATE['db']=hashlib.sha256(raw).hexdigest(); log('db restored',len(raw))
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
