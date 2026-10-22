@echo off
cd /d "%~dp0"
if not exist backups mkdir backups
for /f %%t in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set TS=%%t
powershell -NoProfile -Command "Compress-Archive -Force -Path '.env','data.db','audit.jsonl','static\shots' -DestinationPath 'backups\bangla_bhai_%TS%.zip' -ErrorAction SilentlyContinue"
echo Backup saved: backups\bangla_bhai_%TS%.zip
if not "%1"=="nopause" pause
