"""Fail-open Langfuse tracing for The Royal Bengal Tiger.

Official Python SDK (v5), env-driven. Missing keys, a missing package, or a
Langfuse outage must never break a user request. Secrets are redacted before
they are sent and are never logged.
"""
from __future__ import annotations
import logging, os, re, contextlib
from typing import Any, Optional

log = logging.getLogger("lftrace")

_MAX_STR = 4000
_MAX_MSGS = 12
_SECRET_FILE = os.path.expanduser("~/.secrets/langfuse.env")

# Values that look like keys, bearer tokens, or assignment of secrets.
_KEYISH = re.compile(
    r"\b(?:sk-lf-|pk-lf-|sk-|rk-|xox[baprs]-|ghp_|github_pat_|Bearer\s+)[A-Za-z0-9_\-.]{8,}",
    re.I,
)
_ASSIGN = re.compile(
    r"(?i)((?:api[_-]?key|secret[_-]?key|access[_-]?token|refresh[_-]?token|password|passwd|authorization|bearer|private[_-]?key)"
    r"['\"]?\s*[=:]\s*['\"]?)([^\s'\"&,;]+)"
)
_OTP = re.compile(
    r"(?i)(OTP|one[ -]?time|verification code|কোড|পিন|PIN)([^0-9]{0,24})([0-9]{4,8})"
)

_ST = {
    "init": False,
    "enabled": False,
    "configured": False,
    "client": None,
    "reason": "not-initialized",
}


class _Noop:
    def update(self, *a, **k):
        return self

    def end(self):
        return self


_NOOP = _Noop()


def _truthy(v: Optional[str], default: bool = True) -> bool:
    if v is None or str(v).strip() == "":
        return default
    return str(v).strip().lower() not in ("0", "false", "no", "off")


def _secret_path() -> str:
    # BB_LANGFUSE_ENV_FILE lets tests point at an empty path so the box secret file is never read.
    return os.environ.get("BB_LANGFUSE_ENV_FILE") or _SECRET_FILE

def _load_secret_file() -> None:
    """If process env lacks keys, fill from ~/.secrets/langfuse.env (no overwrite)."""
    try:
        with open(_secret_path()) as f:
            lines = f.readlines()
    except Exception:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k.startswith("LANGFUSE_") and v and not (os.environ.get(k) or "").strip():
            os.environ[k] = v


def _has_keys() -> bool:
    return bool(
        (os.environ.get("LANGFUSE_PUBLIC_KEY") or "").strip()
        and (os.environ.get("LANGFUSE_SECRET_KEY") or "").strip()
    )


def _valid_env(name: str) -> bool:
    return bool(re.fullmatch(r"(?!langfuse)[a-z0-9][a-z0-9_-]*", name or ""))


def redact(text: Any) -> Any:
    """Strip key-like and OTP-like values. Non-strings pass through recursively."""
    if text is None:
        return None
    if isinstance(text, str):
        t = _ASSIGN.sub(r"\1[redacted]", text)
        t = _KEYISH.sub("[redacted]", t)
        t = _OTP.sub(r"\1\2****", t)
        return t
    if isinstance(text, dict):
        return {str(k): redact(v) for k, v in text.items()}
    if isinstance(text, (list, tuple)):
        return [redact(v) for v in text]
    return text


def clip(text: Any, n: int = _MAX_STR) -> Any:
    if text is None:
        return None
    if not isinstance(text, str):
        text = redact(text)
        if not isinstance(text, str):
            return text
    t = redact(text)
    if len(t) > n:
        return t[:n] + f"…(+{len(t)-n} chars)"
    return t


def safe_input(msgs) -> list:
    """Sanitized, truncated chat messages for observation input."""
    out = []
    try:
        seq = list(msgs or [])[-_MAX_MSGS:]
    except Exception:
        return []
    for m in seq:
        try:
            role = (m or {}).get("role", "")
            content = (m or {}).get("content", "")
            if not isinstance(content, str):
                content = str(content)
            out.append({"role": role, "content": clip(content)})
        except Exception:
            continue
    return out


def safe_update(obs, **kwargs) -> None:
    if obs is None or obs is _NOOP:
        return
    try:
        payload = {}
        for k, v in kwargs.items():
            if k in ("input", "output", "metadata", "status_message") and v is not None:
                payload[k] = redact(v) if k != "metadata" else redact(v)
            else:
                payload[k] = v
        obs.update(**payload)
    except Exception:
        log.debug("langfuse update failed", exc_info=False)


def status() -> dict:
    """Safe health snapshot — no keys, no host, no secrets."""
    _ensure()
    return {
        "configured": bool(_ST["configured"]),
        "enabled": bool(_ST["enabled"]),
        "reason": _ST["reason"] if not _ST["enabled"] else "ok",
        "base_url_set": bool((os.environ.get("LANGFUSE_BASE_URL") or "").strip()),
        "project_id_set": bool((os.environ.get("LANGFUSE_PROJECT_ID") or "").strip()),
    }


def reset_for_tests() -> None:
    _ST.update(init=False, enabled=False, configured=False, client=None, reason="not-initialized")


def set_client_for_tests(client, enabled: bool = True, configured: bool = True) -> None:
    _ST.update(init=True, enabled=enabled, configured=configured, client=client, reason="test")


def _ensure() -> None:
    if _ST["init"]:
        return
    _ST["init"] = True
    try:
        _load_secret_file()
    except Exception:
        pass
    if not _truthy(os.environ.get("LANGFUSE_TRACING_ENABLED"), True):
        _ST["reason"] = "disabled"
        return
    if not _has_keys():
        _ST["configured"] = False
        _ST["reason"] = "missing-keys"
        return
    _ST["configured"] = True
    try:
        from langfuse import Langfuse
        release = (os.environ.get("RENDER_GIT_COMMIT") or os.environ.get("BB_COMMIT") or "")[:12] or None
        raw_env = (os.environ.get("LANGFUSE_TRACING_ENVIRONMENT") or os.environ.get("BB_NODE") or "default").strip().lower()
        env_name = raw_env if _valid_env(raw_env) else "default"
        _ST["client"] = Langfuse(
            public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
            base_url=(os.environ.get("LANGFUSE_BASE_URL") or "https://cloud.langfuse.com").strip(),
            environment=env_name,
            release=release,
            timeout=5,
            mask=lambda x: redact(x),
        )
        _ST["enabled"] = True
        _ST["reason"] = "ok"
    except Exception:
        _ST["client"] = None
        _ST["enabled"] = False
        _ST["reason"] = "init-failed"
        log.warning("Langfuse init failed; tracing disabled (fail-open)")


@contextlib.contextmanager
def observation(name: str, as_type: str = "span", **kwargs):
    """Create a current observation, or a no-op if tracing is off or Langfuse errors."""
    _ensure()
    client = _ST["client"] if _ST["enabled"] else None
    if client is None:
        yield _NOOP
        return
    kw = dict(kwargs)
    if "input" in kw:
        kw["input"] = redact(kw["input"])
    if "output" in kw:
        kw["output"] = redact(kw["output"])
    if "metadata" in kw and kw["metadata"] is not None:
        kw["metadata"] = redact(kw["metadata"])
    ctx = None
    try:
        ctx = client.start_as_current_observation(as_type=as_type, name=name, **kw)
        obs = ctx.__enter__()
    except Exception:
        log.debug("langfuse observation start failed", exc_info=False)
        yield _NOOP
        return
    exc = None
    try:
        yield obs
    except BaseException as e:
        exc = e
        safe_update(obs, level="ERROR", status_message=type(e).__name__)
        raise
    finally:
        try:
            if exc is None:
                ctx.__exit__(None, None, None)
            else:
                ctx.__exit__(type(exc), exc, exc.__traceback__)
        except Exception:
            pass


@contextlib.contextmanager
def attrs(**kwargs):
    """Propagate user_id / session_id / tags / metadata. Fail-open."""
    _ensure()
    client = _ST["client"] if _ST["enabled"] else None
    kwargs = {k: v for k, v in kwargs.items() if v is not None and v != ""}
    if client is None or not kwargs:
        yield
        return
    try:
        from langfuse import propagate_attributes
        with propagate_attributes(**kwargs):
            yield
    except Exception:
        log.debug("langfuse propagate_attributes failed", exc_info=False)
        yield


def wrap_async(name: str, as_type: str = "span", input_fn=None, meta_fn=None, attr_fn=None):
    """Decorator: wrap an async function in an observation, fail-open."""
    def dec(fn):
        async def wrapper(*a, **k):
            inp = input_fn(*a, **k) if input_fn else None
            meta = meta_fn(*a, **k) if meta_fn else None
            at = attr_fn(*a, **k) if attr_fn else {}
            with observation(name, as_type=as_type, input=inp, metadata=meta) as obs:
                with attrs(**(at or {})):
                    return await fn(*a, **k)
            # obs kept only so the context manager can record errors
            _ = obs
        wrapper.__name__ = getattr(fn, "__name__", name)
        wrapper.__wrapped__ = fn
        return wrapper
    return dec


def startup_ping() -> None:
    """One cheap, secret-free boot trace. Never raises."""
    try:
        if not _has_keys() and not _ST["init"]:
            # still allow file-based keys
            pass
        with observation(
            "bb.startup",
            as_type="span",
            input={"event": "startup"},
            metadata={
                "node": os.environ.get("BB_NODE", "box"),
                "commit": (os.environ.get("RENDER_GIT_COMMIT") or os.environ.get("BB_COMMIT") or "")[:7],
            },
        ) as sp:
            safe_update(sp, output={"ok": True})
    except Exception:
        pass


def flush() -> None:
    try:
        c = _ST.get("client")
        if c is not None:
            c.flush()
    except Exception:
        pass
