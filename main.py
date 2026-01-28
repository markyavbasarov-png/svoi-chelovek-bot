import asyncio
import logging
import aiosqlite

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

import os
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
            active INTEGER DEFAULT 1
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            from_user INTEGER,
            to_user INTEGER,
            UNIQUE(from_user, to_user)
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            user1 INTEGER,
            user2 INTEGER,
            UNIQUE(user1, user2)
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


# ---------- START ----------
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет 🤍\n\n"
        "Этот бот создан для родителей и тех, кому сейчас нужна поддержка.\n"
        "Здесь можно найти компанию для прогулок с детьми или тёплое общение — "
        "без спешки и без давления.\n\n"
        "Давайте познакомимся немного 🌱",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Начать", callback_data="start_form")]
        ])
    )


# ---------- PROFILE ----------
@dp.callback_query(F.data == "start_form")
async def start_form(call: CallbackQuery, state: FSMContext):
    await state.set_state(Profile.role)
    await call.message.edit_text(
        "Кто вы?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👩‍🍼 Мама", callback_data="role_Мама")],
            [InlineKeyboardButton(text="👨‍🍼 Папа", callback_data="role_Папа")],
            [InlineKeyboardButton(text="🤍 Будущий родитель", callback_data="role_Будущий родитель")],
            [InlineKeyboardButton(text="🌱 Просто ищу поддержку", callback_data="role_Поддержка")]
        ])
    )


@dp.callback_query(Profile.role)
async def role_chosen(call: CallbackQuery, state: FSMContext):
    await state.update_data(role=call.data.replace("role_", ""))
    await state.set_state(Profile.goal)
    await call.message.edit_text(
        "Что для вас сейчас важнее всего?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚶‍♀️ Совместные прогулки с детьми", callback_data="goal_Прогулки")],
            [InlineKeyboardButton(text="💬 Общение и поддержка", callback_data="goal_Поддержка")],
            [InlineKeyboardButton(text="🎀 Поддержка в важный период", callback_data="goal_Период")],
            [InlineKeyboardButton(text="🤝 Всё вместе, без спешки", callback_data="goal_Всё")]
        ])
    )


@dp.callback_query(Profile.goal)
async def goal_chosen(call: CallbackQuery, state: FSMContext):
    await state.update_data(goal=call.data.replace("goal_", ""))
    await state.set_state(Profile.child_age)
    await call.message.edit_text(
        "Если хотите, укажите возраст ребёнка.\nМожно пропустить.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🤰 Ещё ждём", callback_data="age_Ещё ждём")],
            [InlineKeyboardButton(text="👶 0–1 год", callback_data="age_0–1")],
            [InlineKeyboardButton(text="🧸 1–3 года", callback_data="age_1–3")],
            [InlineKeyboardButton(text="🏃‍♂️ 3–6 лет", callback_data="age_3–6")],
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="age_Пропустить")]
        ])
    )


@dp.callback_query(Profile.child_age)
async def age_chosen(call: CallbackQuery, state: FSMContext):
    age = call.data.replace("age_", "")
    await state.update_data(child_age=None if age == "Пропустить" else age)
    await state.set_state(Profile.city)
    await call.message.edit_text("В каком городе вы находитесь?")


@dp.message(Profile.city)
async def city_entered(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(Profile.about)
    await message.answer(
        "Если хотите, напишите пару слов о себе.\n"
        "Или отправьте «Пропустить»."
    )


@dp.message(Profile.about)
async def about_entered(message: Message, state: FSMContext):
    data = await state.get_data()
    about = None if message.text.lower() == "пропустить" else message.text

    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT OR REPLACE INTO users
        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            message.from_user.id,
            message.from_user.username,
            data["role"],
            data["goal"],
            data["child_age"],
            data["city"],
            about
        ))
        await db.commit()

    await state.clear()
    await message.answer(
        "Спасибо 🤍 Ваша анкета создана.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👀 Смотреть анкеты", callback_data="browse")]
        ])
    )


# ---------- BROWSING ----------
@dp.callback_query(F.data == "browse")
async def browse(call: CallbackQuery):
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute("""
        SELECT user_id, role, goal, child_age, city, about
        FROM users
        WHERE user_id != ?
        ORDER BY RANDOM()
        LIMIT 1
        """, (call.from_user.id,))
        user = await cursor.fetchone()

    if not user:
        await call.message.answer("Пока анкет нет 🤍")
        return

    uid, role, goal, child_age, city, about = user
    text = f"{role}\n📍 {city}\nИщу: {goal}\n\n{about or ''}"

    await call.message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💚 Лайк", callback_data=f"like_{uid}"),
                InlineKeyboardButton(text="⏭ Дальше", callback_data="browse")
            ]
        ])
    )


# ---------- LIKE + MATCH ----------
@dp.callback_query(F.data.startswith("like_"))
async def like(call: CallbackQuery):
    from_user = call.from_user.id
    to_user = int(call.data.split("_")[1])

    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR IGNORE INTO likes VALUES (?, ?)",
            (from_user, to_user)
        )

        cursor = await db.execute(
            "SELECT 1 FROM likes WHERE from_user=? AND to_user=?",
            (to_user, from_user)
        )
        mutual = await cursor.fetchone()

        if not mutual:
            await bot.send_message(
                to_user,
                "💚 Кто-то лайкнул вас 🤍"
            )
        else:
            await db.execute(
                "INSERT OR IGNORE INTO matches VALUES (?, ?)",
                (min(from_user, to_user), max(from_user, to_user))
            )

            await bot.send_message(
                from_user,
                "💫 Это взаимно!\nВы можете написать первым 💌",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="💌 Написать первым",
                        url=f"tg://user?id={to_user}"
                    )]
                ])
            )

            await bot.send_message(
                to_user,
                "💫 У вас взаимная симпатия 🤍",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="💬 Написать",
                        url=f"tg://user?id={from_user}"
                    )]
                ])
            )

        await db.commit()

    await call.answer("Готово 🤍")
    await browse(call)


# ---------- RUN ----------
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
