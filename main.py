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
        [InlineKeyboardButton(text="👀 Смотреть анкеты", callback_data="browse")]
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

# ================== PROFILE CARD ==================
async def send_profile_card(chat_id: int, profile: tuple, kb):
    uid, name, age, city, role, goal, about, photo_id = profile
    text = (
        f"{role} {name}, {age} · 📍 {city}\n"
        f"Ищу: {goal}\n\n"
        f"{about or ''}"
    )
    if photo_id:
        await bot.send_photo(chat_id, photo_id, caption=text, reply_markup=kb)
    else:
        await bot.send_message(chat_id, text, reply_markup=kb)

# ================== BROWSE ==================
@dp.callback_query(F.data == "browse")
async def browse(call: CallbackQuery, state: FSMContext):
    await show_next_profile(call, state)

async def show_next_profile(call: CallbackQuery, state: FSMContext):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
        SELECT user_id, name, age, city, role, goal, about, photo_id
        FROM users
        WHERE city = (SELECT city FROM users WHERE user_id = ?)
        AND user_id != ?
        AND user_id NOT IN (
            SELECT to_user FROM likes WHERE from_user = ?
        )
        ORDER BY RANDOM()
        LIMIT 1
        """, (call.from_user.id, call.from_user.id, call.from_user.id))
        profile = await cur.fetchone()

    if not profile:
        await call.message.answer("Анкеты закончились 🤍", reply_markup=main_menu_kb())
        return

    await state.update_data(current_profile_id=profile[0])
    await send_profile_card(call.from_user.id, profile, browse_kb())

# ================== LIKES + NOTIFICATIONS ==================
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
                "SELECT 1 FROM likes WHERE from_user = ? AND to_user = ?",
                (to_user, from_user)
            )
            is_match = await cur.fetchone()

        if is_match:
            await notify_match(from_user, to_user)
        else:
            await bot.send_message(
                to_user,
                "💌 Ты кому-то понравился\nПосмотри анкеты 🤍"
            )

    await show_next_profile(call, state)

async def notify_match(u1: int, u2: int):
    for viewer, partner in [(u1, u2), (u2, u1)]:
        async with aiosqlite.connect(DB) as db:
            cur = await db.execute("""
            SELECT user_id, name, age, city, role, goal, about, photo_id
            FROM users WHERE user_id = ?
            """, (partner,))
            profile = await cur.fetchone()

        await bot.send_message(viewer, "🤍 Кажется, это взаимно")
        await send_profile_card(viewer, profile, match_kb(partner))

# ================== RUN ==================
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
