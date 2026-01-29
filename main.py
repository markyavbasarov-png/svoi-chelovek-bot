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

def browse_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="♥️", callback_data="like"),
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
        "«СвойЧеловек» — это про тепло и поддержку.\n\n"
        "Начнём знакомство?",
        reply_markup=start_kb()
    )

# ================== PROFILE CARD ==================
async def send_profile_card(chat_id: int, profile: tuple, kb):
    (
        user_id,
        username,
        name,
        age,
        city,
        role,
        goal,
        about,
        photo_id
    ) = profile

    text = (
        f"{role} {name}, {age} · 📍 {city}\n"
        f"Ищу: {goal}\n\n"
        f"{about or ''}"
    )

    if photo_id:
        await bot.send_photo(chat_id, photo_id, caption=text, reply_markup=kb)
    else:
        await bot.send_message(chat_id, text, reply_markup=kb)

# ================== LIKE / DISLIKE ==================
@dp.callback_query(F.data.in_(["like", "dislike"]))
async def like_dislike(call: CallbackQuery, state: FSMContext):
    await call.answer()

    # визуальное подтверждение
    await call.message.answer("♥️" if call.data == "like" else "❌")

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
            await notify_like(from_user, to_user)

    await show_next_profile(call, state)

# ================== NOTIFICATIONS ==================
async def notify_like(from_user: int, to_user: int):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT * FROM users WHERE user_id=?",
            (from_user,)
        )
        profile = await cur.fetchone()

    await bot.send_message(
        to_user,
        "💌 Ты кому-то понравился\nПосмотри, может это он или она 🤍"
    )
    await send_profile_card(to_user, profile, browse_kb())

async def notify_match(u1: int, u2: int):
    for viewer, partner in [(u1, u2), (u2, u1)]:
        async with aiosqlite.connect(DB) as db:
            cur = await db.execute(
                "SELECT * FROM users WHERE user_id=?",
                (partner,)
            )
            profile = await cur.fetchone()

        await bot.send_message(viewer, "💫 У вас взаимно")
        await send_profile_card(viewer, profile, match_kb(partner))

# ================== NEXT PROFILE (заглушка) ==================
async def show_next_profile(call: CallbackQuery, state: FSMContext):
    await call.message.answer("🔍 Ищу следующую анкету…")

# ================== RUN ==================
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
