import asyncio
import logging
import aiosqlite
import os

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
bot = Bot(TOKEN)
dp = Dispatcher()

DB = "db.sqlite3"

# ---------- DATABASE ----------
async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            role TEXT,
            goal TEXT,
            child_age TEXT,
            city TEXT,
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

# ---------- FSM ----------
class Profile(StatesGroup):
    role = State()
    goal = State()
    child_age = State()
    city = State()
    about = State()
    photo = State()

class EditProfile(StatesGroup):
    menu = State()
    city = State()
    about = State()
    photo = State()

# ---------- KEYBOARDS ----------
def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👀 Смотреть анкеты", callback_data="browse")],
        [InlineKeyboardButton(text="✏️ Изменить анкету", callback_data="edit_profile")]
    ])

def browse_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️", callback_data="like"),
            InlineKeyboardButton(text="👎", callback_data="dislike")
        ]
    ])

def edit_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📍 Изменить город", callback_data="edit_city")],
        [InlineKeyboardButton(text="📝 Изменить описание", callback_data="edit_about")],
        [InlineKeyboardButton(text="📷 Изменить фото", callback_data="edit_photo")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_profile")]
    ])

# ---------- START ----------
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет 🤍\n\nДавайте познакомимся 🌱",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Начать", callback_data="start_form")]
        ])
    )

# ---------- CREATE PROFILE ----------
@dp.callback_query(F.data == "start_form")
async def start_form(call: CallbackQuery, state: FSMContext):
    await state.set_state(Profile.role)
    await call.message.edit_text(
        "Кто вы?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👩‍🍼 Мама", callback_data="role_Мама")],
            [InlineKeyboardButton(text="👨‍🍼 Папа", callback_data="role_Папа")]
        ])
    )

@dp.callback_query(Profile.role)
async def role_chosen(call: CallbackQuery, state: FSMContext):
    await state.update_data(role=call.data.replace("role_", ""))
    await state.set_state(Profile.goal)
    await call.message.edit_text(
        "Что вы ищете?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚶 Прогулки", callback_data="goal_Прогулки")],
            [InlineKeyboardButton(text="💬 Общение", callback_data="goal_Общение")]
        ])
    )

@dp.callback_query(Profile.goal)
async def goal_chosen(call: CallbackQuery, state: FSMContext):
    await state.update_data(goal=call.data.replace("goal_", ""))
    await state.set_state(Profile.city)
    await call.message.edit_text("Ваш город?")

@dp.message(Profile.city)
async def city_entered(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(Profile.about)
    await message.answer("Пару слов о себе (или отправьте /skip)")

@dp.message(Profile.about)
async def about_entered(message: Message, state: FSMContext):
    if message.text == "/skip":
        await state.update_data(about=None)
    else:
        await state.update_data(about=message.text)
    await state.set_state(Profile.photo)
    await message.answer("Отправьте фото или /skip")

@dp.message(Profile.photo, F.photo)
async def photo_received(message: Message, state: FSMContext):
    await save_profile(message.from_user, state, message.photo[-1].file_id)
    await send_my_profile(message.from_user.id)

@dp.message(Profile.photo)
async def skip_photo(message: Message, state: FSMContext):
    await save_profile(message.from_user, state, None)
    await send_my_profile(message.from_user.id)

async def save_profile(user, state, photo_id):
    data = await state.get_data()
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user.id,
            user.username,
            data["role"],
            data["goal"],
            None,
            data["city"],
            data.get("about"),
            photo_id
        ))
        await db.commit()
    await state.clear()

# ---------- SHOW OWN PROFILE ----------
async def send_my_profile(user_id: int):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT role, goal, city, about, photo_id FROM users WHERE user_id=?",
            (user_id,)
        )
        role, goal, city, about, photo_id = await cur.fetchone()

    text = f"{role}\n📍 {city}\nИщу: {goal}\n\n{about or ''}"

    if photo_id:
        await bot.send_photo(user_id, photo_id, caption=text, reply_markup=main_menu_kb())
    else:
        await bot.send_message(user_id, text, reply_markup=main_menu_kb())

# ---------- EDIT PROFILE ----------
@dp.callback_query(F.data == "edit_profile")
async def edit_profile(call: CallbackQuery, state: FSMContext):
    await state.set_state(EditProfile.menu)
    await call.message.answer("Что изменить?", reply_markup=edit_menu_kb())

@dp.callback_query(F.data == "edit_city")
async def edit_city(call: CallbackQuery, state: FSMContext):
    await state.set_state(EditProfile.city)
    await call.message.answer("Введите новый город:")

@dp.message(EditProfile.city)
async def save_city(message: Message, state: FSMContext):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE users SET city=? WHERE user_id=?",
            (message.text, message.from_user.id)
        )
        await db.commit()
    await state.clear()
    await send_my_profile(message.from_user.id)

@dp.callback_query(F.data == "edit_about")
async def edit_about(call: CallbackQuery, state: FSMContext):
    await state.set_state(EditProfile.about)
    await call.message.answer("Введите новое описание:")

@dp.message(EditProfile.about)
async def save_about(message: Message, state: FSMContext):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE users SET about=? WHERE user_id=?",
            (message.text, message.from_user.id)
        )
        await db.commit()
    await state.clear()
    await send_my_profile(message.from_user.id)

@dp.callback_query(F.data == "edit_photo")
async def edit_photo(call: CallbackQuery, state: FSMContext):
    await state.set_state(EditProfile.photo)
    await call.message.answer("Отправьте новое фото:")

@dp.message(EditProfile.photo, F.photo)
async def save_new_photo(message: Message, state: FSMContext):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE users SET photo_id=? WHERE user_id=?",
            (message.photo[-1].file_id, message.from_user.id)
        )
        await db.commit()
    await state.clear()
    await send_my_profile(message.from_user.id)

@dp.callback_query(F.data == "back_to_profile")
async def back(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await send_my_profile(call.from_user.id)

# ---------- BROWSE ----------
@dp.callback_query(F.data == "browse")
async def browse(call: CallbackQuery):
    await show_next_profile(call)

async def show_next_profile(call: CallbackQuery):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
            SELECT role, goal, city, about, photo_id
            FROM users
            WHERE user_id != ?
            ORDER BY RANDOM()
            LIMIT 1
        """, (call.from_user.id,))
        row = await cur.fetchone()

    if not row:
        await call.message.answer("Анкеты закончились 🤍")
        return

    role, goal, city, about, photo_id = row
    text = f"{role}\n📍 {city}\nИщу: {goal}\n\n{about or ''}"

    if photo_id:
        await call.message.answer_photo(photo_id, caption=text, reply_markup=browse_kb())
    else:
        await call.message.answer(text, reply_markup=browse_kb())

@dp.callback_query(F.data.in_(["like", "dislike"]))
async def swipe(call: CallbackQuery):
    await call.answer()
    await show_next_profile(call)

# ---------- RUN ----------
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
