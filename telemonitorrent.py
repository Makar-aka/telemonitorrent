import os
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from dotenv import load_dotenv
import schedule
import time
from threading import Thread
import logging
from rutracker_api import RutrackerAPI

# Загрузка переменных окружения из файла .env
load_dotenv()
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 10))
BOT_TOKEN = os.getenv('BOT_TOKEN')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = os.getenv('LOG_FORMAT', '%(asctime)s - %(levelname)s - %(message)s')
USE_PROXY = os.getenv('USE_PROXY', 'False').lower() == 'true'
HTTP_PROXY = os.getenv('HTTP_PROXY')
HTTPS_PROXY = os.getenv('HTTPS_PROXY')
RUTRACKER_USERNAME = os.getenv('RUTRACKER_USERNAME')
RUTRACKER_PASSWORD = os.getenv('RUTRACKER_PASSWORD')

# Настройка логирования
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# Путь к базе данных SQLite
db_path = 'database.db'

# Инициализация RutrackerAPI
rutracker_api = RutrackerAPI(RUTRACKER_USERNAME, RUTRACKER_PASSWORD)

# Функция для инициализации базы данных
def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS pages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT,
                        url TEXT,
                        date TEXT,
                        last_checked TEXT)''')
    # Добавление столбца last_checked, если он отсутствует
    cursor.execute("PRAGMA table_info(pages)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'last_checked' not in columns:
        cursor.execute("ALTER TABLE pages ADD COLUMN last_checked TEXT")
    conn.commit()
    conn.close()
    logger.info("База данных инициализирована")

# Функция для добавления страницы в базу данных
def add_page(title, url):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO pages (title, url) VALUES (?, ?)", (title, url))
    conn.commit()
    conn.close()
    logger.info(f"Страница {title} добавлена для мониторинга")

# Функция для получения списка страниц из базы данных
def get_pages():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, url, date, last_checked FROM pages")
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
    logger.info(f"Ссылка для страницы с ID {page_id} обновлена")

# Функция для обновления даты страницы в базе данных
def update_page_date(page_id, new_date):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE pages SET date = ? WHERE id = ?", (new_date, page_id))
    conn.commit()
    conn.close()
    logger.info(f"Дата для страницы с ID {page_id} обновлена")

# Функция для обновления времени последней проверки страницы в базе данных
def update_last_checked(page_id):
    last_checked = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE pages SET last_checked = ? WHERE id = ?", (last_checked, page_id))
    conn.commit()
    conn.close()
    logger.info(f"Время последней проверки для страницы с ID {page_id} обновлено")

# Функция для удаления страницы из базы данных
def delete_page(page_id):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pages WHERE id = ?", (page_id,))
    conn.commit()
    conn.close()
    logger.info(f"Страница с ID {page_id} удалена")

# Функция для проверки изменений на страницах
def check_pages():
    pages = get_pages()
    for page in pages:
        page_id, title, url, old_date, _ = page
        page_content = rutracker_api.get_page_content(url)
        new_date = rutracker_api.parse_date(page_content)
        if new_date and new_date != old_date:
            torrent_url = 'URL_ТОРРЕНТ_ФАЙЛА'  # Замените на URL торрент-файла
            torrent_file_path = f'torrents/{page_id}.torrent'  # Замените на путь к торрент-файлу
            rutracker_api.download_torrent_file(torrent_url, torrent_file_path)
            update_page_date(page_id, new_date)
            logger.info(f"Дата для страницы {title} обновлена и торрент-файл скачан")
        update_last_checked(page_id)

# Обработчик команды /start
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Привет! Используйте /add <ссылка> для добавления страницы и /list для просмотра страниц.')
    logger.info("Команда /start выполнена")

# Обработчик команды /add
def add(update: Update, context: CallbackContext) -> None:
    if len(context.args) != 1:
        update.message.reply_text('Использование: /add <ссылка>')
        logger.warning("Неправильное использование команды /add")
        return

    url = context.args[0]
    title = rutracker_api.get_page_title(url)
    add_page(title, url)
    update.message.reply_text(f'Страница {title} добавлена для мониторинга.')
    logger.info(f"Команда /add выполнена для URL: {url}")

# Обработчик команды /list
def list_pages(update: Update, context: CallbackContext) -> None:
    pages = get_pages()
    if not pages:
        update.message.reply_text('Нет страниц для мониторинга.')
        logger.info("Команда /list выполнена: нет страниц для мониторинга")
        return

    keyboard = [[InlineKeyboardButton(page[1], callback_data=f"page_{page[0]}")] for page in pages]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Страницы для мониторинга:', reply_markup=reply_markup)
    logger.info("Команда /list выполнена")

# Обработчик нажатий на кнопки
def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    data = query.data.split('_')
    action = data[0]
    page_id = int(data[1])

    if action == 'page':
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT url, date, last_checked FROM pages WHERE id = ?", (page_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            url, date, last_checked = row
            edit_date = rutracker_api.get_edit_date(url)
            keyboard = [
                [InlineKeyboardButton("Update", callback_data=f"update_{page_id}"),
                 InlineKeyboardButton("Delete", callback_data=f"delete_{page_id}"),
                 InlineKeyboardButton(f"Обновить сейчас ({last_checked})", callback_data=f"refresh_{page_id}"),
                 InlineKeyboardButton("Раздача", url=url)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.edit_message_text(text=f'Дата: {edit_date}', reply_markup=reply_markup)
            logger.info(f"Кнопка страницы с ID {page_id} нажата, дата: {edit_date}")

    elif action == 'update':
        query.edit_message_text(text=f'Введите новую ссылку для страницы с ID {page_id} с помощью команды /update {page_id} <ссылка>')
        logger.info(f"Кнопка обновления для страницы с ID {page_id} нажата")

    elif action == 'delete':
        delete_page(page_id)
        query.edit_message_text(text=f'Страница с ID {page_id} удалена')
        logger.info(f"Кнопка удаления для страницы с ID {page_id} нажата")

    elif action == 'refresh':
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM pages WHERE id = ?", (page_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            url = row[0]
            edit_date = rutracker_api.get_edit_date(url)
            update_last_checked(page_id)
            keyboard = [[InlineKeyboardButton("Назад", callback_data="back_to_list")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.edit_message_text(text=f'Дата: {edit_date}', reply_markup=reply_markup)
            logger.info(f"Кнопка обновления сейчас для страницы с ID {page_id} нажата, дата: {edit_date}")

    elif action == 'back_to_list':
        list_pages(query, context)

# Обработчик команды /update
def update_page(update: Update, context: CallbackContext) -> None:
    if len(context.args) != 2:
        update.message.reply_text('Использование: /update <ID> <ссылка>')
        logger.warning("Неправильное использование команды /update")
        return

    page_id = int(context.args[0])
    new_url = context.args[1]
    update_page_url(page_id, new_url)
    update.message.reply_text(f'Ссылка для страницы с ID {page_id} обновлена.')
    logger.info(f"Команда /update выполнена для страницы с ID {page_id}")

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





