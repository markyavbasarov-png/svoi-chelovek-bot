import asyncio
import logging
import os
import aiosqlite

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from aiogram.filters import CommandStart

# ================== CONFIG ==================

API_TOKEN = os.getenv("BOT_TOKEN")  # !!! ОБЯЗАТЕЛЬНО через env
DB = "database.db"

logging.basicConfig(level=logging.INFO)

bot = Bot(API_TOKEN)
dp = Dispatcher()

# хранение текущей анкеты пользователя
user_current_profile = {}

# ================== KEYBOARDS ==================

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👀 Смотреть анкеты", callback_data="browse")],
        [InlineKeyboardButton(text="✏️ Изменить анкету", callback_data="edit")]
    ])


def like_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️", callback_data="like"),
            InlineKeyboardButton(text="❌", callback_data="dislike")
        ]
    ])


def like_response_kb(from_user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="❤️ Ответить взаимно",
                callback_data=f"like_back:{from_user_id}"
            ),
            InlineKeyboardButton(
                text="❌ Пропустить",
                callback_data=f"dislike_back:{from_user_id}"
            )
        ]
    ])


def match_kb(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✉️ Написать",
                url=f"tg://user?id={user_id}"
            )
        ]
    ])

# ================== DB HELPERS ==================

async def get_next_profile(viewer_id: int):
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute("""
            SELECT id, name, age, city, goal, photo_id
            FROM profiles
            WHERE id != ?
              AND id NOT IN (
                  SELECT to_user FROM likes WHERE from_user = ?
              )
            ORDER BY RANDOM()
            LIMIT 1
        """, (viewer_id, viewer_id))
        return await cursor.fetchone()


async def get_profile(user_id: int):
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute("""
            SELECT name, age, city, goal, photo_id
            FROM profiles WHERE id = ?
        """, (user_id,))
        return await cursor.fetchone()


async def add_like(from_user: int, to_user: int) -> bool:
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR IGNORE INTO likes (from_user, to_user) VALUES (?, ?)",
            (from_user, to_user)
        )

        cursor = await db.execute(
            "SELECT 1 FROM likes WHERE from_user = ? AND to_user = ?",
            (to_user, from_user)
        )
        match = await cursor.fetchone()
        await db.commit()

    return bool(match)

# ================== START ==================

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "Привет, 🤍\n\n"
        "«свойЧеловек» — это про тепло и поддержку.\n\n"
        "Начнём знакомство?",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="давай 🤍", callback_data="browse")]
            ]
        )
    )

# ================== BROWSE ==================

@dp.callback_query(F.data == "browse")
async def browse(call: CallbackQuery):
    profile = await get_next_profile(call.from_user.id)

    if not profile:
        await call.message.answer(
            "Анкеты закончились 🤍\n"
            "В вашем городе больше нет новых людей",
            reply_markup=main_menu_kb()
        )
        await call.answer()
        return

    user_id, name, age, city, goal, photo_id = profile

    text = (
        f"{name}, {age} · 📍 {city}\n"
        f"Цель: {goal}"
    )

    await call.message.answer_photo(
        photo=photo_id,
        caption=text,
        reply_markup=like_kb()
    )

    # сохраняем текущую анкету
    user_current_profile[call.from_user.id] = user_id

    await call.answer()

# ================== LIKE / DISLIKE ==================

@dp.callback_query(F.data.in_(["like", "dislike"]))
async def like_dislike(call: CallbackQuery):
    to_user_id = user_current_profile.get(call.from_user.id)

    if not to_user_id:
        await call.answer()
        return

    if call.data == "like":
        is_match = await add_like(call.from_user.id, to_user_id)

        if not is_match:
            profile = await get_profile(call.from_user.id)
            if profile:
                name, age, city, goal, photo_id = profile
                text = (
                    "🔔 У вас новый лайк 🤍\n\n"
                    f"{name}, {age}\n"
                    f"📍 {city}\n"
                    f"Цель: {goal}"
                )

                await bot.send_photo(
                    chat_id=to_user_id,
                    photo=photo_id,
                    caption=text,
                    reply_markup=like_response_kb(call.from_user.id)
                )

    await browse(call)

# ================== LIKE BACK ==================

@dp.callback_query(F.data.startswith("like_back:"))
async def like_back(call: CallbackQuery):
    from_user_id = int(call.data.split(":")[1])
    is_match = await add_like(call.from_user.id, from_user_id)

    if is_match:
        await call.message.answer(
            "💞 Это взаимно!\nТеперь вы можете написать друг другу",
            reply_markup=match_kb(from_user_id)
        )

        await bot.send_message(
            from_user_id,
            "💞 У вас взаимный лайк!\nМожно начинать общение 🤍",
            reply_markup=match_kb(call.from_user.id)
        )

    await call.answer()

@dp.callback_query(F.data.startswith("dislike_back:"))
async def dislike_back(call: CallbackQuery):
    await call.answer("Хорошо 🤍")

# ================== RUN ==================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
