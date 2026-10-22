"""Windows launcher: load .env, mirror it into ~/.secrets (where the app reads config), create missing keys, run uvicorn."""
import os, sys, secrets as _s
APP=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEC=os.path.join(os.path.expanduser("~"),".secrets")
def load_env(p):
    d={}
    if os.path.exists(p):
        for l in open(p,encoding="utf-8-sig"):
            l=l.strip()
            if l and not l.startswith("#") and "=" in l:
                k,v=l.split("=",1); d[k.strip()]=v.strip().strip('"')
    return d
FILES={"bangla_bhai":["BB_USER","BB_PASSWORD","BB_SESSION_SECRET","BB_OTP_DEV","BB_EDGE_SECRET","BB_TELEGRAM_TOKEN"],
 "groq":["GROQ_API_KEY"],"gemini":["GEMINI_API_KEY"],"openrouter":["OPENROUTER_API_KEY"],"bbai":["BBAI_TOKEN"],
 "deepgram":["DEEPGRAM_API_KEY"],"assemblyai":["ASSEMBLYAI_API_KEY"],"cartesia":["CARTESIA_API_KEY"],
 "resend":["RESEND_API_KEY","RESEND_FROM"],"agent_gmail":["EMAIL","PASSWORD","AGENT_GMAIL","AGENT_GMAIL_PASSWORD"],"vapid":["VAPID_PUBLIC","VAPID_SUB"]}
def main():
    E=load_env(os.path.join(APP,".env"))
    if not E.get("BB_SESSION_SECRET"): E["BB_SESSION_SECRET"]=_s.token_urlsafe(36)
    if not E.get("BB_USER"): E["BB_USER"]="royal"
    if not E.get("BB_PASSWORD"): sys.exit("Set BB_PASSWORD in .env first (run install.bat).")
    os.makedirs(SEC,exist_ok=True)
    key=os.path.join(SEC,"bb_byok.key")
    if not os.path.exists(key):
        from cryptography.fernet import Fernet
        open(key,"w").write(Fernet.generate_key().decode())
    pem=os.path.join(SEC,"vapid_private.pem")
    vf=os.path.join(SEC,"vapid.env")
    if not E.get("VAPID_PUBLIC"):
        old=load_env(vf)
        if old.get("VAPID_PUBLIC") and os.path.exists(pem): E["VAPID_PUBLIC"]=old["VAPID_PUBLIC"]
        else:
            try:
                import base64
                from py_vapid import Vapid01
                from cryptography.hazmat.primitives import serialization as ser
                v=Vapid01(); v.generate_keys(); v.save_key(pem)
                raw=v.public_key.public_bytes(ser.Encoding.X962,ser.PublicFormat.UncompressedPoint)
                E["VAPID_PUBLIC"]=base64.urlsafe_b64encode(raw).decode().rstrip("=")
            except Exception as e: print("push keys skipped:",type(e).__name__)
    E.setdefault("VAPID_SUB","mailto:"+(E.get("BB_OWNER_EMAIL") or "admin@example.com"))
    for name,keys in FILES.items():
        lines=[f"{k}={E[k]}" for k in keys if E.get(k)]
        p=os.path.join(SEC,name+".env")
        with open(p,"w",encoding="utf-8") as f: f.write("\n".join(lines)+"\n")
    for k in ("BB_OWNER_EMAIL","BB_INSECURE_COOKIE","BB_TELEGRAM_TOKEN","BB_FREE_IMG_DAY","BB_FREE_VID_DAY"):
        if E.get(k): os.environ[k]=E[k]
    os.chdir(APP); sys.path.insert(0,APP)
    import uvicorn
    uvicorn.run("app:app",host="127.0.0.1",port=8090,proxy_headers=True)
if __name__=="__main__": main()
