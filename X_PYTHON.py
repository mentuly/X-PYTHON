import sys
import logging
import asyncio
import sqlite3
from enum import Enum
from aiogram.filters import Command
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ReactionTypeEmoji

class ChatAction(str, Enum):
    """
    This object represents bot actions.

    Choose one, depending on what the user is about to receive:

    - typing for text messages,
    - upload_photo for photos,
    - record_video or upload_video for videos,
    - record_voice or upload_voice for voice notes,
    - upload_document for general files,
    - choose_sticker for stickers,
    - find_location for location data,
    - record_video_note or upload_video_note for video notes.

    Source: https://core.telegram.org/bots/api#sendchataction
    """

    TYPING = "typing"
    UPLOAD_PHOTO = "upload_photo"
    RECORD_VIDEO = "record_video"
    UPLOAD_VIDEO = "upload_video"
    RECORD_VOICE = "record_voice"
    UPLOAD_VOICE = "upload_voice"
    UPLOAD_DOCUMENT = "upload_document"
    CHOOSE_STICKER = "choose_sticker"
    FIND_LOCATION = "find_location"
    RECORD_VIDEO_NOTE = "record_video_note"
    UPLOAD_VIDEO_NOTE = "upload_video_note"

class Form(StatesGroup):
    income = State()
    expense = State()
    balance = State()

logging.basicConfig(level=logging.INFO)

bot = Bot(token="7030634417:AAFPQlM7jUodHPhJGmA34GKjulFWGdD4lRg")
Token="7030634417:AAFPQlM7jUodHPhJGmA34GKjulFWGdD4lRg"
dp = Dispatcher()

def create_users_table():
    connection = sqlite3.connect('database.db')
    cursor = connection.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        balance REAL DEFAULT 0,  -- Add this line
        reserve REAL DEFAULT 0    -- And this line if needed
    )
    """)
    connection.commit()
    connection.close()

create_users_table()


def create_transactions_table():
    connection = sqlite3.connect('database.db')
    cursor = connection.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        is_income BOOLEAN NOT NULL,
        date DATE NOT NULL
    )
    """)
    connection.commit()
    connection.close()

create_transactions_table()


def create_fixed_expenses_table():
    connection = sqlite3.connect('database.db')
    cursor = connection.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fixed_expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        amount REAL NOT NULL
    )
    """)
    connection.commit()
    connection.close()

create_fixed_expenses_table()

def add_fixed_expenses():
    connection = sqlite3.connect('database.db')
    cursor = connection.cursor()
    cursor.execute("""
    INSERT OR IGNORE INTO fixed_expenses (name, amount) VALUES
        ('Оренда', 500),
        ('Зарплата', 600)
    """)
    connection.commit()
    connection.close()

def get_user_balance(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT balance, reserve FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result if result else (0, 0)

def set_user_balance(user_id, balance):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = ?, reserve = ? WHERE user_id = ?", (balance, balance * 0.20, user_id))
    conn.commit()
    conn.close()

def register_user(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()

def register_expense(user_id, amount):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (amount, user_id))
    cursor.execute('INSERT INTO transactions (user_id, amount, is_income, date) VALUES (?, ?, 0, DATE("now"))', (user_id, amount))
    conn.commit()
    conn.close()

def check_balance(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    balance = cursor.fetchone()
    conn.close()
    return balance[0] if balance else 0

def get_total_for_period(user_id, start_date, end_date, is_income):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT SUM(amount) FROM transactions 
        WHERE user_id = ? AND is_income = ? AND date BETWEEN ? AND ?
    """, (user_id, is_income, start_date, end_date))
    result = cursor.fetchone()[0]
    conn.close()
    return result if result else 0

def get_income_summary_for_date(user_id, date):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ? AND is_income = 1 AND date = ?", (user_id, date))
    result = cursor.fetchone()[0]
    conn.close()
    return result if result else 0

def get_expense_summary_for_date(user_id, date):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ? AND is_income = 0 AND date = ?", (user_id, date))
    result = cursor.fetchone()[0]
    conn.close()
    return result if result else 0

def get_total_for_period_with_fixed_expenses(user_id, start_date, end_date, is_income):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT SUM(amount) FROM transactions 
        WHERE user_id = ? AND is_income = ? AND date BETWEEN ? AND ?
    """, (user_id, is_income, start_date, end_date))
    transaction_result = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT SUM(amount) FROM fixed_expenses
        WHERE user_id = ?
    """, (user_id,))
    fixed_expenses_result = cursor.fetchone()[0]
    
    conn.close()
    
    transaction_amount = transaction_result if transaction_result else 0
    fixed_expenses_amount = fixed_expenses_result if fixed_expenses_result else 0
    
    return transaction_amount - fixed_expenses_amount if is_income else transaction_amount + fixed_expenses_amount

def get_daily_summary(user_id, date):
    start_date = end_date = date
    income = get_total_for_period_with_fixed_expenses(user_id, start_date, end_date, is_income=1)
    expenses = get_total_for_period_with_fixed_expenses(user_id, start_date, end_date, is_income=0)
    net_income = income - expenses
    return income, expenses, net_income

def get_weekly_summary(user_id, date):
    start_date = date - timedelta(days=date.weekday())
    end_date = start_date + timedelta(days=6)
    income = get_total_for_period_with_fixed_expenses(user_id, start_date, end_date, is_income=1)
    expenses = get_total_for_period_with_fixed_expenses(user_id, start_date, end_date, is_income=0)
    net_income = income - expenses
    return income, expenses, net_income

def get_monthly_summary(user_id, date):
    start_date = date.replace(day=1)
    end_date = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

    income = get_total_for_period(user_id, start_date, end_date, is_income=1)
    expenses = get_total_for_period(user_id, start_date, end_date, is_income=0)

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(amount) FROM fixed_expenses WHERE user_id = ?", (user_id,))
    fixed_expenses = cursor.fetchone()[0]
    conn.close()

    income = income if income is not None else 0
    expenses = expenses if expenses is not None else 0
    fixed_expenses = fixed_expenses if fixed_expenses is not None else 0
    
    net_income = income - (expenses + fixed_expenses)
    return income, expenses + fixed_expenses, net_income

def get_yearly_summary(user_id, date):
    start_date = date.replace(month=1, day=1)
    end_date = date.replace(month=12, day=31)
    income = get_total_for_period_with_fixed_expenses(user_id, start_date, end_date, is_income=1)
    expenses = get_total_for_period_with_fixed_expenses(user_id, start_date, end_date, is_income=0)
    net_income = income - expenses
    return income, expenses, net_income

def update_fixed_expenses():
    connection = sqlite3.connect('database.db')
    cursor = connection.cursor()
    cursor.execute("UPDATE fixed_expenses SET amount = ? WHERE name = ?",
                   (500, 'Оренда'))

    cursor.execute("UPDATE fixed_expenses SET amount = ? WHERE name = ?",
                   (600, 'Зарплата'))
    
    connection.commit()
    connection.close()

update_fixed_expenses()

def check_column_exists(db_path, table_name, column_name):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = cursor.fetchall()
    
    column_names = [col[1] for col in columns]
    exists = column_name in column_names
    
    conn.close()
    return exists

db_path = 'database.db'
table_name = 'users'
column_name = 'reserve'

if check_column_exists(db_path, table_name, column_name):
    print(f"Стовпець '{column_name}' існує у таблиці '{table_name}'.")
else:
    print(f"Стовпець '{column_name}' відсутній у таблиці '{table_name}'.")

if check_column_exists(db_path, table_name, column_name):
    print(f"Стовпець '{column_name}' існує у таблиці '{table_name}'.")
else:
    print(f"Стовпець '{column_name}' відсутній у таблиці '{table_name}'.")

def add_column_if_not_exists(db_path, table_name, column_name, column_type):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    if not check_column_exists(db_path, table_name, column_name):
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type};")
        print(f"Стовпець '{column_name}' був успішно доданий до таблиці '{table_name}'.")
    else:
        print(f"Стовпець '{column_name}' вже існує у таблиці '{table_name}'.")
    
    conn.commit()
    conn.close()

db_path = 'database.db'
table_name = 'users'
column_name = 'reserve'
column_type = 'REAL'

def update_balance(user_id, expense_amount):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT balance, reserve FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        balance, reserve = row
        if expense_amount > balance - reserve:
            return False
        else:
            new_balance = balance - expense_amount
            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
            conn.commit()
            conn.close()
            return True
    return False

def add_column_if_not_exists(db_path, table_name, column_name, column_type):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    if not check_column_exists(db_path, table_name, column_name):
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type};")
        print(f"Стовпець '{column_name}' був успішно доданий до таблиці '{table_name}'.")
    else:
        print(f"Стовпець '{column_name}' вже існує у таблиці '{table_name}'.")
    
    conn.commit()
    conn.close()

add_column_if_not_exists('database.db', 'users', 'balance', 'REAL')

def get_sorted_incomes(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT amount, date FROM transactions 
        WHERE user_id = ? AND is_income = 1
        ORDER BY amount DESC
    """, (user_id,))
    incomes = cursor.fetchall()
    conn.close()
    return incomes

def get_sorted_expenses(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT amount, date FROM transactions 
        WHERE user_id = ? AND is_income = 0
        ORDER BY amount ASC
    """, (user_id,))
    expenses = cursor.fetchall()
    conn.close()
    return expenses

MONTHS_UKRAINIAN = {
    1: "Січень",
    2: "Лютий",
    3: "Березень",
    4: "Квітень",
    5: "Травень",
    6: "Червень",
    7: "Липень",
    8: "Серпень",
    9: "Вересень",
    10: "Жовтень",
    11: "Листопад",
    12: "Грудень"
}

async def process_calendar_navigation(callback_query: CallbackQuery, state: FSMContext):

    data = callback_query.data
    _, month, year = data.split(':')

    month = int(month)
    year = int(year)
    start_date = datetime(year, month, 1)
    end_date = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    markup = await generate_calendar_markup(start_date, end_date)

    await callback_query.message.edit_text(
        text=f"Вибраний місяць: {MONTHS_UKRAINIAN[month]} {year}",
        reply_markup=markup
    )

    await state.update_data(month=month, year=year)

async def generate_calendar_markup(start_date, end_date):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    prev_month_button = InlineKeyboardButton(
        text="◀️", callback_data=f"navigate:{(start_date.month - 1) or 12}:{start_date.year - (1 if start_date.month == 1 else 0)}"
    )
    current_month_button = InlineKeyboardButton(
        text=f"{MONTHS_UKRAINIAN[start_date.month]} {start_date.year}", callback_data="current_month"
    )
    next_month_button = InlineKeyboardButton(
        text="▶️", callback_data=f"navigate:{(start_date.month % 12) + 1}:{start_date.year + (1 if start_date.month == 12 else 0)}"
    )

    keyboard.inline_keyboard.append([prev_month_button, current_month_button, next_month_button])

    days_of_week = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
    keyboard.inline_keyboard.append([InlineKeyboardButton(text=day, callback_data="noop") for day in days_of_week])

    first_day = start_date.replace(day=1)
    last_day = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    days = [None] * first_day.weekday()
    days.extend(range(1, last_day.day + 1))

    rows = []
    for day in range(0, len(days), 7):
        week_days = days[day:day+7]
        row = [InlineKeyboardButton(
            text=str(d), callback_data=f"day_{d}_{start_date.month}_{start_date.year}"
        ) if d is not None else InlineKeyboardButton(text=" ", callback_data="noop") for d in week_days]
        rows.append(row)

    for row in rows:
        keyboard.inline_keyboard.append(row)

    return keyboard

async def other_typing_action(chat_id, duration=5):
    await bot.send_chat_action(chat_id, ChatAction.TYPING)
    await asyncio.sleep(duration)

async def send_typing_action(chat_id, duration=3):
    await bot.send_chat_action(chat_id, ChatAction.TYPING)
    await asyncio.sleep(duration)

@dp.message(Command('start'))
async def start(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()
    await other_typing_action(chat_id)
    await message.react([ReactionTypeEmoji(emoji = "👍")])
    await message.answer("Вітаємо у боті! для того щоб продовжити натисніть на /balance")
    
@dp.message(Command('balance'))
async def start_command(message: types.Message, state: FSMContext):
    await message.answer("Для початку введи свій початковий баланс.")
    await state.set_state(Form.balance.state)

@dp.message(Form.balance)
async def process_initial_balance(message: types.Message, state: FSMContext):
    try:
        balance = float(message.text)
        chat_id = message.chat.id
        user_id = message.from_user.id
        set_user_balance(user_id, balance)
        reserve = balance * 0.20
        await other_typing_action(chat_id)
        await message.react([ReactionTypeEmoji(emoji = "👍")])
        await message.answer(f"Баланс встановлено: {balance} де 20% від нього буде недоторканим запасом: {reserve}.")
        await message.answer("Ось доступні команди:\n"
                        "/add_income - Додати дохід\n"
                        "/add_expense - Додати витрати\n"
                        "/show_calendar - Показати календар\n"
                        "/daily_summary - Загальна сума доходів і витрат за день\n"
                        "/weekly_summary - Загальна сума доходів і витрат за тиждень\n"
                        "/monthly_summary - Загальна сума доходів і витрат за місяць\n"
                        "/yearly_summary - Загальна сума доходів і витрат за рік\n")
        await state.clear()
    except ValueError:
        await message.answer("Будь ласка, введіть дійсний числовий баланс.")

@dp.message(Command('add_income'))
async def add_income(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    await send_typing_action(chat_id)
    await message.react([ReactionTypeEmoji(emoji="❤")])
    await message.answer("Введіть суму доходу:")
    await state.set_state(Form.income)

@dp.message(Form.income)
async def process_income_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        user_id = message.from_user.id
        chat_id = message.chat.id

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO transactions (user_id, amount, is_income, date) VALUES (?, ?, 1, ?)",
                       (user_id, amount, datetime.now().date()))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        conn.close()

        await send_typing_action(chat_id)
        await message.react([ReactionTypeEmoji(emoji="❤")])
        await message.answer(f"Дохід у розмірі {amount} додано.")
    except ValueError:
        await send_typing_action(chat_id)
        await message.react([ReactionTypeEmoji(emoji="❤")])
        await message.answer("Будь ласка, введіть правильну суму доходу.")
    finally:
        await state.clear()

@dp.message(Command('add_expense'))
async def add_expense(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    await send_typing_action(chat_id)
    await message.react([ReactionTypeEmoji(emoji="❤")])
    await message.answer("Введіть суму витрат:")
    await state.set_state(Form.expense)

@dp.message(Form.expense)
async def process_expense(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        expense_amount = float(message.text)
        if expense_amount <= 0:
            await message.answer("Сума витрат повинна бути більше нуля.")
            return

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT balance, reserve FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()

        if user:
            balance, reserve = user
            if expense_amount > balance - reserve:
                await message.answer("Сума витрат перевищує недоторканий запас. Ви впевнені, що хочете продовжити?")
                await state.set_data({"expense_amount": expense_amount})
                await state.set_state(Form.expense.state)
            else:
                await register_expense(user_id, expense_amount)
                await message.answer("Витрата успішно зареєстрована.")
        else:
            await message.answer("Користувача не знайдено.")
        
        await state.clear()
    except ValueError:
        await message.answer("Будь ласка, введіть правильну числову суму.")

@dp.message(Command('show_calendar'))
async def show_calendar(message: types.Message):
    today = datetime.now()
    chat_id = message.chat.id
    start_date = today.replace(day=1)
    end_date = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

    markup = await generate_calendar_markup(start_date, end_date)
    await other_typing_action(chat_id)
    await message.react([ReactionTypeEmoji(emoji = "👍")])
    await message.answer("Ваш календар:", reply_markup=markup)

@dp.message(Command('daily_summary'))
async def daily_summary(message: types.Message):
    today = datetime.now().date()
    chat_id = message.chat.id
    user_id = message.from_user.id
    income, expenses, net_income = get_daily_summary(user_id, today)

    month_name = MONTHS_UKRAINIAN[today.month]

    await send_typing_action(chat_id)
    await message.react([ReactionTypeEmoji(emoji="❤")])
    await message.answer(
        f"Дата: {today.day} {month_name} {today.year}\n"
        f"Доходи: {income}\n"
        f"Витрати: {expenses}\n"
        f"Чистий заробіток: {net_income}",
    )

@dp.message(Command('weekly_summary'))
async def weekly_summary(message: types.Message):
    today = datetime.now().date()
    chat_id = message.chat.id
    user_id = message.from_user.id
    income, expenses, net_income = get_weekly_summary(user_id, today)

    await send_typing_action(chat_id)
    await message.react([ReactionTypeEmoji(emoji="❤")])
    await message.answer(
        f"Загальна сума доходів за тиждень: {income}\n"
        f"Загальна сума витрат за тиждень: {expenses}\n"
        f"Чистий заробіток за тиждень: {net_income}",
    )

@dp.message(Command('monthly_summary'))
async def monthly_summary(message: types.Message):
    today = datetime.now().date()
    chat_id = message.chat.id
    user_id = message.from_user.id
    income, expenses, net_income = get_monthly_summary(user_id, today)

    await send_typing_action(chat_id)
    await message.react([ReactionTypeEmoji(emoji="❤")])
    await message.answer(
        f"Загальна сума доходів за місяць: {income}\n"
        f"Загальна сума витрат за місяць: {expenses}\n"
        f"Чистий заробіток за місяць: {net_income}",
    )

@dp.message(Command('yearly_summary'))
async def yearly_summary(message: types.Message):
    today = datetime.now().date()
    chat_id = message.chat.id
    user_id = message.from_user.id
    income, expenses, net_income = get_yearly_summary(user_id, today)

    await send_typing_action(chat_id)
    await message.react([ReactionTypeEmoji(emoji="❤")])
    await message.answer(
        f"Загальна сума доходів за рік: {income}\n"
        f"Загальна сума витрат за рік: {expenses}\n"
        f"Чистий заробіток за рік: {net_income}",
    )

@dp.callback_query(lambda c: c.data.startswith('day_'))
async def process_day_selection(callback_query: types.CallbackQuery):
    data = callback_query.data
    _, day, month, year = data.split('_')
    
    selected_date = datetime(year=int(year), month=int(month), day=int(day)).date()
    user_id = callback_query.from_user.id

    income_summary = get_income_summary_for_date(user_id, selected_date)
    expense_summary = get_expense_summary_for_date(user_id, selected_date)

    month_name = MONTHS_UKRAINIAN[selected_date.month]
    await callback_query.message.answer(
        f"Дата: {day} {month_name} {year}\n"
        f"Доходи: {income_summary}\n"
        f"Витрати: {expense_summary}"
    )

@dp.callback_query(lambda c: c.data.startswith('navigate:'))
async def process_calendar_navigation(callback_query: types.CallbackQuery, state: FSMContext):
    data = callback_query.data
    _, month, year = data.split(':')
    
    month = int(month)
    year = int(year)
    
    start_date = datetime(year, month, 1)
    end_date = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    markup = await generate_calendar_markup(start_date, end_date)
    
    await callback_query.message.edit_text(
        text=f"Вибраний місяць: {MONTHS_UKRAINIAN[month]} {year}",
        reply_markup=markup
    )
    
    await state.update_data(month=month, year=year)

async def main() -> None:
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())