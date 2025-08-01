# bot.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from flask import Flask
import threading
import os
from core.downloader import search_youtube, download_song
from core.spotify import get_track_info_from_spotify

DOWNLOADS_DIR = "downloads"
TOKEN = "8352917467:AAFcDYlYWWsMwWcMVu_zl9G2gAYZz5ch2ag"

app = Flask(name)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 EchoirBot — ваш музыкальный помощник\n\n"
        "Отправьте:\n"
        "• Название трека\n"
        "• Ссылку на YouTube/Spotify\n\n"
        "Я найду и отправлю как аудио — слушайте прямо в Telegram!"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if len(query) < 2:
        await update.message.reply_text("❌ Введите запрос.")
        return

    if "spotify.com" in query:
        await update.message.reply_text("🔗 Обрабатываю Spotify...")
        search_query = get_track_info_from_spotify(query)
        if not search_query:
            await update.message.reply_text("❌ Не удалось извлечь из Spotify.")
            return
    else:
        search_query = query

    await update.message.reply_text("🔍 Ищу...")
    results = search_youtube(search_query)

    if not results:
        await update.message.reply_text("❌ Ничего не найдено.")
        return

    context.user_data['results'] = results
    keyboard = [
        [InlineKeyboardButton(f"🎧 {t['title'][:40]}...", callback_data=f"track_{i}")]
        for i, t in enumerate(results)
    ]
    await update.message.reply_text("Выберите:", reply_markup=InlineKeyboardMarkup(keyboard))

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
            await query.message.reply_text("❌ Файл слишком большой (>50 МБ).")
            return
        with open(result['file_path'], 'rb') as f:
            await query.message.reply_audio(
                audio=f,
                title=result['title'],
                performer=result['artist'],
                duration=result['duration']
            )
        os.remove(result['file_path'])
    except Exception as e:
        await query.message.reply_text(f"❌ Ошибка: {str(e)}")

def run_bot():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_download))
    application.run_polling()

if name == "main":
    threading.Thread(target=run_bot).start()
    app.run(port=10000)