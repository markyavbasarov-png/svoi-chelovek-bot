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

API_TOKEN = os.getenv("BOT_TOKEN")
DB = "database.db"

logging.basicConfig(level=logging.INFO)

if not API_TOKEN:
    raise RuntimeError("BOT_TOKEN not set")

bot = Bot(API_TOKEN)
dp = Dispatcher()

current_profiles = {}  # viewer_id -> profile_id


# ---------- KEYBOARDS ----------

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


def like_response_kb(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️ Ответить", callback_data=f"like_back:{user_id}"),
            InlineKeyboardButton(text="❌ Пропустить", callback_data=f"dislike_back:{user_id}")
        ]
    ])


def match_kb(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✉️ Написать", url=f"tg://user?id={user_id}")]
    ])


# ---------- DB ----------

async def get_next_profile(viewer_id: int):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
            SELECT id, name, age, city, goal, photo_id
            FROM profiles
            WHERE id != ?
              AND id NOT IN (
                SELECT to_user FROM likes WHERE from_user = ?
              )
            ORDER BY RANDOM()
            LIMIT 1
        """, (viewer_id, viewer_id))
        return await cur.fetchone()


async def get_profile(user_id: int):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
            SELECT name, age, city, goal, photo_id
            FROM profiles WHERE id = ?
        """, (user_id,))
        return await cur.fetchone()


async def add_like(from_user: int, to_user: int) -> bool:
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR IGNORE INTO likes (from_user, to_user) VALUES (?, ?)",
            (from_user, to_user)
        )
        cur = await db.execute(
            "SELECT 1 FROM likes WHERE from_user=? AND to_user=?",
            (to_user, from_user)
        )
        match = await cur.fetchone()
        await db.commit()
        return bool(match)


# ---------- START ----------

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "Привет, 🤍\n\n«свойЧеловек» — это про тепло и поддержку.\n\nНачнём знакомство?",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="давай 🤍", callback_data="browse")]]
        )
    )


# ---------- BROWSE ----------

@dp.callback_query(F.data == "browse")
async def browse(call: CallbackQuery):
    profile = await get_next_profile(call.from_user.id)

    if not profile:
        await call.message.answer(
            "Анкеты закончились 🤍\nВ вашем городе больше нет новых людей",
            reply_markup=main_menu_kb()
        )
        await call.answer()
        return

    user_id, name, age, city, goal, photo_id = profile
    current_profiles[call.from_user.id] = user_id

    text = f"{name}, {age} · 📍 {city}\nЦель: {goal}"

    await call.message.answer_photo(
        photo=photo_id,
        caption=text,
        reply_markup=like_kb()
    )
    await call.answer()


# ---------- LIKE / DISLIKE ----------

@dp.callback_query(F.data.in_(["like", "dislike"]))
async def like_dislike(call: CallbackQuery):
    to_user = current_profiles.get(call.from_user.id)
    if not to_user:
        await call.answer()
        return

    if call.data == "like":
        is_match = await add_like(call.from_user.id, to_user)

        if not is_match:
            profile = await get_profile(call.from_user.id)
            if profile:
                name, age, city, goal, photo_id = profile
                await bot.send_photo(
                    to_user,
                    photo=photo_id,
                    caption=f"🔔 У вас новый лайк 🤍\n\n{name}, {age}\n📍 {city}\nЦель: {goal}",
                    reply_markup=like_response_kb(call.from_user.id)
                )

    await browse(call)


# ---------- LIKE BACK ----------

@dp.callback_query(F.data.startswith("like_back:"))
async def like_back(call: CallbackQuery):
    other = int(call.data.split(":")[1])
    if await add_like(call.from_user.id, other):
        await call.message.answer(
            "💞 Это взаимно!\nТеперь вы можете написать друг другу",
            reply_markup=match_kb(other)
        )
        await bot.send_message(
            other,
            "💞 У вас взаимный лайк!\nМожно начинать общение 🤍",
            reply_markup=match_kb(call.from_user.id)
        )
    await call.answer()


@dp.callback_query(F.data.startswith("dislike_back:"))
async def dislike_back(call: CallbackQuery):
    await call.answer("Хорошо 🤍")


# ---------- RUN ----------

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
