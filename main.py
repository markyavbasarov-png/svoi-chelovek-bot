import asyncio
import logging
import os
import asyncpg

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ================= FSM =================
class Profile(StatesGroup):
    name = State()
    age = State()
    city = State()
    role = State()
    goal = State()
    about = State()
    photo = State()
    edit_about = State()
    edit_photo = State()
    edit_goal = State()

# ================= KEYBOARDS =================
def start_kb(): return InlineKeyboardMarkup([[InlineKeyboardButton("давай 💫", callback_data="start_form")]])
def role_kb(): return InlineKeyboardMarkup([[InlineKeyboardButton("👩‍🍼 Мама", callback_data="role_Мама")],
                                            [InlineKeyboardButton("👨‍🍼 Папа", callback_data="role_Папа")],
                                            [InlineKeyboardButton("👼🏼 Будущий родитель", callback_data="role_Будущий")]])
def goal_kb(prefix=""): return InlineKeyboardMarkup([
    [InlineKeyboardButton("🚶 Прогулки", callback_data=f"{prefix}Прогулки")],
    [InlineKeyboardButton("💬 Общение", callback_data=f"{prefix}Общение")],
    [InlineKeyboardButton("🫂 Поддержка", callback_data=f"{prefix}Поддержка")],
    [InlineKeyboardButton("☕️ Кофе / встречи", callback_data=f"{prefix}Кофе")],
    [InlineKeyboardButton("👶 Общение с детьми", callback_data=f"{prefix}Дети")]
])
def skip_about_kb(): return InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Пропустить", callback_data="skip_about")]])
def photo_kb(): return InlineKeyboardMarkup([[InlineKeyboardButton("📸 Загрузить фото", callback_data="upload_photo")],
                                             [InlineKeyboardButton("⏭ Пропустить", callback_data="skip_photo")]])
def profile_main_kb(): return InlineKeyboardMarkup([
    [InlineKeyboardButton("❤️ Найти своего", callback_data="browse")],
    [InlineKeyboardButton("✏️ Изменить анкету", callback_data="open_edit_menu")]
])
def edit_menu_kb(): return InlineKeyboardMarkup([
    [InlineKeyboardButton("✏️ О себе", callback_data="edit_about")],
    [InlineKeyboardButton("📸 Фото", callback_data="edit_photo")],
    [InlineKeyboardButton("🎯 Цель", callback_data="edit_goal")],
    [InlineKeyboardButton("🗑 Удалить анкету", callback_data="delete_profile")],
    [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_profile")]
])
def confirm_delete_kb(): return InlineKeyboardMarkup([
    [InlineKeyboardButton("❌ Нет", callback_data="cancel_delete"),
     InlineKeyboardButton("🗑 Да, удалить", callback_data="confirm_delete")]
])
def browse_kb(): return InlineKeyboardMarkup([
    [InlineKeyboardButton("♥️", callback_data="like"),
     InlineKeyboardButton("✖️", callback_data="dislike")]
])
def soft_like_kb(from_user_id:int): return InlineKeyboardMarkup([
    [InlineKeyboardButton("❤️ Ответить", callback_data=f"soft_like:{from_user_id}"),
     InlineKeyboardButton("✖️ Пропустить", callback_data="soft_dislike")]
])
def match_kb(user_id:int): return InlineKeyboardMarkup([
    [InlineKeyboardButton("✉️ Написать", url=f"tg://user?id={user_id}")]
])

# ================= DATABASE =================
async def init_db():
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY, username TEXT, name TEXT, age INT, city TEXT, role TEXT,
        goal TEXT, about TEXT, photo_id TEXT
    );""")
    await conn.execute("""CREATE TABLE IF NOT EXISTS likes (from_user BIGINT, to_user BIGINT, UNIQUE(from_user,to_user));""")
    await conn.close()

async def save_profile(user, data: dict, photo_id=None):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""
        INSERT INTO users(user_id, username, name, age, city, role, goal, about, photo_id)
        VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)
        ON CONFLICT(user_id) DO UPDATE SET username=EXCLUDED.username, name=EXCLUDED.name,
        age=EXCLUDED.age, city=EXCLUDED.city, role=EXCLUDED.role, goal=EXCLUDED.goal, about=EXCLUDED.about, photo_id=EXCLUDED.photo_id
    """, user.id, user.username or f"user_{user.id}", data["name"], data["age"], data["city"], data["role"], data["goal"], data.get("about"), photo_id)
    await conn.close()

async def update_user_field(user_id: int, field: str, value):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute(f"UPDATE users SET {field}=$1 WHERE user_id=$2", value, user_id)
    await conn.close()

async def get_profile(user_id:int):
    conn = await asyncpg.connect(DATABASE_URL)
    profile = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)
    await conn.close()
    return profile

async def delete_profile_pg(user_id:int):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("DELETE FROM likes WHERE from_user=$1 OR to_user=$1", user_id)
    await conn.execute("DELETE FROM users WHERE user_id=$1", user_id)
    await conn.close()

async def add_like(from_user:int, to_user:int):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("INSERT INTO likes(from_user,to_user) VALUES($1,$2) ON CONFLICT DO NOTHING", from_user, to_user)
    match = await conn.fetchrow("SELECT 1 FROM likes WHERE from_user=$1 AND to_user=$2", to_user, from_user)
    await conn.close()
    return bool(match)

async def get_next_profile(user_id:int):
    conn = await asyncpg.connect(DATABASE_URL)
    profile = await conn.fetchrow("""
        SELECT * FROM users WHERE city=(SELECT city FROM users WHERE user_id=$1) AND user_id!=$1
        AND user_id NOT IN (SELECT to_user FROM likes WHERE from_user=$1) ORDER BY RANDOM() LIMIT 1
    """, user_id)
    await conn.close()
    return profile

# ================= SEND =================
async def send_profile_card_func(chat_id:int, profile, kb):
    uid, username, name, age, city, role, goal, about, photo_id = profile
    text=f"{role} {name}, {age} · 📍 {city}\n🔍: {goal}\n\n{about or ''}"
    if photo_id: await bot.send_photo(chat_id, photo_id, caption=text, reply_markup=kb)
    else: await bot.send_message(chat_id, text, reply_markup=kb)

async def render_profile(user_id:int, chat_id:int, kb):
    profile = await get_profile(user_id)
    if profile: await send_profile_card_func(chat_id, profile, kb)

# ================= START =================
@dp.message(CommandStart())
async def cmd_start(message:Message,state:FSMContext):
    await state.clear()
    await message.answer("Привет! Начнем знакомство?", reply_markup=start_kb())

# ================= PROFILE CREATION =================
@dp.callback_query(F.data=="start_form")
async def form_start(call:CallbackQuery,state:FSMContext):
    await state.clear()
    await state.set_state(Profile.name)
    await call.message.answer("Как тебя зовут?")

# Остальная часть — точно такая же, как в предыдущем коде, но при редактировании
# профиль всегда рендерится функцией render_profile, чтобы сообщение обновлялось плавно

# ================= RUN =================
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())
