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
 "hfs:flux-kontext-dev":"FLUX.1 Kontext dev (Hugging Face, free, best photo edit)",
 "pk:tongyi-mai/z-image-turbo":"Z-Image Turbo (Pollinations credit · Pro)",
 "pk:openai/gpt-image-1-mini":"GPT-image-1 mini (Pollinations credit · Pro, can edit)",
 "pk:black-forest-labs/flux.1-kontext-pro":"FLUX.1 Kontext Pro (Pollinations credit · Pro, edit)",
}
# pk: = paid Pollinations pollen (tiny shared credit) -> owner/Pro/Business only, capped; falls back to free models
PK_EDIT_ONLY={"pk:black-forest-labs/flux.1-kontext-pro"}
PK_USER_DAY=int(os.environ.get("BB_PK_USER_DAY","5")); PK_GLOBAL_DAY=int(os.environ.get("BB_PK_GLOBAL_DAY","15"))
POLL=_env(S+'/pollinations.env').get('POLLINATIONS_KEY',''); HFT=_env(S+'/huggingface.env').get('HF_TOKEN','')
FREE_VIDEO={"hfs:wan2.2-i2v":"Wan 2.2 (Hugging Face, free, ~3 s clip; falls back to LTX/CogVideoX, then a slideshow video)",
 "local:slideshow":"Slideshow video (always free: 3 AI images with pan-zoom and crossfades, ~8 s)"}
FREE_EDIT_SET={"hfs:flux-kontext-dev","pk:openai/gpt-image-1-mini","pk:black-forest-labs/flux.1-kontext-pro"}
FREE_EDIT={"cf:black-forest-labs/flux-2-klein-4b","cf:black-forest-labs/flux-2-klein-9b","cf:black-forest-labs/flux-2-dev"}|FREE_EDIT_SET
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
    if model.startswith("pk:"):
        if not POLL: raise RuntimeError("pollinations key missing")
        m=model[3:]; hd={"Authorization":f"Bearer {POLL}"}
        async with httpx.AsyncClient(timeout=180) as c:
            if image is not None:
                r=await c.post("https://gen.pollinations.ai/v1/images/edits",headers=hd,data={"model":m,"prompt":prompt},files={"image":("in."+(_sniff(image)[1] or "png"),image,_sniff(image)[0] or "image/png")})
                if r.status_code!=200: raise _err(r)
                return base64.b64decode(r.json()["data"][0]["b64_json"])
            from urllib.parse import quote
            r=await c.get(f"https://gen.pollinations.ai/image/{quote(prompt)}",params={"model":m,"width":w,"height":h,"quality":"low","seed":int(time.time())%100000},headers=hd)
            if r.status_code!=200: raise _err(r)
            return r.content
    if model=="hfs:flux-kontext-dev":
        if image is None: raise RuntimeError("kontext needs a photo")
        return await asyncio.to_thread(_space_call,"black-forest-labs/FLUX.1-Kontext-Dev","/infer",image,dict(prompt=prompt,steps=20),300)
    raise RuntimeError("unknown model")
def _space_call(space,api,image,kw,timeout):
    """Free Hugging Face ZeroGPU Space via gradio_client (uses owner's free daily ZeroGPU quota)."""
    import tempfile, shutil
    from gradio_client import Client, handle_file
    with tempfile.TemporaryDirectory() as td:
        p=f"{td}/in.{_sniff(image)[1] or 'png'}"; open(p,"wb").write(image)
        c=Client(space,token=HFT or None,verbose=False)
        try: r=c.submit(input_image=handle_file(p),api_name=api,**kw).result(timeout=timeout)
        except BaseException as e: raise RuntimeError(f"space failed: {type(e).__name__}")
        o=r[0] if isinstance(r,(list,tuple)) else r
        o=o.get("video") or o.get("path") if isinstance(o,dict) else o
        data=open(o,"rb").read()
        try: shutil.rmtree(os.path.dirname(o),ignore_errors=True)
        except Exception: pass
    if data[:4]==b"RIFF" and data[8:12]==b"WEBP":
        from PIL import Image; import io
        b=io.BytesIO(); Image.open(io.BytesIO(data)).convert("RGB").save(b,"PNG"); data=b.getvalue()
    return data
async def _space_rest(host,api,image,args,timeout=420):
    """Call a free ZeroGPU Space over its Gradio REST API (more reliable than gradio_client for some Spaces)."""
    B=f"https://{host}/gradio_api"; hd={"Authorization":f"Bearer {HFT}"} if HFT else {}
    async with httpx.AsyncClient(timeout=timeout,headers=hd,follow_redirects=True) as c:
        mt,ext=_sniff(image); up=await c.post(B+"/upload",files={"files":(f"in.{ext or 'png'}",image,mt or "image/png")})
        if up.status_code!=200: raise _err(up)
        x=await c.post(f"{B}/call/{api}",json={"data":[{"path":up.json()[0],"meta":{"_type":"gradio.FileData"}}]+args})
        if x.status_code!=200: raise _err(x)
        ev=None
        async with c.stream("GET",f"{B}/call/{api}/{x.json()['event_id']}") as st:
            async for l in st.aiter_lines():
                if l.startswith("event:"): ev=l[6:].strip()
                elif l.startswith("data:") and ev in("complete","error"):
                    if ev=="error": raise RuntimeError("space error (often the free daily GPU quota is used up): "+l[5:].strip()[:150])
                    o=json.loads(l[5:])[0]; o=o.get("video",o) if isinstance(o,dict) else o
                    try: return await _get(o["url"],hd,300)
                    except httpx.HTTPStatusError: return await _get(o["url"],None,300)
    raise RuntimeError("space: no result")
def _slideshow(imgs,label="Slideshow video"):
    """Local always-free fallback: Ken Burns pan/zoom + crossfades with ffmpeg. Clearly labelled."""
    import tempfile, subprocess
    from PIL import Image; import io
    D=3.2; X=0.8; W,Hh=768,768
    with tempfile.TemporaryDirectory() as td:
        ins=[]
        for i,b in enumerate(imgs):
            f=f"{td}/{i}.png"; Image.open(io.BytesIO(b)).convert("RGB").resize((W,Hh)).save(f); ins+=["-i",f]
        n=len(imgs); fr=int(D*25); fc=[]
        for i in range(n):
            z="min(zoom+0.0015,1.25)" if i%2==0 else "if(eq(on,0),1.25,max(zoom-0.0015,1.0))"
            fc.append(f"[{i}:v]scale={W*2}:{Hh*2},zoompan=z='{z}':x='iw/2-(iw/zoom/2)+0.6*on*(2*{i%2}-1)':y='ih/2-(ih/zoom/2)':d={fr}:s={W}x{Hh}:fps=25,setsar=1,format=yuv420p[v{i}]")
        last="v0"
        for i in range(1,n):
            fc.append(f"[{last}][v{i}]xfade=transition=fade:duration={X}:offset={i*(D-X):.2f}[x{i}]"); last=f"x{i}"
        font=BASE+"/fonts/Atma-Bold.ttf"
        fc.append(f"[{last}]drawtext=fontfile='{font}':text='{label}':x=16:y=h-44:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.45:boxborderw=8[out]")
        out=f"{td}/o.mp4"
        r=subprocess.run(["ffmpeg","-y","-loglevel","error",*ins,"-filter_complex",";".join(fc),"-map","[out]","-c:v","libx264","-pix_fmt","yuv420p","-movflags","+faststart","-r","25",out],capture_output=True,timeout=180)
        if r.returncode!=0: raise RuntimeError("ffmpeg: "+r.stderr.decode()[-1500:])
        return open(out,"rb").read()
async def _ss_img(prompt,seed):
    try: return (await free_image("cf:black-forest-labs/flux-1-schnell",prompt))
    except Exception as e: H["audit"](ev="media_fallback",model="slideshow-cf",err=str(e)[:120])
    from urllib.parse import quote
    try:
        d=await _get(f"https://image.pollinations.ai/prompt/{quote(prompt)}?width=768&height=768&nologo=true&seed={seed}",timeout=60)
        if _sniff(d)[0]: return d
    except Exception as e: H["audit"](ev="media_fallback",model="slideshow-pollinations",err=str(e)[:120])
    return None
def _card(prompt,i):
    """Last-resort local frame so the slideshow ALWAYS works (no network)."""
    from PIL import Image, ImageDraw, ImageFont; import io, textwrap
    cols=[((18,52,86),(32,140,140)),((80,30,90),(220,120,60)),((10,70,40),(200,180,60))][i%3]
    im=Image.new("RGB",(768,768)); d=ImageDraw.Draw(im)
    for y in range(768):
        a=y/767; d.line([(0,y),(768,y)],fill=tuple(int(cols[0][k]*(1-a)+cols[1][k]*a) for k in range(3)))
    try: f=ImageFont.truetype(BASE+"/fonts/Atma-Bold.ttf",40)
    except Exception: f=ImageFont.load_default()
    d.multiline_text((60,260),"\n".join(textwrap.wrap(prompt[:140],26)),font=f,fill="white",spacing=10)
    b=io.BytesIO(); im.save(b,"PNG"); return b.getvalue()
async def slideshow_video(prompt,image=None):
    shots=["","cinematic close-up, ","wide establishing shot, "]
    want=shots[1:] if image is not None else shots
    got=await asyncio.gather(*[_ss_img(sfx+prompt,int(time.time())%100000+i) for i,sfx in enumerate(want)])
    imgs=([image] if image is not None else [])+[g for g in got if g]
    while len(imgs)<3: imgs.append(_card(prompt,len(imgs)))
    return await asyncio.to_thread(_slideshow,imgs)
async def free_video(prompt,image=None,model="hfs:wan2.2-i2v"):
    """Returns (model_used, mp4). Order: Wan 2.2 (client, REST) -> LTX-Video distilled -> CogVideoX-5B -> local slideshow (always works)."""
    if model=="local:slideshow": return "local:slideshow",await slideshow_video(prompt,image)
    src=image
    if src is None:
        try: _,src=await image_with_fallback("cf:black-forest-labs/flux-1-schnell",prompt,None)
        except Exception as e: H["audit"](ev="media_fallback",model="video-img",err=str(e)[:160])
    if src is not None:
        tries=[("hfs:wan2.2-i2v",lambda:asyncio.to_thread(_space_call,"zerogpu-aoti/wan2-2-fp8da-aoti-faster","/generate_video",src,dict(prompt=prompt[:500],duration_seconds=3.0),420)),
               ("hfs:wan2.2-i2v",lambda:_space_rest("zerogpu-aoti-wan2-2-fp8da-aoti-faster.hf.space","generate_video",src,[prompt[:500],6,"",3.0,1,1,42,True])),
               ("hfs:ltx-video",lambda:asyncio.to_thread(_space_any,"Lightricks/ltx-video-distilled","/image_to_video",src,"input_image_filepath",dict(prompt=prompt[:500],mode="image-to-video",duration_ui=2),300)),
               ("hfs:cogvideox-5b",lambda:asyncio.to_thread(_space_any,"zai-org/CogVideoX-5B-Space","/generate",src,"image_input",dict(prompt=prompt[:500],video_input=None,video_strength=0.8,seed_value=-1,scale_status=False,rife_status=False),420))]
        for m,f in tries:
            try:
                d=await f()
                if _sniff(d)[1]=="mp4": return m,d
                raise RuntimeError("not mp4")
            except Exception as e: H["audit"](ev="media_fallback",model=m,err=str(e)[:160])
    return "local:slideshow",await slideshow_video(prompt,src)
def _space_any(space,api,image,img_param,kw,timeout):
    import tempfile, shutil
    from gradio_client import Client, handle_file
    with tempfile.TemporaryDirectory() as td:
        p=f"{td}/in.{_sniff(image)[1] or 'png'}"; open(p,"wb").write(image)
        c=Client(space,token=HFT or None,verbose=False)
        try: r=c.submit(api_name=api,**{img_param:handle_file(p)},**kw).result(timeout=timeout)
        except BaseException as e: raise RuntimeError(f"space failed: {str(e)[:120]}")
        o=r[0] if isinstance(r,(list,tuple)) else r
        if isinstance(o,dict): o=o.get("video") or o.get("path")
        data=open(o,"rb").read(); shutil.rmtree(os.path.dirname(o),ignore_errors=True)
    return data
def pk_allowed(u):
    import plans as _PL
    if H["is_owner"](u): return True,""
    if _PL.plan_of(u) not in("pro","business"): return False,"This model uses paid credit and is for Pro/Business plans. Pick a free model or upgrade at /plans."
    with H["db"]() as c:
        c.execute("create table if not exists ratelimit(k text, t real)")
        n=c.execute("select count(*) from ratelimit where k=? and t>?",(f"pk:{u}",time.time()-86400)).fetchone()[0]
        g=c.execute("select count(*) from ratelimit where k like 'pk:%' and t>?",(time.time()-86400,)).fetchone()[0]
    if n>=PK_USER_DAY or g>=PK_GLOBAL_DAY: return False,"Today's credit for this model is used up. Pick a free model or try tomorrow."
    return True,""
FALLBACK_GEN=["cf:black-forest-labs/flux-1-schnell","cf:bytedance/stable-diffusion-xl-lightning","pollinations:default"]
FALLBACK_EDIT=["hfs:flux-kontext-dev","cf:black-forest-labs/flux-2-klein-9b","cf:black-forest-labs/flux-2-klein-4b"]
async def image_with_fallback(model,prompt,image):
    chain=[model]+[m for m in (FALLBACK_EDIT if image is not None else FALLBACK_GEN) if m!=model]
    last=None
    for m in chain:
        try: return m,await free_image(m,prompt,image)
        except Exception as e:
            last=e; H["audit"](ev="media_fallback",model=m,err=str(e)[:160])
    raise last
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
    u=H["need"](request); pk_ok=pk_allowed(u)[0]
    img=[{"id":k,"name":v,"edit":k in FREE_EDIT,"gen":k not in PK_EDIT_ONLY and not k.startswith("hfs:"),"free":not k.startswith("pk:")} for k,v in FREE_IMAGE.items() if pk_ok or not k.startswith("pk:")]
    img.sort(key=lambda m:0 if m["id"]=="hfs:flux-kontext-dev" else 1)
    vid=[{"id":k,"name":v,"free":True} for k,v in FREE_VIDEO.items()]; chat=byok_chat_list(u)
    for r in keys_for(u):
        lab=r["label"] or PROV[r["provider"]]["name"]
        img+=[{"id":f"byok:{r['id']}:{m}","name":f"🔑 {lab} · {m}","edit":r["provider"]!="luma","free":False} for m in models_of(r,"image")]
        vid+=[{"id":f"byok:{r['id']}:{m}","name":f"🔑 {lab} · {m}","free":False} for m in models_of(r,"video")]
    return {"image":img,"video":vid,"chat":chat,"quota":{"image":quota_left(u,"image"),"video":quota_left(u,"video")},
            "free_video_note":"Free video: short ~3 second AI clip when free GPU is available, otherwise an ~8 second slideshow video. Failed tries do not use your quota."}
def refund(key):
    """Give back one quota unit (newest ratelimit row for key) after a failed generation."""
    try:
        with H["db"]() as c: c.execute("delete from ratelimit where rowid=(select rowid from ratelimit where k=? order by t desc limit 1)",(key,))
    except Exception: pass
async def _run(request,kind,model,prompt,file):
    u=H["need"](request); prompt=(prompt or "").strip()[:2000]
    if not prompt: return JSONResponse({"error":"Prompt is empty"},400)
    if not H["rate_ok"](f"media:{u}",10,60): return JSONResponse({"error":"Too many requests, wait a minute"},429)
    image=None
    if file is not None:
        image=await file.read()
        if len(image)>10*1024*1024 or not _sniff(image)[0]: return JSONResponse({"error":"Upload a JPG/PNG/WEBP under 10 MB"},400)
    charged=[]
    try:
        if model.startswith("byok:"):
            _,kid,m=model.split(":",2); r=key_row(u,kid)
            if not r: return JSONResponse({"error":"Key not found"},404)
            data=await (byok_image(r,m,prompt,image) if kind=="image" else byok_video(r,m,prompt,image))
        else:
            if kind=="video":
                if model not in FREE_VIDEO: return JSONResponse({"error":"Unknown model"},400)
                if quota_left(u,"video")<=0: return JSONResponse({"error":"Daily plan video limit reached. Upgrade at /plans, add your own key, or try tomorrow."},429)
                H["rate_ok"](f"qvideo:{u}",10**9,86400); charged.append(f"qvideo:{u}")
                model,data=await free_video(prompt,image,model)
            else:
                if model not in FREE_IMAGE: return JSONResponse({"error":"Unknown model"},400)
                if image is not None and model not in FREE_EDIT: model="hfs:flux-kontext-dev"
                if image is None and (model in PK_EDIT_ONLY or model.startswith("hfs:")): model="cf:black-forest-labs/flux-1-schnell"
                if model.startswith("pk:"):
                    ok,msg=pk_allowed(u)
                    if not ok: return JSONResponse({"error":msg},403)
                if quota_left(u,"image")<=0: return JSONResponse({"error":f"Daily plan image limit reached. Upgrade at /plans, add your own key, or try tomorrow."},429)
                H["rate_ok"](f"qimage:{u}",10**9,86400); charged.append(f"qimage:{u}")
                if model.startswith("pk:"): H["rate_ok"](f"pk:{u}",10**9,86400); charged.append(f"pk:{u}")
                model,data=await image_with_fallback(model,prompt,image)
        out=save(u,kind,model.split(":",2)[-1] if model.startswith("byok:") else model,prompt,data)
        H.get("act") and H["act"](u,"media",f"{kind}:{model.split(':',2)[-1]}",prompt[:200],"created "+out["url"],True)
        if out["model"]=="local:slideshow": out["note"]="Slideshow video (free AI images with pan-zoom). Real AI video was busy today."
        return out
    except Exception as e:
        for k in charged: refund(k)
        H["audit"](ev="media_err",kind=kind,model=model,err=str(e)[:200],refunded=bool(charged)); H.get("act") and H["act"](u,"media",f"{kind}:{model.split(':',2)[-1]}",prompt[:200],"failed",False)
        return JSONResponse({"error":"This model could not create it right now. Your daily quota was not used. Try another model or try again later.","refunded":bool(charged)},422)
@router.post("/bb/api/media/image")
async def gen_image(request:Request,prompt:str=Form(""),model:str=Form("cf:black-forest-labs/flux-1-schnell"),file:UploadFile|None=File(None)):
    return await _run(request,"image",model,prompt,file)
JOBS={}
class _F:  # holds uploaded bytes so the background job can read them after the request ends
    def __init__(s,b): s.b=b
    async def read(s): return s.b
@router.post("/bb/api/media/video")
async def gen_video(request:Request,prompt:str=Form(""),model:str=Form(""),file:UploadFile|None=File(None)):
    """Video takes minutes (longer than Cloudflare's 100 s limit), so run it as a background job and let the page poll."""
    u=H["need"](request); f=_F(await file.read()) if file is not None else None
    if sum(1 for j in JOBS.values() if j["u"]==u and j["status"]=="running")>=2: return JSONResponse({"error":"Too many requests, wait a minute"},429)
    jid=uuid.uuid4().hex; JOBS[jid]={"u":u,"status":"running","t":time.time()}
    async def work():
        try:
            r=await _run(request,"video",model,prompt,f)
            if isinstance(r,JSONResponse): JOBS[jid].update(status="error",result=json.loads(r.body),code=r.status_code)
            else: JOBS[jid].update(status="done",result=r)
        except Exception as e: JOBS[jid].update(status="error",result={"error":"Video failed. Try again later."}); H["audit"](ev="media_job_err",err=str(e)[:160])
    for k in [k for k,j in JOBS.items() if time.time()-j["t"]>7200]: JOBS.pop(k,None)
    asyncio.create_task(work()); return {"job":jid,"status":"running"}
@router.get("/bb/api/media/job/{jid}")
def video_job(request:Request,jid:str):
    u=H["need"](request); j=JOBS.get(jid)
    if not j or j["u"]!=u: return JSONResponse({"error":"Job not found"},404)
    return {"status":j["status"],**(j.get("result") or {})}
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
