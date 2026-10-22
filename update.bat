@echo off
cd /d "%~dp0"
call backup.bat nopause
call stop.bat
git pull
venv\Scripts\python.exe -m pip install -r requirements.txt
call start.bat
echo Updated.
