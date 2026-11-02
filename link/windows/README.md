# Windows · The Royal Bengal Tiger · Royal Link build

## One clear path (on a Windows 10/11 PC, Python 3.11+ installed)
```powershell
cd link\windows
powershell -ExecutionPolicy Bypass -File .\build.ps1
```
Result: `dist\BanglaBhaiLink\BanglaBhaiLink.exe` (+ installer if Inno Setup is installed).
The EXE/folder name stays `BanglaBhaiLink` for now so the existing installer/upgrade path doesn't break; the tray UI shows "The Royal Bengal Tiger · Royal Link".

## Hub protocol v1 (this version)
- Heartbeat: server pings every 20s, device answers pong; silent >60s ⇒ marked offline and socket closed.
- Reconnect: exponential backoff 1s→60s with jitter, same token; the server re-sends jobs that were in flight (max 3 tries, 120s TTL). Duplicate jobs are ignored by cid.
- Live steps: device sends `running` / `screenshot` / `done` / `error` events per job.
- Tray tooltip: ✅ সংযুক্ত/Connected · 🔄 আবার সংযোগ/Reconnecting · ⛔ অফলাইন/Offline (icon green/yellow/grey, red while a job runs).
- Live frames: `$env:BB_LIVE_FRAMES="1"` sends a 480px JPEG q40 every 3s **only while a job runs**. Off by default (bandwidth).

## Auto-start (opt-in, nothing is changed silently)
```powershell
.\dist\BanglaBhaiLink\BanglaBhaiLink.exe --install-autostart   # adds a .cmd to your Startup folder (no registry, no admin)
.\dist\BanglaBhaiLink\BanglaBhaiLink.exe --remove-autostart
```
The installer (`installer.iss`) can also offer a Startup shortcut checkbox.

Deeplink scheme `royallink://` is unchanged.


**No accounts are created by these scripts.** Packaging is for আব্বা's own PCs (sideload / unsigned).

## Quick run (dev)
```powershell
pip install -r requirements.txt
$env:BB_URL="https://banglabhai.dpdns.org"
python royal_link_tray.py
```

## Release build (onedir, no UPX)
```powershell
.\build.ps1
```
Output: `dist\BanglaBhaiLink\` — zip that folder, or compile `installer.iss` with [Inno Setup 6](https://jrsoftware.org/isinfo.php) to get `BanglaBhaiLink-Setup-0.3.0.exe`.

## Why onedir / no UPX
PyInstaller onefile + UPX is often flagged by Windows Defender heuristics. Onedir + no UPX is the community mitigation. SmartScreen may still show "Windows protected your PC" until reputation builds — **More info → Run anyway** is fine for personal use.

## Screen streams
Screenshots are **on-demand, max width 960, JPEG q55** to stay under ngrok free 1 GB/month. No continuous stream on free ngrok.

## Preferred mesh (later, needs approval)
**Tailscale** is preferred over ngrok for device-to-device once আব্বা approves creating a Tailscale account. Do not create the account without his OK.

## Phone control
Android control APK = **personal sideload only** (never Play Store — Accessibility agent policy). See research note `2026-10-22_bangla_bhai_apps_research.md`. Mobile dashboard = PWA (current).
