import os
import sqlite3
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

TOKEN = os.getenv("BOT_TOKEN")

# ---------- БАЗА ----------
conn = sqlite3.connect("dating.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    age TEXT,
    city TEXT,
    seek TEXT,
    photo TEXT,
    username TEXT
)
""")
conn.commit()

# ---------- КНОПКИ ----------
def main_menu():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📝 Создать анкету")],
            [KeyboardButton("👀 Смотреть анкеты")],
            [KeyboardButton("ℹ️ О боте")]
        ],
        resize_keyboard=True
    )

def seek_menu():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("👨 Парня"), KeyboardButton("👩 Девушку")],
            [KeyboardButton("🤝 Друга"), KeyboardButton("👭 Подругу")]
        ],
        resize_keyboard=True
    )

# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "👋 Привет!\n\n"
        "Здесь можно познакомиться спокойно ❤️\n\n"
        "Выбери действие 👇",
        reply_markup=main_menu()
    )

# ---------- ТЕКСТ ----------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    step = context.user_data.get("step")

    # --- меню ---
    if text == "📝 Создать анкету":
        context.user_data.clear()
        context.user_data["step"] = "name"
        await update.message.reply_text("Как тебя зовут?")
        return

    if text == "ℹ️ О боте":
        await update.message.reply_text(
            "❤️ Знакомства без спешки\n"
            "для родителей-одиночек"
        )
        return

    # --- анкета ---
    if step == "name":
        context.user_data["name"] = text
        context.user_data["step"] = "age"
        await update.message.reply_text("Сколько тебе лет?")
        return

    if step == "age":
        context.user_data["age"] = text
        context.user_data["step"] = "city"
        await update.message.reply_text("Из какого ты города?")
        return

    if step == "city":
        context.user_data["city"] = text
        context.user_data["step"] = "seek"
        await update.message.reply_text(
            "Кого ты ищешь?",
            reply_markup=seek_menu()
        )
        return

    if step == "seek":
        context.user_data["seek"] = text
        context.user_data["step"] = "photo"
        await update.message.reply_text("📸 Пришли своё фото")
        return

# ---------- ФОТО ----------
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("step") != "photo":
        return

    data = context.user_data
    user = update.message.from_user

    cursor.execute(
        "REPLACE INTO users VALUES (?,?,?,?,?,?,?)",
        (
            user.id,
            data["name"],
            data["age"],
            data["city"],
            data["seek"],
            update.message.photo[-1].file_id,
            user.username
        )
    )
    conn.commit()

    context.user_data.clear()

    await update.message.reply_text(
        "✅ Анкета создана!",
        reply_markup=main_menu()
    )

# ---------- ПРОСМОТР ----------
async def show_profiles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT name, age, city, photo FROM users")
    profiles = cursor.fetchall()

    if not profiles:
        await update.message.reply_text(
            "Пока нет анкет 😔",
            reply_markup=main_menu()
        )
        return

    p = profiles[0]
    await update.message.reply_photo(
        photo=p[3],
        caption=f"👤 {p[0]}\n🎂 {p[1]}\n📍 {p[2]}",
        reply_markup=main_menu()
    )

# ---------- ЗАПУСК ----------
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__":
    main()
