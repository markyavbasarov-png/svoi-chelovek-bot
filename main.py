import asyncio
import logging
import os
import aiosqlite

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
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
        await db.execute("""
        CREATE TABLE IF NOT EXISTS views (
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

def my_profile_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👀 Смотреть анкеты", callback_data="browse")],
        [InlineKeyboardButton(text="✍️ Изменить анкету", callback_data="edit_profile")]
    ])

def edit_profile_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Заполнить заново", callback_data="edit_profile_full")],
        [InlineKeyboardButton(text="📸 Изменить фото", callback_data="edit_photo")],
        [InlineKeyboardButton(text="✏️ Изменить текст", callback_data="edit_text")]
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

def cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Отмена", callback_data="cancel_edit")]
    ])

# ================== START ==================
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет 🤍\n\n"
        "Здесь ищут не идеальных.\n"
        "Здесь ищут своих.\n\n"
        "Начнём?",
        reply_markup=start_kb()
    )

# ================== PROFILE FLOW ==================
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
    await call.message.edit_text("Что тебе сейчас ближе?", reply_markup=goal_kb())

@dp.callback_query(F.data.startswith("goal_"), Profile.goal)
async def set_goal(call: CallbackQuery, state: FSMContext):
    await state.update_data(goal=call.data.replace("goal_", ""))
    await state.set_state(Profile.about)
    await call.message.edit_text(
        "Пару слов о себе 🤍\n\nМожно пропустить.",
        reply_markup=skip_about_kb()
    )

@dp.callback_query(F.data == "skip_about", Profile.about)
async def skip_about(call: CallbackQuery, state: FSMContext):
    await state.update_data(about=None)
    await state.set_state(Profile.photo)
    await call.message.edit_text("Добавим фото?", reply_markup=photo_kb())

@dp.message(Profile.about)
async def set_about(message: Message, state: FSMContext):
    await state.update_data(about=message.text)
    await state.set_state(Profile.photo)
    await message.answer("Добавь фото 📸", reply_markup=photo_kb())

@dp.callback_query(F.data == "upload_photo", Profile.photo)
async def upload_photo(call: CallbackQuery):
    await call.answer()

@dp.message(Profile.photo, F.photo)
async def set_photo(message: Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    data = await state.get_data()
    await save_profile(message.from_user.id, data)
    await state.clear()
    await send_my_profile(message.from_user.id)

@dp.callback_query(F.data == "skip_photo", Profile.photo)
async def skip_photo(call: CallbackQuery, state: FSMContext):
    await state.update_data(photo_id=None)
    data = await state.get_data()
    await save_profile(call.from_user.id, data)
    await state.clear()
    await send_my_profile(call.from_user.id)

# ================== SAVE ==================
async def save_profile(user_id: int, data: dict):
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            data.get("username"),
            data.get("name"),
            data.get("age"),
            data.get("city"),
            data.get("role"),
            data.get("goal"),
            data.get("about"),
            data.get("photo_id"),
        ))
        await db.commit()

# ================== MY PROFILE ==================
async def send_my_profile(user_id: int):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
        SELECT name, age, city, goal, about, photo_id
        FROM users WHERE user_id = ?
        """, (user_id,))
        p = await cur.fetchone()

    if not p:
        return

    text = f"{p[0]}, {p[1]} • 📍 {p[2]}\n🔎 {p[3]}\n\n{p[4] or ''}"

    if p[5]:
        await bot.send_photo(user_id, p[5], caption=text, reply_markup=my_profile_kb())
    else:
        await bot.send_message(user_id, text, reply_markup=my_profile_kb())

# ================== BROWSE ==================
@dp.callback_query(F.data == "browse")
async def browse(call: CallbackQuery, state: FSMContext):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
        SELECT * FROM users
        WHERE city = (SELECT city FROM users WHERE user_id = ?)
          AND user_id != ?
          AND user_id NOT IN (
            SELECT to_user FROM views WHERE from_user = ?
          )
        ORDER BY RANDOM() LIMIT 1
        """, (call.from_user.id, call.from_user.id, call.from_user.id))
        profile = await cur.fetchone()

    if not profile:
        await call.message.answer("Пока анкет нет 🤍")
        return

    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR IGNORE INTO views VALUES (?, ?)",
            (call.from_user.id, profile[0])
        )
        await db.commit()

    await state.update_data(current_profile_id=profile[0])

    text = f"{profile[2]}, {profile[3]} • 📍 {profile[4]}\n🔎 {profile[6]}\n\n{profile[7] or ''}"

    if profile[8]:
        await bot.send_photo(call.from_user.id, profile[8], caption=text, reply_markup=browse_kb())
    else:
        await bot.send_message(call.from_user.id, text, reply_markup=browse_kb())

# ================== LIKES + MATCH ==================
@dp.callback_query(F.data.in_(["like", "dislike"]))
async def like_dislike(call: CallbackQuery, state: FSMContext):
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
            cur = await db.execute(
                "SELECT 1 FROM likes WHERE from_user = ? AND to_user = ?",
                (to_user, from_user)
            )
            match = await cur.fetchone()
            await db.commit()

        if match:
            await bot.send_message(from_user, "🤍 Это взаимно!", reply_markup=match_kb(to_user))
            await bot.send_message(to_user, "🤍 Это взаимно!", reply_markup=match_kb(from_user))

    await browse(call, state)

# ================== RUN ==================
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
