"""P1 browser agent foundation: flag OFF by default, tight domain allowlist, screenshot per step, Sentinel tiers.
No real browser is started (session/_launch are mocked); no network."""
import os, sys, unittest, asyncio, tempfile, sqlite3, types
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import flags as FL, sentinel as SN, quarantine as QZ
import browser_agent as BA

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def run(c): return asyncio.run(c)

class TempFlags(unittest.TestCase):
    """flags.DBF -> empty temp DB so nothing reads/writes the real standby data.db."""
    def setUp(self):
        self.tmp = tempfile.mkdtemp(); self._dbf = FL.DBF
        FL.DBF = os.path.join(self.tmp, "data.db")
        c = sqlite3.connect(FL.DBF); c.execute("create table app_settings(k text primary key, v text)"); c.commit(); c.close()
        FL._C["t"] = 0; FL._C["v"] = {}
        self._env = os.environ.pop("BB_BROWSER_AGENT_ALLOW", None)
        # public-IP check without DNS: stand-in for agent._url_ok
        self._agent = sys.modules.get("agent")
        sys.modules["agent"] = types.SimpleNamespace(_url_ok=lambda u: "127.0.0.1" not in u and "localhost" not in u and "10.0.0." not in u)
    def tearDown(self):
        FL.DBF = self._dbf; FL._C["t"] = 0; FL._C["v"] = {}
        if self._env is not None: os.environ["BB_BROWSER_AGENT_ALLOW"] = self._env
        else: os.environ.pop("BB_BROWSER_AGENT_ALLOW", None)
        if self._agent is not None: sys.modules["agent"] = self._agent
        else: sys.modules.pop("agent", None)
        BA._S.clear()
    def set(self, k, v):
        c = sqlite3.connect(FL.DBF); c.execute("insert or replace into app_settings values(?,?)", (k, v)); c.commit(); c.close(); FL._C["t"] = 0

class FlagOffByDefault(TempFlags):
    def test_flag_registered_default_off(self):
        self.assertIn("feat_browser_agent", FL.FLAGS)
        self.assertEqual(FL.FLAGS["feat_browser_agent"][0], "0")
        self.assertFalse(FL.on("feat_browser_agent"))
        self.assertFalse(BA.enabled())
    def test_run_refuses_when_off_and_never_launches(self):
        async def boom(): raise AssertionError("browser must not start while the flag is off")
        orig = BA._launch; BA._launch = boom
        try:
            for name in BA.TOOLS:
                with self.assertRaises(RuntimeError) as e: run(BA.run("t1", name, {"url": "https://example.com"}))
                self.assertIn("বন্ধ", str(e.exception))
        finally: BA._launch = orig
    def test_feat_agent_off_also_turns_it_off(self):
        self.set("feat_browser_agent", "1"); self.set("feat_agent", "0")
        self.assertFalse(BA.enabled())
    def test_on_only_when_owner_sets_it(self):
        self.set("feat_browser_agent", "1")
        self.assertTrue(BA.enabled())
    def test_agent_wires_tools_only_behind_flag(self):
        src = open(os.path.join(ROOT, "agent.py"), encoding="utf-8").read()
        self.assertIn("if BA.enabled(): tools+=", src)                 # not advertised to the planner when off
        self.assertIn("_ba=tool in BA.TOOLS and BA.enabled()", src)    # unknown tool when off
        self.assertNotIn("browser_", "".join(src.split("SAFE_TOOLS=")[1].split("\n")[0]))  # never for restricted users
        self.assertNotIn("browser-use", open(os.path.join(ROOT, "requirements-render.txt")).read())  # Render image unchanged

class Allowlist(TempFlags):
    def test_default_allowlist_is_empty_deny_all(self):
        self.assertEqual(BA.allowlist(), [])
        for u in ("https://example.com", "https://www.google.com", "https://bn.wikipedia.org/wiki/x"):
            self.assertFalse(BA.url_allowed(u), u)
    def test_rejects_unsafe_patterns(self):
        os.environ["BB_BROWSER_AGENT_ALLOW"] = "*, *.*, https://evil.com, evil.com/path, evil.com:8080, localhost, ok.example.org"
        self.assertEqual(BA.allowlist(), ["ok.example.org"])
    def test_matching_rules(self):
        p = ["example.com", "*.wikipedia.org", "mail.site.net"]
        ok = ["https://example.com/a", "http://www.example.com", "https://bn.wikipedia.org/wiki/ঢাকা", "https://wikipedia.org",
              "https://mail.site.net/x", "https://EXAMPLE.com."]
        bad = ["https://evil-example.com", "https://example.com.evil.com", "https://sub.example.com", "https://site.net",
               "https://www.mail.site.net", "ftp://example.com", "file:///etc/passwd", "javascript:alert(1)",
               "https://example.com@evil.com/", "https://user:pw@example.com/", "https://wikipedia.org.evil.io", "", "not a url"]
        for u in ok: self.assertTrue(BA.url_allowed(u, p), u)
        for u in bad: self.assertFalse(BA.url_allowed(u, p), u)
    def test_allowlisted_but_private_is_blocked(self):
        self.assertFalse(BA.url_allowed("http://localhost/", ["localhost.com"]))
        self.assertFalse(BA.host_allowed("localhost", BA.allowlist()))
    def test_settings_key_used(self):
        self.set("browser_agent_allow", "example.com, *.gov.bd")
        self.assertEqual(BA.allowlist(), ["example.com", "*.gov.bd"])
        self.assertTrue(BA.url_allowed("https://www.dhaka.gov.bd/"))
    def test_navigate_off_allowlist_refused_before_browser_starts(self):
        self.set("feat_browser_agent", "1"); self.set("browser_agent_allow", "example.com")
        async def boom(): raise AssertionError("must not launch for a blocked URL")
        orig = BA._launch; BA._launch = boom
        try:
            with self.assertRaises(RuntimeError) as e: run(BA.run("t1", "browser_navigate", {"url": "https://evil.com"}))
            self.assertIn("অনুমোদিত", str(e.exception))
            with self.assertRaises(RuntimeError): run(BA.run("t1", "browser_act", {"action": "rm -rf", "selector": "a"}))
        finally: BA._launch = orig

class FakePage:
    def __init__(self, redirect_to=None):
        self.url = "about:blank"; self.redirect_to = redirect_to; self.shots = []; self.mouse = types.SimpleNamespace(wheel=self._wheel)
    async def _wheel(self, x, y): pass
    async def goto(self, u, timeout=None): self.url = self.redirect_to if (self.redirect_to and u != "about:blank") else u
    async def screenshot(self, path): self.shots.append(path)
    async def inner_text(self, sel): return "body text"
    async def title(self): return "T"
    async def wait_for_load_state(self, *a, **k): pass
    def locator(self, sel):
        page = self
        class L:
            first = None
            async def click(self, timeout=None): page.clicked = sel
            async def fill(self, t, timeout=None): page.filled = t
        l = L(); l.first = l; return l

class Steps(TempFlags):
    def setUp(self):
        super().setUp()
        self.set("feat_browser_agent", "1"); self.set("browser_agent_allow", "example.com")
        self._shots = BA.SHOTS; BA.SHOTS = self.tmp
    def tearDown(self):
        BA.SHOTS = self._shots; super().tearDown()
    def fake(self, page):
        async def sess(tid):
            BA._S.setdefault(tid, {"pw": None, "ctx": None, "page": page, "steps": [], "n": 0, "t": 0}); return BA._S[tid]
        self._sess = BA.session; BA.session = sess
        self.addCleanup(lambda: setattr(BA, "session", self._sess))
    def test_screenshot_every_step(self):
        pg = FakePage(); self.fake(pg)
        r1 = run(BA.run("t9", "browser_navigate", {"url": "https://example.com/"}))
        r2 = run(BA.run("t9", "browser_act", {"action": "click", "selector": "text=More"}))
        r3 = run(BA.run("t9", "browser_read", {}))
        self.assertEqual(len(pg.shots), 3)
        for r in (r1, r2, r3): self.assertTrue(r["image"].startswith("/bb/static/shots/ba_t9_"))
        self.assertEqual([s["step"] for s in BA.steps("t9")], ["browser_navigate", "browser_act", "browser_read"])
    def test_redirect_off_allowlist_blocked(self):
        pg = FakePage(redirect_to="https://evil.com/phish"); self.fake(pg)
        with self.assertRaises(RuntimeError): run(BA.run("t8", "browser_navigate", {"url": "https://example.com/"}))
        self.assertEqual(pg.url, "about:blank")
        self.assertEqual(pg.shots, [])     # nothing from the evil page is captured or returned

class RouteGuard(TempFlags):
    def test_document_requests_need_allowlist_subresources_need_public(self):
        os.environ["BB_BROWSER_AGENT_ALLOW"] = "example.com"
        def route(url, kind):
            r = types.SimpleNamespace(request=types.SimpleNamespace(url=url, resource_type=kind), res=None)
            async def cont(): r.res = "continue"
            async def abort(): r.res = "abort"
            r.continue_ = cont; r.abort = abort; run(BA._guard(r)); return r.res
        self.assertEqual(route("https://example.com/", "document"), "continue")
        self.assertEqual(route("https://evil.com/", "document"), "abort")          # iframes / popups too
        self.assertEqual(route("https://cdn.jsdelivr.net/x.js", "script"), "continue")
        self.assertEqual(route("http://10.0.0.5/admin", "xhr"), "abort")
        self.assertEqual(route("http://127.0.0.1:8090/bb/api", "fetch"), "abort")

class SentinelHook(unittest.TestCase):
    def test_policy_has_browser_tools(self):
        for t in BA.TOOLS: self.assertEqual(SN.POLICY["tools"].get(t), BA.policy_for(t), t)
    def test_act_always_card_navigate_card_in_beta(self):
        self.assertEqual(SN.tier("browser_act"), "control")
        self.assertTrue(SN.pre_call("browser_act")["card"])
        self.assertEqual(SN.category("browser_act"), "control")
        self.assertEqual(SN.tier("browser_navigate"), "act")
        self.assertTrue(SN.pre_call("browser_navigate", tainted=True)["card"])
        self.assertEqual(BA.ALWAYS_CARD, {"browser_navigate", "browser_act"})
        self.assertFalse(SN.pre_call("browser_read")["card"])
    def test_builtin_gate_cannot_be_downgraded(self):
        self.assertEqual(SN._BUILTIN["tools"]["browser_act"], "control")
    def test_page_output_is_untrusted(self):
        for t in ("browser_navigate", "browser_read", "browser_act"):
            self.assertIn(t, SN.UNTRUSTED); self.assertIn(t, QZ.WEB_TOOLS)
    def test_browser_use_config_matches_guards(self):
        cfg = BA.browser_use_config(["example.com"])
        self.assertEqual(cfg["allowed_domains"], ["example.com"])
        self.assertTrue(cfg["headless"]); self.assertTrue(cfg["block_ip_addresses"])
        self.assertEqual(cfg["user_data_dir"], BA.PROFILE)
        self.assertNotIn("google-chrome", BA.PROFILE); self.assertIn(".bb_browser_agent", BA.PROFILE)

if __name__ == "__main__": unittest.main()
