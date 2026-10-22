"""Account/plans/payments pages + owner admin dashboard (CSRF + admin audit)."""
import time, json, secrets, hmac, asyncio, datetime as DT
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
import plans as PL, tg as TG
def setup(app,H):
    need=H["need"]; is_admin=H["is_admin"]; FT=H["FT"]; db=H["db"]; cip=H["cip"]; RT=H["RT"]
    def page(en,bn,js): return HTMLResponse(FT.PAGE.replace("{{T_EN}}",en).replace("{{T_BN}}",bn).replace("{{JS}}",js),headers={"Cache-Control":"no-store"})
    def csrf(request):
        t=request.session.get("csrf")
        if not t: t=secrets.token_urlsafe(24); request.session["csrf"]=t
        return t
    def adm(request,write=False):
        if not is_admin(request): raise H["AdminOnly"]
        if write:
            t=request.headers.get("x-csrf",""); s=request.session.get("csrf","")
            if not s or not hmac.compare_digest(t,s): raise H["AdminOnly"]
        return need(request)
    @app.exception_handler(ValueError)
    async def _ve(request,exc): return JSONResponse({"error":str(exc)[:200]},400)
    # ---------- user side ----------
    @app.get("/plans")
    def plans_redirect(): return RedirectResponse("/account",303)
    @app.get("/account")
    def account_page(request:Request):
        if not H["user"](request): return RedirectResponse("/login",303)
        return page("Account & Plan","অ্যাকাউন্ট ও প্ল্যান",ACCOUNT_JS)
    @app.get("/bb/api/account")
    def account(request:Request):
        u=need(request); s=PL.settings()
        pl={k:{**v,"price":PL.price(k)} for k,v in PL.PLANS.items()}
        return {"sub":PL.sub_info(u),"usage":PL.usage_summary(u),"plans":pl,"pay":{"bkash":s["bkash_number"],"nagad":s["nagad_number"],"note":s["pay_note"]},
                "payments":PL.my_payments(u),"telegram":{"linked":TG.link_of(u),"bot":TG.STATE.get("bot"),"running":TG.STATE.get("running")}}
    @app.post("/bb/api/pay")
    async def pay(request:Request):
        u=need(request); b=await request.json()
        if not H["rate_ok"]("pay:"+u,10,86400): return JSONResponse({"error":"Too many submissions today"},429)
        pid=PL.submit_payment(u,b.get("plan"),b.get("method"),b.get("trxid"),b.get("sender"),b.get("amount"))
        H["audit"](ev="payment_submit",pid=pid); H["notify"](H["owner"],"💳 New payment to review",f"{b.get('method')} · {b.get('plan')}","/admin/panel")
        return {"ok":True,"id":pid}
    @app.post("/bb/api/tg/code")
    def tg_code(request:Request):
        u=need(request)
        if not H["rate_ok"]("tgc:"+u,10,3600): return JSONResponse({"error":"Too many codes"},429)
        return {"code":TG.new_code(u),"bot":TG.STATE.get("bot"),"expires_in":600}
    @app.post("/bb/api/tg/unlink")
    def tg_unlink(request:Request): u=need(request); TG.unlink(u); return {"ok":True}
    # ---------- business team seats ----------
    @app.get("/team")
    def team_page(request:Request):
        if not H["user"](request): return RedirectResponse("/login",303)
        return page("Team","টিম",TEAM_JS)
    @app.get("/bb/api/team")
    def team(request:Request):
        u=need(request); to=PL.team_owner_of(u)
        return {"plan":PL.plan_of(u),"member_of":bool(to),"can_manage":(not to and PL._own_plan(u)=="business"),"max":PL.TEAM_MAX,
                "members":([] if to else PL.team_list(u)),"usage":PL.usage_summary(u)}
    @app.post("/bb/api/team/invite")
    async def team_invite(request:Request):
        u=need(request); b=await request.json()
        if not H["rate_ok"]("team:"+u,30,86400): return JSONResponse({"error":"Too many invites today"},429)
        PL.team_invite(u,b.get("email")); H["audit"](ev="team_invite"); return {"ok":True}
    @app.post("/bb/api/team/remove")
    async def team_remove(request:Request):
        u=need(request); b=await request.json(); PL.team_remove(u,b.get("email")); H["audit"](ev="team_remove"); return {"ok":True}
    @app.post("/bb/api/team/leave")
    def team_leave(request:Request): u=need(request); PL.team_leave(u); return {"ok":True}
    # ---------- admin ----------
    @app.get("/admin/panel")
    def admin_panel(request:Request):
        if not is_admin(request): return RedirectResponse("/admin",303)
        return page("Admin dashboard","এডমিন ড্যাশবোর্ড",f"const CSRF={json.dumps(csrf(request))};"+ADMIN_JS)
    @app.get("/bb/admin/api/overview")
    def overview(request:Request):
        adm(request); now=time.time()
        with db() as c:
            try: users=[dict(r) for r in c.execute("select id,email,role,created,last_login from users order by coalesce(last_login,created) desc limit 200")]
            except Exception: users=[]
            subs={r["user"]:dict(r) for r in c.execute("select * from subs")}
            pend=[dict(r) for r in c.execute("select * from payments where status='pending' order by created")]
            recent=[dict(r) for r in c.execute("select * from payments where status!='pending' order by decided desc limit 30")]
            days=[(DT.date.today()-DT.timedelta(days=i)).isoformat() for i in range(13,-1,-1)]
            use={d:{k:0 for k in PL.KINDS} for d in days}
            for r in c.execute("select day,kind,sum(n) n from usage where day>=? group by day,kind",(days[0],)):
                if r["day"] in use and r["kind"] in use[r["day"]]: use[r["day"]][r["kind"]]=r["n"]
            rev={}
            for r in c.execute("select decided,amount from payments where status='approved'"):
                m=time.strftime("%Y-%m",time.localtime(r["decided"])); rev[m]=rev.get(m,0)+(r["amount"] or 0)
            aud=[dict(r) for r in c.execute("select * from admin_audit order by id desc limit 40")]
        for u in users:
            s=subs.get(u["id"]); u["plan"]=PL.plan_of(u["id"]); u["expires"]=s["expires"] if s else None
        em={u["id"]:u["email"] for u in users}
        for p in pend+recent: p["email"]=em.get(p["user"],p["user"])
        counts={k:sum(1 for u in users if u["plan"]==k) for k in PL.PLANS}
        health=[{"id":k,"label":v[0],"configured":bool(v[2]),"cooldown":max(0,int(RT.COOL.get(k,0)-now))} for k,v in RT.CHAIN.items()]
        return {"users":users,"counts":counts,"pending":pend,"recent":recent,"usage":use,"revenue":dict(sorted(rev.items())[-12:]),
                "health":health,"stats":RT.STATS,"settings":PL.settings(),"audit":aud,"telegram":{k:TG.STATE.get(k) for k in("running","bot","error")},"plans":PL.PLANS}
    @app.post("/bb/admin/api/payments/{pid}")
    async def decide(request:Request,pid:str):
        a=adm(request,True); b=await request.json(); ok=b.get("action")=="approve"
        p,exp=PL.decide_payment(pid,ok,b.get("note",""),int(b.get("months") or 1))
        PL.admin_log(a,"payment_"+("approve" if ok else "reject"),{"id":pid,"user":p["user"],"trxid":p["trxid"],"plan":p["plan"]},H["cip"](request))
        H["notify"](p["user"],"✅ Payment approved — "+PL.PLANS[p["plan"]]["name"]+" active" if ok else "❌ Payment rejected",
                    ("Valid until "+time.strftime("%d %b %Y",time.localtime(exp))) if ok else (b.get("note") or "Please check your TrxID and try again."),"/account")
        return {"ok":True,"expires":exp}
    @app.post("/bb/admin/api/users/{uid}/plan")
    async def setplan(request:Request,uid:str):
        a=adm(request,True); b=await request.json(); PL.set_plan(uid,b.get("plan"),int(b.get("days") or 30))
        PL.admin_log(a,"set_plan",{"user":uid,"plan":b.get("plan"),"days":b.get("days")},cip(request)); return {"ok":True}
    @app.post("/bb/admin/api/settings")
    async def setset(request:Request):
        a=adm(request,True); b=await request.json(); ch={}
        for k,v in b.items():
            v=str(v).strip()
            if k in("bkash_number","nagad_number") and v and not __import__("re").fullmatch(r"01[3-9]\d{8}",v): raise ValueError(k+": use 01XXXXXXXXX")
            PL.set_setting(k,v); ch[k]=v
        PL.admin_log(a,"settings",ch,cip(request)); return {"ok":True}
    @app.post("/bb/admin/api/probe")
    async def probe(request:Request):
        adm(request,True); out={}
        async def one(k):
            t=time.time()
            try: await RT.complete([{"role":"user","content":"Reply with OK"}],chain=[k],tries=1,timeout=25); out[k]={"ok":True,"ms":int((time.time()-t)*1000)}
            except Exception as e: out[k]={"ok":False,"err":type(e).__name__}
        await asyncio.gather(*[one(k) for k in RT.CHAIN]); PL.admin_log(need(request),"probe_models",{k:v["ok"] for k,v in out.items()},cip(request)); return out

TEAM_JS=r"""
let D;async function render(){try{D=await api('/bb/api/team')}catch(e){m.innerHTML='<div class="card err">'+esc(e.message)+'</div>';return}
if(D.member_of){m.innerHTML=`<div class=card><b>${T('You are a member of a Business team','আপনি একটি Business টিমের সদস্য')}</b><div class=mut>${T('You share the team daily quotas. Your memory, chats and API keys stay private to you.','আপনি টিমের দৈনিক কোটা ভাগ করে ব্যবহার করেন। আপনার মেমরি, চ্যাট আর API কী শুধু আপনার কাছেই গোপন থাকে।')}</div><button class="b r" style="margin-top:10px" onclick=leave()>${T('Leave team','টিম ছাড়ুন')}</button></div>`;return}
if(!D.can_manage){m.innerHTML=`<div class=card><b>${T('Team seats are part of the Business plan','টিম সিট Business প্ল্যানের অংশ')}</b><div class=mut>${T('Upgrade to Business to invite up to 5 members who share your quotas.','Business-এ আপগ্রেড করলে ৫ জন পর্যন্ত সদস্য যোগ করতে পারবেন, যারা আপনার কোটা ভাগ করবে।')}</div><a href=/account style="color:var(--acc)">${T('See plans','প্ল্যান দেখুন')}</a></div>`;return}
m.innerHTML=`<div class=card><b>${T('Invite a member','সদস্য যোগ করুন')}</b> <span class=mut>(${D.members.length} / ${D.max})</span><div class=mut>${T('They join automatically the next time they log in with an email code. Members share your daily quotas; their memory, chats and API keys stay private.','তারা পরের বার ইমেইল কোড দিয়ে লগইন করলেই নিজে থেকে যুক্ত হবে। সদস্যরা আপনার দৈনিক কোটা ভাগ করবে; তাদের মেমরি, চ্যাট আর API কী গোপন থাকবে।')}</div>
<div class=row style="margin-top:8px"><input id=em type=email class=grow placeholder="${T('Member email','সদস্যের ইমেইল')}"><button class=b onclick=inv() ${D.members.length>=D.max?'disabled':''}>${T('Invite','আমন্ত্রণ')}</button></div><div id=msg class=mut></div></div>`+
(D.members.map(x=>`<div class=card><div class=row><div class=grow><b>${esc(x.email)}</b><div class=mut>${x.status=='active'?T('Active','সক্রিয়')+' · '+when(x.joined):T('Invited, waiting for first login','আমন্ত্রিত, প্রথম লগইনের অপেক্ষায়')}</div></div><button class="b r" onclick="rm('${esc(x.email)}')">${T('Remove','সরান')}</button></div></div>`).join('')||`<div class=empty>${T('No members yet.','এখনো কোনো সদস্য নেই।')}</div>`)}
async function inv(){try{await api('/bb/api/team/invite',{method:'POST',body:JSON.stringify({email:em.value})});render()}catch(e){msg.textContent=e.message;msg.className='err'}}
async function rm(e){if(!confirm(T('Remove this member?','এই সদস্যকে সরাবেন?')))return;await api('/bb/api/team/remove',{method:'POST',body:JSON.stringify({email:e})});render()}
async function leave(){if(!confirm(T('Leave this team?','এই টিম ছাড়বেন?')))return;await api('/bb/api/team/leave',{method:'POST'});render()}
"""
ACCOUNT_JS=r"""
let D;async function render(){try{D=await api('/bb/api/account')}catch(e){m.innerHTML='<div class="card err">'+esc(e.message)+'</div>';return}
const s=D.sub,u=D.usage,P=D.plans;const lim=x=>x==null?'∞':x;
const bar=(k,lab)=>{const x=u[k];const p=x.limit?Math.min(100,100*x.used/x.limit):0;return `<div style="margin:6px 0"><div class="row mut"><span class=grow>${lab}</span><span>${x.used} / ${lim(x.limit)}</span></div><div style="height:6px;background:var(--bd);border-radius:9px"><div style="width:${p}%;height:6px;background:var(--acc);border-radius:9px"></div></div></div>`};
const plan=k=>`<div class=card style="flex:1;min-width:180px;${s.plan==k?'border-color:var(--acc)':''}"><b>${P[k].name}</b> ${s.plan==k?'<span class=tag>'+T('Current','বর্তমান')+'</span>':''}<div style="font-size:22px;margin:6px 0">৳${P[k].price}<span class=mut>${P[k].price?T('/month','/মাস'):''}</span></div>
<div class=mut>${P[k].chat} ${T('messages/day','মেসেজ/দিন')}<br>${P[k].images} ${T('images/day','ছবি/দিন')}<br>${P[k].voice} ${T('voice/day','ভয়েস/দিন')}<br>${P[k].memory} ${T('memories','স্মৃতি')}<br>${P[k].jobs} ${T('schedules','শিডিউল')} · ${P[k].skills} ${T('skills','স্কিল')}</div></div>`;
const pays=D.payments.map(p=>`<div class="row mut"><span class=grow>${when(p.created)} · ${esc(p.method)} · ${esc(p.trxid)} · ৳${p.amount}</span><span class="tag ${p.status=='rejected'?'high':p.status=='pending'?'medium':''}">${esc(p.status)}</span></div>${p.note?'<div class=mut>'+esc(p.note)+'</div>':''}`).join('');
const num=D.pay.bkash||D.pay.nagad;const tgl=D.telegram.linked;
m.innerHTML=`<div class=card><div class=row><div class=grow><b>${T('Your plan','আপনার প্ল্যান')}: ${esc(s.name)}</b>${s.owner?' <span class=tag>ADMIN</span>':''}${s.team_member?' <span class=tag>'+T('Team member','টিম সদস্য')+'</span>':''} ${s.plan=='business'?'<a href=/team style="color:var(--acc);font-size:13px">'+T('Manage team','টিম পরিচালনা')+'</a>':''}<div class=mut>${s.expires?T('Valid until ','মেয়াদ: ')+when(s.expires):''}</div></div></div>
${bar('chat',T('Messages today','আজকের মেসেজ'))}${bar('images',T('Images today','আজকের ছবি'))}${bar('voice',T('Voice today','আজকের ভয়েস'))}</div>
<div class=row style="flex-wrap:wrap;align-items:stretch">${plan('free')}${plan('pro')}${plan('business')}</div>
<div class=card><b>${T('Upgrade with bKash / Nagad','বিকাশ / নগদ দিয়ে আপগ্রেড')}</b>
${num?`<div class=mut style="margin:6px 0">${T('Send money (Send Money) to','এই নম্বরে Send Money করুন')}: ${D.pay.bkash?'bKash <b>'+esc(D.pay.bkash)+'</b>':''} ${D.pay.nagad?' · Nagad <b>'+esc(D.pay.nagad)+'</b>':''}<br>${esc(D.pay.note)}<br>⚠️ ${T('Never share your PIN or OTP with anyone.','কখনো কাউকে PIN বা OTP দেবেন না।')}</div>
<div class=row style="flex-wrap:wrap"><select id=pp><option value=pro>Pro ৳${P.pro.price}</option><option value=business>Business ৳${P.business.price}</option></select><select id=pm><option value=bkash>bKash</option><option value=nagad>Nagad</option></select></div>
<input id=ps placeholder="${T('Your sending number 01XXXXXXXXX','যে নম্বর থেকে পাঠিয়েছেন 01XXXXXXXXX')}" style="margin-top:8px"><input id=pa type=number placeholder="${T('Amount (৳)','টাকার পরিমাণ (৳)')}" style="margin-top:8px"><input id=pt placeholder="TrxID" style="margin-top:8px;text-transform:uppercase">
<button class=b style="margin-top:8px" onclick=pay()>${T('Submit for review','যাচাইয়ের জন্য জমা দিন')}</button><div id=pmsg class=mut></div>`
:`<div class=mut style="margin-top:6px">${T('Payments are not open yet. Please check back soon.','পেমেন্ট এখনো চালু হয়নি। শীঘ্রই আবার দেখুন।')}</div>`}
${pays?'<div style="margin-top:10px">'+pays+'</div>':''}</div>
<div class=card><b>Telegram</b><div class=mut>${tgl?T('Linked','লিংক করা')+(tgl.username?' @'+esc(tgl.username):''):T('Use Bangla Bhai from Telegram: text, voice, photos, PDFs.','Telegram থেকে বাংলা ভাই ব্যবহার করুন: লেখা, ভয়েস, ছবি, PDF।')}</div>
${D.telegram.running?'':'<div class=mut>'+T('Telegram bot is not active yet.','Telegram বট এখনো চালু হয়নি।')+'</div>'}
<div class=row style="margin-top:8px">${tgl?`<button class="b g" onclick=tgu()>${T('Unlink','লিংক বাতিল')}</button>`:`<button class=b onclick=tgc()>${T('Get link code','লিংক কোড নিন')}</button>`}</div><div id=tgm></div></div>`}
async function pay(){pmsg.textContent='…';try{await api('/bb/api/pay',{method:'POST',body:JSON.stringify({plan:pp.value,method:pm.value,sender:ps.value,amount:pa.value,trxid:pt.value})});render()}catch(e){pmsg.innerHTML='<span class=err>'+esc(e.message)+'</span>'}}
async function tgc(){try{const j=await api('/bb/api/tg/code',{method:'POST'});tgm.innerHTML=`<div class=card>${T('Send this to the bot within 10 minutes','১০ মিনিটের মধ্যে বটকে পাঠান')}: <b style="font-size:20px">/link ${j.code}</b>${j.bot?`<br><a href="https://t.me/${esc(j.bot)}?start=${j.code}" target=_blank rel=noopener>${T('Open','খুলুন')} @${esc(j.bot)}</a>`:''}</div>`}catch(e){tgm.innerHTML='<span class=err>'+esc(e.message)+'</span>'}}
async function tgu(){await api('/bb/api/tg/unlink',{method:'POST'});render()}
"""
ADMIN_JS=r"""
async function nbu(u,p){try{const r=p?await W(u):await api(u);nbout.innerHTML=r.url?`<a href="${esc(r.url)}" rel=noreferrer>${esc(r.url)}</a> <button class=b onclick="navigator.clipboard.writeText('${esc(r.url)}')">📋</button>`:'—'}catch(e){nbout.textContent=e.message}}
let D;const W=(u,b)=>api(u,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF':CSRF},body:JSON.stringify(b||{})});
function bars(data,labels,color){const mx=Math.max(1,...data),w=100/data.length;return `<svg viewBox="0 0 100 42" preserveAspectRatio=none style="width:100%;height:120px">${data.map((v,i)=>`<rect x="${i*w+w*.15}" y="${40-38*v/mx}" width="${w*.7}" height="${38*v/mx}" rx=.8 fill="${color}"><title>${esc(labels[i])}: ${v}</title></rect>`).join('')}<line x1=0 y1=40 x2=100 y2=40 stroke="#243a5c" stroke-width=.3 /></svg><div class="row mut" style="font-size:10.5px"><span class=grow>${esc(labels[0]||'')}</span><span>${esc(labels[labels.length-1]||'')} · max ${mx}</span></div>`}
async function render(){try{D=await api('/bb/admin/api/overview')}catch(e){m.innerHTML='<div class="card err">'+esc(e.message)+'</div>';return}
const days=Object.keys(D.usage),chat=days.map(d=>D.usage[d].chat),img=days.map(d=>D.usage[d].images+D.usage[d].voice);const rk=Object.keys(D.revenue),rv=rk.map(k=>D.revenue[k]);
const tot=rv.reduce((a,b)=>a+b,0);const st=D.settings;
const kpi=(n,l)=>`<div class=card style="flex:1;min-width:120px;text-align:center"><div style="font-size:24px;font-weight:700">${n}</div><div class=mut>${l}</div></div>`;
m.style.maxWidth='980px';
m.innerHTML=`<div class=card><a href=/admin/dev style="text-decoration:none;color:inherit">🛠 <b>${T('Dev Agent — change the app by command','ডেভ এজেন্ট — কমান্ড দিয়ে অ্যাপ বদলান')}</b> →</a></div><div class=card><a href=/notebook/ style="text-decoration:none;color:inherit">📒 <b>${T('Royal Notebook — all links, accounts, directory','রয়েল নোটবুক — সব লিংক, অ্যাকাউন্ট, ডিরেক্টরি')}</b> →</a><div class=row style="flex-wrap:wrap;margin-top:6px"><button class=b onclick="nbu('/bb/admin/api/nb/url')">${T('Show no-login link','লগইন ছাড়া লিংক দেখাও')}</button><button class="b r" onclick="if(confirm('Rotate? Old link stops working.'))nbu('/bb/admin/api/nb/rotate',1)">${T('Rotate link','নতুন লিংক বানাও')}</button></div><div id=nbout class=mut style="word-break:break-all"></div></div><div class=row style="flex-wrap:wrap">${kpi(D.users.length,T('Users','ব্যবহারকারী'))}${kpi(D.counts.pro+D.counts.business,T('Paid','পেইড'))}${kpi(D.pending.length,T('Pending payments','পেন্ডিং পেমেন্ট'))}${kpi('৳'+tot,T('Revenue','আয়'))}</div>
<div class=card><b>${T('Pending payments','পেন্ডিং পেমেন্ট')}</b>${D.pending.length?D.pending.map(p=>`<div class=card><div class=row style="flex-wrap:wrap"><span class=grow><b>${esc(p.email)}</b> · ${esc(p.plan)} · ${esc(p.method)} · ৳${p.amount}<br><span class=mut>TrxID <b>${esc(p.trxid)}</b> · ${T('from','থেকে')} ${esc(p.sender)} · ${when(p.created)}</span></span>
<input id=n_${p.id} placeholder="${T('note (optional)','নোট (ঐচ্ছিক)')}" style="max-width:180px"><button class="b ok" onclick="dec('${p.id}','approve')">${T('Approve','অনুমোদন')}</button><button class="b r" onclick="dec('${p.id}','reject')">${T('Reject','বাতিল')}</button></div></div>`).join(''):'<div class=mut>'+T('Nothing to review.','যাচাইয়ের কিছু নেই।')+'</div>'}
<div class=mut>${T('Check the TrxID in your own bKash/Nagad app before approving.','অনুমোদনের আগে নিজের বিকাশ/নগদ অ্যাপে TrxID মিলিয়ে নিন।')}</div></div>
<div class=row style="flex-wrap:wrap;align-items:stretch"><div class=card style="flex:1;min-width:280px"><b>${T('Messages / day (14 days)','মেসেজ / দিন (১৪ দিন)')}</b>${bars(chat,days,'#1e6fd9')}</div><div class=card style="flex:1;min-width:280px"><b>${T('Images + voice / day','ছবি + ভয়েস / দিন')}</b>${bars(img,days,'#3d8bfd')}</div>
<div class=card style="flex:1;min-width:280px"><b>${T('Revenue / month','আয় / মাস')}</b>${rk.length?bars(rv,rk,'#f4b400'):'<div class=mut style="padding:30px 0">'+T('No revenue yet','এখনো আয় নেই')+'</div>'}</div></div>
<div class=card><div class=row><b class=grow>${T('Model health','মডেলের অবস্থা')}</b><button class="b g" onclick=probe()>${T('Test now','এখন পরীক্ষা')}</button></div><div id=ph>${D.health.map(h=>`<div class="row mut" id=h_${h.id.replace(/\W/g,'_')}><span class=grow>${esc(h.label)}</span><span class=tag>${!h.configured?T('no key','কী নেই'):h.cooldown?T('cooling ','বিরতি ')+h.cooldown+'s':'OK'}</span></div>`).join('')}</div>
<div class=mut>${T('Calls','কল')} ${D.stats.calls} · ${T('retries','পুনরায়')} ${D.stats.retries} · ${T('failovers','বদল')} ${D.stats.failovers} · Telegram: ${D.telegram.running?'✅ @'+esc(D.telegram.bot):'⏸ '+esc(D.telegram.error||'')}</div></div>
<div class=card><b>${T('Users','ব্যবহারকারী')}</b><div style="overflow:auto"><table style="width:100%;font-size:13px;border-collapse:collapse">${D.users.map(u=>`<tr style="border-top:1px solid var(--bd)"><td>${esc(u.email||u.id)}${u.role=='owner'?' <span class=tag>ADMIN</span>':''}</td><td>${esc(u.plan)}${u.expires?'<div class=mut>'+when(u.expires)+'</div>':''}</td><td class=mut>${u.last_login?when(u.last_login):'-'}</td><td>${u.role=='owner'?'':`<select onchange="sp('${esc(u.id)}',this.value)"><option value="">${T('Set plan…','প্ল্যান…')}</option><option value=free>Free</option><option value=pro>Pro 30d</option><option value=business>Business 30d</option></select>`}</td></tr>`).join('')}</table></div></div>
<div class=card><b>${T('Settings','সেটিংস')}</b><div class=mut>${T('Payment numbers users will send money to. Leave empty to keep payments closed.','ব্যবহারকারীরা যে নম্বরে টাকা পাঠাবে। খালি রাখলে পেমেন্ট বন্ধ থাকবে।')}</div>
<label class=mut>bKash</label><input id=s_b value="${esc(st.bkash_number)}" placeholder="01XXXXXXXXX"><label class=mut>Nagad</label><input id=s_n value="${esc(st.nagad_number)}" placeholder="01XXXXXXXXX">
<label class=mut>${T('Note shown to users','ব্যবহারকারীকে দেখানো নোট')}</label><input id=s_t value="${esc(st.pay_note)}" placeholder="Send Money, then submit TrxID"><div class=row><div class=grow><label class=mut>Pro ৳</label><input id=s_p value="${esc(st.price_pro)}"></div><div class=grow><label class=mut>Business ৳</label><input id=s_x value="${esc(st.price_business)}"></div></div>
<button class=b style="margin-top:8px" onclick=save()>${T('Save','সেভ')}</button> <span id=smsg class=mut></span></div>
<div class=card><b>${T('Recent payments','সাম্প্রতিক পেমেন্ট')}</b>${D.recent.map(p=>`<div class="row mut"><span class=grow>${esc(p.email)} · ${esc(p.plan)} · ${esc(p.trxid)} · ৳${p.amount}</span><span class=tag>${esc(p.status)}</span></div>`).join('')||'<div class=mut>-</div>'}</div>
<div class=card><b>${T('Admin audit log','এডমিন অডিট লগ')}</b>${D.audit.map(a=>`<div class=mut>${when(a.t)} · ${esc(a.action)} · ${esc(a.detail)}</div>`).join('')||'<div class=mut>-</div>'}</div>
<div class=mut style="text-align:center;padding:10px"><a href=/webui/>Open WebUI</a> · <a href=/bb/link/>Devices</a> · <a href=/change-password>Password</a></div>`}
async function dec(id,a){if(!confirm(a=='approve'?T('Approve this payment?','এই পেমেন্ট অনুমোদন করবেন?'):T('Reject this payment?','বাতিল করবেন?')))return;try{await W('/bb/admin/api/payments/'+id,{action:a,note:document.getElementById('n_'+id).value});render()}catch(e){alert(e.message)}}
async function sp(u,p){if(!p||!confirm(T('Change plan?','প্ল্যান বদলাবেন?')))return;try{await W('/bb/admin/api/users/'+encodeURIComponent(u)+'/plan',{plan:p,days:30});render()}catch(e){alert(e.message)}}
async function save(){smsg.textContent='…';try{await W('/bb/admin/api/settings',{bkash_number:s_b.value,nagad_number:s_n.value,pay_note:s_t.value,price_pro:s_p.value,price_business:s_x.value});smsg.textContent='✓';render()}catch(e){smsg.innerHTML='<span class=err>'+esc(e.message)+'</span>'}}
async function probe(){ph.style.opacity=.5;try{const r=await W('/bb/admin/api/probe');for(const k in r){const el=document.getElementById('h_'+k.replace(/\W/g,'_'));if(el)el.lastElementChild.textContent=r[k].ok?'OK '+r[k].ms+'ms':'FAIL '+(r[k].err||'')}}catch(e){alert(e.message)}ph.style.opacity=1}
"""
