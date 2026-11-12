"""Offline Langfuse tracing tests. CI must not need real keys or network."""
import os, sys, unittest, asyncio, json
from contextlib import contextmanager
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Isolate from any shell/box secrets before importing lftrace.
for k in list(os.environ):
    if k.startswith("LANGFUSE_"):
        os.environ.pop(k, None)
os.environ["BB_LANGFUSE_ENV_FILE"] = "/tmp/bb-langfuse-tests-no-file.env"

import lftrace as LF
import router as RT


class FakeObs:
    def __init__(self, kwargs):
        self.kwargs = kwargs
        self.updates = []
    def update(self, **k):
        self.updates.append(k)
        return self
    def end(self):
        return self


class FakeClient:
    def __init__(self, boom=False):
        self.boom = boom
        self.calls = []
        self.obs = []
        self.flushed = False
    def start_as_current_observation(self, **kw):
        if self.boom:
            raise RuntimeError("langfuse-down")
        self.calls.append(kw)
        obs = FakeObs(kw)
        self.obs.append(obs)
        @contextmanager
        def cm():
            yield obs
        return cm()
    def flush(self):
        self.flushed = True


class LangfuseAdapter(unittest.TestCase):
    def setUp(self):
        for k in list(os.environ):
            if k.startswith("LANGFUSE_"):
                os.environ.pop(k, None)
        os.environ["BB_LANGFUSE_ENV_FILE"] = "/tmp/bb-langfuse-tests-no-file.env"
        LF.reset_for_tests()

    def tearDown(self):
        for k in list(os.environ):
            if k.startswith("LANGFUSE_"):
                os.environ.pop(k, None)
        os.environ["BB_LANGFUSE_ENV_FILE"] = "/tmp/bb-langfuse-tests-no-file.env"
        LF.reset_for_tests()

    def test_disabled_without_keys(self):
        st = LF.status()
        self.assertFalse(st["configured"])
        self.assertFalse(st["enabled"])
        self.assertEqual(st["reason"], "missing-keys")
        self.assertFalse(st["base_url_set"])
        self.assertFalse(st["project_id_set"])
        with LF.observation("x") as obs:
            obs.update(output="should-not-throw")
            self.assertIs(obs, LF._NOOP)

    def test_disabled_when_flag_off_even_with_keys(self):
        os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-lf-TESTNOTAREALKEY000000000000000"
        os.environ["LANGFUSE_SECRET_KEY"] = "sk-lf-TESTNOTAREALKEY000000000000000"
        os.environ["LANGFUSE_TRACING_ENABLED"] = "0"
        LF.reset_for_tests()
        st = LF.status()
        self.assertFalse(st["enabled"])
        self.assertEqual(st["reason"], "disabled")

    def test_status_never_includes_secrets(self):
        os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-lf-TESTNOTAREALKEY000000000000000"
        os.environ["LANGFUSE_SECRET_KEY"] = "sk-lf-TESTNOTAREALKEY000000000000000"
        os.environ["LANGFUSE_BASE_URL"] = "https://example.invalid"
        os.environ["LANGFUSE_PROJECT_ID"] = "cm-test-project-id-xxxxx"
        LF.set_client_for_tests(FakeClient(), enabled=True, configured=True)
        blob = json.dumps(LF.status())
        self.assertNotIn("pk-lf-", blob)
        self.assertNotIn("sk-lf-", blob)
        self.assertNotIn("TESTNOTAREAL", blob)
        self.assertNotIn("example.invalid", blob)
        self.assertNotIn("cm-test-project", blob)
        self.assertTrue(LF.status()["base_url_set"])
        self.assertTrue(LF.status()["project_id_set"])

    def test_redact_keys_and_otp(self):
        raw = "Authorization: Bearer sk-lf-TESTNOTAREALKEY000000000000000 otp is 123456 for login, GROQ_API_KEY=gsk_abc123def456"
        out = LF.redact(raw)
        self.assertNotIn("sk-lf-TEST", out)
        self.assertNotIn("123456", out)
        self.assertNotIn("gsk_abc123def456", out)
        self.assertIn("[redacted]", out)
        self.assertIn("****", out)

    def test_safe_input_truncates_and_redacts(self):
        msgs = [{"role": "user", "content": "key=sk-lf-TESTNOTAREALKEY000000000000000 " + ("x" * 8000)}]
        inp = LF.safe_input(msgs)
        self.assertEqual(len(inp), 1)
        self.assertNotIn("sk-lf-TEST", inp[0]["content"])
        self.assertLessEqual(len(inp[0]["content"]), 4100)

    def test_observation_records_and_updates(self):
        client = FakeClient()
        LF.set_client_for_tests(client)
        with LF.observation("router.complete", as_type="span", input={"q": "hi"}, metadata={"n": 1}) as obs:
            LF.safe_update(obs, output={"ok": True})
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0]["name"], "router.complete")
        self.assertEqual(client.calls[0]["as_type"], "span")
        self.assertTrue(any("ok" in (u.get("output") or {}) for u in client.obs[0].updates))

    def test_observation_fail_open_on_client_error(self):
        LF.set_client_for_tests(FakeClient(boom=True))
        with LF.observation("boom") as obs:
            self.assertIs(obs, LF._NOOP)
            obs.update(output="still-ok")

    def test_startup_ping_is_safe_without_keys(self):
        LF.startup_ping()  # must not raise
        client = FakeClient()
        LF.set_client_for_tests(client)
        LF.startup_ping()
        self.assertEqual(client.calls[0]["name"], "bb.startup")
        self.assertEqual(client.calls[0]["input"], {"event": "startup"})


class RouterTracing(unittest.TestCase):
    def setUp(self):
        for k in list(os.environ):
            if k.startswith("LANGFUSE_"):
                os.environ.pop(k, None)
        os.environ["BB_LANGFUSE_ENV_FILE"] = "/tmp/bb-langfuse-tests-no-file.env"
        LF.reset_for_tests()
        self._once = RT._once
        self._cool = dict(RT.COOL)
        self._stats = dict(RT.STATS)

    def tearDown(self):
        RT._once = self._once
        RT.COOL.clear(); RT.COOL.update(self._cool)
        RT.STATS.clear(); RT.STATS.update(self._stats)
        LF.reset_for_tests()

    def test_complete_works_when_tracing_off(self):
        async def fake(c, mid, spec, msgs, json_mode, timeout):
            return "hello from model"
        RT._once = fake
        name, text, trace = asyncio.run(RT.complete(
            [{"role": "user", "content": "ping"}],
            chain=["groq:openai/gpt-oss-120b"],
            extra=[("groq:openai/gpt-oss-120b", ("Groq", "http://x", "unused-key", "openai/gpt-oss-120b", "oa"))],
            tries=1,
        ))
        self.assertIn("gpt-oss-120b", name)
        self.assertEqual(text, "hello from model")
        self.assertTrue(trace)

    def test_complete_records_generation_and_redacts_secrets(self):
        client = FakeClient()
        LF.set_client_for_tests(client)
        async def fake(c, mid, spec, msgs, json_mode, timeout):
            return "answer"
        RT._once = fake
        secret_msg = [{"role": "user", "content": "my key is sk-lf-TESTNOTAREALKEY000000000000000"}]
        name, text, trace = asyncio.run(RT.complete(
            secret_msg,
            chain=["groq:openai/gpt-oss-120b"],
            extra=[("groq:openai/gpt-oss-120b", ("Groq", "http://x", "unused-key", "openai/gpt-oss-120b", "oa"))],
            tries=1,
        ))
        self.assertEqual(text, "answer")
        names = [c["name"] for c in client.calls]
        self.assertIn("router.complete", names)
        self.assertTrue(any(n.startswith("llm.") for n in names))
        dumped = json.dumps(client.calls)
        self.assertNotIn("sk-lf-TEST", dumped)
        self.assertNotIn("unused-key", dumped)

    def test_complete_fail_open_when_langfuse_down(self):
        LF.set_client_for_tests(FakeClient(boom=True))
        async def fake(c, mid, spec, msgs, json_mode, timeout):
            return "still works"
        RT._once = fake
        name, text, trace = asyncio.run(RT.complete(
            [{"role": "user", "content": "ping"}],
            chain=["groq:openai/gpt-oss-120b"],
            extra=[("groq:openai/gpt-oss-120b", ("Groq", "http://x", "unused-key", "openai/gpt-oss-120b", "oa"))],
            tries=1,
        ))
        self.assertEqual(text, "still works")

    def test_complete_records_error_then_raises(self):
        client = FakeClient()
        LF.set_client_for_tests(client)
        async def boom(c, mid, spec, msgs, json_mode, timeout):
            raise RT.ModelError("fatal", "nope")
        RT._once = boom
        with self.assertRaises(RT.ModelError):
            asyncio.run(RT.complete(
                [{"role": "user", "content": "ping"}],
                chain=["groq:openai/gpt-oss-120b"],
                extra=[("groq:openai/gpt-oss-120b", ("Groq", "http://x", "unused-key", "openai/gpt-oss-120b", "oa"))],
                tries=1,
            ))
        levels = [u.get("level") for o in client.obs for u in o.updates]
        self.assertIn("ERROR", levels)
        # error bodies / keys must not appear
        dumped = json.dumps(client.calls) + json.dumps([u for o in client.obs for u in o.updates])
        self.assertNotIn("unused-key", dumped)


if __name__ == "__main__":
    unittest.main()
