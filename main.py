import asyncio
import logging
import os
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
        [InlineKeyboardButton(text="🌱 Будущая мама / папа", callback_data="role_Будущий")]
    ])

def goal_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚶 Прогулки", callback_data="goal_Прогулки")],
        [InlineKeyboardButton(text="💬 Общение", callback_data="goal_Общение")]
    ])

def skip_about_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_about")]
    ])

def photo_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📷 Загрузить фото", callback_data="upload_photo")],
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_photo")]
    ])

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👀 Смотреть анкеты", callback_data="browse")],
        [InlineKeyboardButton(text="✏️ Изменить анкету", callback_data="edit_profile")]
    ])

def browse_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="♥️", callback_data="like"),
            InlineKeyboardButton(text="❌", callback_data="dislike")
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ])

def match_kb(username: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать", url=f"https://t.me/{username}")]
    ])

# ================== START ==================
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет, 🤍\n\n"
        "Ты не случайно здесь.\n"
        "«свойЧеловек» — это про тепло и поддержку.\n\n"
        "Начнём знакомство?",
        reply_markup=start_kb()
    )

# ================== PROFILE FLOW ==================
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
        await message.answer("Возраст цифрами 🤍")
        return
    await state.update_data(age=int(message.text))
    await state.set_state(Profile.city)
    await message.answer("Из какого ты города?")

@dp.message(Profile.city)
async def set_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(Profile.role)
    await message.answer("Кто ты сейчас?", reply_markup=role_kb())

@dp.callback_query(F.data.startswith("role_"), Profile.role)
async def set_role(call: CallbackQuery, state: FSMContext):
    await state.update_data(role=call.data.replace("role_", ""))
    await state.set_state(Profile.goal)
    await call.message.edit_text("Что вам сейчас ближе?", reply_markup=goal_kb())

@dp.callback_query(F.data.startswith("goal_"), Profile.goal)
async def set_goal(call: CallbackQuery, state: FSMContext):
    await state.update_data(goal=call.data.replace("goal_", ""))
    await state.set_state(Profile.about)
    await call.message.edit_text(
        "Здесь ищут не идеальных,\nа своих 🤍\n\n"
        "Если хочется — расскажите пару слов о себе.",
        reply_markup=skip_about_kb()
    )

@dp.callback_query(F.data == "skip_about", Profile.about)
async def skip_about(call: CallbackQuery, state: FSMContext):
    await state.update_data(about=None)
    await state.set_state(Profile.photo)
    await call.message.edit_text(
        "Если хочется, можно добавить фото 🤍",
        reply_markup=photo_kb()
    )

@dp.message(Profile.about)
async def set_about(message: Message, state: FSMContext):
    await state.update_data(about=message.text)
    await state.set_state(Profile.photo)
    await message.answer("Добавить фото?", reply_markup=photo_kb())

@dp.callback_query(F.data == "skip_photo", Profile.photo)
async def skip_photo(call: CallbackQuery, state: FSMContext):
    await save_profile(call.from_user, state, None)
    await send_my_profile(call.from_user.id)

@dp.callback_query(F.data == "upload_photo", Profile.photo)
async def upload_photo(call: CallbackQuery):
    await call.message.edit_text(
        "Хорошо 🤍\n\n"
        "Просто отправь сюда фотографию.\n"
        "Я аккуратно добавлю её в анкету 🌿"
    )

@dp.message(Profile.photo, F.photo)
async def set_photo(message: Message, state: FSMContext):
    await save_profile(message.from_user, state, message.photo[-1].file_id)
    await send_my_profile(message.from_user.id)

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

# ================== SHOW PROFILE ==================
async def send_my_profile(user_id: int):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
        SELECT name, age, city, role, goal, about, photo_id
        FROM users WHERE user_id=?
        """, (user_id,))
        name, age, city, role, goal, about, photo_id = await cur.fetchone()

    text = (
        f"{role} {name}, {age} · 📍 {city}\n"
        f"Ищу: {goal}\n\n"
        f"{about or ''}"
    )

    if photo_id:
        await bot.send_photo(user_id, photo_id, caption=text, reply_markup=main_menu_kb())
    else:
        await bot.send_message(user_id, text, reply_markup=main_menu_kb())

# ================== EDIT PROFILE ==================
@dp.callback_query(F.data == "edit_profile")
async def edit_profile(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(Profile.name)

    await call.message.answer(
        "Хорошо 🤍\n\n"
        "Давай обновим анкету.\n"
        "Начнём сначала.\n\n"
        "Как тебя зовут?"
    )
# ================== BROWSE ==================
@dp.callback_query(F.data == "browse")
async def browse(call: CallbackQuery):
    await show_next_profile(call)

@dp.callback_query(F.data.in_(["like", "dislike"]))
async def like_dislike(call: CallbackQuery):
    await call.answer()  # 🔥 ОБЯЗАТЕЛЬНО

    if call.data == "like":
        await save_like(call.from_user.id, call.message.text)

    await show_next_profile(call)

@dp.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.message.answer("🤍", reply_markup=main_menu_kb())

async def save_like(from_user: int, text: str):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT user_id, username FROM users")
        users = await cur.fetchall()
        for uid, username in users:
            if username and username in text:
                try:
                    await db.execute(
                        "INSERT INTO likes VALUES (?, ?)",
                        (from_user, uid)
                    )
                    await db.commit()
                except:
                    pass

async def show_next_profile(call: CallbackQuery):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
        SELECT user_id, username, name, age, city, role, goal, about, photo_id
        FROM users
        WHERE city = (SELECT city FROM users WHERE user_id = ?)
        AND user_id != ?
        ORDER BY RANDOM()
        LIMIT 1
        """, (call.from_user.id, call.from_user.id))
        row = await cur.fetchone()

    if not row:
        await call.message.answer("Анкеты закончились 🤍", reply_markup=main_menu_kb())
        return

    uid, username, name, age, city, role, goal, about, photo_id = row

    text = f"{role} {name}, {age} · 📍 {city}\nИщу: {goal}\n\n{about or ''}"

    if photo_id:
        await call.message.answer_photo(photo_id, caption=text, reply_markup=browse_kb())
    else:
        await call.message.answer(text, reply_markup=browse_kb())

# ================== RUN ==================
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
