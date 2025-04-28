import random
import asyncio
import aiohttp
from flask import session
from utils.deezer import load_artists, get_artist_top_tracks


async def fetch_track_with_preview(artist_id, difficulty):
    async with aiohttp.ClientSession() as session:
        tracks = await get_artist_top_tracks(session, artist_id, limit=20)
        if not tracks:
            return None

        sorted_tracks = sorted(tracks, key=lambda x: x["rank"], reverse=True)

        if difficulty == 'easy':
            track = random.choice(sorted_tracks[:5]) if len(sorted_tracks) >= 5 else sorted_tracks[
                0] if sorted_tracks else None
        elif difficulty == 'medium':
            mid_start = min(5, len(sorted_tracks))
            mid_end = min(10, len(sorted_tracks))
            track = random.choice(sorted_tracks[mid_start:mid_end]) if mid_end > mid_start else sorted_tracks[
                0] if sorted_tracks else None
        else:  # hard
            low_start = min(10, len(sorted_tracks))
            track = random.choice(sorted_tracks[low_start:]) if len(sorted_tracks) > low_start else sorted_tracks[
                0] if sorted_tracks else None

        return track


def select_track_and_options(difficulty, style='any', country=None):
    if 'used_track_ids' not in session:
        session['used_track_ids'] = []
    if 'used_artists' not in session or not isinstance(session['used_artists'], dict):
        session['used_artists'] = {'easy': [], 'medium': [], 'hard': []}
    if 'last_artist_index' not in session or not isinstance(session['last_artist_index'], dict):
        session['last_artist_index'] = {'easy': 0, 'medium': 0, 'hard': 0}

    used_track_ids = set(session['used_track_ids'])
    used_artists = set(session['used_artists'][difficulty])
    last_index = session['last_artist_index'][difficulty]

    all_artists = load_artists(genre=style)
    if not all_artists:
        return None, []

    if difficulty == 'easy':
        artist_pool = all_artists[:100]
    elif difficulty == 'medium':
        artist_pool = all_artists[:1000]
    else:  # hard
        artist_pool = all_artists[100:]

    available_artists = [artist for artist in artist_pool if artist['name'] not in used_artists]
    if len(available_artists) < 4:
        print(f"[{difficulty.upper()}] Недостаточно доступных артистов: {len(available_artists)}")
        return None, []

    selected_artists = []
    current_index = last_index
    attempts = 0
    max_attempts = len(available_artists)

    while len(selected_artists) < 4 and attempts < max_attempts:
        if current_index >= len(artist_pool):
            current_index = 0
        artist = artist_pool[current_index]
        if artist['name'] not in used_artists:
            selected_artists.append(artist)
            print(f"Выбран артист: {artist['name']} (жанр: {artist['genre']}, индекс: {current_index})")
        current_index += 1
        attempts += 1

    if len(selected_artists) < 4:
        print(f"Не удалось найти достаточно артистов: найдено {len(selected_artists)} из 4")
        return None, []

    session['last_artist_index'][difficulty] = current_index

    correct_artist = random.choice(selected_artists)
    correct_track = asyncio.run(fetch_track_with_preview(correct_artist['id'], difficulty))

    if not correct_track or "preview" not in correct_track or not correct_track["preview"]:
        print(f"Не удалось найти трек с превью для {correct_artist['name']}")
        return None, []

    correct_track['artist'] = {'name': correct_artist['name']}
    print(
        f"Правильный трек: {correct_track['title']} от {correct_artist['name']}, Preview URL: {correct_track['preview']}")

    tracks = [correct_track]
    other_artists = [artist for artist in selected_artists if artist['name'] != correct_artist['name']]

    fake_track_titles = [
        "Dreamy Nights", "Echoes of Tomorrow", "Silent Waves", "Golden Horizon",
        "Midnight Breeze", "Starlit Journey", "Whispers in the Dark", "Fading Lights"
    ]

    for artist in other_artists:
        fake_track = {
            'id': f"fake_{artist['id']}_{random.randint(1000, 9999)}",
            'title': random.choice(fake_track_titles),
            'artist': {'name': artist['name']},
            'preview': None
        }
        tracks.append(fake_track)
        print(f"Фейковый трек: {fake_track['title']} от {artist['name']}")

    options = tracks
    random.shuffle(options)

    used_track_ids.add(correct_track['id'])
    used_artists.add(correct_artist['name'])
    for track in options:
        used_track_ids.add(track['id'])
        used_artists.add(track['artist']['name'])
        print(f"Добавлен трек в used_track_ids: {track['id']} ({track['title']} от {track['artist']['name']})")

    session['used_track_ids'] = list(used_track_ids)
    session['used_artists'][difficulty] = list(used_artists)

    return correct_track, options