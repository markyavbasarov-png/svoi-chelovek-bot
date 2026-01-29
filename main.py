import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from repository import add_like, get_next_profile, get_profile

TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

bot = Bot(TOKEN)
dp = Dispatcher()

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
        [InlineKeyboardButton(text="🌱 Будущий родитель", callback_data="role_Будущий")]
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
        [InlineKeyboardButton(text="👀 Смотреть анкеты", callback_data="browse")],
        [InlineKeyboardButton(text="✏️ Изменить анкету", callback_data="edit_profile")]
    ])

def like_kb():
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

# ================== START ==================
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет, 🤍\n\n"
        "«свойЧеловек» — это про тепло и поддержку.\n\n"
        "Начнём знакомство?",
        reply_markup=start_kb()
    )

# ================== BROWSE ==================
@dp.callback_query(F.data == "browse")
async def browse(call: CallbackQuery, state: FSMContext):
    await show_next_profile(call, state)

async def show_next_profile(call: CallbackQuery, state: FSMContext):
    profile = await get_next_profile(call.from_user.id)

    if not profile:
        await call.message.answer(
            "Анкеты закончились 🤍\nВ вашем городе больше нет новых людей",
            reply_markup=main_menu_kb()
        )
        return

    user_id, name, age, city, goal, photo_id = profile
    await state.update_data(current_profile_id=user_id)

    text = (
        f"{name}, {age} · 📍 {city}\n"
        f"{goal}"
    )

    if photo_id:
        await call.message.answer_photo(
            photo_id,
            caption=text,
            reply_markup=like_kb()
        )
    else:
        await call.message.answer(
            text,
            reply_markup=like_kb()
        )

# ================== LIKES + SOFT MATCH ==================
@dp.callback_query(F.data.in_(["like", "dislike"]))
async def like_dislike(call: CallbackQuery, state: FSMContext):
    await call.answer()

    data = await state.get_data()
    to_user = data.get("current_profile_id")

    if not to_user:
        return

    if call.data == "like":
        is_match = await add_like(call.from_user.id, to_user)

        if is_match:
            await notify_match(call.from_user.id, to_user)
        else:
            await notify_like(call.from_user.id, to_user)

    await show_next_profile(call, state)

async def notify_like(from_user_id: int, to_user_id: int):
    profile = await get_profile(from_user_id)
    if not profile:
        return

    name, age, city, goal, photo_id = profile
    text = (
        f"🔔 У вас новый лайк 🤍\n\n"
        f"{name}, {age} · 📍 {city}\n"
        f"{goal}"
    )

    if photo_id:
        await bot.send_photo(
            to_user_id,
            photo_id,
            caption=text,
            reply_markup=like_kb()
        )
    else:
        await bot.send_message(
            to_user_id,
            text,
            reply_markup=like_kb()
        )

async def notify_match(u1: int, u2: int):
    await bot.send_message(
        u1,
        "💫 У вас совпадение!\nМожно написать 🤍",
        reply_markup=match_kb(u2)
    )
    await bot.send_message(
        u2,
        "💫 У вас совпадение!\nМожно написать 🤍",
        reply_markup=match_kb(u1)
    )

# ================== RUN ==================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
