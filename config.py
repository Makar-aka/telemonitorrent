import os
import sys
import logging
from dotenv import load_dotenv

# Загрузка переменных окружения из файла .env
load_dotenv()

# Функция для получения обязательных переменных окружения
def get_env_var(name):
    value = os.environ.get(name)
    if value is None:
        print(f"ОШИБКА: Переменная окружения {name} не задана")
        sys.exit(1)
    return value

# Основные настройки
CHECK_INTERVAL = int(get_env_var('CHECK_INTERVAL'))
BOT_TOKEN = get_env_var('BOT_TOKEN')
LOG_LEVEL = get_env_var('LOG_LEVEL')
LOG_FORMAT = get_env_var('LOG_FORMAT')
LOG_FILE = get_env_var('LOG_FILE')
LOG_MAX_BYTES = int(os.environ.get('LOG_MAX_BYTES', 10485760))  # 10 MB по умолчанию
LOG_BACKUP_COUNT = int(os.environ.get('LOG_BACKUP_COUNT', 5))  # 5 резервных копий по умолчанию
RUTRACKER_USERNAME = get_env_var('RUTRACKER_USERNAME')
RUTRACKER_PASSWORD = get_env_var('RUTRACKER_PASSWORD')
FILE_DIR = get_env_var('FILE_DIR')
NOTIFICATIONS_ENABLED = os.environ.get('NOTIFICATIONS_ENABLED', 'True').lower() == 'true'
USE_PROXY = os.environ.get('USE_PROXY', 'false').lower() == 'true'
HTTP_PROXY = os.environ.get('HTTP_PROXY', '')
HTTPS_PROXY = os.environ.get('HTTPS_PROXY', '')
TIMEZONE = os.environ.get('TIMEZONE', 'UTC')

# Настройки qBittorrent
QBITTORRENT_ENABLED = os.environ.get('QBITTORRENT_ENABLED', 'false').lower() == 'true'
QBITTORRENT_URL = os.environ.get('QBITTORRENT_URL')
QBITTORRENT_USERNAME = os.environ.get('QBITTORRENT_USERNAME')
QBITTORRENT_PASSWORD = os.environ.get('QBITTORRENT_PASSWORD')
QBITTORRENT_CATEGORY = os.environ.get('QBITTORRENT_CATEGORY')
QBITTORRENT_SAVE_PATH = os.environ.get('QBITTORRENT_SAVE_PATH', '')

# Пути к базам данных SQLite
DB_PATH = get_env_var('DB_PATH')
USERS_DB_PATH = get_env_var('USERS_DB_PATH')

# Состояния для ConversationHandler
WAITING_URL = 1

# Создание базового логгера (будет переопределен в bot.py)
logger = logging.getLogger(__name__)

def check_required_env_vars():
    """
    Проверяет доступность важных ресурсов для работы программы и авторизацию в qBittorrent.
    """
    # Проверка возможности создания директории для файлов
    if not os.path.exists(FILE_DIR):
        try:
            os.makedirs(FILE_DIR)
            print(f"Создана директория для файлов: {FILE_DIR}")
        except Exception as e:
            print(f"ОШИБКА: Невозможно создать директорию {FILE_DIR}: {e}")
            sys.exit(1)
    
    # Создание директории для лог-файла, если она не существует
    log_dir = os.path.dirname(LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
            print(f"Создана директория для логов: {log_dir}")
        except Exception as e:
            print(f"ОШИБКА: Невозможно создать директорию для логов {log_dir}: {e}")
            sys.exit(1)
    
    # Проверка авторизации в qBittorrent, если включено
    if QBITTORRENT_ENABLED:
        if not QBITTORRENT_URL:
            print("ОШИБКА: Включена интеграция с qBittorrent, но не указан URL (QBITTORRENT_URL)")
            sys.exit(1)
        
        try:
            check_qbittorrent_auth()
            print(f"Подключение к qBittorrent успешно настроено ({QBITTORRENT_URL})")
        except Exception as e:
            print(f"ОШИБКА: Не удалось подключиться к qBittorrent: {e}")
            sys.exit(1)
    
    # Вывод информации о текущих настройках
    print(f"Интервал проверки: {CHECK_INTERVAL} минут")
    print(f"Директория для файлов: {FILE_DIR}")
    print(f"Файл логов: {LOG_FILE}")
    print(f"Уведомления: {'Включены' if NOTIFICATIONS_ENABLED else 'Отключены'}")
    print(f"Временная зона: {TIMEZONE}")
    print(f"qBittorrent: {'Включен' if QBITTORRENT_ENABLED else 'Отключен'}")

def check_qbittorrent_auth():
    """
    Проверяет авторизацию в qBittorrent API.
    
    Raises:
        Exception: Если авторизация не удалась.
    """
    import requests
    
    if not QBITTORRENT_ENABLED:
        return
    
    if not QBITTORRENT_URL:
        raise Exception("Не указан URL qBittorrent")
    
    try:
        # Создаем сессию
        session = requests.Session()
        
        # Авторизуемся
        login_url = f"{QBITTORRENT_URL}/api/v2/auth/login"
        login_data = {
            "username": QBITTORRENT_USERNAME or "admin",  # Используем значение по умолчанию, если не указано
            "password": QBITTORRENT_PASSWORD or "adminadmin"  # Используем значение по умолчанию, если не указано
        }
        
        login_response = session.post(login_url, data=login_data, timeout=10)
        
        if login_response.status_code != 200:
            raise Exception(f"Ошибка авторизации. Код статуса: {login_response.status_code}")
        
        # Проверяем версию API для подтверждения успешной авторизации
        api_version_url = f"{QBITTORRENT_URL}/api/v2/app/version"
        api_version_response = session.get(api_version_url, timeout=10)
        
        if api_version_response.status_code != 200:
            raise Exception(f"Ошибка проверки версии API. Код статуса: {api_version_response.status_code}")
        
        qbittorrent_version = api_version_response.text
        print(f"Версия qBittorrent: {qbittorrent_version}")
        
    except requests.exceptions.ConnectionError:
        raise Exception("Не удалось подключиться к qBittorrent. Проверьте URL и доступность сервера.")
    except requests.exceptions.Timeout:
        raise Exception("Таймаут подключения к qBittorrent.")
    except Exception as e:
        raise Exception(f"Ошибка при авторизации в qBittorrent: {e}")
