import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

API_TOKEN = "PASTE_YOUR_TOKEN_HERE"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# -------------------------
# ВРЕМЕННОЕ ХРАНИЛИЩЕ
# -------------------------
users = {}       # анкеты
likes = {}       # кто кого лайкнул

# -------------------------
# FSM
# -------------------------
class анкета(StatesGroup):
    gender = State()
    name = State()
    age = State()
    city = State()
    photo = State()
    goal = State()
    confirm = State()

# -------------------------
# /start
# -------------------------
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Моя анкета")

    await message.answer(
        "💗 Добро пожаловать в «СвойЧеловек»\n\n"
        "Здесь можно найти не просто знакомство —\n"
        "а друга, подругу, поддержку или любовь.\n\n"
        "Давай начнём с анкеты ✨",
        reply_markup=kb
    )

# -------------------------
# МОЯ АНКЕТА
# -------------------------
@dp.message_handler(lambda m: m.text == "Моя анкета")
async def my_profile(message: types.Message):
    if message.from_user.id in users:
        u = users[message.from_user.id]
        text = (
            f"👤 {u['name']}, {u['age']}\n"
            f"📍 {u['city']}\n"
            f"💭 {u['goal']}"
        )

        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("Поиск людей")
        kb.add("Изменить анкету")

        await message.answer(text, reply_markup=kb)
    else:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("Парень", "Девушка")
        await message.answer("Кто ты?", reply_markup=kb)
        await анкета.gender.set()

# -------------------------
# СОЗДАНИЕ АНКЕТЫ
# -------------------------
@dp.message_handler(state=анкета.gender)
async def set_gender(message: types.Message, state: FSMContext):
    await state.update_data(gender=message.text)
    await message.answer("Как тебя зовут?")
    await анкета.name.set()

@dp.message_handler(state=анкета.name)
async def set_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Сколько тебе лет?")
    await анкета.age.set()

@dp.message_handler(state=анкета.age)
async def set_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введи число 🙂")
        return
    await state.update_data(age=int(message.text))
    await message.answer("Откуда ты?")
    await анкета.city.set()

@dp.message_handler(state=анкета.city)
async def set_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text)

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Загрузить фото", "Пропустить")

    await message.answer("Хочешь добавить фото?", reply_markup=kb)
    await анкета.photo.set()

@dp.message_handler(lambda m: m.text == "Пропустить", state=анкета.photo)
async def skip_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo=None)
    await message.answer(
        "Кого ты хочешь найти здесь?\n\n"
        "Например:\n"
        "Хочу найти друзей\n"
        "Ищу поддержку\n"
        "Хочу отношений"
    )
    await анкета.goal.set()

@dp.message_handler(content_types=types.ContentType.PHOTO, state=анкета.photo)
async def save_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await message.answer("Кого ты хочешь найти здесь?")
    await анкета.goal.set()

@dp.message_handler(state=анкета.goal)
async def set_goal(message: types.Message, state: FSMContext):
    await state.update_data(goal=message.text)
    data = await state.get_data()

    text = (
        f"👤 {data['name']}, {data['age']}\n"
        f"📍 {data['city']}\n"
        f"💭 {data['goal']}\n\n"
        "Всё верно?"
    )

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Подтвердить", "Изменить")

    if data.get("photo"):
        await message.answer_photo(data["photo"], caption=text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)

    await анкета.confirm.set()

@dp.message_handler(lambda m: m.text == "Подтвердить", state=анкета.confirm)
async def confirm_profile(message: types.Message, state: FSMContext):
    users[message.from_user.id] = await state.get_data()
    await state.finish()

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Моя анкета", "Поиск людей")

    await message.answer("Готово 🤍 Анкета сохранена.", reply_markup=kb)

@dp.message_handler(lambda m: m.text == "Изменить", state="*")
async def edit_profile(message: types.Message, state: FSMContext):
    await state.finish()
    users.pop(message.from_user.id, None)
    await message.answer("Давай создадим анкету заново ✨")
    await my_profile(message)

# -------------------------
# ПОИСК
# -------------------------
@dp.message_handler(lambda m: m.text == "Поиск людей")
async def search(message: types.Message):
    if message.from_user.id not in users:
        await message.answer("Сначала нужно заполнить анкету 🤍")
        return

    for uid, u in users.items():
        if uid != message.from_user.id:
            text = (
                f"👤 {u['name']}, {u['age']}\n"
                f"📍 {u['city']}\n"
                f"💭 {u['goal']}"
            )

            kb = types.InlineKeyboardMarkup()
            kb.add(
                types.InlineKeyboardButton("❤️ Откликается", callback_data=f"like_{uid}"),
                types.InlineKeyboardButton("➡️ Дальше", callback_data="next")
            )

            if u.get("photo"):
                await message.answer_photo(u["photo"], caption=text, reply_markup=kb)
            else:
                await message.answer(text, reply_markup=kb)
            return

    await message.answer("Анкеты закончились 🤍")

# -------------------------
# ЛАЙКИ / МЭТЧ
# -------------------------
@dp.callback_query_handler(lambda c: c.data.startswith("like_"))
async def like(callback: types.CallbackQuery):
    target = int(callback.data.split("_")[1])
    me = callback.from_user.id

    likes.setdefault(target, set()).add(me)

    if me in likes.get(target, set()) and target in likes.get(me, set()):
        await callback.message.answer("💫 У вас взаимный интерес!")
    else:
        await callback.message.answer("❤️ Лайк отправлен")

    await callback.answer()

# -------------------------
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
