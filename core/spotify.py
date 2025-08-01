# core/spotify.py
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os

# Замени на свои данные
CLIENT_ID = os.getenv("1d294952213a4564ac572f03ff08f916")
CLIENT_SECRET = os.getenv("3dd01c6a9c1146fc908865cd9caa77aa")
if not CLIENT_ID or not CLIENT_SECRET:
    print("Не заданы SPOTIFY_CLIENT_ID или SPOTIFY_CLIENT_SECRET")
    sp=None
else:
try:
    auth_manager = SpotifyClientCredentials(client_id="1d294952213a4564ac572f03ff08f916", client_secret="3dd01c6a9c1146fc908865cd9caa77aa")
    sp = spotipy.Spotify(auth_manager=auth_manager)
except Exception as e:
    print("Spotify API не доступен:", e)
    sp = None

def get_track_info_from_spotify(url):
    if not sp:
        return None
    try:
        if "track" in url:
            track = sp.track(url)
            return f"{track['name']} {track['artists'][0]['name']}"
        elif "album" in url:
            album = sp.album(url)
            return f"{album['name']} {album['artists'][0]['name']}"
        elif "playlist" in url:
            playlist = sp.playlist(url)
            first = playlist['tracks']['items'][0]['track']
            return f"{first['name']} {first['artists'][0]['name']}"
        return None
    except Exception as e:
        print("Ошибка Spotify:", e)
        return None
