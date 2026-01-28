import asyncio
import logging
import aiosqlite
import os

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
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
            about TEXT
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
        "Здесь можно найти тёплое общение и поддержку.\n"
        "Давайте познакомимся 🌱",
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
            [InlineKeyboardButton(text="🤰 Ещё ждём", callback_data="age_Ещё ждём")],
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
    await message.answer("Пару слов о себе или «Пропустить»")


@dp.message(Profile.about)
async def about_entered(message: Message, state: FSMContext):
    data = await state.get_data()
    about = None if message.text.lower() == "пропустить" else message.text

    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT OR REPLACE INTO users
        VALUES (?, ?, ?, ?, ?, ?, ?)
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
        "🤍 Анкета создана",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👀 Смотреть анкеты", callback_data="browse")]
        ])
    )


# ---------- SEND PROFILE (ОДНА КНОПКА) ----------
async def send_profile(user_id: int, to_user: int):
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute("""
        SELECT role, goal, city, about
        FROM users WHERE user_id=?
        """, (user_id,))
        u = await cursor.fetchone()

    if not u:
        return

    role, goal, city, about = u
    text = f"{role}\n📍 {city}\nИщу: {goal}\n\n{about or ''}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❤️ Нравится", callback_data=f"like_{user_id}")]
    ])

    await bot.send_message(to_user, text, reply_markup=kb)


# ---------- SMART BROWSE ----------
@dp.callback_query(F.data == "browse")
async def browse(call: CallbackQuery):
    me = call.from_user.id

    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT city, goal FROM users WHERE user_id=?",
            (me,)
        )
        my = await cur.fetchone()
        if not my:
            await call.message.answer("Сначала создайте анкету 🤍")
            return

        city, goal = my

        cur = await db.execute("""
        SELECT user_id FROM users
        WHERE user_id != ?
          AND city = ?
          AND goal = ?
          AND user_id NOT IN (
              SELECT to_user FROM likes WHERE from_user=?
          )
        ORDER BY RANDOM() LIMIT 1
        """, (me, city, goal, me))
        row = await cur.fetchone()

        if not row:
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
        await call.message.answer("Пока подходящих анкет нет 🤍")
        return

    await send_profile(row[0], me)


# ---------- LIKE = СВАЙП ----------
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
        mutual = await cur.fetchone()

        if mutual:
            await db.execute(
                "INSERT OR IGNORE INTO matches VALUES (?, ?)",
                (min(from_user, to_user), max(from_user, to_user))
            )

            for a, b in [(from_user, to_user), (to_user, from_user)]:
                await bot.send_message(
                    a,
                    "💫 У вас взаимная симпатия",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="💬 Написать",
                            url=f"tg://user?id={b}"
                        )]
                    ])
                )
        else:
            # входящий лайк = анкета
            await send_profile(from_user, to_user)

        await db.commit()

    await call.answer("❤️")
    await browse(call)  # ← СВАЙП ВПЕРЁД


# ---------- RUN ----------
async def main():
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
