"""Royal owner dashboard (/admin/dash): overview, users + deep timeline, permissions/approvals,
feature flags, inactive-user nudges (queued → owner Approve & Send), audit log viewer.
Every route is owner-only: page → 303 /admin, API → 403. Writes need X-CSRF."""
import os, time, json, csv, io, hmac, hashlib, secrets, threading, sqlite3, datetime as DT
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
import flags as FL, plans as PL
BASE=os.path.expanduser('~/bangla_bhai')
UI=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'admin_ui','dash.html'),encoding='utf-8').read()
DAY=86400
def _tz_day(t): return DT.datetime.fromtimestamp(t,DT.timezone(DT.timedelta(hours=6))).strftime("%Y-%m-%d")
def _day_ts(d):
    try: return DT.datetime.strptime(d,"%Y-%m-%d").replace(tzinfo=DT.timezone(DT.timedelta(hours=6))).timestamp()+12*3600
    except Exception: return None
def _q(c,sql,a=()):
    try: return [dict(r) for r in c.execute(sql,a)]
    except sqlite3.OperationalError: return []
def _one(c,sql,a=(),d=0):
    try: r=c.execute(sql,a).fetchone(); return (r[0] if r and r[0] is not None else d)
    except sqlite3.OperationalError: return d
def _clip(s,n=180):
    s="" if s is None else str(s); return s if len(s)<=n else s[:n]+"…"

def setup(app,H):
    db=H["db"]; is_admin=H["is_admin"]; AdminOnly=H["AdminOnly"]; audit=H["audit"]; RT=H["RT"]; OWNER=H["owner"]
    SECRET=(H.get("secret") or "x").encode()
    with db() as c:
        c.executescript("""
        create table if not exists nudge_batches(id text primary key,created real,actor text,days int,channel text,subject text,body text,users text,status text,approved real,finished real,results text);
        create table if not exists nudge_log(id integer primary key autoincrement,user text,t real,batch text,via text,status text);
        create table if not exists nudge_optout(user text primary key,t real);""")
    def csrf(request):
        t=request.session.get("csrf")
        if not t: t=secrets.token_urlsafe(24); request.session["csrf"]=t
        return t
    def adm(request,write=False):
        if not is_admin(request): raise AdminOnly
        if write:
            t=request.headers.get("x-csrf",""); s=request.session.get("csrf","")
            if not s or not hmac.compare_digest(t,s): raise AdminOnly
        return request.session.get("u") or OWNER
    def redact(s):
        try: return H["redact"](s)
        except Exception: return s

    # ---------- page ----------
    @app.get("/admin/dash")
    def dash_page(request:Request):
        if not is_admin(request): return RedirectResponse("/admin",303)
        return HTMLResponse(UI.replace("__CSRF__",json.dumps(csrf(request))),headers={"Cache-Control":"no-store","X-Robots-Tag":"noindex"})

    # ---------- helpers ----------
    def last_active_map(c):
        out={}
        for r in _q(c,"select id,created,last_login from users"): out[r["id"]]=max(r["last_login"] or 0,r["created"] or 0)
        for sql in ("select user u,max(updated) t from chats group by user","select user u,max(ts) t from actions group by user",
                    "select user u,max(updated) t from tasks group by user","select user u,max(created) t from media group by user"):
            for r in _q(c,sql):
                if r["u"] is not None: out[r["u"]]=max(out.get(r["u"],0),r["t"] or 0)
        for r in _q(c,"select user u,max(day) d from usage group by user"):
            t=_day_ts(r["d"] or "")
            if t and r["u"] is not None: out[r["u"]]=max(out.get(r["u"],0),min(t,time.time()))
        return out
    def persist_state():
        try: return json.load(open(BASE+"/.persist_state.json"))
        except Exception: return {}
    def standby_state():
        try: return json.load(open(BASE+"/.standby_sync.json"))
        except Exception: return None

    # ---------- overview ----------
    @app.get("/bb/admin/api/dash/overview")
    def ov(request:Request):
        adm(request); now=time.time()
        with db() as c:
            la=last_active_map(c); users=_q(c,"select id,role,created from users")
            days=[(DT.date.today()-DT.timedelta(days=i)).isoformat() for i in range(13,-1,-1)]
            use={d:{"chat":0,"images":0,"voice":0,"videos":0} for d in days}
            for r in _q(c,"select day,kind,sum(n) n from usage where day>=? group by day,kind",(days[0],)):
                if r["day"] in use and r["kind"] in use[r["day"]]: use[r["day"]][r["kind"]]=r["n"]
            msgs={d:0 for d in days}
            for r in _q(c,"select created from messages where created>? and role='user'",(now-15*DAY,)):
                d=_tz_day(r["created"]);
                if d in msgs: msgs[d]+=1
            sign={d:0 for d in days}
            for u in users:
                d=_tz_day(u["created"] or 0)
                if d in sign: sign[d]+=1
            k={"users":len(users),
               "active_24h":sum(1 for t in la.values() if now-t<DAY),"active_7d":sum(1 for t in la.values() if now-t<7*DAY),
               "active_30d":sum(1 for t in la.values() if now-t<30*DAY),
               "chats":_one(c,"select count(*) from chats"),"messages":_one(c,"select count(*) from messages"),
               "messages_24h":_one(c,"select count(*) from messages where created>? and role='user'",(now-DAY,)),
               "tasks":_one(c,"select count(*) from tasks"),"approvals_pending":_one(c,"select count(*) from approvals where status='pending'"),
               "devices":_one(c,"select count(*) from devices where status='approved'"),
               "devices_online":_one(c,"select count(*) from devices where status='approved' and last_seen>?",(now-90,)),
               "media":_one(c,"select count(*) from media"),"jobs":_one(c,"select count(*) from jobs where enabled=1"),
               "audit_24h":_one(c,"select count(*) from audit_events where t>?",(now-DAY,)),
               "login_fail_24h":_one(c,"select count(*) from audit_events where t>? and ev='login' and data like '%\"ok\": false%'",(now-DAY,)),
               "payments_pending":_one(c,"select count(*) from payments where status='pending'"),
               "nudge_pending":_one(c,"select count(*) from nudge_batches where status='pending'")}
        st=persist_state()
        backup={"last_push":st.get("last_push"),"last_check":st.get("last_check"),"restored":st.get("restored"),"daily_last":st.get("daily_last"),
                "daily_kept":st.get("daily_count"),"size_gz":st.get("last_push_gz"),"size_warn":bool(st.get("size_warn")),
                "refused_at":st.get("last_refused"),"refused_reason":st.get("refused_reason"),"limit_mb":25}
        models=[m for m in model_rows() if m["tier"]=="user"]
        return {"now":now,"node":os.environ.get("BB_NODE","box"),"health":H["health"](),"backup":backup,"standby":standby_state(),
                "kpi":k,"usage":use,"messages":msgs,"signups":sign,"models":models,"stats":RT.STATS,
                "advisors":H.get("advisors",[]),"council_on":FL.on("feat_council"),"flags":FL.all_flags()}

    # ---------- users ----------
    @app.get("/bb/admin/api/dash/users")
    def users(request:Request,q:str="",inactive:int=0):
        adm(request); now=time.time()
        with db() as c:
            la=last_active_map(c)
            rows=_q(c,"select id,email,name,role,created,last_login from users order by created desc limit 1000")
            cnt=lambda sql:{r["u"]:r["n"] for r in _q(c,sql)}
            chats=cnt("select user u,count(*) n from chats group by user")
            msgs=cnt("select c.user u,count(*) n from messages m join chats c on c.id=m.chat_id group by c.user")
            acts=cnt("select user u,count(*) n from actions group by user"); tasks=cnt("select user u,count(*) n from tasks group by user")
            appr=cnt("select user u,count(*) n from approvals where status='pending' group by user")
            wk=cnt("select user u,sum(n) n from usage where day>='%s' group by user"%(DT.date.today()-DT.timedelta(days=6)).isoformat())
            nud={r["u"]:r["t"] for r in _q(c,"select user u,max(t) t from nudge_log group by user")}
        out=[]; ql=q.strip().lower()
        for r in rows:
            if ql and ql not in ((r["email"] or "")+" "+(r["name"] or "")+" "+r["id"]).lower(): continue
            a=la.get(r["id"],0)
            if inactive and (now-a)<inactive*DAY: continue
            out.append({**r,"last_active":a,"plan":PL.plan_of(r["id"]),"chats":chats.get(r["id"],0),"messages":msgs.get(r["id"],0),
                        "actions":acts.get(r["id"],0),"tasks":tasks.get(r["id"],0),"pending":appr.get(r["id"],0),"week":wk.get(r["id"],0),
                        "last_nudge":nud.get(r["id"]),"owner":r["role"]=="owner" or r["id"]==OWNER})
        out.sort(key=lambda x:-(x["last_active"] or 0))
        return {"users":out}

    @app.get("/bb/admin/api/dash/users/{uid}")
    def user_detail(request:Request,uid:str):
        adm(request); now=time.time()
        with db() as c:
            u=_q(c,"select id,email,name,role,created,last_login from users where id=?",(uid,))
            if not u: return JSONResponse({"error":"not found"},404)
            u=u[0]; em=(u["email"] or "").lower(); is_own=u["role"]=="owner" or uid==OWNER
            la=last_active_map(c).get(uid,0)
            days=[(DT.date.today()-DT.timedelta(days=i)).isoformat() for i in range(29,-1,-1)]
            use={d:0 for d in days}
            for r in _q(c,"select day,sum(n) n from usage where user=? and day>=? group by day",(uid,days[0])):
                if r["day"] in use: use[r["day"]]=r["n"]
            tl=[]
            for r in _q(c,"select ts,kind,tool,input,ok,status,task from actions where user=? order by ts desc limit 150",(uid,)):
                tl.append({"t":r["ts"],"type":"action","title":(r["tool"] or r["kind"] or "action"),"ok":r["ok"],"status":r["status"],"detail":_clip(redact(r["input"]),160)})
            for r in _q(c,"select created,decided,tool,risk,status,why from approvals where user=? order by created desc limit 100",(uid,)):
                tl.append({"t":r["created"],"type":"approval","title":r["tool"],"risk":r["risk"],"status":r["status"],"detail":_clip(r["why"],160),"decided":r["decided"]})
            for r in _q(c,"select created,updated,goal,status,resumes from tasks where user=? order by created desc limit 80",(uid,)):
                tl.append({"t":r["created"],"type":"task","title":_clip(r["goal"],120),"status":r["status"],"detail":f"resumes {r['resumes'] or 0}"})
            for r in _q(c,"select created,kind,model from media where user=? order by created desc limit 80",(uid,)):
                tl.append({"t":r["created"],"type":"media","title":r["kind"],"detail":r["model"] or ""})
            for r in _q(c,"select created,title,cron,enabled,last_status from jobs where user=? order by created desc limit 40",(uid,)):
                tl.append({"t":r["created"],"type":"job","title":_clip(r["title"],80),"status":("on" if r["enabled"] else "off"),"detail":(r["cron"] or "")+" "+(r["last_status"] or "")})
            for r in _q(c,"select created,status,plan,amount,method from payments where user=? order by created desc limit 40",(uid,)):
                tl.append({"t":r["created"],"type":"payment","title":f"{r['plan']} ৳{r['amount']}","status":r["status"],"detail":r["method"]})
            pats=[uid]+([em] if em else [])
            seen=set()
            for p in pats:
                for r in _q(c,"select id,t,ev,data from audit_events where data like ? order by id desc limit 150",("%"+p+"%",)):
                    if r["id"] in seen: continue
                    seen.add(r["id"]); tl.append({"t":r["t"],"type":"audit","title":r["ev"],"detail":_clip(r["data"],160)})
            for r in _q(c,"select t,action,detail from admin_audit where detail like ? order by id desc limit 60",("%"+uid+"%",)):
                tl.append({"t":r["t"],"type":"admin","title":r["action"],"detail":_clip(r["detail"],160)})
            for r in _q(c,"select t,via,status,batch from nudge_log where user=? order by t desc limit 20",(uid,)):
                tl.append({"t":r["t"],"type":"nudge","title":r["via"],"status":r["status"],"detail":r["batch"]})
            chat_days={}
            for r in _q(c,"select m.created from messages m join chats ch on ch.id=m.chat_id where ch.user=? and m.role='user' and m.created>?",(uid,now-30*DAY)):
                d=_tz_day(r["created"]); chat_days[d]=chat_days.get(d,0)+1
            for d,n in chat_days.items():
                tl.append({"t":_day_ts(d),"type":"chat","title":f"{n} মেসেজ","detail":d})
            counts={"chats":_one(c,"select count(*) from chats where user=?",(uid,)),
                    "messages":_one(c,"select count(*) from messages m join chats ch on ch.id=m.chat_id where ch.user=?",(uid,)),
                    "actions":_one(c,"select count(*) from actions where user=?",(uid,)),"tasks":_one(c,"select count(*) from tasks where user=?",(uid,)),
                    "approvals":_one(c,"select count(*) from approvals where user=?",(uid,)),"media":_one(c,"select count(*) from media where user=?",(uid,)),
                    "memories":_one(c,"select count(*) from memories where user=?",(uid,)),"jobs":_one(c,"select count(*) from jobs where user=?",(uid,)),
                    "skills":_one(c,"select count(*) from skills where user=?",(uid,)),"push":_one(c,"select count(*) from push_subs where user=?",(uid,)),
                    "keys":_one(c,"select count(*) from user_keys where user=?",(uid,)),"connections":_one(c,"select count(*) from conn_oauth where user=?",(uid,))}
            devices=perms=[]
            if is_own:
                devices=_q(c,"select id,name,kind,status,created,last_seen from devices order by created desc")
                perms=_q(c,"select p.device,p.cap,p.mode,d.name from perms p left join devices d on d.id=p.device")
                for d in devices: tl.append({"t":d["created"],"type":"device","title":d["name"],"status":d["status"],"detail":d["kind"]})
            opt=bool(_one(c,"select 1 from nudge_optout where user=?",(uid,)))
        tl=[x for x in tl if x.get("t")]; tl.sort(key=lambda x:-x["t"])
        return {"user":{**u,"plan":PL.plan_of(uid),"last_active":la,"owner":is_own,"optout":opt},"counts":counts,"usage":use,
                "timeline":tl[:400],"devices":devices,"perms":perms}

    # ---------- permissions / approvals ----------
    @app.get("/bb/admin/api/dash/perms")
    def perms(request:Request,kind:str="approvals",status:str="",risk:str="",user:str="",q:str="",days:int=0):
        adm(request); now=time.time(); a=[]; w=[]
        with db() as c:
            em={r["id"]:r["email"] or r["name"] or r["id"] for r in _q(c,"select id,email,name from users")}
            if kind=="approvals":
                if status: w.append("status=?"); a.append(status)
                if risk: w.append("risk=?"); a.append(risk)
                if user: w.append("user=?"); a.append(user)
                if q: w.append("(tool like ? or why like ? or args like ?)"); a+=["%"+q+"%"]*3
                if days: w.append("created>?"); a.append(now-days*DAY)
                rows=_q(c,"select id,user,task,tool,args,why,risk,status,created,decided from approvals"+(" where "+" and ".join(w) if w else "")+" order by created desc limit 300",tuple(a))
                for r in rows: r["who"]=em.get(r["user"],r["user"]); r["args"]=_clip(redact(r["args"]),200); r["why"]=_clip(r["why"],200)
                facets={"status":[r["s"] for r in _q(c,"select distinct status s from approvals") if r["s"]],"risk":[r["s"] for r in _q(c,"select distinct risk s from approvals") if r["s"]]}
            elif kind=="actions":
                if status=="ok": w.append("ok=1")
                elif status=="fail": w.append("(ok=0 or ok is null)")
                if user: w.append("user=?"); a.append(user)
                if q: w.append("(tool like ? or kind like ? or input like ?)"); a+=["%"+q+"%"]*3
                if days: w.append("ts>?"); a.append(now-days*DAY)
                rows=_q(c,"select id,user,ts created,kind,tool,input,ok,status,task from actions"+(" where "+" and ".join(w) if w else "")+" order by ts desc limit 300",tuple(a))
                for r in rows: r["who"]=em.get(r["user"],r["user"]); r["input"]=_clip(redact(r["input"]),200)
                facets={"status":["ok","fail"],"risk":[]}
            else:
                devs=_q(c,"select id,name,kind,status,created,last_seen from devices order by created desc")
                pm={}
                for r in _q(c,"select device,cap,mode from perms"): pm.setdefault(r["device"],{})[r["cap"]]=r["mode"]
                rows=[]
                for d in devs:
                    if status and d["status"]!=status: continue
                    if q and q.lower() not in (d["name"] or "").lower(): continue
                    rows.append({**d,"online":bool(d["last_seen"] and now-d["last_seen"]<90),"perms":pm.get(d["id"],{})})
                facets={"status":[r["s"] for r in _q(c,"select distinct status s from devices") if r["s"]],"risk":[]}
        return {"kind":kind,"rows":rows,"facets":facets,"users":[{"id":k,"label":v} for k,v in em.items()],"caps":H.get("caps",{})}
    @app.post("/bb/admin/api/dash/revoke-all")
    def revoke_all(request:Request):
        a=adm(request,True); H["revoke_all"](); audit(ev="admin_revoke_all",by=a); PL.admin_log(a,"revoke_all","",H["cip"](request)); return {"ok":True}

    # ---------- models (provider flags + dev tier) ----------
    def model_rows():
        now=time.time(); dev=RT.dev_chain(); out=[]
        for k in list(RT.DEFAULT)+[m for m in RT.CHAIN if m not in RT.DEFAULT]:
            v=RT.CHAIN[k]; p=k.split(":")[0]; f=RT.PROV_FLAG.get(p); l=RT.LAST.get(k) or {}
            out.append({"id":k,"label":v[0],"provider":p,"tier":"user" if k in RT.DEFAULT else "dev","in_dev":k in dev,
                        "flag":f,"flag_on":RT.allowed(k),"configured":bool(v[2]),"cooldown":max(0,int(RT.COOL.get(k,0)-now)),
                        "last_ok":l.get("ok"),"last_t":l.get("t"),"last_ms":l.get("ms"),"last_err":l.get("err")})
        return out
    @app.get("/bb/admin/api/dash/models")
    def models_get(request:Request):
        adm(request)
        return {"models":model_rows(),"dev_model":RT.dev_model(),"dev_chain":RT.dev_chain(),"providers":RT.PROVIDERS,"stats":RT.STATS}
    @app.post("/bb/admin/api/dash/devmodel")
    async def devmodel_set(request:Request):
        a=adm(request,True); b=await request.json(); m=str(b.get("model","auto"))
        if m!="auto" and m not in RT.CHAIN: raise HTTPException(400,"unknown model")
        prev=FL.set_val("dev_model",m)
        audit(ev="settings_changed",key="dev_model",frm=str(prev or "auto"),to=m,by=a,ip=H["cip"](request))
        PL.admin_log(a,"dev_model",{"model":m},H["cip"](request))
        return {"ok":True,"dev_model":RT.dev_model(),"dev_chain":RT.dev_chain()}
    @app.post("/bb/admin/api/dash/models/probe")
    async def models_probe(request:Request):
        a=adm(request,True); b=await request.json(); m=str(b.get("id",""))
        if m not in RT.CHAIN: raise HTTPException(400,"unknown model")
        t0=time.time()
        try:
            _n,t,_tr=await RT.complete([{"role":"user","content":"Reply with only the word OK"}],chain=["__none__"],extra=[(m,RT.CHAIN[m])],timeout=60,tries=1)
            ok=bool(t and t.strip()); out=(t or "")[:40]; err=None
        except Exception as e: ok=False; out=""; err=str(e)[:80]
        audit(ev="model_probe",key=m,ok=ok,by=a)
        return {"ok":ok,"reply":out,"err":err,"ms":int((time.time()-t0)*1000)}

    # ---------- flags ----------
    @app.get("/bb/admin/api/dash/flags")
    def flags_get(request:Request):
        adm(request)
        with db() as c: hist=_q(c,"select t,data from audit_events where ev='flag_changed' order by id desc limit 30")
        return {"flags":FL.all_flags(),"history":hist}
    @app.post("/bb/admin/api/dash/flags")
    async def flags_set(request:Request):
        a=adm(request,True); b=await request.json(); k=str(b.get("key","")); v=bool(b.get("on"))
        prev=FL.set_flag(k,v)
        audit(ev="flag_changed",key=k,frm=str(prev),to=("1" if v else "0"),by=a,ip=H["cip"](request))
        PL.admin_log(a,"flag",{"key":k,"on":v},H["cip"](request))
        return {"ok":True,"flags":FL.all_flags()}

    # ---------- nudges ----------
    def unsub_token(uid): return hmac.new(SECRET,("nudge-unsub:"+uid).encode(),hashlib.sha256).hexdigest()[:24]
    @app.get("/bb/admin/api/dash/nudge/candidates")
    def nudge_cands(request:Request,days:int=14):
        adm(request); now=time.time(); days=max(1,min(int(days),365))
        with db() as c:
            la=last_active_map(c); rows=_q(c,"select id,email,name,role,created from users")
            last={r["u"]:r["t"] for r in _q(c,"select user u,max(t) t from nudge_log where status in('sent','dry_run') group by user")}
            opt={r["user"] for r in _q(c,"select user from nudge_optout")}
            push={r["u"] for r in _q(c,"select distinct user u from push_subs")}
        out=[]
        for r in rows:
            if r["role"]=="owner" or r["id"]==OWNER: continue
            a=la.get(r["id"],0)
            if now-a<days*DAY: continue
            why=None
            if r["id"] in opt: why="optout"
            elif last.get(r["id"]) and now-last[r["id"]]<30*DAY: why="recent"
            out.append({"id":r["id"],"email":r["email"],"name":r["name"],"last_active":a,"idle_days":int((now-a)/DAY),
                        "last_nudge":last.get(r["id"]),"eligible":why is None,"why":why,"push":r["id"] in push})
        out.sort(key=lambda x:-x["idle_days"])
        return {"days":days,"users":out}
    @app.get("/bb/admin/api/dash/nudge/batches")
    def nudge_batches(request:Request):
        adm(request)
        with db() as c: rows=_q(c,"select * from nudge_batches order by created desc limit 50")
        for r in rows: r["users"]=json.loads(r["users"] or "[]"); r["results"]=json.loads(r["results"] or "{}")
        return {"batches":rows,"dry_run":os.environ.get("BB_NUDGE_DRYRUN")=="1"}
    @app.post("/bb/admin/api/dash/nudge/batches")
    async def nudge_queue(request:Request):
        a=adm(request,True); b=await request.json()
        ch=b.get("channel","inapp")
        if ch not in("inapp","email","both"): raise ValueError("channel")
        subj=str(b.get("subject","")).strip()[:120]; body=str(b.get("body","")).strip()[:1500]
        if not subj or not body: raise ValueError("বিষয় ও বার্তা লিখুন")
        ids=[str(x) for x in (b.get("users") or [])][:100]
        days=int(b.get("days") or 14)
        elig={x["id"] for x in nudge_cands(request,days)["users"] if x["eligible"]}
        ids=[x for x in dict.fromkeys(ids) if x in elig]
        if not ids: raise ValueError("যোগ্য কোনো ইউজার বাছাই করা হয়নি")
        bid="nb_"+secrets.token_hex(5)
        with db() as c: c.execute("insert into nudge_batches(id,created,actor,days,channel,subject,body,users,status,results) values(?,?,?,?,?,?,?,?,?,?)",
                                  (bid,time.time(),a,days,ch,subj,body,json.dumps(ids),"pending","{}"))
        audit(ev="nudge_queued",batch=bid,n=len(ids),channel=ch,by=a); PL.admin_log(a,"nudge_queued",{"batch":bid,"n":len(ids),"channel":ch},H["cip"](request))
        return {"ok":True,"id":bid,"n":len(ids)}
    @app.post("/bb/admin/api/dash/nudge/batches/{bid}/cancel")
    def nudge_cancel(request:Request,bid:str):
        a=adm(request,True)
        with db() as c: n=c.execute("update nudge_batches set status='cancelled',finished=? where id=? and status='pending'",(time.time(),bid)).rowcount
        if not n: raise ValueError("শুধু পেন্ডিং ব্যাচ বাতিল করা যায়")
        audit(ev="nudge_cancelled",batch=bid,by=a); PL.admin_log(a,"nudge_cancelled",{"batch":bid},H["cip"](request)); return {"ok":True}
    @app.post("/bb/admin/api/dash/nudge/batches/{bid}/approve")
    async def nudge_approve(request:Request,bid:str):
        a=adm(request,True); b=await request.json()
        if b.get("confirm")!="APPROVE_AND_SEND": raise ValueError("explicit confirmation required")
        with db() as c:
            n=c.execute("update nudge_batches set status='sending',approved=? where id=? and status='pending'",(time.time(),bid)).rowcount
            r=_q(c,"select * from nudge_batches where id=?",(bid,))
        if not n or not r: raise ValueError("ব্যাচটি পেন্ডিং নেই")
        audit(ev="nudge_approved",batch=bid,by=a,ip=H["cip"](request)); PL.admin_log(a,"nudge_approved",{"batch":bid},H["cip"](request))
        threading.Thread(target=_send_batch,args=(r[0],),daemon=True).start()
        return {"ok":True,"status":"sending"}
    def _send_batch(bt):
        dry=os.environ.get("BB_NUDGE_DRYRUN")=="1"; res={}
        ids=json.loads(bt["users"] or "[]")
        with db() as c:
            info={r["id"]:r for r in _q(c,"select id,email,name from users")}
            opt={r["user"] for r in _q(c,"select user from nudge_optout")}
        for uid in ids:
            u=info.get(uid); st=[]
            if not u or uid in opt: res[uid]="skipped"; continue
            name=u["name"] or (u["email"] or "").split("@")[0] or "বন্ধু"
            body=bt["body"].replace("{name}",name); subj=bt["subject"].replace("{name}",name)
            if bt["channel"] in("inapp","both"):
                if dry: st.append("inapp:dry_run")
                else:
                    try: H["notify"](uid,subj,body,"/app"); st.append("inapp:sent")
                    except Exception as e: st.append("inapp:fail "+type(e).__name__)
            if bt["channel"] in("email","both"):
                if not u["email"]: st.append("email:no_address")
                elif dry: st.append("email:dry_run")
                else:
                    link=f"{H.get('public_url','https://banglabhai.dpdns.org')}/nudge/unsubscribe?u={uid}&t={unsub_token(uid)}"
                    try:
                        import connections as CN
                        ok,_d=CN.gmail_send(u["email"],subj,body+"\n\n—\nআর এমন মেইল চান না? / Unsubscribe: "+link)
                        st.append("email:sent" if ok else "email:fail")
                    except Exception as e: st.append("email:fail "+type(e).__name__)
                    time.sleep(3)  # be gentle with Gmail limits
            res[uid]=", ".join(st)
            stat="dry_run" if dry else ("sent" if any(x.endswith(":sent") for x in st) else "failed")
            with db() as c: c.execute("insert into nudge_log(user,t,batch,via,status) values(?,?,?,?,?)",(uid,time.time(),bt["id"],bt["channel"],stat))
        fin="dry_run" if dry else "sent"
        with db() as c: c.execute("update nudge_batches set status=?,finished=?,results=? where id=?",(fin,time.time(),json.dumps(res,ensure_ascii=False),bt["id"]))
        audit(ev="nudge_done",batch=bt["id"],status=fin,n=len(ids))
    @app.get("/nudge/unsubscribe")
    def unsub(u:str="",t:str=""):
        ok=bool(u) and hmac.compare_digest(t,unsub_token(u))
        if ok:
            with db() as c: c.execute("insert or replace into nudge_optout values(?,?)",(u,time.time()))
            audit(ev="nudge_optout",user=u)
        msg="আপনাকে আর মনে করানোর মেইল পাঠানো হবে না। / You won't get reminder emails anymore." if ok else "লিংকটি সঠিক নয়। / Invalid link."
        return HTMLResponse(f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Bangla Bhai</title><body style='font-family:system-ui,sans-serif;background:#0a0b14;color:#eef;display:grid;place-items:center;min-height:90vh'><p style='max-width:420px;text-align:center'>{msg}</p></body>",status_code=200 if ok else 400)

    # ---------- audit viewer ----------
    @app.get("/bb/admin/api/dash/audit")
    def audit_view(request:Request,src:str="events",q:str="",ev:str="",days:int=30,limit:int=200,offset:int=0,fmt:str="json"):
        adm(request); now=time.time(); limit=max(1,min(int(limit),2000 if fmt=="csv" else 500)); a=[]; w=[]
        with db() as c:
            if src=="admin":
                if days: w.append("t>?"); a.append(now-days*DAY)
                if ev: w.append("action=?"); a.append(ev)
                if q: w.append("(action like ? or detail like ? or actor like ? or ip like ?)"); a+=["%"+q+"%"]*4
                rows=_q(c,"select id,t,action ev,actor,detail data,ip from admin_audit"+(" where "+" and ".join(w) if w else "")+" order by id desc limit ? offset ?",tuple(a)+(limit,offset))
                evs=[r["e"] for r in _q(c,"select distinct action e from admin_audit order by e")]
                total=_one(c,"select count(*) from admin_audit"+(" where "+" and ".join(w) if w else ""),tuple(a))
            elif src=="dev":
                if days: w.append("t>?"); a.append(now-days*DAY)
                if ev: w.append("ev=?"); a.append(ev)
                if q: w.append("(ev like ? or detail like ? or job like ?)"); a+=["%"+q+"%"]*3
                rows=_q(c,"select rowid id,t,ev,job,detail data from devagent_audit"+(" where "+" and ".join(w) if w else "")+" order by t desc limit ? offset ?",tuple(a)+(limit,offset))
                evs=[r["e"] for r in _q(c,"select distinct ev e from devagent_audit order by e")]
                total=_one(c,"select count(*) from devagent_audit"+(" where "+" and ".join(w) if w else ""),tuple(a))
            else:
                if days: w.append("t>?"); a.append(now-days*DAY)
                if ev: w.append("ev=?"); a.append(ev)
                if q: w.append("(ev like ? or data like ?)"); a+=["%"+q+"%"]*2
                rows=_q(c,"select id,t,ev,data from audit_events"+(" where "+" and ".join(w) if w else "")+" order by id desc limit ? offset ?",tuple(a)+(limit,offset))
                evs=[r["e"] for r in _q(c,"select distinct ev e from audit_events order by e")]
                total=_one(c,"select count(*) from audit_events"+(" where "+" and ".join(w) if w else ""),tuple(a))
        for r in rows: r["data"]=redact(r.get("data") or "")
        if fmt=="csv":
            buf=io.StringIO(); wr=csv.writer(buf); keys=list(rows[0].keys()) if rows else ["id","t","ev","data"]
            wr.writerow(keys+["time_dhaka"])
            for r in rows: wr.writerow([r.get(k) for k in keys]+[DT.datetime.fromtimestamp(r["t"] or 0,DT.timezone(DT.timedelta(hours=6))).strftime("%Y-%m-%d %H:%M:%S")])
            audit(ev="audit_export",src=src,n=len(rows))
            return Response(buf.getvalue(),media_type="text/csv",headers={"Content-Disposition":f"attachment; filename=bb-audit-{src}.csv","Cache-Control":"no-store"})
        return {"src":src,"rows":rows,"events":evs,"total":total}
