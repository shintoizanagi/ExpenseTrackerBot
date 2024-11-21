from dotenv import load_dotenv
import os
import matplotlib.pyplot as plt
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import sqlite3
import io
import datetime
import pandas as pd

# Загрузка переменных из .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect("finance.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            amount REAL,
            category TEXT,
            note TEXT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# Добавить доход или расход
def add_transaction(user_id, trans_type, amount, category, note):
    conn = sqlite3.connect("finance.db")
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO transactions (user_id, type, amount, category, note)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, trans_type, amount, category, note))
    conn.commit()
    conn.close()

# Получить баланс
def get_balance(user_id):
    conn = sqlite3.connect("finance.db")
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) AS income,
            SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) AS expense
        FROM transactions WHERE user_id = ?
    ''', (user_id,))
    result = cursor.fetchone()
    conn.close()
    income = result[0] if result[0] else 0
    expense = result[1] if result[1] else 0
    return income, expense, income - expense

# Получить статистику по категориям
def get_stats(user_id):
    conn = sqlite3.connect("finance.db")
    cursor = conn.cursor()
    cursor.execute('''
        SELECT category, 
               SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) AS income,
               SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) AS expense
        FROM transactions WHERE user_id = ?
        GROUP BY category
    ''', (user_id,))
    results = cursor.fetchall()
    conn.close()
    return results if results else []

# Создать круговую диаграмму
def create_pie_chart(user_id):
    stats = get_stats(user_id)
    expense_data = [(category, expense) for category, _, expense in stats if expense > 0]
    
    if not expense_data:
        return None  # Если нет данных о расходах

    categories, amounts = zip(*expense_data)

    plt.figure(figsize=(6, 6))
    plt.pie(amounts, labels=categories, autopct='%1.1f%%', startangle=140)
    plt.title("Расходы по категориям")
    plt.tight_layout()

    buffer = io.BytesIO()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    plt.close()
    return buffer

# Получить отчёт за текущий месяц
async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.chat_id
    conn = sqlite3.connect("finance.db")
    cursor = conn.cursor()

    # Получаем текущий месяц и год
    now = datetime.datetime.now()
    start_date = now.replace(day=1)  # Первый день месяца
    end_date = now.replace(day=28) + datetime.timedelta(days=4)  # Последний день месяца
    end_date = end_date.replace(day=1) - datetime.timedelta(days=1)

    cursor.execute('''
        SELECT 
            SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) AS income,
            SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) AS expense
        FROM transactions
        WHERE user_id = ? AND date BETWEEN ? AND ?
    ''', (user_id, start_date, end_date))
    result = cursor.fetchone()
    conn.close()

    income = result[0] if result[0] else 0
    expense = result[1] if result[1] else 0
    balance = income - expense

    await update.message.reply_text(
        f"Отчёт за {now.strftime('%B %Y')}:\n\n"
        f"Доходы: {income:.2f}₽\n"
        f"Расходы: {expense:.2f}₽\n"
        f"Баланс: {balance:.2f}₽"
    )

# Построить график доходов и расходов по дням
def create_line_chart(user_id):
    conn = sqlite3.connect("finance.db")
    cursor = conn.cursor()
    cursor.execute('''
        SELECT date, type, SUM(amount)
        FROM transactions
        WHERE user_id = ?
        GROUP BY date, type
    ''', (user_id,))
    data = cursor.fetchall()
    conn.close()

    if not data:
        return None  # Нет данных для графика

    # Преобразуем данные в DataFrame
    df = pd.DataFrame(data, columns=["date", "type", "amount"])
    df["date"] = pd.to_datetime(df["date"])

    # Построение графика
    plt.figure(figsize=(10, 6))
    for t_type, group in df.groupby("type"):
        group = group.sort_values("date")
        plt.plot(group["date"], group["amount"], label=t_type.capitalize())

    plt.xlabel("Дата")
    plt.ylabel("Сумма (₽)")
    plt.title("Доходы и расходы по дням")
    plt.legend()
    plt.grid()

    buffer = io.BytesIO()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    plt.close()
    return buffer

async def linechart_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.chat_id
    chart = create_line_chart(user_id)

    if chart:
        await update.message.reply_photo(photo=chart, caption="График доходов и расходов по дням")
    else:
        await update.message.reply_text("Нет данных для построения графика.")

# Обработчики команд
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Привет! Я помогу учитывать ваши расходы и доходы. Напишите /help для инструкций.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Доступные команды:\n"
                                    "/balance - Показать текущий баланс\n"
                                    "/stats - Показать статистику по категориям\n"
                                    "/chart - Показать график расходов\n"
                                    "/linechart - Показать график доходов и расходов по дням\n"
                                    "/report - Показать отчёт за месяц\n"
                                    "/transactions - Показать все транзакции\n"
                                    "/delete [ID] - Удалить транзакцию по ID\n\n"
                                    "Для добавления записи:\n"
                                    "`+ [сумма] [категория] | [комментарий]` для доходов\n"
                                    "`- [сумма] [категория] | [комментарий]` для расходов\n\n"
                                    "Пример: `+ 1000 Зарплата | Работа в компании X` или `- 200 Еда | Покупка продуктов`", parse_mode="Markdown")

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.chat_id
    income, expense, balance = get_balance(user_id)
    await update.message.reply_text(
        f"Ваш баланс:\n\nДоходы: {income:.2f}₽\nРасходы: {expense:.2f}₽\nТекущий баланс: {balance:.2f}₽"
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.chat_id
    stats = get_stats(user_id)
    if stats:
        message = "Статистика по категориям:\n"
        for category, income, expense in stats:
            message += f"- {category}: доходы {income:.2f}₽, расходы {expense:.2f}₽\n"
    else:
        message = "Нет данных для статистики."
    await update.message.reply_text(message)

async def chart_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.chat_id
    chart = create_pie_chart(user_id)

    if chart:
        await update.message.reply_photo(photo=chart, caption="Ваши расходы по категориям")
    else:
        await update.message.reply_text("Нет данных для создания графика расходов.")

# Просмотр всех транзакций с ID и комментариями
async def transactions_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.chat_id
    conn = sqlite3.connect("finance.db")
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, type, amount, category, note, date FROM transactions 
        WHERE user_id = ?
    ''', (user_id,))
    results = cursor.fetchall()
    conn.close()

    if results:
        message = "Все транзакции:\n"
        for row in results:
            message += f"ID: {row[0]}, Тип: {row[1]}, Сумма: {row[2]}₽, Категория: {row[3]}, Примечание: {row[4]}, Дата: {row[5]}\n"
    else:
        message = "Нет транзакций для отображения."

    await update.message.reply_text(message)

# Удалить транзакцию
async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.chat_id
    if context.args:
        transaction_id = context.args[0]
        conn = sqlite3.connect("finance.db")
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM transactions WHERE user_id = ? AND id = ?
        ''', (user_id, transaction_id))
        conn.commit()
        conn.close()

        await update.message.reply_text(f"Транзакция с ID {transaction_id} была удалена.")
    else:
        await update.message.reply_text("Пожалуйста, укажите ID транзакции для удаления.")

# Основная функция
def main():
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("chart", chart_command))
    app.add_handler(CommandHandler("linechart", linechart_command))
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CommandHandler("transactions", transactions_command))
    app.add_handler(CommandHandler("delete", delete_command))

    app.run_polling()

if __name__ == "__main__":
    main()
