import asyncio
import logging
import os
import aiosqlite

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import CommandStart, Command
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
        [InlineKeyboardButton(text="👼🏼 Будущий родитель", callback_data="role_Будущий")]
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
        [InlineKeyboardButton(text="📸 Загрузить фото", callback_data="upload_photo")],
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_photo")]
    ])

def after_create_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👀 Смотреть анкеты", callback_data="view_profiles")]
    ])

def my_profile_manage_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Изменить анкету", callback_data="edit_profile")],
        [InlineKeyboardButton(text="💬 Изменить текст", callback_data="edit_text")],
        [InlineKeyboardButton(text="📸 Изменить фото", callback_data="edit_photo")],
        [InlineKeyboardButton(text="🗑 Удалить анкету", callback_data="delete_profile")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_profile")]
    ])

def browse_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="♥️", callback_data="like"),
            InlineKeyboardButton(text="✖️", callback_data="dislike")
        ]
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

# ================= MY PROFILE =================
async def check_profile_exists(message: Message) -> bool:
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT 1 FROM users WHERE user_id = ?",
            (message.from_user.id,)
        )
        exists = await cur.fetchone()

    if not exists:
        await message.answer(
            "Твоя анкета ещё не создана 🤍\nДавай начнём знакомство",
            reply_markup=start_kb()
        )
        return False

    return True

@dp.message(Command("myprofile"))
async def my_profile(message: Message):
    if not await check_profile_exists(message):
        return
    await send_my_profile(message.from_user.id)

# ============== CALLBACKS ==============
@dp.callback_query(F.data == "back_to_profile")
async def back_to_profile(call: CallbackQuery):
    await call.answer()
    await send_my_profile(call.from_user.id)

@dp.callback_query(F.data == "delete_profile")
async def delete_profile(call: CallbackQuery):
    await call.answer()
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM users WHERE user_id = ?", (call.from_user.id,))
        await db.execute(
            "DELETE FROM likes WHERE from_user = ? OR to_user = ?",
            (call.from_user.id, call.from_user.id)
        )
        await db.commit()

    await call.message.answer(
        "🗑 Анкета удалена\n\n"
        "Если захочешь — всегда можно создать новую 🤍",
        reply_markup=start_kb()
    )

# ================= VIEW PROFILES =================
@dp.callback_query(F.data == "view_profiles")
async def view_profiles(call: CallbackQuery):
    await call.answer()

    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
            SELECT user_id, name, age, city, role, goal, about, photo_id
            FROM users
            WHERE city = (SELECT city FROM users WHERE user_id = ?)
              AND user_id != ?
            ORDER BY RANDOM()
            LIMIT 1
        """, (call.from_user.id, call.from_user.id))

        profile = await cur.fetchone()

    if not profile:
        await call.message.answer(
            "🤍 Пока анкет нет.\nЗагляни чуть позже"
        )
        return

    await send_profile_card(
        chat_id=call.from_user.id,
        profile=profile,
        kb=browse_kb()
    )

# ================= PROFILE FLOW =================
@dp.callback_query(F.data == "start_form")
async def start_form(call: CallbackQuery, state: FSMContext):
    await state.clear()
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
    await message.answer(
        "Если хочется, можно добавить фото 🤍",
        reply_markup=photo_kb()
    )

@dp.callback_query(F.data == "skip_photo", Profile.photo)
async def skip_photo(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await save_profile(call.from_user, state, photo_id=None)
    profile = await get_profile(call.from_user.id)
    await send_profile_card(call.from_user.id, profile, after_create_kb())

@dp.message(F.photo, Profile.photo)
async def set_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await save_profile(message.from_user, state, photo_id)
    profile = await get_profile(message.from_user.id)
    await send_profile_card(message.from_user.id, profile, after_create_kb())

# ================= SAVE =================
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

# ================= PROFILE RENDER =================
async def get_profile(user_id: int):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT user_id, name, age, city, role, goal, about, photo_id FROM users WHERE user_id = ?",
            (user_id,)
        )
        return await cur.fetchone()

async def send_profile_card(chat_id: int, profile: tuple, kb=None):
    uid, name, age, city, role, goal, about, photo_id = profile
    text = (
        f"{role} {name}, {age} · 📍 {city}\n"
        f"🎯 {goal}\n\n"
        f"{about or ''}"
    )

    if photo_id:
        await bot.send_photo(chat_id, photo_id, caption=text, reply_markup=kb)
    else:
        await bot.send_message(chat_id, text, reply_markup=kb)

async def send_my_profile(user_id: int):
    profile = await get_profile(user_id)
    if profile:
        await send_profile_card(user_id, profile, my_profile_manage_kb())

# ================= RUN =================
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
