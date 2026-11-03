"""রয়্যাল এজেন্ট phase 2: design (generate / simple edits / Bangla text) and defensive security checks for the owner's own devices & sites."""
import base64, io, json, re, time, uuid, hashlib, ssl, socket, asyncio, os
from urllib.parse import urlparse
from fastapi import Request
from fastapi.responses import JSONResponse
import httpx
BRAND = {'royal_blue': '#1A3A8F', 'royal_black': '#0D0D12', 'royal_red': '#C8102E', 'white': '#FFFFFF', 'gold': '#D4AF37'}
FD = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
FONTS = {'hind': 'HindSiliguri-Bold.ttf', 'noto': 'NotoSansBengali.ttf', 'galada': 'Galada-Regular.ttf', 'atma': 'Atma-Bold.ttf'}
KINDS = {'image': (1024, 1024, ''), 'logo': (1024, 1024, 'minimal flat vector logo mark, clean shapes, centered, plain background, no text, '),
         'poster': (768, 1152, 'professional poster design, bold composition, space for headline, '),
         'post': (1080, 1080, 'eye-catching social media post graphic, modern, '), 'story': (720, 1280, 'vertical social media story graphic, '),
         'banner': (1500, 500, 'wide web banner, clean layout, ')}
SIZES = {'square': (1080, 1080), 'post': (1080, 1080), 'story': (1080, 1920), 'fb_cover': (1640, 624), 'yt_thumb': (1280, 720), 'a4': (2480, 3508), 'logo': (512, 512)}
DEF_DOMAINS = ['banglabhai.dpdns.org']
def _png(im, fmt='PNG'):
    b = io.BytesIO(); im.save(b, fmt); return b.getvalue()
def _hex(c, d='#FFFFFF'):
    c = str(c or '').strip(); c = BRAND.get(c, c)
    return c if re.fullmatch(r'#[0-9a-fA-F]{6}', c) else d
def text_on(img, text, pos='bottom', color='#FFFFFF', size=0, font='hind', band=None):
    from PIL import Image, ImageDraw, ImageFont, features
    im = img.convert('RGBA'); W, H = im.size; size = int(size) or max(24, W // 14)
    lay = ImageFont.Layout.RAQM if features.check('raqm') else ImageFont.Layout.BASIC
    f = ImageFont.truetype(os.path.join(FD, FONTS.get(font, FONTS['hind'])), size, layout_engine=lay)
    d = ImageDraw.Draw(im)
    lines = []
    for para in str(text)[:400].split('\n'):
        cur = ''
        for w in para.split(' '):
            t = (cur + ' ' + w).strip()
            if d.textlength(t, font=f) > W * .9 and cur: lines.append(cur); cur = w
            else: cur = t
        lines.append(cur)
    lh = int(size * 1.45); th = lh * len(lines)
    y0 = {'top': int(H * .05), 'center': (H - th) // 2}.get(pos, H - th - int(H * .06))
    if band: ov = Image.new('RGBA', im.size, (0, 0, 0, 0)); ImageDraw.Draw(ov).rectangle([0, y0 - size // 3, W, y0 + th + size // 4], fill=tuple(int(_hex(band)[i:i + 2], 16) for i in (1, 3, 5)) + (200,)); im = Image.alpha_composite(im, ov); d = ImageDraw.Draw(im)
    for i, ln in enumerate(lines):
        tw = d.textlength(ln, font=f)
        d.text(((W - tw) / 2, y0 + i * lh), ln, font=f, fill=_hex(color), stroke_width=max(1, size // 18) if not band else 0, stroke_fill='#0D0D12')
    return im, lay == ImageFont.Layout.RAQM
def remove_bg(img, tol=40):
    """Simple background removal: flood-fill similar colour from the borders (works for plain/studio backgrounds)."""
    from PIL import Image
    import numpy as np
    from PIL import ImageDraw
    im = img.convert('RGBA'); a = np.asarray(im).astype(int); rgb = a[..., :3]; H, W = rgb.shape[:2]
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]]); ref = np.median(border, 0)
    close = (np.abs(rgb - ref).sum(-1) < tol * 3).astype('uint8') * 255
    m = Image.fromarray(close).copy(); st = max(1, min(W, H) // 60)
    for x in range(0, W, st):
        for y in (0, H - 1):
            if m.getpixel((x, y)) == 255: ImageDraw.floodfill(m, (x, y), 128)
    for y in range(0, H, st):
        for x in (0, W - 1):
            if m.getpixel((x, y)) == 255: ImageDraw.floodfill(m, (x, y), 128)
    bg = np.asarray(m) == 128
    al = np.where(bg, 0, 255).astype('uint8'); al = np.asarray(Image.fromarray(al).filter(__import__('PIL.ImageFilter', fromlist=['x']).GaussianBlur(1)))
    out = a.astype('uint8').copy(); out[..., 3] = np.minimum(out[..., 3], al); return Image.fromarray(out)
def fit(img, w, h, mode='cover', bgc='#FFFFFF'):
    from PIL import Image, ImageOps
    if mode == 'cover': return ImageOps.fit(img.convert('RGBA'), (w, h), Image.LANCZOS)
    im = img.convert('RGBA'); im.thumbnail((w, h), Image.LANCZOS); c = Image.new('RGBA', (w, h), _hex(bgc)); c.alpha_composite(im, ((w - im.width) // 2, (h - im.height) // 2)); return c
# ---------------- security helpers ----------------
SUS_TLD = {'zip', 'mov', 'xyz', 'top', 'click', 'country', 'gq', 'tk', 'ml', 'cf', 'ga', 'work', 'support', 'rest', 'fit', 'loan', 'cam', 'monster'}
BRANDS = ['paypal', 'bkash', 'nagad', 'facebook', 'google', 'microsoft', 'apple', 'amazon', 'dutchbangla', 'dbbl', 'bank', 'netflix', 'whatsapp', 'instagram', 'rocket', 'upay']
SHORT = {'bit.ly', 'tinyurl.com', 't.co', 'goo.gl', 'is.gd', 'cutt.ly', 'rb.gy', 'shorturl.at', 'ow.ly', 'tiny.cc'}
def url_heur(u):
    u = u.strip(); u = u if re.match(r'^[a-z]+://', u, re.I) else 'http://' + u
    p = urlparse(u); h = (p.hostname or '').lower(); F = []; score = 0
    def add(pt, msg): nonlocal score; score += pt; F.append(msg)
    if p.scheme != 'https': add(15, 'HTTPS নেই — তথ্য এনক্রিপ্ট হয় না')
    if re.fullmatch(r'[\d.]+', h) or ':' in h: add(25, 'ডোমেইনের বদলে সরাসরি IP ঠিকানা')
    if h.startswith('xn--') or '.xn--' in h: add(25, 'Punycode/ভিন্ন অক্ষরের ডোমেইন (নকল নামের ঝুঁকি)')
    tld = h.rsplit('.', 1)[-1] if '.' in h else ''
    if tld in SUS_TLD: add(15, f'.{tld} ডোমেইন প্রায়ই প্রতারণায় ব্যবহৃত হয়')
    if h in SHORT: add(15, 'লিংক-শর্টনার — আসল গন্তব্য লুকানো')
    if h.count('.') >= 4: add(10, 'অনেক সাবডোমেইন')
    if '@' in p.netloc: add(30, 'URL-এ @ চিহ্ন — আসল সাইট লুকানোর কৌশল')
    if len(u) > 120: add(5, 'অস্বাভাবিক লম্বা URL')
    if h.count('-') >= 3: add(10, 'ডোমেইনে অনেক হাইফেন')
    for b in BRANDS:
        if b in h and not re.search(r'(^|\.)' + b + r'\.(com|net|org|com\.bd|bd)$', h): add(25, f'"{b}" নাম আছে কিন্তু আসল ডোমেইন নয় — ফিশিং হতে পারে'); break
    if re.search(r'login|verify|secure|account|update|wallet|otp|password|signin|confirm', u, re.I): add(10, 'লগইন/ভেরিফাই ধরনের শব্দ')
    if re.search(r'\.(exe|scr|apk|msi|bat|js|vbs|zip|rar|iso)(\?|$)', p.path, re.I): add(20, 'সরাসরি প্রোগ্রাম/আর্কাইভ ডাউনলোড')
    return u, h, min(100, score), F
def sec_headers_report(url, r, cert):
    H = {k.lower(): v for k, v in r.headers.items()}; out = []
    want = [('strict-transport-security', 'HSTS নেই', 'Strict-Transport-Security: max-age=31536000; includeSubDomains'),
            ('content-security-policy', 'CSP নেই', "Content-Security-Policy: default-src 'self'"),
            ('x-content-type-options', 'X-Content-Type-Options নেই', 'X-Content-Type-Options: nosniff'),
            ('referrer-policy', 'Referrer-Policy নেই', 'Referrer-Policy: strict-origin-when-cross-origin'),
            ('permissions-policy', 'Permissions-Policy নেই', 'Permissions-Policy: camera=(), microphone=(self), geolocation=()')]
    for k, bad, fix in want: out.append({'ok': k in H, 'item': k, 'msg': ('✓ আছে: ' + H[k][:80]) if k in H else bad, 'fix': '' if k in H else fix})
    xf = 'x-frame-options' in H or 'frame-ancestors' in H.get('content-security-policy', '')
    out.append({'ok': xf, 'item': 'clickjacking', 'msg': '✓ ফ্রেম-সুরক্ষা আছে' if xf else 'X-Frame-Options/frame-ancestors নেই', 'fix': '' if xf else 'X-Frame-Options: SAMEORIGIN'})
    if 'server' in H and re.search(r'\d', H['server']): out.append({'ok': False, 'item': 'server', 'msg': 'Server হেডারে ভার্সন দেখা যাচ্ছে: ' + H['server'], 'fix': 'ভার্সন নম্বর লুকান'})
    for c in r.headers.get_list('set-cookie') if hasattr(r.headers, 'get_list') else []:
        n = c.split('=')[0]; fl = c.lower()
        if 'secure' not in fl or 'httponly' not in fl: out.append({'ok': False, 'item': 'cookie ' + n, 'msg': f'কুকি "{n}"-এ Secure/HttpOnly নেই', 'fix': 'Set-Cookie-এ Secure; HttpOnly; SameSite=Lax দিন'})
    if cert:
        out.append({'ok': cert['days'] > 14, 'item': 'ssl', 'msg': f"SSL সার্টিফিকেট বৈধ, মেয়াদ আর {cert['days']} দিন ({cert['issuer']}) · {cert['proto']}", 'fix': '' if cert['days'] > 14 else 'সার্টিফিকেট নবায়ন করুন'})
    return out
def cert_info(host):
    ctx = ssl.create_default_context()
    with socket.create_connection((host, 443), timeout=8) as s:
        with ctx.wrap_socket(s, server_hostname=host) as ss:
            c = ss.getpeercert(); proto = ss.version()
    exp = ssl.cert_time_to_seconds(c['notAfter']); iss = dict(x[0] for x in c['issuer']).get('organizationName', '?')
    return {'days': int((exp - time.time()) / 86400), 'issuer': iss, 'proto': proto}

def register(app, dev_ok, owner, db, RT, RL):
    def gate(j, request, cost=1):
        d = dev_ok(j.get('token'), request)
        if not d: return None, JSONResponse({'error': 'unauthorized'}, 403)
        L = [t for t in RL.get(d['id'], []) if time.time() - t < 3600]
        if len(L) >= 60: return None, JSONResponse({'error': 'ঘণ্টায় ৬০টির সীমা'}, 429)
        RL[d['id']] = L + [time.time()] * cost; return d, None
    def save_note(title, body, png=None, name='design.png'):
        nid = uuid.uuid4().hex[:12]; now = time.time()
        with db() as c:
            if png:
                fid = uuid.uuid4().hex[:16]; body = body + f'\n\n![{name}](/bb/api/notes/file/{fid})'
                c.execute('insert into note_files values(?,?,?,?,?,?,?,?)', (fid, nid, owner, name, 'image/png', len(png), png, now))
            c.execute("insert into notes(id,user,title,body,folder,tags,created,updated) values(?,?,?,?,?,?,?,?)", (nid, owner, title[:60], body, 'ডিজাইন' if png else 'সিকিউরিটি', '[]', now, now))
        return nid
    def setting(k, default):
        with db() as c:
            c.execute('create table if not exists agent_kv(k text primary key,v text)')
            r = c.execute('select v from agent_kv where k=?', (k,)).fetchone()
        return json.loads(r[0]) if r else default
    def setset(k, v):
        with db() as c: c.execute('create table if not exists agent_kv(k text primary key,v text)'); c.execute('insert or replace into agent_kv values(?,?)', (k, json.dumps(v)))
    @app.get('/bb/link/design/caps')
    def dcaps():
        from PIL import features
        return {'raqm': bool(features.check('raqm')), 'brand': BRAND, 'kinds': list(KINDS), 'sizes': SIZES, 'fonts': list(FONTS)}
    @app.post('/bb/link/design')
    async def design(request: Request):
        j = await request.json(); op = j.get('op') or 'gen'
        d, e = gate(j, request, 2 if op == 'gen' else 1)
        if e: return e
        from PIL import Image
        img = None
        if j.get('image_b64'):
            try: img = Image.open(io.BytesIO(base64.b64decode(str(j['image_b64']).split(',')[-1])[:12 * 1024 * 1024])); img.load()
            except Exception: return JSONResponse({'error': 'ছবি পড়া যায়নি'}, 400)
        info = {}
        try:
            if op == 'gen':
                kind = j.get('kind') if j.get('kind') in KINDS else 'image'; w, h, pre = KINDS[kind]
                prompt = str(j.get('prompt') or '').strip()[:800]
                if not prompt: return JSONResponse({'error': 'কী বানাবো লিখুন'}, 400)
                if re.search(r'[\u0980-\u09FF]', prompt):
                    try: _, t, _ = await RT.complete([{'role': 'system', 'content': 'Translate this design request to a concise English image-generation prompt. Do not include any text/letters to render. Output only the prompt.'}, {'role': 'user', 'content': prompt}], timeout=30, tries=1); prompt = re.sub(r'<think>.*?</think>', '', t or prompt, flags=re.S).strip()[:600]
                    except Exception: pass
                if j.get('brand'): pre += 'color palette of deep royal blue, rich near-black and crimson red, regal premium feel, no letters, no numbers, no watermark, '
                import media
                model, data = None, None
                try:
                    if media.POLL: data = await media.free_image('pk:tongyi-mai/z-image-turbo', pre + prompt, None, w, h); model = 'pollinations z-image'
                except Exception as ex: info['note'] = str(ex)[:80]
                if data is None: model, data = await media.image_with_fallback('pollinations:default', pre + prompt, None)
                img = Image.open(io.BytesIO(data)); img.load(); info.update(model=model, prompt=prompt)
            elif img is None: return JSONResponse({'error': 'আগে একটি ছবি দিন/বানান'}, 400)
            elif op == 'rmbg': img = remove_bg(img, int(j.get('tol') or 40))
            elif op == 'resize':
                w, h = SIZES.get(j.get('preset'), (int(j.get('w') or 1080), int(j.get('h') or 1080))); img = fit(img, min(w, 4000), min(h, 4000), j.get('mode') or 'cover', j.get('bg') or '#FFFFFF')
            elif op == 'crop':
                x, y, w, h = [float(v) for v in (j.get('box') or [0, 0, 1, 1])]; W, H = img.size
                img = img.crop((int(x * W), int(y * H), int((x + w) * W), int((y + h) * H)))
            elif op == 'text':
                img, info['shaped'] = text_on(img, j.get('text') or '', j.get('pos') or 'bottom', j.get('color') or 'white', j.get('size') or 0, j.get('font') or 'hind', j.get('band'))
            else: return JSONResponse({'error': 'unknown op'}, 400)
        except Exception as ex: return JSONResponse({'error': 'ডিজাইন ব্যর্থ: ' + str(ex)[:160]}, 502)
        if j.get('text') and op == 'gen': img, info['shaped'] = text_on(img, j['text'], j.get('pos') or 'bottom', j.get('color') or 'white', 0, 'hind', j.get('band'))
        img = img.convert('RGBA'); img.thumbnail((4000, 4000)); png = _png(img)
        if len(png) > 7_500_000: png = _png(img.convert('RGB'), 'JPEG')
        nid = save_note('🎨 ' + (str(j.get('prompt') or j.get('text') or op)[:50]), 'রয়্যাল এজেন্ট ডিজাইন · ' + op + (' · ' + info.get('prompt', '') if info.get('prompt') else ''), png) if j.get('save') else None
        return {'image_b64': base64.b64encode(png).decode(), 'w': img.width, 'h': img.height, 'note': nid, **info}
    # ---------------- security (defensive, owner's own assets only) ----------------
    @app.post('/bb/link/sec')
    async def sec(request: Request):
        j = await request.json(); d, e = gate(j, request)
        if e: return e
        op = j.get('op')
        if op == 'url':
            u, h, score, F = url_heur(str(j.get('url') or '')[:2000])
            if not h: return JSONResponse({'error': 'URL ঠিক নয়'}, 400)
            res = {'url': u, 'host': h, 'score': score, 'flags': F}
            try:
                async with httpx.AsyncClient(timeout=8, follow_redirects=False) as c:
                    r = await c.head(u)
                    if r.is_redirect: res['redirect'] = r.headers.get('location', '')[:300]
            except Exception: res['unreach'] = True
            res['verdict'] = 'বিপজ্জনক মনে হচ্ছে — খুলবেন না' if score >= 50 else 'সন্দেহজনক — সাবধানে' if score >= 25 else 'বড় কোনো লক্ষণ নেই (তবুও নিশ্চিত নয়)'
            return res
        if op == 'hash':
            hx = str(j.get('sha256') or '').lower().strip()
            if not re.fullmatch(r'[0-9a-f]{64}', hx): return JSONResponse({'error': 'sha256 দিন'}, 400)
            res = {'sha256': hx, 'name': str(j.get('name') or '')[:120], 'known_good': None, 'flags': []}
            try:
                async with httpx.AsyncClient(timeout=10) as c:
                    r = await c.get('https://hashlookup.circl.lu/lookup/sha256/' + hx, headers={'accept': 'application/json'})
                if r.status_code == 200: js = r.json(); res['known_good'] = True; res['source'] = js.get('FileName') or js.get('ProductName') or 'CIRCL hashlookup (NSRL)'
                elif r.status_code == 404: res['known_good'] = False
            except Exception: res['lookup_error'] = True
            n = res['name'].lower()
            if re.search(r'\.(pdf|docx?|xlsx?|jpg|png|txt)\.(exe|scr|js|vbs|bat|cmd)$', n): res['flags'].append('দ্বৈত এক্সটেনশন (যেমন .pdf.exe) — প্রতারণার সাধারণ কৌশল')
            if re.search(r'\.(exe|scr|js|vbs|bat|cmd|ps1|hta|msi|jar|apk)$', n): res['flags'].append('চালানো যায় এমন ফাইল — শুধু বিশ্বস্ত উৎস থেকে')
            res['vt'] = 'https://www.virustotal.com/gui/file/' + hx
            res['verdict'] = ('পরিচিত ফাইল (NSRL তালিকায় আছে)' + (' — তবে নামের সতর্কতা দেখুন' if res['flags'] else '')) if res['known_good'] else 'অজানা ফাইল — VirusTotal লিংকে হ্যাশ দেখে নিন' + (' · সতর্কতা আছে' if res['flags'] else '')
            return res
        if op == 'domains':
            doms = setting('sec_domains', DEF_DOMAINS)
            if j.get('add'):
                dm = str(j['add']).lower().strip().strip('/').replace('https://', '').replace('http://', '').split('/')[0]
                if not re.fullmatch(r'[a-z0-9.-]+\.[a-z]{2,}', dm): return JSONResponse({'error': 'ডোমেইন ঠিক নয়'}, 400)
                if not j.get('confirm_owned'): return JSONResponse({'error': 'নিশ্চিত করুন ডোমেইনটি আপনার নিজের'}, 400)
                if dm not in doms: doms.append(dm); setset('sec_domains', doms)
            if j.get('remove') and j['remove'] in doms and j['remove'] not in DEF_DOMAINS: doms.remove(j['remove']); setset('sec_domains', doms)
            return {'domains': doms}
        if op == 'site':
            dm = str(j.get('domain') or '').lower().strip(); doms = setting('sec_domains', DEF_DOMAINS)
            if dm not in doms: return JSONResponse({'error': 'শুধু আপনার অনুমোদিত নিজের ডোমেইন স্ক্যান করা যায়'}, 403)
            try:
                cert = await asyncio.to_thread(cert_info, dm)
            except Exception as ex: cert = None; certerr = str(ex)[:120]
            try:
                async with httpx.AsyncClient(timeout=12, follow_redirects=True) as c:
                    r = await c.get('https://' + dm + '/'); r0 = await c.get('http://' + dm + '/', follow_redirects=False)
            except Exception as ex: return JSONResponse({'error': 'সাইটে পৌঁছানো যায়নি: ' + str(ex)[:100]}, 502)
            items = sec_headers_report(dm, r, cert)
            if not cert: items.append({'ok': False, 'item': 'ssl', 'msg': 'SSL পরীক্ষা ব্যর্থ: ' + certerr, 'fix': 'সার্টিফিকেট ঠিক করুন'})
            redir = r0.is_redirect and r0.headers.get('location', '').startswith('https://')
            items.append({'ok': redir, 'item': 'http→https', 'msg': '✓ HTTP থেকে HTTPS-এ পাঠায়' if redir else 'HTTP থেকে HTTPS-এ রিডাইরেক্ট নেই', 'fix': '' if redir else 'সব HTTP অনুরোধ 301 দিয়ে HTTPS-এ পাঠান'})
            ok = sum(i['ok'] for i in items); grade = 'A' if ok >= len(items) - 1 else 'B' if ok >= len(items) - 3 else 'C' if ok >= len(items) / 2 else 'D'
            if j.get('save'): save_note('🛡 ' + dm + ' স্ক্যান · গ্রেড ' + grade, '\n'.join(('✅ ' if i['ok'] else '⚠ ') + i['msg'] + ((' → ' + i['fix']) if i['fix'] else '') for i in items))
            return {'domain': dm, 'grade': grade, 'items': items, 'status': r.status_code}
        if op == 'breach':
            em = str(j.get('email') or '').strip().lower()
            if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[a-z]{2,}', em): return JSONResponse({'error': 'ইমেইল ঠিক নয়'}, 400)
            try:
                async with httpx.AsyncClient(timeout=15) as c:
                    r = await c.get('https://api.xposedornot.com/v1/check-email/' + em)
                js = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
                br = (js.get('breaches') or [[]])[0] if r.status_code == 200 else []
                return {'email': em, 'breaches': br[:60], 'count': len(br), 'source': 'XposedOrNot (free)', 'tip': 'পাসওয়ার্ড বদলান, প্রতিটি সাইটে আলাদা পাসওয়ার্ড ও 2FA চালু করুন' if br else 'জানা কোনো ফাঁসে পাওয়া যায়নি'}
            except Exception as ex: return JSONResponse({'error': 'ব্রিচ সার্ভিস সাড়া দেয়নি: ' + str(ex)[:80]}, 502)
        if op == 'report':
            data = str(j.get('data') or '')[:18000]
            try:
                _, t, _ = await RT.complete([{'role': 'system', 'content': 'তুমি একজন ডিফেন্সিভ সাইবার সিকিউরিটি সহকারী। ব্যবহারকারীর নিজের Windows PC-র রিড-অনলি স্বাস্থ্য তথ্য দেওয়া হলো। সহজ বাংলায় রিপোর্ট দাও: ১) সারসংক্ষেপ (ভালো/মনোযোগ দরকার) ২) ঝুঁকিগুলো (খোলা পোর্ট, অচেনা স্টার্টআপ, সন্দেহজনক প্রসেস, আপডেট, অ্যান্টিভাইরাস) ৩) প্রতিটির সহজ সমাধান ধাপ। কখনো অ্যান্টিভাইরাস/Panda বন্ধ করতে বলবে না। প্রত্যেক অনুমান স্পষ্ট বলো। সংক্ষেপে।'}, {'role': 'user', 'content': data}], timeout=90, tries=2)
                rep = re.sub(r'<think>.*?</think>', '', t or '', flags=re.S).strip()
            except Exception: return JSONResponse({'error': 'AI এখন ব্যস্ত'}, 503)
            nid = save_note('🛡 PC হেলথ রিপোর্ট ' + time.strftime('%Y-%m-%d', time.gmtime(time.time() + 21600)), rep) if j.get('save') else None
            return {'report': rep, 'note': nid}
        return JSONResponse({'error': 'unknown op'}, 400)


ASSIST_SYS = ('তুমি "মামণি" — অফিসে কাজ করা আব্বুর পাশে বসা ছোট্ট সহকারী। আব্বু এখন কোন অ্যাপে কী করছেন (জানালার শিরোনাম) দেখে '
              'একটি মাত্র ছোট, কাজের, নির্দিষ্ট বাংলা পরামর্শ দাও (সর্বোচ্চ ২ বাক্য, ১৬০ অক্ষর)। Excel হলে প্রাসঙ্গিক সূত্র/শর্টকাট (সূত্র ইংরেজিতে লিখবে), '
              'ইমেইল হলে ভদ্র উত্তরের একটি লাইন, ব্রাউজার/ডকুমেন্ট হলে দরকারি শর্টকাট। পাসওয়ার্ড বা ব্যক্তিগত তথ্য কখনো চাইবে না। শুধু JSON: {"tip":"..."}')
TYPO_SYS = ('নিচের লেখায় স্পষ্ট বানান/টাইপো ভুল থাকলে সর্বোচ্চ ৩টি ঠিক করে দাও। ভুল না থাকলে fixes খালি। শুধু JSON: {"fixes":[{"from":"..","to":".."}]}')


def register_assist(app, dev_ok, RT, RL):
    """/bb/link/assist — contextual Bangla work tips for the desktop companion (title/app only; typo check on copied text)."""
    from fastapi import Request
    @app.post('/bb/link/assist')
    async def lassist(request: Request):
        j = await request.json(); d = dev_ok(j.get('token'), request)
        if not d: return JSONResponse({'error': 'unauthorized'}, 403)
        k = 'as:' + d['id']; L = [t for t in RL.get(k, []) if time.time() - t < 3600]
        if len(L) >= 30: return JSONResponse({'error': 'rate'}, 429)
        RL[k] = L + [time.time()]
        kind = j.get('kind') or 'tip'
        if kind == 'typo':
            txt = str(j.get('text') or '')[:1200]
            if len(txt) < 12: return {'fixes': []}
            msgs = [{'role': 'system', 'content': TYPO_SYS}, {'role': 'user', 'content': txt}]
        else:
            app_ = str(j.get('app') or '')[:60]; title = str(j.get('title') or '')[:160]
            if re.search(r'pass|login|log in|sign.?in|otp|পাসওয়ার্ড|bank', title, re.I): return {'tip': ''}
            msgs = [{'role': 'system', 'content': ASSIST_SYS}, {'role': 'user', 'content': f'অ্যাপ: {app_}\nশিরোনাম: {title}\nকতক্ষণ: {int(j.get("mins") or 0)} মিনিট'}]
        try:
            _, t, _ = await RT.complete(msgs, json_mode=True, timeout=40, tries=2)
            t = re.sub(r'<think>.*?</think>', '', t or '', flags=re.S); m = re.search(r'\{.*\}', t, re.S); o = json.loads(m.group(0)) if m else {}
        except Exception: return JSONResponse({'error': 'busy'}, 503)
        if kind == 'typo':
            fx = [f for f in (o.get('fixes') or [])[:3] if isinstance(f, dict) and f.get('from') and f.get('to') and f['from'] != f['to']]
            return {'fixes': [{'from': str(f['from'])[:40], 'to': str(f['to'])[:40]} for f in fx]}
        return {'tip': str(o.get('tip') or '')[:200]}
