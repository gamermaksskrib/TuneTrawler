# bot.py
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from core.downloader import search_youtube, download_song
from core.spotify import get_track_info_from_spotify

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(name)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN не задан в переменных окружения")
    raise EnvironmentError("TELEGRAM_BOT_TOKEN not set")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        "🎵 EchoirBot — ваш музыкальный помощник\n\n"
        "Отправьте:\n"
        "• Название трека (например: *Bohemian Rhapsody*)\n"
        "• Ссылку на YouTube\n"
        "• Ссылку на Spotify\n\n"
        "Я найду и отправлю как аудиозапись — слушайте прямо в Telegram!"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    query = update.message.text.strip()
    if len(query) < 2:
        await update.message.reply_text("❌ Введите более полный запрос.")
        return

    # Обработка Spotify-ссылок
    if "spotify.com" in query:
        await update.message.reply_text("🔗 Обрабатываю Spotify-ссылку...")
        search_query = get_track_info_from_spotify(query)
        if not search_query:
            await update.message.reply_text("❌ Не удалось извлечь данные из Spotify. Попробую поискать по названию...")
            search_query = query
    else:
        search_query = query

    await update.message.reply_text("🔍 Ищу на YouTube...")
    results = search_youtube(search_query, max_results=5)

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
        await query.edit_message_text(f"🎧 Скачиваю: {track['title']}...")

        # Скачивание трека
        result = download_song(track['url'])
        if not result:
            await query.message.reply_text("❌ Не удалось скачать трек (возможно, файл слишком большой).")
            return

        file_path = result['file_path']
        
        # Проверка существования файла
        if not os.path.exists(file_path):
            await query.message.reply_text("❌ Ошибка: файл не найден.")
            return
        # Проверка размера файла (Telegram лимит 50 МБ)
        file_size = os.path.getsize(file_path)
        if file_size > 50 * 1024 * 1024:
            await query.message.reply_text("❌ Файл слишком большой (>50 МБ). Попробуйте другой трек.")
            os.remove(file_path)
            return
            # Отправка аудио
        with open(file_path, 'rb') as audio:
            await query.message.reply_audio(
                audio=audio,
                title=result['title'],
                performer=result['artist'],
                duration=result['duration']
            )

        # Удаление временного файла
        os.remove(file_path)

    except Exception as e:
        logger.error(f"Ошибка при скачивании: {e}")
        await query.message.reply_text(
            f"❌ Произошла ошибка при обработке запроса.\n\n"
            f"Попробуйте:\n"
            f"• Начать заново с /start\n"
            f"• Проверить корректность запроса"
        )

def main():
    """Запуск бота"""
    logger.info("✅ Инициализация Telegram-бота...")
    
    try:
        application = Application.builder().token(TOKEN).build()

        # Добавление обработчиков
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(CallbackQueryHandler(handle_download))

        logger.info("🚀 Бот запущен и готов к работе!")
        application.run_polling()
        
    except Exception as e:
        logger.critical(f"❌ Критическая ошибка запуска бота: {e}")
        raise

if name == "main":
    main()
