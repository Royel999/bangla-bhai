#!/usr/bin/env python3
"""Royal Vault sync (box side). Builds the entry list from ~/.secrets + known service info,
encrypts it, and publishes ONLY ciphertext to Cloudflare KV (via persist.req / X-BB-Edge).
  vault_sync.py feed            # hybrid-encrypt to the phone's registered public key (no-op if none)
  vault_sync.py import          # (re)create one-time import blob; passphrase -> ~/.secrets/vault_import_pass.txt
  vault_sync.py stats           # print category counts only (never values)
Never prints secret values."""
import os, sys, json, time, base64, hashlib, secrets, glob
sys.path.insert(0, os.path.expanduser('~/bangla_bhai'))
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
SEC = os.path.expanduser('~/.secrets'); DOM = 'https://banglabhai.dpdns.org'
ITER = 600000
b64 = lambda b: base64.b64encode(b).decode()

# file -> (name, category, url, notes)
META = {
 'bangla_bhai.env': ('Bangla Bhai app (owner login + edge secret)', 'Bangla Bhai', DOM+'/admin/panel', 'Admin login: open /login, sign in with owner email skbadol3210@gmail.com (email code) or BB_USER/BB_PASSWORD. Admin panel: /admin/panel. BB_EDGE_SECRET is the Worker->app header X-BB-Edge.'),
 'bbai.env': ('Bangla Bhai API token', 'Bangla Bhai', DOM+'/api', ''),
 'bb_byok.key': ('BYOK encryption key (user API keys)', 'Bangla Bhai', '', 'Fernet key that encrypts users\' own API keys in data.db. Losing it = users must re-add keys.'),
 'vapid.env': ('Web Push VAPID public', 'Bangla Bhai', '', 'Private key in vapid_private.pem'),
 'vapid_private.pem': ('Web Push VAPID private key', 'Bangla Bhai', '', ''),
 'ntfy_topic': ('ntfy alert topic', 'Bangla Bhai', 'https://ntfy.sh', ''),
 'render.env': ('Render API key', 'Hosting & Domain', 'https://dashboard.render.com', 'Service: https://bangla-bhai-q0x5.onrender.com (login with GitHub Royel999)'),
 'ngrok.env': ('ngrok', 'Hosting & Domain', 'https://dashboard.ngrok.com', 'Tunnel: pueblo-onshore-undesired.ngrok-free.dev (box fallback)'),
 'google_oauth_client.json': ('Google OAuth client (Gmail/Drive/Calendar)', 'Hosting & Domain', 'https://console.cloud.google.com/apis/credentials?project=bangla-bhai', 'Google Cloud project: bangla-bhai'),
 'groq.env': ('Groq', 'AI Models', 'https://console.groq.com/keys', ''),
 'gemini.env': ('Google Gemini', 'AI Models', 'https://aistudio.google.com/apikey', ''),
 'GEMINI_API_KEY': ('Gemini (raw key file)', 'AI Models', 'https://aistudio.google.com/apikey', ''),
 'openrouter.env': ('OpenRouter', 'AI Models', 'https://openrouter.ai/keys', ''),
 'OPENROUTER_API_KEY': ('OpenRouter (raw key file)', 'AI Models', 'https://openrouter.ai/keys', ''),
 'deepseek.env': ('DeepSeek', 'AI Models', 'https://platform.deepseek.com/api_keys', ''),
 'mistral.env': ('Mistral', 'AI Models', 'https://console.mistral.ai/api-keys', ''),
 'zai.env': ('Z.ai (GLM)', 'AI Models', 'https://z.ai/manage-apikey/apikey-list', ''),
 'agentrouter.env': ('AgentRouter', 'AI Models', 'https://agentrouter.org', ''),
 'pollinations.env': ('Pollinations (image/video)', 'Media & Voice', 'https://enter.pollinations.ai', ''),
 'huggingface.env': ('Hugging Face token', 'Media & Voice', 'https://huggingface.co/settings/tokens', 'User Badol3210'),
 'huggingface_login.env': ('Hugging Face login', 'Media & Voice', 'https://huggingface.co/login', ''),
 'deepgram.env': ('Deepgram (speech-to-text)', 'Media & Voice', 'https://console.deepgram.com', ''),
 'assemblyai.env': ('AssemblyAI', 'Media & Voice', 'https://www.assemblyai.com/app', ''),
 'cartesia.env': ('Cartesia (voice)', 'Media & Voice', 'https://play.cartesia.ai/keys', ''),
 'resend.env': ('Resend (email)', 'Email & Messaging', 'https://resend.com/api-keys', ''),
 'agent_gmail.env': ('Agent Gmail account', 'Email & Messaging', 'https://mail.google.com', ''),
 'n8n.env': ('n8n (automation)', 'Automation & Tools', '', 'Self-hosted n8n on the box'),
 'squidex.env': ('Squidex CMS', 'Automation & Tools', 'https://cloud.squidex.io', ''),
 'box_apps.env': ('Open WebUI admin (box)', 'Automation & Tools', '', ''),
 'telegram.env': ('Telegram bot', 'Email & Messaging', 'https://t.me/BotFather', 'Env BB_TELEGRAM_TOKEN'),
}
STATIC = [
 ('link:user', 'Bangla Bhai — user app link', 'Links', DOM+'/', [], 'Share this with users'),
 ('link:login', 'Bangla Bhai — login', 'Links', DOM+'/login', [], 'Owner: skbadol3210@gmail.com'),
 ('link:admin', 'Bangla Bhai — Admin panel', 'Links', DOM+'/admin/panel', [], 'Owner session required'),
 ('link:connections', 'Bangla Bhai — Connections', 'Links', DOM+'/connections', [], ''),
 ('link:vault', 'Royal Vault', 'Links', DOM+'/vault/', [], 'This app'),
 ('link:render', 'Render service', 'Hosting & Domain', 'https://bangla-bhai-q0x5.onrender.com', [], 'Dashboard: https://dashboard.render.com (GitHub login)'),
 ('link:cloudflare', 'Cloudflare dashboard', 'Hosting & Domain', 'https://dash.cloudflare.com', [], 'Worker: banglabhai-proxy; KV store via /__bbstore'),
 ('link:domain', 'Domain banglabhai.dpdns.org', 'Hosting & Domain', 'https://dash.domain.digitalplat.org', [], 'Free DigitalPlat domain, DNS on Cloudflare'),
 ('link:github', 'GitHub repo', 'Hosting & Domain', 'https://github.com/Royel999/bangla-bhai', [('Username','Royel999',False)], 'Public, PolyForm Noncommercial'),
 ('link:gcloud', 'Google Cloud project bangla-bhai', 'Hosting & Domain', 'https://console.cloud.google.com/home/dashboard?project=bangla-bhai', [], ''),
 ('pend:brevo', 'Brevo (login emails) — pending', 'Pending', 'https://app.brevo.com/settings/keys/api', [], 'Key not yet added'),
 ('pend:telegram', 'Telegram bot token — pending', 'Pending', 'https://t.me/BotFather', [], 'Put in Connections > Telegram'),
 ('pend:pay', 'bKash / Nagad number — pending', 'Pending', DOM+'/admin/panel', [], 'Admin > Settings'),
 ('link:twilio', 'Twilio', 'Email & Messaging', 'https://console.twilio.com', [], ''),
 ('link:retell', 'Retell AI', 'Media & Voice', 'https://dashboard.retellai.com', [], ''),
 ('link:speko', 'Speko', 'Media & Voice', 'https://speko.ai', [], ''),
]
SECRET_HINT = ('KEY','TOKEN','SECRET','PASSWORD','PASS','PRIVATE','AUTH')

def parse(path, fn):
    with open(path, errors='replace') as fh: raw = fh.read()
    if fn.endswith(('.json', '.pem', '.key')) or '=' not in raw.split('\n')[0] or fn.isupper():
        return [('value', raw.strip(), True)]
    out = []
    for l in raw.splitlines():
        if '=' in l and not l.lstrip().startswith('#'):
            k, v = l.split('=', 1); k = k.strip()
            out.append((k, v.strip().strip('"\''), any(h in k.upper() for h in SECRET_HINT)))
    return out

def build():
    E = []
    for p in sorted(glob.glob(SEC+'/*')):
        fn = os.path.basename(p)
        if fn.startswith('vault_') or os.path.isdir(p): continue
        name, cat, url, notes = META.get(fn, (fn, 'Other', '', ''))
        f = parse(p, fn)
        E.append(dict(id='srv:'+fn, src='server', cat=cat, name=name, url=url, notes=notes+(' (file ~/.secrets/'+fn+')'),
                      fields=[dict(k=k, v=v, s=s) for k, v, s in f]))
    for i, n, c, u, f, no in STATIC:
        E.append(dict(id='srv:'+i, src='server', cat=c, name=n, url=u, notes=no, fields=[dict(k=k, v=v, s=s) for k, v, s in f]))
    for e in E: e['h'] = hashlib.sha256(json.dumps([e['name'], e['url'], e['notes'], e['fields']], sort_keys=True).encode()).hexdigest()[:16]
    return E

def kv():
    import persist; return persist.req

def pw_encrypt(obj, pw):
    salt, iv = os.urandom(16), os.urandom(12)
    k = PBKDF2HMAC(hashes.SHA256(), 32, salt, ITER).derive(pw.encode())
    return dict(kdf='PBKDF2-SHA256', iter=ITER, salt=b64(salt), iv=b64(iv), ct=b64(AESGCM(k).encrypt(iv, json.dumps(obj).encode(), None)))

def hybrid_encrypt(obj, pub_raw):
    pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), pub_raw)
    eph = ec.generate_private_key(ec.SECP256R1()); sh = eph.exchange(ec.ECDH(), pub)
    k = HKDF(hashes.SHA256(), 32, b'', b'royal-vault-feed-v1').derive(sh); iv = os.urandom(12)
    epk = eph.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return dict(alg='ECDH-P256+HKDF-SHA256+A256GCM', epk=b64(epk), iv=b64(iv), ct=b64(AESGCM(k).encrypt(iv, json.dumps(obj).encode(), None)))

WORDS = None
def passphrase(n=6):
    global WORDS
    if WORDS is None:
        WORDS = None
    if os.path.exists('/usr/share/dict/words'):
        with open('/usr/share/dict/words') as _w: WORDS=[w.strip().lower() for w in _w if w.strip().isalpha() and 4<=len(w.strip())<=7 and w.strip().islower()]
    if not WORDS: return '-'.join(secrets.token_urlsafe(5) for _ in range(n))
    return '-'.join(secrets.choice(WORDS) for _ in range(n)) + '-' + str(secrets.randbelow(90)+10)

def cmd_feed(req=None, entries=None):
    req = req or kv(); pub = req('GET', 'vault_pub')
    if not pub or pub == b'-': print('feed: no phone registered yet (skipped)'); return False
    pub = json.loads(pub); E = entries if entries is not None else build()
    digest = hashlib.sha256(json.dumps([e['h'] for e in E]).encode()).hexdigest()[:16]
    cur = req('GET', 'vault_feed'); cur = json.loads(cur) if cur else {}
    if cur.get('digest') == digest and cur.get('kid') == pub['kid']: print('feed: unchanged v%s' % cur.get('v')); return True
    v = int(cur.get('v', 0)) + 1
    feed = dict(v=v, ts=int(time.time()), digest=digest, kid=pub['kid'], **hybrid_encrypt(dict(v=v, entries=E), base64.b64decode(pub['raw'])))
    req('PUT', 'vault_feed', json.dumps(feed).encode()); print('feed: published v%d, %d entries' % (v, len(E))); return True

def cmd_import(req=None, pass_path=SEC+'/vault_import_pass.txt', ttl=86400):
    req = req or kv(); pw = passphrase(); reg = secrets.token_urlsafe(32); iid = secrets.token_urlsafe(24)
    blob = dict(exp=int(time.time())+ttl, **pw_encrypt(dict(entries=build(), register_token=reg, created=int(time.time())), pw))
    req('PUT', 'vault_imp:'+iid, json.dumps(blob).encode())
    req('PUT', 'vault_reg', hashlib.sha256(reg.encode()).hexdigest().encode())
    fd = os.open(pass_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f: f.write(pw + '\n')
    os.chmod(pass_path, 0o600)
    url = DOM + '/vault/import/' + iid
    with open(SEC+'/vault_import_url.txt', 'w') as f: f.write(url+'\n')
    print('import URL:', url); print('passphrase written to', pass_path); return url

def cmd_stats():
    from collections import Counter
    E = build(); print(len(E), 'entries'); [print(' ', c, n) for c, n in sorted(Counter(e['cat'] for e in E).items())]

if __name__ == '__main__':
    {'feed': cmd_feed, 'import': cmd_import, 'stats': cmd_stats}[sys.argv[1] if len(sys.argv) > 1 else 'feed']()
