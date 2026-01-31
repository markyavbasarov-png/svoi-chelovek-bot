import asyncio
import logging
import os
import math
import aiosqlite
from datetime import datetime, timedelta

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
SEARCH_RADIUS_KM = 30

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
            lat REAL,
            lon REAL
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            from_user INTEGER,
            to_user INTEGER,
            created_at TEXT,
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
    location = State()

# ================= HELPERS =================
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# ================= KEYBOARDS =================
def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👀 Смотреть анкеты", callback_data="browse")],
        [InlineKeyboardButton(text="⚙️ Управление", callback_data="manage")]
    ])

def manage_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить анкету", callback_data="edit_profile")],
        [InlineKeyboardButton(text="📸 Изменить фото", callback_data="edit_photo")],
        [InlineKeyboardButton(text="💬 Изменить текст", callback_data="edit_about")],
        [InlineKeyboardButton(text="🗑 Удалить анкету", callback_data="delete_confirm")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")]
    ])

def confirm_delete_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Нет", callback_data="back_menu")],
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data="delete_account")]
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

# ================= START =================
@dp.message(CommandStart())
@dp.message(Command("myprofile"))
async def reset_and_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню 👇", reply_markup=main_menu_kb())

# ================= MANAGE =================
@dp.callback_query(F.data == "manage")
async def manage(call: CallbackQuery):
    await call.message.edit_text("Управление анкетой ⚙️", reply_markup=manage_kb())

@dp.callback_query(F.data == "back_menu")
async def back_menu(call: CallbackQuery):
    await call.message.edit_text("Главное меню 👇", reply_markup=main_menu_kb())

# ================= DELETE =================
@dp.callback_query(F.data == "delete_confirm")
async def delete_confirm(call: CallbackQuery):
    await call.message.edit_text(
        "Ты уверена, что хочешь удалить анкету?",
        reply_markup=confirm_delete_kb()
    )

@dp.callback_query(F.data == "delete_account")
async def delete_account(call: CallbackQuery):
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM users WHERE user_id = ?", (call.from_user.id,))
        await db.execute("DELETE FROM likes WHERE from_user = ? OR to_user = ?", (call.from_user.id, call.from_user.id))
        await db.commit()
    await call.message.edit_text("Анкета удалена 🤍")

# ================= BROWSE =================
@dp.callback_query(F.data == "browse")
async def browse(call: CallbackQuery, state: FSMContext):
    await show_next_profile(call, state)

async def show_next_profile(call: CallbackQuery, state: FSMContext):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT lat, lon FROM users WHERE user_id = ?", (call.from_user.id,))
        me = await cur.fetchone()
        if not me or not me[0]:
            await call.message.answer("Нужно отправить геолокацию 📍")
            return

        my_lat, my_lon = me

        cur = await db.execute("""
        SELECT user_id, name, age, city, role, goal, about, photo_id, lat, lon
        FROM users WHERE user_id != ?
        """, (call.from_user.id,))
        users = await cur.fetchall()

    for u in users:
        dist = haversine(my_lat, my_lon, u[8], u[9])
        if dist <= SEARCH_RADIUS_KM:
            await state.update_data(current_profile_id=u[0])
            await send_profile_card(call.from_user.id, u[:8], browse_kb())
            return

    await call.message.answer("Пока нет анкет поблизости 🤍", reply_markup=main_menu_kb())

# ================= LIKES =================
@dp.callback_query(F.data.in_(["like", "dislike"]))
async def like_dislike(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    to_user = data.get("current_profile_id")

    if not to_user:
        return

    if call.data == "like":
        async with aiosqlite.connect(DB) as db:
            await db.execute(
                "INSERT OR IGNORE INTO likes VALUES (?, ?, ?)",
                (call.from_user.id, to_user, datetime.utcnow().isoformat())
            )
            await db.commit()

            cur = await db.execute(
                "SELECT 1 FROM likes WHERE from_user = ? AND to_user = ?",
                (to_user, call.from_user.id)
            )
            mutual = await cur.fetchone()

        if mutual:
            await notify_match(call.from_user.id, to_user)
        else:
            await bot.send_message(to_user, "💌 Кому-то понравилась твоя анкета")

    await show_next_profile(call, state)

async def notify_match(u1, u2):
    for viewer, partner in [(u1, u2), (u2, u1)]:
        await bot.send_message(viewer, "🤍 У вас взаимная симпатия!")
        await send_profile_card(viewer, await get_profile(partner), match_kb(partner))

# ================= PROFILE RENDER =================
async def get_profile(user_id):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
        SELECT user_id, name, age, city, role, goal, about, photo_id
        FROM users WHERE user_id = ?
        """, (user_id,))
        return await cur.fetchone()

async def send_profile_card(chat_id, profile, kb):
    uid, name, age, city, role, goal, about, photo_id = profile
    text = f"{role} {name}, {age} · 📍 {city}\n🔍 {goal}\n\n{about or ''}"
    if photo_id:
        await bot.send_photo(chat_id, photo_id, caption=text, reply_markup=kb)
    else:
        await bot.send_message(chat_id, text, reply_markup=kb)

# ================= RUN =================
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
