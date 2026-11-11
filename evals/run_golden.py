"""P0 eval gate. Offline (CI): Sentinel policy + injection detector on evals/golden_bn.jsonl, must be 100%.
--live: also asks the real router a few Bangla questions (needs keys; never run in CI)."""
import os, sys, json, asyncio
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0,ROOT)
import sentinel as SN, quarantine as QZ
def run_offline(path):
    ok=bad=0; fails=[]
    for ln in open(path,encoding="utf-8"):
        c=json.loads(ln)
        if c["kind"]=="sentinel":
            r=SN.pre_call(c["tool"],c.get("args"),c.get("tainted",False),c.get("actions",0))
            good=all(r.get(k)==v for k,v in c["expect"].items())
        else:
            good=bool(QZ.suspicious(c["text"]))==c["expect"]["flagged"]
        if good: ok+=1
        else: bad+=1; fails.append(c["id"])
    return ok,bad,fails
LIVE=[("বাংলাদেশের রাজধানীর নাম কী? এক শব্দে বলো।",["ঢাকা"]),("২ আর ৩ যোগ করলে কত? শুধু সংখ্যা।",["5","৫"]),
      ("Reply with the single word: PONG",["PONG"])]
async def run_live():
    import router as RT
    res=[]
    for q,want in LIVE:
        try: m,t,_=await RT.complete([{"role":"user","content":q}],timeout=40,tries=1); res.append((q,m,any(w in t for w in want),t[:80]))
        except Exception as e: res.append((q,"none",False,str(e)[:80]))
    return res
if __name__=="__main__":
    ok,bad,fails=run_offline(os.path.join(os.path.dirname(os.path.abspath(__file__)),"golden_bn.jsonl"))
    print(f"offline: {ok}/{ok+bad} pass"+(f"  FAIL: {fails}" if fails else ""))
    rc=1 if bad else 0
    if "--live" in sys.argv:
        for q,m,g,t in asyncio.run(run_live()): print(("PASS" if g else "FAIL"),m,"|",q,"->",t.replace("\n"," "))
    sys.exit(rc)
