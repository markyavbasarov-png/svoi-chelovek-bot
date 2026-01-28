import asyncio
import logging
import aiosqlite
import os

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    InputMediaPhoto
)
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
bot = Bot(TOKEN)
dp = Dispatcher()

DB = "db.sqlite3"
MAX_PHOTOS = 3

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
            about TEXT
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS photos (
            user_id INTEGER,
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
    photos = State()

# ---------- START ----------
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет 🤍\n\nДавайте создадим анкету 🌱",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Начать", callback_data="start_form")]
        ])
    )

# ---------- PROFILE ----------
@dp.callback_query(F.data == "start_form")
async def start_form(call: CallbackQuery, state: FSMContext):
    await state.set_state(Profile.role)
    await call.message.edit_text(
        "Кто вы?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👩‍🍼 Мама", callback_data="role_Мама")],
            [InlineKeyboardButton(text="👨‍🍼 Папа", callback_data="role_Папа")],
            [InlineKeyboardButton(text="🌱 Ищу поддержку", callback_data="role_Поддержка")]
        ])
    )

@dp.callback_query(Profile.role)
async def role_chosen(call: CallbackQuery, state: FSMContext):
    await state.update_data(role=call.data.replace("role_", ""))
    await state.set_state(Profile.goal)
    await call.message.edit_text(
        "Что вы ищете?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Общение", callback_data="goal_Общение")],
            [InlineKeyboardButton(text="🚶‍♀️ Прогулки", callback_data="goal_Прогулки")],
            [InlineKeyboardButton(text="🤝 Всё вместе", callback_data="goal_Всё")]
        ])
    )

@dp.callback_query(Profile.goal)
async def goal_chosen(call: CallbackQuery, state: FSMContext):
    await state.update_data(goal=call.data.replace("goal_", ""))
    await state.set_state(Profile.city)
    await call.message.edit_text("В каком городе вы?")

@dp.message(Profile.city)
async def city_entered(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(Profile.about)
    await message.answer(
        "Пару слов о себе",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="about_skip")]
        ])
    )

@dp.callback_query(F.data == "about_skip", Profile.about)
async def about_skip(call: CallbackQuery, state: FSMContext):
    await state.update_data(about=None)
    await start_photos(call.message, state)

@dp.message(Profile.about)
async def about_entered(message: Message, state: FSMContext):
    await state.update_data(about=message.text)
    await start_photos(message, state)

# ---------- PHOTOS ----------
async def start_photos(message: Message, state: FSMContext):
    await state.set_state(Profile.photos)
    await state.update_data(photos=[])
    await message.answer(
        "Добавьте до 3 фото 📷\nМожно отправлять по одному",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_photos")]
        ])
    )

@dp.message(Profile.photos, F.photo)
async def photo_received(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])

    if len(photos) >= MAX_PHOTOS:
        await message.answer("Можно добавить максимум 3 фото 📸")
        return

    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)

    if len(photos) < MAX_PHOTOS:
        await message.answer(f"Фото {len(photos)}/{MAX_PHOTOS} добавлено")
    else:
        await finish_profile(message.from_user, state)
        await message.answer("🤍 Анкета создана",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👀 Смотреть анкеты", callback_data="browse")]
            ])
        )

@dp.callback_query(F.data == "skip_photos", Profile.photos)
async def skip_photos(call: CallbackQuery, state: FSMContext):
    await finish_profile(call.from_user, state)
    await call.message.edit_text(
        "🤍 Анкета создана",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👀 Смотреть анкеты", callback_data="browse")]
        ])
    )

async def finish_profile(user, state):
    data = await state.get_data()
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user.id,
            user.username,
            data["role"],
            data["goal"],
            None,
            data["city"],
            data.get("about")
        ))
        await db.execute("DELETE FROM photos WHERE user_id=?", (user.id,))
        for pid in data.get("photos", []):
            await db.execute(
                "INSERT INTO photos VALUES (?, ?)",
                (user.id, pid)
            )
        await db.commit()
    await state.clear()

# ---------- SEND PROFILE ----------
async def send_profile(user_id: int, to_user: int):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT role, goal, city, about FROM users WHERE user_id=?",
            (user_id,)
        )
        user = await cur.fetchone()

        cur = await db.execute(
            "SELECT photo_id FROM photos WHERE user_id=?",
            (user_id,)
        )
        photos = [p[0] for p in await cur.fetchall()]

    role, goal, city, about = user
    text = f"{role}\n📍 {city}\nИщу: {goal}\n\n{about or ''}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️", callback_data=f"like_{user_id}"),
            InlineKeyboardButton(text="👎", callback_data=f"skip_{user_id}")
        ]
    ])

    if photos:
        media = [
            InputMediaPhoto(media=photos[0], caption=text)
        ]
        for p in photos[1:]:
            media.append(InputMediaPhoto(media=p))

        await bot.send_media_group(to_user, media)
        await bot.send_message(to_user, " ", reply_markup=kb)
    else:
        await bot.send_message(to_user, text, reply_markup=kb)

# ---------- BROWSE ----------
@dp.callback_query(F.data == "browse")
async def browse(call: CallbackQuery):
    me = call.from_user.id
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
        SELECT user_id FROM users
        WHERE user_id != ?
        AND user_id NOT IN (
            SELECT to_user FROM likes WHERE from_user=?
        )
        ORDER BY RANDOM() LIMIT 1
        """, (me, me))
        row = await cur.fetchone()

    if not row:
        await call.message.answer(
            "🤍 Анкеты закончились\nМы подберём новых 🌱"
        )
        return

    await send_profile(row[0], me)

@dp.callback_query(F.data.startswith("skip_"))
async def skip(call: CallbackQuery):
    await browse(call)

@dp.callback_query(F.data.startswith("like_"))
async def like(call: CallbackQuery):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR IGNORE INTO likes VALUES (?, ?)",
            (call.from_user.id, int(call.data.split("_")[1]))
        )
        await db.commit()
    await browse(call)

# ---------- RUN ----------
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
