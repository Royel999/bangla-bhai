"""Royal Notes: editable notebook for logged-in users (per-user). Stored in data.db (backed up by persist).
Tables: notes, note_versions, note_files. API under /bb/api/notes; UI at /notes (static/notes/)."""
import json, time, uuid, re, os, base64
from fastapi import Request, UploadFile, File
from fastapi.responses import JSONResponse, Response, FileResponse, RedirectResponse
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'notes')
MAXF = 8 * 1024 * 1024
MAXV = 50
SCHEMA = """create table if not exists notes(id text primary key,user text,title text,body text,folder text default '',tags text default '[]',
 pinned int default 0,fav int default 0,archived int default 0,trashed int default 0,color text default '',created real,updated real);
create index if not exists notes_u on notes(user,updated);
create table if not exists note_versions(id integer primary key autoincrement,note_id text,title text,body text,ts real);
create index if not exists nv_n on note_versions(note_id,ts);
create table if not exists note_files(id text primary key,note_id text,user text,name text,mime text,size int,data blob,created real);"""
AI = {
 'summarize': 'নিচের নোটটির সংক্ষিপ্ত সারাংশ দাও (নোটের ভাষাতেই, বুলেট পয়েন্টে)। শুধু সারাংশ দাও।',
 'to_bn': 'নিচের লেখাটি স্বাভাবিক, শুদ্ধ বাংলায় অনুবাদ করো। Markdown ফরম্যাট বজায় রাখো। শুধু অনুবাদ দাও।',
 'to_en': 'Translate the following note into natural English. Keep Markdown formatting. Output only the translation.',
 'fix': 'নিচের লেখার বানান, ব্যাকরণ ও বিরামচিহ্ন ঠিক করো, অর্থ ও ভাষা একই রাখো, Markdown বজায় রাখো। শুধু সংশোধিত লেখা দাও।',
 'todo': 'নিচের নোট থেকে করণীয় কাজগুলো বের করে Markdown চেকলিস্ট বানাও, প্রতিটি লাইন "- [ ] কাজ" আকারে; তারিখ থাকলে শেষে "@YYYY-MM-DD" যোগ করো। শুধু চেকলিস্ট দাও।',
 'title': 'নিচের নোটের জন্য ৩-৬ শব্দের একটি শিরোনাম দাও (নোটের ভাষায়)। শুধু শিরোনাম।',
 'expand': 'নিচের নোটটিকে আরো বিস্তারিত, গোছানো ও স্পষ্ট করে লেখো (একই ভাষায়, Markdown)। শুধু লেখাটি দাও।',
}
TASK = re.compile(r'^\s*[-*]\s+\[( |x|X)\]\s+(.*)$')
DUE = re.compile(r'@(\d{4}-\d{2}-\d{2})')
def _row(r, full=True):
    d = dict(r); d['tags'] = json.loads(d.get('tags') or '[]')
    if not full: d['body'] = (d.get('body') or '')[:240]
    return d
def setup(app, HH):
    db, need, RT, audit = HH['db'], HH['need'], HH['RT'], HH['audit']
    with db() as c: c.executescript(SCHEMA)
    def U(request):
        try: return need(request)
        except PermissionError: return None
    def W(request):  # write guard: custom header forces CORS preflight (CSRF-safe)
        return request.headers.get('x-bb-notes') == '1'
    E401 = lambda: JSONResponse({'error': 'unauthorized'}, 401)
    E400 = lambda m='bad request': JSONResponse({'error': m}, 400)
    def own(c, u, nid):
        return c.execute('select * from notes where id=? and user=?', (nid, u)).fetchone()
    @app.get('/notes', include_in_schema=False)
    def p0(request: Request): return RedirectResponse('/notes/', 307)
    @app.get('/notes/', include_in_schema=False)
    def page(request: Request):
        if not U(request): return RedirectResponse('/v4?next=/notes/', 303)
        return FileResponse(D + '/index.html', headers={'Cache-Control': 'no-cache'})
    @app.get('/notes/{name}', include_in_schema=False)
    def asset(name: str):
        m = {'notes.js': 'application/javascript', 'notes.css': 'text/css', 'sw.js': 'application/javascript', 'manifest.webmanifest': 'application/manifest+json'}
        if name not in m: return Response('Not found', 404)
        return FileResponse(D + '/' + name, media_type=m[name], headers={'Cache-Control': 'no-cache'})
    @app.get('/bb/api/notes')
    def lst(request: Request, q: str = '', folder: str = '', tag: str = '', view: str = 'all'):
        u = U(request)
        if not u: return E401()
        w, a = ['user=?'], [u]
        if view == 'trash': w.append('trashed=1')
        else:
            w.append('trashed=0')
            w.append('archived=1' if view == 'archive' else 'archived=0')
            if view == 'fav': w.append('fav=1')
        if folder: w.append('folder=?'); a.append(folder)
        if tag: w.append('tags like ?'); a.append('%' + json.dumps(tag, ensure_ascii=False)[1:-1].join(['"', '"']) + '%')
        for t in q.split()[:6]:
            w.append('(title like ? or body like ? or tags like ?)'); a += ['%' + t + '%'] * 3
        with db() as c:
            rows = c.execute('select * from notes where ' + ' and '.join(w) + ' order by pinned desc, updated desc limit 500', a).fetchall()
            meta = c.execute('select folder, tags from notes where user=? and trashed=0', (u,)).fetchall()
        fo, tg = {}, {}
        for m in meta:
            if m['folder']: fo[m['folder']] = fo.get(m['folder'], 0) + 1
            for t in json.loads(m['tags'] or '[]'): tg[t] = tg.get(t, 0) + 1
        return {'notes': [_row(r, False) for r in rows], 'folders': fo, 'tags': tg}
    @app.get('/bb/api/notes/tasks')
    def tasks(request: Request):
        u = U(request)
        if not u: return E401()
        out = []
        with db() as c:
            for r in c.execute('select id,title,body from notes where user=? and trashed=0 and archived=0', (u,)):
                for i, ln in enumerate((r['body'] or '').split('\n')):
                    m = TASK.match(ln)
                    if m:
                        dm = DUE.search(m.group(2))
                        out.append({'note': r['id'], 'title': r['title'], 'line': i, 'done': m.group(1) != ' ', 'text': DUE.sub('', m.group(2)).strip(), 'due': dm.group(1) if dm else None})
        out.sort(key=lambda t: (t['done'], t['due'] or '9999'))
        return {'tasks': out}
    @app.post('/bb/api/notes')
    async def create(request: Request):
        u = U(request)
        if not u: return E401()
        if not W(request): return E400()
        j = await request.json(); now = time.time(); nid = j.get('id') or uuid.uuid4().hex[:12]
        if not re.fullmatch(r'[A-Za-z0-9_-]{6,40}', nid): return E400('bad id')
        with db() as c:
            if c.execute('select 1 from notes where id=?', (nid,)).fetchone(): return E400('exists')
            c.execute('insert into notes(id,user,title,body,folder,tags,pinned,fav,color,created,updated) values(?,?,?,?,?,?,?,?,?,?,?)',
                (nid, u, str(j.get('title', ''))[:300], str(j.get('body', ''))[:500000], str(j.get('folder', ''))[:80], json.dumps([str(t)[:40] for t in j.get('tags', [])][:30], ensure_ascii=False),
                 int(bool(j.get('pinned'))), int(bool(j.get('fav'))), str(j.get('color', ''))[:20], now, now))
            r = own(c, u, nid)
        return _row(r)
    @app.get('/bb/api/notes/{nid}')
    def get(nid: str, request: Request):
        u = U(request)
        if not u: return E401()
        with db() as c:
            r = own(c, u, nid)
            if not r: return JSONResponse({'error': 'not found'}, 404)
            fs = [dict(x) for x in c.execute('select id,name,mime,size,created from note_files where note_id=? and user=?', (nid, u))]
        d = _row(r); d['files'] = fs; return d
    @app.put('/bb/api/notes/{nid}')
    async def upd(nid: str, request: Request):
        u = U(request)
        if not u: return E401()
        if not W(request): return E400()
        j = await request.json(); now = time.time()
        with db() as c:
            r = own(c, u, nid)
            if not r: return JSONResponse({'error': 'not found'}, 404)
            if j.get('base') and float(j['base']) + 0.001 < r['updated'] and not j.get('force'):
                return JSONResponse({'error': 'conflict', 'server': _row(r)}, 409)
            if ('body' in j and j['body'] != r['body']) or ('title' in j and j['title'] != r['title']):
                last = c.execute('select ts from note_versions where note_id=? order by ts desc limit 1', (nid,)).fetchone()
                if not last or now - last['ts'] > 120 or j.get('snapshot'):
                    c.execute('insert into note_versions(note_id,title,body,ts) values(?,?,?,?)', (nid, r['title'], r['body'], now))
                    c.execute('delete from note_versions where note_id=? and id not in (select id from note_versions where note_id=? order by ts desc limit ?)', (nid, nid, MAXV))
            f, a = [], []
            for k, lim in (('title', 300), ('body', 500000), ('folder', 80), ('color', 20)):
                if k in j: f.append(k + '=?'); a.append(str(j[k])[:lim])
            for k in ('pinned', 'fav', 'archived', 'trashed'):
                if k in j: f.append(k + '=?'); a.append(int(bool(j[k])))
            if 'tags' in j: f.append('tags=?'); a.append(json.dumps([str(t)[:40] for t in j['tags']][:30], ensure_ascii=False))
            f.append('updated=?'); a.append(now)
            c.execute('update notes set ' + ','.join(f) + ' where id=? and user=?', a + [nid, u])
            r = own(c, u, nid)
        return _row(r)
    @app.delete('/bb/api/notes/{nid}')
    def dele(nid: str, request: Request):
        u = U(request)
        if not u: return E401()
        if not W(request): return E400()
        with db() as c:
            r = own(c, u, nid)
            if not r: return JSONResponse({'error': 'not found'}, 404)
            if not r['trashed']: c.execute('update notes set trashed=1,updated=? where id=?', (time.time(), nid)); return {'ok': True, 'trashed': True}
            c.execute('delete from notes where id=?', (nid,)); c.execute('delete from note_versions where note_id=?', (nid,)); c.execute('delete from note_files where note_id=?', (nid,))
        return {'ok': True, 'deleted': True}
    @app.get('/bb/api/notes/{nid}/versions')
    def vers(nid: str, request: Request):
        u = U(request)
        if not u: return E401()
        with db() as c:
            if not own(c, u, nid): return JSONResponse({'error': 'not found'}, 404)
            return {'versions': [dict(x) for x in c.execute('select id,title,body,ts from note_versions where note_id=? order by ts desc', (nid,))]}
    @app.post('/bb/api/notes/{nid}/files')
    async def up(nid: str, request: Request, file: UploadFile = File(...)):
        u = U(request)
        if not u: return E401()
        if not W(request): return E400()
        data = await file.read()
        if len(data) > MAXF: return E400('ফাইল ৮ MB-এর বেশি')
        with db() as c:
            if not own(c, u, nid): return JSONResponse({'error': 'not found'}, 404)
            tot = c.execute('select coalesce(sum(size),0) from note_files where user=?', (u,)).fetchone()[0]
            if tot + len(data) > 200 * 1024 * 1024: return E400('মোট ২০০ MB সীমা পূর্ণ')
            fid = uuid.uuid4().hex[:16]
            c.execute('insert into note_files values(?,?,?,?,?,?,?,?)', (fid, nid, u, (file.filename or 'file')[:120], file.content_type or 'application/octet-stream', len(data), data, time.time()))
        return {'id': fid, 'name': file.filename, 'mime': file.content_type, 'size': len(data), 'url': '/bb/api/notes/file/' + fid}
    @app.get('/bb/api/notes/file/{fid}')
    def fget(fid: str, request: Request):
        u = U(request)
        if not u: return E401()
        with db() as c: r = c.execute('select * from note_files where id=? and user=?', (fid, u)).fetchone()
        if not r: return Response('Not found', 404)
        safe = r['mime'] if r['mime'].startswith(('image/', 'audio/', 'video/')) and 'svg' not in r['mime'] else 'application/octet-stream'
        disp = 'inline' if safe != 'application/octet-stream' else 'attachment'
        from urllib.parse import quote
        return Response(r['data'], media_type=safe, headers={'Content-Disposition': disp + "; filename*=UTF-8''" + quote(r['name']), 'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'private, max-age=86400'})
    @app.delete('/bb/api/notes/file/{fid}')
    def fdel(fid: str, request: Request):
        u = U(request)
        if not u: return E401()
        if not W(request): return E400()
        with db() as c: c.execute('delete from note_files where id=? and user=?', (fid, u))
        return {'ok': True}
    @app.post('/bb/api/notes/{nid}/ai')
    async def ai(nid: str, request: Request):
        u = U(request)
        if not u: return E401()
        if not W(request): return E400()
        j = await request.json(); act = j.get('action')
        if act not in AI and act != 'ask': return E400('unknown action')
        with db() as c: r = own(c, u, nid)
        if not r: return JSONResponse({'error': 'not found'}, 404)
        txt = (j.get('text') or r['body'] or '')[:24000]
        if not txt.strip(): return E400('নোট খালি')
        sysm = AI.get(act) or ('নোটটির ভিত্তিতে প্রশ্নের উত্তর দাও (প্রশ্নের ভাষায়)। প্রশ্ন: ' + str(j.get('q', ''))[:1000])
        try:
            _, t, _ = await RT.complete([{'role': 'system', 'content': sysm}, {'role': 'user', 'content': txt}], timeout=60, tries=2)
        except Exception as e:
            return JSONResponse({'error': 'AI এখন ব্যস্ত, একটু পরে চেষ্টা করুন'}, 503)
        t = re.sub(r'<think>.*?</think>', '', t or '', flags=re.S).strip()
        try: audit(ev='notes_ai', act=act)
        except Exception: pass
        return {'text': t}
    @app.get('/bb/api/notes/{nid}/export.md')
    def exp(nid: str, request: Request):
        u = U(request)
        if not u: return E401()
        with db() as c: r = own(c, u, nid)
        if not r: return Response('Not found', 404)
        from urllib.parse import quote
        tags = json.loads(r['tags'] or '[]')
        md = '# ' + (r['title'] or 'Untitled') + '\n\n' + (('Tags: ' + ', '.join('#' + t for t in tags) + '\n\n') if tags else '') + (r['body'] or '')
        return Response(md, media_type='text/markdown; charset=utf-8', headers={'Content-Disposition': "attachment; filename*=UTF-8''" + quote((r['title'] or 'note')[:60] + '.md')})

# ---------------- Clipboard history + smart features ----------------
CLIP_SCHEMA = """create table if not exists clips(id integer primary key autoincrement,user text,device text,kind text,cat text,content text,hash text,
 pinned int default 0,count int default 1,created real,last real);
create index if not exists clips_u on clips(user,last);
create unique index if not exists clips_h on clips(user,hash);"""
import hashlib as _hl, base64 as _b64
SENS = [re.compile(p, re.I) for p in (r'\b\d{4,8}\b.{0,40}\b(otp|code|কোড|পিন|pin|verification)\b', r'\b(otp|code|কোড|pin|verification)\b.{0,40}\b\d{4,8}\b',
        r'^\s*\d{4,8}\s*$', r'(?:\d[ -]?){13,19}', r'(password|passwd|pwd|পাসওয়ার্ড)\s*[:=]', r'-----BEGIN [A-Z ]*PRIVATE KEY', r'\b(sk|pk|ghp|gho|xox[bpa]|AKIA)[-_A-Za-z0-9]{16,}')]
def _luhn(s):
    d = [int(c) for c in re.sub(r'\D', '', s)][::-1]
    return 13 <= len(d) <= 19 and sum(x if i % 2 == 0 else (x * 2 - 9 if x * 2 > 9 else x * 2) for i, x in enumerate(d)) % 10 == 0
def sensitive(t):
    t = t or ''
    if any(p.search(t) for p in SENS[:3] + SENS[4:]): return True
    for m in SENS[3].finditer(t):
        if _luhn(m.group(0)): return True
    s = t.strip()  # looks like a password: single token, mixed classes, 8-64 chars
    if ' ' not in s and 8 <= len(s) <= 64 and not s.startswith(('http', 'www')) and sum(bool(re.search(p, s)) for p in (r'[a-z]', r'[A-Z]', r'\d', r'[^\w]')) >= 3 and '@' not in s: return True
    return False
def categorize(kind, t):
    if kind == 'image': return 'image'
    s = (t or '').strip()
    if re.fullmatch(r'(https?://|www\.)\S+', s): return 'link'
    if re.fullmatch(r'[\w.+-]+@[\w-]+\.[\w.-]+', s): return 'email'
    if re.fullmatch(r'[+]?[\d\s()০-৯-]{7,18}', s) and len(re.sub(r'\D', '', s)) >= 7: return 'phone'
    if re.search(r'[{};]\s*$|^\s*(def|function|import|const|let|class|SELECT|<\w+)\b|=>|\bfor\s*\(', s, re.M): return 'code'
    if re.search(r'\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{4}-\d{2}-\d{2}', s) and len(s) < 60: return 'date'
    if re.search(r'[\u0980-\u09FF]', s): return 'bangla'
    return 'text'
def suggest(cat, t):
    return {'link': ['🔗 লিংক খুলুন', '📝 পড়ার তালিকায় রাখুন'], 'email': ['✉️ ইমেইল লিখুন', '👤 যোগাযোগে রাখুন'], 'phone': ['📞 কল করুন', '👤 যোগাযোগে রাখুন'],
            'code': ['💻 কোড নোটে রাখুন', '✨ AI দিয়ে ব্যাখ্যা'], 'date': ['📅 কাজ হিসেবে রাখুন'], 'image': ['🖼 নোটে ছবি রাখুন']}.get(cat, ['📝 নোট বানান', '✨ সারাংশ'])
def setup_clips(app, HH):
    db, need, owner, AG, RT = HH['db'], HH['need'], HH['owner'], HH['AG'], HH['RT']
    with db() as c: c.executescript(CLIP_SCHEMA)
    def purge():
        with db() as c: c.execute('delete from clips where pinned=0 and last<?', (time.time() - 30 * 86400,))
    purge(); _P = {'t': time.time()}
    def U(request):
        if time.time() - _P['t'] > 3600: _P['t'] = time.time(); purge()
        try: return need(request)
        except PermissionError: return None
    def add(u, dev, kind, content):
        if not content or len(content) > 2_000_000: return {'skipped': 'size'}
        if kind != 'image' and sensitive(content): return {'skipped': 'private'}
        h = _hl.sha256((kind + ':' + content).encode()).hexdigest(); now = time.time(); cat = categorize(kind, content)
        if kind == 'text' and cat == 'link': kind = 'url'
        with db() as c:
            r = c.execute('select id from clips where user=? and hash=?', (u, h)).fetchone()
            if r: c.execute('update clips set last=?,count=count+1,device=? where id=?', (now, dev, r['id'])); return {'id': r['id'], 'dup': True, 'cat': cat}
            cur = c.execute('insert into clips(user,device,kind,cat,content,hash,created,last) values(?,?,?,?,?,?,?,?)', (u, dev, kind, cat, content, h, now, now))
            n = c.execute('select count(*) from clips where user=? and pinned=0', (u,)).fetchone()[0]
            if n > 5000: c.execute('delete from clips where id in (select id from clips where user=? and pinned=0 order by last limit ?)', (u, n - 5000))
            return {'id': cur.lastrowid, 'cat': cat}
    def row(r, full=False):
        d = dict(r); d.pop('hash', None); d['suggest'] = suggest(d['cat'], d['content'])
        if d['kind'] == 'image' and not full: d['content'] = d['content'][:200000]
        return d
    @app.post('/bb/api/clips')
    async def cpost(request: Request):
        u = U(request)
        if not u: return JSONResponse({'error': 'unauthorized'}, 401)
        if request.headers.get('x-bb-notes') != '1': return JSONResponse({'error': 'bad request'}, 400)
        j = await request.json()
        return add(u, str(j.get('device') or 'web')[:40], j.get('kind') if j.get('kind') in ('text', 'image', 'url') else 'text', str(j.get('content') or ''))
    @app.post('/bb/link/clip')
    async def lpost(request: Request):
        j = await request.json(); d = AG.dev_by_token(j.get('token', ''))
        if not d or d['status'] != 'approved': return JSONResponse({'error': 'unauthorized'}, 403)
        kind = j.get('kind') if j.get('kind') in ('text', 'image', 'url') else 'text'
        return add(owner, (d['name'] or d['id'])[:40], kind, str(j.get('content') or ''))
    @app.get('/bb/link/clips')
    def lget(token: str, n: int = 15):
        d = AG.dev_by_token(token)
        if not d or d['status'] != 'approved': return JSONResponse({'error': 'unauthorized'}, 403)
        with db() as c: rs = c.execute("select id,kind,cat,substr(content,1,500) content,last,pinned from clips where user=? and kind!='image' order by last desc limit ?", (owner, min(n, 50))).fetchall()
        return {'clips': [dict(r) for r in rs]}
    @app.post('/bb/link/note')
    async def lnote(request: Request):
        j = await request.json(); d = AG.dev_by_token(j.get('token', ''))
        if not d or d['status'] != 'approved': return JSONResponse({'error': 'unauthorized'}, 403)
        body = str(j.get('body') or '')[:100000]
        if not body.strip(): return JSONResponse({'error': 'empty'}, 400)
        nid = uuid.uuid4().hex[:12]; now = time.time(); title = str(j.get('title') or body.strip().split('\n')[0][:60])
        with db() as c: c.execute("insert into notes(id,user,title,body,folder,tags,created,updated) values(?,?,?,?,?,?,?,?)", (nid, owner, title, body, 'দ্রুত নোট', '[]', now, now))
        return {'id': nid}
    # ---- bird panel (device token): AI ask / translate / summarise / screen, today hub, note search ----
    MODES = {'ask': 'তুমি রয়েল নোটবুকের সহকারী। সংক্ষেপে, প্রশ্নের ভাষায় (ডিফল্ট বাংলা) উত্তর দাও।',
             'translate': 'Translate the text: Bangla→English, any other language→Bangla. Output only the translation.',
             'summarise': 'নিচের লেখাটির ৩-৫ বুলেটে বাংলায় সারাংশ দাও।',
             'explain': 'নিচের লেখা/কোড সহজ বাংলায় ব্যাখ্যা করো, সংক্ষেপে।',
             'screen': 'ব্যবহারকারীর স্ক্রিনের লেখা (OCR) ও প্রশ্ন দেওয়া হলো। স্ক্রিনে কী আছে বুঝে প্রশ্নের উত্তর দাও, সংক্ষেপে বাংলায়।'}
    _ASKT = {}
    def dev_ok(tok, request=None):
        d = AG.dev_by_token(tok or '') if tok else None
        if d and d['status'] == 'approved': return d
        if request is not None and U(request) == owner and (request.method == 'GET' or request.headers.get('x-bb-notes') == '1'): return {'id': 'web', 'name': 'ওয়েব', 'status': 'approved'}
        return None
    @app.post('/bb/link/ask')
    async def lask(request: Request):
        j = await request.json(); d = dev_ok(j.get('token'), request)
        if not d: return JSONResponse({'error': 'unauthorized'}, 403)
        L = [t for t in _ASKT.get(d['id'], []) if time.time() - t < 3600]
        if len(L) >= 60: return JSONResponse({'error': 'ঘণ্টায় ৬০টির সীমা'}, 429)
        _ASKT[d['id']] = L + [time.time()]
        mode = j.get('mode') if j.get('mode') in MODES else 'ask'; q = str(j.get('q') or '')[:4000]; text = str(j.get('text') or '')[:20000]
        if mode == 'screen' and j.get('image_b64'):
            try:
                import ocr, asyncio
                data = base64.b64decode(j['image_b64'])[:8 * 1024 * 1024]
                text = (await asyncio.to_thread(ocr.cloud_image_text, data, 'image/png'))[:16000] or text
            except Exception as e: text = text or ('(স্ক্রিন পড়া যায়নি: %s)' % str(e)[:80])
        if not (q or text).strip(): return JSONResponse({'error': 'empty'}, 400)
        user = text if not q else (q + (('\n\n---\n' + text) if text else ''))
        try:
            _, t, _ = await RT.complete([{'role': 'system', 'content': MODES[mode]}, {'role': 'user', 'content': user}], timeout=60, tries=2)
            return {'answer': re.sub(r'<think>.*?</think>', '', t or '', flags=re.S).strip()}
        except Exception: return JSONResponse({'error': 'AI এখন ব্যস্ত, একটু পরে চেষ্টা করুন'}, 503)
    @app.get('/bb/link/hub')
    def lhub(request: Request, token: str = ''):
        d = dev_ok(token, request)
        if not d: return JSONResponse({'error': 'unauthorized'}, 403)
        today = time.strftime('%Y-%m-%d', time.gmtime(time.time() + 6 * 3600)); tasks = []
        with db() as c:
            for r in c.execute('select id,title,body from notes where user=? and trashed=0 and archived=0', (owner,)):
                for ln in (r['body'] or '').split('\n'):
                    m = TASK.match(ln)
                    if m and m.group(1) == ' ':
                        dm = DUE.search(m.group(2)); due = dm.group(1) if dm else None
                        if due and due <= today: tasks.append({'note': r['id'], 'text': DUE.sub('', m.group(2)).strip()[:120], 'due': due, 'late': due < today})
            nn = c.execute('select count(*) from notes where user=? and trashed=0', (owner,)).fetchone()[0]
            nc = c.execute('select count(*) from clips where user=?', (owner,)).fetchone()[0]
        busy = 0
        try:
            import device_hub as DH
            if d['id'] == 'web': busy = sum(len(v) for v in DH.INFLIGHT.values()); online = True
            else: busy = len(DH.INFLIGHT.get(d['id'], {})); online = DH.online(d['id'])
        except Exception: online = True
        return {'today': today, 'tasks': sorted(tasks, key=lambda t: t['due'])[:15], 'notes': nn, 'clips': nc, 'device': {'name': d['name'], 'online': online, 'busy': busy}}
    @app.get('/bb/link/search')
    def lsearch(request: Request, q: str, token: str = ''):
        if not dev_ok(token, request): return JSONResponse({'error': 'unauthorized'}, 403)
        w, a = ['user=? and trashed=0'], [owner]
        for t in q.split()[:6]: w.append('(title like ? or body like ?)'); a += ['%' + t + '%'] * 2
        with db() as c: rs = c.execute('select id,title,substr(body,1,160) body from notes where ' + ' and '.join(w) + ' order by updated desc limit 12', a).fetchall()
        return {'notes': [dict(r) for r in rs]}
    @app.post('/bb/link/stt')
    async def lstt(request: Request, token: str = '', file: UploadFile = File(...)):
        d = dev_ok(token, request)
        if not d: return JSONResponse({'error': 'unauthorized'}, 403)
        data = await file.read(10_000_001)
        if len(data) > 10_000_000: return JSONResponse({'error': 'too large'}, 413)
        try: t, _ = await AG.stt(data, file.content_type); return {'text': t}
        except Exception as e: return JSONResponse({'error': str(e)[:200]}, 502)
    @app.get('/bb/api/clips')
    def cget(request: Request, q: str = '', cat: str = '', limit: int = 100):
        u = U(request)
        if not u: return JSONResponse({'error': 'unauthorized'}, 401)
        w, a = ['user=?'], [u]
        if cat: w.append('cat=?'); a.append(cat)
        for t in q.split()[:6]: w.append("kind!='image' and content like ?"); a.append('%' + t + '%')
        with db() as c:
            rs = c.execute('select * from clips where ' + ' and '.join(w) + ' order by pinned desc,last desc limit ?', a + [min(limit, 300)]).fetchall()
            cats = {r['cat']: r['n'] for r in c.execute('select cat,count(*) n from clips where user=? group by cat', (u,))}
        return {'clips': [row(r) for r in rs], 'cats': cats, 'keep_days': 30}
    @app.put('/bb/api/clips/{cid}')
    async def cput(cid: int, request: Request):
        u = U(request)
        if not u or request.headers.get('x-bb-notes') != '1': return JSONResponse({'error': 'unauthorized'}, 401)
        j = await request.json()
        with db() as c: c.execute('update clips set pinned=? where id=? and user=?', (int(bool(j.get('pinned'))), cid, u))
        return {'ok': True}
    @app.delete('/bb/api/clips/{cid}')
    def cdel(cid: int, request: Request):
        u = U(request)
        if not u or request.headers.get('x-bb-notes') != '1': return JSONResponse({'error': 'unauthorized'}, 401)
        with db() as c:
            if cid == 0: c.execute('delete from clips where user=? and pinned=0', (u,))
            else: c.execute('delete from clips where id=? and user=?', (cid, u))
        return {'ok': True}
    @app.get('/bb/api/clips/digest')
    async def digest(request: Request, ai: int = 1):
        u = U(request)
        if not u: return JSONResponse({'error': 'unauthorized'}, 401)
        with db() as c: rs = c.execute("select cat,substr(content,1,300) content,device from clips where user=? and kind!='image' and last>? order by last desc limit 80", (u, time.time() - 86400)).fetchall()
        cats = {}
        for r in rs: cats[r['cat']] = cats.get(r['cat'], 0) + 1
        out = {'count': len(rs), 'cats': cats, 'summary': ''}
        if ai and rs:
            try:
                _, t, _ = await RT.complete([{'role': 'system', 'content': 'এগুলো আজ ব্যবহারকারী যা কপি করেছেন। বাংলায় ৩-৬ বুলেটে সংক্ষিপ্ত দৈনিক সারাংশ দাও: কী নিয়ে কাজ করছেন, জরুরি লিংক/নম্বর, আর পরামর্শ (কী নোট/কাজ বানানো উচিত)।'},
                                             {'role': 'user', 'content': '\n---\n'.join(r['content'] for r in rs)[:12000]}], timeout=60, tries=2)
                out['summary'] = re.sub(r'<think>.*?</think>', '', t or '', flags=re.S).strip()
            except Exception: out['summary'] = ''
        return out
    # ---- smart notes: related + auto tag/title + semantic-ish search ----
    def toks(s):
        return {w for w in re.findall(r'[\w\u0980-\u09FF]{3,}', (s or '').lower()) if w not in STOP}
    @app.get('/bb/api/notes/{nid}/related')
    def related(nid: str, request: Request):
        u = U(request)
        if not u: return JSONResponse({'error': 'unauthorized'}, 401)
        with db() as c:
            me = c.execute('select * from notes where id=? and user=?', (nid, u)).fetchone()
            if not me: return JSONResponse({'error': 'not found'}, 404)
            rs = c.execute('select id,title,body,tags,updated from notes where user=? and trashed=0 and id!=?', (u, nid)).fetchall()
        a = toks(me['title'] + ' ' + me['body'] + ' ' + me['tags']); sc = []
        for r in rs:
            b = toks(r['title'] + ' ' + r['body'] + ' ' + r['tags'])
            if a and b:
                s = len(a & b) / (len(a | b) ** .5)
                if s > 0.15: sc.append((s, {'id': r['id'], 'title': r['title'], 'score': round(s, 2)}))
        return {'related': [x[1] for x in sorted(sc, key=lambda x: -x[0])[:6]]}
    @app.get('/bb/api/notes-smart/search')
    async def ssearch(request: Request, q: str):
        u = U(request)
        if not u: return JSONResponse({'error': 'unauthorized'}, 401)
        qs = toks(q)
        try:
            _, t, _ = await RT.complete([{'role': 'system', 'content': 'Give 8 search keywords (Bangla and English synonyms/translations) for the query, comma separated, nothing else.'}, {'role': 'user', 'content': q[:300]}], timeout=20, tries=1)
            qs |= toks(re.sub(r'<think>.*?</think>', '', t or '', flags=re.S).replace(',', ' '))
        except Exception: pass
        with db() as c: rs = c.execute('select id,title,body,tags,folder,updated,pinned,fav from notes where user=? and trashed=0', (u,)).fetchall()
        out = []
        for r in rs:
            txt = (r['title'] + ' ' + r['body'] + ' ' + r['tags']).lower()
            s = sum(txt.count(w) for w in qs) + 3 * sum(w in (r['title'] or '').lower() for w in qs)
            if s: d = dict(r); d['body'] = d['body'][:240]; d['tags'] = json.loads(d['tags'] or '[]'); d['score'] = s; out.append(d)
        return {'notes': sorted(out, key=lambda x: -x['score'])[:50], 'terms': sorted(qs)[:20]}
    @app.post('/bb/api/notes/{nid}/autotag')
    async def autotag(nid: str, request: Request):
        u = U(request)
        if not u or request.headers.get('x-bb-notes') != '1': return JSONResponse({'error': 'unauthorized'}, 401)
        with db() as c: r = c.execute('select * from notes where id=? and user=?', (nid, u)).fetchone()
        if not r or len((r['body'] or '').strip()) < 40: return {'skipped': True}
        try:
            _, t, _ = await RT.complete([{'role': 'system', 'content': 'Return JSON only: {"title": "3-6 word title in the note language", "tags": ["2-4 short lowercase tags in the note language"]}'}, {'role': 'user', 'content': r['body'][:6000]}], timeout=30, tries=1)
            j = json.loads(re.search(r'\{.*\}', t, re.S).group(0))
        except Exception: return {'skipped': True}
        tags = json.loads(r['tags'] or '[]'); new = [str(x)[:30].lstrip('#') for x in j.get('tags', [])][:4]
        upd = {'tags': json.dumps(list(dict.fromkeys(tags + new))[:12], ensure_ascii=False)}
        if not (r['title'] or '').strip() and j.get('title'): upd['title'] = str(j['title'])[:120]
        with db() as c: c.execute('update notes set ' + ','.join(k + '=?' for k in upd) + ' where id=?', list(upd.values()) + [nid])
        return {'tags': json.loads(upd['tags']), 'title': upd.get('title')}
STOP = set('the and for with this that from are was have you your not but করে এবং থেকে জন্য হবে আমি আমার এটা একটা তার করা আছে এই সেই করতে হয়'.split())
