"""Owner Notebook. Two doors: /notebook/ (owner session) and /nb/<capability token>/ (no login; token hash in KV
key nb_cap, rotate via admin button or vault_tools/nb_rotate.py). Data is built on the box (vault_sync.py notebook),
AES-GCM encrypted with a key derived from BB_EDGE_SECRET, stored in Cloudflare KV (notebook_blob). Nothing secret in git."""
import os, json, base64, hashlib, hmac, secrets, time
from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
import persist
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'notebook')
DOM = 'https://banglabhai.dpdns.org'
FILES = {'nb.js': 'application/javascript', 'nb.css': 'text/css', 'icon.png': 'image/png'}
CSP = "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; manifest-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
NOSTORE = {'Cache-Control': 'no-store, private', 'Pragma': 'no-cache', 'X-Robots-Tag': 'noindex, nofollow', 'Referrer-Policy': 'no-referrer', 'Content-Security-Policy': CSP}
def key():
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives import hashes
    s = persist._sec()
    if not s: raise RuntimeError('no server key')
    return HKDF(hashes.SHA256(), 32, b'bb-notebook-salt', b'bb-notebook-v1').derive(s.encode())
def enc(obj):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    iv = os.urandom(12); return json.dumps(dict(iv=base64.b64encode(iv).decode(), ct=base64.b64encode(AESGCM(key()).encrypt(iv, json.dumps(obj).encode(), b'notebook')).decode())).encode()
def decrypt(blob):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    j = json.loads(blob)
    return json.loads(AESGCM(key()).decrypt(base64.b64decode(j['iv']), base64.b64decode(j['ct']), b'notebook'))
def rotate():
    """New capability token -> KV (hash + encrypted URL). Returns the URL."""
    t = secrets.token_urlsafe(32); url = DOM + '/nb/' + t + '/'
    persist.req('PUT', 'nb_cap', hashlib.sha256(t.encode()).hexdigest().encode())
    persist.req('PUT', 'nb_cap_url', enc({'url': url, 'ts': int(time.time())}))
    _C.update(h=None, t=0); return url
def current_url():
    b = persist.req('GET', 'nb_cap_url')
    return decrypt(b)['url'] if b and b != b'-' else None
_C = {'h': None, 't': 0}
def _cap():
    if time.time() - _C['t'] > 30:
        try: b = persist.req('GET', 'nb_cap'); _C['h'] = b.decode() if b and b != b'-' else None
        except Exception: pass
        _C['t'] = time.time()
    return _C['h']
RL = {}
def _rl(request, n=120, win=600):
    ip = request.headers.get('cf-connecting-ip') or (request.client.host if request.client else '')
    now = time.time(); a = [x for x in RL.get(ip, []) if now - x < win]; a.append(now); RL[ip] = a
    if len(RL) > 5000: RL.clear()
    return len(a) <= n
def _ok(tok):
    h = _cap(); return bool(h) and len(tok) >= 32 and hmac.compare_digest(hashlib.sha256(tok.encode()).hexdigest(), h)
NF = lambda: Response('Not found', 404, media_type='text/plain', headers=NOSTORE)
def _data():
    try: b = persist.req('GET', 'notebook_blob')
    except Exception: b = None
    if not b or b == b'-': return JSONResponse({'error': 'not published yet'}, 503, headers=NOSTORE)
    try: return JSONResponse(decrypt(b), headers=NOSTORE)
    except Exception: return JSONResponse({'error': 'decrypt failed'}, 500, headers=NOSTORE)
def _file(name, cap):
    if name == 'manifest.webmanifest':
        sc = '/nb/' + cap + '/' if cap else '/notebook/'
        m = {'name': 'Royal Notebook', 'short_name': 'Notebook', 'id': sc, 'start_url': sc, 'scope': sc, 'display': 'standalone', 'background_color': '#0b1a33', 'theme_color': '#0b1a33',
             'icons': [{'src': sc + 'icon.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any maskable'}]}
        return JSONResponse(m, media_type='application/manifest+json', headers=NOSTORE)
    if name not in FILES: return NF()
    return FileResponse(D + '/' + name, media_type=FILES[name], headers=NOSTORE)
def setup(app, HH):
    is_admin = HH['is_admin']
    @app.get('/notebook', include_in_schema=False)
    def nb0(request: Request): return RedirectResponse('/notebook/', 307)
    @app.get('/notebook/', include_in_schema=False)
    def nb(request: Request):
        if not is_admin(request): return RedirectResponse('/admin?next=/notebook/', 303, headers=NOSTORE)
        return FileResponse(D + '/index.html', headers=NOSTORE)
    @app.get('/notebook/data', include_in_schema=False)
    @app.get('/notebook/api/data', include_in_schema=False)
    def data(request: Request):
        if not is_admin(request): return JSONResponse({'error': 'unauthorized'}, 401, headers=NOSTORE)
        if request.headers.get('x-bb-nb') != '1': return JSONResponse({'error': 'bad request'}, 400, headers=NOSTORE)
        return _data()
    @app.get('/notebook/{name}', include_in_schema=False)
    def nf(name: str): return _file(name, None)
    @app.get('/nb/{tok}/', include_in_schema=False)
    def cap(tok: str, request: Request):
        if not _rl(request) or not _ok(tok): return NF()
        return FileResponse(D + '/index.html', headers=NOSTORE)
    @app.get('/nb/{tok}', include_in_schema=False)
    def cap0(tok: str, request: Request):
        if not _rl(request) or not _ok(tok): return NF()
        return RedirectResponse('/nb/' + tok + '/', 307, headers=NOSTORE)
    @app.get('/nb/{tok}/{name}', include_in_schema=False)
    def capf(tok: str, name: str, request: Request):
        if not _rl(request) or not _ok(tok): return NF()
        if name == 'data':
            if request.headers.get('x-bb-nb') != '1': return JSONResponse({'error': 'bad request'}, 400, headers=NOSTORE)
            return _data()
        return _file(name, tok)
    @app.post('/bb/admin/api/nb/rotate', include_in_schema=False)
    def rot(request: Request):
        if not is_admin(request): return JSONResponse({'error': 'unauthorized'}, 401)
        t = request.headers.get('x-csrf', ''); s = request.session.get('csrf', '')
        if not s or not hmac.compare_digest(t, s): return JSONResponse({'error': 'csrf'}, 403)
        return JSONResponse({'url': rotate()}, headers=NOSTORE)
    @app.get('/bb/admin/api/nb/url', include_in_schema=False)
    def cur(request: Request):
        if not is_admin(request): return JSONResponse({'error': 'unauthorized'}, 401)
        return JSONResponse({'url': current_url()}, headers=NOSTORE)
