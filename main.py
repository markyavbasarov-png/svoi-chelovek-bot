import os
import psycopg2
from datetime import timedelta
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ================== CONFIG ==================
TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")

conn = psycopg2.connect(DB_URL)
conn.autocommit = True

# ================== TEXTS ==================
WELCOME_TEXT = (
    "💗 Добро пожаловать в «СвойЧеловек»\n\n"
    "Здесь можно найти не просто знакомство —\n"
    "а друга, подругу, поддержку или любовь.\n\n"
    "Это пространство для тех,\n"
    "кто устал быть сильным в одиночку\n"
    "и хочет, чтобы его поняли 🤍\n\n"
    "Здесь не оценивают и не торопят.\n"
    "Здесь принимают такими, какие вы есть.\n\n"
    "Давай начнём с анкеты ✨"
)

# ================== DB ==================
def init_db():
    with conn.cursor() as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            gender TEXT,
            name TEXT,
            age INT,
            city TEXT,
            looking TEXT,
            photo TEXT,
            last_seen TIMESTAMP
        );
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY,
            from_user BIGINT,
            to_user BIGINT,
            reason TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS blocked_users (
            user_id BIGINT PRIMARY KEY,
            blocked_at TIMESTAMP DEFAULT NOW()
        );
        """)

# ================== KEYBOARDS ==================
def menu_start():
    return ReplyKeyboardMarkup([["📝 Моя анкета"]], resize_keyboard=True)

def menu_after_profile():
    return ReplyKeyboardMarkup(
        [["👤 Моя анкета"], ["🔍 Поиск людей"]],
        resize_keyboard=True
    )

def back():
    return ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)

# ================== UTILS ==================
def update_last_seen(user_id):
    with conn.cursor() as c:
        c.execute(
            "UPDATE users SET last_seen = NOW() WHERE user_id=%s",
            (user_id,)
        )

# ================== START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    with conn.cursor() as c:
        c.execute("SELECT last_seen FROM users WHERE user_id=%s", (user_id,))
        row = c.fetchone()

    if row and row[0]:
        if (update.message.date - row[0]) > timedelta(days=7):
            await update.message.reply_text(
                "Мы снова рядом 🤍\n\n"
                "В поиске появились новые люди.\n"
                "Можно вернуться в своём темпе.",
                reply_markup=menu_after_profile()
            )
            update_last_seen(user_id)
            return

    await update.message.reply_text(WELCOME_TEXT, reply_markup=menu_start())
    update_last_seen(user_id)

# ================== FORM ==================
async def start_form(update, context):
    context.user_data.clear()
    context.user_data["step"] = "gender"
    await update.message.reply_text(
        "Кто ты?",
        reply_markup=ReplyKeyboardMarkup(
            [["Парень", "Девушка"]],
            resize_keyboard=True
        )
    )

async def handle_text(update, context):
    text = update.message.text
    step = context.user_data.get("step")

    if text == "⬅️ Назад":
        await start(update, context)
        return

    if step == "gender":
        context.user_data["gender"] = text
        context.user_data["step"] = "name"
        await update.message.reply_text("Как тебя зовут?")

    elif step == "name":
        context.user_data["name"] = text
        context.user_data["step"] = "age"
        await update.message.reply_text("Сколько тебе лет?")

    elif step == "age":
        if not text.isdigit():
            await update.message.reply_text("Введите возраст числом")
            return
        context.user_data["age"] = int(text)
        context.user_data["step"] = "city"
        await update.message.reply_text("Откуда ты?")

    elif step == "city":
        context.user_data["city"] = text
        context.user_data["step"] = "photo"
        await update.message.reply_text(
            "Хочешь добавить фото?",
            reply_markup=ReplyKeyboardMarkup(
                [["Загрузить фото", "Пропустить"]],
                resize_keyboard=True
            )
        )

    elif step == "looking":
        context.user_data["looking"] = text
        await confirm_profile(update, context)

# ================== PHOTO ==================
async def handle_photo(update, context):
    if context.user_data.get("step") != "photo":
        return

    context.user_data["photo"] = update.message.photo[-1].file_id
    context.user_data["step"] = "looking"
    await update.message.reply_text("Кого ты хочешь найти?")

# ================== CONFIRM ==================
async def confirm_profile(update, context):
    d = context.user_data
    text = (
        "Вот как выглядит твоя анкета:\n\n"
        f"{d['gender']}\n"
        f"{d['name']}, {d['age']}\n"
        f"{d['city']}\n"
        f"{d['looking']}\n\n"
        "Всё верно?"
    )

    if d.get("photo"):
        await update.message.reply_photo(
            photo=d["photo"],
            caption=text,
            reply_markup=ReplyKeyboardMarkup(
                [["✅ Подтвердить", "✏️ Изменить"]],
                resize_keyboard=True
            )
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=ReplyKeyboardMarkup(
                [["✅ Подтвердить", "✏️ Изменить"]],
                resize_keyboard=True
            )
        )

# ================== SAVE ==================
async def save_profile(update, context):
    d = context.user_data
    user_id = update.message.from_user.id

    with conn.cursor() as c:
        c.execute("""
        INSERT INTO users VALUES (%s,%s,%s,%s,%s,%s,NOW())
        ON CONFLICT (user_id) DO UPDATE SET
        gender=EXCLUDED.gender,
        name=EXCLUDED.name,
        age=EXCLUDED.age,
        city=EXCLUDED.city,
        looking=EXCLUDED.looking,
        photo=EXCLUDED.photo,
        last_seen=NOW()
        """, (
            user_id,
            d["gender"],
            d["name"],
            d["age"],
            d["city"],
            d["looking"],
            d.get("photo")
        ))

    context.user_data.clear()
    await update.message.reply_text(
        "Готово 🤍 Анкета сохранена.",
        reply_markup=menu_after_profile()
    )

# ================== MY PROFILE ==================
async def show_my_profile(update, context):
    user_id = update.message.from_user.id
    with conn.cursor() as c:
        c.execute(
            "SELECT gender, name, age, city, looking, photo FROM users WHERE user_id=%s",
            (user_id,)
        )
        row = c.fetchone()

    if not row:
        await update.message.reply_text("Анкета не найдена 🤍")
        return

    gender, name, age, city, looking, photo = row
    text = (
        "Твоя анкета:\n\n"
        f"{gender}\n{name}, {age}\n{city}\n{looking}"
    )

    if photo:
        await update.message.reply_photo(photo=photo, caption=text)
    else:
        await update.message.reply_text(text)

# ================== ROUTER ==================
async def router(update, context):
    text = update.message.text

    if text == "📝 Моя анкета":
        await start_form(update, context)

    elif text == "✅ Подтвердить":
        await save_profile(update, context)

    elif text == "👤 Моя анкета":
        await show_my_profile(update, context)

    elif text == "🔍 Поиск людей":
        await update.message.reply_text(
            "Поиск скоро будет доступен 🤍\n"
            "Мы подбираем людей аккуратно."
        )

    else:
        await handle_text(update, context)

# ================== MAIN ==================
def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, router))

    app.run_polling()

if __name__ == "__main__":
    main()
