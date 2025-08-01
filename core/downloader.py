# core/downloader.py
import yt_dlp
import os

def search_youtube(query, max_results=5):
    ydl_opts = {
        'quiet': True,
        'format': 'bestaudio/best',
        'noplaylist': True,
        'extract_flat': True,
        'skip_download': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            result = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            if not result or 'entries' not in result:
                return []
            return [
                {
                    'title': e.get('title', 'Unknown'),
                    'url': e.get('webpage_url') or e.get('url', ''),
                    'duration': e.get('duration', 0),
                    'thumbnail': e.get('thumbnail'),
                    'uploader': e.get('uploader', 'Unknown'),
                    'id': e.get('id', '')
                }
                for e in result['entries'] if e.get('webpage_url')
            ]
        except Exception as e:
            print("Ошибка поиска:", e)
            return []

def download_song(url, output_dir="downloads"):
    os.makedirs(output_dir, exist_ok=True)
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{output_dir}/%(id)s.%(ext)s',
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            },
            {
                'key': 'EmbedThumbnail',
            },
        ],
        'embedthumbnail': True,
        'addmetadata': True,
        'writethumbnail': False,
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            mp3_file = f"{output_dir}/{info['id']}.mp3"
            file_size = os.path.getsize(mp3_file)
            if file_size > 50 * 1024 * 1024:  # >50 МБ
                os.remove(mp3_file)
                return None
            return {
                'file_path': mp3_file,
                'title': info.get('title', 'Unknown'),
                'artist': info.get('artist') or info.get('uploader', 'Unknown'),
                'duration': info.get('duration', 0),
            }
    except Exception as e:
        print("Ошибка скачивания:", e)
        return None