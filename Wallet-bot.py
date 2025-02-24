import os
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Загрузка конфигурации из .env файла
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(',') if id]

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

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
    # Здесь будет интеграция с TON для генерации кошелька
    pass

# Регистрация пользователя
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    user_id = message.from_user.id
    ref_id = message.get_args()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, referral_id) VALUES (?, ?)", (user_id, ref_id if ref_id else None))
    conn.commit()
    await message.reply("Добро пожаловать! Ваш аккаунт успешно создан.")

# Пополнение баланса (заглушка)
@dp.message_handler(commands=['deposit'])
async def deposit(message: types.Message):
    user_id = message.from_user.id
    # Здесь логика пополнения через TON blockchain
    await message.reply("Для пополнения используйте ваш TON-кошелек.")

# Проверка баланса
@dp.message_handler(commands=['balance'])
async def check_balance(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT balance_ton, balance_usdt, balance_bac FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if result:
        ton, usdt, bac = result
        await message.reply(f"Ваш баланс:\nTON: {ton}\nUSDT: {usdt}\nBAC: {bac}")
    else:
        await message.reply("Вы не зарегистрированы. Используйте /start.")

# Отправка токенов другому пользователю
@dp.message_handler(commands=['send'])
async def send_tokens(message: types.Message):
    user_id = message.from_user.id
    args = message.get_args().split()
    if len(args) != 3:
        await message.reply("Используйте формат: /send <user_id> <token> <amount>")
        return
    try:
        recipient_id = int(args[0])
        token = args[1].lower()
        amount = float(args[2])
    except ValueError:
        await message.reply("Неверный формат данных.")
        return
    if token not in ['ton', 'usdt', 'bac']:
        await message.reply("Поддерживаются только токены: TON, USDT, BAC.")
        return
    cursor.execute(f"SELECT balance_{token} FROM users WHERE user_id = ?", (user_id,))
    sender_balance = cursor.fetchone()
    if not sender_balance or sender_balance[0] < amount:
        await message.reply("Недостаточно средств.")
        return
    cursor.execute(f"UPDATE users SET balance_{token} = balance_{token} - ? WHERE user_id = ?", (amount, user_id))
    cursor.execute(f"UPDATE users SET balance_{token} = balance_{token} + ? WHERE user_id = ?", (amount, recipient_id))
    conn.commit()
    await message.reply(f"Вы успешно отправили {amount} {token.upper()} пользователю {recipient_id}.")

# Административное начисление токенов
@dp.message_handler(commands=['add_tokens'])
async def add_tokens(message: types.Message):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        await message.reply("У вас нет прав на выполнение этой команды.")
        return
    args = message.get_args().split()
    if len(args) != 3:
        await message.reply("Используйте формат: /add_tokens <user_id> <token> <amount>")
        return
    try:
        target_id = int(args[0])
        token = args[1].lower()
        amount = float(args[2])
    except ValueError:
        await message.reply("Неверный формат данных.")
        return
    if token not in ['ton', 'usdt', 'bac']:
        await message.reply("Поддерживаются только токены: TON, USDT, BAC.")
        return
    cursor.execute(f"UPDATE users SET balance_{token} = balance_{token} + ? WHERE user_id = ?", (amount, target_id))
    conn.commit()
    await message.reply(f"Начислено {amount} {token.upper()} пользователю {target_id}.")

# Ежедневное начисление процентов по стейкингу
scheduler = AsyncIOScheduler()

def daily_staking():
    cursor.execute("UPDATE users SET balance_ton = balance_ton * 1.01, balance_usdt = balance_usdt * 1.005, balance_bac = balance_bac * 1.02")
    conn.commit()

scheduler.add_job(daily_staking, 'interval', days=1)
scheduler.start()

# Запуск бота
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
