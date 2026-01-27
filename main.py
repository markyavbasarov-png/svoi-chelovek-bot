import os
import psycopg2
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ================== НАСТРОЙКИ ==================
TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")

conn = psycopg2.connect(DB_URL)
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


# ================== ТЕКСТ СТАРТА ==================
WELCOME_TEXT = (
    "💗 Добро пожаловать в «СвойЧеловек»\n\n"
    "Здесь можно найти не просто знакомство —\n"
    "а друга, подругу, поддержку или любовь.\n\n"
    "Это пространство для тех,\n"
    "кто устал быть «сильным» в одиночку\n"
    "и хочет, чтобы его поняли 🤍\n\n"
    "Здесь не оценивают и не торопят.\n"
    "Здесь принимают — такими, какие вы есть.\n\n"
    "Давай начнём с анкеты ✨"
)


# ================== КНОПКИ ==================
def menu_start():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("Моя анкета")]],
        resize_keyboard=True
    )


def gender_kb():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("Парень"), KeyboardButton("Девушка")]],
        resize_keyboard=True
    )


def confirm_kb():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("Подтвердить"), KeyboardButton("Изменить")]],
        resize_keyboard=True
    )


def menu_after_profile():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("Моя анкета"), KeyboardButton("Поиск людей")]],
        resize_keyboard=True
    )


# ================== /start ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        WELCOME_TEXT,
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


# ================== ТЕКСТОВАЯ ЛОГИКА ==================
async def handle_text(update, context):
    text = update.message.text
    step = context.user_data.get("step")

    if step == "gender" and text in ["Парень", "Девушка"]:
        context.user_data["gender"] = text
        context.user_data["step"] = "name"
        await update.message.reply_text(
            "Как тебя зовут?🤍"
        )

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
        await update.message.reply_text(
            "Откуда ты?🤍"
        )

    elif step == "city":
        context.user_data["city"] = text
        context.user_data["step"] = "photo"
        await update.message.reply_text(
            "Хочешь добавить фото?\n"
            "С фото людям проще понять, кто ты.\n"
            "Но это не обязательно 🤍",
            reply_markup=photo_kb()
        )

    elif step == "photo" and text == "Пропустить":
        context.user_data["photo"] = None
        context.user_data["step"] = "looking"
        await update.message.reply_text(
            "Кого ты хочешь найти?\n\n"
            "— хочу найти друзей\n"
            "— ищу поддержку\n"
            "— хочется общения\n"
            "— открыт(а) к отношениям"
        )

    elif step == "looking":
        context.user_data["looking"] = text
        context.user_data["step"] = "confirm"

        d = context.user_data
        profile_view = (
            "Спасибо 🤍\n"
            "Вот как тебя увидят другие:\n\n"
            f"{d['name']}\n"
            f"{d['looking']}\n\n"
            "Всё верно?"
        )

        await update.message.reply_text(
            profile_view,
            reply_markup=confirm_kb()
        )


# ================== ФОТО ==================
async def handle_photo(update, context):
    if context.user_data.get("step") != "photo":
        return

    photo = update.message.photo[-1]
    context.user_data["photo"] = photo.file_id
    context.user_data["step"] = "looking"

    await update.message.reply_text(
        "Отлично 🤍\n\n"
        "Кого ты хочешь найти?\n\n"
        "— хочу найти друзей\n"
        "— ищу поддержку\n"
        "— хочется общения\n"
        "— открыт(а) к отношениям"
    )


# ================== СОХРАНЕНИЕ ==================
async def save_profile(update, context):
    d = context.user_data
    user_id = update.message.from_user.id

    with conn.cursor() as c:
        c.execute("""
        INSERT INTO users (user_id, gender, name, age, city, looking, photo)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
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
            d.get("gender"),
            d.get("name"),
            d.get("age"),
            d.get("city"),
            d.get("looking"),
            d.get("photo"),
        ))

    context.user_data.clear()

    await update.message.reply_text(
        "Готово 🤍\n"
        "Твоя анкета сохранена.\n\n"
        "Теперь ты можешь:\n"
        "– смотреть анкеты других\n"
        "– находить близких по духу людей\n"
        "– общаться и знакомиться",
        reply_markup=menu_after_profile()
    )


# ================== РОУТЕР ==================
async def router(update, context):
    text = update.message.text

    if text == "Моя анкета":
        await start_profile(update, context)

    elif text == "Подтвердить":
        await save_profile(update, context)

    elif text == "Изменить":
        await start_profile(update, context)

    elif text == "Поиск людей":
        await update.message.reply_text(
            "Ты в разделе поиска 🤍\n\n"
            "Функция скоро будет доступна.",
            reply_markup=menu_after_profile()
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
