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

# Пути к базам данных SQLite
DB_PATH = get_env_var('DB_PATH')
USERS_DB_PATH = get_env_var('USERS_DB_PATH')

# Состояния для ConversationHandler
WAITING_URL = 1

# Создание базового логгера (будет переопределен в bot.py)
logger = logging.getLogger(__name__)

def check_required_env_vars():
    """
    Проверяет доступность важных ресурсов для работы программы.
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
    
    # Вывод информации о текущих настройках
    print(f"Интервал проверки: {CHECK_INTERVAL} минут")
    print(f"Директория для файлов: {FILE_DIR}")
    print(f"Файл логов: {LOG_FILE}")
    print(f"Уведомления: {'Включены' if NOTIFICATIONS_ENABLED else 'Отключены'}")
    print(f"Временная зона: {TIMEZONE}")
