# bot.py
import os
import logging
import sys
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, CallbackContext

# Загрузка переменных окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Получение токена из переменных окружения
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logger.critical("❌ ОШИБКА: TELEGRAM_BOT_TOKEN не задан в переменных окружения или файле .env")
    sys.exit(1)

# Проверка наличия необходимых переменных для Spotify
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
    logger.warning("⚠️ Предупреждение: Не заданы SPOTIFY_CLIENT_ID или SPOTIFY_CLIENT_SECRET. Функционал Spotify будет недоступен.")

# Папка для загрузок
DOWNLOADS_DIR = "downloads"
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    logger.info(f"Пользователь {update.effective_user.id} запустил бота")
    
    welcome_message = (
        "🎵 EchoirBot — ваш музыкальный помощник\n\n"
        "Отправьте:\n"
        "• Название трека (например: *Bohemian Rhapsody*)\n"
        "• Ссылку на YouTube\n"
        "• Ссылку на Spotify\n\n"
        "Я найду и отправлю как аудиозапись — слушайте прямо в Telegram!"
    )
    await update.message.reply_text(welcome_message)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = update.effective_user.id
    query = update.message.text.strip()
    logger.info(f"Пользователь {user_id} запросил: '{query}'")
    
    # Проверка длины запроса
    if len(query) < 2:
        await update.message.reply_text("❌ Введите более полный запрос (минимум 2 символа).")
        return

    # Обработка Spotify-ссылок
    if "spotify.com" in query:
        await update.message.reply_text("🔗 Обрабатываю Spotify-ссылку...")
        try:
            from core.spotify import get_track_info_from_spotify
            search_query = get_track_info_from_spotify(query)
            if not search_query:
                logger.warning(f"Пользователь {user_id} отправил недействительную Spotify-ссылку: {query}")
                await update.message.reply_text(
                    "❌ Не удалось извлечь данные из Spotify. Попробую поискать по названию..."
                )
                search_query = query
            else:
                logger.info(f"Извлечено из Spotify: '{search_query}'")
        except Exception as e:
            logger.error(f"Ошибка обработки Spotify: {e}")
            await update.message.reply_text(
                "⚠️ Проблема с обработкой Spotify. Использую прямой поиск..."
            )
            search_query = query
    else:
        search_query = query

    await update.message.reply_text("🔍 Ищу на YouTube...")
    
    try:
        from core.downloader import search_youtube
        results = search_youtube(search_query, max_results=5)
        
        # Проверка наличия результатов
        if not results:
            logger.info(f"По запросу '{search_query}' ничего не найдено")
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
        logger.info(f"Найдено {len(results)} результатов для '{search_query}'")
        # Создание кнопок
        keyboard = []
        for i, track in enumerate(results):
            title = track['title'][:40] + "..." if len(track['title']) > 40 else track['title']
            keyboard.append([InlineKeyboardButton(f"🎧 {title}", callback_data=f"track_{i}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Выберите трек:", reply_markup=reply_markup)
        
    except Exception as e:
        logger.exception(f"Ошибка поиска: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при поиске.\n\n"
            "Попробуйте позже или измените запрос."
        )


async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора трека"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} выбрал трек")
    
    try:
        # Извлечение индекса из callback_data
        idx = int(query.data.split("_")[1])
        results = context.user_data.get('results', [])
        
        # Проверка корректности индекса
        if not results or idx >= len(results) or idx < 0:
            logger.warning(f"Пользователь {user_id} выбрал неверный индекс: {idx}")
            await query.edit_message_text("❌ Неверный выбор. Пожалуйста, начните поиск заново.")
            return

        track = results[idx]
        logger.info(f"Скачивание трека: {track['title']} (ID: {track.get('id', 'N/A')})")
        await query.edit_message_text(f"🎧 Скачиваю: {track['title']}...")

        # Скачивание трека
        from core.downloader import download_song
        result = download_song(track['url'], DOWNLOADS_DIR)
        
        if not result:
            logger.warning(f"Не удалось скачать трек: {track['title']}")
            await query.message.reply_text("❌ Не удалось скачать трек (возможно, файл слишком большой).")
            return

        file_path = result['file_path']
        
        # Проверка существования файла
        if not os.path.exists(file_path):
            logger.error(f"Файл не найден: {file_path}")
            await query.message.reply_text("❌ Ошибка: файл не найден.")
            return

        # Проверка размера файла (Telegram лимит 50 МБ)
        file_size = os.path.getsize(file_path)
        if file_size > 50 * 1024 * 1024:
            logger.warning(f"Файл слишком большой: {file_path} ({file_size} байт)")
            await query.message.reply_text("❌ Файл слишком большой (>50 МБ). Попробуйте другой трек.")
            os.remove(file_path)
            return

        # Отправка аудио
        logger.info(f"Отправка аудио пользователю {user_id}: {file_path}")
        with open(file_path, 'rb') as audio:
            await query.message.reply_audio(
                audio=audio,
                title=result['title'],
                performer=result['artist'],
                duration=result['duration']
            )

        # Удаление временного файла
        os.remove(file_path)
        logger.info(f"Временный файл удален: {file_path}")

    except Exception as e:
        logger.exception(f"Ошибка при скачивании для пользователя {user_id}: {e}")
        await query.message.reply_text(
            f"❌ Произошла ошибка при обработке запроса.\n\n"
            f"Попробуйте:\n"
            f"• Начать заново с /start\n"
            f"• Проверить корректность запроса"
        )


def main():
    """Запуск бота"""
    logger.info("========================================")
    logger.info("🚀 Запуск Echoir Telegram Bot")
    logger.info(f"Версия python-telegram-bot: {Application.version}")
    logger.info(f"Токен бота: {TOKEN[:5]}...{TOKEN[-5:]}")
    logger.info(f"Папка для загрузок: {os.path.abspath(DOWNLOADS_DIR)}")
    # Проверка наличия необходимых модулей
    try:
        import yt_dlp
        logger.info(f"yt-dlp версия: {yt_dlp.version.version}")
    except ImportError:
        logger.critical("❌ ОШИБКА: yt-dlp не установлен. Выполните: pip install yt-dlp")
        sys.exit(1)
    
    try:
        import spotipy
        logger.info("spotipy: установлен")
    except ImportError:
        logger.warning("⚠️ spotipy не установлен. Функционал Spotify будет ограничен.")
    
    # Создание и настройка приложения
    try:
        application = Application.builder().token(TOKEN).build()
        logger.info("✅ Приложение Telegram инициализировано")
        
        # Добавление обработчиков
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(CallbackQueryHandler(handle_download))
        
        logger.info("✅ Обработчики добавлены")
        logger.info("🤖 Бот запущен. Ожидание сообщений...")
        
        # Запуск бота
        application.run_polling()
        
    except Exception as e:
        logger.critical(f"❌ Критическая ошибка запуска бота: {e}")
        sys.exit(1)


if name == "main":
    main()
