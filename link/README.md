# Royal Link — বাংলা ভাই ডিভাইস সংযোগ

মালিকের অনুমতি ছাড়া কিছুই চলে না। সব `audit.jsonl`-এ লগ।

## অ্যান্ড্রয়েড — এক লাইনে আবার চালান (স্ক্রিপ্ট রি-ডাউনলোড + পেয়ার)
```bash
curl -fsSL https://banglabhai.dpdns.org/bb/link/install_termux.sh | bash -s -- https://banglabhai.dpdns.org
# fallback: https://pueblo-onshore-undesired.ngrok-free.dev
```
পেয়ার কোড টার্মউক্সে দেখাবে → বাংলা ভাই **সেটিংস → অনুমতি কেন্দ্র** থেকে Approve।

Shizuku সেটআপ: [SHIZUKU_BN.md](./SHIZUKU_BN.md)

## ক্ষমতা (Permission center)
camera · mic · screen · browser · **sms** · **sms_send** · **call** · **personal** · **location** · **settings_ctl** · **apps** · full  
ডিফল্ট Ask। `sms_send` ও `call_make` সবসময় Approve কার্ড দেখায় (outgoing)।

## Windows
`windows/README.md` — PyInstaller onedir + Inno Setup।
