"""Sentinel gate (P0, inspired by Meta Muse Sentinel pattern; own code).
ONE place that classifies outgoing / irreversible actions:
  send    : sms_send, call_make, mcp tools that send/post/email/message, Telegram sends
  post    : mcp tools that publish/post/tweet/upload
  pay     : plan payment decisions, any tool mentioning pay/charge/transfer
  control : click/tap/type_text/swipe/keyevent (Royal Link screen control)
  account : settings_ctl, plan changes, owner auth/password, connection add/remove
Rules: gated actions ALWAYS need an explicit approval card (never 'always allow'), and every
decision (asked / approved / denied / executed) is written to audit_events via auditdb (jsonl fallback).
Multi-way: if audit DB write fails, auditdb still appends audit.jsonl; if both fail we still block nothing silently
-- check() itself never raises."""
import re, os, json
try: import auditdb as _A
except Exception: _A=None
# ---- v2: one policy file (sentinel_policy.json) is the source of truth for every tool's risk tier ----
_BUILTIN={"tools":{"sms_send":"send","sms_fill":"send","call_make":"send","settings_ctl":"account","app_stop":"account",
         "browser_act":"control","click":"control","tap":"control","type_text":"control","type":"control","swipe":"control","keyevent":"control"},
         "gated_tiers":["control","send","post","pay","account"],"max_actions_per_task":25,"untrusted_sources":[],
         "sensitive_sources":[],"blocked":[]}
def _load_policy():
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"sentinel_policy.json"),encoding="utf-8") as f: p=json.load(f)
        if not isinstance(p.get("tools"),dict): raise ValueError("bad policy")
        # fail-safe: the built-in gated tools can never be downgraded by an edited policy file
        for t,c in _BUILTIN["tools"].items(): p["tools"][t]=c
        for k,v in _BUILTIN.items(): p.setdefault(k,v)
        return p
    except Exception: return dict(_BUILTIN)
POLICY=_load_policy()
GATED=set(POLICY["gated_tiers"])|set(_BUILTIN["gated_tiers"])
UNTRUSTED=set(POLICY.get("untrusted_sources") or [])
SENSITIVE=set(POLICY.get("sensitive_sources") or [])
TOOL_CAT={t:c for t,c in POLICY["tools"].items() if c in GATED}
_SEND=re.compile(r"(send|email|mail|message|reply|sms|whatsapp|telegram|dm\b|invite)",re.I)
_POST=re.compile(r"(post|publish|tweet|upload|share|comment|schedule_post)",re.I)
_PAY=re.compile(r"(pay|charge|checkout|purchase|transfer|refund|invoice|order)",re.I)
_ACCT=re.compile(r"(delete_account|password|signup|sign_up|create_account|oauth|revoke|add_member|remove_member)",re.I)
def category(tool,args=None):
    """Return send/post/pay/account or None. mcp_call is classified by the inner tool name."""
    args=args or {}
    if tool in TOOL_CAT: return TOOL_CAT[tool]
    name=str(args.get("tool","")) if tool=="mcp_call" else ""
    if not name: return None
    for cat,rx in (("pay",_PAY),("account",_ACCT),("post",_POST),("send",_SEND)):
        if rx.search(name): return cat
    return None
def gated(tool,args=None): return category(tool,args) is not None
def tier(tool,args=None):
    """read|act|control|send|post|pay|account. Unknown tools are 'act' (fail-closed: never auto 'read')."""
    c=category(tool,args)
    if c: return c
    return POLICY["tools"].get(tool,"act")
def pre_call(tool,args=None,tainted=False,actions=0):
    """Decide before ANY tool call. Returns {"block":bool,"card":bool,"tier":str,"reason":str}. Never raises.
    block: policy-blocked tool, or the task already used its action budget.
    card : gated tier always; 'act' after the task read untrusted data (prompt-injection defence)."""
    try:
        t=tier(tool,args)
        if tool in (POLICY.get("blocked") or []): return {"block":True,"card":False,"tier":t,"reason":"policy_blocked"}
        if t!="read" and actions>=int(POLICY.get("max_actions_per_task",25)): return {"block":True,"card":False,"tier":t,"reason":"action_budget"}
        if t in GATED: return {"block":False,"card":True,"tier":t,"reason":"gated_"+t}
        if t=="act" and tainted: return {"block":False,"card":True,"tier":t,"reason":"tainted_act"}
        return {"block":False,"card":False,"tier":t,"reason":"ok"}
    except Exception:
        return {"block":False,"card":True,"tier":"act","reason":"sentinel_error"}
def log(stage,cat,who=None,**k):
    """stage: asked|approved|denied|executed|blocked. Never raises."""
    try:
        if _A: _A.write(ev="sentinel_"+stage,cat=cat,user=who,**{a:(str(b)[:300]) for a,b in k.items()})
    except Exception: pass
