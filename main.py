import asyncio
import logging
import os
import aiosqlite

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
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
            name TEXT,
            age INTEGER,
            city TEXT,
            goal TEXT,
            time TEXT,
            child_age INTEGER,
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
class Form(StatesGroup):
    name = State()
    age = State()
    city = State()
    goal = State()
    time = State()
    child_age = State()
    about = State()
    photo = State()

# ================= KEYBOARDS =================
def start_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Давай 💫", callback_data="start")]
    ])

def goal_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚶 Прогулки", callback_data="goal_Прогулки")],
        [InlineKeyboardButton(text="💬 Общение", callback_data="goal_Общение")]
    ])

def time_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌅 Утро", callback_data="time_Утро")],
        [InlineKeyboardButton(text="🌞 День", callback_data="time_День")],
        [InlineKeyboardButton(text="🌙 Вечер", callback_data="time_Вечер")]
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

# ================= START =================
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Здесь ищут не идеальных,\nа своих 🤍\n\nНачнём?",
        reply_markup=start_kb()
    )

@dp.callback_query(F.data == "start")
async def start_form(call: CallbackQuery, state: FSMContext):
    await state.set_state(Form.name)
    await call.message.edit_text("Как тебя зовут?")

# ================= FORM =================
@dp.message(Form.name)
async def name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Form.age)
    await message.answer("Сколько тебе лет?")

@dp.message(Form.age)
async def age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Возраст цифрами")
    await state.update_data(age=int(message.text))
    await state.set_state(Form.city)
    await message.answer("Город?")

@dp.message(Form.city)
async def city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(Form.goal)
    await message.answer("Что ищешь?", reply_markup=goal_kb())

@dp.callback_query(F.data.startswith("goal_"), Form.goal)
async def goal(call: CallbackQuery, state: FSMContext):
    await state.update_data(goal=call.data.replace("goal_", ""))
    await state.set_state(Form.time)
    await call.message.edit_text("Когда чаще гуляешь?", reply_markup=time_kb())

@dp.callback_query(F.data.startswith("time_"), Form.time)
async def time(call: CallbackQuery, state: FSMContext):
    await state.update_data(time=call.data.replace("time_", ""))
    await state.set_state(Form.child_age)
    await call.message.edit_text("Возраст ребёнка?")

@dp.message(Form.child_age)
async def child_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Цифрами")
    await state.update_data(child_age=int(message.text))
    await state.set_state(Form.about)
    await message.answer("Пару слов о себе 🤍", reply_markup=skip_about_kb())

@dp.callback_query(F.data == "skip_about", Form.about)
async def skip_about(call: CallbackQuery, state: FSMContext):
    await state.update_data(about=None)
    await state.set_state(Form.photo)
    await call.message.edit_text("Фото можно добавить или пропустить", reply_markup=photo_kb())

@dp.message(Form.about)
async def about(message: Message, state: FSMContext):
    await state.update_data(about=message.text)
    await state.set_state(Form.photo)
    await message.answer("Фото?", reply_markup=photo_kb())

@dp.callback_query(F.data == "skip_photo", Form.photo)
async def skip_photo(call: CallbackQuery, state: FSMContext):
    await save_profile(call.from_user.id, state, None)
    await send_my_profile(call.from_user.id)

@dp.message(Form.photo, F.photo)
async def photo(message: Message, state: FSMContext):
    await save_profile(message.from_user.id, state, message.photo[-1].file_id)
    await send_my_profile(message.from_user.id)

# ================= SAVE / SHOW =================
async def save_profile(user_id, state, photo_id):
    data = await state.get_data()
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            data["name"],
            data["age"],
            data["city"],
            data["goal"],
            data["time"],
            data["child_age"],
            data.get("about"),
            photo_id
        ))
        await db.commit()
    await state.clear()

async def send_my_profile(user_id):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        u = await cur.fetchone()

    text = (
        f"{u[1]}, {u[2]} · {u[3]}\n"
        f"🎯 {u[4]} · ⏰ {u[5]}\n"
        f"👶 {u[6]} лет\n\n"
        f"{u[7] or ''}"
    )

    if u[8]:
        await bot.send_photo(user_id, u[8], caption=text, reply_markup=my_profile_kb())
    else:
        await bot.send_message(user_id, text, reply_markup=my_profile_kb())

# ================= BROWSE =================
@dp.callback_query(F.data == "browse")
async def browse(call: CallbackQuery, state: FSMContext):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
        SELECT * FROM users
        WHERE user_id != ?
        AND user_id NOT IN (
            SELECT to_user FROM likes WHERE from_user = ?
        )
        ORDER BY RANDOM() LIMIT 1
        """, (call.from_user.id, call.from_user.id))
        u = await cur.fetchone()

    if not u:
        return await call.message.answer("Анкет пока нет 🤍")

    await state.update_data(current=u[0])
    text = (
        f"{u[1]}, {u[2]} · {u[3]}\n"
        f"🎯 {u[4]} · ⏰ {u[5]}\n"
        f"👶 {u[6]} лет\n\n"
        f"{u[7] or ''}"
    )

    if u[8]:
        await bot.send_photo(call.from_user.id, u[8], caption=text, reply_markup=browse_kb())
    else:
        await bot.send_message(call.from_user.id, text, reply_markup=browse_kb())

@dp.callback_query(F.data.in_(["like", "dislike"]))
async def like(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    to_user = data.get("current")

    if call.data == "like":
        async with aiosqlite.connect(DB) as db:
            await db.execute("INSERT OR IGNORE INTO likes VALUES (?, ?)",
                             (call.from_user.id, to_user))
            await db.commit()

    await browse(call, state)

# ================= RUN =================
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
