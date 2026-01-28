import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters import CommandStart
import aiosqlite

import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

# ================= DB =================

DB_NAME = "dating.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            gender TEXT,
            name TEXT,
            age INTEGER,
            city TEXT,
            looking_for TEXT,
            about TEXT
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            from_user INTEGER,
            to_user INTEGER,
            UNIQUE(from_user, to_user)
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS skips (
            from_user INTEGER,
            to_user INTEGER,
            UNIQUE(from_user, to_user)
        )
        """)
        await db.commit()

# ================= FSM =================

class Profile(StatesGroup):
    gender = State()
    name = State()
    age = State()
    city = State()
    looking_for = State()
    about = State()
    confirm = State()

class Browse(StatesGroup):
    show = State()

# ================= KEYBOARDS =================

start_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="START 💫")]],
    resize_keyboard=True
)

create_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="➕ Создать анкету")]],
    resize_keyboard=True
)

gender_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👨 Мужчина"), KeyboardButton(text="👩 Женщина")]
    ],
    resize_keyboard=True
)

looking_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💙 Мужчину"), KeyboardButton(text="💗 Женщину")],
        [KeyboardButton(text="🤍 Не важно")]
    ],
    resize_keyboard=True
)

about_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="➖ Пропустить")]],
    resize_keyboard=True
)

confirm_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Всё верно")],
        [KeyboardButton(text="✏️ Изменить")]
    ],
    resize_keyboard=True
)

browse_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="❤️ Нравится"), KeyboardButton(text="➡️ Дальше")],
        [KeyboardButton(text="🚫 Не моё")]
    ],
    resize_keyboard=True
)

# ================= START =================

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет 🤍\n\n"
        "Иногда всё начинается с одного шага…\n"
        "И, возможно, сегодня он именно здесь.\n\n"
        "Этот бот создан, чтобы помочь тебе\n"
        "найти своего человека —\n"
        "того, с кем будет тепло, спокойно\n"
        "и по-настоящему.\n\n"
        "Давай начнём знакомство?",
        reply_markup=create_kb
    )
       

# ================= CREATE PROFILE =================

async def create_profile(message: Message, state: FSMContext):
    await state.set_state(Profile.gender)
    await message.answer("Кто ты?", reply_markup=gender_kb)

async def set_gender(message: Message, state: FSMContext):
    await state.update_data(gender=message.text)
    await state.set_state(Profile.name)
    await message.answer("Как тебя зовут?")

async def set_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Profile.age)
    await message.answer("Сколько тебе лет?")

async def set_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Введите возраст цифрами")
    await state.update_data(age=int(message.text))
    await state.set_state(Profile.city)
    await message.answer("Из какого ты города?")

async def set_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(Profile.looking_for)
    await message.answer("Кого ты ищешь?", reply_markup=looking_kb)

async def set_looking(message: Message, state: FSMContext):
    await state.update_data(looking_for=message.text)
    await state.set_state(Profile.about)
    await message.answer(
        "Напиши пару слов о себе 🤍",
        reply_markup=about_kb
    )

async def set_about(message: Message, state: FSMContext):
    about = "" if message.text == "➖ Пропустить" else message.text
    data = await state.update_data(about=about)

    text = (
        f"{data['name']}, {data['age']}\n"
        f"{data['city']}\n\n"
        f"{data['about'] or ''}"
    )

    await state.set_state(Profile.confirm)
    await message.answer(text, reply_markup=confirm_kb)

async def confirm_profile(message: Message, state: FSMContext):
    data = await state.get_data()

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        INSERT OR REPLACE INTO users
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            message.from_user.id,
            data["gender"],
            data["name"],
            data["age"],
            data["city"],
            data["looking_for"],
            data["about"],
        ))
        await db.commit()

    await state.clear()
    await show_profile(message, state)

# ================= BROWSING =================

async def show_profile(message: Message, state: FSMContext):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("""
        SELECT user_id, name, age, city, about
        FROM users
        WHERE user_id != ?
        AND user_id NOT IN (
            SELECT to_user FROM likes WHERE from_user=?
            UNION
            SELECT to_user FROM skips WHERE from_user=?
        )
        ORDER BY RANDOM()
        LIMIT 1
        """, (message.from_user.id, message.from_user.id, message.from_user.id))
        row = await cur.fetchone()

    if not row:
        return await message.answer("Пока здесь тихо 🤍")

    uid, name, age, city, about = row
    await state.update_data(current=uid)

    await state.set_state(Browse.show)
    await message.answer(
        f"{name}, {age}\n{city}\n\n{about}",
        reply_markup=browse_kb
    )

async def like(message: Message, state: FSMContext):
    data = await state.get_data()
    to_user = data["current"]

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO likes VALUES (?, ?)",
            (message.from_user.id, to_user)
        )
        cur = await db.execute(
            "SELECT 1 FROM likes WHERE from_user=? AND to_user=?",
            (to_user, message.from_user.id)
        )
        mutual = await cur.fetchone()
        await db.commit()

    if mutual:
        link = f"https://t.me/user?id={to_user}"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="💬 Написать", url=link)]]
        )
        await message.answer(
            "Кажется, это взаимно 💫\nСамое время написать лично 🤍",
            reply_markup=kb
        )

    await show_profile(message, state)

async def skip(message: Message, state: FSMContext):
    data = await state.get_data()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO skips VALUES (?, ?)",
            (message.from_user.id, data["current"])
        )
        await db.commit()

    await show_profile(message, state)

# ================= MAIN =================

async def main():
    await init_db()
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()

    dp.message.register(start, CommandStart())
    dp.message.register(start, F.text == "START 💫")
    dp.message.register(create_profile, F.text == "➕ Создать анкету")

    dp.message.register(set_gender, Profile.gender)
    dp.message.register(set_name, Profile.name)
    dp.message.register(set_age, Profile.age)
    dp.message.register(set_city, Profile.city)
    dp.message.register(set_looking, Profile.looking_for)
    dp.message.register(set_about, Profile.about)
    dp.message.register(confirm_profile, F.text == "✅ Всё верно")

    dp.message.register(like, F.text == "❤️ Нравится")
    dp.message.register(skip, F.text.in_(["➡️ Дальше", "🚫 Не моё"]))

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
