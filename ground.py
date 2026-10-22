"""Accuracy layer: current date/time + live web grounding for time-sensitive questions."""
import re, time, datetime, httpx, html as H
TZ=datetime.timezone(datetime.timedelta(hours=6))
LIVE=re.compile(r"(today|tonight|now|current|currently|latest|recent|news|this (week|month|year)|price|rate|score|weather|forecast|election|president|prime minister|ceo|who (is|won)|stock|bitcoin|dollar|exchange|release|20(2[5-9]|3\d)|আজ|এখন|বর্তমান|সর্বশেষ|সাম্প্রতিক|খবর|দাম|রেট|আবহাওয়া|নির্বাচন|প্রধানমন্ত্রী|রাষ্ট্রপতি|কে জিতেছে|স্কোর|ডলার|বিটকয়েন)",re.I)
_cache={}
def now_line():
    n=datetime.datetime.now(TZ)
    return f"Current date/time: {n:%A, %d %B %Y, %H:%M} (Asia/Dhaka, UTC+6). Use this for any date math; never assume an older date."
RULES=("Always reply in the same language as the user's latest message. Accuracy rules: answer only what you are confident is true. For math, compute step by step and double-check the final number. "
       "If live web results are provided, base time-sensitive facts on them and cite the source link; if they don't answer it, say so. "
       "If you don't know or a fact may be outdated, say so plainly instead of guessing. Never invent links, numbers, quotes or names.")
def needs_live(q): return bool(q) and len(q)<600 and bool(LIVE.search(q))
async def search(q,n=5):
    k=q.strip().lower()[:200]
    if k in _cache and time.time()-_cache[k][0]<900: return _cache[k][1]
    try:
        # httpx's TLS fingerprint gets a 202 bot-challenge from DuckDuckGo; curl is accepted
        import asyncio
        p=await asyncio.create_subprocess_exec("curl","-s","-m","7","-A","Mozilla/5.0","--data-urlencode","q="+q[:300],"https://html.duckduckgo.com/html/",stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
        txt=(await p.communicate())[0].decode("utf-8","ignore")
        links=re.findall(r'class="result__a" href="([^"]+)"[^>]*>(.*?)</a>',txt)
        snips=re.findall(r'class="result__snippet"[^>]*>(.*?)</a>',txt,re.S)
        out=[]
        for i,(u,t) in enumerate(links[:n]):
            m=re.search(r"uddg=([^&]+)",u)
            if m:
                from urllib.parse import unquote; u=unquote(m.group(1))
            s=H.unescape(re.sub("<.*?>","",snips[i] if i<len(snips) else "")).strip()
            out.append(f"- {H.unescape(re.sub('<.*?>','',t))} — {u}\n  {s[:300]}")
        res="\n".join(out)
    except Exception: res=""
    _cache[k]=(time.time(),res); return res
async def context(q):
    s=now_line()+"\n"+RULES
    if needs_live(q):
        r=await search(q)
        if r: s+="\n\nLive web results (fetched just now):\n"+r
    return s
