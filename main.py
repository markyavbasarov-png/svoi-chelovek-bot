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
logger = logging.getLogger(__name__)

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
        c.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            from_user BIGINT,
            to_user BIGINT,
            UNIQUE(from_user, to_user)
        );
        """)
        conn.commit()
    conn.close()
    logger.info("DB initialized")

# ================= KEYBOARDS =================
main_keyboard = ReplyKeyboardMarkup(
    [
        ["🔍 Смотреть анкеты"],
        ["❤️ Совпадения"],
        ["👤 Моя анкета"],
        ["➕ Создать анкету"],
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
            await update.message.reply_text("Введите число")
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
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("step") != "photo":
        return

    try:
        # PHOTO или DOCUMENT
        if update.message.photo:
            photo_id = update.message.photo[-1].file_id
        elif update.message.document and update.message.document.mime_type.startswith("image/"):
            photo_id = update.message.document.file_id
        else:
            await update.message.reply_text("Пожалуйста, пришли изображение")
            return

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

        text = (
            f"👤 {data['gender']}, {data['age']}\n"
            f"📍 {data['city']}\n"
            f"🎯 {data['looking']}\n\n"
            f"💬 {data['about']}"
        )

        await update.message.reply_photo(
            photo_id,
            caption=text,
            reply_markup=main_keyboard
        )

        context.user_data.clear()
        logger.info("Profile saved successfully")

    except Exception:
        logger.exception("Ошибка при сохранении анкеты")
        await update.message.reply_text(
            "❌ Ошибка при сохранении анкеты. Попробуй ещё раз.",
            reply_markup=main_keyboard
        )
        context.user_data.clear()

# ================= MY PROFILE =================
async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_connection()
    with conn.cursor() as c:
        c.execute("SELECT * FROM users WHERE user_id=%s", (update.effective_user.id,))
        user = c.fetchone()
    conn.close()

    if not user:
        await update.message.reply_text(
            "У тебя ещё нет анкеты",
            reply_markup=main_keyboard
        )
        return

    text = (
        f"👤 {user['gender']}, {user['age']}\n"
        f"📍 {user['city']}\n"
        f"🎯 {user['looking']}\n\n"
        f"💬 {user['about']}"
    )

    await update.message.reply_photo(
        user["photo_id"],
        caption=text,
        reply_markup=main_keyboard
    )

# ================= ROUTER =================
async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "➕ Создать анкету":
        await create_profile(update, context)
    elif text == "👤 Моя анкета":
        await my_profile(update, context)
    elif text in ("🔍 Смотреть анкеты", "❤️ Совпадения"):
        await update.message.reply_text("🔧 В разработке", reply_markup=main_keyboard)
    elif context.user_data.get("step"):
        await handle_profile(update, context)

# ================= MAIN =================
def main():
    init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, router))

    logger.info("Bot started")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
