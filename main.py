from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os

TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет!\n\n"
        "Я бот знакомств для родителей-одиночек ❤️\n\n"
        "Скоро здесь можно будет:\n"
        "• создать анкету\n"
        "• найти близкого по духу человека\n"
        "• общаться безопасно и спокойно\n\n"
        "✨ Мы только начинаем, но ты уже с нами!"
    )

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.run_polling()
