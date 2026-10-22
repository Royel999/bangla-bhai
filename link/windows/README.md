# Windows · Royal Link build

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
