import sqlite3
from datetime import datetime
import os
from config import DB_PATH, USERS_DB_PATH, logger, FILE_DIR

# Функции для работы с базой данных пользователей
def init_users_db():
    logger.debug("Начало инициализации базы данных пользователей")
    conn = sqlite3.connect(USERS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY,
                        is_admin INTEGER DEFAULT 0,
                        sub INTEGER DEFAULT 1)''')
    conn.commit()
    conn.close()
    logger.info("База данных пользователей инициализирована")

def user_exists(user_id):
    logger.debug(f"Проверка существования пользователя с ID {user_id}")
    conn = sqlite3.connect(USERS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, is_admin, sub FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        logger.debug(f"Пользователь с ID {user_id} найден в базе")
    else:
        logger.debug(f"Пользователь с ID {user_id} не найден в базе")
    
    return result

def add_user(user_id, is_admin=0, sub=1):
    logger.debug(f"Добавление пользователя с ID {user_id}, is_admin={is_admin}, sub={sub}")
    conn = sqlite3.connect(USERS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (id, is_admin, sub) VALUES (?, ?, ?)", 
                   (user_id, is_admin, sub))
    conn.commit()
    conn.close()
    logger.info(f"Пользователь {user_id} добавлен в базу данных")

def update_user_admin(user_id, is_admin):
    logger.debug(f"Обновление статуса администратора для пользователя с ID {user_id} на {is_admin}")
    conn = sqlite3.connect(USERS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_admin = ? WHERE id = ?", (is_admin, user_id))
    affected_rows = cursor.rowcount
    conn.commit()
    conn.close()
    
    if affected_rows > 0:
        logger.info(f"Статус администратора пользователя {user_id} обновлен на {is_admin}")
    else:
        logger.warning(f"Не удалось обновить статус администратора для пользователя {user_id}")

def update_user_sub(user_id, sub):
    logger.debug(f"Обновление статуса подписки для пользователя с ID {user_id} на {sub}")
    conn = sqlite3.connect(USERS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET sub = ? WHERE id = ?", (sub, user_id))
    affected_rows = cursor.rowcount
    conn.commit()
    conn.close()
    
    if affected_rows > 0:
        logger.info(f"Статус подписки пользователя {user_id} обновлен на {sub}")
    else:
        logger.warning(f"Не удалось обновить статус подписки для пользователя {user_id}")

def get_users():
    logger.debug("Получение списка всех пользователей")
    conn = sqlite3.connect(USERS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, is_admin, sub FROM users")
    users = cursor.fetchall()
    conn.close()
    
    logger.debug(f"Получено {len(users)} пользователей из базы данных")
    return users

def delete_user(user_id):
    logger.debug(f"Удаление пользователя с ID {user_id}")
    conn = sqlite3.connect(USERS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    affected_rows = cursor.rowcount
    conn.commit()
    conn.close()
    
    if affected_rows > 0:
        logger.info(f"Пользователь {user_id} удален из базы данных")
    else:
        logger.warning(f"Не удалось удалить пользователя {user_id} (возможно, не существует)")

# Функции для работы с базой данных страниц
def init_db():
    logger.debug("Начало инициализации базы данных страниц")
    conn = sqlite3.connect(DB_PATH)
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
        logger.debug("Добавление столбца 'last_checked' в таблицу pages")
        cursor.execute("ALTER TABLE pages ADD COLUMN last_checked TEXT")
    conn.commit()
    conn.close()
    logger.info("База данных страниц инициализирована")

def url_exists(url):
    logger.debug(f"Проверка существования URL: {url}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title FROM pages WHERE url = ?", (url,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        logger.debug(f"URL {url} найден в базе с ID {result[0]}")
    else:
        logger.debug(f"URL {url} не найден в базе")
    
    return result

def find_first_available_id():
    logger.debug("Поиск первого доступного ID для новой страницы")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM pages ORDER BY id")
    existing_ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    next_id = 1
    while next_id in existing_ids:
        next_id += 1
    
    logger.debug(f"Найден свободный ID: {next_id}")
    return next_id

def add_page(title, url, rutracker_api):
    logger.debug(f"Добавление страницы '{title}' с URL: {url}")
    # Проверяем, существует ли уже такая ссылка
    existing_page = url_exists(url)
    if existing_page:
        page_id, existing_title = existing_page
        logger.info(f"Страница с URL {url} уже существует с ID {page_id} и заголовком '{existing_title}'")
        return None, existing_title, page_id
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    free_id = find_first_available_id()
    cursor.execute("INSERT INTO pages (id, title, url) VALUES (?, ?, ?)", 
                   (free_id, title, url))
    page_id = free_id
    conn.commit()
    conn.close()
    logger.info(f"Страница '{title}' добавлена для мониторинга с ID {page_id}")

    # Загрузка торрент-файла при добавлении новой страницы
    logger.debug(f"Получение содержимого страницы для {url}")
    page_content = rutracker_api.get_page_content(url)
    new_date = rutracker_api.parse_date(page_content)
    if new_date:
        logger.debug(f"Обнаружена дата: {new_date}, скачивание торрент-файла")
        torrent_file_path = os.path.join(FILE_DIR, f'{page_id}.torrent')
        rutracker_api.download_torrent_by_url(url, torrent_file_path)
        update_page_date(page_id, new_date)
        logger.info(f"Торрент-файл для новой страницы '{title}' скачан в {torrent_file_path}")
    else:
        logger.warning(f"Не удалось определить дату для страницы с URL {url}")
    
    update_last_checked(page_id)
    
    return page_id, title, None

def get_pages():
    logger.debug("Получение списка всех страниц")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, url, date, last_checked FROM pages")
    pages = cursor.fetchall()
    conn.close()
    
    logger.debug(f"Получено {len(pages)} страниц из базы данных")
    return pages

def get_page_by_id(page_id):
    logger.debug(f"Получение страницы с ID {page_id}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, url, date, last_checked FROM pages WHERE id = ?", (page_id,))
    page = cursor.fetchone()
    conn.close()
    
    if page:
        logger.debug(f"Страница с ID {page_id} найдена: {page[1]}")
    else:
        logger.warning(f"Страница с ID {page_id} не найдена")
    
    return page

def update_page_url(page_id, new_url):
    logger.debug(f"Обновление URL для страницы с ID {page_id} на {new_url}")
    # Проверяем, существует ли уже такая ссылка
    existing_page = url_exists(new_url)
    if existing_page and existing_page[0] != page_id:
        logger.warning(f"URL {new_url} уже используется для страницы с ID {existing_page[0]}")
        return False, existing_page[0], existing_page[1]
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE pages SET url = ? WHERE id = ?", (new_url, page_id))
    affected_rows = cursor.rowcount
    conn.commit()
    conn.close()
    
    if affected_rows > 0:
        logger.info(f"Ссылка для страницы с ID {page_id} обновлена на {new_url}")
    else:
        logger.warning(f"Не удалось обновить ссылку для страницы с ID {page_id}")
    
    return True, None, None

def update_page_date(page_id, new_date):
    logger.debug(f"Обновление даты для страницы с ID {page_id} на {new_date}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE pages SET date = ? WHERE id = ?", (new_date, page_id))
    affected_rows = cursor.rowcount
    conn.commit()
    conn.close()
    
    if affected_rows > 0:
        logger.info(f"Дата для страницы с ID {page_id} обновлена на {new_date}")
    else:
        logger.warning(f"Не удалось обновить дату для страницы с ID {page_id}")

def update_last_checked(page_id):
    last_checked = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    logger.debug(f"Обновление времени последней проверки для страницы с ID {page_id} на {last_checked}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE pages SET last_checked = ? WHERE id = ?", (last_checked, page_id))
    affected_rows = cursor.rowcount
    conn.commit()
    conn.close()
    
    if affected_rows > 0:
        logger.info(f"Время последней проверки для страницы с ID {page_id} обновлено на {last_checked}")
    else:
        logger.warning(f"Не удалось обновить время последней проверки для страницы с ID {page_id}")

def delete_page(page_id):
    logger.debug(f"Удаление страницы с ID {page_id}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Получаем информацию о странице перед удалением для логирования
    cursor.execute("SELECT title, url FROM pages WHERE id = ?", (page_id,))
    page_info = cursor.fetchone()
    
    cursor.execute("DELETE FROM pages WHERE id = ?", (page_id,))
    affected_rows = cursor.rowcount
    conn.commit()
    conn.close()
    
    if affected_rows > 0:
        if page_info:
            title, url = page_info
            logger.info(f"Страница с ID {page_id} ('{title}', {url}) удалена")
        else:
            logger.info(f"Страница с ID {page_id} удалена")
    else:
        logger.warning(f"Не удалось удалить страницу с ID {page_id} (возможно, не существует)")
    
    # Удаляем торрент-файл, если он существует
    torrent_file_path = os.path.join(FILE_DIR, f'{page_id}.torrent')
    if os.path.exists(torrent_file_path):
        try:
            os.remove(torrent_file_path)
            logger.debug(f"Торрент-файл {torrent_file_path} удален")
        except Exception as e:
            logger.error(f"Ошибка при удалении торрент-файла {torrent_file_path}: {e}")
