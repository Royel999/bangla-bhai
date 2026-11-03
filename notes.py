"""Royal Notes: editable notebook for logged-in users (per-user). Stored in data.db (backed up by persist).
Tables: notes, note_versions, note_files. API under /bb/api/notes; UI at /notes (static/notes/)."""
import json, time, uuid, re, os
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
