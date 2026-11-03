"""Royal Doyel panel — borderless animated glass panel (pywebview / Edge WebView2) shown when the bird is clicked.
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
class Api:
    def token(self): return CFG['token']
    def bird(self, cmd, arg=''): out({'bird': cmd, 'arg': arg}); return True
    def status(self): return STATUS
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
W = webview.create_window('রয়েল দোয়েল', CFG['base'].rstrip('/') + '/bb/static/notes/panel.html?m=win', js_api=Api(), width=420, height=640, x=int(CFG.get('x', 200)), y=int(CFG.get('y', 100)),
                          frameless=True, easy_drag=False, on_top=True, transparent=True, background_color='#0b1a33', resizable=True)
def started(): threading.Thread(target=reader, daemon=True).start()
webview.start(started, private_mode=False, storage_path=__import__('os').path.expanduser('~/.rbt_panel'))
