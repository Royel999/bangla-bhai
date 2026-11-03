"""Royal Agent panel (রয়্যাল এজেন্ট) — borderless animated glass panel (pywebview / Edge WebView2) shown when the bird is clicked.
Launched by royal_clip.py as a child process. stdin: first line = JSON {base, token}; then commands: show/hide/status.
stdout: JSON lines {"bird": cmd, "arg": v} back to the bird. Needs:  pip install pywebview  (WebView2 runtime ships with Windows 10/11)."""
import sys, json, threading, base64, io, ctypes, webbrowser
import webview
CFG = json.loads(sys.stdin.readline()); STATUS = {}
def out(o): sys.stdout.write(json.dumps(o, ensure_ascii=False) + '\n'); sys.stdout.flush()
def clip_get():
    u, k = ctypes.windll.user32, ctypes.windll.kernel32; u.GetClipboardData.restype = ctypes.c_void_p; k.GlobalLock.restype = ctypes.c_void_p; k.GlobalLock.argtypes = [ctypes.c_void_p]; k.GlobalUnlock.argtypes = [ctypes.c_void_p]
    if not u.OpenClipboard(None): return ''
    try:
        h = u.GetClipboardData(13)
        if not h: return ''
        p = k.GlobalLock(h)
        try: return ctypes.wstring_at(p)
        finally: k.GlobalUnlock(h)
    finally: u.CloseClipboard()
def clip_set(t):
    u, k = ctypes.windll.user32, ctypes.windll.kernel32; k.GlobalAlloc.restype = ctypes.c_void_p; k.GlobalLock.restype = ctypes.c_void_p; k.GlobalLock.argtypes = [ctypes.c_void_p]; k.GlobalUnlock.argtypes = [ctypes.c_void_p]; u.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    data = (t + '\0').encode('utf-16-le'); h = k.GlobalAlloc(0x0042, len(data)); p = k.GlobalLock(h); ctypes.memmove(p, data, len(data)); k.GlobalUnlock(h)
    if u.OpenClipboard(None):
        try: u.EmptyClipboard(); u.SetClipboardData(13, h)
        finally: u.CloseClipboard()

# ───────── রয়্যাল এজেন্ট executor: safe PC actions only (no shell); risky steps are confirmed in the panel before they reach here ─────────
import os, time, subprocess
LASTFG = [0]
def _fg_watch():
    u = ctypes.windll.user32; buf = ctypes.create_unicode_buffer(256)
    while True:
        try:
            h = u.GetForegroundWindow(); u.GetWindowTextW(h, buf, 256); t = buf.value
            if h and 'রয়্যাল এজেন্ট' not in t and t not in ('', 'tk'): LASTFG[0] = h
        except Exception: pass
        time.sleep(0.4)
VK = {'ctrl': 0x11, 'control': 0x11, 'shift': 0x10, 'alt': 0x12, 'win': 0x5B, 'enter': 0x0D, 'return': 0x0D, 'tab': 0x09, 'esc': 0x1B, 'escape': 0x1B, 'space': 0x20,
      'backspace': 0x08, 'delete': 0x2E, 'del': 0x2E, 'up': 0x26, 'down': 0x28, 'left': 0x25, 'right': 0x27, 'home': 0x24, 'end': 0x23, 'pageup': 0x21, 'pagedown': 0x22}
VK.update({'f%d' % i: 0x6F + i for i in range(1, 13)})
def _vk(k):
    k = str(k).lower().strip()
    if k in VK: return VK[k]
    if len(k) == 1: return ctypes.windll.user32.VkKeyScanW(ord(k)) & 0xFF
    raise ValueError('unknown key ' + k)
def _focus():
    h = LASTFG[0]
    if h:
        u = ctypes.windll.user32
        try: u.keybd_event(0x12, 0, 0, 0); u.SetForegroundWindow(h); u.keybd_event(0x12, 0, 2, 0)
        except Exception: pass
        time.sleep(0.25)
def _keys(keys):
    u = ctypes.windll.user32; vs = [_vk(k) for k in keys]
    for v in vs: u.keybd_event(v, 0, 0, 0); time.sleep(0.02)
    for v in reversed(vs): u.keybd_event(v, 0, 2, 0); time.sleep(0.02)
class _KI(ctypes.Structure): _fields_ = [('wVk', ctypes.c_ushort), ('wScan', ctypes.c_ushort), ('dwFlags', ctypes.c_ulong), ('time', ctypes.c_ulong), ('extra', ctypes.c_size_t)]
class _IN(ctypes.Structure): _fields_ = [('type', ctypes.c_ulong), ('ki', _KI), ('pad', ctypes.c_ubyte * 8)]
def _type(text):
    u = ctypes.windll.user32
    for ch in str(text):
        if ch == '\n': _keys(['enter']); continue
        b = ch.encode('utf-16-le')
        for code in [int.from_bytes(b[i:i + 2], 'little') for i in range(0, len(b), 2)]:
            for fl in (4, 6):  # KEYEVENTF_UNICODE, | KEYUP
                i = _IN(); i.type = 1; i.ki = _KI(0, code, fl, 0, 0); u.SendInput(1, ctypes.byref(i), ctypes.sizeof(_IN))
        time.sleep(0.008)
APPS = {'chrome': 'chrome', 'google chrome': 'chrome', 'edge': 'msedge', 'msedge': 'msedge', 'excel': 'excel', 'word': 'winword', 'winword': 'winword', 'outlook': 'outlook',
        'powerpoint': 'powerpnt', 'powerpnt': 'powerpnt', 'notepad': 'notepad', 'calc': 'calc', 'calculator': 'calc', 'explorer': 'explorer', 'paint': 'mspaint', 'mspaint': 'mspaint',
        'snippingtool': 'snippingtool', 'snipping tool': 'snippingtool'}
BLOCK = ('cmd', 'powershell', 'pwsh', 'regedit', 'reg', 'wscript', 'cscript', 'mshta', 'bcdedit', 'diskpart', 'taskkill', 'netsh', 'sc')
def _path(p):
    p = os.path.expandvars(os.path.expanduser(str(p).strip().strip('"')))
    home = os.path.expanduser('~')
    for k in ('Downloads', 'Desktop', 'Documents', 'Pictures', 'Music', 'Videos'):
        if p.lower() in (k.lower(), k.lower() + ' folder', k.lower() + ' ফোল্ডার'): p = os.path.join(home, k)
    if p.lower().startswith('downloads') and not os.path.exists(p) and os.path.isdir(r'D:\Desktop Backup(Don' + "'" + r't Delete)\Downloads'): p = r'D:\Desktop Backup(Don' + "'" + r't Delete)\Downloads'
    return p
def agent_do(s):
    a, g = s.get('action'), s.get('args') or {}
    if a == 'open_url':
        u = str(g.get('url', ''))
        if not u.startswith(('http://', 'https://')): u = 'https://' + u
        webbrowser.open(u); time.sleep(1); return {'ok': True}
    if a == 'web_search': webbrowser.open('https://www.google.com/search?q=' + __import__('urllib.parse').parse.quote(str(g.get('q', '')))); time.sleep(1); return {'ok': True}
    if a == 'open_app':
        n = str(g.get('name', '')).lower().strip().removesuffix('.exe'); n = APPS.get(n, n)
        if not n or n in BLOCK or any(c in n for c in '&|;<>'): return {'ok': False, 'msg': 'নিরাপত্তার কারণে চালানো হবে না'}
        try: os.startfile(n)
        except OSError:
            try: os.startfile(n + '.exe')
            except OSError as e: return {'ok': False, 'msg': 'অ্যাপ পাওয়া যায়নি (%s)' % n}
        time.sleep(1.5); return {'ok': True}
    if a == 'open_path':
        p = _path(g.get('path', ''))
        if not os.path.exists(p): return {'ok': False, 'msg': 'পথ পাওয়া যায়নি: ' + p}
        if os.path.isfile(p) and os.path.splitext(p)[1].lower() in ('.exe', '.msi', '.bat', '.cmd', '.ps1', '.vbs', '.reg', '.scr', '.js'): return {'ok': False, 'msg': 'প্রোগ্রাম ফাইল এজেন্ট চালায় না — নিজে খুলুন'}
        os.startfile(p); time.sleep(1); return {'ok': True, 'msg': p}
    if a == 'type_text': _focus(); _type(g.get('text', '')); return {'ok': True}
    if a == 'hotkey': _focus(); _keys(g.get('keys') or []); time.sleep(.3); return {'ok': True}
    if a == 'press': _focus(); _keys([g.get('key', 'enter')]); time.sleep(.3); return {'ok': True}
    if a == 'wait': time.sleep(max(0, min(10, float(g.get('sec') or 1)))); return {'ok': True}
    if a == 'clipboard_set': clip_set(str(g.get('text', ''))); return {'ok': True}
    if a == 'screenshot': return {'ok': True, 'image': Api().screenshot()}
    if a == 'search_files':
        q = str(g.get('query', '')).lower().strip(); hits = []; t0 = time.time()
        roots = [os.path.expanduser('~/' + k) for k in ('Desktop', 'Documents', 'Downloads', 'OneDrive')] + [r'D:\Desktop Backup(Don' + "'" + r't Delete)\Downloads']
        for r in roots:
            for dp, dn, fn in os.walk(r):
                for f in fn:
                    if q and q in f.lower(): hits.append(os.path.join(dp, f))
                if len(hits) > 15 or time.time() - t0 > 8: break
        return {'ok': True, 'msg': ('পাওয়া গেছে:\n' + '\n'.join(hits[:15])) if hits else 'কিছু পাওয়া যায়নি'}
    return {'ok': False, 'msg': 'অজানা ধাপ'}
class Api:
    def token(self): return CFG['token']
    def bird(self, cmd, arg=''): out({'bird': cmd, 'arg': arg}); return True
    def status(self): return STATUS
    def agent_do(self, js):
        try: return agent_do(json.loads(js))
        except Exception as e: return {'ok': False, 'msg': str(e)[:160]}
    def clipboard(self):
        try: return clip_get()
        except Exception: return ''
    def copy(self, t):
        try: clip_set(str(t)); return True
        except Exception: return False
    def open(self, url):
        if str(url).startswith(('http://', 'https://')): webbrowser.open(url)
        return True
    def close(self): W.hide(); out({'bird': 'panel_closed'}); return True
    def screenshot(self):
        """Hide panel + bird, grab all screens, return PNG base64 (max 1600px) for 'ask AI about my screen'."""
        import time
        from PIL import ImageGrab
        W.hide(); out({'bird': 'hide_briefly'}); time.sleep(0.45)
        try:
            im = ImageGrab.grab(all_screens=True); im.thumbnail((1600, 1600)); b = io.BytesIO(); im.save(b, 'PNG'); return base64.b64encode(b.getvalue()).decode()
        finally: W.show()
def reader():
    for ln in sys.stdin:
        try:
            c = json.loads(ln)
            if c.get('cmd') == 'status': STATUS.clear(); STATUS.update(c['s'])
            elif c.get('cmd') == 'show':
                W.move(int(c['x']), int(c['y'])); W.show(); W.restore() if hasattr(W, 'restore') else None
                W.evaluate_js('window.rbtShow&&rbtShow(%s)' % json.dumps(c.get('tab') or ''))
            elif c.get('cmd') == 'quit': W.destroy(); return
        except Exception as e: out({'err': str(e)[:200]})
    W.destroy()
W = webview.create_window('রয়্যাল এজেন্ট', CFG['base'].rstrip('/') + '/bb/static/notes/panel.html?m=win', js_api=Api(), width=420, height=640, x=int(CFG.get('x', 200)), y=int(CFG.get('y', 100)),
                          frameless=True, easy_drag=False, on_top=True, transparent=True, background_color='#0b1a33', resizable=True)
def started(): threading.Thread(target=reader, daemon=True).start(); threading.Thread(target=_fg_watch, daemon=True).start()
webview.start(started, private_mode=False, storage_path=__import__('os').path.expanduser('~/.rbt_panel'))
