import json
from pathlib import Path
import urllib.request
import urllib.error
import logging

# Настройка логирования
logging.basicConfig(filename='game.log', level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

GENRES_DIR = Path("genres")
ALL_ARTISTS_FILE = Path("artists_with_tracks.json")

def load_artists(genre=None):
    artists = []
    if genre and genre != "any":
        # Загружаем артистов из файла жанра
        file_path = GENRES_DIR / f"{genre}.json"
        if not file_path.exists():
            logger.error(f"Файл для жанра {genre} не найден: {file_path}")
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
            logger.info(f"Загружено {len(artists)} артистов для жанра {genre}")
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Ошибка при загрузке {file_path}: {e}")
            return []
    else:
        # Загружаем всех артистов из artists_with_tracks.json
        if not ALL_ARTISTS_FILE.exists():
            logger.error(f"Файл {ALL_ARTISTS_FILE} не найден")
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
            logger.info(f"Загружено {len(artists)} артистов для жанра any")
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Ошибка при загрузке {ALL_ARTISTS_FILE}: {e}")
            return []
    return artists

def fetch(url):
    try:
        with urllib.request.urlopen(url) as response:
            if response.status != 200:
                logger.warning(f"Ошибка при запросе {url}: {response.status}")
                return None
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        logger.warning(f"HTTP ошибка при запросе {url}: {e.code} {e.reason}")
        return None
    except Exception as e:
        logger.warning(f"Исключение при запросе {url}: {e}")
        return None

def get_artist_top_tracks(artist_id, limit=20):
    url = f"https://api.deezer.com/artist/{artist_id}/top?limit={limit}"
    logger.debug(f"Запрос топ-треков для artist_id={artist_id}: {url}")
    data = fetch(url)
    if not data:
        return []
    tracks = data.get("data", [])
    valid_tracks = []
    for track in tracks:
        if "preview" in track and track["preview"]:
            try:
                headers = {'Origin': 'http://127.0.0.1:5000'}
                req = urllib.request.Request(track["preview"], headers=headers, method='HEAD')
                with urllib.request.urlopen(req) as response:
                    content_type = response.headers.get('Content-Type', '')
                    if response.status == 200 and 'audio' in content_type.lower():
                        valid_tracks.append(track)
                        logger.debug(f"Валидное превью: {track['preview']} для трека {track.get('title', 'Unknown')}")
                    else:
                        logger.debug(f"Превью недоступно: {track['preview']} (Status: {response.status}, Content-Type: {content_type})")
            except urllib.error.HTTPError as e:
                logger.debug(f"HTTP ошибка проверки превью {track['preview']}: {e.code} {e.reason}")
            except Exception as e:
                logger.debug(f"Ошибка проверки превью {track['preview']}: {e}")
        else:
            logger.debug(f"Трек без превью: {track.get('title', 'Unknown')} (artist_id={artist_id})")
    logger.info(f"Найдено {len(valid_tracks)} валидных треков для artist_id={artist_id}")
    return valid_tracks