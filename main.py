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
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

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
        [InlineKeyboardButton(text="👼🏼 Будущий родитель", callback_data="role_Будущий")]
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
        [InlineKeyboardButton(text="📸 Загрузить фото", callback_data="upload_photo")],
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_photo")]
    ])

def edit_profile_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_profile")],
        [InlineKeyboardButton(text="❤️ Смотреть анкеты", callback_data="browse")]
    ])

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def cancel_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="cancel_edit")]
        ]
    )
def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👀 Смотреть анкеты", callback_data="browse")]
    ])

def my_profile_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👀 Смотреть анкеты", callback_data="browse")],
        [InlineKeyboardButton(text="✍️ Изменить анкету", callback_data="edit_profile")],
        [InlineKeyboardButton(text="📸 Изменить фото", callback_data="edit_photo")],
        [InlineKeyboardButton(text="💬 Изменить текст анкеты", callback_data="edit_about")]
    ])

def edit_profile_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
    text="📝 анкету заново",
    callback_data="edit_profile_full"
)
                
        ],
        [
            InlineKeyboardButton(
                text="📸 Изменить фото",
                callback_data="edit_photo"
            )
        ],
        [
            InlineKeyboardButton(
                text="✏️ текст",
                callback_data="edit_text"
            )
        ]
    ])
    
def browse_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="♥️", callback_data="like"),
            InlineKeyboardButton(text="✖️", callback_data="dislike")
        ]
    ])

def view_liker_kb(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="👀 Посмотреть анкету",
                callback_data=f"view_like:{user_id}"
            )
        ]
    ])
def match_kb(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✉️ Написать", url=f"tg://user?id={user_id}")]
    ])
# ========= HELPERS / PROFILE =========

async def send_my_profile(user_id: int):
    data = await get_profile(user_id)

    await bot.send_photo(
        chat_id=user_id,
        photo=data["photo_id"],
        caption=(
            "Вот твоя анкета 🤍\n\n"
            f"{data['name']}, {data['age']} • 📍 {data['city']}\n"
            f"🔎 {data['goal']}\n\n"
            f"{data['about']}"
        ),
        reply_markup=my_profile_kb()
    )

# ================== START ==================
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
    "Привет 🤍\n\n"
    "Ты не случайно здесь.\n\n"
    "«свойЧеловек» — это место для родителей,\n"
    "где можно быть собой.\n"
    "Без спешки. Без оценок.\n\n"
    "Здесь не ищут идеальных.\n"
    "Здесь ищут своих.\n\n"
    "Начнём знакомство?",
    reply_markup=start_kb()
)

# ================= MY PROFILE =================
@dp.message(Command("myprofile"))
async def my_profile(message: Message):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT 1 FROM users WHERE user_id = ?",
            (message.from_user.id,)
        )
        exists = await cur.fetchone()

    if not exists:
        await message.answer(
            "Твоя анкета ещё не создана 🤍\nДавай начнём знакомство?",
            reply_markup=start_kb()
        )
        return

    await send_my_profile(message.from_user.id)

# ================= CALLBACKS =================
@dp.callback_query(F.data == "edit_photo")
async def edit_photo(call: CallbackQuery, state: FSMContext):
    await call.message.edit_caption(
        caption=call.message.caption,
        reply_markup=None
    )

    await state.set_state(Profile.photo)

    await call.message.answer(
        "Пришли новое фото 📸",
        reply_markup=cancel_kb()
    )

@dp.callback_query(F.data == "edit_text")
async def edit_text(call: CallbackQuery, state: FSMContext):
    await call.message.edit_caption(
        caption=call.message.caption,
        reply_markup=None
    )

    await state.set_state(Profile.about)

    await call.message.answer(
        "Напиши новый текст анкеты ✍️",
        reply_markup=cancel_kb()
    )
# ================= PROFILE FLOW =================
@dp.callback_query(F.data == "start_form")
async def start_form(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(Profile.name)
    await call.message.edit_text(
    "Небольшая анкета —\n"
    "чтобы другим было чуть легче тебя узнать 🤍\n\n"
    "Можно отвечать просто.\n"
    "Можно пропускать.\n"
    "Всё — по желанию.\n\n"
    "Как тебя зовут?"
)

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
    await message.answer("Кто ты сейчас?", reply_markup=role_kb())

@dp.callback_query(F.data.startswith("role_"), Profile.role)
async def set_role(call: CallbackQuery, state: FSMContext):
    await state.update_data(role=call.data.replace("role_", ""))
    await state.set_state(Profile.goal)
    await call.message.edit_text("Что вам сейчас ближе?", reply_markup=goal_kb())

@dp.callback_query(F.data.startswith("goal_"), Profile.goal)
async def set_goal(call: CallbackQuery, state: FSMContext):
    await state.update_data(goal=call.data.replace("goal_", ""))
    await state.set_state(Profile.about)

    await call.message.edit_text(
        "Здесь ищут не идеальных,\n"
        "а своих 🤍\n\n"
        "Если хочется —\n"
        "напиши пару слов о себе.\n\n"
        "Если нет — можно пропустить.",
        reply_markup=skip_about_kb()
    )

@dp.callback_query(F.data == "skip_about", Profile.about)
async def skip_about(call: CallbackQuery, state: FSMContext):
    await state.update_data(about=None)
    await state.set_state(Profile.photo)
    await call.message.edit_text(
    "Если хочется, можно добавить фото 🤍\n\n"
    "А если не сейчас —\n"
    "это тоже нормально.",
    reply_markup=photo_kb()

)
    
@dp.callback_query(F.data == "edit_profile")
async def edit_profile(call: CallbackQuery):
    await call.answer()

    if call.message.photo:
        await call.message.edit_caption(
            caption="Что хочешь изменить?",
            reply_markup=edit_profile_menu_kb()
        )
    else:
        await call.message.edit_text(
            text="Что хочешь изменить?",
            reply_markup=edit_profile_menu_kb()
        )
        
@dp.callback_query(F.data == "edit_profile_full")
async def edit_profile_full(call: CallbackQuery, state: FSMContext):
    await call.message.edit_reply_markup(reply_markup=None)
    await state.clear()
    await state.set_state(Profile.name)
    await call.message.answer("Давай обновим анкету 🤍\nКак тебя зовут?")

@dp.callback_query(F.data == "edit_text")
async def edit_text(call: CallbackQuery, state: FSMContext):
    await call.message.edit_caption(
        caption=call.message.caption,
        reply_markup=None
    )
    await state.set_state(Profile.about)
    await call.message.answer(
        "Напиши новый текст анкеты ✍️",
        reply_markup=cancel_kb()
    )
@dp.callback_query(F.data == "cancel_edit")
async def cancel_edit(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.clear()

    await send_my_profile(call.from_user.id)

    
@dp.message(Profile.about)
async def set_about(message: Message, state: FSMContext):
    await state.update_data(about=message.text)
    await state.set_state(Profile.photo)
    await message.answer(
        "Добавить фото?",
        reply_markup=photo_kb()
    )
@dp.callback_query(F.data == "upload_photo", Profile.photo)
async def upload_photo(call: CallbackQuery):
    await call.message.edit_text("Отправь фотографию 🤍")

@dp.callback_query(F.data == "skip_photo", Profile.photo)
async def skip_photo(call: CallbackQuery, state: FSMContext):
    await save_profile(call.from_user, state, None)
    await send_my_profile(call.from_user.id)

@dp.message(Profile.photo, F.photo)
async def set_photo(message: Message, state: FSMContext):
    await save_profile(message.from_user, state, message.photo[-1].file_id)
    await send_my_profile(message.from_user.id)

# ================= SAVE =================
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

# ================= PROFILE RENDER =================
async def send_profile_card(chat_id: int, profile: tuple, kb):
    uid, name, age, city, role, goal, about, photo_id = profile
    text = (
        f"{role} {name}, {age} · 📍 {city}\n"
        f"🔍: {goal}\n\n"
        f"{about or ''}"
    )
    if photo_id:
        await bot.send_photo(chat_id, photo_id, caption=text, reply_markup=kb)
    else:
        await bot.send_message(chat_id, text, reply_markup=kb)

async def send_my_profile(user_id: int):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
            SELECT user_id, name, age, city, role, goal, about, photo_id
            FROM users WHERE user_id = ?
        """, (user_id,))
        profile = await cur.fetchone()

    if profile:
        await bot.send_message(
            user_id,
            "Вот твоя анкета 🤍\n\n"
            "Если захочешь —\n"
            "можно что-то изменить\n"
            "или просто посмотреть других."
        )

        await send_profile_card(
            user_id,
            profile,
            edit_profile_kb()
        )

# ================= BROWSE =================
@dp.callback_query(F.data == "browse")
async def browse_profiles(call: CallbackQuery, state: FSMContext):

    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            """
            SELECT user_id, name, age, city, role, goal, about, photo
            FROM users
            WHERE city = (SELECT city FROM users WHERE user_id = ?)
              AND user_id != ?
              AND user_id NOT IN (
                  SELECT to_user FROM views WHERE from_user = ?
              )
            ORDER BY RANDOM()
            LIMIT 1
            """,
            (call.from_user.id, call.from_user.id, call.from_user.id)
        )

        profile = await cur.fetchone()

    if not profile:
        await call.message.answer(
            "🤍 Сейчас подходящих анкет нет\n\n"
            "Можно сделать паузу,\n"
            "налить чай\n"
            "и вернуться позже —\n"
            "мы будем ждать 🤍",
            reply_markup=main_menu_kb()
        )
        return

    # сохраняем просмотр анкеты
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR IGNORE INTO views (from_user, to_user) VALUES (?, ?)",
            (call.from_user.id, profile[0])
        )
        await db.commit()

    await state.update_data(current_profile_id=profile[0])
    await send_profile_card(call.from_user.id, profile)
# ================= LIKES + MATCH =================
@dp.callback_query(lambda c: c.data in ["like", "dislike"])
async def like_dislike(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    to_user = data.get("current_profile_id")
    from_user = call.from_user.id

    if not to_user:
        return

    if call.data == "like":
        async with aiosqlite.connect(DB) as db:
            await db.execute(
                "INSERT OR IGNORE INTO likes VALUES (?, ?)",
                (from_user, to_user)
            )
            await db.commit()

        await bot.send_message(
            to_user,
            "💖 Тебя лайкнули",
            reply_markup=view_liker_kb(from_user)
        )
async def notify_match(u1: int, u2: int):
    for viewer, partner in [(u1, u2), (u2, u1)]:
        async with aiosqlite.connect(DB) as db:
            cur = await db.execute("""
            SELECT user_id, name, age, city, role, goal, about, photo_id
            FROM users WHERE user_id = ?
            """, (partner,))
            profile = await cur.fetchone()

        await bot.send_message(
            viewer,
            "🤍 Кажется, это взаимно\n\n"
            "Можно просто сказать\n"
            "«привет».\n"
            "Этого достаточно."
)
        await send_profile_card(viewer, profile, match_kb(partner))    
        async with aiosqlite.connect(DB) as db:
            cur = await db.execute(
                "SELECT 1 FROM likes WHERE from_user = ? AND to_user = ?",
                (to_user, from_user)
            )
            is_match = await cur.fetchone()

        if is_match:
            await notify_match(from_user, to_user)

    await show_next_profile(call, state)


# ================= RUN =================
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
