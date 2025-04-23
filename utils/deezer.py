import requests
import time

DEEZER_API_URL = "https://api.deezer.com"


def get_genre_id(style):
    """Получение ID жанра по его названию."""
    try:
        response = requests.get(f"{DEEZER_API_URL}/genre")
        response.raise_for_status()
        genres = response.json().get('data', [])
        for genre in genres:
            if genre['name'].lower() == style.lower():
                return genre['id']
        print(f"Жанр {style} не найден")
        return None
    except requests.RequestException as e:
        print(f"Ошибка при загрузке жанров: {e}")
        return None


def fetch_tracks(difficulty, style='any', index=0, target_count=10):
    """Получение треков, упорядоченных по популярности, с учётом сложности."""
    collected_tracks = []

    # Используем /search для всех уровней
    query = 'track:"" '
    if style != 'any':
        genre_id = get_genre_id(style)
        if genre_id:
            query += f'genre_id:{genre_id} '
        else:
            print(f"Жанр {style} не найден, возвращаем пустой список")
            return []
    url = f"{DEEZER_API_URL}/search"
    params = {
        'q': query,
        'order': 'RANKING',
        'limit': 50,
        'index': index
    }
    endpoint_name = "search"

    try:
        print(f"[{difficulty.upper()}] Deezer /{endpoint_name}: index={index}")
        response = requests.get(url, params=params)
        response.raise_for_status()

        if response.status_code == 429:
            print(f"[{difficulty.upper()}] Превышение лимита запросов к Deezer API, ожидание 5 секунд...")
            time.sleep(5)
            return fetch_tracks(difficulty, style, index, target_count)

        data = response.json()
        tracks = data.get('data', [])
        total_tracks = data.get('total', 0)  # Общее количество треков
        print(
            f"[{difficulty.upper()}] Получено {len(tracks)} треков на индексе {index}, всего доступно: {total_tracks}")

        if not tracks:
            print(f"[{difficulty.upper()}] Больше треков не найдено")
            return collected_tracks

        for track in tracks:
            if len(collected_tracks) >= target_count:
                break
            if not track.get('preview'):
                print(f"[{difficulty.upper()}] Трек {track.get('title', 'Unknown')} пропущен: нет preview")
                continue
            if track.get('duration', 0) < 30:
                print(
                    f"[{difficulty.upper()}] Трек {track.get('title', 'Unknown')} пропущен: длительность меньше 30 секунд")
                continue
            collected_tracks.append(track)
            print(
                f"[{difficulty.upper()}] Добавлен трек: {track.get('title')} - {track.get('artist', {}).get('name')} (rank: {track.get('rank', 0)})")

    except requests.RequestException as e:
        print(f"[{difficulty.upper()}] Ошибка Deezer: {e}")

    print(f"[{difficulty.upper()}] Итоговое количество треков: {len(collected_tracks)}")
    return collected_tracks


def fetch_option_tracks(exclude_ids, exclude_artists, style='any', index=0, target_count=3):
    """Получение треков для вариантов ответа с учётом index."""
    query = 'track:"" '
    if style != 'any':
        genre_id = get_genre_id(style)
        if genre_id:
            query += f'genre_id:{genre_id} '

    collected_tracks = []
    current_index = index
    attempts = 0
    max_attempts = 5

    while len(collected_tracks) < target_count and attempts < max_attempts:
        try:
            params = {
                'q': query,
                'order': 'RANKING',
                'limit': 50,
                'index': current_index
            }
            print(f"[OPTIONS] Deezer /search: index={current_index}")
            response = requests.get(f"{DEEZER_API_URL}/search", params=params)
            response.raise_for_status()

            if response.status_code == 429:
                print(f"[OPTIONS] Превышение лимита запросов к Deezer API для вариантов, ожидание 5 секунд...")
                time.sleep(5)
                continue

            data = response.json()
            tracks = data.get('data', [])
            total_tracks = data.get('total', 0)
            print(
                f"[OPTIONS] Получено {len(tracks)} треков для вариантов на индексе {current_index}, всего доступно: {total_tracks}")

            if not tracks:
                current_index = max(0, current_index - 50)
                attempts += 1
                print(
                    f"[OPTIONS] Больше треков для вариантов не найдено, уменьшаем index до {current_index}, попытка {attempts}/{max_attempts}")
                continue

            for track in tracks:
                if len(collected_tracks) >= target_count:
                    break
                if not track.get('preview'):
                    print(f"[OPTIONS] Трек {track.get('title', 'Unknown')} пропущен: нет preview")
                    continue
                if track.get('duration', 0) < 30:
                    print(f"[OPTIONS] Трек {track.get('title', 'Unknown')} пропущен: длительность меньше 30 секунд")
                    continue
                if track['id'] in exclude_ids:
                    print(
                        f"[OPTIONS] Трек {track.get('title', 'Unknown')} пропущен: уже использован (id: {track['id']})")
                    continue
                if track['artist']['name'] in exclude_artists:
                    print(
                        f"[OPTIONS] Трек {track.get('title', 'Unknown')} пропущен: исполнитель уже использован ({track['artist']['name']})")
                    continue
                collected_tracks.append(track)
                print(
                    f"[OPTIONS] Добавлен трек для варианта: {track.get('title')} - {track.get('artist', {}).get('name')} (rank: {track.get('rank', 0)})")

            current_index += 50
            if current_index >= total_tracks:
                current_index = max(0, total_tracks - 50)
                attempts += 1
                print(
                    f"[OPTIONS] Достигнут конец списка (total={total_tracks}), новый index={current_index}, попытка {attempts}/{max_attempts}")

        except requests.RequestException as e:
            print(f"[OPTIONS] Ошибка Deezer: {e}")
            break

    print(f"[OPTIONS] Итоговое количество треков для вариантов: {len(collected_tracks)}")
    return collected_tracks