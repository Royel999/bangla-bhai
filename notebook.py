"""Owner Notebook: simple visible notebook at /notebook. Data is built on the box (vault_tools/vault_sync.py notebook),
AES-GCM encrypted with a key derived from BB_EDGE_SECRET, stored in Cloudflare KV (notebook_blob) and decrypted here
ONLY for the owner session. Nothing secret lives in the repo."""
import os, json, base64
from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
import persist
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'notebook')
FILES = {'nb.js': 'application/javascript', 'nb.css': 'text/css', 'manifest.webmanifest': 'application/manifest+json'}
NOSTORE = {'Cache-Control': 'no-store, private', 'Pragma': 'no-cache', 'X-Robots-Tag': 'noindex', 'Referrer-Policy': 'no-referrer'}
def key():
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives import hashes
    s = persist._sec()
    if not s: raise RuntimeError('no server key')
    return HKDF(hashes.SHA256(), 32, b'bb-notebook-salt', b'bb-notebook-v1').derive(s.encode())
def decrypt(blob):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    j = json.loads(blob)
    return json.loads(AESGCM(key()).decrypt(base64.b64decode(j['iv']), base64.b64decode(j['ct']), b'notebook'))
def setup(app, HH):
    is_admin = HH['is_admin']
    @app.get('/notebook', include_in_schema=False)
    def nb(request: Request):
        if not is_admin(request): return RedirectResponse('/admin?next=/notebook', 303, headers=NOSTORE)
        return FileResponse(D + '/index.html', headers=NOSTORE)
    @app.get('/notebook/api/data', include_in_schema=False)
    def data(request: Request):
        if not is_admin(request): return JSONResponse({'error': 'unauthorized'}, 401, headers=NOSTORE)
        if request.headers.get('x-bb-nb') != '1': return JSONResponse({'error': 'bad request'}, 400, headers=NOSTORE)
        try: b = persist.req('GET', 'notebook_blob')
        except Exception: b = None
        if not b or b == b'-': return JSONResponse({'error': 'not published yet'}, 503, headers=NOSTORE)
        try: return JSONResponse(decrypt(b), headers=NOSTORE)
        except Exception: return JSONResponse({'error': 'decrypt failed'}, 500, headers=NOSTORE)
    @app.get('/notebook/{name}', include_in_schema=False)
    def nf(name: str):
        if name not in FILES: return JSONResponse({'error': 'not found'}, 404)
        return FileResponse(D + '/' + name, media_type=FILES[name], headers={'Cache-Control': 'no-cache'})
