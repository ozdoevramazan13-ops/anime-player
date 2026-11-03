"""
NeonWave — музыкальный сайт в одном файле.

Запуск:
    pip install flask requests
    python main.py
Открыть: http://127.0.0.1:5000

Что умеет:
  * собственный плеер (очередь, перемотка, громкость, next/prev, shuffle, repeat)
  * поиск по исполнителю, названию и ОТРЫВКУ ТЕКСТА песни (iTunes Search API + LRCLIB)
  * своя библиотека: загружаешь свои mp3/ogg/wav/m4a, они хранятся в папке uploads/
  * распознавание голосом: подпеваешь -> браузер распознаёт слова -> ищем по тексту.
    Если задать переменную окружения AUDD_API_TOKEN, запись ещё уходит
    на аудио-распознавание (как Shazam) через api.audd.io
  * вкладка «История прослушиваний» (SQLite)
  * тёмно-синий неоновый дизайн

Важно: хранилища «всех песен интернета» не существует и быть не может
(авторские права). Сайт использует 30-секундные легальные превью из iTunes
и твои собственные файлы.
"""
import os
import re
import sqlite3
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import requests
from flask import Flask, Response, jsonify, request, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
DB_PATH = os.path.join(BASE_DIR, "neonwave.db")
AUDD_TOKEN = os.environ.get("AUDD_API_TOKEN", "")
ALLOWED_EXT = {".mp3", ".ogg", ".wav", ".m4a", ".flac", ".aac"}

os.makedirs(UPLOAD_DIR, exist_ok=True)
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 МБ


# ----------------------------------------------------------------- БД
def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with db() as con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS library(
                id TEXT PRIMARY KEY, title TEXT, artist TEXT,
                filename TEXT, created REAL)"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS history(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id TEXT, title TEXT, artist TEXT,
                cover TEXT, url TEXT, played REAL)"""
        )


init_db()


# ------------------------------------------------------- внешние API
def itunes_search(term, limit=25):
    try:
        r = requests.get(
            "https://itunes.apple.com/search",
            params={"term": term, "entity": "song", "media": "music", "limit": limit},
            timeout=10,
        )
        items = r.json().get("results", [])
    except Exception:
        return []
    out = []
    for it in items:
        if not it.get("previewUrl"):
            continue
        out.append(
            {
                "id": "it-%s" % it.get("trackId"),
                "title": it.get("trackName", ""),
                "artist": it.get("artistName", ""),
                "cover": (it.get("artworkUrl100") or "").replace("100x100", "300x300"),
                "url": it["previewUrl"],
                "source": "iTunes (превью 30 сек)",
            }
        )
    return out


def best_snippet(lyrics, query):
    """Строка текста, ближе всего совпадающая с запросом."""
    words = set(re.findall(r"\w+", query.lower()))
    best, score = "", 0
    for line in (lyrics or "").splitlines():
        lw = set(re.findall(r"\w+", line.lower()))
        s = len(words & lw)
        if s > score:
            best, score = line.strip(), s
    return best


def lyrics_search(query, limit=8):
    try:
        r = requests.get(
            "https://lrclib.net/api/search", params={"q": query}, timeout=10,
            headers={"User-Agent": "NeonWave/1.0"},
        )
        found = r.json()
    except Exception:
        return []
    seen, picks = set(), []
    for f in found:
        key = (f.get("artistName", "").lower(), f.get("trackName", "").lower())
        if key in seen or not key[1]:
            continue
        seen.add(key)
        picks.append(f)
        if len(picks) >= limit:
            break

    def resolve(f):
        hits = itunes_search("%s %s" % (f["artistName"], f["trackName"]), 1)
        snippet = best_snippet(f.get("plainLyrics"), query)
        if hits:
            hits[0]["snippet"] = snippet
            return hits[0]
        return None

    with ThreadPoolExecutor(max_workers=6) as ex:
        return [t for t in ex.map(resolve, picks) if t]


def local_tracks(q=None):
    with db() as con:
        if q:
            like = "%%%s%%" % q
            rows = con.execute(
                "SELECT * FROM library WHERE title LIKE ? OR artist LIKE ? ORDER BY created DESC",
                (like, like),
            ).fetchall()
        else:
            rows = con.execute("SELECT * FROM library ORDER BY created DESC").fetchall()
    return [
        {
            "id": "loc-" + r["id"],
            "title": r["title"],
            "artist": r["artist"],
            "cover": "",
            "url": "/uploads/" + r["filename"],
            "source": "Моя библиотека",
        }
        for r in rows
    ]


# ------------------------------------------------------------- API
@app.get("/api/search")
def api_search():
    q = (request.args.get("q") or "").strip()
    mode = request.args.get("mode", "all")  # all | artist | lyrics
    if not q:
        return jsonify([])
    results = local_tracks(q)
    if mode in ("all", "artist"):
        results += itunes_search(q)
    if mode in ("all", "lyrics"):
        lyr = lyrics_search(q)
        ids = {t["id"] for t in results}
        results += [t for t in lyr if t["id"] not in ids]
    return jsonify(results)


@app.get("/api/library")
def api_library():
    return jsonify(local_tracks())


@app.post("/api/upload")
def api_upload():
    files = request.files.getlist("files")
    added = 0
    for f in files:
        ext = os.path.splitext(f.filename or "")[1].lower()
        if ext not in ALLOWED_EXT:
            continue
        tid = uuid.uuid4().hex
        fname = tid + ext
        f.save(os.path.join(UPLOAD_DIR, fname))
        base = os.path.splitext(os.path.basename(f.filename))[0]
        artist, title = ("Неизвестный исполнитель", base)
        if " - " in base:
            artist, title = [s.strip() for s in base.split(" - ", 1)]
        with db() as con:
            con.execute(
                "INSERT INTO library VALUES(?,?,?,?,?)",
                (tid, title, artist, fname, time.time()),
            )
        added += 1
    return jsonify({"added": added})


@app.get("/uploads/<path:name>")
def uploads(name):
    return send_from_directory(UPLOAD_DIR, name)


@app.post("/api/history")
def api_history_add():
    t = request.get_json(force=True)
    with db() as con:
        con.execute(
            "INSERT INTO history(track_id,title,artist,cover,url,played) VALUES(?,?,?,?,?,?)",
            (t.get("id"), t.get("title"), t.get("artist"), t.get("cover"), t.get("url"), time.time()),
        )
    return jsonify(ok=True)


@app.get("/api/history")
def api_history_get():
    with db() as con:
        rows = con.execute("SELECT * FROM history ORDER BY played DESC LIMIT 200").fetchall()
    return jsonify(
        [
            {
                "id": r["track_id"], "title": r["title"], "artist": r["artist"],
                "cover": r["cover"], "url": r["url"], "source": "История",
                "played": r["played"],
            }
            for r in rows
        ]
    )


@app.delete("/api/history")
def api_history_clear():
    with db() as con:
        con.execute("DELETE FROM history")
    return jsonify(ok=True)


@app.post("/api/recognize")
def api_recognize():
    """Аудио-распознавание через AudD (нужен AUDD_API_TOKEN)."""
    if not AUDD_TOKEN:
        return jsonify(configured=False, track=None)
    f = request.files.get("audio")
    if not f:
        return jsonify(configured=True, track=None)
    try:
        r = requests.post(
            "https://api.audd.io/",
            data={"api_token": AUDD_TOKEN},
            files={"file": (f.filename or "rec.webm", f.read())},
            timeout=30,
        )
        res = (r.json() or {}).get("result")
    except Exception:
        res = None
    if not res:
        return jsonify(configured=True, track=None)
    hits = itunes_search("%s %s" % (res.get("artist", ""), res.get("title", "")), 1)
    track = hits[0] if hits else {
        "id": "audd-" + uuid.uuid4().hex[:8], "title": res.get("title", ""),
        "artist": res.get("artist", ""), "cover": "", "url": "", "source": "AudD",
    }
    return jsonify(configured=True, track=track)


@app.get("/")
def index():
    return Response(PAGE, mimetype="text/html")


# ------------------------------------------------------------ ФРОНТ
PAGE = r"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NeonWave</title>
<style>
:root{
  --bg:#050816; --bg2:#0a1030; --panel:#0c1440; --line:#1b2a7a;
  --neon:#27e1ff; --neon2:#6a5cff; --pink:#ff3fd8; --text:#d9e6ff; --dim:#7f93c9;
}
*{box-sizing:border-box;margin:0;padding:0}
body{
  background:radial-gradient(1200px 600px at 20% -10%,#12206b55,transparent),
             radial-gradient(900px 500px at 100% 0%,#4b1fa855,transparent),var(--bg);
  color:var(--text);font-family:"Segoe UI",system-ui,sans-serif;min-height:100vh;padding-bottom:120px;
}
header{display:flex;align-items:center;gap:18px;padding:18px 28px;flex-wrap:wrap}
.logo{font-size:28px;font-weight:800;letter-spacing:2px;color:var(--neon);
  text-shadow:0 0 8px var(--neon),0 0 24px var(--neon2)}
.logo span{color:var(--pink);text-shadow:0 0 8px var(--pink)}
.searchbox{flex:1;min-width:260px;display:flex;gap:8px}
input[type=text],select{
  background:var(--bg2);border:1px solid var(--line);color:var(--text);
  padding:12px 16px;border-radius:12px;font-size:15px;outline:none;flex:1}
input[type=text]:focus,select:focus{border-color:var(--neon);box-shadow:0 0 12px #27e1ff66}
select{flex:0 0 auto}
button{cursor:pointer;border:1px solid var(--neon);background:transparent;color:var(--neon);
  padding:11px 18px;border-radius:12px;font-size:15px;transition:.2s}
button:hover{background:var(--neon);color:#001;box-shadow:0 0 18px var(--neon)}
button.pink{border-color:var(--pink);color:var(--pink)}
button.pink:hover{background:var(--pink);color:#001;box-shadow:0 0 18px var(--pink)}
button.rec{border-color:var(--pink);color:var(--pink)}
button.rec.on{background:var(--pink);color:#001;animation:pulse 1s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 #ff3fd8aa}100%{box-shadow:0 0 0 18px #ff3fd800}}
nav{display:flex;gap:6px;padding:0 28px;border-bottom:1px solid var(--line);overflow-x:auto}
nav button{border:none;border-bottom:3px solid transparent;border-radius:0;color:var(--dim);padding:14px 20px}
nav button.active{color:var(--neon);border-bottom-color:var(--neon);text-shadow:0 0 10px var(--neon);background:transparent;box-shadow:none}
main{padding:24px 28px;max-width:1100px;margin:0 auto}
.tab{display:none}.tab.active{display:block}
.status{color:var(--dim);margin:8px 0 16px;min-height:22px}
.row{display:flex;align-items:center;gap:14px;padding:10px 14px;margin-bottom:8px;
  background:linear-gradient(90deg,var(--panel),#0a1034);border:1px solid #162266;border-radius:14px;transition:.2s}
.row:hover{border-color:var(--neon);box-shadow:0 0 16px #27e1ff44}
.row.playing{border-color:var(--pink);box-shadow:0 0 18px #ff3fd855}
.cover{width:54px;height:54px;border-radius:10px;background:linear-gradient(135deg,var(--neon2),var(--neon));
  object-fit:cover;flex:0 0 54px;display:flex;align-items:center;justify-content:center;font-size:22px}
.meta{flex:1;min-width:0}
.meta b{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.meta small{color:var(--dim)}
.meta i{display:block;color:var(--neon);font-size:13px;margin-top:3px;opacity:.9}
.src{font-size:11px;color:var(--dim);white-space:nowrap}
.drop{border:2px dashed var(--line);border-radius:16px;padding:26px;text-align:center;color:var(--dim);margin-bottom:18px}
.drop:hover{border-color:var(--neon);color:var(--neon)}
.hint{background:#0c1a5a88;border:1px solid var(--line);border-radius:14px;padding:16px;margin-bottom:16px;color:var(--dim);line-height:1.5}
.big{display:flex;flex-direction:column;align-items:center;gap:16px;padding:30px 0}
.big button{width:150px;height:150px;border-radius:50%;font-size:48px;padding:0}
.heard{font-size:18px;color:var(--neon);min-height:28px;text-align:center}
/* плеер */
#player{position:fixed;left:0;right:0;bottom:0;background:#060b2add;backdrop-filter:blur(12px);
  border-top:1px solid var(--neon);box-shadow:0 -4px 30px #27e1ff33;padding:12px 24px;
  display:flex;align-items:center;gap:18px;flex-wrap:wrap;z-index:10}
#pinfo{display:flex;align-items:center;gap:12px;width:260px;min-width:200px}
#pcover{width:52px;height:52px;border-radius:10px;object-fit:cover;background:linear-gradient(135deg,var(--neon2),var(--neon))}
#ptitle{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:190px}
#partist{color:var(--dim);font-size:13px}
#pctl{display:flex;flex-direction:column;flex:1;min-width:260px;gap:6px}
#btns{display:flex;justify-content:center;gap:10px}
#btns button{padding:7px 14px;font-size:18px}
#btns .main{width:48px;height:48px;border-radius:50%;padding:0;box-shadow:0 0 14px #27e1ff88}
#btns button.on{background:var(--pink);border-color:var(--pink);color:#001}
#seekrow{display:flex;align-items:center;gap:10px;font-size:12px;color:var(--dim)}
input[type=range]{-webkit-appearance:none;appearance:none;height:6px;border-radius:6px;background:#16226e;outline:none;flex:1}
input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:15px;height:15px;border-radius:50%;
  background:var(--neon);box-shadow:0 0 10px var(--neon);cursor:pointer}
#vol{width:110px;flex:0 0 110px}
</style>
</head>
<body>
<header>
  <div class="logo">NEON<span>WAVE</span></div>
  <div class="searchbox">
    <input type="text" id="q" placeholder="Исполнитель, название или строчка из песни…">
    <select id="mode">
      <option value="all">Везде</option>
      <option value="artist">Исполнитель / название</option>
      <option value="lyrics">Отрывок текста</option>
    </select>
    <button id="go">Найти</button>
  </div>
</header>

<nav id="tabs">
  <button data-tab="search" class="active">🔎 Поиск</button>
  <button data-tab="listen">🎤 Распознать</button>
  <button data-tab="library">💿 Моя библиотека</button>
  <button data-tab="history">🕘 История</button>
</nav>

<main>
  <section id="search" class="tab active">
    <div class="status" id="sstatus">Введи запрос — найду по исполнителю или по словам из песни.</div>
    <div id="results"></div>
  </section>

  <section id="listen" class="tab">
    <div class="hint">Нажми на микрофон и подпой или пропой кусочек песни (10–15 секунд).
      Браузер распознаёт слова, и мы ищем песню по тексту. Лучше работает в Chrome / Edge.
      Если на сервере задан <code>AUDD_API_TOKEN</code>, запись также проверяется по звуку, как в Shazam.</div>
    <div class="big">
      <select id="lang" style="flex:0">
        <option value="ru-RU">Русский</option><option value="en-US">English</option>
        <option value="uk-UA">Українська</option><option value="es-ES">Español</option>
      </select>
      <button class="rec" id="mic">🎤</button>
      <div class="heard" id="heard"></div>
      <div class="status" id="lstatus"></div>
    </div>
    <div id="lresults"></div>
  </section>

  <section id="library" class="tab">
    <div class="drop">
      <p>Загрузи свои треки (mp3, ogg, wav, m4a, flac). Имя файла вида <b>Исполнитель - Название.mp3</b> разберётся само.</p><br>
      <input type="file" id="file" multiple accept="audio/*">
      <button id="upl" class="pink">Загрузить</button>
    </div>
    <div class="status" id="lbstatus"></div>
    <div id="libres"></div>
  </section>

  <section id="history" class="tab">
    <div style="margin-bottom:14px"><button class="pink" id="clearHist">Очистить историю</button></div>
    <div class="status" id="hstatus"></div>
    <div id="histres"></div>
  </section>
</main>

<div id="player">
  <div id="pinfo">
    <img id="pcover" alt="">
    <div><div id="ptitle">Ничего не играет</div><div id="partist">—</div></div>
  </div>
  <div id="pctl">
    <div id="btns">
      <button id="shuf" title="Перемешать">🔀</button>
      <button id="prev">⏮</button>
      <button id="play" class="main">▶</button>
      <button id="next">⏭</button>
      <button id="rep" title="Повтор">🔁</button>
    </div>
    <div id="seekrow"><span id="cur">0:00</span><input type="range" id="seek" min="0" max="1000" value="0"><span id="dur">0:00</span></div>
  </div>
  <div style="display:flex;align-items:center;gap:8px">🔊<input type="range" id="vol" min="0" max="100" value="80"></div>
  <audio id="audio" preload="auto"></audio>
</div>

<script>
const $ = s => document.querySelector(s);
const audio = $('#audio');
let queue = [], idx = -1, shuffle = false, repeat = false;

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = t => { if(!isFinite(t)) return '0:00'; const m=Math.floor(t/60), s=Math.floor(t%60); return m+':'+String(s).padStart(2,'0'); };

/* ---------- вкладки ---------- */
document.querySelectorAll('#tabs button').forEach(b => b.onclick = () => {
  document.querySelectorAll('#tabs button').forEach(x => x.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
  b.classList.add('active'); $('#'+b.dataset.tab).classList.add('active');
  if (b.dataset.tab === 'history') loadHistory();
  if (b.dataset.tab === 'library') loadLibrary();
});

/* ---------- список треков ---------- */
function render(el, tracks) {
  el.innerHTML = '';
  tracks.forEach((t, i) => {
    const row = document.createElement('div');
    row.className = 'row' + (queue[idx] && queue[idx].url === t.url && el.dataset.active ? ' playing' : '');
    const cover = t.cover ? `<img class="cover" src="${esc(t.cover)}" alt="">` : `<div class="cover">♪</div>`;
    const when = t.played ? ' · ' + new Date(t.played*1000).toLocaleString('ru-RU') : '';
    row.innerHTML = `${cover}<div class="meta"><b>${esc(t.title)}</b><small>${esc(t.artist)}</small>
      ${t.snippet ? `<i>«…${esc(t.snippet)}…»</i>` : ''}</div>
      <div class="src">${esc(t.source||'')}${when}</div><button>▶</button>`;
    row.querySelector('button').onclick = () => { queue = tracks.slice(); playIndex(i); };
    el.appendChild(row);
  });
}

/* ---------- плеер ---------- */
function playIndex(i) {
  if (i < 0 || i >= queue.length) return;
  idx = i; const t = queue[i];
  if (!t.url) { alert('У этого трека нет аудио-источника'); return; }
  audio.src = t.url; audio.play();
  $('#ptitle').textContent = t.title; $('#partist').textContent = t.artist;
  $('#pcover').src = t.cover || '';
  document.title = t.title + ' — NeonWave';
  fetch('/api/history', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(t)});
}
function nextTrack() {
  if (!queue.length) return;
  if (shuffle) return playIndex(Math.floor(Math.random()*queue.length));
  if (idx + 1 < queue.length) playIndex(idx + 1); else if (repeat) playIndex(0);
}
$('#play').onclick = () => { if (!audio.src) return; audio.paused ? audio.play() : audio.pause(); };
$('#next').onclick = nextTrack;
$('#prev').onclick = () => { if (audio.currentTime > 3) audio.currentTime = 0; else playIndex(idx - 1); };
$('#shuf').onclick = e => { shuffle = !shuffle; e.currentTarget.classList.toggle('on', shuffle); };
$('#rep').onclick = e => { repeat = !repeat; e.currentTarget.classList.toggle('on', repeat); };
audio.onplay = () => $('#play').textContent = '⏸';
audio.onpause = () => $('#play').textContent = '▶';
audio.onended = () => { if (repeat && queue.length === 1) { audio.currentTime = 0; audio.play(); } else nextTrack(); };
audio.ontimeupdate = () => {
  if (audio.duration) $('#seek').value = (audio.currentTime / audio.duration) * 1000;
  $('#cur').textContent = fmt(audio.currentTime); $('#dur').textContent = fmt(audio.duration);
};
$('#seek').oninput = e => { if (audio.duration) audio.currentTime = (e.target.value / 1000) * audio.duration; };
$('#vol').oninput = e => audio.volume = e.target.value / 100;
audio.volume = 0.8;
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
  if (e.code === 'Space') { e.preventDefault(); $('#play').click(); }
});

/* ---------- поиск ---------- */
async function search(q, mode) {
  const r = await fetch('/api/search?q=' + encodeURIComponent(q) + '&mode=' + mode);
  return r.json();
}
async function doSearch() {
  const q = $('#q').value.trim(); if (!q) return;
  $('#sstatus').textContent = 'Ищу…'; $('#results').innerHTML = '';
  const res = await search(q, $('#mode').value);
  $('#sstatus').textContent = res.length ? `Найдено: ${res.length}` : 'Ничего не найдено';
  render($('#results'), res);
}
$('#go').onclick = doSearch;
$('#q').addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });

/* ---------- библиотека ---------- */
async function loadLibrary() {
  const r = await (await fetch('/api/library')).json();
  $('#lbstatus').textContent = r.length ? `Треков: ${r.length}` : 'Пока пусто — загрузи свои файлы.';
  render($('#libres'), r);
}
$('#upl').onclick = async () => {
  const files = $('#file').files; if (!files.length) return;
  const fd = new FormData(); for (const f of files) fd.append('files', f);
  $('#lbstatus').textContent = 'Загружаю…';
  const r = await (await fetch('/api/upload', {method:'POST', body: fd})).json();
  $('#file').value = ''; $('#lbstatus').textContent = `Добавлено: ${r.added}`; loadLibrary();
};

/* ---------- история ---------- */
async function loadHistory() {
  const r = await (await fetch('/api/history')).json();
  $('#hstatus').textContent = r.length ? `Записей: ${r.length}` : 'История пуста.';
  render($('#histres'), r);
}
$('#clearHist').onclick = async () => {
  if (!confirm('Очистить всю историю?')) return;
  await fetch('/api/history', {method:'DELETE'}); loadHistory();
};

/* ---------- распознавание голосом ---------- */
let rec = null, mediaRec = null, chunks = [], finalText = '', listening = false;
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

$('#mic').onclick = async () => {
  if (listening) return stopListen();
  finalText = ''; chunks = [];
  $('#heard').textContent = ''; $('#lresults').innerHTML = '';
  let stream = null;
  try { stream = await navigator.mediaDevices.getUserMedia({audio:true}); }
  catch (e) { $('#lstatus').textContent = 'Нет доступа к микрофону.'; return; }

  mediaRec = new MediaRecorder(stream);
  mediaRec.ondataavailable = e => chunks.push(e.data);
  mediaRec.onstop = () => { stream.getTracks().forEach(t => t.stop()); finishListen(); };
  mediaRec.start();

  if (SR) {
    rec = new SR(); rec.lang = $('#lang').value; rec.continuous = true; rec.interimResults = true;
    rec.onresult = e => {
      let txt = '';
      for (let i = 0; i < e.results.length; i++) txt += e.results[i][0].transcript + ' ';
      finalText = txt.trim(); $('#heard').textContent = finalText;
    };
    rec.onerror = () => {};
    rec.start();
  } else {
    $('#lstatus').textContent = 'Распознавание слов не поддерживается этим браузером (нужен Chrome/Edge); останется только аудио-режим.';
  }
  listening = true; $('#mic').classList.add('on');
  $('#lstatus').textContent = 'Слушаю… пой! (нажми ещё раз, чтобы закончить)';
  setTimeout(() => { if (listening) stopListen(); }, 15000);
};

function stopListen() {
  listening = false; $('#mic').classList.remove('on');
  try { rec && rec.stop(); } catch (e) {}
  try { mediaRec && mediaRec.state !== 'inactive' && mediaRec.stop(); } catch (e) {}
}

async function finishListen() {
  $('#lstatus').textContent = 'Ищу песню…';
  let found = [];
  // 1) аудио-распознавание (если на сервере есть токен AudD)
  try {
    const fd = new FormData();
    fd.append('audio', new Blob(chunks, {type: 'audio/webm'}), 'rec.webm');
    const r = await (await fetch('/api/recognize', {method:'POST', body: fd})).json();
    if (r.track) found.push(Object.assign({snippet: 'распознано по звуку'}, r.track));
  } catch (e) {}
  // 2) поиск по распознанным словам
  if (finalText.length > 2) {
    const res = await search(finalText, 'lyrics');
    const ids = new Set(found.map(t => t.id));
    found = found.concat(res.filter(t => !ids.has(t.id)));
  }
  $('#lstatus').textContent = found.length ? 'Возможно, это одна из этих песен:' :
    'Не удалось распознать. Попробуй спеть чётче и подольше, выбрав нужный язык.';
  render($('#lresults'), found);
}
</script>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
