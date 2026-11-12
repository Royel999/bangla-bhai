"""P1 foundation: supervised browser agent (flag feat_browser_agent, default OFF). 2026-11-12.

Why not hand the task to browser-use 1.0 directly?  browser-use 1.0.x (MIT, PyPI 1.0.2 on 2026-11-11) lets the
LLM write Python in ONE persistent REPL on raw CDP. Its own docs say the domain guard is "a guard for an aligned
model, not a sandbox: subresources are not filtered, and the REPL's own Python networking is not the browser".
Its defaults are also the paid Browser Use cloud browser + bu-fast gateway model (BROWSER_USE_API_KEY) and
telemetry ON. A REPL step cannot be shown to Sentinel as one click/type, so it cannot be our live path.

So the agent loop (agent.py) drives THIS module one explicit step at a time, and every step is a normal agent tool:
  browser_navigate {url}                    tier act      -> Sentinel pre_call (card when the task is tainted)
  browser_read     {}                       tier read     -> page text (UNTRUSTED, fenced/quarantined)
  browser_act      {action,selector,text}   tier control  -> ALWAYS an Approve card (gated tier, audited)
  browser_close    {}                       tier read
Guards (all on, not configurable off):
  * flag feat_browser_agent must be ON (default OFF) - FL.need() on every call.
  * domain allowlist (app_settings 'browser_agent_allow' or env BB_BROWSER_AGENT_ALLOW, comma list).
    Default EMPTY = deny every site. Patterns: 'example.com' (+www), '*.example.com' (+subdomains), 'sub.example.com'.
    Applied to the requested URL, every document (main/sub frame) request, and the final URL after redirects.
  * every other request (images, scripts, XHR) must still be public (agent._url_ok: no localhost/private IPs).
  * a SEPARATE Chromium profile on the box (~/.bb_browser_agent/profile), never the owner's desktop Chrome.
  * a screenshot after EVERY step (static/shots/ba_*.png) returned to the UI and kept in the step log.
browser_use_config() builds the matching browser-use 1.0 Browser(...) kwargs (local chromium, same profile dir,
same allowlist, headless) for a later, separately-approved autonomous mode; it is NOT executed anywhere."""
import os, re, time, uuid
from urllib.parse import urlsplit
FLAG="feat_browser_agent"
ALLOW_KEY="browser_agent_allow"
PROFILE=os.environ.get("BB_BROWSER_AGENT_PROFILE") or os.path.expanduser("~/.bb_browser_agent/profile")
BASE=os.path.expanduser("~/bangla_bhai")
SHOTS=os.path.join(BASE,"static","shots")
MAX_STEPS=40           # per session, on top of Sentinel's per-task action budget
NAV_TIMEOUT=30000
# beta: navigate AND act always show an Approve card (agent.py force_card), even before the task is tainted
ALWAYS_CARD=frozenset({"browser_navigate","browser_act"})
ACTIONS=("click","type","press","select","scroll","check")
TOOLS={
 "browser_navigate":("browser","ব্রাউজার এজেন্ট: অনুমোদিত (allowlist) সাইটে যাওয়া, প্রতি ধাপে স্ক্রিনশট",{"url":"str"}),
 "browser_read":("browser","ব্রাউজার এজেন্ট: বর্তমান পেজের লেখা ও স্ক্রিনশট",{}),
 "browser_act":("browser","ব্রাউজার এজেন্ট: ক্লিক/লেখা/বোতাম (প্রতিবার অনুমতি কার্ড)",{"action":"click|type|press|select|scroll|check","selector":"css বা text=...","text":"str"}),
 "browser_close":("browser","ব্রাউজার এজেন্ট বন্ধ",{}),
}
# ---------- flag / config ----------
def enabled():
    try:
        import flags as FL; return FL.on(FLAG)
    except Exception: return False      # fail closed
def need():
    if not enabled(): raise RuntimeError("ব্রাউজার এজেন্ট এখন বন্ধ (অ্যাডমিন ফ্ল্যাগ feat_browser_agent)")
def allowlist():
    raw=os.environ.get("BB_BROWSER_AGENT_ALLOW")
    if raw is None:
        try:
            import flags as FL; raw=FL.get_val(ALLOW_KEY,"") or ""
        except Exception: raw=""
    out=[]
    for p in re.split(r"[,\s]+",str(raw)):
        p=p.strip().lower().rstrip(".")
        if not p: continue
        if p in("*","*.*") or "/" in p or ":" in p: continue        # never allow wildcard-all, schemes, paths or ports
        if not re.fullmatch(r"(\*\.)?[a-z0-9-]+(\.[a-z0-9-]+)+",p): continue
        out.append(p)
    return out
def _host(u):
    try: s=urlsplit(str(u).strip())
    except Exception: return None
    if s.scheme not in("http","https") or not s.hostname: return None
    if s.username or s.password: return None          # https://ok.com@evil.com tricks
    h=s.hostname.lower().rstrip(".")
    try: h=h.encode("idna").decode("ascii")
    except Exception: return None
    return h
def host_allowed(host,patterns):
    if not host: return False
    for p in patterns:
        if p.startswith("*."):
            base=p[2:]
            if host==base or host.endswith("."+base): return True
        elif host==p: return True
        elif p.count(".")==1 and host=="www."+p: return True
    return False
def url_allowed(u,patterns=None):
    """True only for http(s) URLs whose host is on the allowlist AND is public (agent._url_ok)."""
    pats=allowlist() if patterns is None else patterns
    h=_host(u)
    if not host_allowed(h,pats): return False
    try:
        import agent as AG; return AG._url_ok(u)
    except Exception: return False
def policy_for(tool):
    """Tier each new tool should have in sentinel_policy.json (tests keep the two in sync)."""
    return {"browser_navigate":"act","browser_read":"read","browser_act":"control","browser_close":"read"}.get(tool)
# ---------- session (one per task) ----------
_S={}   # task id -> {"ctx","page","steps":[...],"n":int,"t":float}
async def _launch():
    from playwright.async_api import async_playwright
    os.makedirs(PROFILE,exist_ok=True)
    pw=await async_playwright().start()
    kw=dict(user_data_dir=PROFILE,headless=True,viewport={"width":1200,"height":800},accept_downloads=False,
            args=["--no-first-run","--no-default-browser-check","--disable-sync"])
    exe=os.environ.get("BB_BROWSER_AGENT_CHROME")
    if exe: kw["executable_path"]=exe
    try: ctx=await pw.chromium.launch_persistent_context(**kw)
    except Exception:
        if exe or not os.path.exists("/usr/bin/google-chrome"): await pw.stop(); raise
        kw["executable_path"]="/usr/bin/google-chrome"; ctx=await pw.chromium.launch_persistent_context(**kw)
    return pw,ctx
async def _guard(route):
    req=route.request
    ok=url_allowed(req.url) if req.resource_type=="document" else _public(req.url)
    if ok: await route.continue_()
    else: await route.abort()
def _public(u):
    if str(u).startswith(("data:","blob:")): return True
    try:
        import agent as AG; return AG._url_ok(u)
    except Exception: return False
async def session(tid):
    s=_S.get(tid)
    if s: return s
    pw,ctx=await _launch()
    await ctx.route("**/*",_guard)
    page=ctx.pages[0] if ctx.pages else await ctx.new_page()
    s=_S[tid]={"pw":pw,"ctx":ctx,"page":page,"steps":[],"n":0,"t":time.time()}
    return s
async def _shot(s,tid,label):
    os.makedirs(SHOTS,exist_ok=True)
    fn=f"ba_{re.sub(r'[^a-zA-Z0-9]','',str(tid))[:12]}_{s['n']:02d}_{uuid.uuid4().hex[:6]}.png"
    await s["page"].screenshot(path=os.path.join(SHOTS,fn))
    url="/bb/static/shots/"+fn
    s["steps"].append({"n":s["n"],"t":time.time(),"step":label,"url":s["page"].url,"shot":url})
    return url
async def _text(page,limit=3500):
    try: t=await page.inner_text("body")
    except Exception: t=""
    return f"শিরোনাম: {await page.title()}\nURL: {page.url}\n{t[:limit]}"
async def close(tid):
    s=_S.pop(tid,None)
    if not s: return
    try: await s["ctx"].close()
    finally:
        try: await s["pw"].stop()
        except Exception: pass
async def run(tid,name,a):
    """Entry point from agent.run_tool. Sentinel has ALREADY decided (pre_call + card) before this runs."""
    need()
    a=a or {}
    if name=="browser_close": await close(tid); return "ব্রাউজার এজেন্ট বন্ধ হয়েছে"
    if name=="browser_navigate":
        u=str(a.get("url","")).strip()
        if not url_allowed(u): raise RuntimeError("এই সাইট অনুমোদিত তালিকায় নেই (browser_agent_allow) — মালিককে যোগ করতে বলো")
    if name=="browser_act":
        act=str(a.get("action","")).lower()
        if act not in ACTIONS: raise RuntimeError("action হতে হবে: "+"|".join(ACTIONS))
    if name not in TOOLS: raise RuntimeError("অজানা ব্রাউজার টুল")
    s=await session(tid)
    if s["n"]>=MAX_STEPS: raise RuntimeError("ব্রাউজার এজেন্টের ধাপের সীমা শেষ")
    s["n"]+=1; page=s["page"]
    if name=="browser_navigate":
        await page.goto(u,timeout=NAV_TIMEOUT)
        if not url_allowed(page.url):
            await page.goto("about:blank"); raise RuntimeError("রিডাইরেক্ট অনুমোদিত তালিকার বাইরে — আটকানো হলো")
    elif name=="browser_act":
        sel=str(a.get("selector","")).strip(); txt=str(a.get("text",""))
        if act!="scroll" and not sel: raise RuntimeError("selector দাও")
        loc=page.locator(sel).first if sel else None
        if act=="click": await loc.click(timeout=10000)
        elif act=="type": await loc.fill(txt[:2000],timeout=10000)
        elif act=="press": await loc.press(txt or "Enter",timeout=10000)
        elif act=="select": await loc.select_option(txt,timeout=10000)
        elif act=="check": await loc.check(timeout=10000)
        elif act=="scroll": await page.mouse.wheel(0,800)
        try: await page.wait_for_load_state("domcontentloaded",timeout=10000)
        except Exception: pass
        if not url_allowed(page.url):
            await page.goto("about:blank"); raise RuntimeError("পেজ অনুমোদিত তালিকার বাইরে গেছে — আটকানো হলো")
    img=await _shot(s,tid,name)
    return {"text":await _text(page),"image":img}
def steps(tid): return list((_S.get(tid) or {}).get("steps") or [])
# ---------- browser-use 1.0 adapter (config only; not executed) ----------
BROWSER_USE_PIN="browser-use==1.0.2"
def browser_use_config(patterns=None):
    """kwargs for browser_use.Browser('chromium', **kw) matching our guards. Telemetry must be off via env
    ANONYMIZED_TELEMETRY=false, and an LLM from OUR free router must be passed (never the paid bu-fast gateway)."""
    pats=allowlist() if patterns is None else patterns
    return {"headless":True,"user_data_dir":PROFILE,"allowed_domains":list(pats),"block_ip_addresses":True}
