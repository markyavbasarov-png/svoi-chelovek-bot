import logging
import os
import sqlite3

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InputMediaPhoto,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)

# ====== СОСТОЯНИЯ ======
TARGET, PHOTO, BIO, VIEW = range(4)

# ====== БАЗА ======
conn = sqlite3.connect("profiles.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS profiles (
    user_id INTEGER PRIMARY KEY,
    target TEXT,
    photo TEXT,
    bio TEXT
)
""")
conn.commit()


# ====== КЛАВИАТУРЫ ======
def back_keyboard():
    return ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)

def target_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["👩 Подругу", "🤝 Друга"],
            ["👨 Парня", "👩‍❤️‍👨 Девушку"],
            ["⬅️ Назад"],
        ],
        resize_keyboard=True,
    )

def main_menu():
    return ReplyKeyboardMarkup(
        [["👀 Смотреть анкеты"]], resize_keyboard=True
    )


# ====== /start ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет 💫\nВ кого ты ищешь?",
        reply_markup=target_keyboard(),
    )
    return TARGET


# ====== ЦЕЛЬ ======
async def get_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        return await start(update, context)

    context.user_data["target"] = update.message.text

    await update.message.reply_text(
        "📸 Отправь своё фото",
        reply_markup=back_keyboard(),
    )
    return PHOTO


# ====== ФОТО ======
async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        await update.message.reply_text(
            "В кого ты ищешь?",
            reply_markup=target_keyboard(),
        )
        return TARGET

    photo_id = update.message.photo[-1].file_id
    context.user_data["photo"] = photo_id

    await update.message.reply_text(
        "✍️ Расскажи о себе",
        reply_markup=back_keyboard(),
    )
    return BIO


# ====== О СЕБЕ ======
async def get_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        await update.message.reply_text(
            "📸 Отправь своё фото",
            reply_markup=back_keyboard(),
        )
        return PHOTO

    bio = update.message.text
    if len(bio) < 10:
        await update.message.reply_text("Напиши чуть подробнее 🙂")
        return BIO

    user_id = update.message.from_user.id

    cursor.execute(
        "REPLACE INTO profiles (user_id, target, photo, bio) VALUES (?, ?, ?, ?)",
        (
            user_id,
            context.user_data["target"],
            context.user_data["photo"],
            bio,
        ),
    )
    conn.commit()

    await update.message.reply_text(
        "✅ Анкета сохранена!",
        reply_markup=main_menu(),
    )
    return VIEW


# ====== ПРОСМОТР АНКЕТ ======
async def view_profiles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    cursor.execute(
        "SELECT photo, bio FROM profiles WHERE user_id != ? LIMIT 50",
        (user_id,),
    )
    profiles = cursor.fetchall()

    if not profiles:
        await update.message.reply_text("Анкет пока нет 😔")
        return VIEW

    for photo, bio in profiles:
        await update.message.reply_photo(
            photo=photo,
            caption=bio,
        )

    return VIEW


def main():
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN не задан")

    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            TARGET: [MessageHandler(filters.TEXT, get_target)],
            PHOTO: [
                MessageHandler(filters.PHOTO, get_photo),
                MessageHandler(filters.TEXT, get_photo),
            ],
            BIO: [MessageHandler(filters.TEXT, get_bio)],
            VIEW: [MessageHandler(filters.TEXT, view_profiles)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conv)

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
