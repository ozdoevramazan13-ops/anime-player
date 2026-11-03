from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import httpx
import urllib.parse

app = FastAPI()
ANILIBRIA_BASE = "https://api.anilibria.app/api/v1"
KODIK_API = "https://kodikapi.com/search"
# Публичный токен Kodik (может меняться, но часто работает для тестов)
KODIK_TOKEN = "b3f8c8e7f3e0e1d6c9a2b5f4e8d7c6b5"

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
            r = await client.get(f"{ANILIBRIA_BASE}/app/search/releases?query={search}")
        else:
            r = await client.get(f"{ANILIBRIA_BASE}/anime/releases/latest?limit=24")
        
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

@app.get("/api/release/{release_id}")
async def release_info(release_id: int):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{ANILIBRIA_BASE}/anime/releases/{release_id}")
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
                    "hls": hls_url,
                    "voice": voice_names
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

# Поиск озвучек на Kodik (альтернативный источник)
@app.get("/api/voices/{title}")
async def get_voices(title: str):
    async with httpx.AsyncClient() as client:
        params = {
            "token": KODIK_TOKEN,
            "title": title,
            "limit": 10,
            "with_episodes": "true"
        }
        try:
            r = await client.get(KODIK_API, params=params)
            data = r.json()
            results = data.get("results", [])
            
            voices = []
            for item in results:
                voice_name = item.get("translation", {}).get("title", "Неизвестно")
                # У Kodik ссылки на эпизоды лежат в link
                episodes_link = item.get("link", "")
                if episodes_link:
                    voices.append({
                        "voice": voice_name,
                        "episodes_url": episodes_link
                    })
            return {"voices": voices}
        except Exception:
            return {"voices": []}

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
        /* ДИЗАЙН: Тёмно-синий неоновый */
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
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 1.5rem; }
        .card { background: var(--surface); border-radius: 16px; overflow: hidden; cursor: pointer; transition: 0.3s; border: 1px solid transparent; position: relative; }
        .card:hover { transform: translateY(-8px); border-color: var(--accent); box-shadow: 0 10px 30px rgba(77, 124, 255, 0.25); }
        .card img { width: 100%; aspect-ratio: 2/3; object-fit: cover; display: block; }
        .card-info { padding: 1rem; }
        .card-title { font-size: 0.9rem; font-weight: bold; margin-bottom: 0.4rem; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
        .card-meta { font-size: 0.75rem; color: var(--accent); }
        .card-voice { font-size: 0.7rem; color: var(--muted); margin-top: 0.3rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        
        .details-layout { display: grid; grid-template-columns: 1fr 380px; gap: 2rem; }
        @media (max-width: 1000px) { .details-layout { grid-template-columns: 1fr; } }
        .video-container { background: black; border-radius: 16px; overflow: hidden; border: 1px solid rgba(77, 124, 255, 0.3); box-shadow: 0 0 30px rgba(77, 124, 255, 0.15); }
        video { width: 100%; aspect-ratio: 16/9; display: block; }
        .details-info { margin-top: 1.5rem; background: var(--surface); padding: 1.5rem; border-radius: 16px; }
        .details-info h2 { color: var(--accent); margin-bottom: 0.8rem; font-size: 1.4rem; }
        .details-info p { color: var(--muted); line-height: 1.7; font-size: 0.9rem; }
        .tag { display: inline-block; background: rgba(77, 124, 255, 0.15); color: var(--accent); padding: 0.3rem 1rem; border-radius: 20px; font-size: 0.8rem; margin-right: 0.5rem; margin-bottom: 0.5rem; border: 1px solid rgba(77, 124, 255, 0.3); }
        
        .episode-list { background: var(--surface); border-radius: 16px; padding: 1.2rem; max-height: 650px; overflow-y: auto; }
        .episode-list h3 { margin-bottom: 1rem; color: var(--accent); font-size: 1.1rem; }
        .ep-btn { width: 100%; text-align: left; padding: 0.9rem 1rem; margin-bottom: 0.5rem; background: rgba(0,0,0,0.25); color: white; border: 1px solid rgba(77, 124, 255, 0.15); border-radius: 10px; cursor: pointer; transition: 0.2s; display: flex; justify-content: space-between; align-items: center; }
        .ep-btn:hover { border-color: var(--accent); background: rgba(77, 124, 255, 0.08); }
        .ep-btn.active { border-color: var(--accent); box-shadow: inset 0 0 15px rgba(77, 124, 255, 0.2); background: rgba(77, 124, 255, 0.12); }
        
        /* Выбор озвучки */
        .voice-selector { margin-bottom: 1.5rem; background: var(--surface); padding: 1rem; border-radius: 12px; border: 1px solid rgba(77, 124, 255, 0.2); }
        .voice-selector label { display: block; font-size: 0.85rem; color: var(--muted); margin-bottom: 0.5rem; }
        .voice-selector select { width: 100%; padding: 0.7rem; border-radius: 8px; background: rgba(0,0,0,0.4); color: white; border: 1px solid var(--muted); font-size: 0.9rem; }
        .voice-selector select:focus { border-color: var(--accent); outline: none; }
        
        .back-btn { margin-bottom: 1.5rem; display: inline-flex; align-items: center; gap: 0.5rem; background: none; border: none; color: var(--muted); font-size: 1rem; cursor: pointer; }
        .back-btn:hover { color: var(--accent); text-shadow: var(--accent-glow); }
        .loader { text-align: center; color: var(--accent); font-size: 1.2rem; padding: 3rem; text-shadow: var(--accent-glow); }
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
            <div class="hero">
                <h2>Твой портал в мир аниме</h2>
                <p>Смотри любимые тайтлы в высоком качестве. Выбирай озвучку по вкусу.</p>
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
                    
                    <!-- Блок выбора озвучки (Kodik) -->
                    <div class="voice-selector" id="voice-selector" style="display:none;">
                        <label>Доступные озвучки (альтернативный источник):</label>
                        <select id="voiceSelect" onchange="changeVoice()">
                            <option value="">-- Выберите озвучку --</option>
                        </select>
                    </div>

                    <div class="details-info">
                        <h2 id="watch-title">Название</h2>
                        <div id="watch-tags" style="margin-bottom: 1rem;"></div>
                        <p id="watch-desc">Описание...</p>
                    </div>
                </div>
                <div class="right-col">
                    <div class="episode-list">
                        <h3>Эпизоды (AniLibria)</h3>
                        <div id="episodes-container"><div class="loader">Загрузка...</div></div>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <script>
        let hls = null;
        let currentEpisodes = [];
        let currentTitle = '';

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
                const shuffled = data.items.sort(() => 0.5 - Math.random()).slice(0, 12);
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
                    <img src="${item.poster}" loading="lazy" onerror="this.src='https://via.placeholder.com/300x450/121a2e/4d7cff?text=No+Image'">
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
            document.getElementById('voice-selector').style.display = 'none';
            document.getElementById('video').removeAttribute('src');
            if (hls) { hls.destroy(); hls = null; }

            try {
                const res = await fetch('/api/release/' + id);
                const data = await res.json();
                
                currentTitle = data.name;
                document.getElementById('watch-title').innerText = data.name;
                document.getElementById('watch-desc').innerText = data.description || 'Описание отсутствует.';
                
                let tagsHtml = `<span class="tag">${data.year || 'Год неизвестен'}</span>`;
                tagsHtml += `<span class="tag">🎙 ${data.voice}</span>`;
                document.getElementById('watch-tags').innerHTML = tagsHtml;
                
                currentEpisodes = data.episodes || [];
                
                if (currentEpisodes.length > 0) {
                    document.getElementById('episodes-container').innerHTML = currentEpisodes.map((ep, i) => `
                        <button class="ep-btn" id="ep-btn-${i}" onclick="playEpisode(${i})">
                            <span>${ep.name}</span>
                            <span>▶</span>
                        </button>
                    `).join('');
                    playEpisode(0);
                } else {
                    document.getElementById('episodes-container').innerHTML = '<div style="color:var(--muted)">Эпизоды не найдены</div>';
                }

                // Ищем альтернативные озвучки на Kodik
                loadVoices(data.name);

            } catch(e) {
                document.getElementById('watch-title').innerText = 'Ошибка загрузки';
                document.getElementById('watch-desc').innerText = e.message;
            }
        }

        async function loadVoices(title) {
            try {
                const res = await fetch('/api/voices/' + encodeURIComponent(title));
                const data = await res.json();
                if (data.voices && data.voices.length > 0) {
                    const selector = document.getElementById('voice-selector');
                    const select = document.getElementById('voiceSelect');
                    selector.style.display = 'block';
                    select.innerHTML = '<option value="">-- Выберите озвучку (Kodik) --</option>' + 
                        data.voices.map((v, i) => `<option value="${i}">${v.voice}</option>`).join('');
                    // Сохраняем ссылки для переключения
                    window.kodikVoices = data.voices;
                }
            } catch(e) {
                console.log('Kodik voices not found');
            }
        }

        function changeVoice() {
            const idx = document.getElementById('voiceSelect').value;
            if (idx === '' || !window.kodikVoices) return;
            const voice = window.kodikVoices[parseInt(idx)];
            // Kodik отдает ссылку на iframe, но мы можем попробовать загрузить как HLS
            // В реальности Kodik использует свой плеер, но для демо просто покажем алерт
            alert('Выбрана озвучка: ' + voice.voice + '.\\n\\nKodik требует встраивания iframe. В этой версии переключение доступно только для AniLibria.\\n\\nДля полной интеграции нужен прокси-сервер.');
            // Сбрасываем селект обратно
            document.getElementById('voiceSelect').value = '';
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
        }

        loadHome();
        loadCatalog();
    </script>
</body>
</html>
    """
