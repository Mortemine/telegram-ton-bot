import os
import sqlite3
import asyncio
import pymongo
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime


# Загрузка конфигурации из .env файла
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(':') if id]
MONGODB_URI = os.getenv("MONGODB_URI")

def connect_db():
    try:
        mongo_uri = MONGODB_URI
        
        if not mongo_uri:
            raise ValueError("❌ Отсутствует переменная окружения MONGODB_URI")
        
        client = pymongo.MongoClient(mongo_uri)
        db = client["BacTokenData"]
        print("✅ Подключено к базе BacTokenData")

        return db, client
    except Exception as error:
        print("❌ Ошибка подключения к MongoDB:", error)
        exit(1)

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Подключение к базе данных
db, client = connect_db()
collection = db['bactokenbotusers']

def get_data_with_struct(user_id, phone_number, username, balances, transactions):
    return {
        "user_id": user_id,
        "registration_date": datetime.utcnow(),
        "phone_number": phone_number,
        "username": username,
        "balances": balances,
        "transactions": transactions
    }

class AdminActions(StatesGroup):
    WAITING_FOR_ADD_TOKENS = State()

class UserActions(StatesGroup):
    WAITING_FOR_ADD_TOKENS = State()

# Функция создания кошелька (имитация)
def create_wallet(user_id):
    pass

# Создание клавиатуры
def base_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Проверить баланс")],
            [KeyboardButton(text="Пополнить баланс")],
            [KeyboardButton(text="Отправить токены")],
            [KeyboardButton(text="Начислить токены (админ)")],
        ],
        resize_keyboard=True  # Адаптируем размер клавиатуры
    )
    return keyboard

def reg_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Регистрация", request_contact=True)],
        ],
        resize_keyboard=True  # Адаптируем размер клавиатуры
    )
    return keyboard

# Приветственное сообщение
@router.message(lambda message: message.text == "/start")
async def start_command(message: Message):
    user = collection.find_one({"user_id": message.from_user.id})

    if user:
        await message.reply("Добро пожаловать! Выберите действие:", reply_markup=base_keyboard())
    else:
        await message.reply("Добро пожаловать! Для дальнейшей работы зарегистрируйтесь.", reply_markup=reg_keyboard())

@dp.message(F.contact)
async def start_command(message: Message):
    user = collection.find_one({"user_id": message.from_user.id})
    if not user:
        user_id = message.from_user.id
        phone_number = message.contact.phone_number
        username = message.from_user.username
        balances = {"TON": 0, "USDT": 0, "BAC": 0}
        transactions = []
        data = get_data_with_struct(user_id, phone_number, username, balances, transactions)
        collection.insert_one(data)
        await message.reply("Регистрация успешна.", reply_markup=base_keyboard())
    else:
        await message.reply("Вы уже зарегистрированы.", reply_markup=base_keyboard())

# Проверка баланса
@router.message(lambda message: message.text == "Проверить баланс")
async def check_balance(message: Message):
    user_id = message.from_user.id
    balance = collection.find_one({"user_id": user_id})["balances"]
    if balance:
        await message.reply(f"Ваш баланс:\nTON: {balance['TON']}\nUSDT: {balance['USDT']}\nBAC: {balance['BAC']}")
    else:
        await message.reply("Вы не зарегистрированы. Используйте /start.")

# Пополнение баланса
@router.message(lambda message: message.text == "Пополнить баланс")
async def deposit(message: Message):
    user_id = message.from_user.id
    await message.reply("Для пополнения используйте ваш TON-кошелек.")

# Отправка токенов другому пользователю
@router.message(lambda message: message.text == "Отправить токены")
async def send_tokens(message: Message, state: FSMContext):
    await message.reply("Для перевода введите данные в формате: <user_id> <token> <amount>")
    await state.set_state(UserActions.WAITING_FOR_ADD_TOKENS)

# Административное начисление токенов
@router.message(lambda message: message.text == "Начислить токены (админ)")
async def add_tokens(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        await message.reply("У вас нет прав на выполнение этой команды.")
        return
    await message.reply("Для начисления введите данные в формате: <user_id> <token> <amount>")
    # Устанавливаем состояние ожидания данных для начисления
    await state.set_state(AdminActions.WAITING_FOR_ADD_TOKENS)

# Обработка ввода данных для отправки или начисления токенов
@router.message(AdminActions.WAITING_FOR_ADD_TOKENS)
async def process_admin_add_tokens(message: Message, state: FSMContext):
    text = message.text.split()
    if len(text) != 3:
        await message.reply("Неверный формат данных. Используйте: <user_id> <token> <amount>")
        return
    try:
        target_id = int(text[0])
        token = text[1].lower()
        amount = float(text[2])
    except ValueError:
        await message.reply("Неверный формат данных.")
        return
    if token not in ['ton', 'usdt', 'bac']:
        await message.reply("Поддерживаются только токены: TON, USDT, BAC.")
        return

    # Выполняем начисление
    collection.update_one({"user_id": target_id}, {"$inc": {f"balances.{token.upper()}": amount}})
    await message.reply(f"Начислено {amount} {token.upper()} пользователю {target_id}.")
    # Сбрасываем состояние
    await state.clear()

@router.message(UserActions.WAITING_FOR_ADD_TOKENS)
async def process_input(message: Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text.split()
    if len(text) != 3:
        await message.reply("Неверный формат данных. Используйте: <user_id> <token> <amount>")
        return
    try:
        target_id = int(text[0])
        token = text[1].lower()
        amount = float(text[2])
    except ValueError:
        await message.reply("Неверный формат данных.")
        return
    if token not in ['ton', 'usdt', 'bac']:
        await message.reply("Поддерживаются только токены: TON, USDT, BAC.")
        return

    # Проверка баланса отправителя
    sender_balance = collection.find_one({"user_id": user_id})
    if not sender_balance or sender_balance.get("balances", {}).get(token.upper(), 0) < amount:
        await message.reply("Недостаточно средств.")
        return

    # Выполняем перевод
    collection.update_one({"user_id": user_id}, {"$inc": {f"balances.{token.upper()}": -amount}})
    collection.update_one({"user_id": target_id}, {"$inc": {f"balances.{token.upper()}": amount}})
    await message.reply(f"Вы успешно отправили {amount} {token.upper()} пользователю {target_id}.")
    await state.clear()

# Ежедневное начисление процентов по стейкингу
scheduler = AsyncIOScheduler()

def daily_staking():
    cursor.execute("UPDATE users SET balance_ton = balance_ton * 1.01, balance_usdt = balance_usdt * 1.005, balance_bac = balance_bac * 1.02")
    conn.commit()

scheduler.add_job(daily_staking, 'interval', days=1)

# Запуск бота
async def main():
    scheduler.start()
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        scheduler.shutdown()

if __name__ == '__main__':
    asyncio.run(main())