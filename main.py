import os
import psycopg2
import logging
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
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# ================= DB =================
def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

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
        c.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            from_user BIGINT,
            to_user BIGINT,
            UNIQUE(from_user, to_user)
        );
        """)
        conn.commit()
    conn.close()

# ================= KEYBOARDS =================
main_keyboard = ReplyKeyboardMarkup(
    [
        ["🔍 Смотреть анкеты"],
        ["❤️ Совпадения"],
        ["👤 Моя анкета"],
        ["➕ Создать анкету"]
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
    logger.info(f"/start from {update.effective_user.id}")
    context.user_data.clear()
    await update.message.reply_text(
        "💖 Добро пожаловать в «СвойЧеловек»",
        reply_markup=main_keyboard
    )

# ================= CREATE PROFILE =================
async def create_profile(update, context):
    logger.info("Start create profile")
    context.user_data.clear()
    context.user_data["step"] = "gender"
    await update.message.reply_text("Ты парень или девушка?")

async def handle_profile(update, context):
    step = context.user_data.get("step")
    text = update.message.text.strip()
    logger.info(f"Profile step={step}, text={text}")

    if step == "gender":
        context.user_data["gender"] = text
        context.user_data["step"] = "age"
        await update.message.reply_text("Возраст?")
        return

    if step == "age":
        if not text.isdigit():
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
        return

# ================= PHOTO =================
async def handle_photo(update, context):
    if context.user_data.get("step") != "photo":
        return

    logger.info("Photo received")

    photo_id = update.message.photo[-1].file_id

    conn = get_connection()
    with conn.cursor() as c:
        c.execute("""
        INSERT INTO users VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
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
            context.user_data["gender"],
            context.user_data["age"],
            context.user_data["city"],
            context.user_data["looking"],
            context.user_data["about"],
            photo_id
        ))
        conn.commit()
    conn.close()

    text = (
        f"👤 {context.user_data['gender']}, {context.user_data['age']}\n"
        f"📍 {context.user_data['city']}\n"
        f"🎯 {context.user_data['looking']}\n\n"
        f"💬 {context.user_data['about']}"
    )

    await update.message.reply_photo(photo_id, caption=text, reply_markup=main_keyboard)
    context.user_data.clear()
    logger
