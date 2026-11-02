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

## Phase C — live view (added)
- **Frames stored as files**, not DB blobs: `data/live_frames/<device>/<uuid>.jpg|png` (JPEG/PNG magic checked, ≤600 KB, newest 60 per device kept, git-ignored). Served only via admin-only `GET /bb/link/frame/{device}/{file}` (no-store).
- Frames are accepted only when the owner turned **Live frames ON** for that device (`POST /bb/api/devices/{id}/live {"on":true}`; default OFF, resets OFF on server restart, audited `link_live_toggle`). The server pushes `{"type":"live","on":..}` to the tray; the tray then sends 480px q40 frames every 3s **only while a job runs**. `BB_LIVE_FRAMES=1` on the PC still works as a local override.
- Server adds a `thinking` step ("পাঠানো হলো / sent: action") on dispatch; screenshot results add a `screenshot` step with the image URL.
- `GET /bb/link/steps?device=&since=` (admin-only now) → `{online, live, steps[{t,cid,phase,text,frame?}], latest_frame, now}`.
- **Live view page:** `/bb/live` (admin-only) — device picker, Connected/Offline pill, Bengali+English step timeline, latest screen, live-frame toggle. Polls every 1.5s.
- Permissions untouched: the toggle only controls frames; Ask/Always/Never still gate every action.
