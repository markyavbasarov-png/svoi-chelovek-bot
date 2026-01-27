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
def search_kb():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("❤️ Дальше")],
            [KeyboardButton("❌ Стоп")]
        ],
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
        reply_markup=menu_after_profile()
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

# ================== МОЯ АНКЕТА ==================
async def show_my_profile(update, context):
    user_id = update.message.from_user.id

    with conn.cursor() as c:
        c.execute("""
        SELECT name, age, city, looking, photo
        FROM users
        WHERE user_id = %s
        """, (user_id,))
        row = c.fetchone()

    if not row:
        await update.message.reply_text(
            "У тебя ещё нет анкеты 🤍\n\nДавай создадим её?",
            reply_markup=menu_start()
        )
        return

    name, age, city, looking, photo = row

    text = (
        f"{name}\n"
        f"{looking}\n\n"
        f"📍 {city}\n"
        f"🎂 {age} лет"
    )

    if photo:
        await update.message.reply_photo(
            photo=photo,
            caption=text,
            reply_markup=menu_after_profile()
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=menu_after_profile()
        )

# ================== РЕДАКТИРОВАНИЕ ==================
async def edit_profile(update, context):
    user_id = update.message.from_user.id

    with conn.cursor() as c:
        c.execute("""
        SELECT gender, name, age, city, looking, photo
        FROM users
        WHERE user_id = %s
        """, (user_id,))
        row = c.fetchone()

    if not row:
        await update.message.reply_text(
            "Анкета не найдена 🤍\nДавай создадим её заново",
            reply_markup=menu_start()
        )
        return

    gender, name, age, city, looking, photo = row

    # загружаем данные в user_data
    context.user_data.clear()
    context.user_data.update({
        "gender": gender,
        "name": name,
        "age": age,
        "city": city,
        "looking": looking,
        "photo": photo,
        "step": "gender"
    })

    await update.message.reply_text(
        "Давай обновим твою анкету 🤍\n\n"
        "Начнём сначала.\n"
        "Ты всегда можешь изменить ответы.",
        reply_markup=gender_kb()
    )

# ================== ПОИСК ЛЮДЕЙ ==================
async def search_people(update, context):
    user_id = update.message.from_user.id

    # берём список уже показанных
    shown = context.user_data.get("shown_users", []).copy()

    # чтобы не показать самого себя
    if user_id not in shown:
        shown.append(user_id)

    with conn.cursor() as c:
        if shown:
            c.execute(
                """
                SELECT user_id, name, age, city, looking, photo
                FROM users
                WHERE user_id NOT IN %s
                ORDER BY RANDOM()
                LIMIT 1
                """,
                (tuple(shown),)
            )
        else:
            c.execute(
                """
                SELECT user_id, name, age, city, looking, photo
                FROM users
                ORDER BY RANDOM()
                LIMIT 1
                """
            )

        row = c.fetchone()

    # если анкеты закончились
    if not row:
        context.user_data["shown_users"] = []
        await update.message.reply_text(
            "Пока больше никого нет 🤍\nЗагляни позже",
            reply_markup=menu_after_profile()
        )
        return

    other_id, name, age, city, looking, photo = row

    # сохраняем, что этот пользователь уже показан
    shown.append(other_id)
    context.user_data["shown_users"] = shown

    text = (
        f"{name}\n"
        f"{looking}\n\n"
        f"📍 {city}\n"
        f"🎂 {age} лет"
    )

    if photo:
        await update.message.reply_photo(
            photo=photo,
            caption=text,
            reply_markup=search_kb()
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=search_kb()
        )
        
# ================== РОУТЕР ==================
async def router(update, context):
    text = update.message.text

    
    if text == "Моя анкета":
        await show_my_profile(update, context)

    elif text == "✏️ Редактировать анкету":
        await edit_profile(update, context)

    elif text == "Подтвердить" and context.user_data.get("step") == "confirm":
        await save_profile(update, context)

    elif text == "Изменить":
        await start_profile(update, context)

    # ===== ПОИСК ЛЮДЕЙ =====
    elif text == "Поиск людей":
    user_id = update.message.from_user.id

    with conn.cursor() as c:
        c.execute(
            "SELECT 1 FROM users WHERE user_id = %s",
            (user_id,)
        )
        exists = c.fetchone()

     if not exists:
        await update.message.reply_text(
            "Сначала нужно заполнить анкету 🤍"
        )
        await start_profile(update, context)
        return

    context.user_data["shown_users"] = []
    await search_people(update, context)

     elif text == "❤️ Дальше":
    await search_people(update, context)

     elif text == "❌ Стоп":
    context.user_data.clear()
    await update.message.reply_text(
        "Поиск остановлен 🤍",
        reply_markup=menu_after_profile()
    )

    # ===== ВСЁ ОСТАЛЬНОЕ =====
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
