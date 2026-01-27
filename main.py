import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ================= LOGGING =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("svoi-chelovek")

# ================= ENV =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

if not BOT_TOKEN or not DATABASE_URL:
    raise RuntimeError("BOT_TOKEN или DATABASE_URL не заданы")

# ================= DB =================
def get_connection():
    return psycopg2.connect(
        DATABASE_URL,
        sslmode="require",
        cursor_factory=RealDictCursor
    )

def init_db():
    conn = get_connection()
    with conn.cursor() as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            gender TEXT,
            age INT,
            city TEXT,
            looking TEXT,
            about TEXT,
            photo_id TEXT
        );
        """)
        conn.commit()
    conn.close()
    logger.info("DB ready")

# ================= KEYBOARDS =================
main_keyboard = ReplyKeyboardMarkup(
    [
        ["🔍 Смотреть анкеты"],
        ["👤 Моя анкета"],
        ["➕ Создать анкету"],
    ],
    resize_keyboard=True
)

browse_keyboard = ReplyKeyboardMarkup(
    [
        ["❤️ Лайк", "➡️ Пропустить"],
        ["👤 Моя анкета"]
    ],
    resize_keyboard=True
)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "💖 Добро пожаловать в «СвойЧеловек»",
        reply_markup=main_keyboard
    )

# ================= CREATE PROFILE =================
async def create_profile(update, context):
    context.user_data.clear()
    context.user_data["step"] = "gender"
    await update.message.reply_text("Ты парень или девушка?")

async def handle_profile(update, context):
    step = context.user_data.get("step")
    text = update.message.text

    if step == "gender":
        context.user_data["gender"] = text
        context.user_data["step"] = "age"
        await update.message.reply_text("Возраст?")
        return

    if step == "age":
        if not text.isdigit():
            await update.message.reply_text("Возраст числом")
            return
        context.user_data["age"] = int(text)
        context.user_data["step"] = "city"
        await update.message.reply_text("Город?")
        return

    if step == "city":
        context.user_data["city"] = text
        context.user_data["step"] = "looking"
        await update.message.reply_text("Кого ищешь?")
        return

    if step == "looking":
        context.user_data["looking"] = text
        context.user_data["step"] = "about"
        await update.message.reply_text("О себе")
        return

    if step == "about":
        context.user_data["about"] = text
        context.user_data["step"] = "photo"
        await update.message.reply_text("Пришли одно фото 📸")

# ================= PHOTO =================
async def handle_photo(update, context):
    if context.user_data.get("step") != "photo":
        return

    photo_id = update.message.photo[-1].file_id
    data = context.user_data

    conn = get_connection()
    with conn.cursor() as c:
        c.execute("""
        INSERT INTO users (user_id, username, gender, age, city, looking, about, photo_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (user_id) DO UPDATE SET
            username=EXCLUDED.username,
            gender=EXCLUDED.gender,
            age=EXCLUDED.age,
            city=EXCLUDED.city,
            looking=EXCLUDED.looking,
            about=EXCLUDED.about,
            photo_id=EXCLUDED.photo_id
        """, (
            update.effective_user.id,
            update.effective_user.username,
            data["gender"],
            data["age"],
            data["city"],
            data["looking"],
            data["about"],
            photo_id
        ))
        conn.commit()
    conn.close()

    context.user_data.clear()

    # 🚀 СРАЗУ ПЕРЕХОД К ПРОСМОТРУ
    await update.message.reply_text(
        "Анкета готова 💖\nСмотрим анкеты?",
        reply_markup=browse_keyboard
    )

# ================= ROUTER =================
async def router(update, context):
    text = update.message.text

    if text == "➕ Создать анкету":
        await create_profile(update, context)
    elif text == "🔍 Смотреть анкеты":
        await update.message.reply_text("🔜 Скоро здесь будут анкеты", reply_markup=browse_keyboard)
    elif context.user_data.get("step"):
        await handle_profile(update, context)

# ================= MAIN =================
def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, router))

    logger.info("Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
