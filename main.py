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
        "Ты не случайно здесь.\n"
        "«свойЧеловек» — это про тепло и поддержку.\n\n"
        "Начнём знакомство?",
        reply_markup=start_kb()
    )

@dp.callback_query(F.data == "start_form")
async def start_form(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.answer("Как тебя зовут?")
    await state.set_state(Profile.name)

# ================== FSM FLOW ==================
@dp.message(Profile.name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Сколько тебе лет?")
    await state.set_state(Profile.age)

@dp.message(Profile.age)
async def get_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Введи возраст числом 🙂")
    await state.update_data(age=int(message.text))
    await message.answer("Из какого ты города?")
    await state.set_state(Profile.city)

@dp.message(Profile.city)
async def get_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await message.answer("Кто ты?", reply_markup=role_kb())
    await state.set_state(Profile.role)

@dp.callback_query(Profile.role, F.data.startswith("role_"))
async def get_role(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.update_data(role=call.data.replace("role_", ""))
    await call.message.answer("Что ты ищешь?", reply_markup=goal_kb())
    await state.set_state(Profile.goal)

@dp.callback_query(Profile.goal, F.data.startswith("goal_"))
async def get_goal(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.update_data(goal=call.data.replace("goal_", ""))
    await call.message.answer("Хочешь рассказать о себе?", reply_markup=skip_about_kb())
    await state.set_state(Profile.about)

@dp.message(Profile.about)
async def get_about(message: Message, state: FSMContext):
    await state.update_data(about=message.text)
    await message.answer("Добавим фото?", reply_markup=photo_kb())
    await state.set_state(Profile.photo
