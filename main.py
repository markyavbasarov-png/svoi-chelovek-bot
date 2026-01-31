import asyncio
import logging
import os
import time
import aiosqlite

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

TOKEN = os.getenv("BOT_TOKEN")
DB = "db.sqlite3"

logging.basicConfig(level=logging.INFO)

bot = Bot(TOKEN)
dp = Dispatcher()

# ================= DATABASE =================
async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            name TEXT,
            age INTEGER,
            city TEXT,
            role TEXT,
            goal TEXT,
            about TEXT,
            photo_id TEXT,
            is_active INTEGER DEFAULT 1,
            last_active INTEGER,
            walk_time TEXT,
            child_age TEXT
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            from_user INTEGER,
            to_user INTEGER,
            UNIQUE(from_user, to_user)
        )
        """)
        await db.commit()

# ================= FSM =================
class Profile(StatesGroup):
    name = State()
    age = State()
    city = State()
    role = State()
    goal = State()
    about = State()
    photo = State()
    walk_time = State()
    child_age = State()

# ================= KEYBOARDS =================
def start_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Давай 💫", callback_data="start_form")]
    ])

def browse_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️", callback_data="back"),
            InlineKeyboardButton(text="♥️", callback_data="like"),
            InlineKeyboardButton(text="❌", callback_data="dislike")
        ],
        [
            InlineKeyboardButton(text="🚩 Пожаловаться", callback_data="report")
        ]
    ])

def after_profile_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👀 Смотреть анкеты", callback_data="browse")],
        [InlineKeyboardButton(text="🙈 Скрыть анкету", callback_data="hide_profile")]
    ])

def report_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Спам", callback_data="report_spam")],
        [InlineKeyboardButton(text="Грубость", callback_data="report_rude")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="browse")]
    ])

# ================= START =================
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🤍 Здесь ищут своих.\n\nНачнём?",
        reply_markup=start_kb()
    )

# ================= PROFILE FLOW =================
@dp.callback_query(F.data == "start_form")
async def start_form(call: CallbackQuery, state: FSMContext):
    await state.set_state(Profile.name)
    await call.message.edit_text("Как тебя зовут?")

@dp.message(Profile.name)
async def set_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Profile.age)
    await message.answer("Сколько тебе лет?")

@dp.message(Profile.age)
async def set_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Цифрами 🤍")
    await state.update_data(age=int(message.text))
    await state.set_state(Profile.city)
    await message.answer("Город?")

@dp.message(Profile.city)
async def set_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(Profile.goal)
    await message.answer("Что ищешь? (прогулки / общение)")

@dp.message(Profile.goal)
async def set_goal(message: Message, state: FSMContext):
    await state.update_data(goal=message.text)
    await state.set_state(Profile.walk_time)
    await message.answer("Когда чаще гуляешь? (утро / день / вечер)")

@dp.message(Profile.walk_time)
async def set_walk_time(message: Message, state: FSMContext):
    await state.update_data(walk_time=message.text)
    await state.set_state(Profile.child_age)
    await message.answer("Возраст ребёнка?")

@dp.message(Profile.child_age)
async def set_child_age(message: Message, state: FSMContext):
    await state.update_data(child_age=message.text)
    await state.set_state(Profile.about)
    await message.answer("Пару слов о себе 🤍")

@dp.message(Profile.about)
async def set_about(message: Message, state: FSMContext):
    await state.update_data(about=message.text)
    await state.set_state(Profile.photo)
    await message.answer("Фото можно добавить, а можно пропустить")

@dp.message(Profile.photo, F.photo)
async def set_photo(message: Message, state: FSMContext):
    await save_profile(message.from_user, state, message.photo[-1].file_id)
    await send_my_profile(message.from_user.id)

@dp.message(Profile.photo)
async def skip_photo(message: Message, state: FSMContext):
    await save_profile(message.from_user, state, None)
    await send_my_profile(message.from_user.id)

# ================= SAVE =================
async def save_profile(user, state, photo_id):
    data = await state.get_data()
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT OR REPLACE INTO users
        (user_id, username, name, age, city, goal, about, photo_id, is_active, last_active, walk_time, child_age)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
        """, (
            user.id,
            user.username,
            data["name"],
            data["age"],
            data["city"],
            data["goal"],
            data["about"],
            photo_id,
            int(time.time()),
            data["walk_time"],
            data["child_age"]
        ))
        await db.commit()
    await state.clear()

# ================= BROWSE =================
@dp.callback_query(F.data == "browse")
async def browse(call: CallbackQuery, state: FSMContext):
    await show_next(call, state)

async def show_next(call, state):
    data = await state.get_data()
    prev = data.get("current_profile")

    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
        SELECT user_id, name, age, city, goal, about, photo_id
        FROM users
        WHERE user_id != ?
          AND is_active = 1
        ORDER BY
          (city = (SELECT city FROM users WHERE user_id=?)) DESC,
          (goal = (SELECT goal FROM users WHERE user_id=?)) DESC,
          ABS(age - (SELECT age FROM users WHERE user_id=?))
        LIMIT 1
        """, (call.from_user.id, call.from_user.id, call.from_user.id, call.from_user.id))
        profile = await cur.fetchone()

    if not profile:
        return await call.message.answer("🤍 Пока анкет нет")

    await state.update_data(prev_profile=prev, current_profile=profile)
    await send_profile(call.from_user.id, profile)

async def send_profile(chat_id, profile):
    uid, name, age, city, goal, about, photo = profile
    text = f"{name}, {age} · {city}\n🎯 {goal}\n\n{about}"
    if photo:
        await bot.send_photo(chat_id, photo, caption=text, reply_markup=browse_kb())
    else:
        await bot.send_message(chat_id, text, reply_markup=browse_kb())

# ================= BACK =================
@dp.callback_query(F.data == "back")
async def back(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    prev = data.get("prev_profile")
    if prev:
        await send_profile(call.from_user.id, prev)

# ================= SAFETY =================
@dp.callback_query(F.data == "report")
async def report(call: CallbackQuery):
    await call.message.answer("Что случилось?", reply_markup=report_kb())

@dp.callback_query(F.data.startswith("report_"))
async def report_done(call: CallbackQuery):
    await call.message.answer("Спасибо 🤍 Мы разберёмся")

@dp.callback_query(F.data == "hide_profile")
async def hide_profile(call: CallbackQuery):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE users SET is_active = 0 WHERE user_id = ?",
            (call.from_user.id,)
        )
        await db.commit()
    await call.message.answer("Анкета скрыта 🙈")

# ================= REMINDERS =================
async def reminder_loop():
    while True:
        async with aiosqlite.connect(DB) as db:
            cur = await db.execute("""
            SELECT user_id FROM users
            WHERE last_active < ?
            """, (int(time.time()) - 3 * 86400,))
            users = await cur.fetchall()

        for (uid,) in users:
            try:
                await bot.send_message(uid, "🤍 Тут появились новые люди")
            except:
                pass

        await asyncio.sleep(3600)

# ================= RUN =================
async def main():
    await init_db()
    asyncio.create_task(reminder_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
