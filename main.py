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

# ================= FSM =================
class Profile(StatesGroup):
    name = State()
    age = State()
    city = State()
    role = State()
    goal = State()
    about = State()
    photo = State()

# ================= KEYBOARDS =================
def start_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Давай 💫", callback_data="start_form")]
    ])

def role_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👩‍🍼 Мама", callback_data="role_Мама")],
        [InlineKeyboardButton(text="👨‍🍼 Папа", callback_data="role_Папа")],
        [InlineKeyboardButton(text="👼 Будущий родитель", callback_data="role_Будущий")]
    ])

def goal_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚶 Прогулки", callback_data="goal_Прогулки")],
        [InlineKeyboardButton(text="💬 Общение", callback_data="goal_Общение")]
    ])

def photo_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Загрузить фото", callback_data="upload_photo")],
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_photo")]
    ])

def my_profile_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👀 Смотреть анкеты", callback_data="browse")],
        [InlineKeyboardButton(text="✍️ Изменить анкету", callback_data="edit_profile")]
    ])

def edit_profile_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎂 Возраст", callback_data="edit_age")],
        [InlineKeyboardButton(text="🏙 Город", callback_data="edit_city")],
        [InlineKeyboardButton(text="🎯 Цель", callback_data="edit_goal")],
        [InlineKeyboardButton(text="📝 О себе", callback_data="edit_about")],
        [InlineKeyboardButton(text="📸 Фото", callback_data="edit_photo")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data="delete_profile")],
        [InlineKeyboardButton(text="⬅️ Отмена", callback_data="cancel_edit")]
    ])

def browse_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="♥️", callback_data="like"),
            InlineKeyboardButton(text="✖️", callback_data="dislike")
        ]
    ])

def match_kb(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✉️ Написать", url=f"tg://user?id={user_id}")]
    ])

# ================= START =================
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет 🤍\n\nНачнём знакомство?",
        reply_markup=start_kb()
    )

# ================= PROFILE CREATE =================
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
        await message.answer("Возраст цифрами")
        return
    await state.update_data(age=int(message.text))
    await state.set_state(Profile.city)
    await message.answer("Город?")

@dp.message(Profile.city)
async def set_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(Profile.role)
    await message.answer("Кто ты?", reply_markup=role_kb())

@dp.callback_query(F.data.startswith("role_"), Profile.role)
async def set_role(call: CallbackQuery, state: FSMContext):
    await state.update_data(role=call.data.replace("role_", ""))
    await state.set_state(Profile.goal)
    await call.message.edit_text("Цель?", reply_markup=goal_kb())

@dp.callback_query(F.data.startswith("goal_"), Profile.goal)
async def set_goal(call: CallbackQuery, state: FSMContext):
    await state.update_data(goal=call.data.replace("goal_", ""))
    await state.set_state(Profile.about)
    await call.message.edit_text("Пару слов о себе? (можно текстом)")

@dp.message(Profile.about)
async def set_about(message: Message, state: FSMContext):
    await state.update_data(about=message.text)
    await state.set_state(Profile.photo)
    await message.answer("Добавить фото?", reply_markup=photo_kb())

@dp.callback_query(F.data == "skip_photo", Profile.photo)
async def skip_photo(call: CallbackQuery, state: FSMContext):
    await save_profile(call.from_user, state, None)
    await send_my_profile(call.from_user.id)

@dp.message(F.photo, Profile.photo)
async def set_photo(message: Message, state: FSMContext):
    await save_profile(message.from_user, state, message.photo[-1].file_id)
    await send_my_profile(message.from_user.id)

# ================= SAVE / LOAD =================
async def save_profile(user, state, photo_id):
    data = await state.get_data()
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user.id, user.username,
            data["name"], data["age"], data["city"],
            data["role"], data["goal"], data.get("about"),
            photo_id
        ))
        await db.commit()
    await state.clear()

async def update_user_field(user_id, field, value):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            f"UPDATE users SET {field} = ? WHERE user_id = ?",
            (value, user_id)
        )
        await db.commit()

async def get_profile(user_id):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT user_id, name, age, city, role, goal, about, photo_id FROM users WHERE user_id=?",
            (user_id,)
        )
        return await cur.fetchone()

async def send_profile_card(chat_id, profile, kb):
    uid, name, age, city, role, goal, about, photo_id = profile
    text = f"{role} {name}, {age} · {city}\n🎯 {goal}\n\n{about or ''}"
    if photo_id:
        await bot.send_photo(chat_id, photo_id, caption=text, reply_markup=kb)
    else:
        await bot.send_message(chat_id, text, reply_markup=kb)

async def send_my_profile(user_id):
    profile = await get_profile(user_id)
    await send_profile_card(user_id, profile, my_profile_kb())

# ================= EDIT =================
@dp.callback_query(F.data == "edit_profile")
async def edit_profile(call: CallbackQuery):
    await call.message.answer("Что изменить?", reply_markup=edit_profile_kb())

@dp.callback_query(F.data == "edit_age")
async def edit_age(call: CallbackQuery, state: FSMContext):
    await state.set_state(Profile.age)
    await call.message.answer("Новый возраст:")

@dp.message(Profile.age)
async def upd_age(message: Message, state: FSMContext):
    await update_user_field(message.from_user.id, "age", int(message.text))
    await state.clear()
    await send_my_profile(message.from_user.id)

@dp.callback_query(F.data == "edit_city")
async def edit_city(call: CallbackQuery, state: FSMContext):
    await state.set_state(Profile.city)
    await call.message.answer("Новый город:")

@dp.message(Profile.city)
async def upd_city(message: Message, state: FSMContext):
    await update_user_field(message.from_user.id, "city", message.text)
    await state.clear()
    await send_my_profile(message.from_user.id)

@dp.callback_query(F.data == "edit_goal")
async def edit_goal(call: CallbackQuery, state: FSMContext):
    await state.set_state(Profile.goal)
    await call.message.answer("Цель:", reply_markup=goal_kb())

@dp.callback_query(F.data.startswith("goal_"), Profile.goal)
async def upd_goal(call: CallbackQuery, state: FSMContext):
    await update_user_field(call.from_user.id, "goal", call.data.replace("goal_", ""))
    await state.clear()
    await send_my_profile(call.from_user.id)

@dp.callback_query(F.data == "edit_about")
async def edit_about(call: CallbackQuery, state: FSMContext):
    await state.set_state(Profile.about)
    await call.message.answer("Новый текст:")

@dp.message(Profile.about)
async def upd_about(message: Message, state: FSMContext):
    await update_user_field(message.from_user.id, "about", message.text)
    await state.clear()
    await send_my_profile(message.from_user.id)

@dp.callback_query(F.data == "edit_photo")
async def edit_photo(call: CallbackQuery, state: FSMContext):
    await state.set_state(Profile.photo)
    await call.message.answer("Новое фото:")

@dp.message(F.photo, Profile.photo)
async def upd_photo(message: Message, state: FSMContext):
    await update_user_field(message.from_user.id, "photo_id", message.photo[-1].file_id)
    await state.clear()
    await send_my_profile(message.from_user.id)

@dp.callback_query(F.data == "delete_profile")
async def delete_profile(call: CallbackQuery):
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM users WHERE user_id=?", (call.from_user.id,))
        await db.commit()
    await call.message.answer("Анкета удалена", reply_markup=start_kb())

@dp.callback_query(F.data == "cancel_edit")
async def cancel_edit(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await send_my_profile(call.from_user.id)

# ================= BROWSE =================
@dp.callback_query(F.data == "browse")
async def browse(call: CallbackQuery, state: FSMContext):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
        SELECT user_id, name, age, city, role, goal, about, photo_id
        FROM users
        WHERE user_id != ?
        ORDER BY RANDOM() LIMIT 1
        """, (call.from_user.id,))
        profile = await cur.fetchone()

    if not profile:
        await call.message.answer("Анкет пока нет")
        return

    await state.update_data(current_profile_id=profile[0])
    await send_profile_card(call.from_user.id, profile, browse_kb())

@dp.callback_query(F.data == "like")
async def like(call: CallbackQuery, state: FSMContext):
    await browse(call, state)

@dp.callback_query(F.data == "dislike")
async def dislike(call: CallbackQuery, state: FSMContext):
    await browse(call, state)

# ================= RUN =================
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
