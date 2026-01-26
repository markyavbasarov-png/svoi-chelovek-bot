import os
import psycopg2
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")

conn = psycopg2.connect(DB_URL)
conn.autocommit = True

# ================== БАЗА ==================
def init_db():
    with conn.cursor() as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            gender TEXT,
            age INT,
            city TEXT,
            about TEXT,
            looking TEXT,
            photo TEXT
        );
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            from_id BIGINT,
            to_id BIGINT,
            UNIQUE(from_id, to_id)
        );
        """)

# ================== КНОПКИ ==================
def back():
    return ReplyKeyboardMarkup([[KeyboardButton("⬅️ Назад")]], resize_keyboard=True)

def menu():
    return ReplyKeyboardMarkup(
        [
            ["📝 Создать / Редактировать анкету"],
            ["👀 Смотреть анкеты"],
            ["🗑 Удалить анкету"]
        ],
        resize_keyboard=True
    )

# ================== START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Добро пожаловать!\n\nАнкеты • Лайки • Мэтчи",
        reply_markup=menu()
    )

# ================== АНКЕТА ==================
async def start_form(update, context):
    context.user_data.clear()
    context.user_data["step"] = "gender"
    await update.message.reply_text(
        "Ты мужчина или женщина?",
        reply_markup=ReplyKeyboardMarkup(
            [["👨 Мужчина", "👩 Женщина"], ["⬅️ Назад"]],
            resize_keyboard=True
        )
    )

async def handle_form(update, context):
    text = update.message.text
    step = context.user_data.get("step")

    if text == "⬅️ Назад":
        await start(update, context)
        return

    if step == "gender":
        context.user_data["gender"] = text
        context.user_data["step"] = "age"
        await update.message.reply_text("Сколько тебе лет?", reply_markup=back())

    elif step == "age":
        if not text.isdigit():
            await update.message.reply_text("Введите число")
            return
        context.user_data["age"] = int(text)
        context.user_data["step"] = "city"
        await update.message.reply_text(
            "Откуда ты?\n\nМожешь отправить геолокацию 📍",
            reply_markup=ReplyKeyboardMarkup(
                [
                    [KeyboardButton("📍 Отправить геолокацию", request_location=True)],
                    ["⬅️ Назад"]
                ],
                resize_keyboard=True
            )
        )

    elif step == "city":
        context.user_data["city"] = text.strip().lower()
        context.user_data["step"] = "about"
        await update.message.reply_text("Расскажи о себе", reply_markup=back())

    elif step == "about":
        context.user_data["about"] = text
        context.user_data["step"] = "looking"
        await update.message.reply_text(
            "Кого ищешь?",
            reply_markup=ReplyKeyboardMarkup(
                [
                    ["👩 Подругу", "🤝 Друга"],
                    ["👨 Парня", "👩‍❤️‍👨 Девушку"],
                    ["⬅️ Назад"]
                ],
                resize_keyboard=True
            )
        )

    elif step == "looking":
        context.user_data["looking"] = text
        context.user_data["step"] = "photo"
        await update.message.reply_text("Пришли фото", reply_markup=back())

# ================== ГЕОЛОКАЦИЯ ==================
async def handle_location(update, context):
    if context.user_data.get("step") != "city":
        return

    # ⚠️ Без внешних API — город вводится вручную после гео
    context.user_data["city"] = "unknown"
    context.user_data["step"] = "about"

    await update.message.reply_text(
        "📍 Геолокация получена!\nТеперь напиши название города текстом ✍️",
        reply_markup=back()
    )

# ================== ФОТО + СОХРАНЕНИЕ ==================
async def handle_photo(update, context):
    if context.user_data.get("step") != "photo":
        return

    user_id = update.message.from_user.id
    photo = update.message.photo[-1].file_id
    d = context.user_data

    with conn.cursor() as c:
        c.execute("""
        INSERT INTO users VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (user_id) DO UPDATE SET
        gender=EXCLUDED.gender,
        age=EXCLUDED.age,
        city=EXCLUDED.city,
        about=EXCLUDED.about,
        looking=EXCLUDED.looking,
        photo=EXCLUDED.photo
        """, (
            user_id,
            d["gender"],
            d["age"],
            d["city"],
            d["about"],
            d["looking"],
            photo
        ))

    await update.message.reply_photo(
        photo=photo,
        caption="✅ Анкета сохранена",
        reply_markup=menu()
    )
    context.user_data.clear()

# ================== ПРОСМОТР (ГОРОД + LOOKING) ==================
async def view_profiles(update, context):
    user_id = update.message.from_user.id
    context.user_data["index"] = 0

    with conn.cursor() as c:
        c.execute(
            "SELECT city, looking FROM users WHERE user_id=%s",
            (user_id,)
        )
        row = c.fetchone()

        if not row:
            await update.message.reply_text("Сначала создай анкету 👇", reply_markup=menu())
            return

        city, looking = row

        c.execute("""
        SELECT u.user_id, u.gender, u.age, u.city, u.about, u.photo
        FROM users u
        WHERE u.user_id != %s
          AND u.city = %s
          AND u.looking = %s
          AND NOT EXISTS (
              SELECT 1 FROM likes l
              WHERE l.from_id = %s AND l.to_id = u.user_id
          )
        LIMIT 50
        """, (user_id, city, looking, user_id))

        context.user_data["profiles"] = c.fetchall()

    await show_profile(update, context)

async def show_profile(update, context):
    profiles = context.user_data.get("profiles", [])
    i = context.user_data.get("index", 0)

    if i >= len(profiles):
        await update.message.reply_text(
            "Анкеты по твоим параметрам закончились 😔",
            reply_markup=menu()
        )
        return

    uid, gender, age, city, about, photo = profiles[i]
    context.user_data["current"] = uid

    await update.message.reply_photo(
        photo=photo,
        caption=f"{gender}\n🎂 {age}\n📍 {city}\n\n{about}",
        reply_markup=ReplyKeyboardMarkup(
            [["❤️ Лайк", "➡️ Дальше", "⏭ Пропустить"], ["⬅️ Назад"]],
            resize_keyboard=True
        )
    )

# ================== ЛАЙК ==================
async def like(update, context):
    user = update.message.from_user.id
    target = context.user_data.get("current")

    with conn.cursor() as c:
        c.execute(
            "INSERT INTO likes VALUES (%s,%s) ON CONFLICT DO NOTHING",
            (user, target)
        )
        c.execute(
            "SELECT 1 FROM likes WHERE from_id=%s AND to_id=%s",
            (target, user)
        )
        if c.fetchone():
            await update.message.reply_text("💞 У вас мэтч!")

    context.user_data["index"] += 1
    await show_profile(update, context)

# ================== УДАЛЕНИЕ ==================
async def delete_profile(update, context):
    user = update.message.from_user.id
    with conn.cursor() as c:
        c.execute("DELETE FROM users WHERE user_id=%s", (user,))
        c.execute("DELETE FROM likes WHERE from_id=%s OR to_id=%s", (user, user))
    await update.message.reply_text("Анкета удалена", reply_markup=menu())

# ================== РОУТЕР ==================
async def router(update, context):
    t = update.message.text

    if t == "📝 Создать / Редактировать анкету":
        await start_form(update, context)
    elif t == "👀 Смотреть анкеты":
        await view_profiles(update, context)
    elif t == "❤️ Лайк":
        await like(update, context)
    elif t in ["➡️ Дальше", "⏭ Пропустить"]:
        context.user_data["index"] += 1
        await show_profile(update, context)
    elif t == "🗑 Удалить анкету":
        await delete_profile(update, context)
    else:
        await handle_form(update, context)

# ================== MAIN ==================
def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, router))

    app.run_polling()

if __name__ == "__main__":
    main()
