from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
import httpx
import asyncio

app = FastAPI()

SHIKIMORI_API = "https://shikimori.one/api"
HEADERS = {"User-Agent": "MyCustomAnimePlayer/1.0"}

# --- API: Поиск аниме (Shikimori) ---
@app.get("/api/search")
async def search(q: str = Query(...)):
    async with httpx.AsyncClient(headers=HEADERS) as client:
        try:
            r = await client.get(f"{SHIKIMORI_API}/animes", params={"search": q, "limit": 20})
            r.raise_for_status()
            data = r.json()
            items = []
            for anime in data:
                poster = anime.get("image", {}).get("original", "")
                if poster and not poster.startswith("http"):
                    poster = "https://shikimori.one" + poster
                items.append({
                    "id": anime.get("id"),
                    "name": anime.get("russian") or anime.get("name"),
                    "poster": poster,
                    "year": anime.get("aired_on", "")[:4] if anime.get("aired_on") else "",
                    "score": anime.get("score", "0")
                })
            return {"items": items}
        except Exception as e:
            return {"items": [], "error": str(e)}

# --- API: Получение озвучек (через открытый парсер) ---
@app.get("/api/voices/{shikimori_id}")
async def get_voices(shikimori_id: int):
    # В реальности здесь должен быть вызов парсера (например, через библиотеку anime-parsers)
    # Так как мы не можем запустить стороннюю библиотеку прямо в этом файле без зависимостей,
    # мы используем публичный API-агрегатор (если он доступен) или возвращаем демо-список.
    # Для демонстрации работы плеера я отдаю список популярных студий.
    
    # Пытаемся найти на AniLibria по shikimori_id (если совпадет - берем реальные эпизоды)
    async with httpx.AsyncClient(headers=HEADERS) as client:
        try:
            r = await client.get("https://api.anilibria.app/api/v1/anime/releases/latest?limit=50")
            releases = r.json()
            if isinstance(releases, dict): releases = releases.get("data", [])
            
            # Ищем совпадение по shikimori_id
            matched_release = None
            for rel in releases:
                if str(rel.get("shikimori_id")) == str(shikimori_id):
                    matched_release = rel
                    break
            
            voices = []
            if matched_release:
                team = matched_release.get("team") or {}
                for v in team.get("voice", []):
                    voices.append({
                        "id": v.get("id"),
                        "name": v.get("name"),
                        "type": "Озвучка (AniLibria)"
                    })
            
            # Если не нашли на AniLibria, отдаем демо-список для теста плеера
            if not voices:
                voices = [
                    {"id": "1", "name": "AniDAB", "type": "Озвучка"},
                    {"id": "2", "name": "Studio Band", "type": "Озвучка"},
                    {"id": "3", "name": "AniLibria", "type": "Озвучка"},
                    {"id": "4", "name": "Оригинал + Субтитры", "type": "Субтитры"}
                ]
            
            return {"voices": voices, "anilibria_id": matched_release.get("id") if matched_release else None}
        except Exception as e:
            return {"voices": [], "error": str(e)}

# --- API: Эпизоды для выбранной озвучки ---
@app.get("/api/episodes/{anilibria_id}")
async def get_episodes(anilibria_id: int):
    async with httpx.AsyncClient(headers=HEADERS) as client:
        try:
            r = await client.get(f"https://api.anilibria.app/api/v1/anime/releases/{anilibria_id}")
            data = r.json()
            eps = []
            for e in data.get("episodes", []):
                hls_url = e.get("hls_1080") or e.get("hls_720") or e.get("hls_480")
                if hls_url:
                    eps.append({"name": e.get("name") or f"Эпизод {e.get('ordinal')}", "hls": hls_url})
            return {"episodes": eps}
        except Exception as e:
            return {"episodes": [], "error": str(e)}

# --- Фронтенд: Наш кастомный плеер ---
@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>My Anime Player</title>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@1.5.17/dist/hls.min.js"></script>
    <style>
        :root { --bg: #0a0e1a; --surface: #121a2e; --accent: #4d7cff; --text: #e8edf5; --muted: #6b7a99; }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
        
        header { padding: 1rem; display: flex; gap: 1rem; align-items: center; background: rgba(18, 26, 46, 0.9); border-bottom: 1px solid rgba(77, 124, 255, 0.2); position: sticky; top: 0; z-index: 100; flex-wrap: wrap; }
        .logo { color: var(--accent); font-size: 1.4rem; font-weight: 900; cursor: pointer; }
        nav a { color: var(--text); text-decoration: none; font-weight: 600; margin-right: 1rem; cursor: pointer; }
        nav a:hover, nav a.active { color: var(--accent); }
        .search-box { margin-left: auto; display: flex; gap: 0.5rem; width: 100%; max-width: 400px; }
        input { padding: 0.6rem 1rem; border-radius: 20px; border: 1px solid var(--muted); background: rgba(0,0,0,0.4); color: white; flex: 1; }
        button { padding: 0.6rem 1.2rem; border-radius: 20px; background: transparent; color: var(--accent); font-weight: bold; border: 1px solid var(--accent); cursor: pointer; }
        button:hover { background: var(--accent); color: var(--bg); }
        
        main { padding: 1rem; max-width: 1200px; margin: 0 auto; }
        .page { display: none; }
        .page.active { display: block; }
        
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 1rem; }
        .card { background: var(--surface); border-radius: 10px; overflow: hidden; cursor: pointer; border: 1px solid transparent; transition: 0.2s; }
        .card:hover { border-color: var(--accent); transform: translateY(-2px); }
        .card img { width: 100%; aspect-ratio: 2/3; object-fit: cover; }
        .card-info { padding: 0.5rem; }
        .card-title { font-size: 0.8rem; font-weight: bold; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
        .card-meta { font-size: 0.7rem; color: var(--accent); margin-top: 0.2rem; }
        
        .watch-layout { display: grid; grid-template-columns: 1fr 320px; gap: 1.5rem; }
        @media (max-width: 900px) { .watch-layout { grid-template-columns: 1fr; } }
        
        .player-wrap { position: relative; width: 100%; background: #000; border-radius: 12px; overflow: hidden; aspect-ratio: 16/9; border: 1px solid rgba(77,124,255,0.3); box-shadow: 0 0 20px rgba(77,124,255,0.15); }
        video { width: 100%; height: 100%; display: block; }
        
        .sidebar { background: var(--surface); border-radius: 12px; padding: 1rem; }
        .sidebar h3 { margin-bottom: 0.8rem; font-size: 1rem; color: var(--accent); }
        .voice-list { display: flex; flex-direction: column; gap: 0.5rem; margin-bottom: 1.5rem; }
        .voice-btn { text-align: left; padding: 0.7rem; background: rgba(0,0,0,0.3); border: 1px solid #333; border-radius: 8px; color: white; cursor: pointer; }
        .voice-btn:hover, .voice-btn.active { border-color: var(--accent); background: rgba(77,124,255,0.1); }
        
        .ep-list { display: flex; flex-direction: column; gap: 0.4rem; max-height: 300px; overflow-y: auto; }
        .ep-btn { text-align: left; padding: 0.6rem; background: rgba(0,0,0,0.2); border: 1px solid #222; border-radius: 6px; color: white; cursor: pointer; }
        .ep-btn:hover { border-color: var(--accent); }
        
        .back-btn { margin-bottom: 1rem; background: none; border: none; color: var(--muted); cursor: pointer; font-size: 1rem; }
        .loader { text-align: center; color: var(--accent); padding: 2rem; }
    </style>
</head>
<body>
    <header>
        <div class="logo" onclick="nav('home')">My Anime Player</div>
        <nav>
            <a onclick="nav('home')" id="nav-home" class="active">Главная</a>
        </nav>
        <div class="search-box">
            <input type="text" id="searchInput" placeholder="Поиск (Shikimori)..." onkeydown="if(event.key==='Enter') doSearch()">
            <button onclick="doSearch()">Найти</button>
        </div>
    </header>
    <main>
        <div id="page-home" class="page active">
            <h2 style="margin-bottom:1rem">Кастомный плеер с озвучками</h2>
            <p style="color:var(--muted); margin-bottom:1rem">Поиск по Shikimori. Выбор озвучек встроен в плеер.</p>
            <div id="catalog-grid" class="grid"><div class="loader">Загрузка...</div></div>
        </div>
        
        <div id="page-watch" class="page">
            <button class="back-btn" onclick="nav('home')">← Назад к поиску</button>
            <h2 id="watch-title" style="margin-bottom:1rem">Название</h2>
            <div class="watch-layout">
                <div>
                    <div class="player-wrap">
                        <video id="video" controls crossorigin="anonymous"></video>
                    </div>
                </div>
                <div class="sidebar">
                    <h3>🎙 Озвучки</h3>
                    <div id="voices-container" class="voice-list"><div class="loader">Загрузка...</div></div>
                    <h3>📺 Эпизоды</h3>
                    <div id="episodes-container" class="ep-list"><div style="color:var(--muted); font-size:0.8rem;">Выберите озвучку</div></div>
                </div>
            </div>
        </div>
    </main>
    <script>
        let hls = null;
        let currentShikimoriId = null;
        let currentAnilibriaId = null;

        function nav(id) {
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('nav a').forEach(a => a.classList.remove('active'));
            document.getElementById('page-' + id).classList.add('active');
            if(document.getElementById('nav-' + id)) document.getElementById('nav-' + id).classList.add('active');
        }

        async function doSearch() {
            const q = document.getElementById('searchInput').value;
            const g = document.getElementById('catalog-grid');
            g.innerHTML = '<div class="loader">Поиск...</div>';
            try {
                const r = await fetch('/api/search?q=' + encodeURIComponent(q));
                const d = await r.json();
                renderGrid(d.items, g);
            } catch(e) { g.innerHTML = '<div class="loader">Ошибка</div>'; }
        }

        function renderGrid(items, c) {
            if (!items || !items.length) { c.innerHTML = '<div class="loader">Ничего не найдено</div>'; return; }
            c.innerHTML = items.map(i => `
                <div class="card" onclick="openAnime(${i.id}, '${i.name.replace(/'/g, "\\'")}')">
                    <img src="${i.poster}" loading="lazy">
                    <div class="card-info">
                        <div class="card-title">${i.name}</div>
                        <div class="card-meta">${i.year} ★ ${i.score}</div>
                    </div>
                </div>
            `).join('');
        }

        async function openAnime(shikimoriId, name) {
            nav('watch');
            currentShikimoriId = shikimoriId;
            document.getElementById('watch-title').innerText = name;
            document.getElementById('voices-container').innerHTML = '<div class="loader">Поиск озвучек...</div>';
            document.getElementById('episodes-container').innerHTML = '<div style="color:var(--muted); font-size:0.8rem;">Выберите озвучку</div>';
            if (hls) { hls.destroy(); hls = null; }
            document.getElementById('video').removeAttribute('src');

            try {
                const r = await fetch('/api/voices/' + shikimoriId);
                const d = await r.json();
                currentAnilibriaId = d.anilibria_id;
                
                const container = document.getElementById('voices-container');
                if (d.voices && d.voices.length) {
                    container.innerHTML = d.voices.map(v => `
                        <button class="voice-btn" onclick="selectVoice('${v.name}')">${v.name} <span style="color:var(--muted); font-size:0.7rem;">(${v.type})</span></button>
                    `).join('');
                } else {
                    container.innerHTML = '<div style="color:var(--muted)">Озвучки не найдены</div>';
                }
            } catch(e) {
                document.getElementById('voices-container').innerHTML = '<div style="color:red">Ошибка</div>';
            }
        }

        async function selectVoice(voiceName) {
            document.querySelectorAll('.voice-btn').forEach(b => b.classList.remove('active'));
            event.target.closest('.voice-btn').classList.add('active');
            
            if (!currentAnilibriaId) {
                document.getElementById('episodes-container').innerHTML = '<div style="color:var(--muted)">Видео для этой озвучки нет в базе</div>';
                return;
            }

            const container = document.getElementById('episodes-container');
            container.innerHTML = '<div class="loader">Загрузка эпизодов...</div>';

            try {
                const r = await fetch('/api/episodes/' + currentAnilibriaId);
                const d = await r.json();
                if (d.episodes && d.episodes.length) {
                    container.innerHTML = d.episodes.map(ep => `
                        <button class="ep-btn" onclick="playVideo('${ep.hls}')">${ep.name}</button>
                    `).join('');
                    // Автоматически включаем первый
                    playVideo(d.episodes[0].hls);
                } else {
                    container.innerHTML = '<div style="color:var(--muted)">Эпизоды не найдены</div>';
                }
            } catch(e) {
                container.innerHTML = '<div style="color:red">Ошибка</div>';
            }
        }

        function playVideo(url) {
            const video = document.getElementById('video');
            if (hls) { hls.destroy(); hls = null; }
            if (Hls.isSupported()) {
                hls = new Hls();
                hls.loadSource(url);
                hls.attachMedia(video);
            } else {
                video.src = url;
            }
            video.play().catch(() => {});
        }

        // Стартовый поиск
        doSearch();
    </script>
</body>
</html>
    """
