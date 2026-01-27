import logging
import sqlite3
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ================== НАСТРОЙКИ ==================
TOKEN = "YOUR_BOT_TOKEN_HERE"
DB_NAME = "profiles.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

# ================== БАЗА ДАННЫХ ==================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            user_id INTEGER PRIMARY KEY,
            photo_id TEXT
        )
    """)
    conn.commit()
    conn.close()

# ================== КЛАВИАТУРА ==================
main_keyboard = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🔍 Смотреть анкеты")],
        [KeyboardButton("❤️ Совпадения")],
        [KeyboardButton("👤 Моя анкета")],
        [KeyboardButton("➕ Создать анкету")]
    ],
    resize_keyboard=True
)

# ================== ХЕНДЛЕРЫ ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💖 Добро пожаловать в «СвойЧеловек»!\n\n"
        "Нажми «Создать анкету», чтобы начать 👇",
        reply_markup=main_keyboard
    )

async def create_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "📸 Пришли одно фото"
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id

        if not update.message.photo:
            await update.message.reply_text("❌ Фото не получено. Попробуй ещё раз.")
            return

        photo_id = update.message.photo[-1].file_id

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()

        c.execute("""
            INSERT INTO profiles (user_id, photo_id)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET photo_id=excluded.photo_id
        """, (user_id, photo_id))

        conn.commit()
        conn.close()

        await update.message.reply_text(
            "✅ Анкета сохранена!",
            reply_markup=main_keyboard
        )

    except Exception as e:
        logging.exception("Ошибка при сохранении анкеты")
        await update.message.reply_text(
            "❌ Ошибка при сохранении анкеты.\n"
            "Нажми «Создать анкету» и попробуй ещё раз."
        )

async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT photo_id FROM profiles WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        await update.message.reply_text(
            "❌ Анкета не найдена.\nНажми «Создать анкету»"
        )
        return

    await update.message.reply_photo(
        photo=row[0],
        caption="👤 Твоя анкета",
        reply_markup=main_keyboard
    )

# ================== ЗАПУСК ==================
def main():
    init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^➕ Создать анкету$"), create_profile))
    app.add_handler(MessageHandler(filters.Regex("^👤 Моя анкета$"), my_profile))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    logging.info("🚀 Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
