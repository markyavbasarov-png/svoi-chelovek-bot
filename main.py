import asyncio
import logging
import os
import aiosqlite

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.types import BotCommand
from aiogram.filters import CommandStart, Command
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
    goal = State()          # создание
    edit_goal = State()     # редактирование
    about = State()         # создание
    edit_about = State()    # ✅ РЕДАКТИРОВАНИЕ
    photo = State()
    edit_photo = State()

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
        [InlineKeyboardButton(text="💞 Найти своего ", callback_data="browse")]
    ])

def profile_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="❤️ Найти своего",
                callback_data="browse"
            )
        ],
        [
            InlineKeyboardButton(
                text="✏️ Изменить анкету",
                callback_data="open_edit_menu"
            )
        ]
    ])
def edit_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ О себе", callback_data="edit_about")],
        [InlineKeyboardButton(text="📸 Фото", callback_data="edit_photo")],
        [InlineKeyboardButton(text="🎯 Цель", callback_data="edit_goal")],
        [InlineKeyboardButton(text="🗑 Удалить анкету", callback_data="delete_profile")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_profile")]
    ])
def confirm_delete_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Нет", callback_data="cancel_delete"),
            InlineKeyboardButton(text="🗑 Да, удалить", callback_data="confirm_delete")
        ]
    ])
def browse_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="♥️", callback_data="like"),
            InlineKeyboardButton(text="✖️", callback_data="dislike")
        ]
    ])

def soft_like_kb(from_user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="❤️ Ответить",
                callback_data=f"soft_like:{from_user_id}"
            ),
            InlineKeyboardButton(
                text="✖️ Пропустить",
                callback_data="soft_dislike"
            )
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


# ================= EDIT PROFILE (MENU) =================
@dp.message(Command("editprofile"))
async def edit_profile_menu(message: Message, state: FSMContext):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT user_id, name, age, city, role, goal, about, photo_id "
            "FROM users WHERE user_id = ?",
            (message.from_user.id,)
        )
        profile = await cur.fetchone()

    if not profile:
        await message.answer(
            "У тебя ещё нет анкеты 🤍\nДавай создадим?",
            reply_markup=start_kb()
        )
        return

    await state.clear()

    await send_profile_card(
        message.from_user.id,
        profile,
        edit_menu_kb()   # 👈 кнопки: город / фото / о себе / удалить / назад
    )

async def edit_current_message(call: CallbackQuery, text: str, kb):
    if call.message.photo:
        await call.message.edit_caption(
            caption=text,
            reply_markup=kb
        )
    else:
        await call.message.edit_text(
            text,
            reply_markup=kb
        )
# ================= CALLBACKS =================
@dp.callback_query(F.data == "open_edit_menu")
async def open_edit_menu(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.clear()

    if call.message.photo:
        await call.message.edit_caption(
            caption="Что вы хотите изменить?",
            reply_markup=edit_menu_kb()
        )
    else:
        await call.message.edit_text(
            "Что вы хотите изменить?",
            reply_markup=edit_menu_kb()
        )
@dp.callback_query(F.data == "back_to_profile")
async def back_to_profile(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.clear()

    # 🔒 убираем кнопки у текущего сообщения
    if call.message.photo:
        await call.message.edit_caption(reply_markup=None)
    else:
        await call.message.edit_reply_markup(reply_markup=None)

    # 👉 показываем анкету
    await send_my_profile(call.from_user.id)

@dp.callback_query(F.data == "edit_photo")
async def edit_photo(call: CallbackQuery, state: FSMContext):
    await state.set_state(Profile.edit_photo)
    await edit_current_message(
        call,
        "📸 Пришлите новое фото",
        None
    )

# 2️⃣ если пришло ФОТО — сохраняем
@dp.message(Profile.edit_photo, F.photo)
async def save_edited_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id

    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE users SET photo_id = ? WHERE user_id = ?",
            (photo_id, message.from_user.id)
        )
        await db.commit()

    await state.clear()
    await message.answer("📸 Фото обновлено")
    await send_my_profile(message.from_user.id)


# 3️⃣ если пришло НЕ фото — объясняем
@dp.message(Profile.edit_photo)
async def edit_photo_wrong(message: Message):
    await message.answer("Пожалуйста, отправь фото 📸, не текст и не файл")
    
@dp.callback_query(F.data == "edit_about")
async def edit_about(call: CallbackQuery, state: FSMContext):
    await state.set_state(Profile.edit_about)
    await edit_current_message(
        call,
        "✏️ Напишите новый текст анкеты",
        None
    )

@dp.message(Profile.edit_about)
async def save_edit_about(message: Message, state: FSMContext):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE users SET about = ? WHERE user_id = ?",
            (message.text, message.from_user.id)
        )
        await db.commit()

    await state.clear()
    await message.answer("✏️ О себе обновлено")
    await send_my_profile(message.from_user.id)

@dp.callback_query(F.data == "edit_goal")
async def edit_goal(call: CallbackQuery, state: FSMContext):
    await state.set_state(Profile.edit_goal)
    await edit_current_message(
        call,
        "🎯 Что вам сейчас ближе?",
        goal_kb()
    )
@dp.callback_query(F.data.startswith("goal_"), Profile.edit_goal)
async def edit_goal_save(call: CallbackQuery, state: FSMContext):
    goal = call.data.replace("goal_", "")

    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE users SET goal = ? WHERE user_id = ?",
            (goal, call.from_user.id)
        )
        await db.commit()

    await state.clear()
    await call.message.edit_text(f"🎯 Цель обновлена: {goal}")
    await send_my_profile(call.from_user.id)

@dp.callback_query(F.data == "delete_profile")
async def ask_delete_confirm(call: CallbackQuery):
    await edit_current_message(
        call,
        "⚠️ Ты точно хочешь удалить анкету?\n\nЭто действие нельзя отменить.",
        confirm_delete_kb()
    )
@dp.callback_query(F.data == "confirm_delete")
async def confirm_delete(call: CallbackQuery):
    await call.answer()
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "DELETE FROM users WHERE user_id = ?",
            (call.from_user.id,)
        )
        await db.commit()

    await call.message.answer(
        "🗑 Анкета удалена\n\nХочешь создать новую?",
        reply_markup=start_kb()
    )
@dp.callback_query(F.data == "cancel_delete")
async def cancel_delete(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.clear()

    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT user_id, name, age, city, role, goal, about, photo_id "
            "FROM users WHERE user_id = ?",
            (call.from_user.id,)
        )
        profile = await cur.fetchone()

    if not profile:
        await call.message.answer(
            "Анкета не найдена 🤍",
            reply_markup=start_kb()
        )
        return

    await send_profile_card(
        call.from_user.id,
        profile,
        edit_menu_kb()
    )

# ================= PROFILE FLOW =================
@dp.callback_query(F.data == "start_form")
async def start_form(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(Profile.name)
    await call.message.edit_text("Как тебя зовут?")

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
        "Здесь ищут не идеальных, а своих 🤍\n\n"
        "Если хочется — расскажите пару слов о себе.",
        reply_markup=skip_about_kb()
    )

@dp.callback_query(F.data == "skip_about", Profile.about)
async def skip_about(call: CallbackQuery, state: FSMContext):
    await state.update_data(about=None)
    await state.set_state(Profile.photo)
    await call.message.edit_text(
        "Если хочется, можно добавить фото 🤍",
        reply_markup=photo_kb()
    )

@dp.message(Profile.about)
async def set_about(message: Message, state: FSMContext):
    await state.update_data(about=message.text)
    await state.set_state(Profile.photo)
    await message.answer("Добавить фото?", reply_markup=photo_kb())

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
        await send_profile_card(user_id, profile, profile_main_kb())

# ================= BROWSE =================
@dp.callback_query(F.data == "browse")
async def browse(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await show_next_profile(call, state)


async def show_next_profile(call: CallbackQuery, state: FSMContext):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
        SELECT user_id, name, age, city, role, goal, about, photo_id
        FROM users
        WHERE city = (SELECT city FROM users WHERE user_id = ?)
        AND user_id != ?
        AND user_id NOT IN (
            SELECT to_user FROM likes WHERE from_user = ?
        )
        ORDER BY RANDOM()
        LIMIT 1
        """, (call.from_user.id, call.from_user.id, call.from_user.id))

        profile = await cur.fetchone()

    if not profile:
        await call.message.answer(
            "😔 Пока подходящих анкет нет\n"
            "Мы сообщим, как только появятся новые 💛"
        )
        return

    # 🔑 КЛЮЧЕВАЯ СТРОКА — ВСЁ ПРАВИЛЬНО
    await state.update_data(current_profile_id=profile[0])

    await send_profile_card(
        call.from_user.id,
        profile,
        browse_kb()
    )
# ================= LIKES + MATCH =================
# ❤️ / ✖️ при просмотре анкеты
@dp.callback_query(F.data.in_(["like", "dislike"]))
async def like_dislike(call: CallbackQuery, state: FSMContext):
    await call.answer("❤️" if call.data == "like" else "✖️")

    data = await state.get_data()
    to_user = data.get("current_profile_id")
    from_user = call.from_user.id

    if not to_user:
        return

    # ❌ дизлайк — просто следующая анкета
    if call.data == "dislike":
        await show_next_profile(call, state)
        return

    # ❤️ пользователь лайкнул
    async with aiosqlite.connect(DB) as db:

        # ⛔ проверяем: не лайкал ли уже
        cur = await db.execute(
            "SELECT 1 FROM likes WHERE from_user = ? AND to_user = ?",
            (from_user, to_user)
        )
        if await cur.fetchone():
            await show_next_profile(call, state)
            return

        # ✅ пишем лайк
        await db.execute(
            "INSERT INTO likes (from_user, to_user) VALUES (?, ?)",
            (from_user, to_user)
        )
        await db.commit()

    # 💛 мягкое уведомление лайкнутому
    await notify_soft_like(from_user, to_user)

    # ➡️ следующая анкета
    await show_next_profile(call, state)


# 💛 мягкое уведомление о лайке
async def notify_soft_like(from_user: int, to_user: int):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
            SELECT user_id, name, age, city, role, goal, about, photo_id
            FROM users WHERE user_id = ?
        """, (from_user,))
        profile = await cur.fetchone()

    if not profile:
        return

    await bot.send_message(
        to_user,
        "💛 Кому-то вы понравились\n"
        "Возможно, это начало чего-то тёплого"
    )

    await asyncio.sleep(0.3)

    await send_profile_card(
        to_user,
        profile,
        soft_like_kb(from_user)  # передаём ID лайкнувшего
    )


# ❤️ / ✖️ ответ на soft-like
@dp.callback_query(F.data.startswith("soft_like"))
async def soft_like_response(call: CallbackQuery):
    await call.answer()

    # 🔒 убираем кнопки сразу
    await call.message.edit_reply_markup(reply_markup=None)

    from_user = call.from_user.id          # тот, кто отвечает
    to_user = int(call.data.split(":")[1]) # тот, кто лайкнул первым

    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR IGNORE INTO likes (from_user, to_user) VALUES (?, ?)",
            (from_user, to_user)
        )
        await db.commit()

    # 💞 теперь это МАТЧ
    await notify_match(from_user, to_user)

    await call.message.edit_text(
        "🤍 Это взаимно\n"
        "Теперь можно написать друг другу 🌿"
    )


@dp.callback_query(F.data == "soft_dislike")
async def soft_dislike(call: CallbackQuery):
    await call.answer()
    await call.message.edit_text("🤍 Хорошо, идём дальше")


# 💞 матч-уведомление
async def notify_match(u1: int, u2: int):
    for viewer, partner in [(u1, u2), (u2, u1)]:
        async with aiosqlite.connect(DB) as db:
            cur = await db.execute("""
                SELECT user_id, name, age, city, role, goal, about, photo_id
                FROM users WHERE user_id = ?
            """, (partner,))
            profile = await cur.fetchone()

        if not profile:
            continue

        await bot.send_message(
            viewer,
            "🤍 У вас взаимная симпатия\n"
            "Можно написать друг другу 🌿"
        )

        await asyncio.sleep(0.3)

        await send_profile_card(
            viewer,
            profile,
            match_kb(partner)
        )
# ================= RUN =================
async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Начать"),
        BotCommand(command="myprofile", description="Моя анкета"),
        BotCommand(command="editprofile", description="Изменить анкету"),
    ]
    await bot.set_my_commands(commands)
async def main():
    await init_db()
    await set_commands(bot) 
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
