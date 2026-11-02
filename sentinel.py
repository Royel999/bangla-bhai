"""Sentinel gate (P0, inspired by Meta Muse Sentinel pattern; own code).
ONE place that classifies outgoing / irreversible actions:
  send    : sms_send, call_make, mcp tools that send/post/email/message, Telegram sends
  post    : mcp tools that publish/post/tweet/upload
  pay     : plan payment decisions, any tool mentioning pay/charge/transfer
  account : settings_ctl, plan changes, owner auth/password, connection add/remove
Rules: gated actions ALWAYS need an explicit approval card (never 'always allow'), and every
decision (asked / approved / denied / executed) is written to audit_events via auditdb (jsonl fallback).
Multi-way: if audit DB write fails, auditdb still appends audit.jsonl; if both fail we still block nothing silently
-- check() itself never raises."""
import re
try: import auditdb as _A
except Exception: _A=None
TOOL_CAT={"sms_send":"send","call_make":"send","settings_ctl":"account","app_stop":"account"}
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
def log(stage,cat,who=None,**k):
    """stage: asked|approved|denied|executed|blocked. Never raises."""
    try:
        if _A: _A.write(ev="sentinel_"+stage,cat=cat,user=who,**{a:(str(b)[:300]) for a,b in k.items()})
    except Exception: pass
