# Royal Link Device Hub v1 — The Royal Bengal Tiger

## Gaps found in the old protocol (origin/main)
1. No app-level heartbeat; "online" = DB last_seen < 40s, only touched on results → idle devices looked offline.
2. A job was popped from the queue and sent; if the socket dropped before the result, it was **lost** (caller waited 120s then failed).
3. Reconnect with the same token opened a second push task on the same queue → an old half-dead socket could steal jobs.
4. Client `on_close` recursed into `loop_ws` with a fixed 3s sleep (stack growth, reconnect storms, no backoff).
5. No structured progress events → no Siri-like live view possible.
6. Tray tooltip did not distinguish Connected / Reconnecting / Offline.

## What v1 does (`device_hub.py`, `app.py` /bb/link/ws, /bb/link/poll, /bb/link/steps)
- **Heartbeat:** server sends `hello{hb:20,timeout:60}`, then `ping` every 20s. Any frame from the device updates its beat. Silent >60s ⇒ audit `link_hb_timeout`, socket closed (4408), device shows offline (`AG.devices()` uses hub beat + last_seen).
- **Reconnect / sessions:** each socket gets a session id; the newest session for a device wins, older push loops stop and hand their job back to the queue.
- **Pending queue:** sent-but-unanswered jobs are tracked per device; on disconnect they are re-queued (max 3 attempts, 120s TTL; expired ones dropped + audited). Client de-dups by cid and resends a cached result instead of re-running an action. In-memory: survives disconnects, not a server restart.
- **Live steps:** device → `{"type":"step","cid","phase":thinking|running|screenshot|done|error,"text"}`; kept in a 200-entry ring per device; owner-only `GET /bb/link/steps?device=..&since=..`.
- **Audit:** link_session, link_ws_open/close, link_dispatch (with attempt), link_requeue, link_drop, link_hb_timeout, link_step, link_result.
- **Permissions:** unchanged. Ask/Always/Never checks happen before `device_call`; the hub only transports already-approved jobs.
- Old clients (only `{cid,result}`) keep working; they simply ignore hello/ping.

## Not yet (next phase)
- UI panel streaming `/bb/link/steps` (Phase C). Live frame images (`frame_b64`) are sent by the tray only with BB_LIVE_FRAMES=1 and are currently discarded by the server (only text stored) — wire into media store in Phase C.
- Android client still uses the old protocol (works, but without the new pong/steps).

## Test
```
venv/bin/python scripts/smoke_device_hub.py
python3 -m venv /tmp/rltest && /tmp/rltest/bin/pip install websocket-client websockets && /tmp/rltest/bin/python scripts/e2e_tray_reconnect.py
```
