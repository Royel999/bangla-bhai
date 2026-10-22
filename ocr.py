"""Local OCR: RapidOCR for images, pdftotext (+RapidOCR on scanned pages) for PDFs."""
import io, subprocess, tempfile, os
_ENG=None
LOW_MEM=os.environ.get("BB_LOW_MEM")=="1"   # Render 512MB: OCR in the cloud, never load ONNX locally
OCR_PROMPT="Transcribe ALL text in this image exactly as written (any language, keep line breaks). Output only the text, nothing else. If there is no text, output nothing."
def shrink(data,ctype,maxpx=2000):
    """Downscale big photos before upload: fewer tokens, faster vision, tiny RAM (draft mode decode)."""
    if len(data)<600_000: return data,ctype
    try:
        from PIL import Image; im=Image.open(io.BytesIO(data)); im.draft("RGB",(maxpx,maxpx))
        im=im.convert("RGB"); im.thumbnail((maxpx,maxpx)); b=io.BytesIO(); im.save(b,"JPEG",quality=85); return b.getvalue(),"image/jpeg"
    except Exception: return data,ctype
def cloud_image_text(data,ctype="image/png",timeout=30):
    import base64, httpx
    from router import K
    data,ctype=shrink(data,ctype)
    url="data:"+(ctype or "image/png")+";base64,"+base64.b64encode(data).decode()
    msg=[{"role":"user","content":[{"type":"text","text":OCR_PROMPT},{"type":"image_url","image_url":{"url":url}}]}]
    G="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"; best=""
    for u,k,m in ((G,K.get("GEMINI_API_KEY"),"gemini-3.1-flash-lite"),(G,K.get("GEMINI_API_KEY"),"gemini-3.8-flash"),(G,K.get("GEMINI_API_KEY"),"gemini-3.1-flash-lite"),
                  ("https://openrouter.ai/api/v1/chat/completions",K.get("OPENROUTER_API_KEY"),"openrouter/free")):
        if not k: continue
        try:
            r=httpx.post(u,headers={"Authorization":f"Bearer {k}"},json={"model":m,"messages":msg},timeout=timeout)
            if r.status_code==200:
                t=(r.json()["choices"][0]["message"]["content"] or "").strip()
                if len(t)>=40: return t
                best=max(best,t,key=len)
        except Exception: pass
    return best
def _eng():
    global _ENG
    if _ENG is None:
        from rapidocr_onnxruntime import RapidOCR; _ENG=RapidOCR()
    return _ENG
def image_text(data,ctype="image/png"):
    if LOW_MEM: return cloud_image_text(data,ctype)
    res,_=_eng()(data)
    return "\n".join(r[1] for r in (res or []))
def pdf_text(data,max_pages=40):
    with tempfile.TemporaryDirectory() as d:
        p=os.path.join(d,"f.pdf"); open(p,"wb").write(data)
        try: t=subprocess.run(["pdftotext","-layout","-l",str(max_pages),p,"-"],capture_output=True,timeout=60).stdout.decode("utf-8","ignore")
        except Exception: t=""
        if len(t.strip())>=40: return t,"pdftotext"
        # scanned PDF: rasterize first pages and OCR
        try: subprocess.run(["pdftoppm","-r","150","-l",str(min(max_pages,10)),"-png",p,os.path.join(d,"pg")],timeout=120,check=True)
        except Exception: return t,"pdftotext"
        pages=[open(os.path.join(d,f),"rb").read() for f in sorted(x for x in os.listdir(d) if x.startswith("pg"))]
        if LOW_MEM:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(4) as ex: out=list(ex.map(cloud_image_text,pages))
            return "\n\n".join(out),"cloud-vision"
        return "\n\n".join(image_text(p) for p in pages),"rapidocr"
