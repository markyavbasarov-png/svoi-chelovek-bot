import asyncio
import logging
import os
import aiosqlite

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
AGE_RANGE = 5

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

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👀 Смотреть анкеты", callback_data="browse")],
        [InlineKeyboardButton(text="⚙️ Управление", callback_data="manage")]
    ])

def manage_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить анкету", callback_data="edit_profile")],
        [InlineKeyboardButton(text="📸 Изменить фото", callback_data="edit_photo")],
        [InlineKeyboardButton(text="📝 Изменить текст", callback_data="edit_about")],
        [InlineKeyboardButton(text="🗑 Удалить анкету", callback_data="delete_account")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
    ])

def confirm_delete_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❗ Да, удалить", callback_data="confirm_delete")],
        [InlineKeyboardButton(text="⬅️ Отмена", callback_data="back_to_menu")]
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

def photo_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Загрузить фото", callback_data="upload_photo")],
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_photo")]
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
        "Привет 🤍\n\nНачнём знакомство?",
        reply_markup=start_kb()
    )

# ================== MENU ==================
@dp.callback_query(F.data == "manage")
async def manage(call: CallbackQuery):
    await call.message.edit_text("Что хочешь изменить?", reply_markup=manage_kb())
    await call.answer()

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(call: CallbackQuery):
    await call.message.edit_text("Главное меню", reply_markup=main_menu_kb())
    await call.answer()

# ================== PROFILE CREATE / EDIT ==================
@dp.callback_query(F.data == "start_form")
@dp.callback_query(F.data == "edit_profile")
async def start_profile(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(Profile.name)
    await call.message.answer("Как тебя зовут?")

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
    await message.answer("Кто ты?", reply_markup=role_kb())

@dp.callback_query(F.data.startswith("role_"), Profile.role)
async def set_role(call: CallbackQuery, state: FSMContext):
    await state.update_data(role=call.data.replace("role_", ""))
    await state.set_state(Profile.goal)
    await call.message.edit_text("Что ищешь?", reply_markup=goal_kb())

@dp.callback_query(F.data.startswith("goal_"), Profile.goal)
async def set_goal(call: CallbackQuery, state: FSMContext):
    await state.update_data(goal=call.data.replace("goal_", ""))
    await state.set_state(Profile.about)
    await call.message.edit_text("Расскажи немного о себе 🤍")

@dp.message(Profile.about)
async def set_about(message: Message, state: FSMContext):
    await state.update_data(about=message.text)
    await state.set_state(Profile.photo)
    await message.answer("Добавить фото?", reply_markup=photo_kb())

@dp.callback_query(F.data == "upload_photo", Profile.photo)
async def upload_photo(call: CallbackQuery):
    await call.message.edit_text("Отправь фото 🤍")

@dp.message(Profile.photo, F.photo)
async def set_photo(message: Message, state: FSMContext):
    await save_profile(message.from_user, state, message.photo[-1].file_id)
    await send_my_profile(message.from_user.id)

@dp.callback_query(F.data == "skip_photo", Profile.photo)
async def skip_photo(call: CallbackQuery, state: FSMContext):
    await save_profile(call.from_user, state, None)
    await send_my_profile(call.from_user.id)

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

# ================== PROFILE VIEW ==================
async def send_profile_card(chat_id, profile, kb):
    uid, name, age, city, role, goal, about, photo_id = profile
    text = f"{role} {name}, {age} · 📍 {city}\n🔍 {goal}\n\n{about or ''}"
    if photo_id:
        await bot.send_photo(chat_id, photo_id, caption=text, reply_markup=kb)
    else:
        await bot.send_message(chat_id, text, reply_markup=kb)

async def send_my_profile(user_id):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
        SELECT user_id, name, age, city, role, goal, about, photo_id
        FROM users WHERE user_id = ?
        """, (user_id,))
        profile = await cur.fetchone()
    if profile:
        await send_profile_card(user_id, profile, main_menu_kb())

# ================== BROWSE ==================
@dp.callback_query(F.data == "browse")
async def browse(call: CallbackQuery, state: FSMContext):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT age, city FROM users WHERE user_id = ?", (call.from_user.id,))
        me = await cur.fetchone()

    if not me:
        await call.message.answer("Сначала создай анкету 🤍", reply_markup=start_kb())
        return

    my_age, my_city = me

    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
        SELECT user_id, name, age, city, role, goal, about, photo_id
        FROM users
        WHERE city = ?
        AND age BETWEEN ? AND ?
        AND user_id != ?
        AND user_id NOT IN (
            SELECT to_user FROM likes WHERE from_user = ?
        )
        ORDER BY RANDOM()
        LIMIT 1
        """, (
            my_city,
            my_age - AGE_RANGE,
            my_age + AGE_RANGE,
            call.from_user.id,
            call.from_user.id
        ))
        profile = await cur.fetchone()

    if not profile:
        await call.message.answer(
            "💫 Анкет пока нет\nМы обязательно подберём кого-то 🤍",
            reply_markup=main_menu_kb()
        )
        return

    await state.update_data(current_profile_id=profile[0])
    await send_profile_card(call.from_user.id, profile, browse_kb())

# ================== LIKES + MATCH ==================
@dp.callback_query(F.data.in_(["like", "dislike"]))
async def like_dislike(call: CallbackQuery, state: FSMContext):
    await call.answer()
    data = await state.get_data()
    to_user = data.get("current_profile_id")

    if not to_user:
        return

    if call.data == "like":
        async with aiosqlite.connect(DB) as db:
            await db.execute(
                "INSERT OR IGNORE INTO likes VALUES (?, ?)",
                (call.from_user.id, to_user)
            )
            await db.commit()

            await bot.send_message(to_user, "💖 Тебя лайкнули!")

            cur = await db.execute(
                "SELECT 1 FROM likes WHERE from_user = ? AND to_user = ?",
                (to_user, call.from_user.id)
            )
            if await cur.fetchone():
                await notify_match(call.from_user.id, to_user)

    await browse(call, state)

async def notify_match(u1, u2):
    for viewer, partner in [(u1, u2), (u2, u1)]:
        async with aiosqlite.connect(DB) as db:
            cur = await db.execute("""
            SELECT user_id, name, age, city, role, goal, about, photo_id
            FROM users WHERE user_id = ?
            """, (partner,))
            profile = await cur.fetchone()

        await bot.send_message(viewer, "🤍 У вас взаимная симпатия!")
        await send_profile_card(viewer, profile, match_kb(partner))

# ================== DELETE ==================
@dp.callback_query(F.data == "delete_account")
async def delete_account(call: CallbackQuery):
    await call.message.edit_text(
        "Ты уверен(а), что хочешь удалить анкету?",
        reply_markup=confirm_delete_kb()
    )

@dp.callback_query(F.data == "confirm_delete")
async def confirm_delete(call: CallbackQuery):
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM users WHERE user_id = ?", (call.from_user.id,))
        await db.execute("DELETE FROM likes WHERE from_user = ? OR to_user = ?", (call.from_user.id, call.from_user.id))
        await db.commit()

    await call.message.edit_text(
        "Анкета удалена 🤍\nЕсли захочешь — мы всегда рядом.",
        reply_markup=start_kb()
    )

# ================== RUN ==================
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
