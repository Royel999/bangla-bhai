"""Royal Clip — clipboard watcher + always-on-top floating notebook bubble (Windows/Linux/macOS, tkinter).
Visible by design: the 📒 bubble is always on screen while capture runs; right-click → ⏸ pause. Passwords/OTPs/card numbers are skipped
locally before anything is sent. Clips go to <BASE>/bb/link/clip with the device link token; kept 30 days on the server."""
import re, json, time, threading, base64, io, hashlib, os
import urllib.request as U
SENS = [re.compile(p, re.I) for p in (r'\b\d{4,8}\b.{0,40}\b(otp|code|কোড|পিন|pin|verification)\b', r'\b(otp|code|কোড|pin|verification)\b.{0,40}\b\d{4,8}\b',
        r'^\s*\d{4,8}\s*$', r'(password|passwd|pwd|পাসওয়ার্ড)\s*[:=]', r'-----BEGIN [A-Z ]*PRIVATE KEY', r'\b(sk|pk|ghp|gho|xox[bpa]|AKIA)[-_A-Za-z0-9]{16,}')]
def _luhn(s):
    d = [int(c) for c in re.sub(r'\D', '', s)][::-1]
    return 13 <= len(d) <= 19 and sum(x if i % 2 == 0 else (x * 2 - 9 if x * 2 > 9 else x * 2) for i, x in enumerate(d)) % 10 == 0
def sensitive(t):
    if any(p.search(t) for p in SENS): return True
    if any(_luhn(m.group(0)) for m in re.finditer(r'(?:\d[ -]?){13,19}', t)): return True
    s = t.strip()
    return ' ' not in s and 8 <= len(s) <= 64 and not s.startswith(('http', 'www')) and '@' not in s and sum(bool(re.search(p, s)) for p in (r'[a-z]', r'[A-Z]', r'\d', r'[^\w]')) >= 3
PAUSE_F = os.path.expanduser('~/.rbt_clip_pause')
class Clip:
    def __init__(self, base, token, status=None):
        self.base, self.tok, self.status = base.rstrip('/'), token, status or {}
        self.paused = os.path.exists(PAUSE_F); self.last = None; self.root = None; self.mini = None
    def post(self, path, data):
        req = U.Request(self.base + path, data=json.dumps(data).encode(), method='POST', headers={'Content-Type': 'application/json', 'User-Agent': 'RoyalLink/2.1'})
        with U.urlopen(req, timeout=20) as r: return json.loads(r.read())
    def get(self, path):
        with U.urlopen(U.Request(self.base + path, headers={'User-Agent': 'RoyalLink/2.1'}), timeout=20) as r: return json.loads(r.read())
    def send(self, kind, content):
        def go():
            try: self.post('/bb/link/clip', {'token': self.tok, 'kind': kind, 'content': content})
            except Exception as e: print('clip send failed', e)
        threading.Thread(target=go, daemon=True).start()
    def poll(self):
        try:
            if not self.paused:
                try: t = self.root.clipboard_get()
                except Exception: t = None
                if t:
                    h = hashlib.sha1(t.encode('utf-8', 'ignore')).hexdigest()
                    if h != self.last:
                        first = self.last is None; self.last = h
                        if not first and t.strip() and len(t) < 200000 and not sensitive(t): self.send('text', t)
                else:
                    try:
                        from PIL import ImageGrab, Image
                        im = ImageGrab.grabclipboard()
                        if isinstance(im, Image.Image):
                            h = hashlib.sha1(im.tobytes()[:200000]).hexdigest()
                            if h != self.last:
                                first = self.last is None; self.last = h
                                if not first:
                                    im.thumbnail((1280, 1280)); b = io.BytesIO(); im.convert('RGB').save(b, 'JPEG', quality=70)
                                    self.send('image', 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode())
                    except Exception: pass
        finally: self.root.after(1200, self.poll)
    def toggle_pause(self):
        self.paused = not self.paused
        if self.paused: open(PAUSE_F, 'w').close()
        elif os.path.exists(PAUSE_F): os.remove(PAUSE_F)
        self.paint()
    def paint(self):
        self.lbl.config(text='⏸' if self.paused else '📒', bg='#666666' if self.paused else '#ff8c1a')
    def run(self):
        import tkinter as tk
        r = self.root = tk.Tk(); r.overrideredirect(True); r.attributes('-topmost', True)
        try: r.attributes('-alpha', 0.92)
        except Exception: pass
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        pos = self._load_pos() or (sw - 80, sh // 2)
        r.geometry('56x56+%d+%d' % pos)
        self.lbl = tk.Label(r, text='📒', font=('Segoe UI Emoji', 22), bg='#ff8c1a', fg='white', cursor='hand2'); self.lbl.pack(fill='both', expand=True)
        d = {}
        def down(e): d.update(x=e.x_root, y=e.y_root, wx=r.winfo_x(), wy=r.winfo_y(), m=False)
        def move(e):
            dx, dy = e.x_root - d['x'], e.y_root - d['y']
            if abs(dx) + abs(dy) > 4: d['m'] = True
            r.geometry('+%d+%d' % (d['wx'] + dx, d['wy'] + dy))
        def up(e):
            if d.get('m'): self._save_pos(r.winfo_x(), r.winfo_y())
            else: self.open_mini()
        self.lbl.bind('<ButtonPress-1>', down); self.lbl.bind('<B1-Motion>', move); self.lbl.bind('<ButtonRelease-1>', up)
        menu = tk.Menu(r, tearoff=0)
        menu.add_command(label='📝 দ্রুত নোট / ক্লিপ', command=self.open_mini)
        menu.add_command(label='⏸ / ▶ ক্লিপবোর্ড ধরা থামান/চালু', command=self.toggle_pause)
        menu.add_command(label='📖 নোটবুক খুলুন', command=lambda: __import__('webbrowser').open(self.base + '/notes/'))
        menu.add_command(label='🗂 ক্লিপবোর্ড ইতিহাস', command=lambda: __import__('webbrowser').open(self.base + '/notes/?view=clips'))
        menu.add_command(label='বাবল লুকান (এই সেশনে)', command=r.withdraw)
        self.lbl.bind('<Button-3>', lambda e: menu.tk_popup(e.x_root, e.y_root))
        self.paint(); r.after(800, self.poll); r.mainloop()
    def _load_pos(self):
        try: return tuple(json.load(open(os.path.expanduser('~/.rbt_bubble.json'))))
        except Exception: return None
    def _save_pos(self, x, y):
        try: json.dump([x, y], open(os.path.expanduser('~/.rbt_bubble.json'), 'w'))
        except Exception: pass
    def open_mini(self):
        import tkinter as tk
        if self.mini and self.mini.winfo_exists(): self.mini.lift(); return
        w = self.mini = tk.Toplevel(self.root); w.title('রয়েল নোটবুক · দ্রুত নোট'); w.attributes('-topmost', True); w.configure(bg='#11264a')
        x = max(0, self.root.winfo_x() - 360); w.geometry('360x460+%d+%d' % (x, max(0, self.root.winfo_y() - 200)))
        F = ('Nirmala UI', 10)
        tk.Label(w, text='📒 দ্রুত নোট', bg='#11264a', fg='#d4af37', font=('Nirmala UI', 12, 'bold')).pack(anchor='w', padx=8, pady=(8, 2))
        txt = tk.Text(w, height=7, wrap='word', font=F, bg='#172f5a', fg='white', insertbackground='white'); txt.pack(fill='x', padx=8); txt.focus_set()
        st = tk.Label(w, text='', bg='#11264a', fg='#9fb0cf', font=F); 
        def save():
            body = txt.get('1.0', 'end').strip()
            if not body: return
            try: self.post('/bb/link/note', {'token': self.tok, 'body': body}); txt.delete('1.0', 'end'); st.config(text='✓ নোটবুকে রাখা হয়েছে')
            except Exception as e: st.config(text='⚠ পাঠানো যায়নি: ' + str(e)[:60])
        bf = tk.Frame(w, bg='#11264a'); bf.pack(fill='x', padx=8, pady=4)
        tk.Button(bf, text='💾 রাখুন (Ctrl+Enter)', command=save, bg='#ff8c1a', fg='white', relief='flat', font=F).pack(side='left')
        tk.Button(bf, text='⏸ থামান' if not self.paused else '▶ চালু', command=lambda: (self.toggle_pause(), w.destroy(), self.open_mini()), relief='flat', font=F).pack(side='left', padx=4)
        tk.Button(bf, text='📖', command=lambda: __import__('webbrowser').open(self.base + '/notes/'), relief='flat', font=F).pack(side='left')
        st.pack(anchor='w', padx=8); txt.bind('<Control-Return>', lambda e: (save(), 'break'))
        tk.Label(w, text='সাম্প্রতিক কপি (ক্লিক = আবার কপি)', bg='#11264a', fg='#9fb0cf', font=F).pack(anchor='w', padx=8, pady=(6, 0))
        lb = tk.Listbox(w, font=F, bg='#0b1a33', fg='white', selectbackground='#d4af37', height=10); lb.pack(fill='both', expand=True, padx=8, pady=(0, 8))
        items = []
        def load():
            try:
                cl = self.get('/bb/link/clips?n=20&token=' + self.tok).get('clips', [])
                items[:] = cl; lb.delete(0, 'end')
                for c in cl: lb.insert('end', c['content'].replace('\n', ' ')[:70])
            except Exception as e: lb.insert('end', '⚠ লোড হয়নি')
        def pick(e):
            i = lb.curselection()
            if i: self.root.clipboard_clear(); self.root.clipboard_append(items[i[0]]['content']); st.config(text='📋 কপি হলো')
        lb.bind('<<ListboxSelect>>', pick); threading.Thread(target=lambda: w.after(0, load), daemon=True).start()
        w.bind('<Escape>', lambda e: w.destroy())
