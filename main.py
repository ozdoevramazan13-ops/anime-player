from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import httpx
import asyncio

app = FastAPI()

# --- КОНФИГУРАЦИЯ ---
SHIKIMORI_API = "https://shikimori.one/api"
KODIK_API = "https://kodikapi.com"
# Токен Kodik (публичный, может меняться)
KODIK_TOKEN = "b3f8c8e7f3e0e1d6c9a2b5f4e8d7c6b5"

HEADERS = {
    "User-Agent": "AnimePortal/1.0 (https://github.com/your-repo)" # Shikimori требует User-Agent 
}

# --- БЭКЕНД ---

@app.get("/api/catalog")
async def catalog(search: str = None):
    """Каталог с Shikimori (там есть ВСЕ аниме)."""
    async with httpx.AsyncClient(headers=HEADERS) as client:
        try:
            if search:
                # Поиск по названию
                r = await client.get(f"{SHIKIMORI_API}/animes", params={
                    "search": search, "limit": 30, "order": "popularity"
                })
            else:
                # Топ аниме (как на главной)
                r = await client.get(f"{SHIKIMORI_API}/animes", params={
                    "limit": 30, "order": "popularity"
                })
            
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
                    "score": anime.get("score", "0"),
                    "voice": "Kodik (выбор озвучек)" # Заглушка, реальные озвучки будут внутри
                })
            return {"items": items}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/release/{shikimori_id}")
async def release_info(shikimori_id: int):
    """Информация об аниме + поиск озвучек на Kodik."""
    async with httpx.AsyncClient(headers=HEADERS) as client:
        try:
            # 1. Получаем инфу с Shikimori
            r = await client.get(f"{SHIKIMORI_API}/animes/{shikimori_id}")
            r.raise_for_status()
            anime = r.json()
            
            poster = anime.get("image", {}).get("original", "")
            if poster and not poster.startswith("http"):
                poster = "https://shikimori.one" + poster

            # 2. Ищем озвучки на Kodik по shikimori_id
            voice_list = []
            try:
                k_params = {
                    "token": KODIK_TOKEN,
                    "shikimori_id": str(shikimori_id),
                    "limit": 20
                }
                kr = await client.get(f"{KODIK_API}/search", params=k_params)
                k_data = kr.json()
                
                for res in k_data.get("results", []):
                    # Kodik отдает ссылку на плеер, из которой можно вытащить озвучку
                    voice_name = res.get("translation", {}).get("title", "Неизвестно")
                    link = res.get("link", "")
                    if link and not link.startswith("http"):
                        link = "https:" + link
                    
                    if voice_name and link:
                        voice_list.append({
                            "voice": voice_name,
                            "link": link,
                            "quality": res.get("quality", "720p")
                        })
            except Exception:
                pass # Если Kodik не ответил, оставляем список пустым

            return {
                "id": anime.get("id"),
                "name": anime.get("russian") or anime.get("name"),
                "description": anime.get("description", "Описание отсутствует."),
                "poster": poster,
                "year": anime.get("aired_on", "")[:4] if anime.get("aired_on") else "",
                "score": anime.get("score", "0"),
                "voices": voice_list # Список доступных озвучек
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

# --- ФРОНТЕНД (Дизайн как у тебя был, но с выбором озвучек) ---

@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Anime Portal (Kodik Edition)</title>
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
        .video-container { background: black; border-radius: 16px; overflow: hidden; border: 1px solid rgba(77, 124, 255, 0.3); box-shadow: 0 0 30px rgba(77, 124, 255, 0.15); aspect-ratio: 16/9; display: flex; align-items: center; justify-content: center; color: var(--muted); }
        video { width: 100%; height: 100%; display: block; }
        .details-info { margin-top: 1.5rem; background: var(--surface); padding: 1.5rem; border-radius: 16px; }
        .details-info h2 { color: var(--accent); margin-bottom: 0.8rem; font-size: 1.4rem; }
        .details-info p { color: var(--muted); line-height: 1.7; font-size: 0.9rem; }
        
        .voice-selector { margin-bottom: 1.5rem; background: var(--surface); padding: 1.5rem; border-radius: 16px; border: 1px solid rgba(77, 124, 255, 0.2); }
        .voice-selector label { display: block; font-size: 0.9rem; color: var(--accent); margin-bottom: 0.8rem; font-weight: bold; }
        .voice-selector select { width: 100%; padding: 0.9rem; border-radius: 10px; background: rgba(0,0,0,0.4); color: white; border: 1px solid var(--muted); font-size: 0.95rem; }
        .voice-selector select:focus { border-color: var(--accent); outline: none; box-shadow: var(--accent-glow); }
        
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
                <p>База Shikimori + озвучки Kodik. Выбирай студию по вкусу.</p>
            </div>
            <h2 class="section-title">Популярное</h2>
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
                    <div class="video-container" id="player-container">
                        <p>Выберите озвучку, чтобы начать просмотр</p>
                    </div>
                    
                    <div class="voice-selector" id="voice-selector" style="display:none;">
                        <label>🎙 Выберите озвучку (Kodik):</label>
                        <select id="voiceSelect" onchange="changeVoice()">
                            <option value="">-- Выберите студию --</option>
                        </select>
                    </div>

                    <div class="details-info">
                        <h2 id="watch-title">Название</h2>
                        <div id="watch-tags" style="margin-bottom: 1rem; color: var(--muted);"></div>
                        <p id="watch-desc">Описание...</p>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <script>
        let currentAnime = null;

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
                renderGrid(data.items, targetGrid);
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
                        <div class="card-meta">${item.year} ★ ${item.score}</div>
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
            document.getElementById('player-container').innerHTML = '<p>Загрузка данных...</p>';
            document.getElementById('voice-selector').style.display = 'none';

            try {
                const res = await fetch('/api/release/' + id);
                const data = await res.json();
                
                currentAnime = data;
                document.getElementById('watch-title').innerText = data.name;
                document.getElementById('watch-desc').innerText = data.description || 'Описание отсутствует.';
                document.getElementById('watch-tags').innerHTML = `Год: ${data.year} | Рейтинг: ${data.score}`;
                
                if (data.voices && data.voices.length > 0) {
                    const selector = document.getElementById('voice-selector');
                    const select = document.getElementById('voiceSelect');
                    selector.style.display = 'block';
                    select.innerHTML = '<option value="">-- Выберите студию --</option>' + 
                        data.voices.map((v, i) => `<option value="${i}">${v.voice} (${v.quality})</option>`).join('');
                    
                    document.getElementById('player-container').innerHTML = '<p>Выберите озвучку в списке ниже</p>';
                } else {
                    document.getElementById('player-container').innerHTML = '<p style="color:red">Озвучки Kodik не найдены для этого тайтла. Попробуйте другое аниме.</p>';
                }

            } catch(e) {
                document.getElementById('watch-title').innerText = 'Ошибка загрузки';
                document.getElementById('watch-desc').innerText = e.message;
            }
        }

        function changeVoice() {
            const idx = document.getElementById('voiceSelect').value;
            if (idx === '' || !currentAnime || !currentAnime.voices) return;
            
            const voice = currentAnime.voices[parseInt(idx)];
            const container = document.getElementById('player-container');
            
            // Kodik отдает ссылку на iframe-плеер. Мы встраиваем его.
            // Это самый надежный способ, так как прямые HLS-ссылки Kodik требуют сложной расшифровки.
            container.innerHTML = `
                <iframe src="${voice.link}" 
                        style="width:100%; height:100%; border:none;" 
                        allow="autoplay; fullscreen; encrypted-media" 
                        allowfullscreen>
                </iframe>
            `;
        }

        loadHome();
        loadCatalog();
    </script>
</body>
</html>
    """
