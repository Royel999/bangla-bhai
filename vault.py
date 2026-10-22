"""Royal Vault server side: serves the static PWA shell and relays CIPHERTEXT ONLY via Cloudflare KV.
Plaintext never reaches the server. KV keys: vault_imp:<id>, vault_reg (sha256 of one-time register token),
vault_pub (phone ECDH P-256 public key), vault_feed (hybrid-encrypted entry list)."""
import os, json, time, hashlib, hmac, re
from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
import persist
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'vault')
FILES = {'app.js': 'application/javascript', 'vault.css': 'text/css', 'manifest.webmanifest': 'application/manifest+json',
         'sw.js': 'application/javascript', 'icon-192.png': 'image/png', 'icon-512.png': 'image/png'}
NOSTORE = {'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex'}
def _get(k):
    try: b = persist.req('GET', k)
    except Exception: return None
    return None if not b or b == b'-' else b
def _del(k):
    try: persist.req('DELETE', k)
    except Exception: pass
    try: persist.req('PUT', k, b'-')
    except Exception: pass
HITS = {}
def setup(app, HH):
    is_owner = HH.get('is_owner'); user = HH.get('user')
    @app.get('/vault', include_in_schema=False)
    def v0(): return RedirectResponse('/vault/')
    @app.get('/vault/', include_in_schema=False)
    def v1(): return FileResponse(D + '/index.html', headers={'Cache-Control': 'no-cache', 'Content-Security-Policy': "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-ancestors 'none'", 'Referrer-Policy': 'no-referrer'})
    @app.get('/vault/import/{iid}', include_in_schema=False)
    def imp(iid: str, request: Request):
        if not re.fullmatch(r'[A-Za-z0-9_-]{20,64}', iid): return JSONResponse({'error': 'not found'}, 404, headers=NOSTORE)
        ip = request.headers.get('cf-connecting-ip') or (request.client.host if request.client else '')
        n = HITS.get((iid, ip), 0) + 1; HITS[(iid, ip)] = n
        b = _get('vault_imp:' + iid)
        if not b or n > 10: return JSONResponse({'error': 'gone'}, 410, headers=NOSTORE)
        j = json.loads(b)
        if j.get('exp', 0) < time.time(): _del('vault_imp:' + iid); return JSONResponse({'error': 'expired'}, 410, headers=NOSTORE)
        return JSONResponse(j, headers=NOSTORE)
    @app.post('/vault/api/register', include_in_schema=False)
    async def reg(request: Request):
        j = await request.json(); tok = str(j.get('register_token', '')); raw = str(j.get('raw', '')); kid = str(j.get('kid', ''))[:64]
        if not re.fullmatch(r'[A-Za-z0-9+/=]{80,100}', raw) or not kid: return JSONResponse({'error': 'bad key'}, 400)
        want = (_get('vault_reg') or b'').decode()
        ok = bool(want) and hmac.compare_digest(hashlib.sha256(tok.encode()).hexdigest(), want)
        if not ok:
            try: ok = bool(is_owner and user and is_owner(user(request)))
            except Exception: ok = False
        if not ok: return JSONResponse({'error': 'forbidden'}, 403)
        persist.req('PUT', 'vault_pub', json.dumps({'kid': kid, 'raw': raw, 'ts': int(time.time())}).encode())
        _del('vault_reg')
        iid = str(j.get('import_id', ''))
        if re.fullmatch(r'[A-Za-z0-9_-]{20,64}', iid): _del('vault_imp:' + iid)
        try: persist.req('PUT', 'vault_want_sync', str(int(time.time())).encode())
        except Exception: pass
        return {'ok': True}
    @app.get('/vault/api/feed', include_in_schema=False)
    def feed():
        b = _get('vault_feed')
        return JSONResponse(json.loads(b) if b else {'v': 0}, headers=NOSTORE)
    @app.get('/vault/{name}', include_in_schema=False)
    def vf(name: str):
        if name not in FILES: return JSONResponse({'error': 'not found'}, 404)
        h = {'Cache-Control': 'no-cache'}
        if name == 'sw.js': h['Service-Worker-Allowed'] = '/vault/'
        return FileResponse(D + '/' + name, media_type=FILES[name], headers=h)
