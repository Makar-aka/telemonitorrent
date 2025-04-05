import sqlite3
from datetime import datetime
import os
from config import DB_PATH, USERS_DB_PATH, logger, FILE_DIR

# Функции для работы с базой данных пользователей
def init_users_db():
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
    conn = sqlite3.connect(USERS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, is_admin, sub FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def add_user(user_id, is_admin=0, sub=1):
    conn = sqlite3.connect(USERS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (id, is_admin, sub) VALUES (?, ?, ?)", 
                   (user_id, is_admin, sub))
    conn.commit()
    conn.close()
    logger.info(f"Пользователь {user_id} добавлен в базу данных")

def update_user_admin(user_id, is_admin):
    conn = sqlite3.connect(USERS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_admin = ? WHERE id = ?", (is_admin, user_id))
    conn.commit()
    conn.close()
    logger.info(f"Статус администратора пользователя {user_id} обновлен на {is_admin}")

def update_user_sub(user_id, sub):
    conn = sqlite3.connect(USERS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET sub = ? WHERE id = ?", (sub, user_id))
    conn.commit()
    conn.close()
    logger.info(f"Статус подписки пользователя {user_id} обновлен на {sub}")

def get_users():
    conn = sqlite3.connect(USERS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, is_admin, sub FROM users")
    users = cursor.fetchall()
    conn.close()
    return users

def delete_user(user_id):
    conn = sqlite3.connect(USERS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    logger.info(f"Пользователь {user_id} удален из базы данных")

# Функции для работы с базой данных страниц
def init_db():
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
        cursor.execute("ALTER TABLE pages ADD COLUMN last_checked TEXT")
    conn.commit()
    conn.close()
    logger.info("База данных страниц инициализирована")

def url_exists(url):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title FROM pages WHERE url = ?", (url,))
    result = cursor.fetchone()
    conn.close()
    return result

def find_first_available_id():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM pages ORDER BY id")
    existing_ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    next_id = 1
    while next_id in existing_ids:
        next_id += 1
    return next_id

def add_page(title, url, rutracker_api):
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

def get_pages():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, url, date, last_checked FROM pages")
    pages = cursor.fetchall()
    conn.close()
    return pages

def get_page_by_id(page_id):
    conn = sqlite3.connect(DB_PATH)
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
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE pages SET url = ? WHERE id = ?", (new_url, page_id))
    conn.commit()
    conn.close()
    logger.info(f"Ссылка для страницы с ID {page_id} обновлена")
    return True, None, None

def update_page_date(page_id, new_date):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE pages SET date = ? WHERE id = ?", (new_date, page_id))
    conn.commit()
    conn.close()
    logger.info(f"Дата для страницы с ID {page_id} обновлена")

def update_last_checked(page_id):
    last_checked = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE pages SET last_checked = ? WHERE id = ?", (last_checked, page_id))
    conn.commit()
    conn.close()
    logger.info(f"Время последней проверки для страницы с ID {page_id} обновлено")

def delete_page(page_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pages WHERE id = ?", (page_id,))
    conn.commit()
    conn.close()
    logger.info(f"Страница с ID {page_id} удалена")
