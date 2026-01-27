import os
import psycopg2
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

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

# ================= PHOTO (ПОКАЗ АНКЕТЫ) =================
async def handle_photo(update, context):
    if context.user_data.get("step") != "photo":
        return

    photo_id = update.message.photo[-1].file_id

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

    await update.message.reply_photo(
        photo_id,
        caption=text,
        reply_markup=main_keyboard
    )

    # ОЧИЩАЕМ ТОЛЬКО ПОСЛЕ ПОКАЗА
    context.user_data.clear()

# ================= FILTER + SHOW =================
def get_random_profile(user_id, min_age, max_age):
    conn = get_connection()
    with conn.cursor() as c:
        c.execute("SELECT city FROM users WHERE user_id=%s", (user_id,))
        city = c.fetchone()
        if not city:
            conn.close()
            return None

        c.execute("""
        SELECT u.user_id, u.username, u.gender, u.age, u.city, u.looking, u.about, u.photo_id
        FROM users u
        WHERE u.user_id != %s
          AND u.city = %s
          AND u.age BETWEEN %s AND %s
          AND NOT EXISTS (
              SELECT 1 FROM likes l
              WHERE l.from_user = %s AND l.to_user = u.user_id
          )
        ORDER BY RANDOM()
        LIMIT 1
        """, (user_id, city[0], min_age, max_age, user_id))

        row = c.fetchone()
    conn.close()
    return row

async def show_profile(update, context):
    if "min_age" not in context.user_data:
        context.user_data["step"] = "filter_min_age"
        await update.message.reply_text("Минимальный возраст?")
        return

    profile = get_random_profile(
        update.effective_user.id,
        context.user_data["min_age"],
        context.user_data["max_age"]
    )

    if not profile:
        await update.message.reply_text("Анкет больше нет 😔", reply_markup=main_keyboard)
        return

    context.user_data["current_profile"] = profile[0]
    _, _, gender, age, city, looking, about, photo_id = profile

    text = f"👤 {gender}, {age}\n📍 {city}\n🎯 {looking}\n\n💬 {about}"

    await update.message.reply_photo(photo_id, caption=text, reply_markup=browse_keyboard)

# ================= MAIN =================
def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_profile))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, show_profile))
    app.run_polling()

if __name__ == "__main__":
    main()
