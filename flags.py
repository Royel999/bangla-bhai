"""Owner feature flags. Stored in app_settings (k=flag name, v='1'/'0'), default ON so nothing changes
until the owner turns a feature off. Every change is written to audit_events by the caller (admin_dash)."""
import os, sqlite3, time
DBF=os.path.expanduser('~/bangla_bhai')+'/data.db'
# key: (default, Bangla label, English label, what it does)
FLAGS={
 "signups_open":     ("1","নতুন সাইনআপ","New signups","নতুন ইমেইলে অ্যাকাউন্ট খোলা (বিদ্যমান ইউজার ও আমন্ত্রিত টিম সদস্য সবসময় পারবে)"),
 "feat_agent":       ("1","এজেন্ট টুলস","Agent tools","এজেন্ট টাস্ক ও সব টুল চালানো (বন্ধ করলে নিচের তিনটাও বন্ধ)"),
 "feat_browse":      ("1","ব্রাউজ","Browse","হেডলেস ব্রাউজারে ওয়েবপেজ খোলা"),
 "feat_shell":       ("1","শেল","Shell","বক্স/ডিভাইসে শেল কমান্ড"),
 "feat_devices":     ("1","ডিভাইস অ্যাকশন","Device actions","যুক্ত ফোন/ল্যাপটপে কাজ চালানো ও নতুন ডিভাইস পেয়ার"),
 "feat_council":     ("1","কাউন্সিল","Council","একাধিক মডেলের পরামর্শ (কাউন্সিল)"),
 "feat_pwa_install": ("1","অ্যাপ ইনস্টল (PWA)","PWA install","ইনস্টল বোতাম ও ইনস্টল প্রম্পট"),
 # v3 UI rollout (owner always sees /v3; these control everyone else)
 "feat_ui_v3":       ("1","নতুন UI (v3) সবার জন্য","New UI v3 for all","চালু = সব ইউজার নতুন চ্যাট/স্কিল/এজেন্ট UI পাবে; বন্ধ = শুধু মালিক (/v3), বাকিরা পুরনো /app"),
 "feat_skill_catalog":("1","স্কিল ক্যাটালগ","Skill catalog","বিল্ট-ইন স্কিল তালিকা ও চ্যাটে স্কিল ব্যবহার (মালিক সবসময় পারবে)"),
 "feat_user_agents": ("1","ইউজারের নিজস্ব এজেন্ট","Personal agents","ইউজাররা নিজের এজেন্ট বানাতে/এডিট করতে পারবে (সর্বোচ্চ ৫টা)"),
 "feat_user_agent_tools":("1","ইউজার এজেন্টের নিরাপদ টুল","User agent safe tools","ইউজারের এজেন্ট শুধু web_search/browse চালাতে পারবে, প্রতিটা ঝুঁকির কাজে অনুমতি কার্ড; বন্ধ = টুল শুধু মালিকের"),
 # AI providers (router.PROV_FLAG). Off = that provider's models are skipped in every chain.
 "prov_groq":        ("1","Groq","AI provider","GPT-OSS 120B — মূল ইউজার মডেল (ফ্রি, ~১০০০/দিন)"),
 "prov_gemini":      ("1","Google Gemini","AI provider","Gemini Flash-Lite (ইউজার) ও 3.6 Flash (ডেভ) — ফ্রি টিয়ার"),
 "prov_zai":         ("1","Z.ai GLM","AI provider","GLM-4.7 Flash — অফিসিয়াল ফ্রি মডেল (ইউজার ব্যাকআপ)"),
 "prov_cloudflare":  ("1","Cloudflare Workers AI","AI provider","GPT-OSS 120B ও Llama 3.3 70B — দিনে ১০k নিউরন ফ্রি"),
 "prov_mistral":     ("1","Mistral","AI provider","Ministral 14B (ইউজার) ও Codestral (ডেভ) — ফ্রি কী"),
 "prov_openrouter":  ("1","OpenRouter (ফ্রি)","AI provider","Auto Free + Nemotron Ultra / Laguna (ডেভ) — মোট ৫০/দিন"),
 "prov_pollinations":("1","Pollinations (ডেভ)","AI provider","GPT-5.3 Codex, GPT-6 Sol, Kimi K3, GLM-5.3 — দৈনিক ফ্রি Pollen; শুধু মালিক/ডেভ"),
}
_C={"t":0,"v":{}}
def _load():
    if time.time()-_C["t"]<3: return _C["v"]
    try:
        c=sqlite3.connect(DBF,timeout=5)
        try: d={k:v for k,v in c.execute("select k,v from app_settings where k in (%s)"%",".join("?"*len(FLAGS)),tuple(FLAGS))}
        finally: c.close()
    except Exception: d={}
    _C["v"]=d; _C["t"]=time.time(); return d
def on(name):
    d=_load(); v=d.get(name, FLAGS.get(name,("1",))[0])
    on_=str(v).strip() not in ("0","false","off","no","")
    if on_ and name in("feat_browse","feat_shell","feat_devices") and not on("feat_agent"): return False
    return on_
def all_flags():
    d=_load()
    return [{"key":k,"on":on(k),"raw_on":str(d.get(k,v[0])).strip() not in("0","false","off","no",""),"bn":v[1],"en":v[2],"desc":v[3]} for k,v in FLAGS.items()]
def set_flag(name,value):
    if name not in FLAGS: raise ValueError("unknown flag")
    c=sqlite3.connect(DBF,timeout=10)
    try:
        prev=c.execute("select v from app_settings where k=?",(name,)).fetchone()
        c.execute("insert or replace into app_settings(k,v) values(?,?)",(name,"1" if value else "0")); c.commit()
    finally: c.close()
    _C["t"]=0
    return (prev[0] if prev else FLAGS[name][0])
def get_val(k,default=None):
    try:
        c=sqlite3.connect(DBF,timeout=5)
        try: r=c.execute("select v from app_settings where k=?",(k,)).fetchone()
        finally: c.close()
        return r[0] if r else default
    except Exception: return default
def set_val(k,v):
    if k in FLAGS: raise ValueError("use set_flag")
    c=sqlite3.connect(DBF,timeout=10)
    try:
        prev=c.execute("select v from app_settings where k=?",(k,)).fetchone()
        c.execute("insert or replace into app_settings(k,v) values(?,?)",(k,str(v))); c.commit()
    finally: c.close()
    return prev[0] if prev else None
class Off(Exception): pass
OFF_MSG={"feat_agent":"এজেন্ট টুলস এখন বন্ধ (অ্যাডমিন)","feat_browse":"ব্রাউজ টুল এখন বন্ধ (অ্যাডমিন)","feat_shell":"শেল টুল এখন বন্ধ (অ্যাডমিন)",
         "feat_devices":"ডিভাইস অ্যাকশন এখন বন্ধ (অ্যাডমিন)","feat_skill_catalog":"স্কিল ক্যাটালগ এখন বন্ধ (অ্যাডমিন)","feat_user_agents":"নিজস্ব এজেন্ট এখন বন্ধ (অ্যাডমিন)","feat_user_agent_tools":"এজেন্টের টুল এখন শুধু মালিকের জন্য (অ্যাডমিন)","signups_open":"নতুন সাইনআপ এখন বন্ধ — পরে চেষ্টা করুন। / New signups are closed right now."}
def need(name):
    if not on(name): raise RuntimeError(OFF_MSG.get(name,"এই ফিচার এখন বন্ধ"))
