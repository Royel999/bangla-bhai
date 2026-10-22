"""Telegram bot (long polling, private chats only). Starts automatically once BB_TELEGRAM_TOKEN exists
(env var, ~/.secrets/telegram.env or ~/.secrets/bangla_bhai.env). Users link with a one-time code from /account."""
import os, time, asyncio, secrets, sqlite3, httpx, re, json
S=os.path.expanduser('~/.secrets'); BASE=os.path.expanduser('~/bangla_bhai'); DBF=BASE+'/data.db'
H={}   # filled by setup(): answer, stt, ocr_image, ocr_pdf, take, audit, plan_of
STATE={"running":False,"bot":None,"error":"","since":None}
def db():
    c=sqlite3.connect(DBF,timeout=15); c.row_factory=sqlite3.Row; return c
with db() as c:
    c.executescript("""create table if not exists tg_links(tg_id text primary key,user text,username text,created real);
    create table if not exists tg_codes(code text primary key,user text,expires real);""")
def token():
    t=os.environ.get("BB_TELEGRAM_TOKEN","").strip()
    if t: return t
    for f in ("telegram.env","bangla_bhai.env"):
        try:
            for l in open(f"{S}/{f}"):
                if l.startswith("BB_TELEGRAM_TOKEN="): return l.split("=",1)[1].strip().strip('"')
        except Exception: pass
    return ""
def new_code(u):
    code=f"{secrets.randbelow(10**6):06d}"
    with db() as c:
        c.execute("delete from tg_codes where user=? or expires<?",(u,time.time()))
        c.execute("insert into tg_codes values(?,?,?)",(code,u,time.time()+600))
    return code
def link_of(u):
    with db() as c: r=c.execute("select tg_id,username,created from tg_links where user=?",(u,)).fetchone()
    return dict(r) if r else None
def unlink(u):
    with db() as c: c.execute("delete from tg_links where user=?",(u,))
def _user_for(tg_id):
    with db() as c: r=c.execute("select user from tg_links where tg_id=?",(str(tg_id),)).fetchone()
    return r["user"] if r else None
def _redeem(code,tg_id,uname):
    with db() as c:
        r=c.execute("select user from tg_codes where code=? and expires>?",(code,time.time())).fetchone()
        if not r: return None
        c.execute("delete from tg_codes where code=?",(code,))
        c.execute("delete from tg_links where user=? or tg_id=?",(r["user"],str(tg_id)))
        c.execute("insert into tg_links values(?,?,?,?)",(str(tg_id),r["user"],uname or "",time.time()))
    return r["user"]
DOCS={}   # tg_id -> (text, name, ts) last uploaded document for follow-up questions
HELP=("👋 Bangla Bhai / বাংলা ভাই\n\nTo connect: open the app → Account → Telegram → 'Get link code', then send here:\n/link 123456\n\n"
      "অ্যাপে Account → Telegram থেকে কোড নিয়ে এখানে /link 123456 লিখুন।\n\nAfter linking: send text, voice notes, photos or PDFs. /plan · /unlink · /help")
async def _api(c,tok,method,**kw):
    r=await c.post(f"https://api.telegram.org/bot{tok}/{method}",**kw); return r.json()
async def _send(c,tok,chat,text):
    for i in range(0,max(1,len(text)),3900):
        await _api(c,tok,"sendMessage",json={"chat_id":chat,"text":text[i:i+3900] or "…","disable_web_page_preview":True})
async def _file(c,tok,fid,maxb):
    j=await _api(c,tok,"getFile",json={"file_id":fid})
    if not j.get("ok"): raise RuntimeError("file")
    if (j["result"].get("file_size") or 0)>maxb: raise ValueError("too big")
    return (await c.get(f"https://api.telegram.org/file/bot{tok}/{j['result']['file_path']}")).content
async def handle(c,tok,m):
    chat=m.get("chat",{})
    if chat.get("type")!="private": return            # private chats only
    tid=str(m["from"]["id"]); uname=m["from"].get("username",""); txt=(m.get("text") or m.get("caption") or "").strip()
    mm=re.match(r"^/(?:link|start)\s+(\d{6})$",txt)
    if mm:
        u=_redeem(mm.group(1),tid,uname); H["audit"](ev="tg_link",ok=bool(u))
        return await _send(c,tok,chat["id"],"✅ Linked! Now just talk to me. / লিংক হয়েছে!" if u else "❌ Code invalid or expired. Get a new one in the app. / কোড ভুল বা মেয়াদ শেষ।")
    if txt in("/start","/help"): return await _send(c,tok,chat["id"],HELP)
    u=_user_for(tid)
    if not u: return await _send(c,tok,chat["id"],HELP)
    if txt=="/unlink": unlink(u); return await _send(c,tok,chat["id"],"Unlinked. / লিংক বাতিল হয়েছে।")
    if txt=="/plan":
        i=H["sub_info"](u); return await _send(c,tok,chat["id"],f"Plan: {i['name']}"+(f" (until {time.strftime('%d %b %Y',time.localtime(i['expires']))})" if i.get('expires') else ""))
    await _api(c,tok,"sendChatAction",json={"chat_id":chat["id"],"action":"typing"})
    try:
        if m.get("voice") or m.get("audio"):
            v=m.get("voice") or m.get("audio")
            if (v.get("duration") or 0)>120: return await _send(c,tok,chat["id"],"Voice too long (max 2 min). / ভয়েস ২ মিনিটের বেশি।")
            ok,lim=H["take"](u,"voice")
            if not ok: return await _send(c,tok,chat["id"],H["quota_msg"]("voice",lim))
            data=await _file(c,tok,v["file_id"],10_000_000); txt,_=await H["stt"](data,v.get("mime_type") or "audio/ogg")
            await _send(c,tok,chat["id"],"🎙️ "+txt)
        elif m.get("photo") or m.get("document"):
            d=m.get("document"); fid=(d or m["photo"][-1])["file_id"]; name=(d or {}).get("file_name","photo.jpg")
            data=await _file(c,tok,fid,20_000_000)
            if name.lower().endswith(".pdf") or (d or {}).get("mime_type")=="application/pdf": t,_=await asyncio.to_thread(H["ocr_pdf"],data)
            else: t=await asyncio.to_thread(H["ocr_image"],data)
            if not t.strip(): return await _send(c,tok,chat["id"],"No text found. / কোনো লেখা পাওয়া যায়নি।")
            DOCS[tid]=(t[:30000],name,time.time())
            if not txt: return await _send(c,tok,chat["id"],f"📄 Read {name} ({len(t)} chars). Ask me anything about it. / এখন প্রশ্ন করুন।")
        if not txt: return
        ok,lim=H["take"](u,"chat")
        if not ok: return await _send(c,tok,chat["id"],H["quota_msg"]("chat",lim))
        doc=DOCS.get(tid); ctx=f"[Document: {doc[1]}]\n{doc[0]}" if doc and time.time()-doc[2]<3600 else ""
        ans=await H["answer"](u,txt,ctx); H["audit"](ev="tg_msg")
        await _send(c,tok,chat["id"],ans)
    except ValueError: await _send(c,tok,chat["id"],"File too large. / ফাইল খুব বড়।")
    except Exception as e:
        H["audit"](ev="tg_err",err=str(e)[:150]); await _send(c,tok,chat["id"],"⚠️ Something went wrong, please try again. / একটু পরে আবার চেষ্টা করুন।")
async def run():
    off=0
    while True:
        tok=token()
        if not tok: STATE.update(running=False,error="no token"); await asyncio.sleep(60); continue
        try:
            async with httpx.AsyncClient(timeout=70) as c:
                me=await _api(c,tok,"getMe")
                if not me.get("ok"): STATE.update(running=False,error="token rejected"); await asyncio.sleep(300); continue
                STATE.update(running=True,bot=me["result"].get("username"),error="",since=time.time())
                await _api(c,tok,"deleteWebhook")
                while token()==tok:
                    j=await _api(c,tok,"getUpdates",json={"offset":off,"timeout":50,"allowed_updates":["message"]})
                    for up in j.get("result",[]):
                        off=up["update_id"]+1
                        if up.get("message"): asyncio.create_task(handle(c,tok,up["message"]))
        except asyncio.CancelledError: raise
        except Exception as e: STATE.update(running=False,error=type(e).__name__); await asyncio.sleep(15)
