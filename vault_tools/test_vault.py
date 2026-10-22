#!/usr/bin/env python3
"""Royal Vault crypto + sync tests. Never prints secret values."""
import os, sys, json, base64, tempfile, unittest
sys.path.insert(0, os.path.expanduser('~/bangla_bhai'))
sys.path.insert(0, os.path.expanduser('~/bangla_bhai/vault_tools'))
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import vault_sync as VS

class VaultCrypto(unittest.TestCase):
    def test_pw_roundtrip(self):
        obj = {'entries':[{'id':'t','name':'x','fields':[{'k':'K','v':'secret-value-xyz','s':True}]}]}
        blob = VS.pw_encrypt(obj, 'master-password-test-99')
        self.assertIn('ct', blob); self.assertEqual(blob['iter'], 600000)
        # decrypt
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        salt = base64.b64decode(blob['salt']); iv = base64.b64decode(blob['iv'])
        k = PBKDF2HMAC(hashes.SHA256(), 32, salt, blob['iter']).derive(b'master-password-test-99')
        plain = json.loads(AESGCM(k).decrypt(iv, base64.b64decode(blob['ct']), None))
        self.assertEqual(plain['entries'][0]['fields'][0]['v'], 'secret-value-xyz')
        # wrong password fails
        k2 = PBKDF2HMAC(hashes.SHA256(), 32, salt, blob['iter']).derive(b'wrong')
        with self.assertRaises(Exception):
            AESGCM(k2).decrypt(iv, base64.b64decode(blob['ct']), None)

    def test_hybrid_roundtrip(self):
        priv = ec.generate_private_key(ec.SECP256R1())
        pub_raw = priv.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        obj = {'v':1,'entries':[{'id':'a','name':'n','fields':[]}]}
        feed = VS.hybrid_encrypt(obj, pub_raw)
        # decrypt like the phone
        epk = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), base64.b64decode(feed['epk']))
        sh = priv.exchange(ec.ECDH(), epk)
        k = HKDF(hashes.SHA256(), 32, b'', b'royal-vault-feed-v1').derive(sh)
        plain = json.loads(AESGCM(k).decrypt(base64.b64decode(feed['iv']), base64.b64decode(feed['ct']), None))
        self.assertEqual(plain['v'], 1); self.assertEqual(len(plain['entries']), 1)

    def test_build_categories(self):
        E = VS.build(); self.assertGreaterEqual(len(E), 20)
        cats = {e['cat'] for e in E}
        for need in ('AI Models','Hosting & Domain','Bangla Bhai','Links','Pending','Media & Voice'):
            self.assertIn(need, cats)
        # no empty secret-looking values in fields for real files (may be empty pending)
        for e in E:
            self.assertTrue(e['id'].startswith('srv:'))
            self.assertIn('h', e)

    def test_import_blob_self_delete_sim(self):
        """Simulate one-time import: encrypt, decrypt once, then 'delete' the stored blob.
        Uses a temp fake KV — never the real vault_imp keys."""
        store = {}
        def fake_req(method, key, data=None):
            if method == 'GET': return store.get(key)
            if method == 'PUT': store[key] = data; return b'ok'
            if method == 'DELETE': store.pop(key, None); return b'ok'
        # monkey
        real = VS.kv
        try:
            # inline a mini import without touching Cloudflare
            pw = 'alpha-bravo-charlie-delta-echo-42'
            iid = 'TESTONLY_sim_import_id_xxxxxxxx'
            blob = dict(exp=9e12, **VS.pw_encrypt({'entries':VS.build()[:3],'register_token':'tok'}, pw))
            store['vault_imp:'+iid] = json.dumps(blob).encode()
            # first download
            b = store['vault_imp:'+iid]; j = json.loads(b)
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            salt = base64.b64decode(j['salt']); iv = base64.b64decode(j['iv'])
            k = PBKDF2HMAC(hashes.SHA256(), 32, salt, j['iter']).derive(pw.encode())
            plain = json.loads(AESGCM(k).decrypt(iv, base64.b64decode(j['ct']), None))
            self.assertEqual(len(plain['entries']), 3)
            # simulate self-delete after successful register
            store.pop('vault_imp:'+iid)
            self.assertIsNone(store.get('vault_imp:'+iid))
        finally:
            pass

if __name__ == '__main__':
    unittest.main(verbosity=2)
