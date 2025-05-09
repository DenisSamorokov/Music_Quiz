import random
import json
import time
from utils.deezer import load_artists
import urllib.request
import urllib.error
import logging

# Настройка логирования
logging.basicConfig(filename='game.log', level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def validate_preview_url(preview_url):
    try:
        headers = {'Origin': 'http://127.0.0.1:5000'}
        req = urllib.request.Request(preview_url, headers=headers, method='HEAD')
        with urllib.request.urlopen(req) as response:
            content_type = response.headers.get('Content-Type', '')
            content_length = response.headers.get('Content-Length', 'unknown')
            status = response.status
            logger.debug(f"Проверка preview_url: {preview_url}, Status: {status}, Content-Type: {content_type}, Content-Length: {content_length}")
            if status == 200 and 'audio' in content_type.lower():
                logger.info(f"Валидный preview_url: {preview_url}")
                return True
            logger.warning(f"Недействительный preview_url: {preview_url} (Status: {status}, Content-Type: {content_type})")
            return False
    except urllib.error.HTTPError as e:
        logger.warning(f"HTTP ошибка при проверке preview_url {preview_url}: {e.code} {e.reason}")
        return False
    except Exception as e:
        logger.warning(f"Ошибка проверки preview_url {preview_url}: {str(e)}")
        return False

def fetch_track_with_preview(artist_id, difficulty):
    start_time = time.time()
    url = f"https://api.deezer.com/artist/{artist_id}/top?limit=50"
    logger.debug(f"Запрос топ-треков для artist_id={artist_id}: {url}")
    try:
        with urllib.request.urlopen(url) as response:
            if response.status != 200:
                logger.warning(f"Ошибка при запросе {url}: {response.status}")
                return None
            data = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        logger.warning(f"HTTP ошибка при запросе {url}: {e.code} {e.reason}")
        return None
    except Exception as e:
        logger.warning(f"Исключение при запросе {url}: {e}")
        return None

    tracks = data.get("data", [])
    if not tracks:
        logger.warning(f"Deezer API вернул пустой список треков для artist_id={artist_id}")
        return None

    valid_tracks = []
    for track in tracks:
        if track.get('preview'):
            if validate_preview_url(track["preview"]):
                valid_tracks.append(track)
            else:
                logger.debug(f"Превью недоступно: {track['preview']} для трека {track.get('title', 'Unknown')}")
        else:
            logger.debug(f"Трек без превью: {track.get('title', 'Unknown')} (artist_id={artist_id})")

    if not valid_tracks:
        logger.warning(f"Нет треков с валидным preview для artist_id={artist_id}")
        return None

    sorted_tracks = sorted(valid_tracks, key=lambda x: x["rank"], reverse=True)

    if difficulty == 'easy':
        track = random.choice(sorted_tracks[:5]) if len(sorted_tracks) >= 5 else sorted_tracks[0]
    elif difficulty == 'medium':
        mid_start = min(5, len(sorted_tracks))
        mid_end = min(10, len(sorted_tracks))
        track = random.choice(sorted_tracks[mid_start:mid_end]) if mid_end > mid_start else sorted_tracks[0]
    else:  # hard
        low_start = min(10, len(sorted_tracks))
        track = random.choice(sorted_tracks[low_start:]) if len(sorted_tracks) > low_start else sorted_tracks[0]

    logger.info(f"[{difficulty.upper()}] Выбран трек: {track['title']} с preview {track['preview']}")
    logger.info(f"[{difficulty.upper()}] Время выбора трека для artist_id={artist_id}: {time.time() - start_time:.2f} сек")
    return track

def fetch_track_without_preview(artist_id, difficulty):
    start_time = time.time()
    url = f"https://api.deezer.com/artist/{artist_id}/top?limit=10"
    logger.debug(f"Запрос треков без превью для artist_id={artist_id}: {url}")
    try:
        with urllib.request.urlopen(url) as response:
            if response.status != 200:
                logger.warning(f"Ошибка при запросе {url}: {response.status}")
                return None
            data = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        logger.warning(f"HTTP ошибка при запросе {url}: {e.code} {e.reason}")
        return None
    except Exception as e:
        logger.warning(f"Исключение при запроса {url}: {e}")
        return None

    tracks = data.get("data", [])
    if not tracks:
        logger.warning(f"Deezer API вернул пустой список треков для artist_id={artist_id}")
        return None

    sorted_tracks = sorted(tracks, key=lambda x: x["rank"], reverse=True)

    if difficulty == 'easy':
        track = random.choice(sorted_tracks[:5]) if len(sorted_tracks) >= 5 else sorted_tracks[0]
    elif difficulty == 'medium':
        mid_start = min(5, len(sorted_tracks))
        mid_end = min(10, len(sorted_tracks))
        track = random.choice(sorted_tracks[mid_start:mid_end]) if mid_end > mid_start else sorted_tracks[0]
    else:  # hard
        low_start = min(10, len(sorted_tracks))
        track = random.choice(sorted_tracks[low_start:]) if len(sorted_tracks) > low_start else sorted_tracks[0]

    logger.info(f"[{difficulty.upper()}] Выбран трек (без превью): {track['title']} для artist_id={artist_id}")
    logger.info(f"[{difficulty.upper()}] Время выбора трека для artist_id={artist_id}: {time.time() - start_time:.2f} сек")
    return track

def fetch_multiple_tracks(artists, difficulty):
    tracks = []
    for artist in artists:
        result = fetch_track_without_preview(artist['id'], difficulty)
        if result:
            result['artist'] = {'name': artist['name']}
            result['id'] = f"track_{result['id']}_{artist['id']}"
            tracks.append(result)
        else:
            logger.warning(f"Не удалось загрузить трек для артиста {artist['name']} (id={artist['id']})")
    return tracks

def select_track_and_options(session, difficulty, style='any', country=None):
    start_time = time.time()
    # Инициализация сессии
    session.setdefault('used_track_ids', [])
    session.setdefault('used_artists', {'easy': [], 'medium': [], 'hard': []})
    session.setdefault('last_artist_index', {'easy': 0, 'medium': 0, 'hard': 0})
    session.setdefault('failed_artists', [])

    used_track_ids = set(session['used_track_ids'][-100:])
    used_artists = set(session['used_artists'][difficulty][-100:])
    failed_artists = session['failed_artists'][-100:]
    last_index = session['last_artist_index'][difficulty]

    logger.info(f"[{difficulty.upper()}] Загружаем артистов для жанра: {style}")
    all_artists = load_artists(genre=style)
    if not all_artists:
        logger.warning(f"[{difficulty.upper()}] Нет артистов для жанра {style}, fallback на any")
        all_artists = load_artists(genre="any")
        style = "any"

    logger.info(f"[{difficulty.upper()}] Всего артистов для жанра {style}: {len(all_artists)}")
    if all_artists:
        logger.info(f"[{difficulty.upper()}] Первые 3 артиста: {[a['name'] + ' (id=' + str(a['id']) + ')' for a in all_artists[:3]]}")

    if style.lower() != 'dance':
        filtered_artists = [a for a in all_artists if not str(a['id']).startswith('unknown_')]
        if filtered_artists:
            all_artists = filtered_artists
            logger.info(f"[{difficulty.upper()}] После фильтрации осталось артистов: {len(all_artists)}")
        else:
            logger.warning(f"[{difficulty.upper()}] Нет артистов с корректными id для жанра {style}, используем всех")
    else:
        logger.info(f"[{difficulty.upper()}] Жанр Dance: используем всех артистов без фильтрации unknown_*")

    if not all_artists:
        logger.error(f"[{difficulty.upper()}] Нет доступных артистов после фильтрации")
        return None, []

    random.shuffle(all_artists)
    if difficulty == 'easy':
        artist_pool = all_artists[:100]
    elif difficulty == 'medium':
        artist_pool = all_artists[:1000]
    else:
        artist_pool = all_artists if len(all_artists) <= 100 else all_artists[100:]

    all_possible_artists = load_artists(genre="any") if style != "any" else load_artists(genre=None)
    all_possible_artists = [a for a in all_possible_artists if not str(a['id']).startswith('unknown_')]
    available_other_artists = [a for a in all_possible_artists if a['name'] not in [artist['name'] for artist in artist_pool]]

    available_artists = [artist for artist in artist_pool if artist['name'] not in used_artists]
    if len(available_artists) < 4:
        logger.info(f"[{difficulty.upper()}] Недостаточно доступных артистов: {len(available_artists)}. Сбрасываем сессию.")
        session['used_artists'][difficulty] = []
        session['used_track_ids'] = []
        used_artists = set()
        available_artists = artist_pool

    correct_track = None
    correct_artist = None
    max_attempts_correct = min(10, len(available_artists))
    attempted_artists = []
    for attempt in range(max_attempts_correct):
        if not available_artists:
            break
        correct_artist = random.choice(available_artists)
        attempted_artists.append(correct_artist['name'])
        logger.info(f"[{difficulty.upper()}] Попытка {attempt + 1}: Проверяем артиста {correct_artist['name']} (id={correct_artist['id']})")
        correct_track = fetch_track_with_preview(correct_artist['id'], difficulty)
        if correct_track and correct_track.get('preview'):
            correct_track['artist'] = {'name': correct_artist['name']}
            correct_track['id'] = f"track_{correct_track['id']}_{correct_artist['id']}"
            break
        logger.warning(f"[{difficulty.upper()}] Не удалось найти трек с валидным превью для {correct_artist['name']} (id={correct_artist['id']})")
        failed_artists.append(correct_artist['name'])
        available_artists = [a for a in available_artists if a['name'] != correct_artist['name']]
        correct_track = None
        correct_artist = None

    if not correct_track:
        logger.info(f"[{difficulty.upper()}] Fallback: пробуем артистов из всех жанров")
        all_artists = load_artists(genre="any")
        filtered_artists = [a for a in all_artists if not str(a['id']).startswith('unknown_')]
        if filtered_artists:
            all_artists = filtered_artists
        random.shuffle(all_artists)
        artist_pool = all_artists[:100] if difficulty == 'easy' else all_artists[:1000] if difficulty == 'medium' else all_artists
        available_artists = [artist for artist in artist_pool if artist['name'] not in used_artists]
        for attempt in range(max_attempts_correct):
            if not available_artists:
                break
            correct_artist = random.choice(available_artists)
            attempted_artists.append(correct_artist['name'])
            logger.info(f"[{difficulty.upper()}] Fallback, попытка {attempt + 1}: Проверяем артиста {correct_artist['name']} (id={correct_artist['id']})")
            correct_track = fetch_track_with_preview(correct_artist['id'], difficulty)
            if correct_track and correct_track.get('preview'):
                correct_track['artist'] = {'name': correct_artist['name']}
                correct_track['id'] = f"track_{correct_track['id']}_{correct_artist['id']}"
                break
            logger.warning(f"[{difficulty.upper()}] Не удалось найти трек с валидным превью для {correct_artist['name']} (id={correct_artist['id']}) (fallback)")
            failed_artists.append(correct_artist['name'])
            available_artists = [a for a in available_artists if a['name'] != correct_artist['name']]
            correct_track = None
            correct_artist = None

    if not correct_track or not correct_artist:
        logger.error(f"[{difficulty.upper()}] Не удалось найти артиста с треком после попыток: {attempted_artists}")
        session['used_track_ids'] = []
        session['failed_artists'] = failed_artists
        return None, []

    logger.info(f"[{difficulty.upper()}] Правильный трек: {correct_track['title']} от {correct_artist['name']}, Preview URL: {correct_track['preview']}")

    incorrect_artists = random.sample(available_other_artists, min(3, len(available_other_artists))) if available_other_artists else []
    incorrect_tracks = []
    if incorrect_artists:
        incorrect_tracks = fetch_multiple_tracks(incorrect_artists, difficulty)

    if len(incorrect_tracks) < 3:
        logger.warning(f"[{difficulty.upper()}] Не удалось найти достаточно неправильных артистов: {len(incorrect_tracks)}")
        session['failed_artists'] = failed_artists
        return None, []

    options = [correct_track] + incorrect_tracks[:3]
    random.shuffle(options)

    used_artists.add(correct_artist['name'])
    for track in incorrect_tracks:
        used_artists.add(track['artist']['name'])
    for track in options:
        used_track_ids.add(track['id'])
        logger.info(f"[{difficulty.upper()}] Добавлен трек в used_track_ids: {track['id']} ({track['title']} от {track['artist']['name']})")

    session['used_track_ids'] = list(used_track_ids)[-100:]
    session['used_artists'][difficulty] = list(used_artists)[-100:]
    session['last_artist_index'][difficulty] = last_index
    session['failed_artists'] = failed_artists[-100:]

    logger.info(f"[{difficulty.upper()}] Общее время выбора треков: {time.time() - start_time:.2f} сек")
    return correct_track, options