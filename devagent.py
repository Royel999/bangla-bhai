"""Dev Agent: owner-only natural-language changes to this app via GitHub PRs (never direct pushes to main).
Flow: command -> read repo (GitHub API) -> LLM plan + search/replace edits -> guardrails -> branch devagent/<ts> + PR
-> CI (devagent-ci.yml) -> owner Approve & Deploy (merge -> Render auto-deploy) / Reject / Rollback (revert PR).
Secrets: GH_DEVAGENT_TOKEN in ~/.secrets/github_devagent.env, RENDER_API_KEY in ~/.secrets/render.env (never in git)."""
import os, re, json, time, base64, asyncio, hmac, secrets, httpx
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
import router as RT
REPO = "Royel999/bangla-bhai"; GH = "https://api.github.com/repos/" + REPO
SRV = "srv-dbd1qtjrjlhs73f2a4gg"; RAPI = "https://api.render.com/v1"
S = os.path.expanduser("~/.secrets")
def _env(f):
    d = {}
    try:
        for l in open(f"{S}/{f}"):
            if "=" in l: k, v = l.strip().split("=", 1); d[k] = v.strip().strip('"')
    except Exception: pass
    return d
def gh_tok(): return _env("github_devagent.env").get("GH_DEVAGENT_TOKEN") or os.environ.get("GH_DEVAGENT_TOKEN")
def rd_tok(): return _env("render.env").get("RENDER_API_KEY")
# ---------- guardrails ----------
PROTECTED = re.compile(r"^(\.github/|auth\.py$|persist\.py$|render_start\.sh$|start\.sh$|supervise\.sh$|keep_supervise\.sh$|Dockerfile$|notebook\.py$|vault|devagent\.py$|connections\.py$|requirements)")
FORBID_PATH = re.compile(r"(^|/)(\.secrets|\.env|.*\.key|.*\.pem|.*\.keystore|data\.db|audit\.jsonl)$|^(venv|archive|media_store)/")
EXFIL = re.compile(r"\.secrets|BB_SECRETS|os\.environ|getenv|_sec\(\)|RENDER_API_KEY|GH_DEVAGENT_TOKEN|API_KEY|subprocess|os\.system|eval\(|exec\(|webhook\.site|ngrok|pastebin|requestbin", re.I)
MAX_FILES, MAX_LINES, MAX_FILE_BYTES = 8, 400, 200_000
TEXT_EXT = (".py", ".js", ".css", ".html", ".md", ".json", ".txt", ".yml", ".yaml", ".sh", ".svg", ".webmanifest", ".toml")
SYS_CMDS = {"restart": "Redeploy/restart the Render service", "status": "Show latest Render deploy status", "logs": "Show recent Render logs", "health": "Check /bb/health on the domain"}
H = {}
def _db():
    c = H["db"]()
    c.execute("create table if not exists devagent_jobs(id text primary key,created real,cmd text,status text,data text)")
    c.execute("create table if not exists devagent_audit(t real,ev text,job text,detail text)"); return c
def log(ev, job="", **d):
    with _db() as c: c.execute("insert into devagent_audit values(?,?,?,?)", (time.time(), ev, job, json.dumps(d, ensure_ascii=False)[:4000]))
    try: H["audit"](ev="devagent_" + ev, job=job)
    except Exception: pass
def jget(i):
    with _db() as c: r = c.execute("select * from devagent_jobs where id=?", (i,)).fetchone()
    return {**json.loads(r["data"]), "id": r["id"], "status": r["status"], "cmd": r["cmd"], "created": r["created"]} if r else None
def jput(j):
    d = {k: v for k, v in j.items() if k not in ("id", "status", "cmd", "created")}
    with _db() as c: c.execute("insert or replace into devagent_jobs values(?,?,?,?,?)", (j["id"], j["created"], j["cmd"], j["status"], json.dumps(d, ensure_ascii=False)))
# ---------- GitHub ----------
async def gh(method, path, root=False, **kw):
    t = gh_tok()
    if not t: raise RuntimeError("GitHub token not configured (github_devagent.env)")
    async with httpx.AsyncClient(timeout=40) as c:
        r = await c.request(method, ("https://api.github.com" if root else GH) + path, headers={"Authorization": "Bearer " + t, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}, **kw)
    if r.status_code >= 400: raise RuntimeError(f"GitHub {method} {path.split('?')[0]} -> {r.status_code}: {r.text[:200]}")
    return r.json() if r.text else {}
async def tree(ref="main"):
    t = await gh("GET", f"/git/trees/{ref}?recursive=1")
    return [x["path"] for x in t["tree"] if x["type"] == "blob" and x.get("size", 0) < MAX_FILE_BYTES and x["path"].endswith(TEXT_EXT) and not FORBID_PATH.search(x["path"])]
async def read(path, ref="main"):
    try: j = await gh("GET", f"/contents/{path}?ref={ref}")
    except RuntimeError as e:
        if "404" in str(e): return None
        raise
    return base64.b64decode(j["content"]).decode("utf-8", "replace")
async def commit_files(branch_from_sha, branch, files, msg):
    """files: {path: text or None(delete)} -> single commit on new branch."""
    base = await gh("GET", f"/git/commits/{branch_from_sha}")
    items = []
    for p, txt in files.items():
        if txt is None: items.append({"path": p, "mode": "100644", "type": "blob", "sha": None})
        else:
            b = await gh("POST", "/git/blobs", json={"content": txt, "encoding": "utf-8"})
            items.append({"path": p, "mode": "100755" if p.endswith(".sh") else "100644", "type": "blob", "sha": b["sha"]})
    t = await gh("POST", "/git/trees", json={"base_tree": base["tree"]["sha"], "tree": items})
    c = await gh("POST", "/git/commits", json={"message": msg, "tree": t["sha"], "parents": [branch_from_sha]})
    await gh("POST", "/git/refs", json={"ref": "refs/heads/" + branch, "sha": c["sha"]})
    return c["sha"]
async def ci(sha):
    j = await gh("GET", f"/commits/{sha}/check-runs")
    runs = j.get("check_runs", [])
    if not runs: return "pending"
    if any(r["status"] != "completed" for r in runs): return "running"
    return "green" if all(r["conclusion"] in ("success", "skipped", "neutral") for r in runs) else "red"
# ---------- Render ----------
async def render(method, path, **kw):
    t = rd_tok()
    if not t: raise RuntimeError("Render key not configured")
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.request(method, RAPI + path, headers={"Authorization": "Bearer " + t, "Accept": "application/json"}, **kw)
    if r.status_code >= 400: raise RuntimeError(f"Render {r.status_code}: {r.text[:200]}")
    return r.json() if r.text else {}
async def last_deploy():
    d = await render("GET", f"/services/{SRV}/deploys?limit=1")
    d = (d[0].get("deploy") if d else {}) or {}
    return {"status": d.get("status"), "commit": ((d.get("commit") or {}).get("id") or "")[:7], "finished": d.get("finishedAt")}
async def system(cmd):
    if cmd == "restart": d = await render("POST", f"/services/{SRV}/deploys", json={"clearCache": "do_not_clear"}); return f"Redeploy started ({d.get('id','')})."
    if cmd == "status": return json.dumps(await last_deploy())
    if cmd == "health":
        async with httpx.AsyncClient(timeout=20) as c: r = await c.get("https://banglabhai.dpdns.org/bb/health")
        return f"{r.status_code} {r.text[:300]}"
    if cmd == "logs":
        s = await render("GET", f"/services/{SRV}"); own = s.get("ownerId")
        j = await render("GET", f"/logs?ownerId={own}&resource={SRV}&limit=40&direction=backward")
        lines = [re.sub(r"\x1b\[[0-9;]*m", "", x.get("message", "")) for x in j.get("logs", [])]
        red = re.compile(r"(gh[opsu]_|github_pat_|sk-|rnd_|AIza|gsk_)[A-Za-z0-9_\-]{8,}")
        return "\n".join(red.sub("[redacted]", l)[:300] for l in lines) or "(no logs)"
    raise ValueError("unknown system command")
# ---------- LLM ----------
GEMK = RT.K.get("GEMINI_API_KEY"); ORK = RT.K.get("OPENROUTER_API_KEY"); GQK = RT.K.get("GROQ_API_KEY")
FREE = [("da:gemini-3.8-flash", ("Gemini 3.8 Flash", RT.GEM, GEMK, "gemini-3.8-flash", "oa")),
        ("da:groq-gptoss", ("Groq GPT-OSS 120B", RT.GROQ, GQK, "openai/gpt-oss-120b", "oa")),
        ("da:gemini-3.5-flash", ("Gemini 3.5 Flash", RT.GEM, GEMK, "gemini-3.5-flash", "oa")),
        ("da:gemini-2.5-flash", ("Gemini 2.5 Flash", RT.GEM, GEMK, "gemini-2.5-flash", "oa")),
        ("da:or-free", ("OpenRouter Free", RT.OR, ORK, "openrouter/free", "oa"))]
def models(u):
    out = [{"id": "auto", "name": "Auto (free: Gemini 3.8 Flash → Groq GPT-OSS → …)"}]
    try: out += H["MD"].byok_chat_list(u)
    except Exception: pass
    return out
def specs(u, sel):
    ex = []
    if sel and sel.startswith("byok:"):
        r = H["MD"].resolve_chat(u, sel)
        if r: ex.append((sel, (r[0], r[1], r[2], r[3], "anthropic" if "anthropic.com" in r[1] else "oa")))
    return ex + [s for s in FREE if s[1][2]]
def _json(t):
    t = re.sub(r"^```(?:json)?|```$", "", t.strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", t, re.S)
    return json.loads(m.group(0) if m else t)
LAST_TRACE = []
async def llm(u, sel, msgs, tries=2):
    last = None
    for _ in range(tries):
        try:
            n, t, tr = await RT.complete(msgs, chain=["__none__"], extra=specs(u, sel), json_mode=True, timeout=90, tries=1)
            LAST_TRACE[:] = [f"{m}={s}"[:80] for m, s in tr]
            return n, _json(t)
        except (ValueError, json.JSONDecodeError) as e: last = e
    raise RuntimeError(f"model gave invalid JSON: {last}")
SYS = """You are the Dev Agent for the "Bangla Bhai" FastAPI app (Python, inline HTML/JS/CSS in app.py, static/ assets).
Map: login/admin-login/app/chat pages are inline HTML f-strings in app.py; landing page = static/landing.html; admin panel UI = biz.py; connections = connections.py + static/connections.*; translations = static/i18n/*.json.
The owner writes commands in Bangla or English. Make the smallest correct change. Respond ONLY with JSON."""
async def pick_files(u, sel, cmd, paths):
    n, j = await llm(u, sel, [{"role": "system", "content": SYS}, {"role": "user", "content":
        f"Command: {cmd}\n\nRepository files:\n" + "\n".join(paths) + '\n\nReturn {"files":[up to 6 paths most likely needing edits or needed for context],"needle":"one short literal string likely present in the code to change, or empty"}'}])
    return n, [p for p in j.get("files", []) if p in paths][:6], (j.get("needle") or "")[:80]
def excerpt(t, needle):
    if len(t) <= 14000: return t
    idx = [m.start() for m in re.finditer(re.escape(needle), t)][:3] if needle else []
    if not idx: return t[:9000] + "\n…(truncated)…"
    out, last = [], -1
    for i in idx:
        a, b = max(0, i - 2500, last), min(len(t), i + 2500)
        if b > a: out.append(t[a:b]); last = b
    return "\n…\n".join(out)
async def plan_edits(u, sel, cmd, files, needle=""):
    ctx = "\n\n".join(f"=== {p} (excerpt) ===\n{excerpt(t, needle)}" for p, t in files.items())[:60000]
    msgs = [{"role": "system", "content": SYS}, {"role": "user", "content": f"""Command: {cmd}

Files:
{ctx}

Return JSON: {{"plan":"short plan in the command's language","title":"short PR title (English)","edits":[{{"path":"file","search":"exact existing text copied verbatim (unique, include enough context)","replace":"new text"}}],"new_files":[{{"path":"...","content":"..."}}]}}
Rules: search must match the file EXACTLY once; keep edits minimal; do not touch secrets, auth or CI unless asked; if impossible, return edits:[] and explain in plan."""}]
    return await llm(u, sel, msgs)
def apply(files, edits):
    out = dict(files); errs = []
    for e in edits:
        p, s, r = e.get("path"), e.get("search", ""), e.get("replace", "")
        if p not in out or out[p] is None: errs.append(f"{p}: file not loaded"); continue
        n = out[p].count(s)
        if not s or n != 1: errs.append(f"{p}: search text found {n} times"); continue
        out[p] = out[p].replace(s, r, 1)
    return out, errs
def udiff(old, new, p):
    import difflib
    return "".join(difflib.unified_diff((old or "").splitlines(True), (new or "").splitlines(True), "a/" + p, "b/" + p, n=2))
def check(orig, new, allow_protected):
    issues, need = [], []
    changed = {p: t for p, t in new.items() if t != orig.get(p)}
    if not changed: issues.append("no changes produced")
    if len(changed) > MAX_FILES: issues.append(f"too many files ({len(changed)}>{MAX_FILES})")
    lines = 0
    for p, t in changed.items():
        if FORBID_PATH.search(p) or ".." in p or p.startswith("/"): issues.append(f"forbidden path {p}")
        if PROTECTED.search(p) and not allow_protected: need.append(p)
        d = udiff(orig.get(p), t, p); lines += sum(1 for l in d.splitlines() if l[:1] in "+-" and not l.startswith(("+++", "---")))
        added = "\n".join(l[1:] for l in d.splitlines() if l.startswith("+") and not l.startswith("+++"))
        old = orig.get(p) or ""
        for m in set(EXFIL.findall(added)):
            if added.count(m) > old.count(m) or m not in old: issues.append(f"{p}: adds sensitive pattern '{m}' (blocked)"); break
        if p.endswith(".py") and t is not None:
            try: compile(t, p, "exec")
            except SyntaxError as e: issues.append(f"{p}: syntax error line {e.lineno}")
    if lines > MAX_LINES: issues.append(f"diff too large ({lines}>{MAX_LINES} lines)")
    return changed, issues, need
# ---------- job runner ----------
async def run_job(jid, u, sel, allow_protected=False):
    j = jget(jid)
    def st(s, **k): j.update(status=s, **k); j.setdefault("steps", []).append([int(time.time()), s]); jput(j)
    try:
        st("reading repo"); paths = await tree()
        n1, picks, needle = await pick_files(u, sel, j["cmd"], paths)
        if needle:
            try:
                r = await gh("GET", "/search/code", root=True, params={"q": f'"{needle}" repo:{REPO}'})
                picks += [x["path"] for x in r.get("items", [])[:3] if x["path"] in paths and x["path"] not in picks]
            except Exception: pass
        picks = picks[:6] or ["app.py"]
        files = {p: await read(p) for p in picks}; files = {p: t for p, t in files.items() if t is not None}
        if needle:  # keep files that actually contain the needle first; drop context-only files that don't
            hit = {p: t for p, t in files.items() if needle in t}
            if hit: files = hit
        st("planning", files=list(files))
        n2, out = await plan_edits(u, sel, j["cmd"], files, needle)
        new, errs = apply(files, out.get("edits") or [])
        for nf in out.get("new_files") or []:
            p = nf.get("path", "")
            if p and p not in paths: new[p] = nf.get("content", "")
        if errs and not any(new[p] != files.get(p) for p in new):
            n2, out = await plan_edits(u, sel, j["cmd"] + "\n\nPrevious attempt failed: " + "; ".join(errs) + ". Copy search text verbatim.", files, needle)
            new, errs = apply(files, out.get("edits") or [])
        changed, issues, need = check(files, new, allow_protected)
        diff = "".join(udiff(files.get(p), t, p) for p, t in changed.items())
        j.update(plan=out.get("plan", ""), title=(out.get("title") or j["cmd"])[:80], diff=diff[:60000], model=n2, warnings=errs, trace=list(LAST_TRACE))
        if issues: st("blocked", error="; ".join(issues)); log("blocked", jid, issues=issues); return
        if need: st("needs_confirm", protected=need, pending=changed); log("needs_confirm", jid, files=need); return
        await open_pr(j, changed)
    except Exception as e:
        st("failed", error=str(e)[:500]); log("failed", jid, error=str(e)[:300])
async def open_pr(j, changed):
    main = (await gh("GET", "/git/ref/heads/main"))["object"]["sha"]
    br = "devagent/" + time.strftime("%Y%m%d-%H%M%S") + "-" + j["id"][:4]
    sha = await commit_files(main, br, changed, f"devagent: {j.get('title','change')}\n\nCommand: {j['cmd'][:500]}")
    pr = await gh("POST", "/pulls", json={"title": "[Dev Agent] " + j.get("title", "change"), "head": br, "base": "main",
        "body": f"**Owner command:** {j['cmd'][:1000]}\n\n**Plan:** {j.get('plan','')[:2000]}\n\nModel: {j.get('model','')}\n\n_Opened by Dev Agent; merges only after owner approval._"})
    j.pop("pending", None); j.update(status="pr_open", branch=br, sha=sha, pr=pr["number"], pr_url=pr["html_url"], base=main)
    j.setdefault("steps", []).append([int(time.time()), "pr_open"]); jput(j); log("pr_open", j["id"], pr=pr["number"])
async def refresh(j):
    if j.get("pr") and j["status"] in ("pr_open", "merged", "deploying", "rollback_open"):
        try: j["ci"] = await ci(j["sha"])
        except Exception as e: j["ci"] = "unknown"
    if j["status"] in ("merged", "deploying") and j.get("merge_sha"):
        try:
            d = await last_deploy(); j["deploy"] = d
            if d.get("commit") == j["merge_sha"][:7] and d.get("status") == "live": j["status"] = "deployed"
            elif d.get("commit") == j["merge_sha"][:7] and d.get("status") in ("build_failed", "update_failed", "canceled"): j["status"] = "deploy_failed"
            else: j["status"] = "deploying"
        except Exception: pass
    jput(j); return j
async def merge(j, label):
    m = await gh("PUT", f"/pulls/{j['pr']}/merge", json={"merge_method": "squash", "commit_title": f"{label} #{j['pr']}: {j.get('title','')}"[:120]})
    try: await gh("DELETE", f"/git/refs/heads/{j['branch']}")
    except Exception: pass
    return m["sha"]
def revert_text(cur, old, new):
    """Undo old->new inside cur (which may have later unrelated edits): 3-way-ish hunk reversal with context."""
    import difflib
    if cur == new: return old
    ol, nl = old.splitlines(True), new.splitlines(True); out = cur
    for tag, i1, i2, j1, j2 in reversed(difflib.SequenceMatcher(None, ol, nl, autojunk=False).get_opcodes()):
        if tag == "equal": continue
        for ctx in (2, 1, 0, 4, 8):
            a0, b0 = max(0, j1 - ctx), min(len(nl), j2 + ctx)
            seg_new = "".join(nl[a0:b0]); seg_old = "".join(nl[a0:j1]) + "".join(ol[i1:i2]) + "".join(nl[j2:b0])
            if seg_new and out.count(seg_new) == 1: out = out.replace(seg_new, seg_old, 1); break
        else: raise RuntimeError("cannot cleanly undo: the same lines were changed again later")
    return out
async def rollback(j):
    """Revert a merged job via a PR that undoes its hunks on top of current main, then merge."""
    msha = j["merge_sha"]; c = await gh("GET", f"/commits/{msha}"); parent = c["parents"][0]["sha"]
    main = (await gh("GET", "/git/ref/heads/main"))["object"]["sha"]
    files = {}
    for f in c.get("files", []):
        p = f["filename"]; old, new, cur = await read(p, parent), await read(p, msha), await read(p, main)
        if old is None: files[p] = None if cur == new else cur  # file added by the change
        elif cur is None: files[p] = old
        else: files[p] = revert_text(cur, old, new)
    files = {p: t for p, t in files.items() if t != (await read(p, main))}
    if not files: raise RuntimeError("nothing to roll back (already reverted?)")
    br = "devagent/rollback-" + time.strftime("%Y%m%d-%H%M%S")
    await commit_files(main, br, files, f"devagent: rollback #{j['pr']}")
    pr = await gh("POST", "/pulls", json={"title": f"[Dev Agent] Rollback #{j['pr']}: {j.get('title','')}"[:120], "head": br, "base": "main", "body": "Owner-approved rollback."})
    m = await gh("PUT", f"/pulls/{pr['number']}/merge", json={"merge_method": "squash"})
    try: await gh("DELETE", f"/git/refs/heads/{br}")
    except Exception: pass
    return pr["number"], m["sha"]
# ---------- routes ----------
def setup(app, HH):
    H.update(HH)
    def own(request):
        u = H["need_admin"](request); return u
    def chk(request):
        if not hmac.compare_digest(request.headers.get("x-csrf", ""), request.session.get("csrf", "") or "x"): raise PermissionError
    def tok(request):
        t = request.session.get("csrf")
        if not t: t = secrets.token_urlsafe(24); request.session["csrf"] = t
        return t
    @app.get("/admin/dev")
    def page(request: Request):
        try: own(request)
        except Exception:
            from fastapi.responses import RedirectResponse; return RedirectResponse("/admin", 303)
        return HTMLResponse(UI.replace("__CSRF__", tok(request)), headers={"Cache-Control": "no-store"})
    @app.get("/bb/api/dev/state")
    async def state(request: Request):
        u = own(request)
        with _db() as c: rows = [r["id"] for r in c.execute("select id from devagent_jobs order by created desc limit 15")]
        jobs = []
        for i in rows:
            j = jget(i)
            if j["status"] in ("pr_open", "merged", "deploying", "rollback_open") and time.time() - j["created"] < 86400 * 3: j = await refresh(j)
            j.pop("pending", None); jobs.append(j)
        return {"jobs": jobs, "models": models(u), "sys": SYS_CMDS, "configured": {"github": bool(gh_tok()), "render": bool(rd_tok())}}
    @app.post("/bb/api/dev/cmd")
    async def cmd(request: Request):
        u = own(request); chk(request); b = await request.json(); t = (b.get("text") or "").strip()
        if not (3 <= len(t) <= 2000): return JSONResponse({"error": "Command must be 3–2000 characters"}, 400)
        if not H["rate_ok"]("devagent:" + str(u), 20, 3600): return JSONResponse({"error": "Rate limit: 20 commands/hour"}, 429)
        jid = secrets.token_hex(6); jput({"id": jid, "created": time.time(), "cmd": t, "status": "queued", "steps": []})
        log("command", jid, text=t[:500], model=b.get("model", "auto"))
        asyncio.create_task(run_job(jid, u, b.get("model", "auto"), bool(b.get("allow_protected"))))
        return {"ok": True, "id": jid}
    @app.post("/bb/api/dev/job/{jid}/{act}")
    async def act(request: Request, jid: str, act: str):
        u = own(request); chk(request); j = jget(jid)
        if not j: return JSONResponse({"error": "not found"}, 404)
        b = {}
        try: b = await request.json()
        except Exception: pass
        try:
            if act == "confirm" and j["status"] == "needs_confirm":
                if b.get("phrase") != "CONFIRM": return JSONResponse({"error": "Type CONFIRM to allow protected files"}, 400)
                log("confirm_protected", jid, files=j.get("protected")); await open_pr(j, j["pending"])
            elif act == "approve" and j["status"] == "pr_open":
                j = await refresh(j)
                if j.get("ci") != "green" and not b.get("force"): return JSONResponse({"error": f"CI is {j.get('ci')}; wait for green"}, 409)
                j["merge_sha"] = await merge(j, "Dev Agent"); j["status"] = "deploying"; jput(j); log("approved_merged", jid, pr=j["pr"])
            elif act == "reject" and j["status"] in ("pr_open", "needs_confirm", "blocked", "failed"):
                if j.get("pr"):
                    await gh("PATCH", f"/pulls/{j['pr']}", json={"state": "closed"})
                    try: await gh("DELETE", f"/git/refs/heads/{j['branch']}")
                    except Exception: pass
                j["status"] = "rejected"; j.pop("pending", None); jput(j); log("rejected", jid)
            elif act == "rollback" and j["status"] in ("deployed", "deploying", "merged", "deploy_failed"):
                n, sha = await rollback(j); j.update(status="rolled_back", rollback_pr=n, rollback_sha=sha); jput(j); log("rollback", jid, pr=n)
            else: return JSONResponse({"error": f"'{act}' not allowed while {j['status']}"}, 409)
        except Exception as e: log("action_error", jid, act=act, error=str(e)[:300]); return JSONResponse({"error": str(e)[:300]}, 502)
        return {"ok": True, "status": j["status"]}
    @app.post("/bb/api/dev/sys")
    async def sysc(request: Request):
        own(request); chk(request); b = await request.json(); c = b.get("cmd")
        if c not in SYS_CMDS: return JSONResponse({"error": "not allowed"}, 400)
        if c == "restart" and b.get("confirm") is not True: return JSONResponse({"error": "confirm required"}, 400)
        if not H["rate_ok"]("devsys", 30, 3600): return JSONResponse({"error": "rate limit"}, 429)
        log("system", "", cmd=c)
        try: return {"ok": True, "out": await system(c)}
        except Exception as e: return JSONResponse({"error": str(e)[:300]}, 502)
    @app.get("/bb/api/dev/audit")
    def aud(request: Request):
        own(request)
        with _db() as c: return {"log": [dict(r) for r in c.execute("select * from devagent_audit order by t desc limit 100")]}
UI = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "devagent.html"), encoding="utf-8").read()
