from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

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
        body { font-family: sans-serif; background: #111; color: white; margin: 0; display: flex; height: 100vh; }
        #player { flex: 1; padding: 10px; display: flex; flex-direction: column; }
        video { width: 100%; background: black; border-radius: 8px; }
        #catalog { width: 300px; background: #222; padding: 10px; overflow-y: auto; }
        .card { background: #333; margin-bottom: 8px; padding: 10px; border-radius: 6px; cursor: pointer; }
        .card:hover { background: #444; }
    </style>
</head>
<body>
    <div id="player">
        <video id="video" controls></video>
        <div style="padding: 10px 0;"><h3 id="nowPlaying">Выберите аниме</h3></div>
    </div>
    <div id="catalog">
        <h3>Каталог</h3>
        <div id="list">Загрузка...</div>
    </div>
    <script>
        let hls = null;
        async function loadCatalog() {
            try {
                const res = await fetch('/api/catalog');
                const data = await res.json();
                const list = document.getElementById('list');
                list.innerHTML = '';
                data.items.forEach(item => {
                    const div = document.createElement('div');
                    div.className = 'card';
                    div.innerHTML = `<b>${item.name}</b><br><small>${item.year || ''}</small>`;
                    div.onclick = () => loadEpisodes(item.id, item.name);
                    list.appendChild(div);
                });
            } catch(e) {
                document.getElementById('list').innerText = 'Ошибка: ' + e.message;
            }
        }
        async function loadEpisodes(id, name) {
            document.getElementById('list').innerHTML = 'Загрузка эпизодов...';
            try {
                const res = await fetch('/api/episodes/' + id);
                const data = await res.json();
                const list = document.getElementById('list');
                list.innerHTML = '<h3>' + name + '</h3>';
                data.episodes.forEach(ep => {
                    const div = document.createElement('div');
                    div.className = 'card';
                    div.innerText = ep.name;
                    div.onclick = () => playVideo(ep.hls, ep.name);
                    list.appendChild(div);
                });
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

@app.get("/api/catalog")
async def catalog():
    import httpx
    async with httpx.AsyncClient() as client:
        r = await client.get("https://api.anilibria.app/api/v1/anime/releases/latest?limit=20")
        data = r.json()
        items = []
        for i in data:
            items.append({
                "id": i.get("id"), 
                "name": i.get("name", {}).get("main", "Без названия"), 
                "year": i.get("year")
            })
        return {"items": items}

@app.get("/api/episodes/{release_id}")
async def episodes(release_id: int):
    import httpx
    async with httpx.AsyncClient() as client:
        r = await client.get(f"https://api.anilibria.app/api/v1/anime/releases/{release_id}")
        data = r.json()
        eps = []
        for e in data.get("episodes", []):
            hls = e.get("hls_1080") or e.get("hls_720")
            if hls:
                eps.append({"name": e.get("name") or f"Эпизод {e.get('ordinal')}", "hls": hls})
        return {"episodes": eps}
