import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

BOT_TOKEN = "PASTE_YOUR_TOKEN_HERE"

# ================= FSM =================
class ProfileFSM(StatesGroup):
    name = State()
    age = State()
    city = State()
    looking = State()
    about = State()

# ================= KEYBOARDS =================
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Создать анкету")],
        [KeyboardButton(text="👤 Моя анкета")]
    ],
    resize_keyboard=True
)

looking_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💖 Отношения")],
        [KeyboardButton(text="💙 Друга")],
        [KeyboardButton(text="💬 Общение")],
        [KeyboardButton(text="🤍 Пока не знаю")]
    ],
    resize_keyboard=True
)

# ================= TEMP STORAGE =================
profiles = {}  # user_id: profile dict

# ================= HANDLERS =================
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Добро пожаловать 💫\n\nВыбери действие:",
        reply_markup=main_kb
    )

async def create_profile(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(ProfileFSM.name)
    await message.answer("Как тебя можно называть? 🙂")

async def set_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(ProfileFSM.age)
    await message.answer("Сколько тебе лет?")

async def set_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите возраст числом 🙏")
        return

    age = int(message.text)
    if age < 16 or age > 100:
        await message.answer("Возраст от 16 до 100")
        return

    await state.update_data(age=age)
    await state.set_state(ProfileFSM.city)
    await message.answer("Из какого ты города?")

async def set_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(ProfileFSM.looking)
    await message.answer("Кого ты ищешь?", reply_markup=looking_kb)

async def set_looking(message: Message, state: FSMContext):
    await state.update_data(looking=message.text)
    await state.set_state(ProfileFSM.about)
    await message.answer("Напиши немного о себе 🤍")

async def set_about(message: Message, state: FSMContext):
    data = await state.get_data()
    data["about"] = message.text

    profiles[message.from_user.id] = data

    text = (
        f"{data['name']}, {data['age']}\n"
        f"{data['city']}\n"
        f"Ищу: {data['looking']}\n\n"
        f"{data['about']}"
    )

    await state.clear()
    await message.answer("Анкета создана 🎉")
    await message.answer(text, reply_markup=main_kb)

async def my_profile(message: Message):
    profile = profiles.get(message.from_user.id)
    if not profile:
        await message.answer("Анкета не найдена 😔", reply_markup=main_kb)
        return

    text = (
        f"{profile['name']}, {profile['age']}\n"
        f"{profile['city']}\n"
        f"Ищу: {profile['looking']}\n\n"
        f"{profile['about']}"
    )
    await message.answer(text, reply_markup=main_kb)

# ================= MAIN =================
async def main():
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.register(start, Command("start"))
    dp.message.register(create_profile, F.text == "➕ Создать анкету")

    dp.message.register(set_name, ProfileFSM.name)
    dp.message.register(set_age, ProfileFSM.age)
    dp.message.register(set_city, ProfileFSM.city)
    dp.message.register(set_looking, ProfileFSM.looking)
    dp.message.register(set_about, ProfileFSM.about)

    dp.message.register(my_profile, F.text == "👤 Моя анкета")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
