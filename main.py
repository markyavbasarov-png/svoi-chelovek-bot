import asyncio
import logging
import os
import random

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import aiosqlite

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_NAME = "dating.db"

logging.basicConfig(level=logging.INFO)

# ======================= DB =======================

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

# ======================= FSM =======================

class Profile(StatesGroup):
    ASK_GENDER = State()
    ASK_NAME = State()
    ASK_AGE = State()
    ASK_CITY = State()
    ASK_LOOKING_FOR = State()
    ASK_ABOUT = State()
    CONFIRM = State()

class Browse(StatesGroup):
    SHOW_PROFILE = State()

# ======================= KEYBOARDS =======================

start_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Давай 😏")]],
    resize_keyboard=True
)

gender_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="👨 Мужчина"), KeyboardButton(text="👩 Женщина")]],
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

# ======================= BOT =======================

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ======================= START =======================

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
        reply_markup=start_kb
    )

@dp.message(F.text == "Давай 😏")
async def begin_profile(message: Message, state: FSMContext):
    await state.set_state(Profile.ASK_GENDER)
    await message.answer("Кто ты?", reply_markup=gender_kb)

# ======================= PROFILE =======================

@dp.message(Profile.ASK_GENDER)
async def save_gender(message: Message, state: FSMContext):
    gender = "male" if "Мужчина" in message.text else "female"
    await state.update_data(gender=gender)
    await state.set_state(Profile.ASK_NAME)
    await message.answer("Как тебя зовут?")

@dp.message(Profile.ASK_NAME)
async def save_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(Profile.ASK_AGE)
    await message.answer("Сколько тебе лет?")

@dp.message(Profile.ASK_AGE)
async def save_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Напиши число 🙂")
    await state.update_data(age=int(message.text))
    await state.set_state(Profile.ASK_CITY)
    await message.answer("Из какого ты города?")

@dp.message(Profile.ASK_CITY)
async def save_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text.strip())
    await state.set_state(Profile.ASK_LOOKING_FOR)
    await message.answer("Кого ты ищешь?", reply_markup=looking_kb)

@dp.message(Profile.ASK_LOOKING_FOR)
async def save_looking(message: Message, state: FSMContext):
    if "Мужчину" in message.text:
        lf = "male"
    elif "Женщину" in message.text:
        lf = "female"
    else:
        lf = "any"
    await state.update_data(looking_for=lf)
    await state.set_state(Profile.ASK_ABOUT)
    await message.answer("Хочешь — напиши пару слов о себе 🤍", reply_markup=about_kb)

@dp.message(Profile.ASK_ABOUT)
async def save_about(message: Message, state: FSMContext):
    about = "" if "Пропустить" in message.text else message.text
    await state.update_data(about=about)

    data = await state.get_data()
    preview = (
        f"{data['name']}, {data['age']}\n"
        f"{data['city']}\n\n"
        f"{data['about']}"
    )

    await state.set_state(Profile.CONFIRM)
    await message.answer(preview, reply_markup=confirm_kb)

# ======================= CONFIRM =======================

@dp.message(Profile.CONFIRM, F.text == "✅ Всё верно")
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
            data["about"]
        ))
        await db.commit()

    await state.set_state(Browse.SHOW_PROFILE)
    await message.answer("Отлично 🤍 Сейчас покажу анкеты", reply_markup=browse_kb)
    await show_profile(message, state)

# ======================= BROWSING =======================
async def show_profile(message: Message, state: FSMContext):
    async with aiosqlite.connect(DB_NAME) as db:
        candidates = await db.execute_fetchall("""
            SELECT * FROM users
            WHERE user_id != ?
            AND user_id NOT IN (
                SELECT to_user FROM skips WHERE from_user=?
            )
        """, (
            message.from_user.id,
            message.from_user.id
        ))

    if not candidates:
        return await message.answer(
            "Пока здесь тихо 🤍\nНо новые люди появляются каждый день",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="🔄 Проверить позже")]],
                resize_keyboard=True
            )
        )

    profile = random.choice(candidates)
    await state.update_data(current_profile=profile[0])

    text = (
        f"{profile[2]}, {profile[3]}\n"
        f"{profile[4]}\n\n"
        f"{profile[6]}"
    )

    await message.answer(text, reply_markup=browse_kb)
# ======================= CHECK AGAIN =======================

@dp.message(F.text == "🔄 Проверить позже")
async def check_again(message: Message, state: FSMContext):
    await state.set_state(Browse.SHOW_PROFILE)
    await message.answer("Секундочку… смотрю, кто появился 👀")
    await show_profile(message, state)

# ======================= LIKE =======================
@dp.message(Browse.SHOW_PROFILE, F.text == "❤️ Нравится")
async def like_profile(message: Message, state: FSMContext):
    data = await state.get_data()
    target = data["current_profile"]

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO likes VALUES (?, ?)",
            (message.from_user.id, target)
        )

        mutual = await db.execute_fetchone(
            "SELECT 1 FROM likes WHERE from_user=? AND to_user=?",
            (target, message.from_user.id)
        )

        await db.commit()

    if mutual:
        link_for_me = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(
                text="💬 Написать",
                url=f"tg://user?id={target}"
            )]]
        )

        link_for_target = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(
                text="💬 Написать",
                url=f"tg://user?id={message.from_user.id}"
            )]]
        )

        await message.answer(
            "💫 Это взаимно!\nМожете написать друг другу 🤍",
            reply_markup=link_for_me
        )

        await bot.send_message(
            target,
            "💫 У вас взаимная симпатия!\nКто-то лайкнул вас в ответ 🤍",
            reply_markup=link_for_target
        )

    await show_profile(message, state)
# ======================= SKIP =======================

@dp.message(Browse.SHOW_PROFILE, F.text.in_(["➡️ Дальше", "🚫 Не моё"]))
async def skip_profile(message: Message, state: FSMContext):
    data = await state.get_data()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO skips VALUES (?, ?)",
            (message.from_user.id, data["current_profile"])
        )
        await db.commit()

    await show_profile(message, state)

# ======================= RUN =======================

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
