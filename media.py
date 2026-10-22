"""Bangla Bhai media studio (image/video generate+edit) and bring-your-own-key (BYOK)."""
import os, json, time, uuid, base64, asyncio, httpx
from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from cryptography.fernet import Fernet
S=os.path.expanduser('~/.secrets'); BASE=os.path.expanduser('~/bangla_bhai'); STORE=BASE+'/media_store'
os.makedirs(STORE,exist_ok=True)
FER=Fernet(open(S+'/bb_byok.key').read().strip().encode())
def _env(f):
    d={}
    try:
        for l in open(f):
            if '=' in l: k,v=l.strip().split('=',1); d[k]=v.strip().strip('"')
    except Exception: pass
    return d
BBAI=_env(S+'/bbai.env').get('BBAI_TOKEN',''); EDGE="https://banglabhai.dpdns.org/__bbai/"
H={}  # injected helpers: need, rate_ok, db, audit, is_owner
router=APIRouter()
FREE_IMG_PER_DAY=int(os.environ.get("BB_FREE_IMG_DAY","20")); FREE_VID_PER_DAY=int(os.environ.get("BB_FREE_VID_DAY","3"))
# ---------- free models (verified live 2026-10-22) ----------
FREE_IMAGE={
 "cf:black-forest-labs/flux-1-schnell":"FLUX.1 schnell (Cloudflare, free)",
 "cf:black-forest-labs/flux-2-klein-4b":"FLUX.2 klein 4B (Cloudflare, free, can edit)",
 "cf:black-forest-labs/flux-2-klein-9b":"FLUX.2 klein 9B (Cloudflare, free, can edit)",
 "cf:black-forest-labs/flux-2-dev":"FLUX.2 dev (Cloudflare, free, can edit)",
 "cf:leonardo/lucid-origin":"Leonardo Lucid Origin (Cloudflare, free)",
 "cf:leonardo/phoenix-1.0":"Leonardo Phoenix 1.0 (Cloudflare, free)",
 "cf:stabilityai/stable-diffusion-xl-base-1.0":"Stable Diffusion XL (Cloudflare, free)",
 "cf:bytedance/stable-diffusion-xl-lightning":"SDXL Lightning (Cloudflare, free, fast)",
 "cf:lykon/dreamshaper-8-lcm":"DreamShaper 8 (Cloudflare, free)",
 "pollinations:default":"Pollinations (free, no key, adds watermark)",
}
FREE_EDIT={"cf:black-forest-labs/flux-2-klein-4b","cf:black-forest-labs/flux-2-klein-9b","cf:black-forest-labs/flux-2-dev"}
# ---------- BYOK providers ----------
PROV={
 "openai":{"name":"OpenAI","base":"https://api.openai.com/v1","chat":["gpt-5","gpt-5-mini","gpt-4.1"],"image":["gpt-image-1.5","gpt-image-1","gpt-image-1-mini"],"video":["sora-2"]},
 "gemini":{"name":"Google Gemini (paid key)","base":"https://generativelanguage.googleapis.com/v1beta/openai","chat":["gemini-3-pro-preview","gemini-2.5-pro","gemini-2.5-flash"],"image":["gemini-2.5-flash-image","gemini-3-pro-image-preview","gemini-3.1-flash-image-preview"],"video":["veo-3.1-generate-preview","veo-3.1-fast-generate-preview","veo-3.1-lite-generate-preview"]},
 "anthropic":{"name":"Anthropic Claude","base":"https://api.anthropic.com/v1","chat":["claude-sonnet-4-5","claude-opus-4-1","claude-haiku-4-5"],"image":[],"video":[]},
 "openrouter":{"name":"OpenRouter","base":"https://openrouter.ai/api/v1","chat":["openai/gpt-5","anthropic/claude-sonnet-4.5","google/gemini-2.5-pro"],"image":["google/gemini-2.5-flash-image"],"video":[]},
 "replicate":{"name":"Replicate","base":"https://api.replicate.com/v1","chat":[],"image":["black-forest-labs/flux-1.1-pro","black-forest-labs/flux-kontext-pro","google/nano-banana"],"video":["google/veo-3-fast","kwaivgi/kling-v2.1","minimax/video-01"]},
 "fal":{"name":"fal.ai","base":"https://fal.run","chat":[],"image":["fal-ai/flux/dev","fal-ai/nano-banana","fal-ai/nano-banana/edit"],"video":["fal-ai/veo3/fast","fal-ai/kling-video/v2.1/standard/text-to-video"]},
 "stability":{"name":"Stability AI","base":"https://api.stability.ai","chat":[],"image":["core","ultra","sd3.5-large"],"video":[]},
 "luma":{"name":"Luma Dream Machine","base":"https://api.lumalabs.ai/dream-machine/v1","chat":[],"image":["photon-1","photon-flash-1"],"video":["ray-2","ray-flash-2"]},
 "runway":{"name":"Runway","base":"https://api.dev.runwayml.com/v1","chat":[],"image":["gen4_image"],"video":["gen4_turbo","veo3"]},
 "custom":{"name":"Custom (OpenAI-compatible)","base":"","chat":[],"image":[],"video":[]},
}
def _db():
    c=H["db"](); c.execute("create table if not exists user_keys(id text primary key,user text,provider text,label text,enc text,base_url text,models text,created real)")
    c.execute("create table if not exists media(id text primary key,user text,kind text,model text,prompt text,file text,mime text,created real)"); return c
def keys_for(u):
    with _db() as c: return [dict(r) for r in c.execute("select * from user_keys where user=? order by created",(u,))]
def key_row(u,kid):
    with _db() as c: r=c.execute("select * from user_keys where id=? and user=?",(kid,u)).fetchone()
    return dict(r) if r else None
def dec(r): return FER.decrypt(r["enc"].encode()).decode()
def models_of(r,kind):
    extra=json.loads(r["models"] or "{}").get(kind,[]) if r.get("models") else []
    return list(dict.fromkeys(extra+PROV.get(r["provider"],{}).get(kind,[])))
# ---------- chat routing for BYOK (OpenAI-compatible endpoints, Anthropic via its OpenAI-compat layer) ----------
def byok_chat_list(u):
    out=[]
    for r in keys_for(u):
        for m in models_of(r,"chat"): out.append({"id":f"byok:{r['id']}:{m}","name":f"🔑 {r['label'] or PROV[r['provider']]['name']} · {m}"})
    return out
def resolve_chat(u,mid):
    """returns (name,url,key,model) or None for byok:<kid>:<model>"""
    try: _,kid,model=mid.split(":",2)
    except ValueError: return None
    r=key_row(u,kid)
    if not r: return None
    base=(r["base_url"] or PROV[r["provider"]]["base"]).rstrip("/")
    return (f"🔑 {model}",base+"/chat/completions",dec(r),model)
# ---------- helpers ----------
def _sniff(b):
    if b[:3]==b"\xff\xd8\xff": return "image/jpeg","jpg"
    if b[:8]==b"\x89PNG\r\n\x1a\n": return "image/png","png"
    if b[:4]==b"RIFF" and b[8:12]==b"WEBP": return "image/webp","webp"
    if b[4:8]==b"ftyp": return "video/mp4","mp4"
    return None,None
def save(u,kind,model,prompt,data):
    mime,ext=_sniff(data)
    if not mime: raise RuntimeError("provider returned no image/video")
    mid=uuid.uuid4().hex; fn=f"{mid}.{ext}"; open(f"{STORE}/{fn}","wb").write(data)
    with _db() as c: c.execute("insert into media values(?,?,?,?,?,?,?,?)",(mid,u,kind,model,prompt[:2000],fn,mime,time.time()))
    H["audit"](ev="media",kind=kind,model=model,size=len(data)); return {"id":mid,"url":f"/bb/api/media/{mid}","mime":mime,"model":model}
async def _get(url,headers=None,timeout=120):
    async with httpx.AsyncClient(timeout=timeout,follow_redirects=True) as c:
        r=await c.get(url,headers=headers or {}); r.raise_for_status(); return r.content
def _err(r): 
    try: j=r.json(); m=(j.get("error") or {}).get("message") if isinstance(j.get("error"),dict) else (j.get("error") or j.get("detail") or j.get("message"))
    except Exception: m=r.text
    return RuntimeError(f"{r.status_code}: {str(m)[:200]}")
# ---------- free image ----------
async def free_image(model,prompt,image=None,w=1024,h=1024):
    if model.startswith("cf:"):
        body={"prompt":prompt,"width":w,"height":h}
        if "flux-1-schnell" in model: body={"prompt":prompt,"steps":6}
        if image is not None: body["image_b64"]=base64.b64encode(image).decode()
        async with httpx.AsyncClient(timeout=120) as c:
            r=await c.post(EDGE+model[3:],headers={"x-bbai-token":BBAI},json=body)
        if r.status_code!=200: raise RuntimeError(r.text[:200])
        return r.content
    if model=="pollinations:default":
        from urllib.parse import quote
        return await _get(f"https://image.pollinations.ai/prompt/{quote(prompt)}?width={w}&height={h}&nologo=true&seed={int(time.time())%100000}")
    raise RuntimeError("unknown model")
# ---------- BYOK image/video ----------
async def byok_image(r,model,prompt,image=None):
    k=dec(r); p=r["provider"]; base=(r["base_url"] or PROV[p]["base"]).rstrip("/")
    async with httpx.AsyncClient(timeout=180,follow_redirects=True) as c:
        if p in("openai","custom"):
            hd={"Authorization":f"Bearer {k}"}
            if image is not None: x=await c.post(base+"/images/edits",headers=hd,data={"model":model,"prompt":prompt},files={"image":("in.png",image,"image/png")})
            else: x=await c.post(base+"/images/generations",headers=hd,json={"model":model,"prompt":prompt,"n":1})
            if x.status_code!=200: raise _err(x)
            d=x.json()["data"][0]; return base64.b64decode(d["b64_json"]) if d.get("b64_json") else await _get(d["url"])
        if p=="gemini":
            parts=[{"text":prompt}]
            if image is not None: parts.append({"inline_data":{"mime_type":_sniff(image)[0] or "image/png","data":base64.b64encode(image).decode()}})
            x=await c.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",headers={"x-goog-api-key":k},json={"contents":[{"parts":parts}],"generationConfig":{"responseModalities":["IMAGE","TEXT"]}})
            if x.status_code!=200: raise _err(x)
            for pt in x.json()["candidates"][0]["content"]["parts"]:
                d=pt.get("inlineData") or pt.get("inline_data")
                if d: return base64.b64decode(d["data"])
            raise RuntimeError("no image in reply")
        if p=="openrouter":
            ct=[{"type":"text","text":prompt}]
            if image is not None: ct.append({"type":"image_url","image_url":{"url":"data:image/png;base64,"+base64.b64encode(image).decode()}})
            x=await c.post(base+"/chat/completions",headers={"Authorization":f"Bearer {k}"},json={"model":model,"modalities":["image","text"],"messages":[{"role":"user","content":ct}]})
            if x.status_code!=200: raise _err(x)
            u=x.json()["choices"][0]["message"]["images"][0]["image_url"]["url"]
            return base64.b64decode(u.split(",",1)[1]) if u.startswith("data:") else await _get(u)
        if p=="replicate": return await _replicate(c,k,model,prompt,image)
        if p=="fal": return await _fal(c,k,model,prompt,image)
        if p=="stability":
            path="/v2beta/stable-image/generate/"+("sd3" if model.startswith("sd3") else model)
            data={"prompt":prompt,"output_format":"png"}; 
            if model.startswith("sd3"): data["model"]=model
            files={"none":("","")} if image is None else {"image":("in.png",image,"image/png")}
            if image is not None: data["mode"]="image-to-image"; data["strength"]="0.6"
            x=await c.post(base+path,headers={"Authorization":f"Bearer {k}","Accept":"image/*"},data=data,files=files)
            if x.status_code!=200: raise _err(x)
            return x.content
        if p=="luma": return await _luma(c,k,base,"image",model,prompt)
        if p=="runway": return await _runway(c,k,base,"image",model,prompt,image)
    raise RuntimeError("this provider has no image models")
def _durl(b): return f"data:{_sniff(b)[0] or 'image/png'};base64,"+base64.b64encode(b).decode()
async def _replicate(c,k,model,prompt,image,video=False):
    inp={"prompt":prompt}
    if image is not None: inp["image_input" if "nano-banana" in model else ("input_image" if "kontext" in model else "image")]=[_durl(image)] if "nano-banana" in model else _durl(image)
    x=await c.post(f"https://api.replicate.com/v1/models/{model}/predictions",headers={"Authorization":f"Bearer {k}","Prefer":"wait=60"},json={"input":inp})
    if x.status_code not in(200,201): raise _err(x)
    j=x.json()
    for _ in range(120):
        if j.get("status") in("succeeded","failed","canceled"): break
        await asyncio.sleep(5); j=(await c.get(j["urls"]["get"],headers={"Authorization":f"Bearer {k}"})).json()
    if j.get("status")!="succeeded": raise RuntimeError(f"replicate: {j.get('status')} {str(j.get('error'))[:150]}")
    o=j["output"]; o=o[0] if isinstance(o,list) else o; return await _get(o)
async def _fal(c,k,model,prompt,image):
    inp={"prompt":prompt}
    if image is not None: inp["image_urls" if "nano-banana" in model else "image_url"]=[_durl(image)] if "nano-banana" in model else _durl(image)
    x=await c.post(f"https://fal.run/{model}",headers={"Authorization":f"Key {k}"},json=inp,timeout=600)
    if x.status_code!=200: raise _err(x)
    j=x.json(); u=(j.get("images") or [{}])[0].get("url") or (j.get("image") or {}).get("url") or (j.get("video") or {}).get("url")
    if not u: raise RuntimeError("fal: no output url")
    return base64.b64decode(u.split(",",1)[1]) if u.startswith("data:") else await _get(u)
async def _luma(c,k,base,kind,model,prompt):
    hd={"Authorization":f"Bearer {k}"}
    x=await c.post(base+("/generations/image" if kind=="image" else "/generations"),headers=hd,json={"prompt":prompt,"model":model})
    if x.status_code not in(200,201): raise _err(x)
    gid=x.json()["id"]
    for _ in range(120):
        await asyncio.sleep(5); j=(await c.get(f"{base}/generations/{gid}",headers=hd)).json()
        if j.get("state")=="completed": return await _get(j["assets"]["image" if kind=="image" else "video"])
        if j.get("state")=="failed": raise RuntimeError("luma: "+str(j.get("failure_reason"))[:150])
    raise RuntimeError("luma: timeout")
async def _runway(c,k,base,kind,model,prompt,image):
    hd={"Authorization":f"Bearer {k}","X-Runway-Version":"2024-11-06"}
    if kind=="image": path,body="/text_to_image",{"model":model,"promptText":prompt,"ratio":"1024:1024"}
    elif image is not None: path,body="/image_to_video",{"model":model,"promptText":prompt,"promptImage":_durl(image),"ratio":"1280:720","duration":5}
    else: path,body="/text_to_video",{"model":model,"promptText":prompt,"ratio":"1280:720","duration":8}
    x=await c.post(base+path,headers=hd,json=body)
    if x.status_code not in(200,201): raise _err(x)
    tid=x.json()["id"]
    for _ in range(120):
        await asyncio.sleep(5); j=(await c.get(f"{base}/tasks/{tid}",headers=hd)).json()
        if j.get("status")=="SUCCEEDED": return await _get(j["output"][0])
        if j.get("status") in("FAILED","CANCELLED"): raise RuntimeError("runway: "+str(j.get("failure"))[:150])
    raise RuntimeError("runway: timeout")
async def byok_video(r,model,prompt,image=None):
    k=dec(r); p=r["provider"]; base=(r["base_url"] or PROV[p]["base"]).rstrip("/")
    async with httpx.AsyncClient(timeout=180,follow_redirects=True) as c:
        if p=="gemini":
            inst={"prompt":prompt}
            if image is not None: inst["image"]={"bytesBase64Encoded":base64.b64encode(image).decode(),"mimeType":_sniff(image)[0] or "image/png"}
            hd={"x-goog-api-key":k}; G="https://generativelanguage.googleapis.com/v1beta/"
            x=await c.post(f"{G}models/{model}:predictLongRunning",headers=hd,json={"instances":[inst]})
            if x.status_code!=200: raise _err(x)
            op=x.json()["name"]
            for _ in range(80):
                await asyncio.sleep(8); j=(await c.get(G+op,headers=hd)).json()
                if j.get("done"):
                    if j.get("error"): raise RuntimeError(str(j["error"].get("message"))[:200])
                    v=j["response"]["generateVideoResponse"]["generatedSamples"][0]["video"]["uri"]; return await _get(v,hd,300)
            raise RuntimeError("veo: timeout")
        if p=="openai":
            hd={"Authorization":f"Bearer {k}"}
            x=await c.post(base+"/videos",headers=hd,data={"model":model,"prompt":prompt})
            if x.status_code not in(200,201): raise _err(x)
            vid=x.json()["id"]
            for _ in range(80):
                await asyncio.sleep(8); j=(await c.get(f"{base}/videos/{vid}",headers=hd)).json()
                if j.get("status")=="completed": return await _get(f"{base}/videos/{vid}/content",hd,300)
                if j.get("status")=="failed": raise RuntimeError("sora: "+str(j.get("error"))[:150])
            raise RuntimeError("sora: timeout")
        if p=="replicate": return await _replicate(c,k,model,prompt,image,True)
        if p=="fal": return await _fal(c,k,model,prompt,image)
        if p=="luma": return await _luma(c,k,base,"video",model,prompt)
        if p=="runway": return await _runway(c,k,base,"video",model,prompt,image)
    raise RuntimeError("this provider has no video models")
# ---------- quota ----------
def quota_left(u,kind):
    import plans as _PL
    if H["is_owner"](u): return 9999
    lim=_PL.limit(u,"images" if kind=="image" else "videos")
    with H["db"]() as c:
        c.execute("create table if not exists ratelimit(k text, t real)")
        n=c.execute("select count(*) from ratelimit where k=? and t>?",(f"q{kind}:{u}",time.time()-86400)).fetchone()[0]
    return max(0,lim-n)
# ---------- routes ----------
@router.get("/studio")
def studio_page(request:Request):
    from fastapi.responses import RedirectResponse
    try: H["need"](request)
    except PermissionError: return RedirectResponse("/login",303)
    return FileResponse(BASE+"/static/studio.html",headers={"Cache-Control":"no-cache"})
@router.get("/bb/api/media/models")
def media_models(request:Request):
    u=H["need"](request); img=[{"id":k,"name":v,"edit":k in FREE_EDIT,"free":True} for k,v in FREE_IMAGE.items()]; vid=[]; chat=byok_chat_list(u)
    for r in keys_for(u):
        lab=r["label"] or PROV[r["provider"]]["name"]
        img+=[{"id":f"byok:{r['id']}:{m}","name":f"🔑 {lab} · {m}","edit":r["provider"]!="luma","free":False} for m in models_of(r,"image")]
        vid+=[{"id":f"byok:{r['id']}:{m}","name":f"🔑 {lab} · {m}","free":False} for m in models_of(r,"video")]
    return {"image":img,"video":vid,"chat":chat,"quota":{"image":quota_left(u,"image"),"video":quota_left(u,"video")},
            "free_video_note":"No video model is free without signup right now. Add your own key (Gemini Veo, OpenAI Sora, Replicate, fal, Luma, Runway)."}
async def _run(request,kind,model,prompt,file):
    u=H["need"](request); prompt=(prompt or "").strip()[:2000]
    if not prompt: return JSONResponse({"error":"Prompt is empty"},400)
    if not H["rate_ok"](f"media:{u}",10,60): return JSONResponse({"error":"Too many requests, wait a minute"},429)
    image=None
    if file is not None:
        image=await file.read()
        if len(image)>10*1024*1024 or not _sniff(image)[0]: return JSONResponse({"error":"Upload a JPG/PNG/WEBP under 10 MB"},400)
    try:
        if model.startswith("byok:"):
            _,kid,m=model.split(":",2); r=key_row(u,kid)
            if not r: return JSONResponse({"error":"Key not found"},404)
            data=await (byok_image(r,m,prompt,image) if kind=="image" else byok_video(r,m,prompt,image))
        else:
            if kind!="image" or model not in FREE_IMAGE: return JSONResponse({"error":"Unknown model"},400)
            if image is not None and model not in FREE_EDIT: model="cf:black-forest-labs/flux-2-klein-4b"
            if quota_left(u,"image")<=0: return JSONResponse({"error":f"Daily plan image limit reached. Upgrade at /plans, add your own key, or try tomorrow."},429)
            H["rate_ok"](f"qimage:{u}",10**9,86400)
            data=await free_image(model,prompt,image)
        out=save(u,kind,model.split(":",2)[-1] if model.startswith("byok:") else model,prompt,data)
        H.get("act") and H["act"](u,"media",f"{kind}:{model.split(':',2)[-1]}",prompt[:200],"created "+out["url"],True); return out
    except Exception as e:
        H["audit"](ev="media_err",kind=kind,model=model,err=str(e)[:200]); H.get("act") and H["act"](u,"media",f"{kind}:{model.split(':',2)[-1]}",prompt[:200],"failed",False)
        return JSONResponse({"error":"This model could not create it right now. Try another model or try again later."},422)
@router.post("/bb/api/media/image")
async def gen_image(request:Request,prompt:str=Form(""),model:str=Form("cf:black-forest-labs/flux-1-schnell"),file:UploadFile|None=File(None)):
    return await _run(request,"image",model,prompt,file)
@router.post("/bb/api/media/video")
async def gen_video(request:Request,prompt:str=Form(""),model:str=Form(""),file:UploadFile|None=File(None)):
    if not model.startswith("byok:"): return JSONResponse({"error":"No free video model is available right now. Add your own key in Studio → My API keys."},400)
    return await _run(request,"video",model,prompt,file)
@router.get("/bb/api/media")
def list_media(request:Request):
    u=H["need"](request)
    with _db() as c: return [{"id":r["id"],"kind":r["kind"],"model":r["model"],"prompt":r["prompt"],"mime":r["mime"],"url":f"/bb/api/media/{r['id']}","created":r["created"]} for r in c.execute("select * from media where user=? order by created desc limit 60",(u,))]
@router.get("/bb/api/media/{mid}")
def get_media(request:Request,mid:str):
    u=H["need"](request)
    with _db() as c: r=c.execute("select * from media where id=? and user=?",(mid,u)).fetchone()
    if not r: return JSONResponse({"error":"not found"},404)
    return FileResponse(f"{STORE}/{r['file']}",media_type=r["mime"],headers={"Cache-Control":"private, max-age=86400"})
@router.delete("/bb/api/media/{mid}")
def del_media(request:Request,mid:str):
    u=H["need"](request)
    with _db() as c:
        r=c.execute("select * from media where id=? and user=?",(mid,u)).fetchone()
        if r: c.execute("delete from media where id=?",(mid,)); 
    if r:
        try: os.remove(f"{STORE}/{r['file']}")
        except OSError: pass
    return {"ok":True}
# ---- keys ----
def _mask(k): return (k[:4]+"…"+k[-4:]) if len(k)>12 else "••••"
@router.get("/bb/api/keys")
def list_keys(request:Request):
    u=H["need"](request)
    return {"providers":{k:{"name":v["name"],"chat":v["chat"],"image":v["image"],"video":v["video"]} for k,v in PROV.items()},
            "keys":[{"id":r["id"],"provider":r["provider"],"label":r["label"],"base_url":r["base_url"],"models":json.loads(r["models"] or "{}"),"hint":_mask(dec(r)),"created":r["created"]} for r in keys_for(u)]}
@router.post("/bb/api/keys")
async def add_key(request:Request):
    u=H["need"](request); b=await request.json()
    if not H["rate_ok"](f"keys:{u}",20,3600): return JSONResponse({"error":"Too many changes"},429)
    p=b.get("provider"); k=(b.get("key") or "").strip(); base=(b.get("base_url") or "").strip()
    if p not in PROV or not (8<=len(k)<=400): return JSONResponse({"error":"Choose a provider and paste a valid key"},400)
    if p=="custom":
        from urllib.parse import urlparse
        pu=urlparse(base)
        if pu.scheme!="https" or not pu.hostname or pu.hostname in("localhost",) or pu.hostname.startswith(("127.","10.","192.168.","169.254.")) or pu.hostname.endswith((".local",".internal")):
            return JSONResponse({"error":"Custom base URL must be a public https URL"},400)
    elif base: base=""
    if len(keys_for(u))>=20: return JSONResponse({"error":"Max 20 keys"},400)
    ms={kk:[str(x).strip()[:120] for x in (b.get("models") or {}).get(kk,[]) if str(x).strip()][:20] for kk in("chat","image","video")}
    if p=="custom" and not any(ms.values()): return JSONResponse({"error":"Add at least one model name"},400)
    kid=uuid.uuid4().hex[:12]
    with _db() as c: c.execute("insert into user_keys values(?,?,?,?,?,?,?,?)",(kid,u,p,(b.get("label") or "")[:60],FER.encrypt(k.encode()).decode(),base or None,json.dumps(ms),time.time()))
    H["audit"](ev="byok_add",provider=p); return {"ok":True,"id":kid}
@router.delete("/bb/api/keys/{kid}")
def del_key(request:Request,kid:str):
    u=H["need"](request)
    with _db() as c: c.execute("delete from user_keys where id=? and user=?",(kid,u))
    H["audit"](ev="byok_del"); return {"ok":True}
