"""Local OCR: RapidOCR for images, pdftotext (+RapidOCR on scanned pages) for PDFs."""
import io, subprocess, tempfile, os
_ENG=None
def _eng():
    global _ENG
    if _ENG is None:
        from rapidocr_onnxruntime import RapidOCR; _ENG=RapidOCR()
    return _ENG
def image_text(data):
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
        out=[]
        for f in sorted(x for x in os.listdir(d) if x.startswith("pg")):
            out.append(image_text(open(os.path.join(d,f),"rb").read()))
        return "\n\n".join(out),"rapidocr"
