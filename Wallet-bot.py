import os
import asyncio
import pymongo
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

# Загрузка конфигурации из .env файла
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_IDS = [int(adm_id) for adm_id in os.getenv("ADMIN_IDS", "").split(':') if id]
MONGODB_URI = os.getenv("MONGODB_URI")


def connect_db():
    try:
        mongo_uri = MONGODB_URI

        if not mongo_uri:
            raise ValueError("❌ Отсутствует переменная окружения MONGODB_URI")

        mongo_client = pymongo.MongoClient(mongo_uri)
        mongo_db = mongo_client["BacTokenData"]
        print("✅ Подключено к базе BacTokenData")

        return mongo_db, mongo_client
    except Exception as error:
        print("❌ Ошибка подключения к MongoDB:", error)
        exit(1)


bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

db, client = connect_db()
collection = db['bactokenbotusers']

recipient_types = {"ID": "user_id", "Номер телефона": "phone_number", "Username": "username"}


def get_data_with_struct(user_id, phone_number, username, balances, transactions):
    return {
        "user_id": user_id,
        "registration_date": datetime.now(),
        "phone_number": phone_number,
        "username": username,
        "balances": balances,
        "transactions": transactions
    }


class AdminActions(StatesGroup):
    WAITING_FOR_ADD_TOKENS = State()


class UserActions(StatesGroup):
    WAITING_FOR_ADD_TOKENS = State()


def create_wallet(user_id):
    pass


def reg_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Регистрация", request_contact=True)],
        ],
        resize_keyboard=True
    )
    return keyboard


class SendTokensStates(StatesGroup):
    CHOOSE_RECIPIENT_TYPE = State()  # Выбор типа получателя
    ENTER_RECIPIENT = State()  # Ввод данных получателя
    CHOOSE_CURRENCY = State()  # Выбор валюты
    ENTER_AMOUNT = State()  # Ввод количества


# Клавиатуры
def recipient_type_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="ID"), KeyboardButton(text="Номер телефона")],
            [KeyboardButton(text="Username"), KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True
    )


def currency_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="TON"), KeyboardButton(text="USDT")],
            [KeyboardButton(text="BAC"), KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True
    )


def base_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Проверить баланс"), KeyboardButton(text="➕ Пополнить баланс")],
            [KeyboardButton(text="📤 Отправить токены"), KeyboardButton(text="🆔 Посмотреть мой ID")],
            [KeyboardButton(text="🌐 Сервисы BAC Community")],
            [KeyboardButton(text="👑 Начислить токены (админ)")]

        ],
        resize_keyboard=True
    )
    return keyboard


def back_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True
    )
    return keyboard


# Начало процесса отправки токенов
@router.message(F.text == "📤 Отправить токены")
async def start_send_tokens(message: Message, state: FSMContext):
    await message.reply("Выберите способ:", reply_markup=recipient_type_keyboard())
    await state.set_state(SendTokensStates.CHOOSE_RECIPIENT_TYPE)


# Обработка выбора типа получателя
@router.message(SendTokensStates.CHOOSE_RECIPIENT_TYPE)
async def choose_recipient_type(message: Message, state: FSMContext):
    if message.text == "🔙 Назад":
        await message.reply("Возвращаемся в главное меню.", reply_markup=base_keyboard())
        await state.clear()
        return

    if message.text not in ["ID", "Номер телефона", "Username"]:
        await message.reply("Пожалуйста, выберите один из предложенных вариантов.")
        return

    await state.update_data(recipient_type=message.text)
    if message.text == "ID":
        await message.reply(f"Введите id пользователя в телеграм (можно узнать в главном меню)")
    elif message.text == "Номер телефона":
        await message.reply(f"Введите номер телефона получателя в формате 7ХХХХХХХХХХ")
    elif message.text == "Username":
        await message.reply(f"Введите username пользователя в телеграм (без @)")
    await state.set_state(SendTokensStates.ENTER_RECIPIENT)


# Обработка ввода данных получателя
@router.message(SendTokensStates.ENTER_RECIPIENT)
async def enter_recipient(message: Message, state: FSMContext):
    if message.text == "🔙 Назад":
        await message.reply("Выберите способ:", reply_markup=recipient_type_keyboard())
        await state.set_state(SendTokensStates.CHOOSE_RECIPIENT_TYPE)
        return

    data = await state.get_data()
    recipient_type = data.get("recipient_type")
    user = None

    # Проверка существования пользователя в базе
    if recipient_type == 'ID':
        user = collection.find_one({"user_id": message.text})
    elif recipient_type == 'Номер телефона':
        user = collection.find_one({"phone_number": message.text})
    elif recipient_type == 'Username':
        user = collection.find_one({"username": message.text})
    if not user:
        await message.reply("Пользователь не найден. Попробуйте снова.")
        return

    await state.update_data(recipient=message.text)
    await message.reply("Выберите валюту:", reply_markup=currency_keyboard())
    await state.set_state(SendTokensStates.CHOOSE_CURRENCY)


# Обработка выбора валюты
@router.message(SendTokensStates.CHOOSE_CURRENCY)
async def choose_currency(message: Message, state: FSMContext):
    if message.text == "🔙 Назад":
        await message.reply("Выберите способ:", reply_markup=recipient_type_keyboard())
        await state.set_state(SendTokensStates.CHOOSE_RECIPIENT_TYPE)
        return

    if message.text not in ["TON", "USDT", "BAC"]:
        await message.reply("Пожалуйста, выберите одну из поддерживаемых валют.")
        return

    await state.update_data(currency=message.text)
    await message.reply("Введите количество:")
    await state.set_state(SendTokensStates.ENTER_AMOUNT)


# Обработка ввода количества
@router.message(SendTokensStates.ENTER_AMOUNT)
async def enter_amount(message: Message, state: FSMContext):
    if message.text == "🔙 Назад":
        # Возвращаемся к выбору валюты
        await message.reply("Выберите валюту:", reply_markup=currency_keyboard())
        await state.set_state(SendTokensStates.CHOOSE_CURRENCY)
        return

    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.reply("Введите корректное положительное число.")
        return

    data = await state.get_data()
    recipient = data.get("recipient")
    currency = data.get("currency")
    user_id = message.from_user.id
    recipient_type = recipient_types[data.get("recipient_type")]

    # Проверка баланса отправителя
    sender_balance = collection.find_one({"user_id": user_id})["balances"][currency]

    if sender_balance < amount:
        await message.reply("Недостаточно средств на балансе. Попробуйте снова.")
        return

    # Выполнение перевода
    recipient_id = collection.find_one({recipient_type: recipient})["user_id"]

    current_balance = collection.find_one({recipient_type: recipient})["balances"][currency]
    sender_current_balance = collection.find_one({"user_id": user_id})["balances"][currency]
    collection.update_one({"user_id": user_id}, {"$inc": {f"balances.{currency.upper()}": -amount},
                                                 "$push": {
                                                     "transactions": {"Type": "Send", "From": user_id, "To": recipient,
                                                                      "Token": currency, "Amount": amount,
                                                                      "New_balance": sender_current_balance - amount,
                                                                      "Date": datetime.now()}}})
    collection.update_one({recipient_type: recipient}, {"$inc": {f"balances.{currency.upper()}": amount},
                                                        "$push": {"transactions": {"Type": "Send", "From": user_id,
                                                                                   "To": recipient, "Token": currency,
                                                                                   "Amount": amount,
                                                                                   "New_balance": current_balance + amount,
                                                                                   "Date": datetime.now()}}})
    await message.reply(f"Перевод {amount} {currency} выполнен успешно.")
    await message.reply("Возвращаемся в главное меню.", reply_markup=base_keyboard())
    await bot.send_message(recipient_id, f"Вам начислены токены {currency}: {amount} от {user_id}")

    await state.clear()


@router.message(lambda message: message.text == "🆔 Посмотреть мой ID")
async def send_tokens(message: Message):
    await message.reply(f"Ваш ID: {message.from_user.id}")


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
        balances = {"TON": 0.0, "USDT": 0.0, "BAC": 0.0}
        transactions = []
        data = get_data_with_struct(user_id, phone_number, username, balances, transactions)
        collection.insert_one(data)
        await message.reply("Регистрация успешна.", reply_markup=base_keyboard())
    else:
        await message.reply("Вы уже зарегистрированы.", reply_markup=base_keyboard())


@router.message(lambda message: message.text == "💰 Проверить баланс")
async def check_balance(message: Message):
    user_id = message.from_user.id
    balance = collection.find_one({"user_id": user_id})["balances"]
    if balance:
        await message.reply(f"Ваш баланс:\nTON: {balance['TON']}\nUSDT: {balance['USDT']}\nBAC: {balance['BAC']}")
    else:
        await message.reply("Вы не зарегистрированы. Используйте /start.")


@router.message(lambda message: message.text == "➕ Пополнить баланс")
async def deposit(message: Message):
    await message.reply("Для пополнения используйте ваш TON-кошелек.")


@router.message(lambda message: message.text == "👑 Начислить токены (админ)")
async def add_tokens(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        await message.reply("У вас нет прав на выполнение этой команды.")
        return
    await message.reply("Для начисления введите данные в формате: <user_id> <token> <amount>",
                        reply_markup=back_keyboard())
    # Устанавливаем состояние ожидания данных для начисления
    await state.set_state(AdminActions.WAITING_FOR_ADD_TOKENS)


# Обработка ввода данных для отправки или начисления токенов
@router.message(AdminActions.WAITING_FOR_ADD_TOKENS)
async def process_admin_add_tokens(message: Message, state: FSMContext):
    if message.text == "Отмена":
        await message.reply("Возвращаемся в главное меню.", reply_markup=base_keyboard())
        await state.clear()
        return
    text = message.text.split()
    if len(text) != 3:
        await message.reply("Неверный формат данных. Используйте: <user_id> <token> <amount>")
        return
    try:
        target_id = int(text[0])
        token = text[1].upper()
        amount = float(text[2])
    except ValueError:
        await message.reply("Неверный формат данных.")
        return
    if token not in ['TON', 'USDT', 'BAC']:
        await message.reply("Поддерживаются только токены: TON, USDT, BAC.")
        return

    # Выполняем начисление
    recipient = collection.find_one({"user_id": target_id})
    if recipient:
        current_balance = recipient["balances"][token]
        collection.update_one({"user_id": target_id}, {"$inc": {f"balances.{token}": amount},
                                                       "$push": {
                                                           "transactions": {"Type": "ADM", "From": message.from_user.id,
                                                                            "To": target_id, "Token": token,
                                                                            "Amount": amount,
                                                                            "New_balance": current_balance + amount,
                                                                            "Date": datetime.now()}}})
        await message.reply(f"Начислено {amount} {token} пользователю {target_id}.")
        await bot.send_message(target_id, f"Вам были начислены токены {token}: {amount}")
    else:
        await message.reply(f"Пользователь не найден")
        return
    # Сбрасываем состояние
    await state.clear()


# Ежедневное начисление процентов по стейкингу
scheduler = AsyncIOScheduler()


def daily_staking():
    pass


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
