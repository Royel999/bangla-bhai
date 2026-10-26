"""One model router for every LLM call: retry 5xx/timeouts with backoff, fail over on 429/quota, cooldowns, BYOK first."""
import os, json, re, time, asyncio, random, httpx
S=os.path.expanduser('~/.secrets')
def _env(f):
    d={}
    try:
        for l in open(f):
            if '=' in l: k,v=l.strip().split('=',1); d[k]=v.strip().strip('"')
    except Exception: pass
    return d
K={}
for f in ("groq","gemini","openrouter","bbai","mistral","zai","pollinations"): K.update(_env(f"{S}/{f}.env"))
GROQ="https://api.groq.com/openai/v1/chat/completions"; GEM="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
OR="https://openrouter.ai/api/v1/chat/completions"; CF="https://banglabhai.dpdns.org/__bbai/"
MIS="https://api.mistral.ai/v1/chat/completions"; ZAI="https://api.z.ai/api/paas/v4/chat/completions"; POL="https://gen.pollinations.ai/v1/chat/completions"
# id -> (label, url, key, model, kind).  All routes below are FREE (no card): see PROVIDERS for limits.
_G,_GM,_O,_M,_Z,_P,_C=K.get("GROQ_API_KEY"),K.get("GEMINI_API_KEY"),K.get("OPENROUTER_API_KEY"),K.get("MISTRAL_API_KEY"),K.get("ZAI_API_KEY"),K.get("POLLINATIONS_KEY"),K.get("BBAI_TOKEN")
CHAIN={
 # ---- user tier (free, generous daily limits) ----
 "groq:openai/gpt-oss-120b":("Groq · GPT-OSS 120B",GROQ,_G,"openai/gpt-oss-120b","oa"),
 "gemini:gemini-3.1-flash-lite":("Google · Gemini Flash-Lite",GEM,_GM,"gemini-3.1-flash-lite","oa"),
 "zai:glm-4.7-flash":("Z.ai · GLM-4.7 Flash",ZAI,_Z,"glm-4.7-flash","oa"),
 "cf:openai/gpt-oss-120b":("Cloudflare · GPT-OSS 120B",CF,_C,"openai/gpt-oss-120b","cf"),
 "cf:meta/llama-3.3-70b-instruct-fp8-fast":("Cloudflare · Llama 3.3 70B",CF,_C,"meta/llama-3.3-70b-instruct-fp8-fast","cf"),
 "mistral:ministral-14b-latest":("Mistral · Ministral 14B",MIS,_M,"ministral-14b-latest","oa"),
 "gemini:gemini-3.5-flash-lite":("Google · Gemini 3.5 Flash-Lite",GEM,_GM,"gemini-3.5-flash-lite","oa"),
 "openrouter:openrouter/free":("OpenRouter · Free",OR,_O,"openrouter/free","oa"),
 # ---- dev tier (most powerful free routes; owner only — small daily quotas) ----
 "pollinations:openai/gpt-5.3-codex":("OpenAI · GPT-5.3 Codex (Pollinations)",POL,_P,"openai/gpt-5.3-codex","oa"),
 "pollinations:openai/gpt-6-sol":("OpenAI · GPT-6 Sol (Pollinations)",POL,_P,"openai/gpt-6-sol","oa"),
 "pollinations:moonshotai/kimi-k3":("Moonshot · Kimi K3 (Pollinations)",POL,_P,"moonshotai/kimi-k3","oa"),
 "pollinations:z-ai/glm-5.3":("Z.ai · GLM-5.3 (Pollinations)",POL,_P,"z-ai/glm-5.3","oa"),
 "pollinations:qwen/qwen3.8-2.4t-a95b":("Qwen 3.8 2.4T (Pollinations)",POL,_P,"qwen/qwen3.8-2.4t-a95b","oa"),
 "pollinations:x-ai/grok-4.6":("xAI · Grok 4.6 (Pollinations)",POL,_P,"x-ai/grok-4.6","oa"),
 "openrouter:nvidia/nemotron-3-ultra-550b-a55b:free":("NVIDIA · Nemotron 3 Ultra 550B (OpenRouter)",OR,_O,"nvidia/nemotron-3-ultra-550b-a55b:free","oa"),
 "openrouter:poolside/laguna-s-2.1:free":("Poolside · Laguna S 2.1 code (OpenRouter)",OR,_O,"poolside/laguna-s-2.1:free","oa"),
 "openrouter:cohere/north-mini-code:free":("Cohere · North Mini Code (OpenRouter)",OR,_O,"cohere/north-mini-code:free","oa"),
 "gemini:gemini-3.6-flash":("Google · Gemini 3.6 Flash",GEM,_GM,"gemini-3.6-flash","oa"),
 "mistral:codestral-latest":("Mistral · Codestral",MIS,_M,"codestral-latest","oa"),
}
DEFAULT=["groq:openai/gpt-oss-120b","gemini:gemini-3.1-flash-lite","zai:glm-4.7-flash","cf:openai/gpt-oss-120b",
         "cf:meta/llama-3.3-70b-instruct-fp8-fast","mistral:ministral-14b-latest","gemini:gemini-3.5-flash-lite","openrouter:openrouter/free"]
DEV=["pollinations:openai/gpt-5.3-codex","pollinations:moonshotai/kimi-k3","openrouter:nvidia/nemotron-3-ultra-550b-a55b:free",
     "pollinations:z-ai/glm-5.3","gemini:gemini-3.6-flash","mistral:codestral-latest","openrouter:poolside/laguna-s-2.1:free",
     "groq:openai/gpt-oss-120b","cf:openai/gpt-oss-120b","zai:glm-4.7-flash","gemini:gemini-3.1-flash-lite"]
DEV_ONLY={m for m in CHAIN if m not in DEFAULT}   # never offered to normal users
# provider -> feature flag (flags.py). Turning one off removes its models from every chain.
PROV_FLAG={"groq":"prov_groq","gemini":"prov_gemini","zai":"prov_zai","cf":"prov_cloudflare","mistral":"prov_mistral",
           "openrouter":"prov_openrouter","pollinations":"prov_pollinations"}
PROVIDERS={  # verified 2026-10-26 on official pages; shown in the admin dashboard
 "groq":"ফ্রি: gpt-oss-120b ~১০০০ রিকোয়েস্ট/দিন, ২০০K টোকেন/দিন",
 "gemini":"ফ্রি: Flash-Lite ~৫০০/দিন, 3.6 Flash ~২০/দিন (প্রতি প্রজেক্ট)",
 "zai":"ফ্রি: GLM-4.7-Flash (অফিসিয়াল ফ্রি মডেল)",
 "cf":"ফ্রি: Workers AI ১০,০০০ নিউরন/দিন (সব CF মডেল মিলিয়ে)",
 "mistral":"ফ্রি Experiment কী: Ministral/Codestral চলে; Small/Medium এই কী-তে বন্ধ",
 "openrouter":"ফ্রি: :free মডেল মিলিয়ে ৫০ রিকোয়েস্ট/দিন, ২০/মিনিট",
 "pollinations":"দৈনিক ফ্রি Pollen গ্রান্ট থেকে খরচ — শুধু ডেভ টিয়ার; শেষ হলে পরের মডেলে যায়",
}
LAST={}            # id -> {"t","ok","ms","err"} last real call result (live model status)
def _note(mid,ok,ms,err=None): LAST[mid]={"t":time.time(),"ok":ok,"ms":ms,"err":err}
def allowed(mid):
    f=PROV_FLAG.get(str(mid).split(":")[0])
    if not f: return True
    try:
        import flags as FL; return FL.on(f)
    except Exception: return True
def dev_model():
    try:
        import flags as FL; v=FL.get_val("dev_model","auto")
    except Exception: v="auto"
    return v if v in CHAIN else "auto"
def dev_chain():
    sel=dev_model(); return ([sel] if sel!="auto" else [])+[m for m in DEV if m!=sel]
COOL={}            # id -> until (after 429/quota)
FORCE_FAIL={}      # test hook (owner only): id -> "429"|"503"; consumed by router
STATS={"calls":0,"retries":0,"failovers":0}
QUOTA=re.compile(r"quota|rate.?limit|daily free allocation|4006|exceeded|insufficient|credits",re.I)
class ModelError(Exception):
    def __init__(s,kind,msg): super().__init__(msg); s.kind=kind   # kind: quota|transient|fatal
def friendly(lang="en"):
    return ("দুঃখিত, এই মুহূর্তে কোনো মডেল সাড়া দিচ্ছে না। একটু পরে আবার চেষ্টা করুন।" if lang=="bn"
            else "Sorry, no model is answering right now. Please try again in a moment.")
def _classify(code,text):
    if code==429 or QUOTA.search(text or ""): return "quota"
    if code>=500 or code in (408,409,425): return "transient"
    return "fatal"
def resolve(chain_ids,extra=None):
    out=[]
    if extra: out+=list(extra)                     # user's own keys first: (id,(label,url,key,model,kind))
    ok=[(i,CHAIN[i]) for i in chain_ids if i in CHAIN and CHAIN[i][2]]
    flt=[x for x in ok if allowed(x[0])]
    # safety: if the owner switched off every provider in this chain, keep the chain alive rather than go dark
    return out+(flt or (ok[:1] if not out else []))
def _fake(mid):
    f=FORCE_FAIL.get(mid) or FORCE_FAIL.get(mid.split(":")[0])
    if f: raise ModelError("quota" if f=="429" else "transient",f"simulated {f}")
async def _once(c,mid,spec,msgs,json_mode,timeout):
    label,url,key,model,kind=spec; _fake(mid)
    try:
        if kind=="cf":
            r=await c.post(url+model,headers={"x-bbai-token":key},json={"messages":msgs,"max_tokens":2048},timeout=timeout)
            if r.status_code!=200: raise ModelError(_classify(r.status_code,r.text),f"{r.status_code}")
            j=r.json(); t=((j.get("choices") or [{}])[0].get("message") or {}).get("content") or (j.get("response") if isinstance(j.get("response"),str) else "") or ""
        elif kind=="anthropic":
            sysm="\n".join(m["content"] for m in msgs if m["role"]=="system"); rest=[m for m in msgs if m["role"]!="system"]
            r=await c.post(url,headers={"x-api-key":key,"anthropic-version":"2023-06-01"},json={"model":model,"max_tokens":4096,"system":sysm,"messages":rest},timeout=timeout)
            if r.status_code!=200: raise ModelError(_classify(r.status_code,r.text),f"{r.status_code}")
            t="".join(b.get("text","") for b in r.json().get("content",[]))
        else:
            body={"model":model,"messages":msgs}
            if json_mode: body["response_format"]={"type":"json_object"}
            r=await c.post(url,headers={"Authorization":f"Bearer {key}"},json=body,timeout=timeout)
            if r.status_code!=200: raise ModelError(_classify(r.status_code,r.text),f"{r.status_code}")
            t=(r.json()["choices"][0]["message"].get("content") or "")
    except (httpx.TimeoutException,httpx.TransportError) as e: raise ModelError("transient",type(e).__name__)
    t=re.sub(r"<think>.*?</think>","",t or "",flags=re.S).strip()
    if not t: raise ModelError("transient","empty")
    return t
async def complete(msgs,chain=None,extra=None,json_mode=False,timeout=60,tries=3,on_event=None):
    """returns (model_name, text, trace). raises ModelError('exhausted') when all fail."""
    STATS["calls"]+=1; trace=[]
    specs=resolve(chain or DEFAULT,extra)
    async with httpx.AsyncClient() as c:
        for n,(mid,spec) in enumerate(specs):
            if COOL.get(mid,0)>time.time() and n<len(specs)-1: trace.append((mid,"cooldown")); continue
            for a in range(tries):
                t0=time.time()
                try:
                    t=await _once(c,mid,spec,msgs,json_mode,timeout); trace.append((mid,"ok")); _note(mid,True,int((time.time()-t0)*1000))
                    return f"{mid.split(':')[0]}/{spec[3]}",t,trace
                except ModelError as e:
                    trace.append((mid,f"{e.kind}:{e}")); _note(mid,False,int((time.time()-t0)*1000),f"{e.kind}:{e}"[:60])
                    if e.kind=="transient" and a<tries-1:
                        STATS["retries"]+=1; on_event and await on_event("retry",spec[0])
                        await asyncio.sleep(min(8,0.8*(2**a))+random.random()*0.3); continue
                    if e.kind=="quota": COOL[mid]=time.time()+90
                    break
            STATS["failovers"]+=1; on_event and await on_event("failover",spec[0])
    raise ModelError("exhausted","all models failed: "+"; ".join(f"{m}={s}" for m,s in trace))
async def stream(msgs,chain=None,extra=None,timeout=90):
    """async gen: ('status',text) ('meta',name) ('delta',text). Failover allowed until first token."""
    specs=resolve(chain or DEFAULT,extra); STATS["calls"]+=1
    # read = max gap between streamed chunks; a stalled provider fails over fast instead of hanging 90s
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout,connect=6,read=25)) as c:
        for n,(mid,spec) in enumerate(specs):
            label,url,key,model,kind=spec
            if COOL.get(mid,0)>time.time() and n<len(specs)-1: continue
            for a in range(2):
                started=False; t0=time.time()
                try:
                    _fake(mid)
                    if kind!="oa":
                        t=await _once(c,mid,spec,msgs,False,timeout); _note(mid,True,int((time.time()-t0)*1000))
                        yield ("meta",f"{mid.split(':')[0]}/{model}"); yield ("delta",t); return
                    async with c.stream("POST",url,headers={"Authorization":f"Bearer {key}"},json={"model":model,"messages":msgs,"stream":True}) as r:
                        if r.status_code!=200:
                            txt=(await r.aread()).decode("utf-8","ignore"); raise ModelError(_classify(r.status_code,txt),str(r.status_code))
                        buf=""; inthink=False; name=None
                        async for line in r.aiter_lines():
                            if not line.startswith("data:"): continue
                            d=line[5:].strip()
                            if d=="[DONE]": break
                            try: j=json.loads(d)
                            except Exception: continue
                            if not name and j.get("model"): name=f"{mid.split(':')[0]}/{j['model']}"
                            ch=(j.get("choices") or [{}])[0].get("delta",{}).get("content") or ""
                            if not ch: continue
                            buf+=ch
                            if "<think>" in buf and "</think>" not in buf: inthink=True; continue
                            if inthink: buf=buf.split("</think>",1)[1]; inthink=False
                            if not started: yield ("meta",name or f"{mid.split(':')[0]}/{model}"); started=True; _note(mid,True,int((time.time()-t0)*1000))
                            yield ("delta",buf); buf=""
                    if not started: raise ModelError("transient","empty")
                    return
                except (httpx.TimeoutException,httpx.TransportError) as e:
                    if started: return
                    err=ModelError("transient",type(e).__name__)
                    if isinstance(e,httpx.TimeoutException): err.kind="slow"   # don't retry a slow provider; fail over
                except ModelError as e:
                    if started: return
                    err=e
                _note(mid,False,int((time.time()-t0)*1000),f"{err.kind}:{err}"[:60])
                if err.kind=="transient" and a==0:
                    STATS["retries"]+=1; yield ("status",("retry",label)); await asyncio.sleep(1.0+random.random()*0.3); continue
                if err.kind=="quota": COOL[mid]=time.time()+90
                break
            STATS["failovers"]+=1; yield ("status",("failover",label))
    raise ModelError("exhausted","all models failed")
