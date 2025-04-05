import sqlite3
from datetime import datetime
import os
from contextlib import contextmanager
from config import DB_PATH, USERS_DB_PATH, logger, FILE_DIR

# Контекстный менеджер для работы с базой данных
@contextmanager
def get_db_connection(db_path):
    """Создает и возвращает соединение с базой данных."""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Позволяет обращаться к столбцам по имени
        yield conn
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Ошибка базы данных: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

# Функции для работы с базой данных пользователей
def init_users_db():
    """Инициализирует базу данных пользователей."""
    logger.debug("Начало инициализации базы данных пользователей")
    try:
        with get_db_connection(USERS_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY,
                            is_admin INTEGER DEFAULT 0,
                            sub INTEGER DEFAULT 1)''')
        logger.info("База данных пользователей инициализирована")
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных пользователей: {e}")
        raise

def user_exists(user_id):
    """Проверяет существование пользователя в базе данных."""
    logger.debug(f"Проверка существования пользователя с ID {user_id}")
    try:
        with get_db_connection(USERS_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, is_admin, sub FROM users WHERE id = ?", (user_id,))
            result = cursor.fetchone()
        
        if result:
            logger.debug(f"Пользователь с ID {user_id} найден в базе")
            return tuple(result)  # Преобразуем Row в tuple для обратной совместимости
        else:
            logger.debug(f"Пользователь с ID {user_id} не найден в базе")
            return None
    except Exception as e:
        logger.error(f"Ошибка при проверке пользователя {user_id}: {e}")
        return None

def add_user(user_id, is_admin=0, sub=1):
    """Добавляет пользователя в базу данных."""
    logger.debug(f"Добавление пользователя с ID {user_id}, is_admin={is_admin}, sub={sub}")
    try:
        with get_db_connection(USERS_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO users (id, is_admin, sub) VALUES (?, ?, ?)", 
                        (user_id, is_admin, sub))
        logger.info(f"Пользователь {user_id} добавлен в базу данных")
    except Exception as e:
        logger.error(f"Ошибка при добавлении пользователя {user_id}: {e}")
        raise

def update_user_admin(user_id, is_admin):
    """Обновляет статус администратора пользователя."""
    logger.debug(f"Обновление статуса администратора для пользователя с ID {user_id} на {is_admin}")
    try:
        with get_db_connection(USERS_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_admin = ? WHERE id = ?", (is_admin, user_id))
            affected_rows = cursor.rowcount
        
        if affected_rows > 0:
            logger.info(f"Статус администратора пользователя {user_id} обновлен на {is_admin}")
        else:
            logger.warning(f"Не удалось обновить статус администратора для пользователя {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при обновлении статуса администратора для пользователя {user_id}: {e}")
        raise

def update_user_sub(user_id, sub):
    """Обновляет статус подписки пользователя."""
    logger.debug(f"Обновление статуса подписки для пользователя с ID {user_id} на {sub}")
    try:
        with get_db_connection(USERS_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET sub = ? WHERE id = ?", (sub, user_id))
            affected_rows = cursor.rowcount
        
        if affected_rows > 0:
            logger.info(f"Статус подписки пользователя {user_id} обновлен на {sub}")
        else:
            logger.warning(f"Не удалось обновить статус подписки для пользователя {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при обновлении статуса подписки для пользователя {user_id}: {e}")
        raise

def get_users():
    """Возвращает список всех пользователей."""
    logger.debug("Получение списка всех пользователей")
    try:
        with get_db_connection(USERS_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, is_admin, sub FROM users")
            users = [tuple(row) for row in cursor.fetchall()]  # Преобразуем Row в tuple для обратной совместимости
        
        logger.debug(f"Получено {len(users)} пользователей из базы данных")
        return users
    except Exception as e:
        logger.error(f"Ошибка при получении списка пользователей: {e}")
        return []

def delete_user(user_id):
    """Удаляет пользователя из базы данных."""
    logger.debug(f"Удаление пользователя с ID {user_id}")
    try:
        with get_db_connection(USERS_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            affected_rows = cursor.rowcount
        
        if affected_rows > 0:
            logger.info(f"Пользователь {user_id} удален из базы данных")
        else:
            logger.warning(f"Не удалось удалить пользователя {user_id} (возможно, не существует)")
    except Exception as e:
        logger.error(f"Ошибка при удалении пользователя {user_id}: {e}")
        raise

# Функции для работы с базой данных страниц
def init_db():
    """Инициализирует базу данных страниц."""
    logger.debug("Начало инициализации базы данных страниц")
    try:
        with get_db_connection(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS pages (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            title TEXT,
                            url TEXT,
                            date TEXT,
                            last_checked TEXT)''')
            
            # Проверка наличия столбца last_checked
            cursor.execute("PRAGMA table_info(pages)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'last_checked' not in columns:
                logger.debug("Добавление столбца 'last_checked' в таблицу pages")
                cursor.execute("ALTER TABLE pages ADD COLUMN last_checked TEXT")
        
        logger.info("База данных страниц инициализирована")
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных страниц: {e}")
        raise

def url_exists(url):
    """Проверяет существование URL в базе данных."""
    logger.debug(f"Проверка существования URL: {url}")
    try:
        with get_db_connection(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title FROM pages WHERE url = ?", (url,))
            result = cursor.fetchone()
        
        if result:
            logger.debug(f"URL {url} найден в базе с ID {result[0]}")
            return tuple(result)
        else:
            logger.debug(f"URL {url} не найден в базе")
            return None
    except Exception as e:
        logger.error(f"Ошибка при проверке URL {url}: {e}")
        return None

def find_first_available_id():
    """Находит первый свободный ID для новой страницы."""
    logger.debug("Поиск первого доступного ID для новой страницы")
    try:
        with get_db_connection(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM pages ORDER BY id")
            existing_ids = [row[0] for row in cursor.fetchall()]
        
        next_id = 1
        while next_id in existing_ids:
            next_id += 1
        
        logger.debug(f"Найден свободный ID: {next_id}")
        return next_id
    except Exception as e:
        logger.error(f"Ошибка при поиске доступного ID: {e}")
        return 1  # В случае ошибки возвращаем 1 и надеемся на лучшее

def add_page(title, url, rutracker_api):
    """Добавляет страницу в базу данных."""
    logger.debug(f"Добавление страницы '{title}' с URL: {url}")
    try:
        # Проверяем, существует ли уже такая ссылка
        existing_page = url_exists(url)
        if existing_page:
            page_id, existing_title = existing_page
            logger.info(f"Страница с URL {url} уже существует с ID {page_id} и заголовком '{existing_title}'")
            return None, existing_title, page_id
        
        with get_db_connection(DB_PATH) as conn:
            cursor = conn.cursor()
            free_id = find_first_available_id()
            cursor.execute("INSERT INTO pages (id, title, url) VALUES (?, ?, ?)", 
                        (free_id, title, url))
            page_id = free_id
        
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
    except Exception as e:
        logger.error(f"Ошибка при добавлении страницы '{title}': {e}")
        raise

def get_pages():
    """Возвращает список всех страниц."""
    logger.debug("Получение списка всех страниц")
    try:
        with get_db_connection(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, url, date, last_checked FROM pages")
            pages = [tuple(row) for row in cursor.fetchall()]
        
        logger.debug(f"Получено {len(pages)} страниц из базы данных")
        return pages
    except Exception as e:
        logger.error(f"Ошибка при получении списка страниц: {e}")
        return []

def get_page_by_id(page_id):
    """Возвращает страницу по ее ID."""
    logger.debug(f"Получение страницы с ID {page_id}")
    try:
        with get_db_connection(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, url, date, last_checked FROM pages WHERE id = ?", (page_id,))
            page = cursor.fetchone()
        
        if page:
            logger.debug(f"Страница с ID {page_id} найдена: {page['title']}")
            return tuple(page)
        else:
            logger.warning(f"Страница с ID {page_id} не найдена")
            return None
    except Exception as e:
        logger.error(f"Ошибка при получении страницы с ID {page_id}: {e}")
        return None

def update_page_url(page_id, new_url):
    """Обновляет URL страницы."""
    logger.debug(f"Обновление URL для страницы с ID {page_id} на {new_url}")
    try:
        # Проверяем, существует ли уже такая ссылка
        existing_page = url_exists(new_url)
        if existing_page and existing_page[0] != page_id:
            logger.warning(f"URL {new_url} уже используется для страницы с ID {existing_page[0]}")
            return False, existing_page[0], existing_page[1]
        
        with get_db_connection(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE pages SET url = ? WHERE id = ?", (new_url, page_id))
            affected_rows = cursor.rowcount
        
        if affected_rows > 0:
            logger.info(f"Ссылка для страницы с ID {page_id} обновлена на {new_url}")
            return True, None, None
        else:
            logger.warning(f"Не удалось обновить ссылку для страницы с ID {page_id}")
            return False, None, None
    except Exception as e:
        logger.error(f"Ошибка при обновлении URL для страницы с ID {page_id}: {e}")
        raise

def update_page_date(page_id, new_date):
    """Обновляет дату страницы."""
    logger.debug(f"Обновление даты для страницы с ID {page_id} на {new_date}")
    try:
        with get_db_connection(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE pages SET date = ? WHERE id = ?", (new_date, page_id))
            affected_rows = cursor.rowcount
        
        if affected_rows > 0:
            logger.info(f"Дата для страницы с ID {page_id} обновлена на {new_date}")
        else:
            logger.warning(f"Не удалось обновить дату для страницы с ID {page_id}")
    except Exception as e:
        logger.error(f"Ошибка при обновлении даты для страницы с ID {page_id}: {e}")
        raise

def update_last_checked(page_id):
    """Обновляет время последней проверки страницы."""
    last_checked = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    logger.debug(f"Обновление времени последней проверки для страницы с ID {page_id} на {last_checked}")
    try:
        with get_db_connection(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE pages SET last_checked = ? WHERE id = ?", (last_checked, page_id))
            affected_rows = cursor.rowcount
        
        if affected_rows > 0:
            logger.info(f"Время последней проверки для страницы с ID {page_id} обновлено на {last_checked}")
        else:
            logger.warning(f"Не удалось обновить время последней проверки для страницы с ID {page_id}")
    except Exception as e:
        logger.error(f"Ошибка при обновлении времени последней проверки для страницы с ID {page_id}: {e}")
        raise

def delete_page(page_id):
    """Удаляет страницу из базы данных и связанный торрент-файл."""
    logger.debug(f"Удаление страницы с ID {page_id}")
    try:
        with get_db_connection(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Получаем информацию о странице перед удалением для логирования
            cursor.execute("SELECT title, url FROM pages WHERE id = ?", (page_id,))
            page_info = cursor.fetchone()
            
            cursor.execute("DELETE FROM pages WHERE id = ?", (page_id,))
            affected_rows = cursor.rowcount
        
        if affected_rows > 0:
            if page_info:
                title, url = page_info['title'], page_info['url']
                logger.info(f"Страница с ID {page_id} ('{title}', {url}) удалена")
            else:
                logger.info(f"Страница с ID {page_id} удалена")
                
            # Удаляем торрент-файл, если он существует
            torrent_file_path = os.path.join(FILE_DIR, f'{page_id}.torrent')
            if os.path.exists(torrent_file_path):
                try:
                    os.remove(torrent_file_path)
                    logger.debug(f"Торрент-файл {torrent_file_path} удален")
                except Exception as e:
                    logger.error(f"Ошибка при удалении торрент-файла {torrent_file_path}: {e}")
        else:
            logger.warning(f"Не удалось удалить страницу с ID {page_id} (возможно, не существует)")
    except Exception as e:
        logger.error(f"Ошибка при удалении страницы с ID {page_id}: {e}")
        raise
