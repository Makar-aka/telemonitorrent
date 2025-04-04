import os
import sqlite3
import requests
from bs4 import BeautifulSoup
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from dotenv import load_dotenv
import schedule
import time
from threading import Thread

# Загрузка переменных окружения из файла .env
load_dotenv()
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 10))
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Путь к базе данных SQLite
db_path = 'database.db'

# Функция для инициализации базы данных
def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS pages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT,
                        url TEXT,
                        date TEXT)''')
    conn.commit()
    conn.close()

# Функция для добавления страницы в базу данных
def add_page(title, url):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO pages (title, url) VALUES (?, ?)", (title, url))
    conn.commit()
    conn.close()

# Функция для получения списка страниц из базы данных
def get_pages():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, url, date FROM pages")
    pages = cursor.fetchall()
    conn.close()
    return pages

# Функция для обновления ссылки страницы в базе данных
def update_page_url(page_id, new_url):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE pages SET url = ? WHERE id = ?", (new_url, page_id))
    conn.commit()
    conn.close()

# Функция для обновления даты страницы в базе данных
def update_page_date(page_id, new_date):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE pages SET date = ? WHERE id = ?", (new_date, page_id))
    conn.commit()
    conn.close()

# Функция для получения содержимого страницы
def get_page_content(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.text

# Функция для парсинга даты с страницы
def parse_date(page_content):
    soup = BeautifulSoup(page_content, 'html.parser')
    date_span = soup.find('span', class_='posted_since hide-for-print')
    if date_span:
        date_text = date_span.text
        match = re.search(r'ред\. (\d{2}-\w{3}-\d{2} \d{2}:\d{2})', date_text)
        if match:
            return match.group(1)
    return None

# Функция для скачивания торрент-файла
def download_torrent_file(url, file_path):
    response = requests.get(url)
    response.raise_for_status()
    with open(file_path, 'wb') as file:
        file.write(response.content)

# Функция для проверки изменений на страницах
def check_pages():
    pages = get_pages()
    for page in pages:
        page_id, title, url, old_date = page
        page_content = get_page_content(url)
        new_date = parse_date(page_content)
        if new_date and new_date != old_date:
            torrent_url = 'URL_ТОРРЕНТ_ФАЙЛА'  # Замените на URL торрент-файла
            torrent_file_path = f'torrents/{page_id}.torrent'  # Замените на путь к торрент-файлу
            download_torrent_file(torrent_url, torrent_file_path)
            update_page_date(page_id, new_date)
            print(f"Дата для страницы {title} обновлена и торрент-файл скачан.")

# Обработчик команды /start
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Привет! Используйте /add <ссылка> для добавления страницы и /list для просмотра страниц.')

# Обработчик команды /add
def add(update: Update, context: CallbackContext) -> None:
    if len(context.args) != 1:
        update.message.reply_text('Использование: /add <ссылка>')
        return

    url = context.args[0]
    title = 'Title'  # Здесь можно добавить логику для получения заголовка страницы
    add_page(title, url)
    update.message.reply_text(f'Страница {title} добавлена для мониторинга.')

# Обработчик команды /list
def list_pages(update: Update, context: CallbackContext) -> None:
    pages = get_pages()
    if not pages:
        update.message.reply_text('Нет страниц для мониторинга.')
        return

    keyboard = [[InlineKeyboardButton(page[1], callback_data=str(page[0]))] for page in pages]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Страницы для мониторинга:', reply_markup=reply_markup)

# Обработчик нажатий на кнопки
def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    page_id = int(query.data)
    query.edit_message_text(text=f'Вы выбрали страницу с ID {page_id}. Используйте /update <ссылка> для обновления.')

# Обработчик команды /update
def update_page(update: Update, context: CallbackContext) -> None:
    if len(context.args) != 2:
        update.message.reply_text('Использование: /update <ID> <ссылка>')
        return

    page_id = int(context.args[0])
    new_url = context.args[1]
    update_page_url(page_id, new_url)
    update.message.reply_text(f'Ссылка для страницы с ID {page_id} обновлена.')

def main() -> None:
    # Инициализация базы данных
    init_db()

    # Создание объекта Updater и передача ему токена вашего бота
    updater = Updater(BOT_TOKEN)

    # Получение диспетчера для регистрации обработчиков
    dispatcher = updater.dispatcher

    # Регистрация обработчиков команд
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("add", add))
    dispatcher.add_handler(CommandHandler("list", list_pages))
    dispatcher.add_handler(CommandHandler("update", update_page))
    dispatcher.add_handler(CallbackQueryHandler(button))

    # Запуск планировщика задач
    schedule.every(CHECK_INTERVAL).minutes.do(check_pages)

    def run_schedule():
        while True:
            schedule.run_pending()
            time.sleep(1)

    # Запуск планировщика в отдельном потоке
    schedule_thread = Thread(target=run_schedule)
    schedule_thread.start()

    # Запуск бота
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
