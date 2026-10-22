@echo off
cd /d "%~dp0.."
if not exist backups mkdir backups
for /f %%t in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set TS=%%t
powershell -NoProfile -Command "$p=@('.env','data.db','audit.jsonl','media_store',(Join-Path $env:USERPROFILE '.secrets\bb_byok.key')) | Where-Object { Test-Path $_ }; Compress-Archive -Force -Path $p -DestinationPath 'backups\bangla_bhai_%TS%.zip'"
echo Backup saved: backups\bangla_bhai_%TS%.zip
if not "%1"=="nopause" pause
