import asyncio
import aiohttp
import json
from pathlib import Path

ARTISTS_FILE = Path("artists.json")

def load_artists(genre=None):
    if not ARTISTS_FILE.exists():
        return []
    try:
        with open(ARTISTS_FILE, "r", encoding="utf-8") as f:
            artists = json.load(f)
        if genre and genre != "any":
            artists = [artist for artist in artists if artist.get("genre") == genre]
        return artists
    except (json.JSONDecodeError, IOError):
        return []

async def fetch(session, url):
    try:
        async with session.get(url) as response:
            if response.status != 200:
                print(f"Ошибка при запросе {url}: {response.status}")
                return None
            return await response.json()
    except Exception as e:
        print(f"Исключение при запросе {url}: {e}")
        return None

async def get_artist_top_tracks(session, artist_id, limit=20):
    url = f"https://api.deezer.com/artist/{artist_id}/top?limit={limit}"
    data = await fetch(session, url)
    if not data:
        return []
    tracks = data.get("data", [])
    valid_tracks = []
    for track in tracks:
        if "preview" in track and track["preview"]:
            try:
                async with session.head(track["preview"]) as response:
                    if response.status == 200:
                        valid_tracks.append(track)
                    else:
                        print(f"Превью недоступно: {track['preview']} (статус: {response.status})")
            except Exception as e:
                print(f"Ошибка проверки превью {track['preview']}: {e}")
        else:
            print(f"Трек без превью: {track.get('title', 'Unknown')}")
    return valid_tracks