"""Multi-user auth: email OTP + owner password. Never print secrets."""
import os, json, time, hmac, hashlib, secrets, sqlite3, smtplib, ssl, re
from email.message import EmailMessage
BASE=os.path.expanduser('~/bangla_bhai'); S=os.path.expanduser('~/.secrets')
DB=BASE+'/data.db'; AUDIT=BASE+'/audit.jsonl'
EMAIL_RE=re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

def env(f):
    d={}
    try:
        for l in open(f):
            if '=' in l: k,v=l.strip().split('=',1); d[k]=v.strip().strip('"')
    except Exception: pass
    return d
CFG=env(S+'/bangla_bhai.env'); GMAIL=env(S+'/agent_gmail.env')
# optional Resend
RESEND=env(S+'/resend.env') if os.path.exists(S+'/resend.env') else {}

def audit(**k): open(AUDIT,'a').write(json.dumps({"t":time.time(),**k},ensure_ascii=False)+"\n")
def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

with db() as c:
    c.executescript("""
create table if not exists users(id text primary key, email text unique, name text, role text default 'user', created real, last_login real);
create table if not exists otps(email text, code_hash text, expires real, tries int default 0, created real);
create index if not exists otps_email on otps(email);
""")

def owner_user(): return CFG.get("BB_USER","abba")
def is_owner(uid): return uid==owner_user()

def ensure_owner():
    u=owner_user()
    with db() as c:
        if not c.execute("select 1 from users where id=?",(u,)).fetchone():
            c.execute("insert into users values(?,?,?,?,?,?)",(u,None,"রয়েল","owner",time.time(),None))
ensure_owner()

def normalize_email(e): return (e or "").strip().lower()

def hash_code(email, code):
    return hashlib.sha256(f"{CFG.get('BB_SESSION_SECRET','x')}:{email}:{code}".encode()).hexdigest()

def create_otp(email):
    email=normalize_email(email)
    if not EMAIL_RE.match(email): raise ValueError("ইমেইল ঠিক নয়")
    code=f"{secrets.randbelow(1000000):06d}"
    with db() as c:
        c.execute("delete from otps where email=?",(email,))
        c.execute("insert into otps values(?,?,?,?,?)",(email,hash_code(email,code),time.time()+600,0,time.time()))
    return code

def verify_otp(email, code):
    email=normalize_email(email); code=(code or "").strip()
    with db() as c:
        r=c.execute("select * from otps where email=? order by created desc limit 1",(email,)).fetchone()
        if not r: return False,"কোড পাওয়া যায়নি — আবার পাঠান"
        if r["expires"]<time.time(): return False,"কোডের মেয়াদ শেষ — আবার পাঠান"
        if r["tries"]>=5: return False,"অনেকবার ভুল — নতুন কোড নিন"
        c.execute("update otps set tries=tries+1 where email=? and created=?",(email,r["created"]))
        if not hmac.compare_digest(r["code_hash"], hash_code(email,code)): return False,"ভুল কোড"
        c.execute("delete from otps where email=?",(email,))
        uid="u_"+hashlib.sha256(email.encode()).hexdigest()[:16]
        if not c.execute("select 1 from users where id=?",(uid,)).fetchone():
            c.execute("insert into users values(?,?,?,?,?,?)",(uid,email,email.split("@")[0],"user",time.time(),time.time()))
        else:
            c.execute("update users set last_login=?, email=? where id=?",(time.time(),email,uid))
    audit(ev="otp_login",email=email); return True, uid

def send_otp_email(email, code):
    """Returns (ok, method, detail). Uses Resend if key, else Gmail SMTP of agent inbox."""
    subject=f"{code} — Bangla Bhai login code / বাংলা ভাই লগইন কোড"
    body=(f"Your Bangla Bhai login code: {code}\n"
          f"আপনার বাংলা ভাই লগইন কোড: {code}\n\n"
          f"কোডটি ১০ মিনিটের জন্য বৈধ। কেউ চাইলে শেয়ার করবেন না।\n\n"
          f"— বাংলা ভাই · Royal Universe")
    errs=[]
    # 0) Owner's connected Gmail (OAuth gmail.compose) — free, any recipient
    try:
        import connections as CN
        ok,d=CN.gmail_send(email,subject,body)
        if ok: audit(ev="otp_sent",via="gmail_api",email=email); return True,"gmail_api","OK"
        errs.append(d)
    except Exception as e: errs.append("gmail_api "+type(e).__name__)
    # 1) Resend (onboarding@resend.dev can only reach the Resend account owner until a domain is verified)
    if RESEND.get("RESEND_API_KEY"):
        try:
            import httpx
            fr=RESEND.get("RESEND_FROM") or "Bangla Bhai <onboarding@resend.dev>"
            r=httpx.post("https://api.resend.com/emails",
                headers={"Authorization":"Bearer "+RESEND["RESEND_API_KEY"]},
                json={"from":fr,"to":[email],"subject":subject,"text":body},timeout=30)
            if r.status_code in(200,201):
                audit(ev="otp_sent",via="resend",email=email); return True,"resend","OK"
            errs.append(f"resend {r.status_code}")
        except Exception as e: errs.append("resend "+type(e).__name__)
    # 2) Gmail SMTP (existing agent mailbox — no new account)
    guser=GMAIL.get("AGENT_GMAIL") or GMAIL.get("EMAIL")
    gpw=GMAIL.get("AGENT_GMAIL_PASSWORD") or GMAIL.get("PASSWORD")
    last_err=""
    # Skip slow Gmail SMTP when BB_OTP_DEV=1 (local QA); still try Resend above
    if guser and gpw and CFG.get("BB_OTP_DEV")!="1":
        try:
            msg=EmailMessage(); msg["Subject"]=subject; msg["From"]=f"বাংলা ভাই <{guser}>"; msg["To"]=email
            msg.set_content(body)
            ctx=ssl.create_default_context()
            with smtplib.SMTP("smtp.gmail.com",587,timeout=3) as s:
                s.starttls(context=ctx); s.login(guser,gpw); s.send_message(msg)
            audit(ev="otp_sent",via="gmail_smtp",email=email); return True,"gmail","OK"
        except Exception as e:
            last_err=str(e)[:160]; audit(ev="otp_send_fail",via="gmail_smtp",err=last_err)
    # 3) Dev fallback only when enabled (local box QA) — code never exposed over HTTP
    if CFG.get("BB_OTP_DEV")=="1":
        path=BASE+"/otp_dev_last.json"
        open(path,"w").write(json.dumps({"email":email,"code":code,"t":time.time(),"via":"dev","note":last_err}))
        os.chmod(path,0o600)
        audit(ev="otp_sent",via="dev_file",email=email)
        return True,"dev","ডেভ মোড: ইমেইল পাঠানো যায়নি, কোড সার্ভার ফাইলে (পাবলিক নয়)"
    if last_err: errs.append("smtp")
    audit(ev="otp_send_fail",email_dom=email.split("@")[-1],errs=errs)
    return False,"none", ";".join(errs) or "ইমেইল পাঠানোর উপায় নেই — Resend API কী বা Gmail SMTP ঠিক করুন (অনুমতি লাগবে)"

def user_row(uid):
    with db() as c: r=c.execute("select * from users where id=?",(uid,)).fetchone()
    return dict(r) if r else None
