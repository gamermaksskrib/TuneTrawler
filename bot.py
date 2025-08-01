# bot.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from flask import Flask
import threading
import os

# Импорт модулей
from core.downloader import search_youtube, download_song
from core.spotify import get_track_info_from_spotify

# === Настройки ===
DOWNLOADS_DIR = "downloads"
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Только из переменных окружения

if not TOKEN:
    raise EnvironmentError("❌ ОШИБКА: Не задан TELEGRAM_BOT_TOKEN в переменных окружения")

# Создаём Flask-приложение (для Render)
flask_app = Flask(name)

@flask_app.route('/')
def home():
    return "<h1>Echoir Telegram Bot is running! 🎵</h1>"

# === Обработчики бота ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 EchoirBot — ваш музыкальный помощник\n\n"
        "Отправьте:\n"
        "• Название трека (например: *Bohemian Rhapsody*)\n"
        "• Ссылку на YouTube\n"
        "• Ссылку на Spotify\n\n"
        "Я найду и отправлю как аудиозапись — слушайте прямо в Telegram!"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if len(query) < 2:
        await update.message.reply_text("❌ Введите более полный запрос.")
        return

    # Проверка на Spotify
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

    if not results:
        await update.message.reply_text("❌ Ничего не найдено. Попробуйте другое название.")
        return

    context.user_data['results'] = results

    keyboard = [
        [InlineKeyboardButton(f"🎧 {track['title'][:40]}...", callback_data=f"track_{i}")]
        for i, track in enumerate(results)
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите трек:", reply_markup=reply_markup)

async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        idx = int(query.data.split("_")[1])
        results = context.user_data.get('results', [])
        if idx >= len(results):
            await query.edit_message_text("❌ Неверный выбор.")
            return

        track = results[idx]
        await query.edit_message_text(f"🎧 Скачиваю: {track['title']}...")

        result = download_song(track['url'], DOWNLOADS_DIR)
        if not result:
            await query.message.reply_text("❌ Не удалось скачать трек (возможно, файл слишком большой).")
            return

        file_path = result['file_path']
        if not os.path.exists(file_path):
            await query.message.reply_text("❌ Ошибка: файл не найден.")
            return

        with open(file_path, 'rb') as audio:
            await query.message.reply_audio(
                audio=audio,
                title=result['title'],
                performer=result['artist'],
                duration=result['duration']
            )

        # Удаляем файл после отправки
        os.remove(file_path)

    except Exception as e:
        await query.message.reply_text(f"❌ Ошибка при скачивании: {str(e)}")

# === Запуск бота в потоке ===
def run_bot():
    print("✅ Инициализация Telegram-бота...")
    try:
        application = Application.builder().token(TOKEN).build()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(CallbackQueryHandler(handle_download))
        print("🚀 Бот запущен и готов к работе!")
        application.run_polling()
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")

# === Запуск Flask + Bot ===
if name == "main":
    # Запускаем бота в фоновом потоке
    threading.Thread(target=run_bot, daemon=True).start()
    # Запускаем Flask на порту, который указывает Render
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)
