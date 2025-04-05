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
RUTRACKER_USERNAME = os.getenv('RUTRACKER_USERNAME')
RUTRACKER_PASSWORD = os.getenv('RUTRACKER_PASSWORD')
FILE_DIR = os.getenv('FILE_DIR')
WHITELIST_PATH = os.getenv('WHITELIST_PATH', 'whitelist.txt')

# Настройка логирования
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# Путь к базе данных SQLite
db_path = 'database.db'

# Инициализация RutrackerAPI
rutracker_api = RutrackerAPI(RUTRACKER_USERNAME, RUTRACKER_PASSWORD)

# Загрузка белого списка пользователей
def load_whitelist():
    whitelist = set()
    if os.path.exists(WHITELIST_PATH):
        with open(WHITELIST_PATH, 'r') as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith('#'):
                    try:
                        user_id = int(line)
                        whitelist.add(user_id)
                    except ValueError:
                        logger.warning(f"Некорректный ID пользователя в файле whitelist: {line}")
    else:
        # Создаем пустой файл whitelist.txt
        with open(WHITELIST_PATH, 'w') as file:
            file.write("# Добавьте ID пользователей по одному на строку\n")
        logger.warning(f"Файл белого списка не найден, создан пустой файл: {WHITELIST_PATH}")
    
    logger.info(f"Загружен белый список: {len(whitelist)} пользователей")
    return whitelist

# Проверка доступа пользователя
def check_user_access(update: Update) -> bool:
    user_id = update.effective_user.id
    if user_id in WHITELIST:
        return True
    
    username = update.effective_user.username or "Не указано"
    first_name = update.effective_user.first_name or "Не указано"
    last_name = update.effective_user.last_name or "Не указано"
    
    logger.warning(
        f"Попытка доступа от неавторизованного пользователя: ID={user_id}, "
        f"Username={username}, Name={first_name} {last_name}"
    )
    
    update.message.reply_text(
        'Извините, у вас нет доступа к этому боту. '
        'Пожалуйста, свяжитесь с администратором.'
    )
    return False

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
    cursor.execute("PRAGMA table_info(pages)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'last_checked' not in columns:
        cursor.execute("ALTER TABLE pages ADD COLUMN last_checked TEXT")
    conn.commit()
    conn.close()
    logger.info("База данных инициализирована")

# Функция для проверки наличия URL в базе данных
def url_exists(url):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title FROM pages WHERE url = ?", (url,))
    result = cursor.fetchone()
    conn.close()
    return result

# Функция для поиска первого свободного ID в базе данных
def find_first_available_id():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM pages ORDER BY id")
    existing_ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    next_id = 1
    while next_id in existing_ids:
        next_id += 1
    return next_id

# Функция для добавления страницы в базу данных
def add_page(title, url):
    # Проверяем, существует ли уже такая ссылка
    existing_page = url_exists(url)
    if existing_page:
        page_id, existing_title = existing_page
        logger.info(f"Страница с URL {url} уже существует с ID {page_id} и заголовком '{existing_title}'")
        return None, existing_title, page_id
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    free_id = find_first_available_id()
    cursor.execute("INSERT INTO pages (id, title, url) VALUES (?, ?, ?)", 
                   (free_id, title, url))
    page_id = free_id
    conn.commit()
    conn.close()
    logger.info(f"Страница {title} добавлена для мониторинга с ID {page_id}")

    # Загрузка торрент-файла при добавлении новой страницы
    page_content = rutracker_api.get_page_content(url)
    new_date = rutracker_api.parse_date(page_content)
    if new_date:
        torrent_file_path = os.path.join(FILE_DIR, f'{page_id}.torrent')
        rutracker_api.download_torrent_by_url(url, torrent_file_path)
        update_page_date(page_id, new_date)
        logger.info(f"Торрент-файл для новой страницы {title} скачан в {torrent_file_path}")
    update_last_checked(page_id)
    
    return page_id, title, None

# Базовые функции для работы с БД
def get_pages():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, url, date, last_checked FROM pages")
    pages = cursor.fetchall()
    conn.close()
    return pages

def update_page_url(page_id, new_url):
    # Проверяем, существует ли уже такая ссылка
    existing_page = url_exists(new_url)
    if existing_page and existing_page[0] != page_id:
        return False, existing_page[0], existing_page[1]
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE pages SET url = ? WHERE id = ?", (new_url, page_id))
    conn.commit()
    conn.close()
    logger.info(f"Ссылка для страницы с ID {page_id} обновлена")
    return True, None, None

def update_page_date(page_id, new_date):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE pages SET date = ? WHERE id = ?", (new_date, page_id))
    conn.commit()
    conn.close()
    logger.info(f"Дата для страницы с ID {page_id} обновлена")

def update_last_checked(page_id):
    last_checked = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE pages SET last_checked = ? WHERE id = ?", (last_checked, page_id))
    conn.commit()
    conn.close()
    logger.info(f"Время последней проверки для страницы с ID {page_id} обновлено")

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

# Функция для отображения списка страниц
def display_pages_list(update_or_query):
    keyboard = []
    pages = get_pages()
    
    # Формируем заголовок с информацией о периодичности проверки
    if CHECK_INTERVAL == 1:
        interval_text = "каждую минуту"
    elif CHECK_INTERVAL < 5:
        interval_text = f"каждые {CHECK_INTERVAL} минуты"
    else:
        interval_text = f"каждые {CHECK_INTERVAL} минут"
    
    title_text = f'Страницы для мониторинга (проверка {interval_text}):'
    
    if pages:
        keyboard = [[InlineKeyboardButton(page[1], callback_data=f"page_{page[0]}")] for page in pages]
    keyboard.append([InlineKeyboardButton("Добавить", callback_data="add_url_button")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if isinstance(update_or_query, Update):
        update_or_query.message.reply_text(title_text, reply_markup=reply_markup)
    else:
        update_or_query.edit_message_text(text=title_text, reply_markup=reply_markup)
    
    logger.info("Список страниц отображен")

# Декоратор для проверки доступа
def restricted(func):
    def wrapped(update, context, *args, **kwargs):
        if not check_user_access(update):
            return
        return func(update, context, *args, **kwargs)
    return wrapped

# Обработчики команд
@restricted
def start(update: Update, context: CallbackContext) -> None:
    welcome_message = ('Привет! Я могу промониторить раздачи на рутрекере, чтобы ты ничего не пропустил! '
                      'Добавь в меня ссылку на сериал, я предупрежу тебя о новых сериях и скачаю его обновления на диск!')
    
    keyboard = [
        [InlineKeyboardButton("Список", callback_data="back_to_list"), 
         InlineKeyboardButton("Добавить", callback_data="add_url_button")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(welcome_message, reply_markup=reply_markup)
    logger.info("Команда /start выполнена")

@restricted
def add_with_arg(update: Update, context: CallbackContext) -> None:
    url = context.args[0]
    title = rutracker_api.get_page_title(url)
    
    page_id, title, existing_id = add_page(title, url)
    
    if page_id is None:
        # Страница уже существует
        update.message.reply_text(f'Эта ссылка уже добавлена в мониторинг под названием "{title}" (ID: {existing_id}).')
        logger.info(f"Попытка добавить дубликат URL: {url}")
    else:
        update.message.reply_text(f'Страница {title} добавлена для мониторинга.')
        logger.info(f"Команда /add выполнена для URL: {url}")

@restricted
def add_start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Пришли мне ссылку для мониторинга:')
    logger.info("Запрос ссылки отправлен")
    return WAITING_URL

@restricted
def add_url(update: Update, context: CallbackContext) -> int:
    url = update.message.text
    logger.debug(f"Получена ссылка: {url}")
    
    try:
        title = rutracker_api.get_page_title(url)
        logger.debug(f"Получен заголовок: {title}")
        
        page_id, title, existing_id = add_page(title, url)
        
        keyboard = [[InlineKeyboardButton("Назад к списку", callback_data="back_to_list")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if page_id is None:
            # Страница уже существует
            update.message.reply_text(
                f'Эта ссылка уже добавлена в мониторинг под названием "{title}" (ID: {existing_id}).',
                reply_markup=reply_markup
            )
            logger.info(f"Попытка добавить дубликат URL: {url}")
        else:
            update.message.reply_text(f'Ссылку поймал и добавил в мониторинг.', reply_markup=reply_markup)
            logger.debug("Отправлено подтверждение добавления")
            logger.info(f"Страница {title} добавлена для мониторинга через сообщение")
    except Exception as e:
        logger.error(f"Ошибка при обработке ссылки: {e}")
        update.message.reply_text(f'Произошла ошибка при обработке ссылки: {str(e)}')
    
    return ConversationHandler.END

@restricted
def cancel_add(update: Update, context: CallbackContext) -> int:
    chat_id = update.message.chat_id
    waiting_key = f'waiting_url_{chat_id}'
    if context.bot_data.get(waiting_key):
        context.bot_data[waiting_key] = False
        
    keyboard = [[InlineKeyboardButton("Назад к списку", callback_data="back_to_list")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Добавление ссылки отменено.', reply_markup=reply_markup)
    logger.info("Добавление ссылки отменено")
    return ConversationHandler.END

@restricted
def list_pages(update: Update, context: CallbackContext) -> None:
    pages = get_pages()
    if not pages:
        update.message.reply_text('Нет страниц для мониторинга.')
        logger.info("Команда /list выполнена: нет страниц для мониторинга")
        return

    display_pages_list(update)

@restricted
def update_page_cmd(update: Update, context: CallbackContext) -> None:
    if len(context.args) != 2:
        update.message.reply_text('Использование: /update <ID> <ссылка>')
        logger.warning("Неправильное использование команды /update")
        return

    page_id = int(context.args[0])
    new_url = context.args[1]
    
    success, existing_id, existing_title = update_page_url(page_id, new_url)
    
    if not success:
        update.message.reply_text(
            f'Эта ссылка уже добавлена в мониторинг под названием "{existing_title}" (ID: {existing_id}).'
        )
        logger.info(f"Попытка обновить на дублирующуюся ссылку: {new_url}")
    else:
        update.message.reply_text(f'Ссылка для страницы с ID {page_id} обновлена.')
        logger.info(f"Команда /update выполнена для страницы с ID {page_id}")

# Обработчик нажатий на кнопки
@restricted
def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    data = query.data
    logger.debug(f"Обработка callback данных: {data}")

    if data == "back_to_list":
        display_pages_list(query)
        logger.info("Возврат к списку страниц")
        return

    if data == "add_url_button":
        # Отправляем сообщение с запросом URL и кнопкой отмены
        keyboard = [[InlineKeyboardButton("Отмена", callback_data="cancel_add")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        context.bot.send_message(
            chat_id=query.message.chat_id,
            text='Пришли мне ссылку для мониторинга:',
            reply_markup=reply_markup
        )
        logger.info("Отправлен запрос на ссылку после нажатия кнопки")
        context.bot_data[f'waiting_url_{query.message.chat_id}'] = True
        return
        
    if data == "cancel_add":
        # Отмена добавления URL
        chat_id = query.message.chat_id
        waiting_key = f'waiting_url_{chat_id}'
        if context.bot_data.get(waiting_key):
            context.bot_data[waiting_key] = False
        
        # Возвращаемся к списку страниц
        display_pages_list(query)
        logger.info("Добавление ссылки отменено, возврат к списку страниц")
        return

    # Разбираем данные callback
    parts = data.split('_')
    if len(parts) < 2:
        logger.warning(f"Неверный формат данных callback: {data}")
        return
    
    action = parts[0]
    
    if action == 'page':
        page_id = int(parts[1])
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT url, date, last_checked FROM pages WHERE id = ?", (page_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            url, date, last_checked = row
            edit_date = rutracker_api.get_edit_date(url)
            keyboard = [
                [InlineKeyboardButton("Назад к списку", callback_data="back_to_list"),
                 InlineKeyboardButton("Delete", callback_data=f"delete_{page_id}"),
                 InlineKeyboardButton(f"Обновить сейчас ({last_checked})", callback_data=f"refresh_{page_id}"),
                 InlineKeyboardButton("Раздача", url=url)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.edit_message_text(text=f'Дата: {edit_date}', reply_markup=reply_markup)
            logger.info(f"Кнопка страницы с ID {page_id} нажата, дата: {edit_date}")

    elif action == 'delete':
        page_id = int(parts[1])
        delete_page(page_id)
        keyboard = [[InlineKeyboardButton("Назад к списку", callback_data="back_to_list")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text=f'Страница с ID {page_id} удалена', reply_markup=reply_markup)
        logger.info(f"Кнопка удаления для страницы с ID {page_id} нажата")

    elif action == 'refresh':
        page_id = int(parts[1])
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM pages WHERE id = ?", (page_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            url = row[0]
            edit_date = rutracker_api.get_edit_date(url)
            update_last_checked(page_id)
            keyboard = [[InlineKeyboardButton("Назад к списку", callback_data="back_to_list")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.edit_message_text(text=f'Дата: {edit_date}', reply_markup=reply_markup)
            logger.info(f"Кнопка обновления сейчас для страницы с ID {page_id} нажата, дата: {edit_date}")

# Обработчик для текстовых сообщений
@restricted
def handle_text(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    waiting_key = f'waiting_url_{chat_id}'
    
    if context.bot_data.get(waiting_key):
        url = update.message.text
        logger.debug(f"Получена ссылка: {url}")
        
        try:
            title = rutracker_api.get_page_title(url)
            logger.debug(f"Получен заголовок: {title}")
            
            page_id, title, existing_id = add_page(title, url)
            
            keyboard = [[InlineKeyboardButton("Назад к списку", callback_data="back_to_list")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if page_id is None:
                # Страница уже существует
                update.message.reply_text(
                    f'Эта ссылка уже добавлена в мониторинг под названием "{title}" (ID: {existing_id}).',
                    reply_markup=reply_markup
                )
                logger.info(f"Попытка добавить дубликат URL: {url}")
            else:
                update.message.reply_text(f'Ссылку поймал и добавил в мониторинг.', reply_markup=reply_markup)
                logger.debug("Отправлено подтверждение добавления")
                logger.info(f"Страница {title} добавлена для мониторинга через сообщение")
            
            context.bot_data[waiting_key] = False
            logger.debug(f"Сброшен флаг ожидания URL для чата {chat_id}")
            
        except Exception as e:
            logger.error(f"Ошибка при обработке ссылки: {e}")
            update.message.reply_text(f'Произошла ошибка при обработке ссылки: {str(e)}')
            context.bot_data[waiting_key] = False

def main() -> None:
    global WHITELIST
    WHITELIST = load_whitelist()
    
    init_db()
    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher

    # Регистрация обработчиков
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("add", add_with_arg, pass_args=True))
    
    add_conversation = ConversationHandler(
        entry_points=[CommandHandler("add", add_start, filters=Filters.command & ~Filters.regex(r'^/add\s+\S+'))],
        states={
            WAITING_URL: [MessageHandler(Filters.text & ~Filters.command, add_url)],
        },
        fallbacks=[CommandHandler("cancel", cancel_add)],
    )
    dispatcher.add_handler(add_conversation)
    
    dispatcher.add_handler(CommandHandler("list", list_pages))
    dispatcher.add_handler(CommandHandler("update", update_page_cmd))
    dispatcher.add_handler(CallbackQueryHandler(button))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))

    # Запуск планировщика задач
    schedule.every(CHECK_INTERVAL).minutes.do(check_pages)

    def run_schedule():
        while True:
            schedule.run_pending()
            time.sleep(1)

    schedule_thread = Thread(target=run_schedule)
    schedule_thread.start()

    # Запуск бота
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()


