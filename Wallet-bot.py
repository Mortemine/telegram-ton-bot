import os
import sqlite3
import asyncio
from aiogram import Bot, Dispatcher, Router, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Загрузка конфигурации из .env файла
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(',') if id]

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Подключение к базе данных
conn = sqlite3.connect('balances.db')
cursor = conn.cursor()

# Создание таблиц, если их нет
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance_ton REAL DEFAULT 0,
    balance_usdt REAL DEFAULT 0,
    balance_bac REAL DEFAULT 0,
    referral_id INTEGER
)
''')
conn.commit()

# Функция создания кошелька (имитация)
def create_wallet(user_id):
    pass

# Создание клавиатуры
def get_keyboard():
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

# Приветственное сообщение
@router.message(lambda message: message.text == "/start")
async def start_command(message: Message):
    user_id = message.from_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    await message.reply("Добро пожаловать! Выберите действие:", reply_markup=get_keyboard())

# Проверка баланса
@router.message(lambda message: message.text == "Проверить баланс")
async def check_balance(message: Message):
    user_id = message.from_user.id
    cursor.execute("SELECT balance_ton, balance_usdt, balance_bac FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if result:
        ton, usdt, bac = result
        await message.reply(f"Ваш баланс:\nTON: {ton}\nUSDT: {usdt}\nBAC: {bac}")
    else:
        await message.reply("Вы не зарегистрированы. Используйте /start.")

# Пополнение баланса
@router.message(lambda message: message.text == "Пополнить баланс")
async def deposit(message: Message):
    user_id = message.from_user.id
    await message.reply("Для пополнения используйте ваш TON-кошелек.")

# Отправка токенов другому пользователю
@router.message(lambda message: message.text == "Отправить токены")
async def send_tokens(message: Message):
    await message.reply("Введите данные в формате: <user_id> <token> <amount>")

# Административное начисление токенов
@router.message(lambda message: message.text == "Начислить токены (админ)")
async def add_tokens(message: Message):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        await message.reply("У вас нет прав на выполнение этой команды.")
        return
    await message.reply("Введите данные в формате: <user_id> <token> <amount>")

# Обработка ввода данных для отправки или начисления токенов
@router.message()
async def process_input(message: Message):
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

    # Если это админская команда
    if message.text.startswith("Начислить"):
        cursor.execute(f"UPDATE users SET balance_{token} = balance_{token} + ? WHERE user_id = ?", (amount, target_id))
        conn.commit()
        await message.reply(f"Начислено {amount} {token.upper()} пользователю {target_id}.")
    else:
        # Проверка баланса отправителя
        cursor.execute(f"SELECT balance_{token} FROM users WHERE user_id = ?", (user_id,))
        sender_balance = cursor.fetchone()
        if not sender_balance or sender_balance[0] < amount:
            await message.reply("Недостаточно средств.")
            return
        cursor.execute(f"UPDATE users SET balance_{token} = balance_{token} - ? WHERE user_id = ?", (amount, user_id))
        cursor.execute(f"UPDATE users SET balance_{token} = balance_{token} + ? WHERE user_id = ?", (amount, target_id))
        conn.commit()
        await message.reply(f"Вы успешно отправили {amount} {token.upper()} пользователю {target_id}.")

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