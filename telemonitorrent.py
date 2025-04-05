import os
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler, CallbackQueryHandler, MessageHandler,
    Filters, CallbackContext, ConversationHandler
)
from dotenv import load_dotenv
import schedule
import time
from threading import Thread
import logging
from rutracker_api import RutrackerAPI

# Состояния для ConversationHandler
WAITING_URL = 1

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
FILE_DIR = os.getenv('FILE_DIR')

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
    page_id = cursor.lastrowid
    conn.commit()
    conn.close()
    logger.info(f"Страница {title} добавлена для мониторинга")

    # Загрузка торрент-файла при добавлении новой страницы
    page_content = rutracker_api.get_page_content(url)
    new_date = rutracker_api.parse_date(page_content)
    if new_date:
        torrent_file_path = os.path.join(FILE_DIR, f'{page_id}.torrent')
        rutracker_api.download_torrent_by_url(url, torrent_file_path)
        update_page_date(page_id, new_date)
        logger.info(f"Торрент-файл для новой страницы {title} скачан в {torrent_file_path}")
    update_last_checked(page_id)

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
            torrent_file_path = os.path.join(FILE_DIR, f'{page_id}.torrent')
            rutracker_api.download_torrent_by_url(url, torrent_file_path)
            update_page_date(page_id, new_date)
            logger.info(f"Дата для страницы {title} обновлена и торрент-файл скачан в {torrent_file_path}")
        update_last_checked(page_id)

# Обработчик команды /start
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Привет! Используйте /add <ссылка> для добавления страницы и /list для просмотра страниц.')
    logger.info("Команда /start выполнена")

# Обработчик команды /add с одним аргументом
def add_with_arg(update: Update, context: CallbackContext) -> None:
    url = context.args[0]
    title = rutracker_api.get_page_title(url)
    add_page(title, url)
    update.message.reply_text(f'Страница {title} добавлена для мониторинга.')
    logger.info(f"Команда /add выполнена для URL: {url}")

# Обработчик команды /add без аргументов - начало диалога добавления
def add_start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Пришли мне ссылку для мониторинга:')
    logger.info("Запрос ссылки отправлен")
    return WAITING_URL

# Обработчик для получения ссылки
def add_url(update: Update, context: CallbackContext) -> int:
    url = update.message.text
    logger.debug(f"Получена ссылка: {url}")
    
    try:
        title = rutracker_api.get_page_title(url)
        logger.debug(f"Получен заголовок: {title}")
        
        add_page(title, url)
        logger.debug("Страница добавлена в базу данных")
        
        keyboard = [[InlineKeyboardButton("Главная", callback_data="back_to_list")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(f'Ссылку поймал и добавил в мониторинг.', reply_markup=reply_markup)
        logger.debug("Отправлено подтверждение добавления")
        
        logger.info(f"Страница {title} добавлена для мониторинга через сообщение")
    except Exception as e:
        logger.error(f"Ошибка при обработке ссылки: {e}")
        update.message.reply_text(f'Произошла ошибка при обработке ссылки: {str(e)}')
    
    return ConversationHandler.END

# Обработчик команды /list
def list_pages(update: Update, context: CallbackContext) -> None:
    pages = get_pages()
    if not pages:
        update.message.reply_text('Нет страниц для мониторинга.')
        logger.info("Команда /list выполнена: нет страниц для мониторинга")
        return

    keyboard = [[InlineKeyboardButton(page[1], callback_data=f"page_{page[0]}")] for page in pages]
    keyboard.append([InlineKeyboardButton("Добавить", callback_data="add_url_button")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Страницы для мониторинга:', reply_markup=reply_markup)
    logger.info("Команда /list выполнена")

# Обработчик нажатий на кнопки
def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    data = query.data.split('_')
    action = data[0]
    logger.debug(f"Обработка действия: {action}")

    if action == 'page':
        page_id = int(data[1])
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT url, date, last_checked FROM pages WHERE id = ?", (page_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            url, date, last_checked = row
            edit_date = rutracker_api.get_edit_date(url)
            keyboard = [
                [InlineKeyboardButton("Назад", callback_data="back_to_list"),
                 InlineKeyboardButton("Delete", callback_data=f"delete_{page_id}"),
                 InlineKeyboardButton(f"Обновить сейчас ({last_checked})", callback_data=f"refresh_{page_id}"),
                 InlineKeyboardButton("Раздача", url=url)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.edit_message_text(text=f'Дата: {edit_date}', reply_markup=reply_markup)
            logger.info(f"Кнопка страницы с ID {page_id} нажата, дата: {edit_date}")

    elif action == 'delete':
        page_id = int(data[1])
        delete_page(page_id)
        query.edit_message_text(text=f'Страница с ID {page_id} удалена')
        logger.info(f"Кнопка удаления для страницы с ID {page_id} нажата")

    elif action == 'refresh':
        page_id = int(data[1])
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
        keyboard = []
        pages = get_pages()
        if pages:
            keyboard = [[InlineKeyboardButton(page[1], callback_data=f"page_{page[0]}")] for page in pages]
        keyboard.append([InlineKeyboardButton("Добавить", callback_data="add_url_button")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text='Страницы для мониторинга:', reply_markup=reply_markup)
        logger.info("Возврат к списку страниц")

    elif action == 'add':
        if data[1] == 'url':
            if data[2] == 'button':
                # Отправляем новое сообщение для запроса URL
                context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text='Пришли мне ссылку для мониторинга:'
                )
                logger.info("Отправлен запрос на ссылку после нажатия кнопки")
                # Сохраняем в контексте информацию о запросе URL
                context.bot_data[f'waiting_url_{query.message.chat_id}'] = True

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

# Обработчик для текстовых сообщений
def handle_text(update: Update, context: CallbackContext) -> None:
    # Проверяем, ожидаем ли мы URL от этого пользователя
    chat_id = update.message.chat_id
    waiting_key = f'waiting_url_{chat_id}'
    
    if context.bot_data.get(waiting_key):
        url = update.message.text
        logger.debug(f"Получена ссылка: {url}")
        
        try:
            title = rutracker_api.get_page_title(url)
            logger.debug(f"Получен заголовок: {title}")
            
            add_page(title, url)
            logger.debug("Страница добавлена в базу данных")
            
            keyboard = [[InlineKeyboardButton("Главная", callback_data="back_to_list")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            update.message.reply_text(f'Ссылку поймал и добавил в мониторинг.', reply_markup=reply_markup)
            logger.debug("Отправлено подтверждение добавления")
            
            # Сбрасываем флаг ожидания
            context.bot_data[waiting_key] = False
            logger.debug(f"Сброшен флаг ожидания URL для чата {chat_id}")
            
            logger.info(f"Страница {title} добавлена для мониторинга через сообщение")
        except Exception as e:
            logger.error(f"Ошибка при обработке ссылки: {e}")
            update.message.reply_text(f'Произошла ошибка при обработке ссылки: {str(e)}')
            context.bot_data[waiting_key] = False

def main() -> None:
    # Инициализация базы данных
    init_db()

    # Создание объекта Updater и передача ему токена вашего бота
    updater = Updater(BOT_TOKEN)

    # Получение диспетчера для регистрации обработчиков
    dispatcher = updater.dispatcher

    # Регистрация обработчика /add с аргументами
    dispatcher.add_handler(CommandHandler("add", add_with_arg, pass_args=True))
    
    # Регистрация обработчика диалога добавления страницы
    add_conversation = ConversationHandler(
        entry_points=[CommandHandler("add", add_start, filters=Filters.command & ~Filters.regex(r'^/add\s+\S+'))],
        states={
            WAITING_URL: [MessageHandler(Filters.text & ~Filters.command, add_url)],
        },
        fallbacks=[CommandHandler("cancel", lambda update, context: ConversationHandler.END)],
    )
    dispatcher.add_handler(add_conversation)
    
    # Регистрация обработчиков команд
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("list", list_pages))
    dispatcher.add_handler(CommandHandler("update", update_page))
    
    # Обработчик для кнопок
    dispatcher.add_handler(CallbackQueryHandler(button))
    
    # Обработчик для текстовых сообщений
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))

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
















