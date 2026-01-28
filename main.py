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

# ---------- START ----------
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет 🤍\n\n"
        "Здесь можно найти тёплое общение и поддержку.\n"
        "Давайте познакомимся 🌱",
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
            [InlineKeyboardButton(text="👨‍🍼 Папа", callback_data="role_Папа")],
            [InlineKeyboardButton(text="🤍 Будущий родитель", callback_data="role_Будущий")],
            [InlineKeyboardButton(text="🌱 Ищу поддержку", callback_data="role_Поддержка")]
        ])
    )

@dp.callback_query(Profile.role)
async def role_chosen(call: CallbackQuery, state: FSMContext):
    await state.update_data(role=call.data.replace("role_", ""))
    await state.set_state(Profile.goal)
    await call.message.edit_text(
        "Что для вас сейчас важно?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚶‍♀️ Прогулки", callback_data="goal_Прогулки")],
            [InlineKeyboardButton(text="💬 Общение", callback_data="goal_Общение")],
            [InlineKeyboardButton(text="🤝 Всё вместе", callback_data="goal_Всё")]
        ])
    )

@dp.callback_query(Profile.goal)
async def goal_chosen(call: CallbackQuery, state: FSMContext):
    await state.update_data(goal=call.data.replace("goal_", ""))
    await state.set_state(Profile.child_age)
    await call.message.edit_text(
        "Возраст ребёнка (можно пропустить)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🤰 Ещё ждём", callback_data="age_Ждём")],
            [InlineKeyboardButton(text="👶 0–1", callback_data="age_0–1")],
            [InlineKeyboardButton(text="🧸 1–3", callback_data="age_1–3")],
            [InlineKeyboardButton(text="🏃 3–6", callback_data="age_3–6")],
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="age_skip")]
        ])
    )

@dp.callback_query(Profile.child_age)
async def age_chosen(call: CallbackQuery, state: FSMContext):
    age = call.data.replace("age_", "")
    await state.update_data(child_age=None if age == "skip" else age)
    await state.set_state(Profile.city)
    await call.message.edit_text("В каком городе вы находитесь?")

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
    await state.set_state(Profile.photo)
    await call.message.edit_text(
        "Хотите добавить фото?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📷 Добавить фото", callback_data="add_photo")],
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_photo")]
        ])
    )

@dp.message(Profile.about)
async def about_entered(message: Message, state: FSMContext):
    await state.update_data(about=message.text)
    await state.set_state(Profile.photo)
    await message.answer(
        "Хотите добавить фото?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📷 Добавить фото", callback_data="add_photo")],
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_photo")]
        ])
    )

# ---------- PHOTO ----------
@dp.callback_query(F.data == "add_photo", Profile.photo)
async def ask_photo(call: CallbackQuery):
    await call.message.edit_text("Отправьте одно фото 📷")

@dp.message(Profile.photo, F.photo)
async def photo_received(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await save_profile(message.from_user, state, photo_id)
    await after_create(message)

@dp.callback_query(F.data == "skip_photo", Profile.photo)
async def skip_photo(call: CallbackQuery, state: FSMContext):
    await save_profile(call.from_user, state, None)
    await after_create(call.message)

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
            data["child_age"],
            data["city"],
            data.get("about"),
            photo_id
        ))
        await db.commit()
    await state.clear()

async def after_create(message: Message):
    await message.answer(
        "🤍 Анкета создана",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👀 Смотреть анкеты", callback_data="browse")],
            [InlineKeyboardButton(text="✏️ Изменить анкету", callback_data="edit_profile")]
        ])
    )

# ---------- EDIT PROFILE ----------
@dp.callback_query(F.data == "edit_profile")
async def edit_menu(call: CallbackQuery, state: FSMContext):
    await state.set_state(EditProfile.menu)
    await call.message.edit_text(
        "Что хотите изменить?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📍 Город", callback_data="edit_city")],
            [InlineKeyboardButton(text="📝 О себе", callback_data="edit_about")],
            [InlineKeyboardButton(text="📷 Фото", callback_data="edit_photo")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="browse")]
        ])
    )

@dp.callback_query(F.data == "edit_city", EditProfile.menu)
async def edit_city(call: CallbackQuery, state: FSMContext):
    await state.set_state(EditProfile.city)
    await call.message.edit_text("Введите новый город 📍")

@dp.message(EditProfile.city)
async def save_city(message: Message, state: FSMContext):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE users SET city=? WHERE user_id=?",
            (message.text, message.from_user.id)
        )
        await db.commit()
    await state.clear()
    await message.answer("✅ Город обновлён")

@dp.callback_query(F.data == "edit_about", EditProfile.menu)
async def edit_about(call: CallbackQuery, state: FSMContext):
    await state.set_state(EditProfile.about)
    await call.message.edit_text("Напишите новый текст о себе 📝")

@dp.message(EditProfile.about)
async def save_about(message: Message, state: FSMContext):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE users SET about=? WHERE user_id=?",
            (message.text, message.from_user.id)
        )
        await db.commit()
    await state.clear()
    await message.answer("✅ Описание обновлено")

@dp.callback_query(F.data == "edit_photo", EditProfile.menu)
async def edit_photo(call: CallbackQuery, state: FSMContext):
    await state.set_state(EditProfile.photo)
    await call.message.edit_text("Отправьте новое фото 📷")

@dp.message(EditProfile.photo, F.photo)
async def save_new_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE users SET photo_id=? WHERE user_id=?",
            (photo_id, message.from_user.id)
        )
        await db.commit()
    await state.clear()
    await message.answer("✅ Фото обновлено")

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
        await bot.send_message(
            me,
            "🤍 Анкеты закончились\n\nМы подберём новых людей и сразу покажем тебе 🌱",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Проверить позже", callback_data="browse")]
            ])
        )
        return

    await send_profile(row[0], me)

async def send_profile(user_id: int, to_user: int):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT role, goal, city, about, photo_id FROM users WHERE user_id=?",
            (user_id,)
        )
        u = await cur.fetchone()

    role, goal, city, about, photo_id = u
    text = f"{role}\n📍 {city}\nИщу: {goal}\n\n{about or ''}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️", callback_data=f"like_{user_id}"),
            InlineKeyboardButton(text="👎", callback_data=f"skip_{user_id}")
        ]
    ])

    if photo_id:
        await bot.send_photo(to_user, photo_id, caption=text, reply_markup=kb)
    else:
        await bot.send_message(to_user, text, reply_markup=kb)

@dp.callback_query(F.data.startswith("skip_"))
async def skip(call: CallbackQuery):
    await browse(call)

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
        if await cur.fetchone():
            for a, b in [(from_user, to_user), (to_user, from_user)]:
                await bot.send_message(
                    a,
                    "💫 У вас взаимная симпатия",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="💬 Написать", url=f"tg://user?id={b}")]
                    ])
                )
        await db.commit()

    await browse(call)

# ---------- RUN ----------
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
