# The Royal Bengal Tiger · Royal Link — Windows (BanglaBhaiLink.exe)

এক পাতায় সব ধাপ · All steps on one page. কোনো অ্যাকাউন্ট খোলা হয় না, কোনো টাকা লাগে না · No accounts, free tools only.

## ১. যা লাগবে · What you need (once)
1. Windows 10/11 PC.
2. **Python 3.11 বা 3.12** — https://www.python.org/downloads/ → ইনস্টলের সময় ✅ **"Add python.exe to PATH"** টিক দিন.
3. (ঐচ্ছিক · optional) **Inno Setup 6** — https://jrsoftware.org/isdl.php → Setup.exe ইনস্টলার বানাতে. না থাকলেও ফোল্ডার চলবে.

## ২. EXE বানানো · Build
এই `windows` ফোল্ডারটা PC-তে কপি করুন (বা build pack zip খুলুন). ফোল্ডারে **Shift + Right-click → "Open PowerShell window here"**, তারপর:
```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```
এটা নিজে করে · It does: pip install (requirements + PyInstaller) → syntax check → icon → PyInstaller → (Inno থাকলে) installer → SHA256.

ফলাফল · Output:
- `dist\BanglaBhaiLink\BanglaBhaiLink.exe` — ফোল্ডারসহ চালান (onedir).
- `dist_installer\BanglaBhaiLink-Setup-0.4.0.exe` — Inno থাকলে.

EXE-এর নাম `BanglaBhaiLink` রাখা হয়েছে যাতে পুরোনো ইনস্টল আপগ্রেড হয়; ট্রে-তে দেখাবে "The Royal Bengal Tiger · Royal Link".

## ৩. ইনস্টল · Install
- Setup.exe চালান → "Start with Windows" টিক দিলে অটো-স্টার্ট হবে.
- SmartScreen "Windows protected your PC" দেখালে → **More info → Run anyway** (unsigned personal app; normal).

## ৪. পেয়ার করা · Pair
1. EXE চালান → ট্রে-তে আইকন আসবে; টুলটিপে লেখা: `⏳ অনুমোদন দরকার · id …`.
2. অ্যাপে (ফোন/ব্রাউজার) **সেটিংস → অনুমতি কেন্দ্র** → নতুন ডিভাইস **Approve** করুন.
3. টুলটিপ হবে `✅ সংযুক্ত / Connected`. টোকেন থাকে `%USERPROFILE%\.bangla_bhai_link.json` এ (কাউকে দেবেন না).
- অন্য সার্ভার হলে · different server: `$env:BB_URL="https://…"` দিয়ে চালান.

## ৫. স্ট্যাটাস · Tray status
| আইকন | টুলটিপ |
|---|---|
| 🟢 সবুজ | ✅ সংযুক্ত / Connected |
| 🟡 হলুদ | 🔄 আবার সংযোগ / Reconnecting (1s→60s backoff) |
| ⚫ ধূসর | ⛔ অফলাইন / Offline |
| 🔴 লাল | কাজ চলছে (কী কাজ লেখা থাকে) — no hidden mode |

Heartbeat: সার্ভার প্রতি ২০ সেকেন্ডে ping, ৬০ সেকেন্ড চুপ থাকলে অফলাইন. নেট গেলে নিজে আবার যুক্ত হয়; অসমাপ্ত কাজ সার্ভার আবার পাঠায় (একই কাজ দুবার চলে না).

## ৬. লাইভ ভিউ · Live frames
- অ্যাপে মালিক হিসেবে **📡 লাইভ ভিউ** (`/bb/live`) → ডিভাইস বাছুন → **লাইভ ফ্রেম** টগল চালু.
- তখন কাজ চলার সময়েই শুধু ৩ সেকেন্ডে একটা ছোট (480px) ছবি যায়. ডিফল্ট বন্ধ; সার্ভার রিস্টার্টে আবার বন্ধ.
- PC-তে সবসময় চাইলে · local override: `$env:BB_LIVE_FRAMES="1"`.
- অনুমতি (Ask/Always) বদলায় না.

## ৭. অটো-স্টার্ট · Autostart (opt-in)
- Installer-এর "Start with Windows" চেকবক্স, **অথবা**
```powershell
.\dist\BanglaBhaiLink\BanglaBhaiLink.exe --install-autostart   # Startup ফোল্ডারে .cmd (no registry, no admin)
.\dist\BanglaBhaiLink\BanglaBhaiLink.exe --remove-autostart
```

## ৮. ডেভ রান · Dev run (EXE ছাড়া)
```powershell
pip install -r requirements.txt
python royal_link_tray.py
```

## সমস্যা · Troubleshooting
- Defender আটকালে: onedir + no-UPX ব্যবহার করা হয়েছে কম ফ্ল্যাগের জন্য; ফোল্ডারটা allow করুন.
- `pip` না চিনলে: Python আবার ইনস্টল করে "Add to PATH" দিন.
- ক্যামেরা/মাইক কাজ না করলে: Windows Settings → Privacy → Camera/Microphone → desktop apps allow.
- `royallink://` deeplink scheme unchanged.
- Tailscale (ngrok-এর বদলে) পরে, জাহাঁপনার অনুমতিতে.
