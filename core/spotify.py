# core/spotify.py
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os

# Получаем ключи из переменных окружения
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

# Проверяем, заданы ли переменные
if not CLIENT_ID:
    print("❌ ОШИБКА: Не задана переменная окружения SPOTIFY_CLIENT_ID")
if not CLIENT_SECRET:
    print("❌ ОШИБКА: Не задана переменная окружения SPOTIFY_CLIENT_SECRET")

sp = None

# Подключаемся к Spotify API, только если ключи есть
if CLIENT_ID and CLIENT_SECRET:
    try:
        auth_manager = SpotifyClientCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
        sp = spotipy.Spotify(auth_manager=auth_manager)
        print("✅ Spotify: Успешно подключено к API")
    except Exception as e:
        print(f"❌ Ошибка подключения к Spotify API: {e}")
        sp = None
else:
    print("⚠️ Spotify: Клиентские данные отсутствуют — режим поиска по названию")

def get_track_info_from_spotify(url):
    """
    Извлекает название и исполнителя из Spotify-ссылки.
    Поддерживает: track, album, playlist
    Возвращает строку: "Название Исполнитель" для поиска на YouTube.
    """
    if not sp:
        print("⚠️ Spotify: API недоступно — пропускаем обработку")
        return None

    try:
        if "track" in url:
            track = sp.track(url)
            title = track["name"]
            artist = track["artists"][0]["name"]
            print(f"🎵 Spotify Track: '{title}' от '{artist}'")
            return f"{title} {artist}"

        elif "album" in url:
            album = sp.album(url)
            album_name = album["name"]
            artist = album["artists"][0]["name"]
            print(f"💽 Spotify Album: '{album_name}' от '{artist}'")
            return f"{album_name} {artist}"

        elif "playlist" in url:
            playlist = sp.playlist(url)
            first_item = playlist["tracks"]["items"][0]
            if first_item and "track" in first_item:
                track = first_item["track"]
                title = track["name"]
                artist = track["artists"][0]["name"]
                print(f"🎶 Spotify Playlist: первый трек '{title}' от '{artist}'")
                return f"{title} {artist}"

        else:
            print("❌ Spotify: Неподдерживаемый тип ссылки")
            return None

    except Exception as e:
        print(f"❌ Ошибка при обработке Spotify-ссылки: {e}")
        return None
