#!/usr/bin/env python3
"""বাংলা ভাই · Royal Link (ল্যাপটপ/ডেস্কটপ এজেন্ট)
মালিকের অনুমতি নিয়ে ক্যামেরা, মাইক, স্ক্রিন, ব্রাউজার ও শেল কন্ট্রোল।
কোনো কাজ গোপনে হয় না — চালু থাকলে স্ক্রিনে লাল ইন্ডিকেটর দেখায়।
"""
import os,sys,json,time,base64,subprocess,tempfile,threading,queue
try: import urllib.request as U
except: raise SystemExit("Python 3 দরকার")
BASE=(os.environ.get("BB_URL") or "https://banglabhai.dpdns.org").rstrip("/")
NAME=os.environ.get("BB_NAME") or (os.environ.get("COMPUTERNAME") or os.uname().nodename)
KIND="laptop"; CFG=os.path.expanduser("~/.bangla_bhai_link.json")
def post(path,data=None,tok=None):
    req=U.Request(BASE+path,data=None if data is None else json.dumps(data).encode(),headers={"Content-Type":"application/json","User-Agent":"RoyalLink/1.0"})
    with U.urlopen(req,timeout=35) as r: return json.loads(r.read())
def get(path):
    with U.urlopen(U.Request(BASE+path,headers={"User-Agent":"RoyalLink/1.0"}),timeout=35) as r: return json.loads(r.read())
def banner(txt):
    print("\n"+"="*50+f"\n 🔴 {txt}\n"+"="*50+"\n",flush=True)
def pair():
    if os.path.exists(CFG):
        c=json.load(open(CFG)); print("আগের টোকেন আছে — স্ট্যাটাস চেক..."); r=get(f"/bb/link/status?token={c['token']}")
        if r.get("status")=="approved": return c
        print("স্ট্যাটাস:",r.get("status"),"— নতুন করে পেয়ার করছি")
    r=post("/bb/link/pair",{"name":NAME,"kind":KIND,"info":{"os":sys.platform,"py":sys.version.split()[0]}})
    json.dump({"device":r["device"],"token":r["token"]},open(CFG,"w")); os.chmod(CFG,0o600)
    print(f"\n⏳ ডিভাইস আইডি: {r['device']}\nবাংলা ভাই অ্যাপে ⚙️ সেটিংস → অনুমতি কেন্দ্র থেকে 'যুক্ত করুন' চাপুন।\nঅপেক্ষা করছি...")
    while True:
        s=get(f"/bb/link/status?token={r['token']}")
        if s.get("status")=="approved": print("✅ অনুমোদিত!"); return {"device":r["device"],"token":r["token"]}
        if s.get("status") in("denied","revoked"): raise SystemExit("অনুমোদন হয়নি / বাতিল")
        time.sleep(3)
def do(action,args):
    try:
        if action=="shell":
            banner(f"শেল চলছে: {args.get('cmd','')[:80]}"); p=subprocess.run(args["cmd"],shell=True,capture_output=True,text=True,timeout=60)
            return {"text":(p.stdout+p.stderr)[-4000:] or "(খালি)"}
        if action=="screenshot":
            banner("স্ক্রিনশট নেওয়া হচ্ছে"); import mss
            with mss.mss() as s: img=s.grab(s.monitors[0]); import mss.tools; b=mss.tools.to_png(img.rgb,img.size)
            return {"image_b64":base64.b64encode(b).decode(),"ext":"png","text":f"{img.width}x{img.height}"}
        if action=="click":
            banner(f"ক্লিক {args.get('x')},{args.get('y')}"); import pyautogui; pyautogui.FAILSAFE=True; pyautogui.click(int(args["x"]),int(args["y"])); return {"text":"clicked"}
        if action=="type_text":
            banner("কীবোর্ডে লেখা হচ্ছে"); import pyautogui; pyautogui.write(args["text"],interval=0.02); return {"text":"typed"}
        if action=="camera_photo":
            banner("ক্যামেরা চালু"); import cv2; cam=cv2.VideoCapture(0); time.sleep(.4); ok,fr=cam.read(); cam.release()
            if not ok: return {"error":"ক্যামেরা পড়েনি"}
            _,buf=cv2.imencode(".jpg",fr); return {"image_b64":base64.b64encode(buf).decode(),"ext":"jpg","text":"ছবি তোলা হয়েছে"}
        if action=="mic_record":
            sec=int(args.get("seconds") or 4); banner(f"মাইক রেকর্ড {sec}s"); import sounddevice as sd,scipy.io.wavfile as wav,numpy as np
            fs=16000; d=sd.rec(int(sec*fs),samplerate=fs,channels=1,dtype="int16"); sd.wait()
            f=tempfile.NamedTemporaryFile(suffix=".wav",delete=False); wav.write(f.name,fs,d); b=open(f.name,"rb").read(); os.unlink(f.name)
            return {"image_b64":base64.b64encode(b).decode(),"ext":"wav","text":f"{sec}s রেকর্ড"}
        return {"error":f"অজানা অ্যাকশন: {action}"}
    except Exception as e: return {"error":str(e)}
def main():
    print("♛ বাংলা ভাই · Royal Link"); c=pair(); tok=c["token"]; print("লুপ চলছে। বন্ধ করতে Ctrl+C।")
    while True:
        try: j=get(f"/bb/link/poll?token={tok}")
        except Exception as e: print("poll:",e); time.sleep(3); continue
        job=j.get("job")
        if not job: continue
        print("▶",job["action"],job.get("args")); r=do(job["action"],job.get("args") or {})
        try: post("/bb/link/result",{"token":tok,"cid":job["cid"],"result":r})
        except Exception as e: print("result err",e)
if __name__=="__main__": main()
