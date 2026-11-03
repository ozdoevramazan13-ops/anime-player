from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import httpx

app = FastAPI()
ANILIBRIA_BASE = "https://api.anilibria.app/api/v1"

def get_poster(item):
    poster_data = item.get("poster") or {}
    opt = poster_data.get("optimized") or {}
    src = opt.get("src") or poster_data.get("src") or ""
    if src.startswith("/"):
        return "https://api.anilibria.app" + src
    return src

@app.get("/api/catalog")
async def catalog(search: str = None):
    async with httpx.AsyncClient() as client:
        try:
            if search:
                r = await client.get(f"{ANILIBRIA_BASE}/app/search/releases", params={"query": search})
            else:
                r = await client.get(f"{ANILIBRIA_BASE}/anime/releases/latest", params={"limit": 30})
            
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict): data = data.get("data", [])
            
            items = []
            for i in data:
                team = i.get("team") or {}
                voice = team.get("voice") or []
                voice_names = ", ".join([v.get("name") for v in voice]) if voice else "AniLibria"
                items.append({
                    "id": i.get("id"), 
                    "name": i.get("name", {}).get("main", "Без названия"), 
                    "poster": get_poster(i),
                    "year": i.get("year"),
                    "voice": voice_names
                })
            return {"items": items}
        except Exception as e:
            return {"items": [], "error": str(e)}

@app.get("/api/release/{release_id}")
async def release_info(release_id: int):
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{ANILIBRIA_BASE}/anime/releases/{release_id}")
            r.raise_for_status()
            data = r.json()
            
            team = data.get("team") or {}
            voice = team.get("voice") or []
            voice_names = ", ".join([v.get("name") for v in voice]) if voice else "AniLibria"
            
            eps = []
            for e in data.get("episodes", []):
                hls_url = e.get("hls_1080") or e.get("hls_720") or e.get("hls_480")
                if hls_url:
                    eps.append({
                        "name": e.get("name") or f"Эпизод {e.get('ordinal')}", 
                        "hls": hls_url
                    })
                    
            return {
                "id": data.get("id"),
                "name": data.get("name", {}).get("main"),
                "description": data.get("description", "Описание отсутствует."),
                "poster": get_poster(data),
                "year": data.get("year"),
                "voice": voice_names,
                "episodes": eps
            }
        except Exception as e:
            return {"error": str(e)}

@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Anime Player</title>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@1.5.17/dist/hls.min.js"></script>
    <style>
        :root { --bg: #0a0e1a; --surface: #121a2e; --accent: #4d7cff; --text: #e8edf5; --muted: #6b7a99; }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
        
        header { padding: 1rem; display: flex; gap: 1rem; align-items: center; background: rgba(18, 26, 46, 0.9); backdrop-filter: blur(10px); position: sticky; top: 0; z-index: 100; border-bottom: 1px solid rgba(77, 124, 255, 0.2); flex-wrap: wrap; }
        .logo { color: var(--accent); font-size: 1.4rem; font-weight: 900; cursor: pointer; }
        nav { display: flex; gap: 1rem; }
        nav a { color: var(--text); text-decoration: none; font-weight: 600; font-size: 0.9rem; cursor: pointer; }
        nav a:hover, nav a.active { color: var(--accent); }
        .search-box { margin-left: auto; display: flex; gap: 0.5rem; width: 100%; max-width: 400px; }
        input { padding: 0.6rem 1rem; border-radius: 20px; border: 1px solid var(--muted); background: rgba(0,0,0,0.4); color: white; outline: none; flex: 1; }
        input:focus { border-color: var(--accent); }
        button { padding: 0.6rem 1.2rem; border-radius: 20px; background: transparent; color: var(--accent); font-weight: bold; border: 1px solid var(--accent); cursor: pointer; }
        button:hover { background: var(--accent); color: var(--bg); }
        
        main { padding: 1rem; max-width: 1400px; margin: 0 auto; }
        .page { display: none; }
        .page.active { display: block; }
        
        .section-title { font-size: 1.4rem; margin-bottom: 1rem; border-left: 4px solid var(--accent); padding-left: 1rem; }
        
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 1rem; }
        @media (min-width: 1000px) { .grid { grid-template-columns: repeat(5, 1fr); gap: 1.5rem; } }
        
        .card { background: var(--surface); border-radius: 12px; overflow: hidden; cursor: pointer; transition: 0.2s; border: 1px solid transparent; }
        .card:hover { transform: translateY(-4px); border-color: var(--accent); }
        .card img { width: 100%; aspect-ratio: 2/3; object-fit: cover; display: block; }
        .card-info { padding: 0.6rem; }
        .card-title { font-size: 0.85rem; font-weight: bold; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
        .card-meta { font-size: 0.7rem; color: var(--accent); margin-top: 0.3rem; }
        
        .details-layout { display: grid; grid-template-columns: 1fr 320px; gap: 1.5rem; }
        @media (max-width: 900px) { .details-layout { grid-template-columns: 1fr; } }
        
        .player-wrap { position: relative; width: 100%; background: #000; border-radius: 12px; overflow: hidden; aspect-ratio: 16/9; border: 1px solid rgba(77,124,255,0.3); }
        video { width: 100%; height: 100%; display: block; }
        
        .sidebar { background: var(--surface); border-radius: 12px; padding: 1rem; }
        .sidebar h3 { margin-bottom: 1rem; color: var(--accent); font-size: 1rem; }
        
        .ep-list { display: flex; flex-direction: column; gap: 0.4rem; max-height: 500px; overflow-y: auto; }
        .ep-btn { text-align: left; padding: 0.7rem; background: rgba(0,0,0,0.25); border: 1px solid rgba(77, 124, 255, 0.15); border-radius: 8px; color: white; cursor: pointer; font-size: 0.85rem; transition: 0.2s; }
        .ep-btn:hover, .ep-btn.active { border-color: var(--accent); background: rgba(77, 124, 255, 0.12); }
        
        .back-btn { margin-bottom: 1rem; background: none; border: none; color: var(--muted); cursor: pointer; font-size: 1rem; display: flex; align-items: center; gap: 0.5rem; }
        .back-btn:hover { color: var(--accent); }
        
        .loader { text-align: center; color: var(--accent); padding: 2rem; font-size: 1.1rem; }
    </style>
</head>
<body>
    <header>
        <div class="logo" onclick="nav('home')">Anime Player</div>
        <nav>
            <a onclick="nav('home')" id="nav-home" class="active">Главная</a>
            <a onclick="nav('catalog')" id="nav-catalog">Каталог</a>
        </nav>
        <div class="search-box">
            <input type="text" id="searchInput" placeholder="Поиск..." onkeydown="if(event.key==='Enter') doSearch()">
            <button onclick="doSearch()">Найти</button>
        </div>
    </header>

    <main>
        <div id="page-home" class="page active">
            <h2 class="section-title">Последние обновления</h2>
            <div id="home-grid" class="grid"><div class="loader">Загрузка...</div></div>
        </div>

        <div id="page-catalog" class="page">
            <h2 class="section-title">Каталог аниме</h2>
            <div id="catalog-grid" class="grid"><div class="loader">Загрузка...</div></div>
        </div>

        <div id="page-watch" class="page">
            <button class="back-btn" onclick="nav('catalog')">← Вернуться в каталог</button>
            <div class="details-layout">
                <div class="left-col">
                    <div class="player-wrap">
                        <video id="video" controls></video>
                    </div>
                    <div class="details-info" style="margin-top:1rem; background:var(--surface); padding:1rem; border-radius:12px;">
                        <h2 id="watch-title" style="color:var(--accent); margin-bottom:0.5rem;">Название</h2>
                        <p id="watch-desc" style="color:var(--muted); font-size:0.9rem; line-height:1.6;">Описание...</p>
                    </div>
                </div>
                <div class="right-col">
                    <div class="sidebar">
                        <h3>Эпизоды</h3>
                        <div id="episodes-container" class="ep-list"><div class="loader">Загрузка...</div></div>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <script>
        let hls = null;

        function nav(id) {
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('nav a').forEach(a => a.classList.remove('active'));
            document.getElementById('page-' + id).classList.add('active');
            if(document.getElementById('nav-' + id)) document.getElementById('nav-' + id).classList.add('active');
            window.scrollTo(0,0);
        }

        async function loadHome() {
            const g = document.getElementById('home-grid');
            try {
                const r = await fetch('/api/catalog');
                const d = await r.json();
                renderGrid(d.items, g);
            } catch(e) { g.innerHTML = '<div class="loader">Ошибка загрузки</div>'; }
        }

        async function loadCatalog(q = '') {
            const g = document.getElementById('catalog-grid');
            g.innerHTML = '<div class="loader">Загрузка...</div>';
            try {
                const r = await fetch('/api/catalog' + (q ? '?search=' + encodeURIComponent(q) : ''));
                const d = await r.json();
                renderGrid(d.items, g);
            } catch(e) { g.innerHTML = '<div class="loader">Ошибка загрузки</div>'; }
        }

        function renderGrid(items, c) {
            if (!items || !items.length) {
                c.innerHTML = '<div class="loader">Ничего не найдено</div>';
                return;
            }
            c.innerHTML = items.map(i => `
                <div class="card" onclick="openAnime(${i.id})">
                    <img src="${i.poster}" loading="lazy" onerror="this.src='https://via.placeholder.com/200x300/121a2e/4d7cff?text=No+Image'">
                    <div class="card-info">
                        <div class="card-title">${i.name}</div>
                        <div class="card-meta">${i.year || ''}</div>
                    </div>
                </div>
            `).join('');
        }

        function doSearch() {
            const q = document.getElementById('searchInput').value;
            nav('catalog');
            loadCatalog(q);
        }

        async function openAnime(id) {
            nav('watch');
            document.getElementById('watch-title').innerText = 'Загрузка...';
            document.getElementById('watch-desc').innerText = '';
            document.getElementById('episodes-container').innerHTML = '<div class="loader">Загрузка...</div>';
            if (hls) { hls.destroy(); hls = null; }
            document.getElementById('video').removeAttribute('src');

            try {
                const r = await fetch('/api/release/' + id);
                const d = await r.json();
                document.getElementById('watch-title').innerText = d.name;
                document.getElementById('watch-desc').innerText = d.description || 'Описание отсутствует.';
                
                if (d.episodes && d.episodes.length) {
                    document.getElementById('episodes-container').innerHTML = d.episodes.map((ep, i) => `
                        <button class="ep-btn" id="ep-btn-${i}" onclick="playEpisode(${i})">
                            ${ep.name}
                        </button>
                    `).join('');
                    // Автоматически включаем первый эпизод
                    playEpisode(0);
                } else {
                    document.getElementById('episodes-container').innerHTML = '<div style="color:var(--muted)">Эпизоды не найдены</div>';
                }
            } catch(e) {
                document.getElementById('watch-title').innerText = 'Ошибка';
                document.getElementById('watch-desc').innerText = e.message;
            }
        }

        function playEpisode(index) {
            const eps = document.querySelectorAll('.ep-btn');
            eps.forEach(b => b.classList.remove('active'));
            if (eps[index]) eps[index].classList.add('active');

            // Нам нужен hls-адрес эпизода. Мы его передадим в атрибуте.
            // Чтобы не делать повторный запрос, сохраним эпизоды глобально.
            // Но в этом упрощенном коде мы просто дергаем бэкенд еще раз (или передаем ссылку).
            // Для простоты: сохраняем эпизоды в window.
            const ep = window.currentEpisodes ? window.currentEpisodes[index] : null;
            if (!ep) return;

            const video = document.getElementById('video');
            if (hls) { hls.destroy(); hls = null; }
            if (Hls.isSupported()) {
                hls = new Hls();
                hls.loadSource(ep.hls);
                hls.attachMedia(video);
            } else {
                video.src = ep.hls;
            }
            video.play().catch(() => {});
        }

        // Перехватываем эпизоды при открытии
        const originalOpenAnime = openAnime;
        openAnime = async function(id) {
            nav('watch');
            document.getElementById('watch-title').innerText = 'Загрузка...';
            document.getElementById('watch-desc').innerText = '';
            document.getElementById('episodes-container').innerHTML = '<div class="loader">Загрузка...</div>';
            if (hls) { hls.destroy(); hls = null; }
            document.getElementById('video').removeAttribute('src');

            try {
                const r = await fetch('/api/release/' + id);
                const d = await r.json();
                window.currentEpisodes = d.episodes || [];
                document.getElementById('watch-title').innerText = d.name;
                document.getElementById('watch-desc').innerText = d.description || 'Описание отсутствует.';
                
                if (window.currentEpisodes.length) {
                    document.getElementById('episodes-container').innerHTML = window.currentEpisodes.map((ep, i) => `
                        <button class="ep-btn" id="ep-btn-${i}" onclick="playEpisode(${i})">
                            ${ep.name}
                        </button>
                    `).join('');
                    playEpisode(0);
                } else {
                    document.getElementById('episodes-container').innerHTML = '<div style="color:var(--muted)">Эпизоды не найдены</div>';
                }
            } catch(e) {
                document.getElementById('watch-title').innerText = 'Ошибка';
                document.getElementById('watch-desc').innerText = e.message;
            }
        }

        loadHome();
        loadCatalog();
    </script>
</body>
</html>
    """
