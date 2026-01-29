import asyncio
import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

TOKEN = os.getenv("BOT_TOKEN")
DB = "users.db"

bot = Bot(TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ---------- DATABASE ----------
async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            name TEXT,
            age TEXT,
            city TEXT,
            district TEXT,
            role TEXT,
            goal TEXT,
            child_age TEXT,
            about TEXT,
            photo_id TEXT
        )
        """)
        await db.commit()


# ---------- FSM ----------
class Profile(StatesGroup):
    name = State()
    age = State()
    city = State()
    district = State()
    role = State()
    goal = State()
    child_age = State()
    about = State()
    photo = State()


# ---------- START ----------
@dp.message(F.text == "/start")
async def start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Profile.name)
    await message.answer("Как вас зовут?")


# ---------- FORM ----------
@dp.message(Profile.name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Profile.age)
    await message.answer("Сколько вам лет?")


@dp.message(Profile.age)
async def get_age(message: Message, state: FSMContext):
    await state.update_data(age=message.text)
    await state.set_state(Profile.city)
    await message.answer("В каком городе вы живёте?")


@dp.message(Profile.city)
async def get_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(Profile.district)
    await message.answer(
        "Укажите район (если не хотите — пропустите)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_district")]
        ])
    )


@dp.callback_query(F.data == "skip_district", Profile.district)
async def skip_district(call: CallbackQuery, state: FSMContext):
    await state.update_data(district=None)
    await ask_role(call, state)


@dp.message(Profile.district)
async def get_district(message: Message, state: FSMContext):
    await state.update_data(district=message.text)
    await ask_role(message, state)


async def ask_role(target, state):
    await state.set_state(Profile.role)
    await target.answer(
        "Кто вы?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👩‍🍼 Мама", callback_data="role_Мама")],
            [InlineKeyboardButton(text="👨‍🍼 Папа", callback_data="role_Папа")]
        ])
    )


@dp.callback_query(F.data.startswith("role_"))
async def get_role(call: CallbackQuery, state: FSMContext):
    await state.update_data(role=call.data.replace("role_", ""))
    await state.set_state(Profile.goal)
    await call.message.edit_text(
        "Что вы ищете?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Общение", callback_data="goal_Общение")],
            [InlineKeyboardButton(text="🚶 Прогулки", callback_data="goal_Прогулки")],
            [InlineKeyboardButton(text="❤️ Отношения", callback_data="goal_Отношения")]
        ])
    )


@dp.callback_query(F.data.startswith("goal_"))
async def get_goal(call: CallbackQuery, state: FSMContext):
    await state.update_data(goal=call.data.replace("goal_", ""))
    await state.set_state(Profile.child_age)
    await call.message.edit_text("Возраст ребёнка?")


@dp.message(Profile.child_age)
async def get_child_age(message: Message, state: FSMContext):
    await state.update_data(child_age=message.text)
    await state.set_state(Profile.about)
    await message.answer("Напишите немного о себе")


@dp.message(Profile.about)
async def get_about(message: Message, state: FSMContext):
    await state.update_data(about=message.text)
    await state.set_state(Profile.photo)
    await message.answer("Отправьте одно фото 📸")


# ---------- PHOTO ----------
@dp.message(Profile.photo, F.photo)
async def get_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photo_id = message.photo[-1].file_id

    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            message.from_user.id,
            message.from_user.username,
            data["name"],
            data["age"],
            data["city"],
            data.get("district"),
            data["role"],
            data["goal"],
            data["child_age"],
            data["about"],
            photo_id
        ))
        await db.commit()

    await state.clear()
    await show_profile(message.from_user.id)


# ---------- SHOW PROFILE ----------
async def show_profile(user_id: int):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
        SELECT name, age, city, district, role, goal, about, photo_id
        FROM users WHERE user_id = ?
        """, (user_id,))
        row = await cur.fetchone()

    name, age, city, district, role, goal, about, photo_id = row

    text = (
        f"{name}, {age}\n"
        f"📍 {city}" + (f", {district}" if district else "") + "\n"
        f"{role}\n"
        f"Ищу: {goal}\n\n"
        f"{about}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👀 Смотреть анкеты", callback_data="browse")],
        [InlineKeyboardButton(text="✏️ Изменить анкету", callback_data="edit")]
    ])

    await bot.send_photo(user_id, photo_id, caption=text, reply_markup=kb)


# ---------- RUN ----------
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
