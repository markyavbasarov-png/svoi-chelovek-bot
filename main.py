import asyncio
import logging
import os
import aiosqlite
import random

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

# ================== DATABASE ==================
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
            photo_id TEXT
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

# ================== FSM ==================
class Profile(StatesGroup):
    name = State()
    age = State()
    city = State()
    role = State()
    goal = State()
    about = State()
    photo = State()

# ================== KEYBOARDS ==================
def start_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="давай 💫", callback_data="start_form")]
    ])

def role_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👩‍🍼 Мама", callback_data="role_Мама")],
        [InlineKeyboardButton(text="👨‍🍼 Папа", callback_data="role_Папа")],
        [InlineKeyboardButton(text="🌱 Будущий родитель", callback_data="role_Будущий")]
    ])

def goal_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚶 Прогулки", callback_data="goal_Прогулки")],
        [InlineKeyboardButton(text="💬 Общение", callback_data="goal_Общение")]
    ])

def skip_kb(action):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data=action)]
    ])

def browse_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️", callback_data="like"),
            InlineKeyboardButton(text="❌", callback_data="dislike")
        ]
    ])

def match_kb(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✉️ Написать", url=f"tg://user?id={user_id}")]
    ])

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👀 Смотреть анкеты", callback_data="browse")]
    ])

# ================== START ==================
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет 🤍\n\n"
        "«СвойЧеловек» — это знакомства с теплом и уважением.\n\n"
        "Начнём?",
        reply_markup=start_kb()
    )

@dp.callback_query(F.data == "start_form")
async def start_form(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.set_state(Profile.name)
    await call.message.answer("Как тебя зовут?")

# ================== FORM ==================
@dp.message(Profile.name)
async def set_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Profile.age)
    await message.answer("Сколько тебе лет?")

@dp.message(Profile.age)
async def set_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Введите число 🙂")
    await state.update_data(age=int(message.text))
    await state.set_state(Profile.city)
    await message.answer("Из какого ты города?")

@dp.message(Profile.city)
async def set_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(Profile.role)
    await message.answer("Кто ты?", reply_markup=role_kb())

@dp.callback_query(F.data.startswith("role_"))
async def set_role(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.update_data(role=call.data.split("_", 1)[1])
    await state.set_state(Profile.goal)
    await call.message.answer("Цель знакомства?", reply_markup=goal_kb())

@dp.callback_query(F.data.startswith("goal_"))
async def set_goal(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.update_data(goal=call.data.split("_", 1)[1])
    await state.set_state(Profile.about)
    await call.message.answer(
        "Напиши пару слов о себе",
        reply_markup=skip_kb("skip_about")
    )

@dp.callback_query(F.data == "skip_about")
async def skip_about(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.update_data(about=None)
    await state.set_state(Profile.photo)
    await call.message.answer(
        "Пришли фото или пропусти",
        reply_markup=skip_kb("skip_photo")
    )

@dp.message(Profile.about)
async def set_about(message: Message, state: FSMContext):
    await state.update_data(about=message.text)
    await state.set_state(Profile.photo)
    await message.answer(
        "Пришли фото или пропусти",
        reply_markup=skip_kb("skip_photo")
    )

@dp.callback_query(F.data == "skip_photo")
async def skip_photo(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await save_profile(call.from_user, state, None)
    await call.message.answer("Анкета сохранена 🤍", reply_markup=main_menu_kb())

@dp.message(Profile.photo)
async def set_photo(message: Message, state: FSMContext):
    if not message.photo:
        return await message.answer("Нужно фото 🙂")
    await save_profile(message.from_user, state, message.photo[-1].file_id)
    await message.answer("Анкета сохранена 🤍", reply_markup=main_menu_kb())

# ================== SAVE ==================
async def save_profile(user, state, photo_id):
    data = await state.get_data()
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user.id,
            user.username,
            data["name"],
            data["age"],
            data["city"],
            data["role"],
            data["goal"],
            data.get("about"),
            photo_id
        ))
        await db.commit()
    await state.clear()

# ================== BROWSE ==================
@dp.callback_query(F.data == "browse")
async def browse(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await show_next_profile(call, state)

async def show_next_profile(call: CallbackQuery, state: FSMContext):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
        SELECT user_id, name, age, city, role, goal, about, photo_id
        FROM users
        WHERE user_id != ?
        ORDER BY RANDOM()
        LIMIT 1
        """, (call.from_user.id,))
        profile = await cur.fetchone()

    if not profile:
        return await call.message.answer("Пока анкет нет 😌")

    await state.update_data(current_profile_id=profile[0])
    await send_profile(call.from_user.id, profile, browse_kb())

async def send_profile(chat_id, profile, kb):
    _, name, age, city, role, goal, about, photo = profile
    text = (
        f"{role} {name}, {age} · 📍 {city}\n"
        f"Ищу: {goal}\n\n"
        f"{about or ''}"
    )
    if photo:
        await bot.send_photo(chat_id, photo, caption=text, reply_markup=kb)
    else:
        await bot.send_message(chat_id, text, reply_markup=kb)

# ================== LIKES ==================
@dp.callback_query(F.data.in_(["like", "dislike"]))
async def like_dislike(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.answer("❤️" if call.data == "like" else "❌")

    data = await state.get_data()
    to_user = data.get("current_profile_id")
    from_user = call.from_user.id

    if not to_user:
        return

    if call.data == "like":
        async with aiosqlite.connect(DB) as db:
            await db.execute(
                "INSERT OR IGNORE INTO likes VALUES (?, ?)",
                (from_user, to_user)
            )
            await db.commit()

            cur = await db.execute(
                "SELECT 1 FROM likes WHERE from_user=? AND to_user=?",
                (to_user, from_user)
            )
            is_match = await cur.fetchone()

        if is_match:
            await notify_match(from_user, to_user)
        else:
            await bot.send_message(to_user, "💌 Ты кому-то понравился 🤍")

    await show_next_profile(call, state)

async def notify_match(u1, u2):
    for a, b in [(u1, u2), (u2, u1)]:
        await bot.send_message(a, "💫 У вас взаимно?")
        await bot.send_message(
            a,
            "Можно написать первым 👇",
            reply_markup=match_kb(b)
        )

# ================== RUN ==================
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
