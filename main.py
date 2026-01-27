import os
import psycopg2
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ========= НАСТРОЙКИ =========
TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")

conn = psycopg2.connect(DB_URL, sslmode="require")
conn.autocommit = True


# ================== БАЗА ДАННЫХ ==================
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
            last_seen TIMESTAMP DEFAULT NOW()
        );
        """)


# ================== КНОПКИ ==================
def menu_start():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("Создать анкету")]],
        resize_keyboard=True
    )


def menu_after_profile():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("Моя анкета")],
            [KeyboardButton("✏️ Редактировать анкету")],
            [KeyboardButton("Поиск людей")]
        ],
        resize_keyboard=True
    )


def gender_kb():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("Парень"), KeyboardButton("Девушка")]],
        resize_keyboard=True
    )


def photo_kb():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📸 Загрузить фото"), KeyboardButton("Пропустить")]],
        resize_keyboard=True
    )


def confirm_kb():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("Подтвердить"), KeyboardButton("Изменить")]],
        resize_keyboard=True
    )


# ================== /start ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "💗 Добро пожаловать в «СвойЧеловек»\n\nДавай начнём с анкеты ✨",
        reply_markup=menu_start()
    )


# ================== СОЗДАНИЕ АНКЕТЫ ==================
async def start_profile(update, context):
    context.user_data.clear()
    context.user_data["step"] = "gender"
    await update.message.reply_text(
        "Выбери вариант 🤍",
        reply_markup=gender_kb()
    )


# ================== АНКЕТА ==================
async def handle_text(update, context):
    text = update.message.text
    step = context.user_data.get("step")

    if step == "gender" and text in ("Парень", "Девушка"):
        context.user_data["gender"] = text
        context.user_data["step"] = "name"
        await update.message.reply_text("Как тебя зовут? 🤍")

    elif step == "name":
        context.user_data["name"] = text
        context.user_data["step"] = "age"
        await update.message.reply_text("Сколько тебе лет?")

    elif step == "age":
        if not text.isdigit():
            await update.message.reply_text("Напиши возраст цифрами 🙂")
            return
        context.user_data["age"] = int(text)
        context.user_data["step"] = "city"
        await update.message.reply_text("Откуда ты? 🤍")

    elif step == "city":
        context.user_data["city"] = text
        context.user_data["step"] = "photo"
        await update.message.reply_text(
            "Хочешь добавить фото?",
            reply_markup=photo_kb()
        )

    elif step == "photo" and text == "Пропустить":
        context.user_data["photo"] = None
        context.user_data["step"] = "looking"
        await ask_looking(update)

    elif step == "looking":
        context.user_data["looking"] = text
        context.user_data["step"] = "confirm"
        d = context.user_data

        await update.message.reply_text(
            f"👤 {d['name']}, {d['age']} лет\n"
            f"📍 {d['city']}\n"
            f"🎯 {d['looking']}\n\n"
            "Всё верно?",
            reply_markup=confirm_kb()
        )

    elif step == "confirm" and text == "Подтвердить":
        await confirm_profile(update, context)

    elif step == "confirm" and text == "Изменить":
        await start_profile(update, context)


# ================== ФОТО ==================
async def handle_photo(update, context):
    if context.user_data.get("step") != "photo":
        return

    photo = update.message.photo[-1]
    context.user_data["photo"] = photo.file_id
    context.user_data["step"] = "looking"
    await ask_looking(update)


async def ask_looking(update):
    await update.message.reply_text(
        "Кого ты хочешь найти?\n\n"
        "— Ищу друга\n"
        "— Ищу поддержку\n"
        "— Хочется общения\n"
        "— Открыт(а) к отношениям"
    )


# ================== СОХРАНЕНИЕ ==================
async def confirm_profile(update, context):
    user_id = update.effective_user.id
    d = context.user_data

    with conn.cursor() as c:
        c.execute("""
            INSERT INTO users (user_id, gender, name, age, city, looking, photo)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                gender = EXCLUDED.gender,
                name = EXCLUDED.name,
                age = EXCLUDED.age,
                city = EXCLUDED.city,
                looking = EXCLUDED.looking,
                photo = EXCLUDED.photo
        """, (
            user_id,
            d["gender"],
            d["name"],
            d["age"],
            d["city"],
            d["looking"],
            d["photo"]
        ))

    await update.message.reply_text(
        "💖 Анкета сохранена!\n\nВот твоя анкета 👇",
        reply_markup=menu_after_profile()
    )

    context.user_data.clear()
    await show_my_profile(update, context)


# ================== МОЯ АНКЕТА ==================
async def show_my_profile(update, context):
    user_id = update.effective_user.id

    with conn.cursor() as c:
        c.execute("""
            SELECT name, age, city, looking, photo
            FROM users WHERE user_id = %s
        """, (user_id,))
        row = c.fetchone()

    if not row:
        await update.message.reply_text("Анкета не найдена 🤍")
        return

    name, age, city, looking, photo = row
    text = f"👤 {name}, {age}\n📍 {city}\n🎯 {looking}"

    if photo:
        await update.message.reply_photo(photo, caption=text)
    else:
        await update.message.reply_text(text)


# ================== ROUTER ==================
async def router(update, context):
    if not update.message or not update.message.text:
        return

    text = update.message.text

    if text == "Создать анкету":
        await start_profile(update, context)

    elif text == "Моя анкета":
        await show_my_profile(update, context)

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
