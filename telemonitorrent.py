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
import sys

# Состояния для ConversationHandler
WAITING_URL = 1

# Загрузка переменных окружения из файла .env
load_dotenv()
CHECK_INTERVAL = int(os.environ['CHECK_INTERVAL'])
BOT_TOKEN = os.environ['BOT_TOKEN']
LOG_LEVEL = os.environ['LOG_LEVEL']
LOG_FORMAT = os.environ['LOG_FORMAT']
RUTRACKER_USERNAME = os.environ['RUTRACKER_USERNAME']
RUTRACKER_PASSWORD = os.environ['RUTRACKER_PASSWORD']
FILE_DIR = os.environ['FILE_DIR']
NOTIFICATIONS_ENABLED = os.environ.get('NOTIFICATIONS_ENABLED', 'True').lower() == 'true'

# Настройка логирования
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# Пути к базам данных SQLite
db_path = 'database.db'
users_db_path = 'users.db'

# Инициализация RutrackerAPI
rutracker_api = RutrackerAPI(RUTRACKER_USERNAME, RUTRACKER_PASSWORD)

# Функция для инициализации базы данных пользователей
def init_users_db():
    conn = sqlite3.connect(users_db_path)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY,
                        is_admin INTEGER DEFAULT 0,
                        sub INTEGER DEFAULT 1)''')
    conn.commit()
    conn.close()
    logger.info("База данных пользователей инициализирована")

# Функция для проверки наличия пользователя в базе данных
def user_exists(user_id):
    conn = sqlite3.connect(users_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, is_admin, sub FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result

# Функция для добавления пользователя в базу данных
def add_user(user_id, is_admin=0, sub=1):
    conn = sqlite3.connect(users_db_path)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (id, is_admin, sub) VALUES (?, ?, ?)", 
                   (user_id, is_admin, sub))
    conn.commit()
    conn.close()
    logger.info(f"Пользователь {user_id} добавлен в базу данных")

# Функция для обновления статуса администратора пользователя
def update_user_admin(user_id, is_admin):
    conn = sqlite3.connect(users_db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_admin = ? WHERE id = ?", (is_admin, user_id))
    conn.commit()
    conn.close()
    logger.info(f"Статус администратора пользователя {user_id} обновлен на {is_admin}")

# Функция для обновления статуса подписки пользователя
def update_user_sub(user_id, sub):
    conn = sqlite3.connect(users_db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET sub = ? WHERE id = ?", (sub, user_id))
    conn.commit()
    conn.close()
    logger.info(f"Статус подписки пользователя {user_id} обновлен на {sub}")

# Функция для получения всех пользователей
def get_users():
    conn = sqlite3.connect(users_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, is_admin, sub FROM users")
    users = cursor.fetchall()
    conn.close()
    return users

# Функция для удаления пользователя
def delete_user(user_id):
    conn = sqlite3.connect(users_db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    logger.info(f"Пользователь {user_id} удален из базы данных")

# Функция для проверки доступа пользователя
def check_user_access(update: Update) -> bool:
    user_id = update.effective_user.id
    user_data = user_exists(user_id)
    
    if user_data:
        return True
    
    # Если пользователя нет в базе
    username = update.effective_user.username or "Не указано"
    first_name = update.effective_user.first_name or "Не указано"
    last_name = update.effective_user.last_name or "Не указано"
    
    # Проверяем, пуста ли база (для первого администратора)
    if len(get_users()) == 0:
        add_user(user_id, is_admin=1)
        logger.info(
            f"Первый пользователь добавлен как администратор: ID={user_id}, "
            f"Username={username}, Name={first_name} {last_name}"
        )
        return True
    
    logger.warning(
        f"Попытка доступа неавторизованного пользователя: ID={user_id}, "
        f"Username={username}, Name={first_name} {last_name}"
    )
    
    # Сообщаем пользователю, что у него нет доступа
    update.message.reply_text(
        'Извините, у вас нет доступа к этому боту. '
        'Пожалуйста, свяжитесь с администратором, чтобы получить доступ.'
    )
    return False

# Функция для проверки прав администратора
def check_admin_access(update: Update) -> bool:
    user_id = update.effective_user.id
    user_data = user_exists(user_id)
    
    if user_data and user_data[1] == 1:  # is_admin = 1
        return True
    
    update.message.reply_text(
        'У вас нет прав администратора для выполнения этой команды.'
    )
    return False

# Функция для отправки уведомлений всем пользователям с подпиской
def send_notification_to_subscribers(bot, message, keyboard=None):
    if not NOTIFICATIONS_ENABLED:
        logger.info("Уведомления отключены в настройках")
        return

    reply_markup = None
    if keyboard:
        reply_markup = InlineKeyboardMarkup(keyboard)

    users = get_users()
    subscribers = [user[0] for user in users if user[2] == 1]  # id где sub = 1
    
    success_count = 0
    for user_id in subscribers:
        try:
            bot.send_message(
                chat_id=user_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            success_count += 1
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")
    
    logger.info(f"Отправлено уведомлений: {success_count} из {len(subscribers)}")

# Функция для инициализации базы данных страниц
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
    logger.info("База данных страниц инициализирована")

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

# Базовые функции для работы с БД страниц
def get_pages():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, url, date, last_checked FROM pages")
    pages = cursor.fetchall()
    conn.close()
    return pages

def get_page_by_id(page_id):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, url, date, last_checked FROM pages WHERE id = ?", (page_id,))
    page = cursor.fetchone()
    conn.close()
    return page

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
    logger.info("Начата проверка страниц на обновления")
    pages = get_pages()
    updates_found = False
    
    for page in pages:
        page_id, title, url, old_date, _ = page
        page_content = rutracker_api.get_page_content(url)
        new_date = rutracker_api.parse_date(page_content)
        
        if new_date and new_date != old_date:
            updates_found = True
            torrent_file_path = os.path.join(FILE_DIR, f'{page_id}.torrent')
            rutracker_api.download_torrent_by_url(url, torrent_file_path)
            update_page_date(page_id, new_date)
            logger.info(f"Дата для страницы {title} обновлена и торрент-файл скачан в {torrent_file_path}")
            
            # Отправляем уведомление о найденном обновлении
            notification_message = (
                f"<b>🆕 Найдено обновление!</b>\n\n"
                f"<b>Название:</b> {title}\n"
                f"<b>Новая дата:</b> {new_date}\n"
                f"<b>Предыдущая дата:</b> {old_date or 'Не задана'}\n"
                f"<b>ID:</b> {page_id}"
            )
            
            keyboard = [
                [InlineKeyboardButton("Открыть раздачу", url=url)],
                [InlineKeyboardButton("Посмотреть список", callback_data="back_to_list")]
            ]
            
            # Отправляем уведомление подписчикам
            send_notification_to_subscribers(BOT, notification_message, keyboard)
            
        update_last_checked(page_id)
    
    if not updates_found:
        logger.info("Обновлений не найдено")
    
    return updates_found

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
        keyboard = []
        for page in pages:
            page_id, title, url, date, last_checked = page
            # Если дата обновления есть, добавляем ее в текст кнопки
            button_text = title
            if date:
                # Сокращаем дату до более компактного формата
                short_date = date.split()[0] if " " in date else date
                button_text = f"{title} [{short_date}]"
            
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"page_{page_id}")])
    
    keyboard.append([InlineKeyboardButton("Добавить", callback_data="add_url_button")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if isinstance(update_or_query, Update):
        update_or_query.message.reply_text(title_text, reply_markup=reply_markup)
    else:
        update_or_query.edit_message_text(text=title_text, reply_markup=reply_markup)
    
    logger.info("Список страниц отображен")

# Декоратор для проверки базового доступа
def restricted(func):
    def wrapped(update, context, *args, **kwargs):
        if not check_user_access(update):
            return
        return func(update, context, *args, **kwargs)
    return wrapped

# Декоратор для проверки прав администратора
def admin_required(func):
    def wrapped(update, context, *args, **kwargs):
        if not check_user_access(update):
            return
        if not check_admin_access(update):
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
        keyboard = [
            [InlineKeyboardButton("Назад к списку", callback_data="back_to_list"),
             InlineKeyboardButton("Добавить еще", callback_data="add_url_button")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(f'Страница {title} добавлена для мониторинга.', reply_markup=reply_markup)
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
        
        keyboard = [
            [InlineKeyboardButton("Назад к списку", callback_data="back_to_list"),
             InlineKeyboardButton("Добавить еще", callback_data="add_url_button")]
        ]
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
        keyboard = [[InlineKeyboardButton("Добавить", callback_data="add_url_button")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text('Нет страниц для мониторинга.', reply_markup=reply_markup)
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
        keyboard = [
            [InlineKeyboardButton("Назад к списку", callback_data="back_to_list")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(f'Ссылка для страницы с ID {page_id} обновлена.', reply_markup=reply_markup)
        logger.info(f"Команда /update выполнена для страницы с ID {page_id}")

# Команда для запуска проверки вручную
@restricted
def check_now(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Запускаю проверку страниц на обновления...')
    
    # Выполняем проверку
    updates_found = check_pages()
    
    keyboard = [[InlineKeyboardButton("Назад к списку", callback_data="back_to_list")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if updates_found:
        update.message.reply_text('Проверка завершена. Найдены обновления!', reply_markup=reply_markup)
    else:
        update.message.reply_text('Проверка завершена. Обновлений не найдено.', reply_markup=reply_markup)
    
    logger.info("Запущена ручная проверка страниц")

# Команда для управления подпиской
@restricted
def toggle_subscription(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    user_data = user_exists(user_id)
    
    if not user_data:
        add_user(user_id)
        update.message.reply_text('Вы подписаны на уведомления об обновлениях.')
        logger.info(f"Пользователь {user_id} подписался на уведомления")
        return
    
    # Меняем статус подписки на противоположный
    current_sub = user_data[2]
    new_sub = 0 if current_sub == 1 else 1
    
    update_user_sub(user_id, new_sub)
    
    if new_sub == 1:
        update.message.reply_text('Вы подписаны на уведомления об обновлениях.')
        logger.info(f"Пользователь {user_id} подписался на уведомления")
    else:
        update.message.reply_text('Вы отписались от уведомлений об обновлениях.')
        logger.info(f"Пользователь {user_id} отписался от уведомлений")

# Команда для отображения статуса подписки
@restricted
def subscription_status(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    user_data = user_exists(user_id)
    
    if not user_data:
        add_user(user_id)
        update.message.reply_text('Вы подписаны на уведомления об обновлениях.')
        return
    
    is_admin = user_data[1]
    is_subscribed = user_data[2]
    
    status_text = f'Ваш ID: {user_id}\n'
    status_text += f'Статус администратора: {"Да" if is_admin else "Нет"}\n'
    status_text += f'Подписка на уведомления: {"Включена" if is_subscribed else "Отключена"}'
    
    update.message.reply_text(status_text)

# Команда для администратора - список пользователей
@admin_required
def list_users(update: Update, context: CallbackContext) -> None:
    users = get_users()
    
    if not users:
        update.message.reply_text('Нет зарегистрированных пользователей.')
        return
    
    users_text = 'Список пользователей:\n\n'
    for user in users:
        user_id, is_admin, is_subscribed = user
        # Попытка получить информацию о пользователе через API
        try:
            user_info = context.bot.get_chat(user_id)
            username = user_info.username or "Нет"
            name = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip() or "Нет"
            user_details = f"@{username}, Имя: {name}"
        except Exception:
            user_details = "Информация недоступна"
        
        users_text += (f'ID: {user_id}, {user_details}\n'
                      f'Админ: {"Да" if is_admin else "Нет"}, '
                      f'Подписка: {"Да" if is_subscribed else "Нет"}\n\n')
    
    update.message.reply_text(users_text)

# Команда для администратора - назначение админа
@admin_required
def make_admin(update: Update, context: CallbackContext) -> None:
    if len(context.args) != 1:
        update.message.reply_text('Использование: /makeadmin <ID>')
        return
    
    try:
        target_id = int(context.args[0])
        
        user_data = user_exists(target_id)
        if not user_data:
            update.message.reply_text(f'Пользователь с ID {target_id} не найден.')
            return
        
        update_user_admin(target_id, 1)
        update.message.reply_text(f'Пользователю с ID {target_id} предоставлены права администратора.')
        logger.info(f"Пользователю {target_id} предоставлены права администратора")
    except ValueError:
        update.message.reply_text('ID пользователя должен быть числом.')

# Команда для администратора - удаление админа
@admin_required
def remove_admin(update: Update, context: CallbackContext) -> None:
    if len(context.args) != 1:
        update.message.reply_text('Использование: /removeadmin <ID>')
        return
    
    try:
        target_id = int(context.args[0])
        
        # Проверка, не пытается ли админ удалить сам себя
        if target_id == update.effective_user.id:
            update.message.reply_text('Нельзя удалить права администратора у самого себя.')
            return
        
        user_data = user_exists(target_id)
        if not user_data:
            update.message.reply_text(f'Пользователь с ID {target_id} не найден.')
            return
        
        update_user_admin(target_id, 0)
        update.message.reply_text(f'У пользователя с ID {target_id} удалены права администратора.')
        logger.info(f"У пользователя {target_id} удалены права администратора")
    except ValueError:
        update.message.reply_text('ID пользователя должен быть числом.')

# Команда для администратора - добавление пользователя
@admin_required
def add_user_cmd(update: Update, context: CallbackContext) -> None:
    if len(context.args) < 1:
        update.message.reply_text('Использование: /adduser <ID> [is_admin=0] [sub=1]')
        return
    
    try:
        target_id = int(context.args[0])
        is_admin = int(context.args[1]) if len(context.args) > 1 else 0
        sub = int(context.args[2]) if len(context.args) > 2 else 1
        
        # Проверка корректности значений
        if is_admin not in [0, 1]:
            update.message.reply_text('Значение is_admin должно быть 0 или 1')
            return
        
        if sub not in [0, 1]:
            update.message.reply_text('Значение sub должно быть 0 или 1')
            return
        
        # Проверяем, существует ли уже пользователь
        user_data = user_exists(target_id)
        if user_data:
            update.message.reply_text(
                f'Пользователь с ID {target_id} уже существует. '
                f'Права администратора: {"Да" if user_data[1] else "Нет"}, '
                f'Подписка: {"Да" if user_data[2] else "Нет"}'
            )
            return
        
        add_user(target_id, is_admin, sub)
        update.message.reply_text(
            f'Пользователь с ID {target_id} добавлен. '
            f'Права администратора: {"Да" if is_admin else "Нет"}, '
            f'Подписка: {"Да" if sub else "Нет"}'
        )
        logger.info(f"Пользователь {target_id} добавлен с правами: admin={is_admin}, sub={sub}")
    except ValueError:
        update.message.reply_text('ID пользователя должен быть числом.')

# Команда для администратора - удаление пользователя
@admin_required
def delete_user_cmd(update: Update, context: CallbackContext) -> None:
    if len(context.args) != 1:
        update.message.reply_text('Использование: /userdel <ID>')
        return
    
    try:
        target_id = int(context.args[0])
        
        # Проверка, не пытается ли админ удалить сам себя
        if target_id == update.effective_user.id:
            update.message.reply_text('Нельзя удалить самого себя.')
            return
        
        user_data = user_exists(target_id)
        if not user_data:
            update.message.reply_text(f'Пользователь с ID {target_id} не найден.')
            return
        
        delete_user(target_id)
        update.message.reply_text(f'Пользователь с ID {target_id} удален.')
        logger.info(f"Пользователь {target_id} удален из базы данных")
    except ValueError:
        update.message.reply_text('ID пользователя должен быть числом.')

@admin_required
def admin_help_cmd(update: Update, context: CallbackContext) -> None:
    """Показывает список всех доступных команд для администратора"""
    help_text = "<b>Список доступных команд:</b>\n\n"
    
    # Команды для всех пользователей
    help_text += "<b>Общие команды:</b>\n"
    help_text += "/start - Начало работы с ботом\n"
    help_text += "/list - Показать список отслеживаемых страниц\n"
    help_text += "/add [ссылка] - Добавить страницу для мониторинга\n"
    help_text += "/update [ID] [ссылка] - Обновить ссылку для страницы\n"
    help_text += "/check - Запустить проверку обновлений вручную\n"
    help_text += "/subscribe - Включить/выключить уведомления\n"
    help_text += "/status - Показать ваш статус и настройки\n\n"
    
    # Команды для администраторов
    help_text += "<b>Команды администратора:</b>\n"
    help_text += "/users - Показать список всех пользователей\n"
    help_text += "/adduser [ID] [is_admin=0] [sub=1] - Добавить пользователя\n"
    help_text += "/userdel [ID] - Удалить пользователя\n"
    help_text += "/makeadmin [ID] - Сделать пользователя администратором\n"
    help_text += "/removeadmin [ID] - Убрать права администратора\n"
    help_text += "/help - Показать этот список команд\n\n"
    
    help_text += "<b>Параметры:</b>\n"
    help_text += "ID - идентификатор пользователя или страницы\n"
    help_text += "is_admin - права администратора (0 или 1)\n"
    help_text += "sub - подписка на уведомления (0 или 1)"
    
    keyboard = [[InlineKeyboardButton("Назад к списку", callback_data="back_to_list")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode='HTML')
    logger.info("Отображен список команд администратора")

# Версия справки для обычных пользователей
@restricted
def user_help_cmd(update: Update, context: CallbackContext) -> None:
    """Показывает список доступных команд для обычного пользователя"""
    
    # Проверяем, является ли пользователь администратором
    user_id = update.effective_user.id
    user_data = user_exists(user_id)
    
    if user_data and user_data[1] == 1:  # is_admin = 1
        # Перенаправляем на админскую справку
        return admin_help_cmd(update, context)
    
    help_text = "<b>Список доступных команд:</b>\n\n"
    
    # Команды для всех пользователей
    help_text += "/start - Начало работы с ботом\n"
    help_text += "/list - Показать список отслеживаемых страниц\n"
    help_text += "/add [ссылка] - Добавить страницу для мониторинга\n"
    help_text += "/update [ID] [ссылка] - Обновить ссылку для страницы\n"
    help_text += "/check - Запустить проверку обновлений вручную\n"
    help_text += "/subscribe - Включить/выключить уведомления\n"
    help_text += "/status - Показать ваш статус и настройки\n"
    help_text += "/help - Показать этот список команд"
    
    keyboard = [[InlineKeyboardButton("Назад к списку", callback_data="back_to_list")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode='HTML')
    logger.info("Отображен список команд пользователя")

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
            
            keyboard = [
                [InlineKeyboardButton("Назад к списку", callback_data="back_to_list"),
                 InlineKeyboardButton("Добавить еще", callback_data="add_url_button")]
            ]
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

def check_required_env_vars():
    required_vars = ['CHECK_INTERVAL', 'BOT_TOKEN', 'LOG_LEVEL', 'LOG_FORMAT', 
                    'RUTRACKER_USERNAME', 'RUTRACKER_PASSWORD', 'FILE_DIR']
    missing_vars = [var for var in required_vars if var not in os.environ]
    
    if missing_vars:
        print("ОШИБКА: Отсутствуют обязательные переменные окружения:")
        for var in missing_vars:
            print(f" - {var}")
        print("\nДобавьте их в файл .env или установите в окружении.")
        sys.exit(1)

def main() -> None:
    check_required_env_vars()
    
    global BOT
    
    # Инициализация баз данных
    init_db()
    init_users_db()
    
    updater = Updater(BOT_TOKEN)
    BOT = updater.bot
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
    dispatcher.add_handler(CommandHandler("check", check_now))
    dispatcher.add_handler(CommandHandler("help", user_help_cmd))
    
    # Команды для управления подписками
    dispatcher.add_handler(CommandHandler("subscribe", toggle_subscription))
    dispatcher.add_handler(CommandHandler("status", subscription_status))
    
    # Административные команды
    dispatcher.add_handler(CommandHandler("users", list_users))
    dispatcher.add_handler(CommandHandler("makeadmin", make_admin))
    dispatcher.add_handler(CommandHandler("removeadmin", remove_admin))
    dispatcher.add_handler(CommandHandler("adduser", add_user_cmd))
    dispatcher.add_handler(CommandHandler("userdel", delete_user_cmd))
    
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
