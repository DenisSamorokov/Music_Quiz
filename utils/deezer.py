import asyncio
import aiohttp
import json
import os
from pathlib import Path

GENRES_DIR = Path("genres")
ALL_ARTISTS_FILE = Path("artists_with_tracks.json")

def load_artists(genre=None):
    artists = []
    if genre and genre != "any":
        # Загружаем артистов из файла жанра
        file_path = GENRES_DIR / f"{genre}.json"
        if not file_path.exists():
            print(f"Файл для жанра {genre} не найден.")
            return []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                genre_artists = json.load(f)
                # Преобразуем структуру для совместимости, исключая артистов без треков
                artists = [
                    {
                        "id": artist.get("id", f"unknown_{idx}"),
                        "name": artist["name"],
                        "genre": genre,
                        "tracks": artist["tracks"]
                    }
                    for idx, artist in enumerate(genre_artists)
                    if artist.get("tracks", [])  # Проверяем, что tracks не пустой
                ]
        except (json.JSONDecodeError, IOError) as e:
            print(f"Ошибка при загрузке {file_path}: {e}")
            return []
    else:
        # Загружаем всех артистов из artists_with_tracks.json
        if not ALL_ARTISTS_FILE.exists():
            print(f"Файл {ALL_ARTISTS_FILE} не найден.")
            return []
        try:
            with open(ALL_ARTISTS_FILE, "r", encoding="utf-8") as f:
                all_artists = json.load(f)
                # Преобразуем структуру для совместимости, исключая артистов без треков
                artists = [
                    {
                        "id": artist.get("id", f"unknown_{idx}"),
                        "name": artist["name"],
                        "genre": ", ".join(artist.get("genres", ["unknown"])),
                        "tracks": artist["tracks"]
                    }
                    for idx, artist in enumerate(all_artists)
                    if artist.get("tracks", [])  # Проверяем, что tracks не пустой
                ]
        except (json.JSONDecodeError, IOError) as e:
            print(f"Ошибка при загрузке {ALL_ARTISTS_FILE}: {e}")
            return []
    return artists

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
                async with session.head(track["preview"], headers={'Origin': 'http://127.0.0.1:5000'}) as response:
                    content_type = response.headers.get('Content-Type', '')
                    if response.status == 200 and 'audio' in content_type.lower():
                        valid_tracks.append(track)
                    else:
                        print(f"Превью недоступно: {track['preview']} (статус: {response.status}, Content-Type: {content_type})")
            except Exception as e:
                print(f"Ошибка проверки превью {track['preview']}: {e}")
        else:
            print(f"Трек без превью: {track.get('title', 'Unknown')}")
    return valid_tracks