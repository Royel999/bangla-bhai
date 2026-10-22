@echo off
cd /d "%~dp0"
if not exist logs mkdir logs
REM --- app (restarts itself if it crashes) ---
start "BanglaBhai-App" /min cmd /c "for /l %%i in (0,0,1) do (venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8090 --proxy-headers >> logs\app.log 2>&1 & timeout /t 5 >nul)"
REM --- Cloudflare tunnel (only if set up, see GUIDE_BN.md) ---
if exist "%USERPROFILE%\.cloudflared\config.yml" (
  start "BanglaBhai-Tunnel" /min cmd /c "for /l %%i in (0,0,1) do (cloudflared tunnel run banglabhai-laptop >> logs\tunnel.log 2>&1 & timeout /t 10 >nul)"
)
if not "%1"=="hidden" (
  timeout /t 4 >nul
  start "" http://127.0.0.1:8090
  echo Bangla Bhai started.
)
