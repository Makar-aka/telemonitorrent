import os
import sys
import logging
from dotenv import load_dotenv

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

# Пути к базам данных SQLite
DB_PATH = 'database.db'
USERS_DB_PATH = 'users.db'

# Состояния для ConversationHandler
WAITING_URL = 1

# Настройка логирования
logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

def check_required_env_vars():
    required_vars = ['CHECK_INTERVAL', 'BOT_TOKEN', 'LOG_LEVEL', 'LOG_FORMAT', 
                    'RUTRACKER_USERNAME', 'RUTRACKER_PASSWORD', 'FILE_DIR']
    missing_vars = [var for var in required_vars if var not in os.environ]
    
    if missing_vars:
        logger.error("ОШИБКА: Отсутствуют обязательные переменные окружения:")
        for var in missing_vars:
            logger.error(f" - {var}")
        logger.error("\nДобавьте их в файл .env или установите в окружении.")
        sys.exit(1)

# Пример функции добавления страницы
def add_page(page_url):
    logger.info(f"Добавление страницы: {page_url}")
    # Логика добавления страницы
    logger.debug(f"Полный лог добавления страницы: {page_url}")

# Пример функции обновления страницы
def update_page(page_url):
    logger.info(f"Обновление страницы: {page_url}")
    # Логика обновления страницы
    logger.debug(f"Полный лог обновления страницы: {page_url}")

# Вызов проверки переменных окружения
check_required_env_vars()
