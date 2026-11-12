# P1 slice 1 — MCP 2026-07-28 client + browser agent foundation (branch `p1-mcp-browser`)

Base: `gh/main` @ `1054ced` (no newer commits on main at 2026-11-12 10:46 Asia/Dhaka). Local only: not pushed, not deployed.

## What changed
| File | Change |
|---|---|
| `mcp_client.py` (new) | Dual-era MCP Streamable HTTP client. Probes `server/discover` with `2026-07-28` (`_meta` protocolVersion/clientInfo/clientCapabilities, headers `MCP-Protocol-Version`, `Mcp-Method`, `Mcp-Name` w/ `=?base64?…?=` encoding). Recognised modern errors (`-32020/-32021/-32022`) are NOT downgraded (−32022 retries a listed version, or goes legacy if only legacy versions are listed); anything else (e.g. 400 `-32600 Missing session ID`, plain 404/405) → legacy `initialize` with `2025-06-18` + `Mcp-Session-Id`, using the server's negotiated version afterwards. Era cached per URL 1 h, re-probed once if the cached assumption fails. MRTR `input_required` → clear error, never auto-answered (we advertise no client capabilities). |
| `connections.py` | `mcp_tools` / `mcp_call` use `mcp_client`; same UX, same tool-list shape, errors still raise. `_rpc` / `mcp_session` kept as legacy wrappers. |
| `browser_agent.py` (new) | Supervised browser agent: tools `browser_navigate` (act), `browser_read` (read), `browser_act` (control), `browser_close` (read). Flag `feat_browser_agent` default **OFF**; domain allowlist (`app_settings.browser_agent_allow` or env `BB_BROWSER_AGENT_ALLOW`), default **empty = deny all**; document requests (incl. iframes) must be allowlisted, sub-resources must be public; final URL re-checked after every navigate/act (off-list → `about:blank`, no screenshot); separate persistent Chromium profile `~/.bb_browser_agent/profile`; screenshot after every successful step + step log. `browser_use_config()` = matching browser-use 1.0 `Browser('chromium', …)` kwargs (not executed). |
| `agent.py` | Browser tools advertised/accepted only when `BA.enabled()`; dispatch to `BA.run`; `browser_navigate` + `browser_act` always force an Approve card (beta); browser session closed at task end. Restricted users never get them (not in SAFE_TOOLS). |
| `sentinel_policy.json` v3, `sentinel.py` | +4 tool tiers (38 total); browser page tools are untrusted sources; `browser_act=control` added to the built-in non-downgradable set. |
| `quarantine.py` | browser tools added to `WEB_TOOLS` (long page text → tool-less JSON extraction). |
| `flags.py` | `feat_browser_agent` ("0"), also off when `feat_agent` is off. |
| `requirements-browser-agent.txt` (new) | Optional pin `browser-use==1.0.2` — NOT in `requirements-render.txt`. |
| tests | `test_mcp_client.py` (15, mocked HTTP), `test_browser_agent.py` (19, no browser/network), `test_mcp_interop.py` (2, skipped unless env set), `test_sentinel_quarantine.py` version 2→3. `evals/golden_bn.jsonl` +3 browser cases (53). |

## Test results (box, venv from requirements-render.txt, Python 3.13)
- Unit: `python -m unittest discover -s tests` → **98 tests, OK (2 interop tests skipped without env)**.
- Eval gate: `python evals/run_golden.py` → **offline 53/53 pass** (no `--live`; no paid APIs).
- CI parity: py_compile + pyflakes (no undefined names) + `node --check` OK; app boot on a throw-away HOME → `/bb/health` ok, `/`, `/login`, `/admin`, `/privacy` = 200; deep health shows Sentinel policy 3 / 38 tools.
- Real interop: our client vs official **mcp 2.3.0** `MCPServer` (modern, 2026-07-28) and **mcp 1.30.0** `FastMCP` (legacy, falls back to 2025-06-18) — list + call OK both.
- Real Chrome smoke (system google-chrome, temp profile, allowlist `example.com`): navigate/read OK with screenshots; navigate to iana.org refused; clicking a link to iana.org blocked by route guard and reset to `about:blank`.

## Live-spec notes vs the plan
- MCP 2026-07-28 is fully stateless: no `initialize`, no `Mcp-Session-Id`, no GET stream; `server/discover` is MUST for servers; `tools/list` results carry `ttlMs`/`cacheScope` (not used yet). Official Python SDK is **v2.x (2.3.0 latest, MIT)**; we did not add it to production — the hand-rolled httpx client keeps the Render image unchanged and is proven against both SDK eras.
- browser-use: latest stable **1.0.2** (2026-11-11), 1.0.3rc1 out 2026-11-12. 1.0 is a REPL-on-CDP rewrite; defaults are the **paid** Browser Use Cloud browser + `bu-fast` gateway, telemetry ON; its domain guard is explicitly "not a sandbox" (sub-resources + REPL Python networking unfiltered). Hence it is not wired; our own step engine carries Sentinel per step.

## Not done / risks
- Not deployed; flag stays OFF even after a deploy until যাহাঁপনা turns it on and sets an allowlist.
- Render image has no Playwright Chromium / google-chrome → browser agent would error there until `playwright install chromium` (memory cost on free tier) — or keep it box-only.
- Blocked steps return no screenshot (by design: nothing from an off-list page is captured).
- No MRTR elicitation/sampling support; no `subscriptions/listen`; no `ttlMs` caching; no `x-mcp-header` `Mcp-Param-*` headers (servers that require them answer `-32020`; we surface the error rather than downgrade).
- MCP stdio transport not supported (same as before).
- Admin UI shows the new flag automatically via `FL.all_flags()`; no UI to edit `browser_agent_allow` yet (set via app_settings).

## Next steps
1. Owner review → merge → deploy (CI runs all tests + eval gate). Then test one real remote MCP server via Connections.
2. Admin field for `browser_agent_allow` + browser step timeline (screenshots) in v4 task view.
3. Memory v2 (P1): bi-temporal facts + PRIVATE chain only; eval cases for recall/forget.
4. Bangla voice (P1): free STT/TTS chain check (Deepgram/Cartesia quota still unverified).
5. Optional: MCP `tools/list` ttl cache, `Mcp-Param-*` headers, elicitation → Approve card bridge.
