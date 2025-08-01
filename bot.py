# bot.py
import os
import logging
import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import yt_dlp
from core.spotify import get_track_info_from_spotify

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
DOWNLOADS_DIR = "downloads"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB (лимит Telegram)

# Получение токена из переменных окружения
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logger.critical("❌ ОШИБКА: TELEGRAM_BOT_TOKEN не задан в переменных окружения")
    raise EnvironmentError("TELEGRAM_BOT_TOKEN not set")

def get_yt_dlp_version():
    """Безопасное получение версии yt-dlp"""
    try:
        return yt_dlp.version.__version__
    except (ImportError, AttributeError):
        return "неизвестно"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    welcome_text = (
        "🎵 **EchoirBot** — ваш музыкальный помощник\n\n"
        "Отправьте:\n"
        "• Название трека (например: *Bohemian Rhapsody*)\n"
        "• Ссылку на YouTube\n"
        "• Ссылку на Spotify\n\n"
        "Я найду и отправлю как аудиозапись — слушайте прямо в Telegram!\n\n"
        "Поддерживаемые форматы:\n"
        "• MP3 320kbps (по умолчанию)\n"
        "• FLAC (Lossless)\n"
        "• AAC 320kbps\n\n"
        "⚠️ *Примечание:* В некоторых странах (например, Россия) возможны ограничения.\n"
        "Решение: Используйте VPN для обхода региональных ограничений."
    )
    await update.message.reply_text(welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    query = update.message.text.strip()
    
    # Проверка длины запроса
    if len(query) < 2:
        await update.message.reply_text("❌ Введите более полный запрос (минимум 2 символа).")
        return
    
    logger.info(f"Получен запрос: '{query}'")

    # Обработка Spotify-ссылок
    if "spotify.com" in query:
        await update.message.reply_text("🔗 Обрабатываю Spotify-ссылку...")
        search_query = get_track_info_from_spotify(query)
        if not search_query:
            await update.message.reply_text(
                "❌ Не удалось извлечь данные из Spotify.\n"
                "Попробую поискать по названию..."
            )
            search_query = query
    else:
        search_query = query

    await update.message.reply_text("🔍 Ищу на YouTube...")
    
    # Поиск музыки
    try:
        from core.downloader import search_youtube
        results = search_youtube(search_query, max_results=5)
    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        await update.message.reply_text(
            "❌ Ошибка при поиске музыки.\n"
            "Попробуйте позже или уточнить запрос."
        )
        return

    # Проверка наличия результатов
    if not results:
        await update.message.reply_text(
            "❌ Ничего не найдено.\n\n"
            "Попробуйте:\n"
            "• Уточнить название\n"
            "• Использовать Spotify-ссылку\n"
            "• Проверить интернет-соединение"
        )
        return

    # Сохранение результатов
    context.user_data['results'] = results

    # Создание кнопок
    keyboard = [
        [InlineKeyboardButton(f"🎧 {track['title'][:40]}...", callback_data=f"track_{i}")]
        for i, track in enumerate(results)
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите трек:", reply_markup=reply_markup)

async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора трека"""
    query = update.callback_query
    await query.answer()

    try:
        # Извлечение индекса из callback_data
        idx = int(query.data.split("_")[1])
        results = context.user_data.get('results', [])
        
        # Проверка корректности индекса
        if not results or idx >= len(results):
            await query.edit_message_text("❌ Неверный выбор. Пожалуйста, начните поиск заново.")
            return

        track = results[idx]
        logger.info(f"Выбран трек: {track['title']}")
        await query.edit_message_text(f"🎧 Скачиваю: {track['title']}...")

        # Скачивание трека
        try:
            from core.downloader import download_song
            result = download_song(track['url'])
        except Exception as e:
            logger.error(f"Ошибка при скачивании: {e}")
            await query.message.reply_text(
                "❌ Ошибка при скачивании трека.\n"
                "Попробуйте выбрать другой трек."
            )
            return

        if not result:
            await query.message.reply_text(
                "❌ Не удалось скачать трек.\n"
                "Возможно, файл слишком большой или недоступен."
            )
            return

        file_path = result['file_path']
        
        # Проверка существования файла
        if not os.path.exists(file_path):
            await query.message.reply_text("❌ Ошибка: файл не найден.")
            return

        # Проверка размера файла (Telegram лимит 50 МБ)
        file_size = os.path.getsize(file_path)
        if file_size > MAX_FILE_SIZE:
            os.remove(file_path)
            await query.message.reply_text(
                "❌ Файл слишком большой (>50 МБ).\n"
                "Попробуйте другой трек или качество."
            )
            return

        # Отправка аудио
        try:
            with open(file_path, 'rb') as audio:
                await query.message.reply_audio(
                    audio=audio,
                    title=result['title'][:64],  # Ограничение длины названия
                    performer=result['artist'][:64],  # Ограничение длины исполнителя
                    duration=min(result['duration'], 2147483),  # Макс. длительность в Telegram
                )
            logger.info(f"Трек отправлен: {result['title']}")
        except Exception as e:
            logger.error(f"Ошибка отправки аудио: {e}")
            await query.message.reply_text(
                "❌ Ошибка при отправке аудио.\n"
                "Попробуйте позже."
            )

        # Удаление временного файла
        try:
            os.remove(file_path)
        except Exception as e:
            logger.warning(f"Не удалось удалить временный файл: {e}")

    except (IndexError, ValueError) as e:
        logger.error(f"Некорректные данные: {e}")
        await query.message.reply_text("❌ Неверный формат запроса. Пожалуйста, начните заново.")
    except Exception as e:
        logger.exception(f"Необработанная ошибка: {e}")
        await query.message.reply_text(
            "❌ Произошла критическая ошибка.\n\n"
            "Пожалуйста, начните заново с /start."
        )

def main():
    """Запуск бота"""
    # Создаем папку для загрузок
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    
    # Логируем информацию о запуске
    logger.info("========================================")
    logger.info("🚀 Запуск Echoir Telegram Bot")
    logger.info(f"Версия python-telegram-bot: {telegram.__version__}")
    
    # Безопасное отображение токена (только для логов!)
    token_preview = f"{TOKEN[:4]}...{TOKEN[-4:]}"
    logger.info(f"Токен бота: {token_preview}")
    
    logger.info(f"Папка для загрузок: {os.path.abspath(DOWNLOADS_DIR)}")
    
    # Получение версии yt-dlp
    yt_dlp_version = get_yt_dlp_version()
    logger.info(f"yt-dlp версия: {yt_dlp_version}")
    
    # Проверка FFmpeg
    try:
        import subprocess
        ffmpeg_version = subprocess.check_output(['ffmpeg', '-version'], stderr=subprocess.STDOUT, text=True)
        ffmpeg_version = ffmpeg_version.split('\n')[0]
        logger.info(f"FFmpeg версия: {ffmpeg_version}")
    except Exception as e:
        logger.warning(f"FFmpeg не найден: {e}")
    
    logger.info("========================================")
    
    try:
        # Создаем и настраиваем приложение
        application = Application.builder().token(TOKEN).build()

        # Добавление обработчиков
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(CallbackQueryHandler(handle_download))

        logger.info("✅ Бот запущен и готов к работе!")
        # Запускаем бота
        application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.critical(f"❌ Критическая ошибка запуска бота: {e}")
        raise

if __name__ == "__main__":
    main()
