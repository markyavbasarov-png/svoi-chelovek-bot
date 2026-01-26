import os
import sqlite3
from datetime import date
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
    age INTEGER,
    city TEXT,
    gender_seek TEXT,
    photo TEXT,
    username TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS likes (
    from_user INTEGER,
    to_user INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS blocks (
    blocker INTEGER,
    blocked INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS reports (
    from_user INTEGER,
    reported_user INTEGER,
    reason TEXT
)
""")

conn.commit()

# ---------- ЛИМИТ ЛАЙКОВ ----------
LIKE_LIMIT = 50
likes_counter = {}

def can_like(user_id):
    today = date.today().isoformat()
    data = likes_counter.get(user_id)

    if not data or data["date"] != today:
        likes_counter[user_id] = {"date": today, "count": 0}

    if likes_counter[user_id]["count"] >= LIKE_LIMIT:
        return False

    likes_counter[user_id]["count"] += 1
    return True

# ---------- КНОПКИ ----------
def main_menu():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📝 Создать анкету")],
            [KeyboardButton("👤 Моя анкета")],
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

def like_menu():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("❤️ Лайк"), KeyboardButton("👎 Дальше")],
            [KeyboardButton("🚫 Заблокировать"), KeyboardButton("⚠️ Пожаловаться")],
            [KeyboardButton("⬅️ В меню")]
        ],
        resize_keyboard=True
    )

# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет!\n\n"
        "Знакомства для родителей-одиночек ❤️\n"
        "Без спешки. Без давления.\n\n"
        "Выбери действие 👇",
        reply_markup=main_menu()
    )

# ---------- ТЕКСТ ----------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id

    # --- меню ---
    if text == "📝 Создать анкету":
        context.user_data.clear()
        context.user_data["step"] = "name"
        await update.message.reply_text("Как тебя зовут?")
        return

    if text == "👀 Смотреть анкеты":
        await show_next_profile(update, context)
        return

    if text == "⬅️ В меню":
        await update.message.reply_text("Главное меню", reply_markup=main_menu())
        return

    if text == "ℹ️ О боте":
        await update.message.reply_text(
            "❤️ Место для спокойных знакомств\n"
            "для родителей-одиночек.\n\n"
            "Без давления и спешки."
        )
        return

    # --- моя анкета ---
    if text == "👤 Моя анкета":
        cursor.execute(
            "SELECT name, age, city, photo FROM users WHERE user_id=?",
            (user_id,)
        )
        profile = cursor.fetchone()

        if not profile:
            await update.message.reply_text(
                "У тебя ещё нет анкеты 🙌",
                reply_markup=main_menu()
            )
            return

        await update.message.reply_photo(
            photo=profile[3],
            caption=
            f"👤 {profile[0]}\n"
            f"🎂 {profile[1]} лет\n"
            f"📍 {profile[2]}\n\n"
            "❌ Напиши «Удалить», чтобы удалить анкету",
            reply_markup=main_menu()
        )
        return

    if text == "Удалить":
        cursor.execute("DELETE FROM users WHERE user_id=?", (user_id,))
        cursor.execute("DELETE FROM likes WHERE from_user=? OR to_user=?", (user_id, user_id))
        cursor.execute("DELETE FROM blocks WHERE blocker=? OR blocked=?", (user_id, user_id))
        conn.commit()

        await update.message.reply_text(
            "❌ Анкета удалена",
            reply_markup=main_menu()
        )
        return

    # --- лайки ---
    if text == "❤️ Лайк":
        if not can_like(user_id):
            await update.message.reply_text(
                "🚫 Лимит лайков на сегодня исчерпан",
                reply_markup=main_menu()
            )
            return

        target = context.user_data.get("current_profile")
        if not target:
            await show_next_profile(update, context)
            return

        cursor.execute("INSERT INTO likes VALUES (?,?)", (user_id, target))
        conn.commit()

        cursor.execute(
            "SELECT 1 FROM likes WHERE from_user=? AND to_user=?",
            (target, user_id)
        )
        if cursor.fetchone():
            cursor.execute(
                "SELECT name, age, city, username FROM users WHERE user_id=?",
                (target,)
            )
            other = cursor.fetchone()

            link = (
                f"https://t.me/{other[3]}"
                if other[3] else
                "У пользователя скрыт username"
            )

            await update.message.reply_text(
                f"💖 Взаимная симпатия!\n\n"
                f"{other[0]}, {other[1]}\n"
                f"{other[2]}\n\n"
                f"👉 {link}",
                reply_markup=main_menu()
            )
            return

        await show_next_profile(update, context)
        return

    if text == "👎 Дальше":
        await show_next_profile(update, context)
        return

    if text == "🚫 Заблокировать":
        target = context.user_data.get("current_profile")
        if target:
            cursor.execute("INSERT INTO blocks VALUES (?,?)", (user_id, target))
            conn.commit()

        await update.message.reply_text(
            "🚫 Пользователь заблокирован",
            reply_markup=main_menu()
        )
        return

    if text == "⚠️ Пожаловаться":
        context.user_data["report"] = True
        await update.message.reply_text("Опиши причину жалобы")
        return

    if context.user_data.get("report"):
        target = context.user_data.get("current_profile")
        if target:
            cursor.execute(
                "INSERT INTO reports VALUES (?,?,?)",
                (user_id, target, text)
            )
            conn.commit()

        context.user_data.pop("report", None)
        await update.message.reply_text(
            "⚠️ Жалоба отправлена",
            reply_markup=main_menu()
        )
        return

    # --- анкета ---
    step = context.user_data.get("step")

    if step == "name":
        context.user_data["name"] = text
        context.user_data["step"] = "age"
        await update.message.reply_text("Сколько тебе лет?")
        return

    if step == "age":
        context.user_data["age"] = int(text)
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
        context.user_data["gender_seek"] = text
        context.user_data["step"] = "photo"
        await update.message.reply_text("Пришли фото 📸")
        return

# ---------- ФОТО ----------
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("step") != "photo":
        return

    user_id = update.message.from_user.id
    photo_id = update.message.photo[-1].file_id
    data = context.user_data

    cursor.execute(
        "REPLACE INTO users VALUES (?,?,?,?,?,?)",
        (
            user_id,
            data["name"],
            data["age"],
            data["city"],
            data["gender_seek"],
            photo_id,
            update.message.from_user.username
        )
    )
    conn.commit()

    context.user_data.clear()

    await update.message.reply_text(
        "✅ Анкета создана!",
        reply_markup=main_menu()
    )

# ---------- ПОКАЗ АНКЕТ ----------
async def show_next_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    cursor.execute("""
    SELECT user_id, name, age, city, photo FROM users
    WHERE user_id != ?
    AND user_id NOT IN (
        SELECT blocked FROM blocks WHERE blocker = ?
    )
    AND gender_seek = (
        SELECT
            CASE gender_seek
                WHEN '👨 Парня' THEN '👩 Девушку'
                WHEN '👩 Девушку' THEN '👨 Парня'
                WHEN '🤝 Друга' THEN '🤝 Друга'
                WHEN '👭 Подругу' THEN '👭 Подругу'
            END
        FROM users WHERE user_id = ?
    )
    """, (user_id, user_id, user_id))

    profiles = cursor.fetchall()

    if not profiles:
        await update.message.reply_text(
            "Анкеты закончились 😔",
            reply_markup=main_menu()
        )
        return

    p = profiles[0]
    context.user_data["current_profile"] = p[0]

    await update.message.reply_photo(
        photo=p[4],
        caption=f"{p[1]}, {p[2]}\n{p[3]}",
        reply_markup=like_menu()
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
