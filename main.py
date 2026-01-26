import os
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

TOKEN = os.getenv("BOT_TOKEN")

users = {}
VIEW_LIMIT = 50

# ---------- КНОПКИ ----------
def main_menu():
    return ReplyKeyboardMarkup(
        [
            ["📝 Создать анкету"],
            ["👀 Смотреть анкеты"],
            ["ℹ️ О боте"]
        ],
        resize_keyboard=True
    )

def back_menu():
    return ReplyKeyboardMarkup(
        [["⬅️ Назад"]],
        resize_keyboard=True
    )

def search_menu():
    return ReplyKeyboardMarkup(
        [
            ["👨 Парня", "👩 Девушку"],
            ["🤝 Друга", "👯 Подругу"],
            ["⬅️ Назад"]
        ],
        resize_keyboard=True
    )

# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Добро пожаловать в «Свой человек» ❤️\n\n"
        "Здесь — тёплые знакомства без спешки.\n\n"
        "Выбери действие 👇",
        reply_markup=main_menu()
    )

# ---------- ТЕКСТ ----------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id

    if text == "⬅️ Назад":
        users.pop(user_id, None)
        await update.message.reply_text("Ты в главном меню 👇", reply_markup=main_menu())
        return

    if text == "📝 Создать анкету":
        users[user_id] = {"step": "name"}
        await update.message.reply_text("Как тебя зовут?", reply_markup=back_menu())
        return

    if text == "ℹ️ О боте":
        await update.message.reply_text(
            "❤️ «Свой человек» — знакомства для родителей-одиночек.\n\n"
            "Без давления. Без спешки."
        )
        return

    if text == "👀 Смотреть анкеты":
        shown = 0
        for uid, profile in users.items():
            if uid != user_id and profile.get("step") == "done":
                await update.message.reply_photo(
                    photo=profile["photo"],
                    caption=(
                        f"👤 {profile['name']}\n"
                        f"🎂 {profile['age']} лет\n"
                        f"📍 {profile['city']}\n"
                        f"🔎 Ищет: {profile['search']}"
                    )
                )
                shown += 1
                if shown >= VIEW_LIMIT:
                    break

        if shown == 0:
            await update.message.reply_text("Пока нет анкет 😔")
        return

    # ---------- АНКЕТА ----------
    if user_id not in users:
        return

    step = users[user_id].get("step")

    if step == "name":
        users[user_id]["name"] = text
        users[user_id]["step"] = "age"
        await update.message.reply_text("Сколько тебе лет?", reply_markup=back_menu())

    elif step == "age":
        if not text.isdigit():
            await update.message.reply_text("Введи возраст цифрами")
            return
        users[user_id]["age"] = text
        users[user_id]["step"] = "city"
        await update.message.reply_text("Из какого ты города?", reply_markup=back_menu())

    elif step == "city":
        users[user_id]["city"] = text
        users[user_id]["step"] = "search"
        await update.message.reply_text(
            "Кого ты ищешь?",
            reply_markup=search_menu()
        )

    elif step == "search":
        users[user_id]["search"] = text
        users[user_id]["step"] = "photo"
        await update.message.reply_text("📸 Пришли своё фото", reply_markup=back_menu())

# ---------- ФОТО ----------
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id not in users:
        return

    if users[user_id].get("step") == "photo":
        users[user_id]["photo"] = update.message.photo[-1].file_id
        users[user_id]["step"] = "done"

        p = users[user_id]

        await update.message.reply_photo(
            photo=p["photo"],
            caption=(
                "✅ Анкета создана!\n\n"
                f"👤 {p['name']}\n"
                f"🎂 {p['age']} лет\n"
                f"📍 {p['city']}\n"
                f"🔎 Ищет: {p['search']}"
            ),
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
