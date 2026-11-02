#!/usr/bin/env python3
"""Smoke test for device_hub (no network, no production): heartbeat, reconnect re-queue, TTL, steps."""
import sys,os,asyncio,time
sys.path.insert(0,os.path.join(os.path.dirname(__file__),".."))
import device_hub as DH
log=[]; DH.set_audit(lambda **k: log.append(k))
async def main():
    q=asyncio.Queue(); did="dev1"
    DH.open_session(did,"s1"); assert DH.online(did)
    await q.put({"cid":"a1","action":"screenshot","args":{}})
    job=await DH.next_job(q,did); DH.mark_sent(did,job); assert job["attempt"]==1
    # socket drops before result -> re-queued
    assert DH.close_session(did,"s1",q)==1 and q.qsize()==1
    DH.open_session(did,"s2")  # reconnect, same token
    job=await DH.next_job(q,did); assert job["cid"]=="a1" and job["attempt"]==2
    DH.mark_sent(did,job); DH.mark_done(did,"a1"); assert DH.close_session(did,"s2",q)==0
    # max attempts
    j={"cid":"b","action":"x","attempt":DH.MAX_ATTEMPTS}; DH.mark_sent(did,j); assert DH.close_session(did,"zz",q)==0
    # TTL
    await q.put({"cid":"old","action":"x","ts":time.time()-DH.PENDING_TTL-1}); await q.put({"cid":"new","action":"x"})
    assert (await DH.next_job(q,did))["cid"]=="new"
    # session replace
    DH.open_session(did,"s3"); DH.open_session(did,"s4"); assert not DH.is_current(did,"s3")
    # heartbeat timeout
    DH.LAST_BEAT[did]=time.time()-DH.HB_TIMEOUT-1; assert not DH.online(did); DH.beat(did); assert DH.online(did)
    # steps
    assert DH.add_step(did,{"phase":"thinking","cid":"c"}) and not DH.add_step(did,{"phase":"hack"})
    for ph in ("running","screenshot","done"): DH.add_step(did,{"phase":ph,"cid":"c"})
    assert [e["phase"] for e in DH.steps(did)]==["thinking","running","screenshot","done"]
    assert any(e["ev"]=="link_requeue" for e in log) and any(e["ev"]=="link_drop" for e in log)
    print("OK device_hub smoke:",len(log),"audit events")
asyncio.run(main())

# Phase C: frames
import tempfile,base64
DH.FRAME_DIR=tempfile.mkdtemp()
jpg=base64.b64encode(b"\xff\xd8\xff"+b"0"*100).decode()
fn=DH.save_frame("dev1",jpg); assert fn and DH.frame_path("dev1",fn)
assert DH.save_frame("../x",jpg) is None and DH.save_frame("dev1",base64.b64encode(b"MZhack").decode()) is None
assert DH.frame_path("dev1","../../etc/passwd") is None
DH.FRAME_KEEP=3
for _ in range(6): DH.save_frame("dev1",jpg)
assert len(os.listdir(os.path.join(DH.FRAME_DIR,"dev1")))==3
print("OK frames")
