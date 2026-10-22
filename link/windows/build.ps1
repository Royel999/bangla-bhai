# Build BanglaBhaiLink onedir + (optional) Inno Setup installer.
# Run on Windows (PowerShell). Does NOT create any accounts.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python -m pip install -U pip
pip install -r requirements.txt pyinstaller
# icon: convert logo if available
if (Test-Path ..\..\static\icon-256.png) {
  # optional: magick convert; else keep placeholder
}
if (-not (Test-Path icon.ico)) {
  python -c "from PIL import Image; Image.new('RGBA',(256,256),(29,78,216,255)).save('icon.ico', sizes=[(16,16),(32,32),(48,48),(256,256)])"
}
pyinstaller --noconfirm bangla_bhai.spec
Write-Host "OK: dist\BanglaBhaiLink\BanglaBhaiLink.exe"
if (Get-Command iscc -ErrorAction SilentlyContinue) {
  iscc installer.iss
  Write-Host "OK: dist_installer\BanglaBhaiLink-Setup-0.3.0.exe"
} else {
  Write-Host "Inno Setup (iscc) not found — onedir folder is enough to zip and run."
}
Get-FileHash dist\BanglaBhaiLink\BanglaBhaiLink.exe -Algorithm SHA256 | Format-List
