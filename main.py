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
                r = await client.get(f"{ANILIBRIA_BASE}/anime/releases/latest", params={"limit": 50})
            
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
    <title>Anime Portal</title>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@1.5.17/dist/hls.min.js"></script>
    <style>
        :root { 
            --bg: #0a0e1a; 
            --surface: #121a2e; 
            --accent: #4d7cff; 
            --accent-glow: 0 0 15px rgba(77, 124, 255, 0.6);
            --text: #e8edf5; 
            --muted: #6b7a99; 
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
        
        header { padding: 1.2rem 2rem; display: flex; gap: 2rem; align-items: center; background: rgba(18, 26, 46, 0.9); backdrop-filter: blur(12px); position: sticky; top: 0; z-index: 100; border-bottom: 1px solid rgba(77, 124, 255, 0.2); }
        .logo { color: var(--accent); font-size: 1.6rem; font-weight: 900; text-transform: uppercase; letter-spacing: 2px; text-shadow: var(--accent-glow); cursor: pointer; }
        nav { display: flex; gap: 1.5rem; }
        nav a { color: var(--text); text-decoration: none; font-weight: 600; cursor: pointer; transition: 0.3s; }
        nav a:hover, nav a.active { color: var(--accent); text-shadow: var(--accent-glow); }
        .search-box { margin-left: auto; display: flex; gap: 0.5rem; }
        input { padding: 0.7rem 1.2rem; border-radius: 25px; border: 1px solid var(--muted); background: rgba(0,0,0,0.4); color: white; outline: none; transition: 0.3s; }
        input:focus { border-color: var(--accent); box-shadow: var(--accent-glow); }
        button { padding: 0.7rem 1.5rem; border: none; border-radius: 25px; background: transparent; color: var(--accent); font-weight: bold; border: 1px solid var(--accent); cursor: pointer; transition: 0.3s; }
        button:hover { background: var(--accent); color: var(--bg); box-shadow: var(--accent-glow); }
        
        main { padding: 2rem; max-width: 1500px; margin: 0 auto; }
        .page { display: none; animation: fadeIn 0.4s ease; }
        .page.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        
        .hero { background: linear-gradient(135deg, rgba(10, 14, 26, 0.95), rgba(77, 124, 255, 0.15)), url('https://images.unsplash.com/photo-1578632767115-351597cf2477?q=80&w=2000&auto=format&fit=crop') center/cover; height: 380px; border-radius: 24px; display: flex; flex-direction: column; justify-content: center; padding: 3rem; margin-bottom: 2.5rem; border: 1px solid rgba(77, 124, 255, 0.3); box-shadow: inset 0 0 60px rgba(0,0,0,0.7), 0 0 30px rgba(77, 124, 255, 0.1); }
        .hero h2 { font-size: 2.8rem; margin-bottom: 1rem; text-shadow: 0 2px 20px rgba(0,0,0,0.9); }
        .hero p { font-size: 1.1rem; color: var(--muted); max-width: 500px; }
        
        .section-title { font-size: 1.6rem; margin-bottom: 1.5rem; border-left: 4px solid var(--accent); padding-left: 1rem; text-shadow: var(--accent-glow); }
        
        /* Сетка строго по 5 в ряд */
        .grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 1.5rem; }
        @media (max-width: 1200px) { .grid { grid-template-columns: repeat(4, 1fr); } }
        @media (max-width: 900px) { .grid { grid-template-columns: repeat(3, 1fr); } }
        @media (max-width: 600px) { .grid { grid-template-columns: repeat(2, 1fr); gap: 1rem; } }
        
        .card { background: var(--surface); border-radius: 16px; overflow: hidden; cursor: pointer; transition: 0.3s; border: 1px solid transparent; position: relative; }
        .card:hover { transform: translateY(-8px); border-color: var(--accent); box-shadow: 0 10px 30px rgba(77, 124, 255, 0.25); }
        .card img { width: 100%; aspect-ratio: 2/3; object-fit: cover; display: block; }
        .card-info { padding: 1rem; }
        .card-title { font-size: 0.9rem; font-weight: bold; margin-bottom: 0.4rem; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
        .card-meta { font-size: 0.75rem; color: var(--accent); }
        
        .details-layout { display: grid; grid-template-columns: 1fr 380px; gap: 2rem; }
        @media (max-width: 1000px) { .details-layout { grid-template-columns: 1fr; } }
        .video-container { background: black; border-radius: 16px; overflow: hidden; border: 1px solid rgba(77, 124, 255, 0.3); box-shadow: 0 0 30px rgba(77, 124, 255, 0.15); aspect-ratio: 16/9; }
        video { width: 100%; height: 100%; display: block; }
        .details-info { margin-top: 1.5rem; background: var(--surface); padding: 1.5rem; border-radius: 16px; }
        .details-info h2 { color: var(--accent); margin-bottom: 0.8rem; font-size: 1.4rem; }
        .details-info p { color: var(--muted); line-height: 1.7; font-size: 0.9rem; }
        .voice-selector { margin-bottom: 1.5rem; background: var(--surface); padding: 1.5rem; border-radius: 16px; border: 1px solid rgba(77, 124, 255, 0.2); }
        .voice-selector label { display: block; font-size: 0.9rem; color: var(--accent); margin-bottom: 0.8rem; font-weight: bold; }
        .voice-selector select { width: 100%; padding: 0.9rem; border-radius: 10px; background: rgba(0,0,0,0.4); color: white; border: 1px solid var(--muted); }
        .back-btn { margin-bottom: 1.5rem; display: inline-flex; align-items: center; gap: 0.5rem; background: none; border: none; color: var(--muted); font-size: 1rem; cursor: pointer; }
        .back-btn:hover { color: var(--accent); text-shadow: var(--accent-glow); }
        .loader { text-align: center; color: var(--accent); font-size: 1.2rem; padding: 3rem; text-shadow: var(--accent-glow); }
        .episode-list { background: var(--surface); border-radius: 16px; padding: 1.2rem; max-height: 650px; overflow-y: auto; }
        .ep-btn { width: 100%; text-align: left; padding: 0.9rem 1rem; margin-bottom: 0.5rem; background: rgba(0,0,0,0.25); color: white; border: 1px solid rgba(77, 124, 255, 0.15); border-radius: 10px; cursor: pointer; transition: 0.2s; display: flex; justify-content: space-between; }
        .ep-btn:hover { border-color: var(--accent); background: rgba(77, 124, 255, 0.08); }
        .ep-btn.active { border-color: var(--accent); box-shadow: inset 0 0 15px rgba(77, 124, 255, 0.2); background: rgba(77, 124, 255, 0.12); }
    </style>
</head>
<body>
    <header>
        <div class="logo" onclick="nav('home')">Anime Portal</div>
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
            <div class="hero"><h2>Твой портал в мир аниме</h2><p>Смотри любимые тайтлы в высоком качестве.</p></div>
            
            <!-- Секция истории просмотров -->
            <div id="history-section" style="display: none; margin-bottom: 2.5rem;">
                <h2 class="section-title">Вы недавно смотрели</h2>
                <div id="history-grid" class="grid"></div>
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
                    <div class="video-container"><video id="video" controls></video></div>
                    <div class="voice-selector" id="voice-selector" style="display:none;">
                        <label>🎙 Дополнительные озвучки (Kodik):</label>
                        <select id="voiceSelect" onchange="changeVoice()"><option value="">-- Выберите --</option></select>
                    </div>
                    <div class="details-info"><h2 id="watch-title">Название</h2><div id="watch-tags" style="margin-bottom: 1rem; color: var(--muted);"></div><p id="watch-desc">Описание...</p></div>
                </div>
                <div class="right-col"><div class="episode-list"><h3>Эпизоды</h3><div id="episodes-container"><div class="loader">Загрузка...</div></div></div></div>
            </div>
        </div>
    </main>
    <script>
        let hls = null, currentEpisodes = [], currentRelease = null;
        
        // История просмотров
        function getHistory() {
            try { return JSON.parse(localStorage.getItem('anime_history')) || []; } catch(e) { return []; }
        }
        function saveToHistory(anime) {
            let hist = getHistory();
            hist = hist.filter(a => a.id !== anime.id); // Удаляем дубликат
            hist.unshift(anime); // Добавляем в начало
            if (hist.length > 10) hist = hist.slice(0, 10); // Храним только 10 последних
            localStorage.setItem('anime_history', JSON.stringify(hist));
            loadHistory(); // Обновляем секцию на главной
        }
        function loadHistory() {
            const hist = getHistory();
            const section = document.getElementById('history-section');
            const grid = document.getElementById('history-grid');
            if (hist.length === 0) {
                section.style.display = 'none';
                return;
            }
            section.style.display = 'block';
            grid.innerHTML = hist.map(item => `
                <div class="card" onclick="openAnime(${item.id})">
                    <img src="${item.poster}" loading="lazy" onerror="this.src='https://via.placeholder.com/300x450/121a2e/4d7cff?text=No+Image'">
                    <div class="card-info">
                        <div class="card-title">${item.name}</div>
                        <div class="card-meta">${item.year || ''}</div>
                    </div>
                </div>
            `).join('');
        }

        function nav(id) { 
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active')); 
            document.querySelectorAll('nav a').forEach(a => a.classList.remove('active')); 
            document.getElementById('page-' + id).classList.add('active'); 
            if(document.getElementById('nav-' + id)) document.getElementById('nav-' + id).classList.add('active'); 
            window.scrollTo(0,0); 
        }
        
        async function loadCatalog(q = '') { 
            const g = document.getElementById('catalog-grid'); 
            g.innerHTML = '<div class="loader">Загрузка...</div>'; 
            try { 
                const r = await fetch('/api/catalog' + (q ? '?search=' + encodeURIComponent(q) : '')); 
                const d = await r.json(); 
                renderGrid(d.items, g); 
            } catch(e) { g.innerHTML = '<div class="loader">Ошибка</div>'; } 
        }
        
        async function loadHome() { 
            const g = document.getElementById('home-grid'); 
            try { 
                const r = await fetch('/api/catalog'); 
                const d = await r.json(); 
                renderGrid(d.items, g); 
            } catch(e) { g.innerHTML = '<div class="loader">Ошибка</div>'; } 
        }
        
        function renderGrid(items, c) { 
            if (!items || !items.length) { c.innerHTML = '<div class="loader">Ничего не найдено</div>'; return; } 
            c.innerHTML = items.map(i => `
                <div class="card" onclick="openAnime(${i.id})">
                    <img src="${i.poster}" loading="lazy" onerror="this.src='https://via.placeholder.com/300x450/121a2e/4d7cff?text=No+Image'">
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
            document.getElementById('voice-selector').style.display = 'none';
            if (hls) { hls.destroy(); hls = null; }
            document.getElementById('video').removeAttribute('src');
            
            try {
                const r = await fetch('/api/release/' + id);
                const d = await r.json();
                currentRelease = d;
                document.getElementById('watch-title').innerText = d.name;
                document.getElementById('watch-desc').innerText = d.description || 'Описание отсутствует.';
                document.getElementById('watch-tags').innerHTML = `Год: ${d.year || '?'} | Озвучка: ${d.voice}`;
                
                // Сохраняем в историю
                saveToHistory({ id: d.id, name: d.name, poster: d.poster, year: d.year });

                currentEpisodes = d.episodes || [];
                if (currentEpisodes.length) {
                    document.getElementById('episodes-container').innerHTML = currentEpisodes.map((ep, i) => `<button class="ep-btn" id="ep-btn-${i}" onclick="playEpisode(${i})"><span>${ep.name}</span><span>▶</span></button>`).join('');
                    playEpisode(0);
                } else {
                    document.getElementById('episodes-container').innerHTML = '<div style="color:var(--muted)">Эпизоды не найдены</div>';
                }
            } catch(e) { document.getElementById('watch-title').innerText = 'Ошибка'; document.getElementById('watch-desc').innerText = e.message; }
        }
        
        function playEpisode(i) {
            const ep = currentEpisodes[i]; if (!ep) return;
            document.querySelectorAll('.ep-btn').forEach(b => b.classList.remove('active'));
            const btn = document.getElementById('ep-btn-' + i); if (btn) btn.classList.add('active');
            const cont = document.querySelector('.video-container');
            if (!cont.querySelector('video')) cont.innerHTML = '<video id="video" controls></video>';
            const video = document.getElementById('video');
            if (hls) { hls.destroy(); hls = null; }
            if (Hls.isSupported()) { hls = new Hls(); hls.loadSource(ep.hls); hls.attachMedia(video); } else { video.src = ep.hls; }
            video.play().catch(() => {});
        }
        
        loadHome(); 
        loadCatalog();
        loadHistory();
    </script>
</body>
</html>
    """
