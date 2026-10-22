@echo off
REM Bangla Bhai one-click installer. Works on its own (downloaded alone) or from inside the repo.
if exist "%~dp0install.ps1" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$f=Join-Path $env:TEMP 'bb_install.ps1'; Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/Royel999/bangla-bhai/main/windows/install.ps1' -OutFile $f; & $f"
)
pause
