@echo off
taskkill /fi "WINDOWTITLE eq BanglaBhai-App*" /t /f >nul 2>&1
taskkill /fi "WINDOWTITLE eq BanglaBhai-Tunnel*" /t /f >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8090" ^| findstr LISTENING') do taskkill /pid %%p /f >nul 2>&1
taskkill /im cloudflared.exe /f >nul 2>&1
echo Bangla Bhai stopped.
