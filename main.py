import os
import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import Command

# ======================
# НАСТРОЙКИ
# ======================

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не найден в переменных окружения")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ------------------ БД ------------------

async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            age INTEGER,
            city TEXT,
            about TEXT,
            photo_id TEXT
        );

        CREATE TABLE IF NOT EXISTS likes (
            from_id INTEGER,
            to_id INTEGER,
            UNIQUE(from_id, to_id)
        );

        CREATE TABLE IF NOT EXISTS views (
            viewer_id INTEGER,
            viewed_id INTEGER,
            UNIQUE(viewer_id, viewed_id)
        );
        """)
        await db.commit()

# ------------------ КНОПКИ ------------------

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Смотреть анкеты", callback_data="browse")],
        [InlineKeyboardButton(text="👤 Моя анкета", callback_data="my_profile")],
        [InlineKeyboardButton(text="⚙️ Управление", callback_data="manage")]
    ])

def browse_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️", callback_data="like"),
            InlineKeyboardButton(text="👎", callback_data="skip")
        ]
    ])

def manage_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить анкету", callback_data="edit_profile")],
        [InlineKeyboardButton(text="🖼 Изменить фото", callback_data="edit_photo")],
        [InlineKeyboardButton(text="📝 Изменить текст", callback_data="edit_text")],
        [InlineKeyboardButton(text="🗑 Удалить аккаунт", callback_data="delete_confirm")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ])

def delete_confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Нет", callback_data="back"),
            InlineKeyboardButton(text="✅ Да", callback_data="delete")
        ]
    ])

# ------------------ START ------------------

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "Привет 🤍\nЭто бот знакомств.\nВыбери действие:",
        reply_markup=main_menu_kb()
    )

# ------------------ ПРОФИЛЬ ------------------

@dp.callback_query(F.data == "my_profile")
async def my_profile(callback: CallbackQuery):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT name, age, city, about, photo_id FROM users WHERE user_id=?",
            (callback.from_user.id,)
        )
        row = await cur.fetchone()

    if not row:
        await callback.message.answer("У тебя ещё нет анкеты.")
        return

    name, age, city, about, photo_id = row
    text = f"{name}, {age} · {city}\n\n{about}"

    if photo_id:
        await bot.send_photo(callback.from_user.id, photo_id, caption=text)
    else:
        await callback.message.answer(text)

# ------------------ УПРАВЛЕНИЕ ------------------

@dp.callback_query(F.data == "manage")
async def manage(callback: CallbackQuery):
    await callback.message.edit_text("⚙️ Управление:", reply_markup=manage_kb())

@dp.callback_query(F.data == "delete_confirm")
async def delete_confirm(callback: CallbackQuery):
    await callback.message.edit_text(
        "Точно удалить аккаунт?",
        reply_markup=delete_confirm_kb()
    )

@dp.callback_query(F.data == "delete")
async def delete_account(callback: CallbackQuery):
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM users WHERE user_id=?", (callback.from_user.id,))
        await db.commit()

    await callback.message.edit_text("Аккаунт удалён.")
    await callback.message.answer("Главное меню:", reply_markup=main_menu_kb())

@dp.callback_query(F.data == "back")
async def back(callback: CallbackQuery):
    await callback.message.edit_text("Главное меню:", reply_markup=main_menu_kb())

# ------------------ ПРОСМОТР АНКЕТ ------------------

async def get_next_profile(user_id: int):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
        SELECT user_id, name, age, city, about, photo_id
        FROM users
        WHERE user_id != ?
        AND user_id NOT IN (
            SELECT viewed_id FROM views WHERE viewer_id=?
        )
        LIMIT 1
        """, (user_id, user_id))
        return await cur.fetchone()

@dp.callback_query(F.data == "browse")
async def browse(callback: CallbackQuery):
    profile = await get_next_profile(callback.from_user.id)

    if not profile:
        await callback.message.answer("Анкеты закончились 🫶")
        return

    uid, name, age, city, about, photo_id = profile
    text = f"{name}, {age} · {city}\n\n{about}"

    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR IGNORE INTO views VALUES (?,?)",
            (callback.from_user.id, uid)
        )
        await db.commit()

    if photo_id:
        await bot.send_photo(callback.from_user.id, photo_id, caption=text, reply_markup=browse_kb())
    else:
        await callback.message.answer(text, reply_markup=browse_kb())

# ------------------ ЛАЙКИ ------------------

@dp.callback_query(F.data == "like")
async def like(callback: CallbackQuery):
    # упрощённый пример
    await callback.answer("❤️ Лайк отправлен")

@dp.callback_query(F.data == "skip")
async def skip(callback: CallbackQuery):
    await browse(callback)

# ------------------ ЗАПУСК ------------------

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
