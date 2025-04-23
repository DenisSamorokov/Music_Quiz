import random
from flask import session
from utils.deezer import fetch_tracks, fetch_option_tracks, fetch_tracks_by_country

def select_track_and_options(difficulty, style='any', country=None):
    """Выбор трека и вариантов ответа."""
    # Если указана страна, используем /chart/{countryId}, иначе /search
    if country:
        # Получаем треки из чартов страны
        tracks = fetch_tracks_by_country(difficulty, country, target_count=10)
    else:
        # Определяем диапазон index для правильного трека
        index_ranges = {
            'easy': (0, 50),
            'medium': (200, 300),
            'hard': (500, 600)
        }
        index_start, index_end = index_ranges.get(difficulty, (500, 600))
        index = random.randint(index_start, index_end)
        # Получаем треки через /search
        tracks = fetch_tracks(difficulty, style=style, index=index, target_count=10)

    if len(tracks) < 4:
        print(f"[{difficulty.upper()}] Не удалось найти достаточно треков для выбора")
        return None, []

    # Получаем списки использованных треков и исполнителей из сессии
    used_track_ids = set(session.get('used_track_ids', []))
    used_artists = set(session.get('used_artists', []))

    # Фильтруем треки, исключая уже использованные
    available_tracks = [
        track for track in tracks
        if track['id'] not in used_track_ids and track['artist']['name'] not in used_artists
    ]

    # Если доступных треков мало, очищаем историю
    if len(available_tracks) < 4:
        print(f"[{difficulty.upper()}] Недостаточно доступных треков, очищаем историю")
        used_track_ids.clear()
        used_artists.clear()
        session['used_track_ids'] = list(used_track_ids)
        session['used_artists'] = list(used_artists)
        available_tracks = tracks

    if not available_tracks:
        print(f"[{difficulty.upper()}] После фильтрации не осталось доступных треков")
        return None, []

    # Сортируем доступные треки по rank и выбираем трек с максимальным rank
    available_tracks.sort(key=lambda x: x.get('rank', 0), reverse=True)
    correct_track = available_tracks[0]
    correct_artist = correct_track['artist']['name']
    print(f"[{difficulty.upper()}] Выбран правильный трек: {correct_track['title']} - {correct_artist} (rank: {correct_track.get('rank', 0)})")

    # Обновляем историю использованных треков и исполнителей
    used_track_ids.add(correct_track['id'])
    used_artists.add(correct_artist)

    # Определяем диапазон index для вариантов ответа
    option_index_ranges = {
        'easy': (200, 300),
        'medium': (500, 600),
        'hard': (800, 900)
    }
    option_index_start, index_end = option_index_ranges.get(difficulty, (800, 900))
    option_index = random.randint(option_index_start, index_end)

    # Получаем треки для вариантов ответа
    option_tracks = fetch_option_tracks(
        used_track_ids,
        used_artists,
        style=style,
        index=option_index,
        target_count=3
    )

    if len(option_tracks) < 3:
        print(f"[{difficulty.upper()}] Не удалось найти достаточно треков для вариантов ответа: {len(option_tracks)} треков")
        return None, []

    # Формируем варианты ответа
    options = []
    selected_artists = {correct_artist}
    allow_same_artist = False

    for track in option_tracks:
        artist = track['artist']['name']
        if len(options) < 3 and (artist not in selected_artists or allow_same_artist):
            options.append({
                'id': track['id'],
                'title': track['title'],
                'artist': artist,
                'preview_url': track['preview']
            })
            selected_artists.add(artist)
            used_track_ids.add(track['id'])
            used_artists.add(artist)

    if len(options) < 3:
        print(f"[{difficulty.upper()}] Не удалось выбрать 3 варианта ответа с разными исполнителями: {len(options)} вариантов, пробуем разрешить совпадение исполнителей")
        allow_same_artist = True
        selected_artists = {correct_artist}
        options = []
        for track in option_tracks:
            artist = track['artist']['name']
            if len(options) < 3:
                options.append({
                    'id': track['id'],
                    'title': track['title'],
                    'artist': artist,
                    'preview_url': track['preview']
                })
                selected_artists.add(artist)
                used_track_ids.add(track['id'])
                used_artists.add(artist)

    if len(options) < 3:
        print(f"[{difficulty.upper()}] Не удалось выбрать 3 варианта ответа даже с совпадением исполнителей: {len(options)} вариантов")
        return None, []

    options.append({
        'id': correct_track['id'],
        'title': correct_track['title'],
        'artist': correct_artist,
        'preview_url': correct_track['preview']
    })

    random.shuffle(options)

    session['used_track_ids'] = list(used_track_ids)
    session['used_artists'] = list(used_artists)

    formatted_correct_track = {
        'id': correct_track['id'],
        'title': correct_track['title'],
        'artist': correct_artist,
        'preview_url': correct_track['preview']
    }

    return formatted_correct_track, options