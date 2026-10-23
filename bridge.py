"""AI Bridge: outside AIs (ChatGPT/Claude/Gemini/Grok/Meta AI) update app sections via secret links.
Flow: /ai/<section>/<token> -> markdown brief (code + rules + answer format) -> owner pastes answer at /admin/bridge
(or AI POSTs to /ai/<section>/<token>/propose) -> proposal (pending) -> preview (diff + live page preview)
-> owner Approve = one commit to main (Render auto-deploys) / Reject. Rollback = one tap, new commit restoring files.
Tokens = HMAC(BB_EDGE_SECRET, section+version) - nothing stored in git. Additive module; uses devagent's GitHub helpers."""
import os, re, json, time, hmac, hashlib, secrets, difflib, html, py_compile, tempfile
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response, RedirectResponse
import persist, devagent as DA
BASE = os.path.dirname(os.path.abspath(__file__)); DOM = "https://banglabhai.dpdns.org"
VER = os.environ.get("BB_BRIDGE_VER", "v1")  # change to rotate every link
H = {}
# name: (Bengali title, what it does, files, mode)  mode full = full-file answers allowed; edit = SEARCH/REPLACE only (big Python files)
SECTIONS = {
 "design":  ("ডিজাইন / থিম (রং, ফন্ট, অ্যানিমেশন)", "Global look & feel: colors, fonts, buttons, animations used by chat app, login pages and studio.", ["static/bb2.css", "static/viz.css", "static/studio.css"], "full"),
 "chat":    ("চ্যাট স্ক্রিন", "Main chat app at /app: message list, input box, sidebar, settings, uploads, voice. HTML+inline CSS in index.html, logic in bb2.js.", ["static/index.html", "static/bb2.js"], "full"),
 "landing": ("হোম / ল্যান্ডিং পেজ", "Public home page at / (marketing page, install button).", ["static/landing.html", "static/install.js"], "full"),
 "pages":   ("প্রাইসিং, প্রাইভেসি, শর্তাবলি, API ডক", "Static info pages: /pricing /privacy /terms /docs/api.", ["static/pricing.html", "static/privacy.html", "static/terms.html", "static/api.html"], "full"),
 "studio":  ("ছবি ও ভিডিও স্টুডিও (পেজ)", "Image/video studio page at /studio (front-end only).", ["static/studio.html", "static/studio.js"], "full"),
 "imagetools": ("ছবি/ভিডিও ইঞ্জিন (সার্ভার)", "Server code for free image/video models, photo edit, BYOK media keys (media.py).", ["media.py"], "edit"),
 "connections": ("কানেকশন পেজ", "Connections page (link Google, etc.) front-end.", ["static/connections.html", "static/connections.js", "static/connections.css"], "full"),
 "login":   ("লগইন / অ্যাডমিন লগইন পেজ", "Login, admin login, OTP, change-password pages: inline HTML f-strings + shared CSS string inside app.py.", ["app.py"], "edit"),
 "admin":   ("অ্যাডমিন প্যানেল", "Admin dashboard /admin/panel: plans, payments, users (biz.py).", ["biz.py", "plans.py"], "edit"),
 "language": ("ভাষা / অনুবাদ (বাংলা ও ইংরেজি লেখা)", "UI translation strings. bn.json = Bengali, en.json = English. Keep keys identical.", ["static/i18n/bn.json", "static/i18n/en.json", "static/i18n.js"], "full"),
 "extras":  ("শিডিউল, স্কিল, ছোট স্ক্রিপ্ট", "Schedules and skills front-end widgets, small helper scripts.", ["static/schedules.js", "static/skills.js", "static/px.js"], "full"),
}
PREVIEW_PAGE = {"chat": "static/index.html", "design": "static/index.html", "landing": "static/landing.html", "studio": "static/studio.html", "connections": "static/connections.html", "pages": "static/pricing.html", "language": "static/landing.html", "extras": "static/index.html"}
def _key(): return (persist._sec() or "").encode()
def token(sec): return hmac.new(_key(), f"aibridge:{VER}:{sec}".encode(), hashlib.sha256).hexdigest() + hmac.new(_key(), f"aibridge2:{VER}:{sec}".encode(), hashlib.sha256).hexdigest()[:16]
def tok_ok(sec, t): return bool(_key()) and isinstance(t, str) and hmac.compare_digest(t, token(sec))
def link(sec): return f"{DOM}/ai/{sec}/{token(sec)}"
RULES = """## RULES (must follow)
1. Keep the logo files and the brand: navy background (#0b1a33), royal blue accent (#1e6fd9), gold (#f4b400), clean minimal style. Do NOT change or remove logo.png / wordmark.svg.
2. User-facing text stays Bengali-first (Bengali UI). Keep i18n keys working; do not delete existing translation keys.
3. Photo edits must ALWAYS preserve the person's face and identity (never remove the face-preserve instruction).
4. Do not touch secrets, passwords, API keys, login security, payment logic, or add external tracking/scripts. No new external servers.
5. Do not remove existing features or routes. Change only what the owner asked. Keep mobile-first, fast, accessible.
6. Only edit the files listed below. If a change needs another file, say so in plain words instead of editing it."""
FMT_FULL = """## HOW TO ANSWER (exact format, the app parses it automatically)
Return ONLY changed files. For each changed file write the COMPLETE new file content (not a snippet), wrapped like this:

=== FILE: static/example.css ===
...complete new content of the file...
=== END FILE ===

You may also use small edits instead of full files:

=== EDIT: static/example.js ===
<<<<<<< SEARCH
exact existing lines copied from the current code
=======
new lines
>>>>>>> REPLACE
=== END EDIT ===

First line must be: SECTION: {sec}\nThen write 1-3 short lines in Bengali explaining what you changed (this is shown to the owner). Do not wrap the blocks in ``` code fences."""
FMT_EDIT = """## HOW TO ANSWER (exact format, the app parses it automatically)
These are large Python files: use ONLY small SEARCH/REPLACE edits (never the full file):

=== EDIT: app.py ===
<<<<<<< SEARCH
exact existing lines copied character-for-character from the current code (enough lines to be unique)
=======
new lines
>>>>>>> REPLACE
=== END EDIT ===

Several SEARCH/REPLACE pairs may go inside one EDIT block. First line must be: SECTION: {sec}\nThen write 1-3 short lines in Bengali explaining the change. Do not wrap the blocks in ``` code fences. Python must stay valid."""
def cur(p):
    try: return open(os.path.join(BASE, p), encoding="utf-8").read()
    except OSError: return ""
def excerpt_login(src):
    a = src.find('CSS="""'); b = src.find('@app.get("/manifest.webmanifest")')
    return src[a:b] if a >= 0 and b > a else src[:20000]
def brief(sec):
    t, what, files, mode = SECTIONS[sec]
    out = [f"# Bangla Bhai (বাংলা ভাই) app — section: {sec} ({t})", "", "You are helping the owner (Royel) improve ONE section of his live web app. App: FastAPI (Python) + plain HTML/CSS/JS, served at https://banglabhai.dpdns.org . Owner speaks Bengali; reply to him in simple Bengali.", "", f"## What this section does\n{what}", "", f"## Files in this section\n" + "\n".join(f"- {f}" for f in files), "", RULES, "", (FMT_FULL if mode == "full" else FMT_EDIT).replace("{sec}", sec), "", "Tell the owner: copy your WHOLE answer and paste it into the app page /admin/bridge (one big box), then tap Preview and Approve.", "", "## CURRENT CODE"]
    for f in files:
        s = cur(f)
        if sec == "login" and f == "app.py": s = excerpt_login(s); out.append(f"\n### {f} (login/admin-login part only; edit only text inside this part)")
        else: out.append(f"\n### {f}")
        out.append(f"<<<BEGIN {f}>>>\n{s}\n<<<END {f}>>>")
    out.append("\n## Owner's request\nThe owner will tell you what to change in the next message. Then answer in the exact format above.")
    return "\n".join(out)
def master_link(): return f"{DOM}/ai/{token('index')}"
def master():
    o = ["# Bangla Bhai (বাংলা ভাই) app — AI MASTER BRIEF", "", "You are helping the owner (Royel, speaks Bengali) change his live web app https://banglabhai.dpdns.org (FastAPI + plain HTML/CSS/JS).",
         "The app is split into sections. STEP 1: pick the section that matches the owner's request from the list below.",
         "STEP 2: open (web-fetch) that section's brief link. It contains the current code, the rules and the exact answer format.",
         "STEP 3: answer with a change bundle in that exact format (first line `SECTION: <name>`, then === FILE/EDIT === blocks). Reply to the owner in simple Bengali.",
         "STEP 4: tell the owner to copy your whole answer and paste it in the app at https://banglabhai.dpdns.org/admin/bridge , then Preview → Approve. Nothing goes live without his approval.",
         "If you cannot open links, ask the owner to paste the section brief text to you.", "", RULES, "", "## SECTIONS"]
    for k, v in SECTIONS.items(): o += [f"- {k} — {v[0]} — {v[1]}", f"  files: {', '.join(v[2])}", f"  brief: {link(k)}"]
    o += ["", "Connector API: POST the change bundle as text/plain to <brief link>/propose to submit it for owner approval."]
    return "\n".join(o)
# ---------- parsing / checks ----------
BLK = re.compile(r"===\s*(FILE|EDIT)\s*:\s*([^\s=]+)\s*===\s*\n(.*?)\n?===\s*END\s*(?:FILE|EDIT)\s*===", re.S)
SR = re.compile(r"<{5,}\s*SEARCH\s*\n(.*?)\n={5,}\s*\n(.*?)\n?>{5,}\s*REPLACE", re.S)
def parse(text, sec):
    """returns (note, {path: new_text}, errors)"""
    text = text.replace("\r\n", "\n"); files = SECTIONS[sec][2]; mode = SECTIONS[sec][3]
    text = re.sub(r"^```[a-zA-Z]*\s*$", "", text, flags=re.M)
    new, errs = {}, []
    blocks = list(BLK.finditer(text))
    note = (text[:blocks[0].start()] if blocks else text).strip()[:1500]
    if not blocks: errs.append("উত্তরে কোনো === FILE: ... === বা === EDIT: ... === ব্লক পাওয়া যায়নি।")
    for m in blocks:
        kind, p, body = m.group(1).upper(), m.group(2).strip().lstrip("./"), m.group(3)
        if p not in files: errs.append(f"{p}: এই ফাইল এই সেকশনের না — বাদ দেওয়া হলো।"); continue
        if kind == "FILE":
            if mode != "full": errs.append(f"{p}: এই সেকশনে শুধু EDIT চলে (পুরো ফাইল না)।"); continue
            new[p] = body.rstrip("\n") + "\n"
        else:
            src = new.get(p, cur(p)); pairs = SR.findall(body)
            if not pairs: errs.append(f"{p}: SEARCH/REPLACE পাওয়া যায়নি।"); continue
            for a, b in pairs:
                if src.count(a) != 1: errs.append(f"{p}: SEARCH অংশ কোডে {'পাওয়া যায়নি' if src.count(a)==0 else 'একাধিকবার আছে'}: {a[:80]!r}"); break
                src = src.replace(a, b, 1)
            else: new[p] = src
    new = {p: v for p, v in new.items() if v != cur(p)}
    return note, new, errs
BAD = re.compile(r"\.secrets|BB_SECRETS|BB_EDGE_SECRET|_sec\(\)|RENDER_API_KEY|GH_DEVAGENT_TOKEN|subprocess|os\.system|\beval\(|\bexec\(|webhook\.site|ngrok|pastebin|requestbin|__import__", re.I)
def check(new):
    errs = []
    for p, t in new.items():
        old = cur(p)
        added = "\n".join(l[1:] for l in difflib.unified_diff(old.splitlines(), t.splitlines(), lineterm="") if l.startswith("+") and not l.startswith("+++"))
        if BAD.search(added): errs.append(f"{p}: নিরাপত্তার কারণে আটকানো হলো (সিক্রেট/সিস্টেম কমান্ড ছোঁয়ার চেষ্টা)।")
        if len(t) > 400_000: errs.append(f"{p}: ফাইল খুব বড়।")
        if p.endswith((".png", ".svg")) or "logo" in p: errs.append(f"{p}: লোগো বদলানো যাবে না।")
        if p.endswith(".py"):
            fd, tmp = tempfile.mkstemp(suffix=".py"); os.write(fd, t.encode()); os.close(fd)
            try: py_compile.compile(tmp, doraise=True)
            except py_compile.PyCompileError as e: errs.append(f"{p}: Python কোডে ভুল — {str(e)[-200:]}")
            finally: os.unlink(tmp)
        if p.endswith(".json"):
            try: json.loads(t)
            except Exception as e: errs.append(f"{p}: JSON ভুল — {e}")
        if p.endswith(".html") and len(old) > 2000 and len(t) < len(old) * 0.3: errs.append(f"{p}: নতুন ফাইল আগের চেয়ে অনেক ছোট — সম্ভবত অসম্পূর্ণ উত্তর।")
    return errs
# ---------- storage ----------
def _db():
    c = H["db"](); c.execute("create table if not exists bridge_props(id text primary key,created real,sec text,src text,status text,data text)"); return c
def pput(pid, sec, src, status, data, created=None):
    with _db() as c: c.execute("insert or replace into bridge_props values(?,?,?,?,?,?)", (pid, created or time.time(), sec, src, status, json.dumps(data, ensure_ascii=False)))
def pget(pid):
    with _db() as c: r = c.execute("select * from bridge_props where id=?", (pid,)).fetchone()
    return dict(r, data=json.loads(r["data"])) if r else None
def plist(n=40):
    with _db() as c: return [dict(r, data=json.loads(r["data"])) for r in c.execute("select * from bridge_props order by created desc limit ?", (n,))]
def detect(text):
    ps = {m.group(2).strip().lstrip("./") for m in BLK.finditer(text.replace("\r\n", "\n"))}
    m = re.search(r"SECTION\s*:\s*([a-z]+)", text)
    if m and m.group(1) in SECTIONS and ps <= set(SECTIONS[m.group(1)][2]): return m.group(1)
    for k, v in SECTIONS.items():
        if ps and ps <= set(v[2]): return k
    for k, v in SECTIONS.items():
        if ps & set(v[2]): return k
    return None
def propose(sec, text, src):
    if sec in ("", "auto", None): sec = detect(text) or "design"
    note, new, errs = parse(text, sec)
    errs += check(new)
    if not new and not errs: errs.append("কোনো পরিবর্তন পাওয়া যায়নি (নতুন কোড আগের মতোই)।")
    pid = time.strftime("%m%d%H%M") + "-" + secrets.token_hex(3)
    st = "pending" if new and not any("আটকানো" in e or "ভুল" in e or "অসম্পূর্ণ" in e for e in errs) else "invalid"
    pput(pid, sec, src, st, {"note": note, "files": new, "errors": errs, "raw": text[:200000]})
    try:
        if st == "pending": H["notify"](H["owner"], "🤖 নতুন AI প্রস্তাব", f"{SECTIONS[sec][0]} — দেখে Approve করুন", "/admin/bridge")
    except Exception: pass
    return pid, st, errs
# ---------- integration agent (free models via Dev Agent's LLM chain) ----------
AGSYS = """You are the Integration Agent for the Bangla Bhai web app (FastAPI + HTML/CSS/JS). The owner pastes code or an AI answer that may be messy, partial, or in any format.
Your job: understand what change it intends and MERGE it into the CURRENT files with minimal exact search/replace edits (never blind overwrite, never delete unrelated code). Fix obvious syntax errors. Keep logo, navy/royal-blue/gold style, Bengali UI, face-preserve rule for photo edits. Never touch secrets, auth security, payments, system commands or add external tracking.
If the paste is unsafe, meaningless, or cannot be merged safely, return edits:[] and explain why in simple Bengali."""
async def agent_section(text):
    lst = "\n".join(f"{k}: {v[0]} | files: {', '.join(v[2])} | {v[1]}" for k, v in SECTIONS.items())
    _, j = await DA.llm(H["owner"], "auto", [{"role": "system", "content": AGSYS}, {"role": "user", "content": f"Sections:\n{lst}\n\nPasted text (start):\n{text[:6000]}\n\nReturn JSON {{\"section\":\"<one section key>\"}}"}])
    k = (j.get("section") or "").strip()
    return k if k in SECTIONS else None
async def agent_merge(sec, text, prev_errs=None):
    files = {p: cur(p) for p in SECTIONS[sec][2]}
    if sec == "login": files["app.py"] = excerpt_login(files["app.py"])
    budget = 70000 // max(1, len(files))
    ctx = "\n\n".join(f"=== CURRENT {p} ===\n{t[:budget]}" for p, t in files.items())
    fb = ("\n\nYour previous attempt failed checks: " + "; ".join(prev_errs)[:1500] + "\nFix it.") if prev_errs else ""
    _, j = await DA.llm(H["owner"], "auto", [{"role": "system", "content": AGSYS}, {"role": "user", "content": f"{ctx}\n\n=== PASTED BY OWNER ===\n{text[:40000]}{fb}\n\nReturn JSON {{\"summary_bn\":\"2-4 short Bengali lines: what will change, or why it cannot be applied\",\"safe\":true,\"edits\":[{{\"path\":\"file\",\"search\":\"exact existing text (unique)\",\"replace\":\"new text\"}}]}}"}])
    new, errs = {}, []
    if j.get("safe") is False: return j.get("summary_bn", ""), {}, ["AI এজেন্ট বলছে এটা নিরাপদ না: " + (j.get("summary_bn") or "")[:300]]
    for e in j.get("edits") or []:
        p, a, b = (e.get("path") or "").lstrip("./"), e.get("search") or "", e.get("replace") or ""
        if p not in files: errs.append(f"{p}: এই সেকশনের ফাইল না"); continue
        src = new.get(p, cur(p))
        if src.count(a) != 1: errs.append(f"{p}: মেলানো যায়নি ({src.count(a)} বার পাওয়া গেছে)"); continue
        new[p] = src.replace(a, b, 1)
    return (j.get("summary_bn") or "")[:1500], {p: v for p, v in new.items() if v != cur(p)}, errs
BLOCKING = ("আটকানো", "ভুল", "অসম্পূর্ণ", "নিরাপদ না")
async def smart(pid, sec, text):
    """Run in background: strict parse first, else integration agent (2 attempts)."""
    pr = pget(pid); d = pr["data"]
    try:
        if sec in ("", "auto"):
            sec = detect(text) or await agent_section(text) or "design"
        note, new, errs = parse(text, sec); errs += check(new)
        if new and not errs: st = "pending"; how = "সরাসরি"
        else:
            how = "AI এজেন্ট"; errs2 = None
            for _ in range(2):
                note, new, e2 = await agent_merge(sec, text, errs2)
                e2 += check(new)
                if new and not any(x in y for y in e2 for x in BLOCKING) and not e2: break
                errs2 = e2 or ["no edits"]
            errs = e2
            if not new and not errs: errs = ["কোনো পরিবর্তন বের করা যায়নি।"]
            st = "pending" if new and not any(x in y for y in errs for x in BLOCKING) else "invalid"
        d.update(note=note, files=new, errors=errs, how=how)
        pput(pid, sec, pr["src"], st, d, pr["created"])
        if st == "pending":
            try: H["notify"](H["owner"], "🤖 নতুন AI প্রস্তাব", f"{SECTIONS[sec][0]} — দেখে Approve করুন", "/admin/bridge")
            except Exception: pass
    except Exception as e:
        d.update(errors=["এজেন্ট কাজ করতে পারেনি: " + str(e)[:200]]); pput(pid, sec if sec in SECTIONS else "design", pr["src"], "invalid", d, pr["created"])
def start_smart(sec, text, src):
    import asyncio
    pid = time.strftime("%m%d%H%M") + "-" + secrets.token_hex(3)
    pput(pid, sec if sec in SECTIONS else "design", src, "working", {"note": "", "files": {}, "errors": [], "raw": text[:200000]})
    asyncio.get_running_loop().create_task(smart(pid, sec, text)); return pid
def diff_html(new):
    out = []
    for p, t in new.items():
        d = list(difflib.unified_diff(cur(p).splitlines(), t.splitlines(), f"আগে: {p}", f"পরে: {p}", lineterm="", n=2))
        rows = []
        for l in d[:1500]:
            c = "a" if l.startswith("+") else "d" if l.startswith("-") else "h" if l.startswith("@@") else ""
            rows.append(f'<div class="{c}">{html.escape(l)}</div>')
        out.append(f"<h4>{html.escape(p)}</h4><div class=diff>{''.join(rows) or '(কোনো পার্থক্য নেই)'}</div>")
    return "".join(out)
# ---------- GitHub commit / rollback ----------
async def commit_main(files, msg):
    ref = await DA.gh("GET", "/git/ref/heads/main"); head = ref["object"]["sha"]
    base = await DA.gh("GET", f"/git/commits/{head}"); items = []
    for p, txt in files.items():
        b = await DA.gh("POST", "/git/blobs", json={"content": txt, "encoding": "utf-8"})
        items.append({"path": p, "mode": "100644", "type": "blob", "sha": b["sha"]})
    t = await DA.gh("POST", "/git/trees", json={"base_tree": base["tree"]["sha"], "tree": items})
    c = await DA.gh("POST", "/git/commits", json={"message": msg, "tree": t["sha"], "parents": [head]})
    await DA.gh("PATCH", "/git/refs/heads/main", json={"sha": c["sha"], "force": False})
    return c["sha"], head
async def approve(pid):
    pr = pget(pid)
    if not pr or pr["status"] != "pending": raise ValueError("এই প্রস্তাব এখন Approve করা যাবে না")
    d = pr["data"]; old = {}
    for p in d["files"]: old[p] = await DA.read(p, "main")
    stale = [p for p in d["files"] if old[p] is not None and old[p] != cur(p)]
    if stale: raise ValueError("লাইভ কোড এর মধ্যে বদলে গেছে (" + ", ".join(stale) + ")। নতুন লিংক থেকে আবার ব্রিফ নিন।")
    sha, parent = await commit_main(d["files"], f"[ai-bridge] {pr['sec']}: {pid}\n\n{d.get('note','')[:500]}")
    d.update(sha=sha, parent=parent, approved=time.time()); pput(pid, pr["sec"], pr["src"], "live", d, pr["created"])
    H["audit"](ev="bridge_approve", pid=pid, sha=sha[:7]); return sha
async def rollback(pid):
    pr = pget(pid)
    if not pr or pr["status"] != "live": raise ValueError("শুধু লাইভ হওয়া পরিবর্তন ফেরত নেওয়া যায়")
    d = pr["data"]; restore = {}
    for p in d["files"]:
        o = await DA.read(p, d["parent"])
        if o is not None: restore[p] = o
    sha, _ = await commit_main(restore, f"[ai-bridge] rollback {pr['sec']}: {pid}")
    d.update(rollback_sha=sha, rolled=time.time()); pput(pid, pr["sec"], pr["src"], "rolled_back", d, pr["created"])
    H["audit"](ev="bridge_rollback", pid=pid, sha=sha[:7]); return sha
# ---------- UI ----------
CSS = """<meta name=viewport content="width=device-width,initial-scale=1"><meta name=robots content=noindex><style>
:root{--bg:#0b1a33;--p:#122442;--t:#eef2f8;--m:#8b98b0;--a:#1e6fd9;--g:#f4b400;--b:#243a5c}
body{margin:0;background:var(--bg);color:var(--t);font-family:'Hind Siliguri','Noto Sans Bengali',system-ui,sans-serif;font-size:16px}
.w{max-width:760px;margin:0 auto;padding:14px}h2{color:var(--g);margin:6px 0 12px}h3{margin:18px 0 8px}
.c{background:var(--p);border:1px solid var(--b);border-radius:14px;padding:14px;margin:10px 0}
.btn,button{display:inline-block;padding:12px 16px;border-radius:10px;border:0;background:var(--a);color:#fff;font-size:16px;font-family:inherit;text-decoration:none;margin:4px 4px 4px 0;cursor:pointer}
.gold{background:var(--g);color:#0b1a33}.red{background:#d62839}.gray{background:#33476b}
select,textarea{width:100%;box-sizing:border-box;background:#0b1a33;color:var(--t);border:1px solid var(--b);border-radius:10px;padding:12px;font-size:15px;font-family:inherit}
textarea{min-height:220px}.m{color:var(--m);font-size:14px}.row{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}
.diff{font:12px/1.45 monospace;background:#071226;border-radius:8px;padding:8px;overflow-x:auto;white-space:pre;max-height:60vh;overflow-y:auto}
.diff .a{background:#0f3d24;color:#9dffbf}.diff .d{background:#4a1520;color:#ffb3bd}.diff .h{color:var(--g)}
.err{color:#ff8a98}.tag{font-size:12px;padding:3px 8px;border-radius:20px;background:#33476b}.live{background:#1d6b3a}.pending{background:#8a6a00}
a{color:#8fb0ff}</style>"""
ST = {"working": "⏳ এজেন্ট কাজ করছে", "pending": "অপেক্ষায়", "live": "লাইভ", "rejected": "বাতিল", "rolled_back": "ফেরত নেওয়া", "invalid": "ভুল উত্তর"}
def page(body, title="AI ব্রিজ"):
    return HTMLResponse(f"<!doctype html><html lang=bn><head><meta charset=utf-8><title>{title}</title>{CSS}</head><body><div class=w>{body}</div></body></html>", headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex", "Referrer-Policy": "no-referrer"})
def md_to_html(t):
    o = []
    for l in t.splitlines():
        e = html.escape(l); e = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", e); e = re.sub(r"`([^`]+)`", r"<code>\1</code>", e)
        if l.startswith("### "): o.append(f"<h4>{e[4:]}</h4>")
        elif l.startswith("## "): o.append(f"<h3>{e[3:]}</h3>")
        elif l.startswith("# "): o.append(f"<h2>{e[2:]}</h2>")
        elif l.startswith("> "): o.append(f"<div class=c>{e[5:]}</div>")
        elif l.strip() == "": o.append("<br>")
        else: o.append(f"<div>{e}</div>")
    return "".join(o)
def setup(app, HH):
    H.update(HH)
    def adm(request):
        if not H["is_admin"](request): raise PermissionError
    def csrf(request):
        t = request.session.get("csrf")
        if not t: t = secrets.token_urlsafe(24); request.session["csrf"] = t
        return t
    async def form_ok(request):
        f = await request.form()
        if not hmac.compare_digest(f.get("csrf", ""), request.session.get("csrf", "") or "x"): raise PermissionError
        return f
    def login_redirect(): return RedirectResponse("/admin?next=/admin/bridge", 303)
    # ----- public (token) API for outside AIs -----
    @app.get("/robots.txt")
    def robots():
        return PlainTextResponse("User-agent: *\nAllow: /ai/\nAllow: /$\nDisallow: /admin\nDisallow: /bb/api/\n", headers={"Cache-Control": "public, max-age=3600"})
    @app.api_route("/ai/{sec}/{tok}", methods=["GET", "HEAD"])
    def ai_brief(sec: str, tok: str):
        if tok == "index.json" and tok_ok("index", sec): return JSONResponse({k: {"title": v[0], "about": v[1], "files": v[2], "brief": link(k)} for k, v in SECTIONS.items()})
        if sec not in SECTIONS or not tok_ok(sec, tok): return PlainTextResponse("not found", 404)
        return PlainTextResponse(brief(sec), headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})
    @app.api_route("/ai/{tok}", methods=["GET", "HEAD"])
    def ai_master(tok: str):
        if not tok_ok("index", tok): return PlainTextResponse("not found", 404)
        return PlainTextResponse(master(), headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})
    @app.post("/ai/{sec}/{tok}/propose")
    async def ai_propose(request: Request, sec: str, tok: str):
        if sec not in SECTIONS or not tok_ok(sec, tok): return PlainTextResponse("not found", 404)
        if not H["rate_ok"]("bridge:" + sec, 30, 3600): return JSONResponse({"error": "rate limit"}, 429)
        b = (await request.body())[:400_000].decode("utf-8", "replace")
        if request.headers.get("content-type", "").startswith("application/json"):
            try: b = json.loads(b).get("answer", "")
            except Exception: pass
        pid = start_smart(sec, b, "api")
        return {"proposal": pid, "status": "working", "note": "Owner must approve in the app (/admin/bridge). Nothing is live yet."}
    # ----- owner pages -----
    @app.get("/admin/bridge")
    def home(request: Request, sec: str = ""):
        try: adm(request)
        except PermissionError: return login_redirect()
        c = csrf(request)
        opts = "<option value=auto selected>🔎 নিজে বুঝে নিক (অটো)</option>" + "".join(f"<option value={k}>{v[0]}</option>" for k, v in SECTIONS.items())
        links = "".join(f"<div class=c><div class=row><b>{v[0]}</b><span class=m>{k}</span></div><div class=m>{html.escape(', '.join(v[2]))}</div><button class=gold onclick=\"cpAll('{k}',this)\">📄 সব কপি করুন</button><a class='btn gray' href=/admin/bridge/brief/{k}.txt?dl=1>⬇️ .txt</a><button class=gray onclick=\"cp('{link(k)}',this)\">🔗 লিংক কপি</button><a class='btn gray' href=/admin/bridge?sec={k}#paste>উত্তর পেস্ট</a></div>" for k, v in SECTIONS.items())
        rows = "".join(f"<div class=c><div class=row><a href=/admin/bridge/p/{p['id']}><b>{SECTIONS.get(p['sec'],('?',))[0]}</b></a><span class='tag {p['status']}'>{ST.get(p['status'],p['status'])}</span></div><div class=m>{time.strftime('%d %b %H:%M', time.localtime(p['created']))} · {html.escape((p['data'].get('note') or '')[:90])}</div></div>" for p in plist())
        body = f"""<div class=row><h2>🤖 AI ব্রিজ</h2><a href=/admin/bridge/guide class='btn gold'>📖 গাইড</a></div>
<p class=m>বাইরের AI (ChatGPT, Claude, Gemini, Grok, Meta AI) দিয়ে অ্যাপের যেকোনো অংশ বদলান। আপনার Approve ছাড়া কিছুই লাইভ হয় না।</p>
<div class=c><b>⭐ মাস্টার লিংক (একটাই লিংক — যেকোনো AI-কে দিন)</b><br><button class=gold onclick="cp('{master_link()}',this)">📋 মাস্টার লিংক কপি</button><button class=gray onclick="cpAll('master',this)">📄 সব কপি করুন</button><br><span class=m>Gemini বা যে AI লিংক খুলতে পারে না: নিচে যে অংশ বদলাতে চান তার "📄 সব কপি করুন" চাপুন, AI-তে পেস্ট করে নির্দেশ দিন।</span></div>
<h3 id=paste>② AI-এর উত্তর এখানে পেস্ট করুন</h3><form class=c method=post action=/admin/bridge/submit><input type=hidden name=csrf value={c}>
<select name=sec>{opts}</select><p></p><textarea name=answer placeholder="AI-এর উত্তর বা যেকোনো কোড — যেমন আছে তেমন পেস্ট করুন। এজেন্ট নিজেই বুঝে ঠিক জায়গায় বসাবে।"></textarea><button class=gold>👀 প্রিভিউ দেখুন</button></form>
<h3>③ প্রস্তাব ও ইতিহাস</h3>{rows or '<p class=m>এখনো কিছু নেই</p>'}
<h3>① সেকশন লিংক (AI-কে দেওয়ার জন্য)</h3><p class=m>লিংকগুলো গোপন — শুধু AI-কে দেবেন, অন্য কাউকে না।</p>{links}
<p><a href=/admin/panel>← অ্যাডমিন প্যানেল</a></p>
<div id=fb style=display:none class=c><b>নিচের লেখা সব সিলেক্ট করে কপি করুন:</b><textarea id=fbt readonly></textarea></div>
<script>function cpAll(k,b){{const u='/admin/bridge/brief/'+k+'.txt';const p=fetch(u,{{credentials:'same-origin'}}).then(r=>{{if(!r.ok)throw 0;return r.text()}});
const ok=()=>{{b.textContent='✅ কপি হয়েছে — এখন AI-তে পেস্ট করুন'}};const fail=()=>p.then(t=>{{const f=document.getElementById('fb'),x=document.getElementById('fbt');f.style.display='block';x.value=t;x.focus();x.select();f.scrollIntoView()}});
try{{if(window.ClipboardItem&&navigator.clipboard.write){{navigator.clipboard.write([new ClipboardItem({{'text/plain':p.then(t=>new Blob([t],{{type:'text/plain'}}))}})]).then(ok).catch(()=>p.then(t=>navigator.clipboard.writeText(t)).then(ok).catch(fail))}}else{{p.then(t=>navigator.clipboard.writeText(t)).then(ok).catch(fail)}}}}catch(e){{fail()}}}}
function cp(t,b){{(navigator.clipboard?navigator.clipboard.writeText(t):Promise.reject()).then(()=>{{b.textContent='✅ কপি হয়েছে'}}).catch(()=>{{prompt('কপি করুন:',t)}})}}</script>"""
        return page(body)
    @app.post("/admin/bridge/submit")
    async def submit(request: Request):
        try: adm(request); f = await form_ok(request)
        except PermissionError: return login_redirect()
        sec = f.get("sec", "")
        if sec not in SECTIONS and sec != "auto": return RedirectResponse("/admin/bridge", 303)
        pid = start_smart(sec, f.get("answer", ""), "paste")
        return RedirectResponse(f"/admin/bridge/p/{pid}", 303)
    @app.get("/admin/bridge/p/{pid}")
    def view(request: Request, pid: str):
        try: adm(request)
        except PermissionError: return login_redirect()
        pr = pget(pid)
        if not pr: return page("<p>পাওয়া যায়নি</p><a href=/admin/bridge>← ফিরে যান</a>")
        d = pr["data"]; c = csrf(request); s = pr["status"]
        errs = "".join(f"<div class=err>⚠️ {html.escape(e)}</div>" for e in d.get("errors", []))
        btn = lambda a, lbl, cl, q="": f"<form method=post action=/admin/bridge/p/{pid}/{a} style=display:inline onsubmit=\"return confirm('{q or lbl}?')\"><input type=hidden name=csrf value={c}><button class='{cl}'>{lbl}</button></form>"
        acts = ""
        if s == "pending":
            pv = f"<a class='btn gray' target=_blank href=/admin/bridge/p/{pid}/preview>📱 পেজ প্রিভিউ</a>" if pr["sec"] in PREVIEW_PAGE else ""
            acts = pv + btn("approve", "✅ Approve (লাইভ করুন)", "gold", "লাইভ করবেন") + btn("reject", "❌ Reject", "red")
        elif s == "live": acts = btn("rollback", "↩️ আগের অবস্থায় ফেরত নিন", "red", "আগের অবস্থায় ফেরত নেবেন") + f"<div class=m>কমিট {d.get('sha','')[:7]} · লাইভ হতে ২-৪ মিনিট লাগে</div>"
        elif s == "rolled_back": acts = f"<div class=m>ফেরত নেওয়া হয়েছে (কমিট {d.get('rollback_sha','')[:7]})</div>"
        msg = html.escape(request.query_params.get("m", ""))
        if s == "working": return page(f"<meta http-equiv=refresh content=4><a href=/admin/bridge>← AI ব্রিজ</a><h2>⏳ এজেন্ট কাজ করছে…</h2><p class=m>আপনার পেস্ট করা কোড বুঝে ঠিক জায়গায় বসানো হচ্ছে আর পরীক্ষা করা হচ্ছে। ১৫-৯০ সেকেন্ড লাগতে পারে। পেজ নিজে থেকেই রিফ্রেশ হবে।</p>")
        body = f"""<a href=/admin/bridge>← AI ব্রিজ</a><h2>{SECTIONS.get(pr['sec'],('?',))[0]}</h2>
<div class=row><span class='tag {s}'>{ST.get(s,s)}</span><span class=m>{pid} · {'API' if pr['src']=='api' else 'পেস্ট'}</span></div>
{f'<div class=c>{msg}</div>' if msg else ''}<div class=c><b>সারসংক্ষেপ ({html.escape(d.get('how','সরাসরি'))}):</b><div>{html.escape(d.get('note') or '—').replace(chr(10),'<br>')}</div></div>{errs}
<div class=c>{acts}<a class='btn gray' href=/admin/bridge>পরে দেখব</a></div>
<h3>কী কী বদলাবে (সবুজ = নতুন, লাল = বাদ)</h3>{diff_html(d.get('files', {})) if s in ('pending','invalid') else '<p class=m>'+', '.join(d.get('files', {}))+'</p>'}"""
        return page(body)
    @app.get("/admin/bridge/p/{pid}/preview")
    def preview(request: Request, pid: str):
        try: adm(request)
        except PermissionError: return login_redirect()
        pr = pget(pid)
        if not pr or pr["sec"] not in PREVIEW_PAGE: return PlainTextResponse("no preview", 404)
        files = pr["data"].get("files", {}); main = PREVIEW_PAGE[pr["sec"]]
        if pr["sec"] == "pages": main = next((p for p in files if p.endswith(".html")), main)
        h = files.get(main, cur(main))
        for p in files:
            if p.startswith("static/") and p != main: h = h.replace("/bb/static/" + p[7:], f"/admin/bridge/p/{pid}/s/{p[7:]}")
        bar = "<div style='position:fixed;bottom:0;left:0;right:0;z-index:99999;background:#f4b400;color:#0b1a33;text-align:center;padding:6px;font:14px sans-serif'>👀 প্রিভিউ — এখনো লাইভ না</div>"
        h = h.replace("</body>", bar + "</body>", 1) if "</body>" in h else h + bar
        return HTMLResponse(h, headers={"Cache-Control": "no-store"})
    @app.get("/admin/bridge/p/{pid}/s/{path:path}")
    def pstatic(request: Request, pid: str, path: str):
        try: adm(request)
        except PermissionError: return PlainTextResponse("no", 403)
        pr = pget(pid); t = (pr or {}).get("data", {}).get("files", {}).get("static/" + path)
        if t is None: return PlainTextResponse("nf", 404)
        mt = {"css": "text/css", "js": "application/javascript", "json": "application/json", "html": "text/html"}.get(path.rsplit(".", 1)[-1], "text/plain")
        return Response(t, media_type=mt, headers={"Cache-Control": "no-store"})
    @app.post("/admin/bridge/p/{pid}/{act}")
    async def act(request: Request, pid: str, act: str):
        try: adm(request); await form_ok(request)
        except PermissionError: return login_redirect()
        try:
            if act == "approve": await approve(pid); m = "✅ লাইভ করা হচ্ছে। ২-৪ মিনিট পর অ্যাপ রিফ্রেশ করুন।"
            elif act == "rollback": await rollback(pid); m = "↩️ আগের অবস্থায় ফেরত নেওয়া হচ্ছে। ২-৪ মিনিট লাগবে।"
            elif act == "reject":
                pr = pget(pid)
                if pr and pr["status"] in ("pending", "invalid"): pput(pid, pr["sec"], pr["src"], "rejected", pr["data"], pr["created"])
                m = "বাতিল করা হলো।"
            else: m = "?"
        except Exception as e: m = "⚠️ " + str(e)[:300]
        from urllib.parse import quote
        return RedirectResponse(f"/admin/bridge/p/{pid}?m=" + quote(m), 303)
    @app.get("/admin/bridge/brief/{sec}.txt")
    def brief_txt(request: Request, sec: str, dl: int = 0):
        try: adm(request)
        except PermissionError: return PlainTextResponse("login", 403)
        if sec not in SECTIONS and sec != "master": return PlainTextResponse("nf", 404)
        t = master() if sec == "master" else brief(sec)
        hd = {"Cache-Control": "no-store"}
        if dl: hd["Content-Disposition"] = f'attachment; filename="bangla-bhai-{sec}.txt"'
        return PlainTextResponse(t, headers=hd)
    @app.get("/admin/bridge/guide")
    def guide(request: Request):
        try: adm(request)
        except PermissionError: return login_redirect()
        return page("<a href=/admin/bridge>← AI ব্রিজ</a>" + md_to_html(cur("static/ai_bridge_guide.md") or "গাইড পাওয়া যায়নি"), "গাইড")
