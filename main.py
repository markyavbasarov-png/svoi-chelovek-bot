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
    logger.info("DB initialized")

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
    context.user_data.clear()
    logger.info(f"/start by {update.effective_user.id}")
    await update.message.reply_text(
        "💖 Добро пожаловать в «СвойЧеловек»",
        reply_markup=main_keyboard
    )

# ================= CREATE PROFILE =================
async def create_profile(update, context):
    logger.info(f"Create profile by {update.effective_user.id}")
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
async def handle_photo(update, context):
    if context.user_data.get("step") != "photo":
        logger.warning("Photo received вне шага анкеты")
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
                data.get("gender"),
                data.get("age"),
                data.get("city"),
                data.get("looking"),
                data.get("about"),
                photo_id
            ))
            conn.commit()
        conn.close()

        text = (
            f"👤 {data.get('gender')}, {data.get('age')}\n"
            f"📍 {data.get('city')}\n"
            f"🎯 {data.get('looking')}\n\n"
            f"💬 {data.get('about')}"
        )

        await update.message.reply_photo(
            photo_id,
            caption=text,
            reply_markup=main_keyboard
        )

        context.user_data.clear()
        logger.info("Profile saved successfully")

    except Exception as e:
        logger.exception("Ошибка при сохранении анкеты")
        await update.message.reply_text(
            "❌ Ошибка при сохранении анкеты. Нажми «Создать анкету» и попробуй снова.",
            reply_markup=main_keyboard
        )
        context.user_data.clear()

# ================= ROUTER =================
async def router(update, context):
    text = update.message.text

    if text == "➕ Создать анкету":
        await create_profile(update, context)
    elif text == "🔍 Смотреть анкеты":
        await update.message.reply_text("🔧 Раздел в разработке", reply_markup=main_keyboard)
    elif text == "👤 Моя анкета":
        await update.message.reply_text("🔧 Раздел в разработке", reply_markup=main_keyboard)
    elif text == "❤️ Совпадения":
        await update.message.reply_text("🔧 Раздел в разработке", reply_markup=main_keyboard)
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
    app.run_polling()

if __name__ == "__main__":
    main()
