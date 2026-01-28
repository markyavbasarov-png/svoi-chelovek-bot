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
            name TEXT,
            district TEXT,
            role TEXT,
            goal TEXT,
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
    name = State()
    district = State()
    role = State()
    goal = State()
    city = State()
    about = State()
    photos = State()

# ---------- START ----------
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет 🤍\nДавайте создадим анкету 🌱",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Начать", callback_data="start_form")]
        ])
    )

# ---------- PROFILE ----------
@dp.callback_query(F.data == "start_form")
async def start_form(call: CallbackQuery, state: FSMContext):
    await state.set_state(Profile.name)
    await call.message.edit_text("Как вас зовут?")

@dp.message(Profile.name)
async def name_entered(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Profile.district)
    await message.answer(
        "Ваш район (если есть)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_district")]
        ])
    )

@dp.callback_query(F.data == "skip_district", Profile.district)
async def skip_district(call: CallbackQuery, state: FSMContext):
    await state.update_data(district=None)
    await ask_role(call.message, state)

@dp.message(Profile.district)
async def district_entered(message: Message, state: FSMContext):
    await state.update_data(district=message.text)
    await ask_role(message, state)

async def ask_role(message, state):
    await state.set_state(Profile.role)
    await message.answer(
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
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_about")]
        ])
    )

@dp.callback_query(F.data == "skip_about", Profile.about)
async def skip_about(call: CallbackQuery, state: FSMContext):
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
        return

    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)

    if len(photos) == MAX_PHOTOS:
        await finish_profile(message.from_user, state)
        await show_preview(message.from_user.id)

@dp.callback_query(F.data == "skip_photos", Profile.photos)
async def skip_photos(call: CallbackQuery, state: FSMContext):
    await finish_profile(call.from_user, state)
    await show_preview(call.from_user.id)

# ---------- SAVE ----------
async def finish_profile(user, state):
    data = await state.get_data()
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user.id,
            user.username,
            data["name"],
            data.get("district"),
            data["role"],
            data["goal"],
            data["city"],
            data.get("about")
        ))
        await db.execute("DELETE FROM photos WHERE user_id=?", (user.id,))
        for pid in data.get("photos", []):
            await db.execute("INSERT INTO photos VALUES (?, ?)", (user.id, pid))
        await db.commit()
    await state.clear()

# ---------- PREVIEW ----------
async def show_preview(user_id: int):
    await bot.send_message(
        user_id,
        "👀 ПРЕДПРОСМОТР АНКЕТЫ",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👀 Смотреть анкеты", callback_data="browse")],
            [InlineKeyboardButton(text="✏️ Изменить анкету", callback_data="start_form")]
        ])
    )

# ---------- SEND PROFILE ----------
async def send_profile(user_id: int, to_user: int):
    async with aiosqlite.connect(DB) as db:
        u = await (await db.execute(
            "SELECT name, district, role, goal, city, about FROM users WHERE user_id=?",
            (user_id,))
        ).fetchone()

        photos = [p[0] for p in await (await db.execute(
            "SELECT photo_id FROM photos WHERE user_id=?", (user_id,))
        ).fetchall()]

    name, district, role, goal, city, about = u
    header = f"{name}"
    if district:
        header += f" • {district}"

    text = f"{header}\n{role}\n📍 {city}\nИщу: {goal}\n\n{about or ''}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❤️", callback_data=f"like_{user_id}"),
         InlineKeyboardButton(text="👎", callback_data=f"skip_{user_id}")]
    ])

    if photos:
        media = [InputMediaPhoto(media=photos[0], caption=text)]
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
        row = await (await db.execute("""
            SELECT user_id FROM users
            WHERE user_id != ?
            AND user_id NOT IN (
                SELECT to_user FROM likes WHERE from_user=?
            )
            ORDER BY RANDOM() LIMIT 1
        """, (me, me))).fetchone()

    if not row:
        await call.message.answer("🤍 Анкеты закончились\nМы подберём новых 🌱")
        return

    await send_profile(row[0], me)

# ---------- LIKE ----------
@dp.callback_query(F.data.startswith("like_"))
async def like(call: CallbackQuery):
    from_user = call.from_user.id
    to_user = int(call.data.split("_")[1])

    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR IGNORE INTO likes VALUES (?, ?)",
            (from_user, to_user)
        )
        cur = await db.execute(
            "SELECT 1 FROM likes WHERE from_user=? AND to_user=?",
            (to_user, from_user)
        )
        mutual = await cur.fetchone()
        await db.commit()

    if mutual:
        for a, b in [(from_user, to_user), (to_user, from_user)]:
            await bot.send_message(
                a,
                "💫 У вас взаимная симпатия",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💬 Написать", url=f"tg://user?id={b}")]
                ])
            )
    else:
        await bot.send_message(
            to_user,
            "💌 Кому-то вы понравились\n\n"
            "Загляните в анкеты — возможно, это взаимно 🤍",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👀 Смотреть анкеты", callback_data="browse")]
            ])
        )

    await browse(call)

@dp.callback_query(F.data.startswith("skip_"))
async def skip(call: CallbackQuery):
    await browse(call)

# ---------- RUN ----------
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
