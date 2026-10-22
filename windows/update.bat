@echo off
cd /d "%~dp0.."
call windows\backup.bat nopause
call windows\stop.bat
git pull --ff-only origin main
venv\Scripts\python.exe -m pip install -r requirements.txt
call windows\start.bat
echo Updated.
