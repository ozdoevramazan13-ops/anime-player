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
            items.append({
                "id": i.get("id"), 
                "name": i.get("name", {}).get("main", "Без названия"), 
                "poster": get_poster(i),
                "year": i.get("year")
            })
        return {"items": items}

@app.get("/api/episodes/{release_id}")
async def episodes(release_id: int):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_BASE}/anime/releases/{release_id}")
        data = r.json()
        
        # Собираем эпизоды, учитывая озвучки
        eps = []
        for e in data.get("episodes", []):
            hls_url = e.get("hls_1080") or e.get("hls_720") or e.get("hls_480")
            if hls_url:
                eps.append({
                    "name": e.get("name") or f"Эпизод {e.get('ordinal')}", 
                    "hls": hls_url
                })
        return {"episodes": eps}

@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Anime Vault</title>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@1.5.17/dist/hls.min.js"></script>
    <style>
        :root { --bg: #0f0f13; --surface: #1a1a22; --accent: #ff6b35; --text: #e8e8ef; --muted: #8a8a9a; }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); height: 100vh; display: flex; flex-direction: column; }
        header { padding: 1rem; display: flex; gap: 1rem; align-items: center; border-bottom: 1px solid #2a2a35; }
        h1 { color: var(--accent); font-size: 1.2rem; }
        input { flex: 1; padding: 0.6rem; border-radius: 8px; border: 1px solid #2a2a35; background: var(--surface); color: white; }
        button { padding: 0.6rem 1rem; border: none; border-radius: 8px; background: var(--accent); color: white; font-weight: bold; cursor: pointer; }
        main { display: grid; grid-template-columns: 1fr 350px; flex: 1; overflow: hidden; }
        .player { padding: 1rem; display: flex; flex-direction: column; gap: 1rem; }
        video { width: 100%; border-radius: 10px; background: black; aspect-ratio: 16/9; }
        .sidebar { background: var(--surface); border-left: 1px solid #2a2a35; overflow-y: auto; padding: 1rem; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 0.8rem; }
        .card { cursor: pointer; text-align: center; }
        .card img { width: 100%; aspect-ratio: 2/3; object-fit: cover; border-radius: 6px; background: #222; }
        .card:hover img { outline: 2px solid var(--accent); }
        .card span { font-size: 0.75rem; display: block; margin-top: 0.3rem; }
        .ep-btn { width: 100%; text-align: left; padding: 0.8rem; margin-bottom: 0.5rem; background: #222; color: white; border: 1px solid #333; border-radius: 6px; cursor: pointer; }
        .ep-btn:hover { background: #333; border-color: var(--accent); }
        .back { background: #444; margin-bottom: 1rem; }
        @media (max-width: 800px) { main { grid-template-columns: 1fr; overflow: auto; } .sidebar { border-left: none; border-top: 1px solid #2a2a35; } }
    </style>
</head>
<body>
    <header>
        <h1>▶ Anime Vault</h1>
        <input type="text" id="search" placeholder="Поиск аниме...">
        <button onclick="loadCatalog(document.getElementById('search').value)">Найти</button>
    </header>
    <main>
        <div class="player">
            <video id="video" controls></video>
            <h3 id="nowPlaying">Выберите аниме</h3>
        </div>
        <div class="sidebar">
            <div id="list"><div style="text-align:center; color:var(--accent)">Загрузка...</div></div>
        </div>
    </main>
    <script>
        let hls = null;
        async function loadCatalog(search = '') {
            document.getElementById('list').innerHTML = '<div style="text-align:center; color:var(--accent)">Загрузка...</div>';
            try {
                const res = await fetch('/api/catalog' + (search ? '?search=' + encodeURIComponent(search) : ''));
                const data = await res.json();
                const list = document.getElementById('list');
                if (!data.items || data.items.length === 0) {
                    list.innerHTML = '<div style="text-align:center">Ничего не найдено</div>';
                    return;
                }
                list.innerHTML = '<div class="grid">' + data.items.map(item => `
                    <div class="card" onclick="loadEpisodes(${item.id}, '${item.name.replace(/'/g, "\\\\'")}')">
                        <img src="${item.poster}" loading="lazy" onerror="this.src='https://via.placeholder.com/150x225?text=No+Image'">
                        <span>${item.name}</span>
                    </div>
                `).join('') + '</div>';
            } catch(e) {
                document.getElementById('list').innerText = 'Ошибка: ' + e.message;
            }
        }
        async function loadEpisodes(id, name) {
            document.getElementById('list').innerHTML = '<div style="text-align:center; color:var(--accent)">Загрузка эпизодов...</div>';
            try {
                const res = await fetch('/api/episodes/' + id);
                const data = await res.json();
                const list = document.getElementById('list');
                if (!data.episodes || data.episodes.length === 0) {
                    list.innerHTML = '<div style="text-align:center">Эпизоды не найдены</div><button class="ep-btn back" onclick="loadCatalog()">Назад</button>';
                    return;
                }
                list.innerHTML = `<button class="ep-btn back" onclick="loadCatalog()">← Назад в каталог</button>
                    <h3 style="margin-bottom: 10px;">${name}</h3>` + 
                    data.episodes.map(ep => `
                        <button class="ep-btn" onclick="playVideo('${ep.hls}', '${ep.name}')">${ep.name}</button>
                    `).join('');
            } catch(e) {
                document.getElementById('list').innerText = 'Ошибка: ' + e.message;
            }
        }
        function playVideo(url, name) {
            if (hls) hls.destroy();
            const video = document.getElementById('video');
            document.getElementById('nowPlaying').innerText = name;
            if (Hls.isSupported()) {
                hls = new Hls();
                hls.loadSource(url);
                hls.attachMedia(video);
            } else {
                video.src = url;
            }
            video.play();
        }
        loadCatalog();
    </script>
</body>
</html>
    """
