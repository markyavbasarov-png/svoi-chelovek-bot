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
            last_seen TIMESTAMP
        );
        """)


# ================== КНОПКИ ==================
def menu_start():
    return ReplyKeyboardMarkup(
        [["Моя анкета"]],
        resize_keyboard=True
    )


def menu_after_profile():
    return ReplyKeyboardMarkup(
        [
            ["Моя анкета"],
            ["Поиск людей"]
        ],
        resize_keyboard=True
    )


def back_menu():
    return ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)


# ================== СТАРТ ==================
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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        WELCOME_TEXT,
        reply_markup=menu_start()
    )


# ================== СОЗДАНИЕ АНКЕТЫ ==================
async def start_profile(update, context):
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
        await update.message.reply_text(
            "Как тебя зовут?\nМожно имя или ник — как тебе комфортно.",
            reply_markup=back_menu()
        )

    elif step == "name":
        context.user_data["name"] = text
        context.user_data["step"] = "age"
        await update.message.reply_text(
            "Сколько тебе лет?\nВозраст нужен только для подбора.",
            reply_markup=back_menu()
        )

    elif step == "age":
        if not text.isdigit():
            await update.message.reply_text("Пожалуйста, введи число 🙂")
            return
        context.user_data["age"] = int(text)
        context.user_data["step"] = "city"
        await update.message.reply_text(
            "Откуда ты?\nГород или страна — как удобно.",
            reply_markup=back_menu()
        )

    elif step == "city":
        context.user_data["city"] = text
        context.user_data["step"] = "photo"
        await update.message.reply_text(
            "Хочешь добавить фото?\nС фото проще понять, кто ты.",
            reply_markup=ReplyKeyboardMarkup(
                [["Загрузить фото", "Пропустить"]],
                resize_keyboard=True
            )
        )

    elif step == "looking":
        context.user_data["looking"] = text
        await confirm_profile(update, context)


# ================== ФОТО ==================
async def handle_photo(update, context):
    if context.user_data.get("step") != "photo":
        return

    context.user_data["photo"] = update.message.photo[-1].file_id
    context.user_data["step"] = "looking"

    await update.message.reply_text(
        "Кого ты хочешь найти здесь?\nМожно написать своими словами."
    )

    await update.message.reply_text(
        "Например:\n"
        "Хочу найти друзей\n"
        "Ищу поддержку\n"
        "Хочу отношений\n"
        "Пока просто пообщаться"
    )


# ================== ПОДТВЕРЖДЕНИЕ ==================
async def confirm_profile(update, context):
    d = context.user_data

    text = (
        "Спасибо 🤍\n"
        "Вот как сейчас выглядит твоя анкета:\n\n"
        f"Пол: {d['gender']}\n"
        f"Имя: {d['name']}\n"
        f"Возраст: {d['age']}\n"
        f"Город: {d['city']}\n"
        f"Цель: {d['looking']}\n\n"
        "Всё верно?"
    )

    if d.get("photo"):
        await update.message.reply_photo(
            photo=d["photo"],
            caption=text,
            reply_markup=ReplyKeyboardMarkup(
                [["Подтвердить", "Изменить"]],
                resize_keyboard=True
            )
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=ReplyKeyboardMarkup(
                [["Подтвердить", "Изменить"]],
                resize_keyboard=True
            )
        )


# ================== СОХРАНЕНИЕ ==================
async def save_profile(update, context):
    d = context.user_data
    user_id = update.message.from_user.id

    with conn.cursor() as c:
        c.execute("""
        INSERT INTO users (
            user_id, gender, name, age, city, looking, photo, last_seen
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,NOW())
        ON CONFLICT (user_id) DO UPDATE SET
            gender = EXCLUDED.gender,
            name = EXCLUDED.name,
            age = EXCLUDED.age,
            city = EXCLUDED.city,
            looking = EXCLUDED.looking,
            photo = EXCLUDED.photo,
            last_seen = NOW()
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
        "Готово 🤍 Твоя анкета сохранена.",
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

    elif text == "Загрузить фото":
        if context.user_data.get("step") == "photo":
            await update.message.reply_text(
                "Хорошо 🙂\nОтправь фото одним сообщением 📸"
            )
        else:
            await update.message.reply_text(
                "Сейчас фото не требуется."
            )

    elif text == "Поиск людей":
        await update.message.reply_text(
            "Ты в разделе поиска 🤍\n\n"
            "Здесь можно спокойно смотреть анкеты других людей.\n"
            "Функция поиска скоро будет доступна.",
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

    print("Бот запущен")
    app.run_polling()


if __name__ == "__main__":
    main()
