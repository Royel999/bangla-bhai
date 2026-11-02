# Mock-server e2e for the tray client (needs: pip install websocket-client websockets). Not touching production.
import asyncio,json,os,subprocess,sys,websockets
got=[];conns=[0]
async def h(ws):
    conns[0]+=1
    await ws.send(json.dumps({"type":"hello"}))
    if conns[0]==1:
        await ws.send(json.dumps({"type":"ping","t":1})); await ws.send(json.dumps({"cid":"j1","action":"shell","args":{"cmd":"echo hi"}}))
        for _ in range(5): got.append(json.loads(await ws.recv()))
        await ws.close()
    else:
        await ws.send(json.dumps({"cid":"j1","action":"shell","args":{"cmd":"echo hi"}}))  # resend dup
        await ws.send(json.dumps({"cid":"j2","action":"shell","args":{"cmd":"echo two"}}))
        for _ in range(4): got.append(json.loads(await ws.recv()))
        stop.set_result(1)
async def main():
    global stop; stop=asyncio.get_running_loop().create_future()
    async with websockets.serve(h,"127.0.0.1",8765):
        src=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","link","royal_link_tray.py")).read()
        code=src.split("if __name__")[0]+"\nBASE='http://127.0.0.1:8765'\nhttp=lambda *a,**k:{'status':'approved'}\nloop_ws('t')\n"
        p=await asyncio.create_subprocess_exec(sys.executable,"-c",code,stdout=subprocess.DEVNULL)
        await asyncio.wait_for(stop,20); p.kill()
    for g in got: print(g)
    print("conns",conns[0])
asyncio.run(main())
