"""
Anime Vault Player — всё в одном файле.
Запуск: pip install fastapi uvicorn httpx && uvicorn main:app --reload
Открыть: http://localhost:8000
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
import httpx
from typing import Optional
import time

app = FastAPI(title="Anime Vault Player")

# ==================== 
ANILIBRIA_BASE = "https://api.anilibria.app/api/v1"
TIMEOUT = httpx.Timeout(15.0, connect=5.0)
_cache: dict[str, tuple[float, dict]] = {}
CACHE_TTL = 300


async def fetch_anilibria(path: str, params: Optional[dict] = None):
    cache_key = f"{path}:{params}"
    now = time.time()
    if cache_key in _cache:
        ts, data = _cache[cache_key]
        if now - ts < CACHE_TTL:
            return data

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            resp = await client.get(f"{ANILIBRIA_BASE}{path}", params=params)
            resp.raise_for_status()
            data = resp.json()
            _cache[cache_key] = (now, data)
            return data
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="AniLibria timeout")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code,
                                detail=f"AniLibria error: {e.response.status_code}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Network error: {str(e)}")


@app.get("/api/catalog")
async def catalog(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=50),
):
    if search:
        data = await fetch_anilibria("/app/search/releases", {"query": search})
        items = data if isinstance(data, list) else data.get("data", [])
    else:
        offset = (page - 1) * limit
        data = await fetch_anilibria("/anime/releases/latest", {"limit": limit, "offset": offset})
        items = data if isinstance(data, list) else data.get("data", [])
        result = []
    for item in items:
        result.append({
            "id": item.get("id"),
            "name": (item.get("name") or {}).get("main") or "Без названия",
            "poster": "https://api.anilibria.app" + (
                ((item.get("poster") or {}).get("optimized") or {}).get("src")
                or (item.get("poster") or {}).get("src", "")
            ),
            "year": item.get("year"),
            "type": ((item.get("type") or {}).get("full_string")
                     or (item.get("type") or {}).get("string")),
        })
    return {"items": result, "page": page}



@app.get("/api/episodes/{release_id}")
async def episodes(release_id: int):
    data = await fetch_anilibria(f"/anime/releases/{release_id}")
    episodes_list = data.get("episodes", [])
    if not episodes_list:
        raise HTTPException(status_code=404, detail="No episodes")

    result = []
    for ep in episodes_list:
        hls_url = ep.get("hls_1080") or ep.get("hls_720") or ep.get("hls_480")
        if not hls_url:
            continue
        result.append({
            "id": ep.get("id"),
            "name": ep.get("name") or f"Эпизод {ep.get('ordinal')}",
            "ordinal": ep.get("ordinal"),
            "hls": hls_url,
        })

    if not result:
        raise HTTPException(status_code=404, detail="No HLS streams")

    return {
        "release_id": release_id,
        "release_name": (data.get("name") or {}).get("main", ""),
        "episodes": result,
    }


# ==================== FRONTEND (встроенный HTML) ====================

HTML_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Anime Vault Player</title>
<script src="https://cdn.jsdelivr.net/npm/hls.js@1.5.17/dist/hls.min.js"></script>
<style>
:root{--bg:#0f0f13;--surface:#1a1a22;--accent:#ff6b35;--text:#e8e8ef;--muted:#8a8a9a}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--text);height:100vh;display:flex;flex-direction:column}
header{padding:0.8rem 1.2rem;display:flex;gap:1rem;align-items:center;flex-wrap:wrap;border-bottom:1px solid #2a2a35}
h1{font-size:1.15rem;color:var(--accent);white-space:nowrap}
.search-bar{display:flex;gap:0.5rem;flex:1;min-width:220px}
.search-bar input{flex:1;padding:0.55rem 0.85rem;border-radius:8px;border:1px solid #2a2a35;background:var(--surface);color:var(--text)}
.btn{padding:0.55rem 1rem;border:none;border-radius:8px;background:var(--accent);color:#fff;font-weight:600;cursor:pointer}
.btn:hover{opacity:0.85}
main{display:grid;grid-template-columns:1fr 380px;flex:1;overflow:hidden}
@media(max-width:900px){main{grid-template-columns:1fr;overflow:auto}}
.player-col{padding:0.8rem;display:flex;flex-direction:column;gap:0.6rem;min-width:0}
.player-wrap{position:relative;width:100%;background:#000;border-radius:10px;overflow:hidden;aspect-ratio:16/9}
.player-wrap video{width:100%;height:100%;display:block}
.now-playing{font-size:0.9rem;color:var(--muted);min-height:1.3em}
.now-playing strong{color:var(--text)}
.status{font-size:0.8rem;color:var(--muted);min-height:1.1em}
.status.error{color:#ff5555}
.side-col{background:var(--surface);border-left:1px solid #2a2a35;overflow-y:auto;padding:0.8rem;display:flex;flex-direction:column;gap:0.5rem}
.side-col h2{font-size:0.85rem;color:var(--muted);text-transform:uppercase;letter-spacing:0.04em;margin-bottom:0.3rem}
.anime-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:0.6rem}
.anime-card{cursor:pointer;border-radius:8px;overflow:hidden;background:#15151d;transition:transform 0.12s,outline 0.12s}
.anime-card:hover{transform:scale(1.02);outline:2px solid var(--accent)}
.anime-card img{width:100%;aspect-ratio:2/3;object-fit:cover;display:block;background:#222}
.anime-card .title{font-size:0.72rem;padding:0.3rem 0.35rem;line-height:1.2;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.anime-card .meta{font-size:0.65rem;color:var(--muted);padding:0 0.35rem 0.35rem}
.episode-list{display:flex;flex-direction:column;gap:0.35rem}
.episode-btn{text-align:left;padding:0.5rem 0.65rem;border-radius:6px;border:1px solid #2a2a35;background:#15151d;color:var(--text);cursor:pointer;font-size:0.82rem}
.episode-btn:hover{background:#252530}
.episode-btn.active{border-color:var(--accent);background:#2a1f1a}
.placeholder{color:var(--muted);font-size:0.82rem;text-align:center;padding:1.5rem 0}
.loading{color:var(--accent);font-size:0.82rem;text-align:center;padding:0.8rem 0}
</style>
</head>
<body>
<header>
  <h1>▶ Anime Vault</h1>
  <div class="search-bar">
    <input type="text" id="searchInput" placeholder="Поиск аниме (AniLibria)..." />
    <button class="btn" id="searchBtn">Найти</button>
    <button class="btn" id="homeBtn">Каталог</button>
  </div>
</header>
<main>
  <section class="player-col">
    <div class="player-wrap"><video id="video" controls preload="metadata"></video></div>
    <div class="now-playing" id="nowPlaying">Выбери аниме и эпизод справа →</div>
    <div class="status" id="status"></div>
  </section>
  <aside class="side-col">
    <h2 id="sideTitle">Каталог</h2>
    <div id="sideContent"><div class="loading">Загрузка...</div></div>
  </aside>
</main>
<script>
'use strict';
const API = ''; // пусто = тот же origin
const video = document.getElementById('video');
const nowPlaying = document.getElementById('nowPlaying');
const statusEl = document.getElementById('status');
const sideTitle = document.getElementById('sideTitle');
const sideContent = document.getElementById('sideContent');
const searchInput = document.getElementById('searchInput');
const searchBtn = document.getElementById('searchBtn');
const homeBtn = document.getElementById('homeBtn');
let hls = null;
let currentEpisodes = [];
let currentReleaseName = '';

function setStatus(msg, isError = false) {
  statusEl.textContent = msg;
  statusEl.classList.toggle('error', isError);
}
function destroyPlayer() {
  if (hls) { hls.destroy(); hls = null; }
  video.removeAttribute('src'); video.load();
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function playHls(url, epName) {
  destroyPlayer();
  if (Hls.isSupported()) {
    hls = new Hls({ enableWorker: true });
    hls.loadSource(url); hls.attachMedia(video);
    hls.on(Hls.Events.ERROR, (_e, data) => {
      if (data.fatal) {
        if (data.type === Hls.ErrorTypes.NETWORK_ERROR) { setStatus('Сетевая ошибка HLS (CORS?)', true); hls.startLoad(); }
        else if (data.type === Hls.ErrorTypes.MEDIA_ERROR) { setStatus('Ошибка медиа, восстановление...', true); hls.recoverMediaError(); }
        else { setStatus('Фатальная ошибка HLS.', true); destroyPlayer(); }
      }
    });
    setStatus('');
  } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
    video.src = url; setStatus('HLS (нативно).');
  } else { setStatus('HLS не поддерживается.', true); return; }
  nowPlaying.innerHTML = '<strong>' + escapeHtml(currentReleaseName) + '</strong> — ' + escapeHtml(epName);
  video.play().catch(() => setStatus('Нажми ▶ для старта.'));
}
async function loadCatalog(search = '') {
  sideTitle.textContent = search ? 'Поиск: «' + search + '»' : 'Каталог';
  sideContent.innerHTML = '<div class="loading">Загрузка...</div>';
  const url = search ? API + '/api/catalog?search=' + encodeURIComponent(search) : API + '/api/catalog?limit=24';
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    renderCatalog(data.items || []);
  } catch (e) { sideContent.innerHTML = '<div class="placeholder">Ошибка: ' + escapeHtml(e.message) + '</div>'; }
}
function renderCatalog(items) {
  if (!items.length) { sideContent.innerHTML = '<div class="placeholder">Ничего не найдено.</div>'; return; }
  sideContent.innerHTML = '<div class="anime-grid">' + items.map(a =>
    '<div class="anime-card" data-id="' + a.id + '">' +
      '<img src="' + escapeHtml(a.poster) + '" alt="" loading="lazy" onerror="this.style.background=\'#333\'" />' +
      '<div class="title">' + escapeHtml(a.name) + '</div>' +
      '<div class="meta">' + escapeHtml([a.type, a.year].filter(Boolean).join(' · ')) + '</div>' +
    '</div>'
  ).join('') + '</div>';
  sideContent.querySelectorAll('.anime-card').forEach(card => {
    card.addEventListener('click', () => loadEpisodes(Number(card.dataset.id)));
  });
}
async function loadEpisodes(releaseId) {
  sideTitle.textContent = 'Эпизоды';
  sideContent.innerHTML = '<div class="loading">Загрузка эпизодов...</div>';
  try {
    const res = await fetch(API + '/api/episodes/' + releaseId);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    currentReleaseName = data.release_name || '';
    currentEpisodes = data.episodes || [];
    renderEpisodes();
  } catch (e) { sideContent.innerHTML = '<div class="placeholder">Ошибка: ' + escapeHtml(e.message) + '</div>'; }
}
function renderEpisodes() {
  if (!currentEpisodes.length) { sideContent.innerHTML = '<div class="placeholder">Эпизоды не найдены.</div>'; return; }
  sideContent.innerHTML = '<div class="episode-list">' + currentEpisodes.map((ep, i) =>
    '<button class="episode-btn" data-idx="' + i + '">' + escapeHtml(ep.name || ('Эпизод ' + ep.ordinal)) + '</button>'
  ).join('') + '</div>';
  sideContent.querySelectorAll('.episode-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      sideContent.querySelectorAll('.episode-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const ep = currentEpisodes[Number(btn.dataset.idx)];
      playHls(ep.hls, ep.name || ('Эпизод ' + ep.ordinal));
    });
  });
}
searchBtn.addEventListener('click', () => loadCatalog(searchInput.value.trim()));
searchInput.addEventListener('keydown', e => { if (e.key === 'Enter') loadCatalog(searchInput.value.trim()); });
homeBtn.addEventListener('click', () => { searchInput.value = ''; loadCatalog(''); });
window.addEventListener('beforeunload', destroyPlayer);
loadCatalog('');
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_PAGE
