import os
import psycopg2
from telegram import (
    Update,
    ReplyKeyboardMarkup
)
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
    "💗 <b>Добро пожаловать в «СвойЧеловек»</b>\n\n"
    "Это пространство для одиноких родителей,\n"
    "будущих мам и пап, а также тех,\n"
    "кто ищет поддержку, дружбу или любовь.\n\n"
    "Здесь не оценивают и не торопят.\n"
    "Здесь понимают: у каждого своя история —\n"
    "и это нормально 🤍\n\n"
    "Здесь ты можешь найти:\n"
    "• близкого по духу человека\n"
    "• подругу или друга\n"
    "• поддержку\n"
    "• или любовь\n\n"
    "Давай начнём с анкеты 👇"
)

# ================== DATABASE ==================
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
            photo TEXT
        );
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS filters (
            user_id BIGINT PRIMARY KEY,
            city TEXT,
            age_from INT,
            age_to INT
        );
        """)

# ================== KEYBOARDS ==================
def main_menu():
    return ReplyKeyboardMarkup(
        [
            ["📝 Рассказать о себе"],
            ["👀 Поиск своего человека"],
            ["⚙️ Фильтры"]
        ],
        resize_keyboard=True
    )

def back():
    return ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)

def gender_kb():
    return ReplyKeyboardMarkup(
        [["Парень", "Девушка"], ["⬅️ Назад"]],
        resize_keyboard=True
    )

def confirm_kb():
    return ReplyKeyboardMarkup(
        [["✅ Подтвердить"], ["⬅️ Назад"]],
        resize_keyboard=True
    )

# ================== START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        WELCOME_TEXT,
        parse_mode="HTML",
        reply_markup=main_menu()
    )

# ================== FORM ==================
async def start_form(update, context):
    context.user_data.clear()
    context.user_data["step"] = "gender"
    await update.message.reply_text(
        "Парень или девушка?",
        reply_markup=gender_kb()
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
        await update.message.reply_text("Как тебя зовут?", reply_markup=back())

    elif step == "name":
        context.user_data["name"] = text
        context.user_data["step"] = "age"
        await update.message.reply_text("Сколько тебе лет?", reply_markup=back())

    elif step == "age":
        if not text.isdigit():
            await update.message.reply_text("Введите число")
            return
        context.user_data["age"] = int(text)
        context.user_data["step"] = "city"
        await update.message.reply_text("Откуда ты?", reply_markup=back())

    elif step == "city":
        context.user_data["city"] = text
        context.user_data["step"] = "photo"
        await update.message.reply_text("Загрузи фото", reply_markup=back())

    elif step == "looking":
        context.user_data["looking"] = text
        await confirm_profile(update, context)

# ================== PHOTO ==================
async def handle_photo(update, context):
    if context.user_data.get("step") != "photo":
        return

    context.user_data["photo"] = update.message.photo[-1].file_id
    context.user_data["step"] = "looking"
    await update.message.reply_text(
        "Кого хочешь найти?",
        reply_markup=back()
    )

# ================== CONFIRM ==================
async def confirm_profile(update, context):
    d = context.user_data

    text = (
        f"📋 <b>Твоя анкета</b>\n\n"
        f"👤 {d['gender']}\n"
        f"📛 {d['name']}\n"
        f"🎂 {d['age']}\n"
        f"📍 {d['city']}\n"
        f"💞 {d['looking']}"
    )

    await update.message.reply_photo(
        photo=d["photo"],
        caption=text,
        parse_mode="HTML",
        reply_markup=confirm_kb()
    )

# ================== SAVE ==================
async def save_profile(update, context):
    d = context.user_data
    user_id = update.message.from_user.id

    with conn.cursor() as c:
        c.execute("""
        INSERT INTO users VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (user_id) DO UPDATE SET
        gender=EXCLUDED.gender,
        name=EXCLUDED.name,
        age=EXCLUDED.age,
        city=EXCLUDED.city,
        looking=EXCLUDED.looking,
        photo=EXCLUDED.photo
        """, (
            user_id,
            d["gender"],
            d["name"],
            d["age"],
            d["city"],
            d["looking"],
            d["photo"]
        ))

    context.user_data.clear()
    await update.message.reply_text(
        "✅ Анкета сохранена!",
        reply_markup=main_menu()
    )

# ================== FILTERS ==================
async def start_filters(update, context):
    context.user_data["filter_step"] = "city"
    await update.message.reply_text(
        "📍 Город (или «любой»):",
        reply_markup=back()
    )

async def handle_filters(update, context):
    text = update.message.text
    step = context.user_data.get("filter_step")

    if step == "city":
        context.user_data["f_city"] = None if text.lower() == "любой" else text
        context.user_data["filter_step"] = "age_from"
        await update.message.reply_text("🎂 Минимальный возраст:")

    elif step == "age_from":
        context.user_data["f_age_from"] = int(text)
        context.user_data["filter_step"] = "age_to"
        await update.message.reply_text("🎂 Максимальный возраст:")

    elif step == "age_to":
        user_id = update.message.from_user.id

        with conn.cursor() as c:
            c.execute("""
            INSERT INTO filters VALUES (%s,%s,%s,%s)
            ON CONFLICT (user_id) DO UPDATE SET
            city=EXCLUDED.city,
            age_from=EXCLUDED.age_from,
            age_to=EXCLUDED.age_to
            """, (
                user_id,
                context.user_data["f_city"],
                context.user_data["f_age_from"],
                int(text)
            ))

        context.user_data.clear()
        await update.message.reply_text(
            "✅ Фильтры сохранены",
            reply_markup=main_menu()
        )

# ================== SEARCH ==================
async def search_profiles(update, context):
    user_id = update.message.from_user.id

    with conn.cursor() as c:
        c.execute("SELECT city, age_from, age_to FROM filters WHERE user_id=%s", (user_id,))
        f = c.fetchone()

        city, age_from, age_to = (None, 18, 100)
        if f:
            city, age_from, age_to = f

        c.execute("""
        SELECT gender,name,age,city,looking,photo
        FROM users
        WHERE user_id != %s
        AND age BETWEEN %s AND %s
        AND (%s IS NULL OR city=%s)
        ORDER BY RANDOM()
        LIMIT 1
        """, (user_id, age_from, age_to, city, city))

        row = c.fetchone()

    if not row:
        await update.message.reply_text("Анкет нет 😔", reply_markup=main_menu())
        return

    text = (
        f"👤 {row[0]}\n"
        f"📛 {row[1]}\n"
        f"🎂 {row[2]}\n"
        f"📍 {row[3]}\n"
        f"💞 {row[4]}"
    )

    await update.message.reply_photo(photo=row[5], caption=text)

# ================== ROUTER ==================
async def router(update, context):
    text = update.message.text

    if text == "📝 Рассказать о себе":
        await start_form(update, context)

    elif text == "✅ Подтвердить":
        await save_profile(update, context)

    elif text == "⚙️ Фильтры":
        await start_filters(update, context)

    elif text == "👀 Поиск своего человека":
        await search_profiles(update, context)

    elif context.user_data.get("filter_step"):
        await handle_filters(update, context)

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
