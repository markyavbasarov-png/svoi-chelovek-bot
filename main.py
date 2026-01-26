import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

TOKEN = os.getenv("BOT_TOKEN")

# Хранилище анкет (временно, в памяти)
users = {}

# ---------- МЕНЮ ----------
def main_menu():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📝 Создать анкету")],
            [KeyboardButton("👀 Смотреть анкеты")],
            [KeyboardButton("ℹ️ О боте")]
        ],
        resize_keyboard=True
    )

# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет!\n\n"
        "Я бот знакомств для родителей-одиночек ❤️\n\n"
        "Здесь можно спокойно познакомиться — без спешки и давления.\n\n"
        "Выбери действие 👇",
        reply_markup=main_menu()
    )

# ---------- КНОПКИ ----------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id

    # Создание анкеты
    if text == "📝 Создать анкету":
        users[user_id] = {"step": "name"}
        await update.message.reply_text("Как тебя зовут?")

    # О боте
    elif text == "ℹ️ О боте":
        await update.message.reply_text(
            "❤️ «Свой человек» — место для тёплых знакомств\n"
            "для родителей-одиночек.\n\n"
            "Без спешки. Без давления."
        )

    # Смотреть анкеты
    elif text == "👀 Смотреть анкеты":
        shown = False

        for uid, profile in users.items():
            if uid != user_id and profile.get("step") == "done":
                await update.message.reply_photo(
                    photo=profile["photo"],
                    caption=
                    f"👤 {profile['name']}\n"
                    f"🎂 {profile['age']} лет\n"
                    f"📍 {profile['city']}"
                )
                shown = True
                break

        if not shown:
            await update.message.reply_text(
                "Пока нет анкет для просмотра 😔\n"
                "Загляни чуть позже"
            )

    # Продолжение заполнения анкеты
    else:
        await handle_form(update, context)

# ---------- АНКЕТА ----------
async def handle_form(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id not in users:
        return

    step = users[user_id].get("step")

    if step == "name":
        users[user_id]["name"] = update.message.text
        users[user_id]["step"] = "age"
        await update.message.reply_text("Сколько тебе лет?")

    elif step == "age":
        users[user_id]["age"] = update.message.text
        users[user_id]["step"] = "city"
        await update.message.reply_text("Из какого ты города?")

    elif step == "city":
        users[user_id]["city"] = update.message.text
        users[user_id]["step"] = "photo"
        await update.message.reply_text("📸 Пришли своё фото")

# ---------- ФОТО ----------
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id not in users:
        return

    if users[user_id].get("step") == "photo":
        users[user_id]["photo"] = update.message.photo[-1].file_id
        users[user_id]["step"] = "done"

        profile = users[user_id]

        await update.message.reply_photo(
            photo=profile["photo"],
            caption=
            f"✅ Анкета создана!\n\n"
            f"👤 {profile['name']}\n"
            f"🎂 {profile['age']} лет\n"
            f"📍 {profile['city']}",
            reply_markup=main_menu()
        )

# ---------- ЗАПУСК ----------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling()

if __name__ == "__main__":
    main()
