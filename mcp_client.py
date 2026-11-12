"""Dual-era MCP client (P1, 2026-11-12). Streamable HTTP only, no extra dependency (httpx).

Modern  = MCP 2026-07-28: stateless, no initialize / Mcp-Session-Id. Every request carries
          _meta{io.modelcontextprotocol/protocolVersion, clientInfo, clientCapabilities} plus the
          headers MCP-Protocol-Version, Mcp-Method and (tools/call, resources/read, prompts/get) Mcp-Name.
          We probe with `server/discover` (servers MUST implement it).
Legacy  = 2025-06-18 (and other initialize-era versions): initialize -> notifications/initialized ->
          Mcp-Session-Id. Used when the probe returns anything that is NOT a recognised modern error
          (spec: basic/versioning "Backward Compatibility", transports/streamable-http "Backward Compatibility").
Era is cached per server URL for ERA_TTL seconds and re-probed once if a cached assumption fails.
MRTR (input_required results): we advertise NO client capabilities (no sampling / elicitation / roots),
so a compliant server should not ask; if one does we stop and return a clear message, never auto-answer.
Tool output returned here is still UNTRUSTED: agent.py fences/quarantines it (sentinel UNTRUSTED has mcp_call)."""
import json, time, base64, re
import httpx
MODERN="2026-07-28"
MODERN_VERSIONS=(MODERN,)
LEGACY="2025-06-18"
LEGACY_OK=("2025-11-25","2025-06-18","2025-03-26")
CLIENT_INFO={"name":"bangla-bhai","version":"1.1"}
MODERN_ERR={-32020:"HeaderMismatch",-32021:"MissingRequiredClientCapability",-32022:"UnsupportedProtocolVersion"}
ERA_TTL=3600
_ERA={}   # url -> {"era":"modern"|"legacy","ver":str,"t":float}
TIMEOUT=30
class McpError(RuntimeError):
    def __init__(self,msg,code=None,status=None,data=None,modern=False):
        super().__init__(msg); self.code=code; self.status=status; self.data=data; self.modern=modern
_SAFE=re.compile(r"^[\x21-\x7e](?:[\x20-\x7e]*[\x21-\x7e])?$")
def hval(v):
    """Header-safe value; non-ASCII / edge spaces / sentinel look-alikes use =?base64?...?= (spec Value Encoding)."""
    s=str(v)
    if _SAFE.match(s) and not (s.startswith("=?base64?") and s.endswith("?=")): return s
    return "=?base64?"+base64.b64encode(s.encode()).decode()+"?="
def _client(): return httpx.AsyncClient(timeout=TIMEOUT,follow_redirects=False)
def _parse(r,rid):
    """Return the JSON-RPC message for rid from a JSON or SSE reply (or None)."""
    ct=r.headers.get("content-type","")
    if "text/event-stream" in ct:
        for l in r.text.splitlines():
            if not l.startswith("data:"): continue
            try: j=json.loads(l[5:].strip())
            except Exception: continue
            if isinstance(j,dict) and j.get("id")==rid and ("result" in j or "error" in j): return j
        return None
    try: j=r.json()
    except Exception: return None
    return j if isinstance(j,dict) else None
def _err(j,status):
    e=j.get("error") or {}
    code=e.get("code") if isinstance(e.get("code"),int) else None
    return McpError(str(e.get("message","MCP error"))[:200],code=code,status=status,data=e.get("data"),modern=code in MODERN_ERR)
async def _post(url,hdr,body,extra):
    h={"Content-Type":"application/json","Accept":"application/json, text/event-stream",**extra,**hdr}
    async with _client() as c: return await c.post(url,headers=h,json=body)
# ---------- modern (2026-07-28) ----------
def _meta(ver): return {"io.modelcontextprotocol/protocolVersion":ver,"io.modelcontextprotocol/clientInfo":CLIENT_INFO,
                        "io.modelcontextprotocol/clientCapabilities":{}}
async def modern_rpc(url,hdr,method,params=None,ver=MODERN,rid=1):
    p=dict(params or {}); p["_meta"]={**(p.get("_meta") or {}),**_meta(ver)}
    extra={"MCP-Protocol-Version":ver,"Mcp-Method":method}
    if method in("tools/call","prompts/get") and p.get("name") is not None: extra["Mcp-Name"]=hval(p["name"])
    if method=="resources/read" and p.get("uri") is not None: extra["Mcp-Name"]=hval(p["uri"])
    r=await _post(url,hdr,{"jsonrpc":"2.0","id":rid,"method":method,"params":p},extra)
    j=_parse(r,rid)
    if j and j.get("error"): raise _err(j,r.status_code)
    if r.status_code>=400 or not j: raise McpError(f"MCP server answered HTTP {r.status_code}",status=r.status_code)
    res=j.get("result") or {}
    if isinstance(res,dict) and res.get("resultType")=="input_required":
        raise McpError("MCP server asked for extra input (MRTR elicitation/sampling) — not supported here; use the server's own app",code="input_required")
    return res
async def discover(url,hdr):
    """Probe. Returns ("modern",ver,result) or ("legacy",None,None). Raises only for auth/transport problems
    that would also break legacy (401/403) so the user sees the real cause."""
    try:
        res=await modern_rpc(url,hdr,"server/discover",{},MODERN,rid="discover-1")
        sv=[v for v in (res.get("supportedVersions") or []) if v in MODERN_VERSIONS]
        if sv: return "modern",sv[0],res
        if any(v in LEGACY_OK for v in (res.get("supportedVersions") or [])): return "legacy",None,None
        return "modern",MODERN,res
    except McpError as e:
        if e.status in(401,403): raise
        if e.modern and e.code==-32022:
            sup=list((e.data or {}).get("supported") or [])
            m=[v for v in sup if v in MODERN_VERSIONS]
            if m: return "modern",m[0],None
            if not sup or any(v in LEGACY_OK for v in sup): return "legacy",None,None
            raise McpError("MCP server needs protocol "+", ".join(map(str,sup))[:80]+" — not supported yet")
        if e.modern: raise   # modern server, but our request was wrong: do not silently downgrade
        return "legacy",None,None
    except httpx.HTTPError: raise
# ---------- legacy (initialize era) ----------
async def legacy_rpc(url,hdr,method,params,sid=None,rid=1,ver=LEGACY):
    extra={"MCP-Protocol-Version":ver}
    if sid: extra["Mcp-Session-Id"]=sid
    body={"jsonrpc":"2.0","method":method,"params":params}
    if rid is not None: body["id"]=rid
    r=await _post(url,hdr,body,extra)
    if r.status_code>=400 and rid is None: raise McpError(f"MCP server answered HTTP {r.status_code}",status=r.status_code)
    sid=r.headers.get("mcp-session-id") or sid
    if rid is None: return None,sid
    j=_parse(r,rid)
    if j and j.get("error"): raise _err(j,r.status_code)
    if r.status_code>=400: raise McpError(f"MCP server answered HTTP {r.status_code}",status=r.status_code)
    if not j: raise McpError("No reply from MCP server")
    return j.get("result"),sid
async def legacy_session(url,hdr):
    """initialize with 2025-06-18; use the version the server answers with (if we know it) for later headers."""
    res,sid=await legacy_rpc(url,hdr,"initialize",{"protocolVersion":LEGACY,"capabilities":{},"clientInfo":CLIENT_INFO})
    ver=(res or {}).get("protocolVersion") if isinstance(res,dict) else None
    ver=ver if ver in LEGACY_OK else LEGACY
    try: await legacy_rpc(url,hdr,"notifications/initialized",{},sid,rid=None,ver=ver)
    except Exception: pass
    return sid,ver
# ---------- one entry point ----------
class Conn:
    """Short-lived per-call connection; era decided by discover() (cached)."""
    def __init__(self,url,hdr): self.url=url; self.hdr=hdr; self.era=None; self.ver=None; self.sid=None; self.info=None
    async def open(self,force=False):
        c=_ERA.get(self.url)
        if c and not force and time.time()-c["t"]<ERA_TTL: self.era,self.ver=c["era"],c["ver"]
        else:
            self.era,self.ver,self.info=await discover(self.url,self.hdr)
            _ERA[self.url]={"era":self.era,"ver":self.ver,"t":time.time()}
        if self.era=="legacy": self.sid,self.ver=await legacy_session(self.url,self.hdr)
        return self
    async def request(self,method,params,rid=2):
        if self.era=="modern": return await modern_rpc(self.url,self.hdr,method,params,self.ver,rid)
        res,_=await legacy_rpc(self.url,self.hdr,method,params,self.sid,rid,self.ver); return res
async def connect(url,hdr):
    c=Conn(url,hdr)
    try: return await c.open()
    except McpError:
        if url in _ERA: _ERA.pop(url,None); return await Conn(url,hdr).open(force=True)
        raise
async def call(url,hdr,method,params,rid=2):
    """Run one request; if a CACHED era assumption fails (server upgraded/downgraded), re-probe once."""
    cached=url in _ERA
    c=await connect(url,hdr)
    try: return await c.request(method,params,rid),c
    except McpError as e:
        if not cached or e.code=="input_required" or (e.modern and e.code not in(-32022,)): raise
        _ERA.pop(url,None); c=await Conn(url,hdr).open(force=True)
        return await c.request(method,params,rid),c
async def list_tools(url,hdr):
    res,c=await call(url,hdr,"tools/list",{})
    return (res or {}).get("tools",[]),c
async def call_tool(url,hdr,name,args):
    res,c=await call(url,hdr,"tools/call",{"name":name,"arguments":args},rid=3)
    return res or {},c
def era_of(url):
    c=_ERA.get(url); return (c["era"],c["ver"]) if c else (None,None)
