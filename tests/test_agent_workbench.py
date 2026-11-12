"""Offline checks for Agent Workbench Phase A: workbench UI (no demo timeline), real plan events,
honest browse-unavailable handling, and the agent-page step budget."""
import os, re, sys, json, asyncio, tempfile, importlib, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


AG = None
def setUpModule():
    """agent.py opens ~/bangla_bhai/data.db at import: point HOME at a throwaway dir for the import only."""
    global AG
    home = os.environ.get("HOME")
    tmp = tempfile.mkdtemp(prefix="bbwb_")
    os.makedirs(os.path.join(tmp, "bangla_bhai"), exist_ok=True)
    os.makedirs(os.path.join(tmp, ".secrets"), exist_ok=True)
    os.environ["HOME"] = tmp
    try:
        for m in ("agent", "actlog", "auditdb", "flags"):
            sys.modules.pop(m, None)
        AG = importlib.import_module("agent")
    finally:
        if home is not None: os.environ["HOME"] = home


class WorkbenchUI(unittest.TestCase):
    def setUp(self):
        self.js = read("static", "v4", "v4.js")

    def test_demo_timeline_removed(self):
        for s in ("demoRun", "#demob", "id=demob", "_demoDecided", "demo data", "ডেমো ডেটা", "'Demo'"):
            self.assertNotIn(s, self.js, s)

    def test_workbench_structure(self):
        for s in ("function pgAgents()", "function pgAgent(id)", "function wbSide(", "function startTpl(",
                  "function wbStart(", "id=plan", "class=plan", "id=fin", "id=cxl", "id=wblive class=vh aria-live=polite",
                  "<progress class=wbspin", "aria-current=step", "/bb/api/v3/agents/${aid}/run", "/bb/api/v3/runs/${tid}?since=${n}",
                  "<details class=\"card wbmore\">", "chatAgent('${a.id}')", "editAgent('${a.id}')"):
            self.assertIn(s, self.js, s)
        # the timeline itself is not a live region (announcements go through one debounced polite region)
        self.assertNotIn("id=tl aria-live", self.js)

    def test_starters_launch_real_agents(self):
        tpl = self.js[self.js.index("const TPL=["):self.js.index("const tName=")]
        self.assertNotIn("chat_only", tpl)          # every starter can start a real run
        self.assertEqual(tpl.count("ex_bn:"), 6)
        self.assertIn("onclick=\"startTpl(${i})\"", self.js)
        self.assertIn("api('/bb/api/v3/agents',{method:'POST'", self.js)

    def test_plan_and_honest_tool_rendering(self):
        self.assertIn("Array.isArray(e.items)", self.js)
        self.assertIn("e.plan_step", self.js)
        self.assertIn("!e.incomplete", self.js)
        self.assertIn("unav:['🚫 '+T('টুল উপলব্ধ নয়','Tool unavailable')", self.js)
        self.assertIn("ST.browseOk===false", self.js)

    def test_cache_bust_and_css(self):
        html = read("static", "v4", "index.html")
        self.assertIn("v4.js?v=1.3-wb", html)
        self.assertIn("v4.css?v=1.2-wb", html)
        css = read("static", "v4", "v4.css")
        self.assertIn("@container wb (inline-size > 860px)", css)
        self.assertRegex(css, r"@media \(prefers-reduced-motion:reduce\)\{progress\.wbspin\{animation:wbspin 6s")
        self.assertIn("@media (pointer:coarse){.wbw .chip", css)

    def test_no_browser_flag_flip_or_chromium(self):
        flags = read("flags.py")
        self.assertIn('"feat_browse":      ("1"', flags)       # default untouched; live override stays in the DB
        for f in ("Dockerfile", "render_start.sh", "requirements-render.txt"):
            if os.path.exists(os.path.join(ROOT, f)):
                txt = read(f).lower()
                self.assertNotIn("playwright install", txt, f)
                self.assertNotIn("apt-get install -y chromium", txt, f)
        for f in ("agent.py", "ui_v3.py"):
            self.assertNotRegex(read(f), r"set_flag\(\s*['\"]feat_browse", f)


class PlanHelpers(unittest.TestCase):
    def test_norm_plan(self):
        self.assertEqual(AG.norm_plan(["Search prices", " ", {"step": "Compare"}, "3) Write summary"]),
                         ["Search prices", "Compare", "Write summary"])
        self.assertEqual(AG.norm_plan("1. খুঁজব\n2. তুলনা করব"), ["খুঁজব", "তুলনা করব"])
        self.assertEqual(len(AG.norm_plan([str(i) + " step" for i in range(10)])), 6)
        self.assertEqual(AG.norm_plan(None), [])
        self.assertEqual(AG.norm_plan({"a": 1}), [])

    def test_step_budget(self):
        self.assertEqual(AG.max_steps(""), 10)
        self.assertEqual(AG.max_steps("x " + AG.steps_mark()), 16)
        self.assertEqual(AG.max_steps("[[steps:99]]"), 16)
        self.assertEqual(AG.strip_marks("hi " + AG.SAFE_AUTO_MARK + " " + AG.steps_mark()), "hi")
        self.assertEqual(AG.bn_num(16), "১৬")
        self.assertIn('sysx+=" "+H["AG"].steps_mark()', read("ui_v3.py"))


class FakeLoop:
    """drive agent.loop with scripted model turns and a fake tool (restricted user, safe_auto)."""
    def __init__(self, turns, browse=False):
        self.turns = list(turns); self.seen = []; self.browse = browse

    def run(self, sysx=""):
        AG.OWNER = "owner"
        tid = "t" + str(id(self))[-6:]
        AG.TASKS[tid] = {"events": [], "pending": {}, "status": "running", "goal": "compare phones", "user": "u1", "sysx": sysx}
        async def llm(msgs, private=False):
            self.seen.append(json.loads(json.dumps(msgs)))
            return "fake-model", (self.turns.pop(0) if self.turns else {"thought": "more", "plan_step": 1, "action": {"tool": "web_search", "args": {"query": "q"}}})
        async def tool(name, a): return "result for " + json.dumps(a)
        async def iso(tool, out, *a, **k): return out, [], "m"
        old = (AG.llm_json, AG.run_tool, AG.browse_ready, AG.QZ.isolate)
        AG.llm_json, AG.run_tool, AG.browse_ready, AG.QZ.isolate = llm, tool, (lambda: self.browse), iso
        try:
            async def go():
                AG.t_id_ctx.set(tid)
                await AG.loop(tid, "compare phones", sysx + " " + AG.SAFE_AUTO_MARK)
            asyncio.run(go())
        finally:
            AG.llm_json, AG.run_tool, AG.browse_ready, AG.QZ.isolate = old
        return AG.TASKS.pop(tid)["events"]


class LoopEvents(unittest.TestCase):
    def test_real_plan_before_tools_and_plan_step(self):
        evs = FakeLoop([
            {"thought": "start", "plan": ["Search prices", "Compare 3 phones", "Write summary"], "plan_step": 1,
             "action": {"tool": "web_search", "args": {"query": "budget phones bd"}}},
            {"thought": "done", "plan_step": 3, "final": "Here is the answer"},
        ]).run()
        types = [e["type"] for e in evs]
        self.assertEqual(types[0], "plan")
        self.assertEqual(evs[0]["items"], ["Search prices", "Compare 3 phones", "Write summary"])
        self.assertIn("১) Search prices", evs[0]["text"])          # old clients still get readable text
        self.assertNotIn("লক্ষ্য বুঝে পরিকল্পনা করছি", json.dumps(evs, ensure_ascii=False))
        self.assertLess(types.index("plan"), types.index("run"))
        thinks = [e for e in evs if e["type"] == "think"]
        self.assertEqual([t.get("plan_step") for t in thinks], [1, 3])
        res = [e for e in evs if e["type"] == "result"][0]
        self.assertEqual(res["tool"], "web_search")
        fin = [e for e in evs if e["type"] == "final"][-1]
        self.assertEqual(fin["text"], "Here is the answer"); self.assertFalse(fin.get("incomplete"))
        self.assertNotIn("approval", types)   # safe_auto web_search for a restricted user runs without a card

    def test_browse_unavailable_is_honest(self):
        fl = FakeLoop([
            {"thought": "open", "plan": ["Open the shop page", "Summarise"], "plan_step": 1, "action": {"tool": "browse", "args": {"url": "https://example.com"}}},
            {"thought": "fallback", "plan_step": 2, "final": "Could not open pages; here is what search shows."},
        ], browse=False)
        evs = fl.run()
        blk = [e for e in evs if e["type"] == "blocked"]
        self.assertEqual(len(blk), 1); self.assertTrue(blk[0]["unavailable"]); self.assertEqual(blk[0]["tool"], "browse")
        self.assertFalse([e for e in evs if e["type"] in ("approval", "run", "result")])   # never a fake browse
        sysmsg = fl.seen[0][0]["content"]
        self.assertNotIn("browse['url']", sysmsg)
        self.assertIn("web_search", sysmsg)
        self.assertIn('"plan"', sysmsg)
        self.assertNotIn("[[steps:", sysmsg); self.assertNotIn("[[perm:", sysmsg)

    def test_step_cap_default_and_agent_budget(self):
        evs = FakeLoop([]).run()
        self.assertEqual(sum(e["type"] == "think" for e in evs), 10)
        self.assertEqual(evs[-1]["text"], "ধাপের সীমা (১০) শেষ হয়েছে।"); self.assertTrue(evs[-1]["incomplete"])
        evs = FakeLoop([]).run(sysx=AG.steps_mark())
        self.assertEqual(sum(e["type"] == "think" for e in evs), 16)
        self.assertEqual(evs[-1]["text"], "ধাপের সীমা (১৬) শেষ হয়েছে।")

    def test_plan_fallback_when_first_turn_has_none(self):
        evs = FakeLoop([
            {"thought": "go", "action": {"tool": "web_search", "args": {"query": "x"}}},   # no plan in turn 1
            {"plan": ["Search", "Answer"]},                                                 # consumed by the fallback planner
            {"thought": "ok", "final": "done"},
        ]).run()
        self.assertEqual(evs[0]["type"], "plan"); self.assertEqual(evs[0]["items"], ["Search", "Answer"])


if __name__ == "__main__":
    unittest.main()
