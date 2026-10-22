# -*- mode: python ; coding: utf-8 -*-
# PyInstaller onedir, NO UPX (AV heuristics). Build on Windows:
#   pip install -r requirements.txt pyinstaller
#   pyinstaller bangla_bhai.spec
from PyInstaller.utils.hooks import collect_all
datas=[]; binaries=[]; hidden=[]
for pkg in ("mss","PIL","cv2","sounddevice","scipy","numpy","pystray","websocket"):
    try:
        d,b,h=collect_all(pkg); datas+=d; binaries+=b; hidden+=h
    except Exception: pass
a=Analysis(['royal_link_tray.py'],pathex=[],binaries=binaries,datas=datas,hiddenimports=hidden+['pyautogui'],
           hookspath=[],hooksconfig={},runtime_hooks=[],excludes=[],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='BanglaBhaiLink',debug=False,bootloader_ignore_signals=False,
        strip=False,upx=False,console=False,icon='icon.ico')
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='BanglaBhaiLink')
