"""Optional interop check against REAL official MCP SDK servers (skipped in CI unless env vars are set).
  modern: mcp==2.3.0  MCPServer(...).streamable_http_app()   -> BB_MCP_INTEROP_MODERN=http://127.0.0.1:8711/mcp
  legacy: mcp==1.30.0 FastMCP(...).streamable_http_app()     -> BB_MCP_INTEROP_LEGACY=http://127.0.0.1:8712/mcp
Both servers expose a tool `echo(text)` returning 'echo:'+text. Run locally only (http://127.0.0.1)."""
import os, sys, unittest, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mcp_client as M

class Interop(unittest.TestCase):
    def _check(self, env, era):
        url = os.environ.get(env)
        if not url: self.skipTest(env + " not set")
        M._ERA.clear()
        tools, c = asyncio.run(M.list_tools(url, {}))
        self.assertEqual(c.era, era); self.assertIn("echo", [t["name"] for t in tools])
        res, _ = asyncio.run(M.call_tool(url, {}, "echo", {"text": "হ্যালো"}))
        self.assertEqual(res["content"][0]["text"], "echo:হ্যালো")
    def test_modern_sdk_v2(self): self._check("BB_MCP_INTEROP_MODERN", "modern")
    def test_legacy_sdk_v1(self): self._check("BB_MCP_INTEROP_LEGACY", "legacy")

if __name__ == "__main__": unittest.main()
