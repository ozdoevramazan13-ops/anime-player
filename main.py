from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import httpx

app = FastAPI()
API_BASE = "https://api.anilibria.app/api/v1"

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
        if search:
            r = await client.get(f"{API_BASE}/app/search/releases?query={search}")
        else:
            r = await client.get(f"{API_BASE}/anime/releases/latest?limit=24")
        
        data = r.json()
        if isinstance(data, dict): data = data.get("data", [])
        
        items = []
        for i in data:
            team = i.get("team") or {}
            voice = team.get("voice") or []
            # Собираем всех озвучивающих в строку
            voice_names = ", ".join([v.get("name") for v in voice]) if voice else "Неизвестно"

            items.append({
                "id": i.get("id"), 
                "name": i.get("name", {}).get("main", "Без названия"), 
                "poster": get_poster(i),
                "year": i.get("year"),
                "voice": voice_names
            })
        return {"items": items}

@app.get("/api/release/{release_id}")
async def release_info(release_id: int):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_BASE}/anime/releases/{release_id}")
        data = r.json()
        
        team = data.get("team") or {}
        voice = team.get("voice") or []
        voice_names = ", ".join([v.get("name") for v in voice]) if voice else "Неизвестно"
        
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

@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Neon Anime</title>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@1.5.17/dist/hls.min.js"></script>
    <style>
        :root { 
            --bg: #050914; 
            --surface: #0d1526; 
            --accent: #00f0ff; 
            --accent-glow: 0 0 10px rgba(0, 240, 255, 0.5), 0 0 20px rgba(0, 240, 255, 0.3);
            --text: #e2e8f0; 
            --muted: #64748b; 
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; overflow-x: hidden; }
        
        header { padding: 1rem 2rem; display: flex; gap: 2rem; align-items: center; background: rgba(13, 21, 38, 0.8); backdrop-filter: blur(10px); position: sticky; top: 0; z-index: 100; border-bottom: 1px solid rgba(0, 240, 255, 0.2); }
        .logo { color: var(--accent); font-size: 1.5rem; font-weight: 900; text-transform: uppercase; letter-spacing: 2px; text-shadow: var(--accent-glow); cursor: pointer; }
        nav { display: flex; gap: 1.5rem; }
        nav a { color: var(--text); text-decoration: none; font-weight: 600; cursor: pointer; transition: 0.3s; }
        nav a:hover, nav a.active { color: var(--accent); text-shadow: var(--accent-glow); }
        .search-box { margin-left: auto; display: flex; gap: 0.5rem; }
        input { padding: 0.6rem 1rem; border-radius: 20px; border: 1px solid var(--muted); background: rgba(0,0,0,0.5); color: white; outline: none; transition: 0.3s; }
        input:focus { border-color: var(--accent); box-shadow: var(--accent-glow); }
        button { padding: 0.6rem 1.2rem; border: none; border-radius: 20px; background: transparent; color: var(--accent); font-weight: bold; border: 1px solid var(--accent); cursor: pointer; transition: 0.3s; }
        button:hover { background: var(--accent); color: var(--bg); box-shadow: var(--accent-glow); }
        
        main { padding: 2rem; max-width: 1400px; margin: 0 auto; }
        .page { display: none; animation: fadeIn 0.4s ease; }
        .page.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        
        .hero { background: linear-gradient(to right, rgba(5, 9, 20, 0.9), rgba(5, 9, 20, 0.3)), url('https://images.unsplash.com/photo-1578632767115-351597cf2477?q=80&w=2000&auto=format&fit=crop') center/cover; height: 400px; border-radius: 20px; display: flex; align-items: center; padding: 3rem; margin-bottom: 2rem; border: 1px solid rgba(0, 240, 255, 0.2); box-shadow: inset 0 0 50px rgba(0,0,0,0.8); }
        .hero h2 { font-size: 3rem; margin-bottom: 1rem; text-shadow: 0 0 10px rgba(0,0,0,0.8); }
        .hero p { font-size: 1.2rem; color: var(--muted); max-width: 500px; }
        
        .section-title { font-size: 1.8rem; margin-bottom: 1.5rem; border-left: 4px solid var(--accent); padding-left: 1rem; text-shadow: var(--accent-glow); }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 1.5rem; }
        .card { background: var(--surface); border-radius: 12px; overflow: hidden; cursor: pointer; transition: 0.3s; border: 1px solid transparent; position: relative; }
        .card:hover { transform: translateY(-5px); border-color: var(--accent); box-shadow: var(--accent-glow); }
        .card img { width: 100%; aspect-ratio: 2/3; object-fit: cover; display: block; }
        .card-info { padding: 1rem; }
        .card-title { font-size: 0.95rem; font-weight: bold; margin-bottom: 0.5rem; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
        .card-meta { font-size: 0.8rem; color: var(--accent); }
        .card-voice { font-size: 0.75rem; color: var(--muted); margin-top: 0.3rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        
        .details-layout { display: grid; grid-template-columns: 1fr 350px; gap: 2rem; }
        @media (max-width: 900px) { .details-layout { grid-template-columns: 1fr; } }
        .video-container { background: black; border-radius: 12px; overflow: hidden; border: 1px solid rgba(0, 240, 255, 0.3); box-shadow: 0 0 20px rgba(0, 240, 255, 0.1); }
        video { width: 100%; aspect-ratio: 16/9; display: block; }
        .details-info { margin-top: 1.5rem; background: var(--surface); padding: 1.5rem; border-radius: 12px; }
        .details-info h2 { color: var(--accent); margin-bottom: 1rem; }
        .details-info p { color: var(--muted); line-height: 1.6; font-size: 0.95rem; }
        .tag { display: inline-block; background: rgba(0, 240, 255, 0.1); color: var(--accent); padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.8rem; margin-right: 0.5rem; margin-bottom: 0.5rem; border: 1px solid rgba(0, 240, 255, 0.3); }
        
        .episode-list { background: var(--surface); border-radius: 12px; padding: 1rem; max-height: 600px; overflow-y: auto; }
        .episode-list h3 { margin-bottom: 1rem; color: var(--accent); }
        .ep-btn { width: 100%; text-align: left; padding: 1rem; margin-bottom: 0.5rem; background: rgba(0,0,0,0.3); color: white; border: 1px solid #1e293b; border-radius: 8px; cursor: pointer; transition: 0.2s; display: flex; justify-content: space-between; }
        .ep-btn:hover { border-color: var(--accent); background: rgba(0, 240, 255, 0.05); }
        .ep-btn.active { border-color: var(--accent); box-shadow: inset 0 0 10px rgba(0,240,255,0.2); }
        
        .back-btn { margin-bottom: 1.5rem; display: inline-flex; align-items: center; gap: 0.5rem; background: none; border: none; color: var(--muted); font-size: 1rem; cursor: pointer; }
        .back-btn:hover { color: var(--accent); text-shadow: var(--accent-glow); }
        
        .loader { text-align: center; color: var(--accent); font-size: 1.2rem; padding: 3rem; text-shadow: var(--accent-glow); }
    </style>
</head>
<body>
    <header>
        <div class="logo" onclick="nav('home')">Neon Anime</div>
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
            <div class="hero">
                <div>
                    <h2>Добро пожаловать</h2>
                    <p>Твой неоновый портал в мир аниме. Смотри любимые тайтлы в высоком качестве с удобным плеером.</p>
                </div>
            </div>
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
                    <div class="video-container">
                        <video id="video" controls></video>
                    </div>
                    <div class="details-info">
                        <h2 id="watch-title">Название</h2>
                        <div id="watch-tags" style="margin-bottom: 1rem;"></div>
                        <p id="watch-desc">Описание...</p>
                    </div>
                </div>
                <div class="right-col">
                    <div class="episode-list">
                        <h3>Эпизоды</h3>
                        <div id="episodes-container"><div class="loader">Загрузка...</div></div>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <script>
        let hls = null;
        let currentEpisodes = [];

        function nav(pageId) {
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('nav a').forEach(a => a.classList.remove('active'));
            
            document.getElementById('page-' + pageId).classList.add('active');
            if (document.getElementById('nav-' + pageId)) {
                document.getElementById('nav-' + pageId).classList.add('active');
            }
            window.scrollTo(0, 0);
        }

        async function loadCatalog(query = '') {
            const targetGrid = document.getElementById('catalog-grid');
            targetGrid.innerHTML = '<div class="loader">Загрузка...</div>';
            
            try {
                const res = await fetch('/api/catalog' + (query ? '?search=' + encodeURIComponent(query) : ''));
                const data = await res.json();
                renderGrid(data.items, targetGrid);
            } catch(e) {
                targetGrid.innerHTML = '<div class="loader">Ошибка загрузки</div>';
            }
        }

        async function loadHome() {
            const targetGrid = document.getElementById('home-grid');
            try {
                const res = await fetch('/api/catalog');
                const data = await res.json();
                const shuffled = data.items.sort(() => 0.5 - Math.random()).slice(0, 10);
                renderGrid(shuffled, targetGrid);
            } catch(e) {
                targetGrid.innerHTML = '<div class="loader">Ошибка загрузки</div>';
            }
        }

        function renderGrid(items, container) {
            if (!items || items.length === 0) {
                container.innerHTML = '<div class="loader">Ничего не найдено</div>';
                return;
            }
            container.innerHTML = items.map(item => `
                <div class="card" onclick="openAnime(${item.id})">
                    <img src="${item.poster}" loading="lazy" onerror="this.src='https://via.placeholder.com/300x450/0d1526/00f0ff?text=No+Image'">
                    <div class="card-info">
                        <div class="card-title">${item.name}</div>
                        <div class="card-meta">${item.year || ''}</div>
                        <div class="card-voice" title="${item.voice}">🎙 ${item.voice}</div>
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
            document.getElementById('watch-tags').innerHTML = '';
            document.getElementById('episodes-container').innerHTML = '<div class="loader">Загрузка...</div>';
            document.getElementById('video').removeAttribute('src');
            document.getElementById('video').poster = '';
            if (hls) { hls.destroy(); hls = null; }

            try {
                const res = await fetch('/api/release/' + id);
                const data = await res.json();
                
                document.getElementById('watch-title').innerText = data.name;
                document.getElementById('watch-desc').innerText = data.description || 'Описание отсутствует.';
                
                let tagsHtml = `<span class="tag">${data.year || 'Год неизвестен'}</span>`;
                tagsHtml += `<span class="tag">🎙 Озвучка: ${data.voice}</span>`;
                document.getElementById('watch-tags').innerHTML = tagsHtml;
                
                currentEpisodes = data.episodes || [];
                
                if (currentEpisodes.length === 0) {
                    document.getElementById('episodes-container').innerHTML = '<div style="color:var(--muted)">Эпизоды не найдены</div>';
                    return;
                }

                document.getElementById('episodes-container').innerHTML = currentEpisodes.map((ep, i) => `
                    <button class="ep-btn" id="ep-btn-${i}" onclick="playEpisode(${i})">
                        <span>${ep.name}</span>
                        <span>▶</span>
                    </button>
                `).join('');

                playEpisode(0);

            } catch(e) {
                document.getElementById('watch-title').innerText = 'Ошибка загрузки';
                document.getElementById('watch-desc').innerText = e.message;
            }
        }

        function playEpisode(index) {
            const ep = currentEpisodes[index];
            if (!ep) return;

            document.querySelectorAll('.ep-btn').forEach(btn => btn.classList.remove('active'));
            const btn = document.getElementById('ep-btn-' + index);
            if (btn) btn.classList.add('active');

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
            
            if (window.innerWidth < 900) {
                document.querySelector('.video-container').scrollIntoView({ behavior: 'smooth' });
            }
        }

        loadHome();
        loadCatalog();
    </script>
</body>
</html>
    """
