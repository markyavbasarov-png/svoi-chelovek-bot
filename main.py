import os
import logging
import psycopg2
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ================= НАСТРОЙКИ =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не задан")

if not DATABASE_URL:
    raise RuntimeError("❌ DATABASE_URL не задан")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)

# ================= DB =================
def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

def init_db():
    conn = get_connection()
    with conn.cursor() as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            gender TEXT,
            age INT,
            city TEXT,
            looking TEXT,
            about TEXT
        );
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            from_user BIGINT,
            to_user BIGINT,
            UNIQUE(from_user, to_user)
        );
        """)
        conn.commit()
    conn.close()
    logger.info("База данных инициализирована")

# ================= KEYBOARDS =================
main_keyboard = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🔍 Смотреть анкеты")],
        [KeyboardButton("👤 Моя анкета")],
        [KeyboardButton("➕ Создать анкету")]
    ],
    resize_keyboard=True
)

browse_keyboard = ReplyKeyboardMarkup(
    [
        [KeyboardButton("❤️ Лайк"), KeyboardButton("➡️ Пропустить")],
        [KeyboardButton("👤 Моя анкета")]
    ],
    resize_keyboard=True
)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "💖 Добро пожаловать в «СвойЧеловек»\n\n"
        "Здесь можно найти близкого по духу человека 🤍",
        reply_markup=main_keyboard
    )

# ================= CREATE PROFILE =================
async def create_profile(update, context):
    context.user_data.clear()
    context.user_data["step"] = "gender"
    await update.message.reply_text("Ты парень или девушка?")

async def handle_profile(update, context):
    step = context.user_data.get("step")
    text = update.message.text.strip()

    if step == "gender":
        context.user_data["gender"] = text
        context.user_data["step"] = "age"
        await update.message.reply_text("Сколько тебе лет?")
        return

    if step == "age":
        if not text.isdigit() or not (16 <= int(text) <= 100):
            await update.message.reply_text("Введите возраст цифрами (16–100)")
            return
        context.user_data["age"] = int(text)
        context.user_data["step"] = "city"
        await update.message.reply_text("Из какого ты города?")
        return

    if step == "city":
        context.user_data["city"] = text
        context.user_data["step"] = "looking"
        await update.message.reply_text("Кого ты ищешь?")
        return

    if step == "looking":
        context.user_data["looking"] = text
        context.user_data["step"] = "about"
        await update.message.reply_text("Напиши немного о себе 🤍")
        return

    if step == "about":
        user_id = update.effective_user.id

        conn = get_connection()
        with conn.cursor() as c:
            c.execute("""
            INSERT INTO users (user_id, gender, age, city, looking, about)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (user_id) DO UPDATE SET
                gender=EXCLUDED.gender,
                age=EXCLUDED.age,
                city=EXCLUDED.city,
                looking=EXCLUDED.looking,
                about=EXCLUDED.about
            """, (
                user_id,
                context.user_data["gender"],
                context.user_data["age"],
                context.user_data["city"],
                context.user_data["looking"],
                text
            ))
            conn.commit()
        conn.close()

        context.user_data.clear()
        await update.message.reply_text(
            "💖 Анкета сохранена!",
            reply_markup=main_keyboard
        )

# ================= SHOW PROFILES =================
def get_random_profile(user_id):
    conn = get_connection()
    with conn.cursor() as c:
        c.execute("SELECT city FROM users WHERE user_id=%s", (user_id,))
        res = c.fetchone()
        if not res:
            conn.close()
            return None

        city = res[0]

        c.execute("""
        SELECT user_id, gender, age, city, looking, about
        FROM users
        WHERE user_id != %s AND city = %s
        ORDER BY RANDOM()
        LIMIT 1
        """, (user_id, city))

        row = c.fetchone()

    conn.close()
    return row

async def show_profile(update, context):
    profile = get_random_profile(update.effective_user.id)

    if not profile:
        await update.message.reply_text(
            "😔 В твоём городе пока нет анкет",
            reply_markup=main_keyboard
        )
        return

    context.user_data["current_profile"] = profile[0]

    _, gender, age, city, looking, about = profile
    await update.message.reply_text(
        f"👤 {gender}, {age}\n📍 {city}\n🎯 {looking}\n\n💬 {about}",
        reply_markup=browse_keyboard
    )

# ================= LIKE =================
async def like_profile(update, context):
    from_user = update.effective_user.id
    to_user = context.user_data.get("current_profile")

    if not to_user:
        await update.message.reply_text("Сначала выбери анкету")
        return

    conn = get_connection()
    with conn.cursor() as c:
        c.execute("""
        INSERT INTO likes (from_user, to_user)
        VALUES (%s,%s)
        ON CONFLICT DO NOTHING
        """, (from_user, to_user))

        c.execute("""
        SELECT 1 FROM likes
        WHERE from_user=%s AND to_user=%s
        """, (to_user, from_user))

        match = c.fetchone()
        conn.commit()
    conn.close()

    if match:
        await update.message.reply_text(
            "💞 У вас взаимная симпатия!",
            reply_markup=main_keyboard
        )

    await show_profile(update, context)

# ================= MY PROFILE =================
async def my_profile(update, context):
    conn = get_connection()
    with conn.cursor() as c:
        c.execute("""
        SELECT gender, age, city, looking, about
        FROM users WHERE user_id=%s
        """, (update.effective_user.id,))
        p = c.fetchone()
    conn.close()

    if not p:
        await update.message.reply_text(
            "Анкета не найдена 😔",
            reply_markup=main_keyboard
        )
        return

    gender, age, city, looking, about = p
    await update.message.reply_text(
        f"👤 {gender}, {age}\n📍 {city}\n🎯 {looking}\n\n💬 {about}",
        reply_markup=main_keyboard
    )

# ================= ROUTER =================
async def router(update, context):
    text = update.message.text

    if text == "➕ Создать анкету":
        await create_profile(update, context)
    elif text == "🔍 Смотреть анкеты":
        await show_profile(update, context)
    elif text == "❤️ Лайк":
        await like_profile(update, context)
    elif text == "➡️ Пропустить":
        await show_profile(update, context)
    elif text == "👤 Моя анкета":
        await my_profile(update, context)
    elif context.user_data.get("step"):
        await handle_profile(update, context)

# ================= MAIN =================
def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, router))
    logger.info("🚀 Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
