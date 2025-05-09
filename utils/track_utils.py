import random
import json
import time
from utils.deezer import load_artists
import urllib.request
import urllib.error

def fetch_track_with_preview(artist_id, difficulty):
    start_time = time.time()
    url = f"https://api.deezer.com/artist/{artist_id}/top?limit=50"
    print(f"[{difficulty.upper()}] Запрос топ-треков для artist_id={artist_id}: {url}")
    try:
        with urllib.request.urlopen(url) as response:
            if response.status != 200:
                print(f"[{difficulty.upper()}] Ошибка при запросе {url}: {response.status}")
                return None
            data = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print(f"[{difficulty.upper()}] HTTP ошибка при запросе {url}: {e.code} {e.reason}")
        return None
    except Exception as e:
        print(f"[{difficulty.upper()}] Исключение при запросе {url}: {e}")
        return None

    tracks = data.get("data", [])
    if not tracks:
        print(f"[{difficulty.upper()}] Deezer API вернул пустой список треков для artist_id={artist_id}")
        return None

    valid_tracks = [track for track in tracks if track.get('preview')]
    if not valid_tracks:
        print(f"[{difficulty.upper()}] Нет треков с превью для artist_id={artist_id}")
        return None

    sorted_tracks = sorted(
        valid_tracks,
        key=lambda x: int(x.get("rank", 0)) if x.get("rank") is not None and str(x.get("rank")).isdigit() else 0,
        reverse=True
    )

    if difficulty == 'easy':
        track = random.choice(sorted_tracks[:5]) if len(sorted_tracks) >= 5 else sorted_tracks[0]
    elif difficulty == 'medium':
        mid_start = min(5, len(sorted_tracks))
        mid_end = min(10, len(sorted_tracks))
        track = random.choice(sorted_tracks[mid_start:mid_end]) if mid_end > mid_start else sorted_tracks[0]
    else:  # hard
        low_start = min(10, len(sorted_tracks))
        track = random.choice(sorted_tracks[low_start:]) if len(sorted_tracks) > low_start else sorted_tracks[0]

    print(f"[{difficulty.upper()}] Выбран трек: {track['title']} с превью {track['preview']}")
    print(f"[{difficulty.upper()}] Время выбора трека для artist_id={artist_id}: {time.time() - start_time:.2f} сек")
    return track

def fetch_track_from_file(artist, difficulty):
    tracks = artist.get('tracks', [])
    if not tracks:
        print(f"[{difficulty.upper()}] Нет треков в файле для артиста {artist['name']} (id={artist['id']})")
        return None

    # Обрабатываем строки и словари в tracks
    processed_tracks = []
    for idx, track in enumerate(tracks):
        if isinstance(track, str):
            try:
                # Пробуем разобрать как JSON
                track = json.loads(track)
            except json.JSONDecodeError:
                # Если не JSON, используем строку как title
                track = {
                    "title": track,
                    "id": f"generated_{artist['id']}_{idx}",
                    "rank": 0
                }
                print(f"[{difficulty.upper()}] Создана заглушка для трека: {track['title']} (артист: {artist['name']})")
        if isinstance(track, dict):
            processed_tracks.append(track)
        else:
            print(f"[{difficulty.upper()}] Некорректный формат трека для артиста {artist['name']}: {track}")
            continue

    if not processed_tracks:
        print(f"[{difficulty.upper()}] Нет валидных треков после обработки для артиста {artist['name']} (id={artist['id']})")
        return None

    # Безопасная сортировка
    sorted_tracks = sorted(
        processed_tracks,
        key=lambda x: int(x.get("rank", 0)) if x.get("rank") is not None and str(x.get("rank")).isdigit() else 0,
        reverse=True
    )

    if difficulty == 'easy':
        track = random.choice(sorted_tracks[:5]) if len(sorted_tracks) >= 5 else sorted_tracks[0]
    elif difficulty == 'medium':
        mid_start = min(5, len(sorted_tracks))
        mid_end = min(10, len(sorted_tracks))
        track = random.choice(sorted_tracks[mid_start:mid_end]) if mid_end > mid_start else sorted_tracks[0]
    else:  # hard
        low_start = min(10, len(sorted_tracks))
        track = random.choice(sorted_tracks[low_start:]) if len(sorted_tracks) > low_start else sorted_tracks[0]

    track['artist'] = {'name': artist['name']}
    track['id'] = f"track_{track['id']}_{artist['id']}"
    print(f"[{difficulty.upper()}] Выбран трек из файла: {track['title']} для артиста {artist['name']}")
    return track

def select_track_and_options(session_data, difficulty, style='any', country=None):
    start_time = time.time()
    # Инициализация сессии
    session_data.setdefault('used_track_ids', [])
    session_data.setdefault('used_artists', {'easy': [], 'medium': [], 'hard': []})
    session_data.setdefault('last_artist_index', {'easy': 0, 'medium': 0, 'hard': 0})
    session_data.setdefault('failed_artists', [])

    used_track_ids = set(session_data['used_track_ids'][-100:])
    used_artists = set(session_data['used_artists'][difficulty][-100:])
    failed_artists = session_data['failed_artists'][-100:]

    print(f"[{difficulty.upper()}] Загружаем артистов из artists_with_tracks.json")
    all_artists = load_artists(genre=None)  # Загружаем всех артистов из artists_with_tracks.json
    if not all_artists:
        print(f"[{difficulty.upper()}] Не удалось загрузить артистов из artists_with_tracks.json")
        return None, [], session_data

    print(f"[{difficulty.upper()}] Всего артистов: {len(all_artists)}")

    # Выбор пула артистов в зависимости от уровня сложности
    if difficulty == 'easy':
        artist_pool = all_artists[:100]
    elif difficulty == 'medium':
        artist_pool = all_artists[:1000]
    else:  # hard
        artist_pool = all_artists[100:] if len(all_artists) > 100 else all_artists

    print(f"[{difficulty.upper()}] Размер пула артистов: {len(artist_pool)}")

    if not artist_pool:
        print(f"[{difficulty.upper()}] Пул артистов пуст")
        return None, [], session_data

    # Фильтрация доступных артистов (не использованных ранее)
    available_artists = [artist for artist in artist_pool if artist['name'] not in used_artists]
    if len(available_artists) < 4:
        print(f"[{difficulty.upper()}] Недостаточно доступных артистов: {len(available_artists)}. Сбрасываем использованных артистов.")
        session_data['used_artists'][difficulty] = []
        session_data['used_track_ids'] = []
        used_artists = set()
        available_artists = artist_pool

    if not available_artists:
        print(f"[{difficulty.upper()}] Нет доступных артистов после фильтрации")
        return None, [], session_data

    # Выбор правильного артиста и трека
    correct_track = None
    correct_artist = None
    max_attempts = min(10, len(available_artists))
    attempted_artists = []
    for attempt in range(max_attempts):
        correct_artist = random.choice(available_artists)
        attempted_artists.append(correct_artist['name'])
        print(f"[{difficulty.upper()}] Попытка {attempt + 1}: Проверяем артиста {correct_artist['name']} (id={correct_artist['id']})")
        correct_track = fetch_track_with_preview(correct_artist['id'], difficulty)
        if correct_track and correct_track.get('preview'):
            correct_track['artist'] = {'name': correct_artist['name']}
            correct_track['id'] = f"track_{correct_track['id']}_{correct_artist['id']}"
            break
        print(f"[{difficulty.upper()}] Не удалось найти трек с превью для {correct_artist['name']} (id={correct_artist['id']})")
        failed_artists.append(correct_artist['name'])
        available_artists = [a for a in available_artists if a['name'] != correct_artist['name']]
        correct_track = None
        correct_artist = None

    if not correct_track or not correct_artist:
        print(f"[{difficulty.upper()}] Не удалось найти артиста с треком после попыток: {attempted_artists}")
        session_data['used_track_ids'] = []
        session_data['failed_artists'] = failed_artists[-100:]
        return None, [], session_data

    print(f"[{difficulty.upper()}] Правильный трек: {correct_track['title']} от {correct_artist['name']}, Preview URL: {correct_track['preview']}")

    # Выбор неправильных вариантов ответа из того же пула
    incorrect_artists = []
    incorrect_tracks = []
    max_incorrect_attempts = min(20, len(available_artists) - 1)
    available_for_incorrect = [a for a in available_artists if a['name'] != correct_artist['name']]
    for _ in range(max_incorrect_attempts):
        if len(incorrect_artists) >= 3:
            break
        if not available_for_incorrect:
            print(f"[{difficulty.upper()}] Нет доступных артистов для неправильных вариантов")
            break
        artist = random.choice(available_for_incorrect)
        track = fetch_track_from_file(artist, difficulty)
        if track:
            incorrect_artists.append(artist)
            incorrect_tracks.append(track)
        else:
            print(f"[{difficulty.upper()}] Пропущен артист {artist['name']} из-за отсутствия валидных треков")
        available_for_incorrect = [a for a in available_for_incorrect if a['name'] != artist['name']]

    if len(incorrect_tracks) < 3:
        print(f"[{difficulty.upper()}] Не удалось найти достаточно неправильных треков: {len(incorrect_tracks)}")
        session_data['failed_artists'] = failed_artists[-100:]
        return None, [], session_data

    options = [correct_track] + incorrect_tracks[:3]
    random.shuffle(options)

    used_artists.add(correct_artist['name'])
    for track in incorrect_tracks:
        used_artists.add(track['artist']['name'])
    for track in options:
        used_track_ids.add(track['id'])
        print(f"[{difficulty.upper()}] Добавлен трек в used_track_ids: {track['id']} ({track['title']} от {track['artist']['name']})")

    session_data['used_track_ids'] = list(used_track_ids)[-100:]
    session_data['used_artists'][difficulty] = list(used_artists)[-100:]
    session_data['last_artist_index'][difficulty] = 0  # Не используется, но сохраняем для совместимости
    session_data['failed_artists'] = failed_artists[-100:]

    print(f"[{difficulty.upper()}] Общее время выбора треков: {time.time() - start_time:.2f} сек")
    return correct_track, options, session_data