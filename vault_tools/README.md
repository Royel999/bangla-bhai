# Royal Vault (box-side)

- `vault_sync.py stats|feed|import` — build entry list from `~/.secrets`, publish hybrid-encrypted feed, or create one-time import blob.
- `hook.sh` — run after any change to `~/.secrets` or service URLs (agents should call this).
- `loop.sh` — every 30 minutes; started by `keep_supervise.sh`.
- Ciphertext only ever leaves the box (Cloudflare KV via `/__bbstore`). Passphrases live in `~/.secrets/vault_import_pass.txt` (mode 600). Never commit secrets.
