#!/usr/bin/env python3
"""বাংলা ভাই · Royal Link — tray edition (Windows/Linux/macOS)
WebSocket client (falls back to HTTP poll). On-demand low-res screenshots only.
No hidden/covert mode. Tray icon + consent indicator.
"""
import os,sys,json,time,base64,subprocess,tempfile,threading,queue,traceback
CFG=os.path.expanduser("~/.bangla_bhai_link.json")
BASE=os.environ.get("BB_URL","https://banglabhai.dpdns.org").rstrip("/")
NAME=os.environ.get("BB_NAME") or (os.environ.get("COMPUTERNAME") or os.uname().nodename)
KIND="laptop"
STATUS={"text":"সংযোগ হচ্ছে…","live":None}
try:
    import urllib.request as U
except Exception as e:
    raise SystemExit(e)

def http(method,path,data=None,timeout=35):
    body=None if data is None else json.dumps(data).encode()
    req=U.Request(BASE+path,data=body,method=method,headers={"Content-Type":"application/json","User-Agent":"RoyalLink/1.1"})
    with U.urlopen(req,timeout=timeout) as r: return json.loads(r.read())

def banner(txt):
    STATUS["live"]=txt; STATUS["text"]="🔴 "+txt
    print("\n"+"="*48+f"\n 🔴 {txt}\n"+"="*48,flush=True)

def clear_live(): STATUS["live"]=None; STATUS["text"]="✅ সংযুক্ত · অপেক্ষায়"

def pair():
    if os.path.exists(CFG):
        c=json.load(open(CFG)); st=http("GET",f"/bb/link/status?token={c['token']}")
        if st.get("status")=="approved": return c
    r=http("POST","/bb/link/pair",{"name":NAME,"kind":KIND,"info":{"os":sys.platform,"tray":True,"ws":True}})
    json.dump({"device":r["device"],"token":r["token"]},open(CFG,"w")); 
    try: os.chmod(CFG,0o600)
    except Exception: pass
    STATUS["text"]=f"⏳ অনুমোদন দরকার · id {r['device']}"
    print(f"⏳ ডিভাইস {r['device']} — সেটিংস → অনুমতি কেন্দ্র থেকে যুক্ত করুন")
    while True:
        s=http("GET",f"/bb/link/status?token={r['token']}")
        if s.get("status")=="approved": return {"device":r["device"],"token":r["token"]}
        if s.get("status") in("denied","revoked"): raise SystemExit("অনুমোদন হয়নি")
        time.sleep(3)

def do(action,args):
    try:
        if action=="shell":
            banner(f"শেল: {args.get('cmd','')[:80]}")
            p=subprocess.run(args["cmd"],shell=True,capture_output=True,text=True,timeout=60)
            return {"text":(p.stdout+p.stderr)[-4000:] or "(খালি)"}
        if action=="screenshot":
            # on-demand, low-res (ngrok 1GB/mo) — max width 960
            banner("স্ক্রিনশট (কম রেজো)"); import mss
            from PIL import Image; import io
            with mss.mss() as s:
                img=s.grab(s.monitors[int(args.get("monitor") or 0)])
                im=Image.frombytes("RGB",img.size,img.rgb)
                w=min(960,im.width); h=int(im.height*w/im.width)
                im=im.resize((w,h),Image.BILINEAR)
                buf=io.BytesIO(); im.save(buf,"JPEG",quality=55)
            return {"image_b64":base64.b64encode(buf.getvalue()).decode(),"ext":"jpg","text":f"{w}x{h} jpeg q55"}
        if action=="click":
            banner(f"ক্লিক {args.get('x')},{args.get('y')}"); import pyautogui; pyautogui.FAILSAFE=True
            pyautogui.click(int(args["x"]),int(args["y"])); return {"text":"clicked"}
        if action=="type_text":
            banner("কীবোর্ড"); import pyautogui; pyautogui.write(args["text"],interval=0.02); return {"text":"typed"}
        if action=="camera_photo":
            banner("ক্যামেরা"); import cv2; cam=cv2.VideoCapture(0); time.sleep(.3); ok,fr=cam.read(); cam.release()
            if not ok: return {"error":"ক্যামেরা পড়েনি"}
            # downscale
            h,w=fr.shape[:2]; sc=min(1.0,720/max(w,h)); 
            if sc<1: fr=cv2.resize(fr,(int(w*sc),int(h*sc)))
            _,buf=cv2.imencode(".jpg",fr,[int(cv2.IMWRITE_JPEG_QUALITY),70])
            return {"image_b64":base64.b64encode(buf).decode(),"ext":"jpg","text":"ছবি"}
        if action=="mic_record":
            sec=int(args.get("seconds") or 4); banner(f"মাইক {sec}s")
            import sounddevice as sd, scipy.io.wavfile as wav
            fs=16000; d=sd.rec(int(sec*fs),samplerate=fs,channels=1,dtype="int16"); sd.wait()
            f=tempfile.NamedTemporaryFile(suffix=".wav",delete=False); wav.write(f.name,fs,d)
            b=open(f.name,"rb").read(); os.unlink(f.name)
            return {"image_b64":base64.b64encode(b).decode(),"ext":"wav","text":f"{sec}s"}
        return {"error":f"অজানা: {action}"}
    except Exception as e:
        return {"error":str(e)}
    finally:
        clear_live()

def loop_http(tok):
    while True:
        try: j=http("GET",f"/bb/link/poll?token={tok}",timeout=35)
        except Exception as e: print("poll",e); time.sleep(3); continue
        job=j.get("job")
        if not job: continue
        r=do(job["action"],job.get("args") or {})
        try: http("POST","/bb/link/result",{"token":tok,"cid":job["cid"],"result":r})
        except Exception as e: print("result",e)

def loop_ws(tok):
    try:
        import websocket  # websocket-client
    except ImportError:
        print("websocket-client নেই — HTTP poll"); return loop_http(tok)
    url=BASE.replace("https://","wss://").replace("http://","ws://")+"/bb/link/ws?token="+tok
    def on_msg(ws,msg):
        try: job=json.loads(msg)
        except Exception: return
        if not job.get("cid"): return
        r=do(job["action"],job.get("args") or {})
        ws.send(json.dumps({"cid":job["cid"],"result":r}))
    def on_err(ws,e): print("ws err",e)
    def on_close(ws,*a): print("ws closed — ৩ সেকেন্ড পর আবার"); time.sleep(3); loop_ws(tok)
    def on_open(ws): STATUS["text"]="✅ WebSocket সংযুক্ত"; print("WS open")
    ws=websocket.WebSocketApp(url,on_message=on_msg,on_error=on_err,on_close=on_close,on_open=on_open)
    ws.run_forever(ping_interval=20,ping_timeout=10)

def tray_loop():
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
        print("pystray/Pillow নেই — tray ছাড়া চলবে"); return
    def icon_img(color):
        im=Image.new("RGBA",(64,64),(0,0,0,0)); d=ImageDraw.Draw(im)
        d.ellipse((4,4,60,60),fill=color); d.rectangle((20,28,44,48),fill=(255,215,0,255))
        return im
    def make():
        state=[None]
        def refresh(icon):
            icon.icon=icon_img((200,16,46,255) if STATUS["live"] else (29,78,216,255))
            icon.title="বাংলা ভাই · "+STATUS["text"]
        def quit_(icon,item): icon.stop(); os._exit(0)
        icon=pystray.Icon("bangla_bhai",icon_img((29,78,216,255)),"বাংলা ভাই · Royal Link",
            menu=pystray.Menu(pystray.MenuItem(lambda i: STATUS["text"],None,enabled=False),
                              pystray.MenuItem("বন্ধ করুন",quit_)))
        state[0]=icon
        def tick():
            while True: refresh(icon); time.sleep(1)
        threading.Thread(target=tick,daemon=True).start(); icon.run()
    threading.Thread(target=make,daemon=True).start()

def main():
    global BASE
    if not BASE:
        # first-run dialog
        try:
            import tkinter as tk; from tkinter import simpledialog
            root=tk.Tk(); root.withdraw()
            BASE=simpledialog.askstring("বাংলা ভাই","সার্ভার URL (https://banglabhai.dpdns.org):",parent=root) or ""
            root.destroy()
        except Exception:
            BASE=input("বাংলা ভাই URL: ").strip()
        BASE=BASE.rstrip("/")
        if not BASE: raise SystemExit("URL দরকার")
    print("♛ বাংলা ভাই · Royal Link (tray)"); c=pair(); tray_loop()
    # prefer WS
    try: loop_ws(c["token"])
    except Exception: loop_http(c["token"])

if __name__=="__main__":
    try: main()
    except KeyboardInterrupt: pass
