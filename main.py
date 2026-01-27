import os
import logging
import psycopg2
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
    raise RuntimeError("❌ BOT_TOKEN или DATABASE_URL не заданы")

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
    logger.info("✅ DB initialized")

# ================= KEYBOARDS =================
main_keyboard = ReplyKeyboardMarkup(
    [
        ["🔍 Смотреть анкеты"],
        ["❤️ Совпадения"],
        ["👤 Моя анкета"],
        ["➕ Создать анкету"],
    ],
    resize_keyboard=True,
)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    logger.info(f"/start by {update.effective_user.id}")
    await update.message.reply_text(
        "💖 Добро пожаловать в «СвойЧеловек»",
        reply_markup=main_keyboard,
    )

# ================= CREATE PROFILE =================
async def create_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Create profile by {update.effective_user.id}")
    context.user_data.clear()
    context.user_data["step"] = "gender"
    await update.message.reply_text("Ты парень или девушка?")

async def handle_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("step")
    text = update.message.text

    if step == "gender":
        context.user_data["gender"] = text
        context.user_data["step"] = "age"
        await update.message.reply_text("Сколько тебе лет?")
        return

    if step == "age":
        if not text.isdigit():
            await update.message.reply_text("❗ Введи возраст числом")
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
        await update.message.reply_text("Напиши пару слов о себе")
        return

    if step == "about":
        context.user_data["about"] = text
        context.user_data["step"] = "photo"
        await update.message.reply_text("Пришли одно фото 📸")
        return

# ================= PHOTO =================
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("step") != "photo":
        logger.warning("Фото получено вне сценария анкеты")
        return

    try:
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
                photo_id,
            ))
            conn.commit()
        conn.close()

        caption = (
            f"👤 {data['gender']}, {data['age']}\n"
            f"📍 {data['city']}\n"
            f"🎯 {data['looking']}\n\n"
            f"💬 {data['about']}"
        )

        await update.message.reply_photo(
            photo_id,
            caption=caption,
            reply_markup=main_keyboard,
        )

        context.user_data.clear()
        logger.info("✅ Profile saved")

    except Exception:
        logger.exception("❌ Ошибка сохранения анкеты")
        context.user_data.clear()
        await update.message.reply_text(
            "Произошла ошибка 😢 Попробуй создать анкету заново",
            reply_markup=main_keyboard,
        )

# ================= ROUTERS =================
async def profile_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("step"):
        await handle_profile(update, context)

async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "➕ Создать анкету":
        await create_profile(update, context)
        return

    if text in ("🔍 Смотреть анкеты", "👤 Моя анкета", "❤️ Совпадения"):
        await update.message.reply_text(
            "🔧 Раздел в разработке",
            reply_markup=main_keyboard,
        )
        return

    if not context.user_data.get("step"):
        await update.message.reply_text(
            "Я тебя не понял 🤔 Используй кнопки меню 👇",
            reply_markup=main_keyboard,
        )

# ================= MAIN =================
def main():
    init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, profile_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_router))

    logger.info("🚀 Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
