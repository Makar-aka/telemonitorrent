import schedule
import time
import logging
from threading import Thread
from telegram.ext import (
    Updater, CommandHandler, CallbackQueryHandler, MessageHandler,
    Filters, ConversationHandler
)
from rutracker_api import RutrackerAPI
from dotenv import load_dotenv
import os

from config import (
    check_required_env_vars, BOT_TOKEN, CHECK_INTERVAL, RUTRACKER_USERNAME, 
    RUTRACKER_PASSWORD, WAITING_URL, logger
)
from database import init_db, init_users_db
from utils import check_pages
from handlers import (
    start, add_with_arg, add_start, add_url, cancel_add, list_pages, 
    update_page_cmd, check_now, toggle_subscription, subscription_status,
    list_users, make_admin, remove_admin, add_user_cmd, delete_user_cmd,
    user_help_cmd, button, handle_text, set_dependencies
)

# Загрузка переменных окружения из .env файла
load_dotenv()

LOG_FILE = os.getenv('LOG_FILE')
LOG_FORMAT = os.getenv('LOG_FORMAT')

# Создание файла логов, если он не существует
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, 'w') as file:
        pass

# Настройка логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Создание обработчиков
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(logging.Formatter(LOG_FORMAT))

# Добавление обработчиков к логгеру
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

# Пример логирования для проверки
logger.info("Логирование настроено")

def main() -> None:
    logger.debug("Запуск main функции")
    check_required_env_vars()
    
    # Инициализация баз данных
    logger.debug("Инициализация баз данных")
    init_db()
    init_users_db()
    
    # Инициализация RutrackerAPI
    logger.debug("Инициализация RutrackerAPI")
    rutracker_api = RutrackerAPI(RUTRACKER_USERNAME, RUTRACKER_PASSWORD)
    
    # Инициализация бота и диспетчера
    logger.debug("Инициализация бота и диспетчера")
    updater = Updater(BOT_TOKEN)
    BOT = updater.bot
    dispatcher = updater.dispatcher
    
    # Передаем зависимости в модуль handlers
    logger.debug("Передача зависимостей в модуль handlers")
    set_dependencies(rutracker_api, BOT)

    # Регистрация обработчиков
    logger.debug("Регистрация обработчиков")
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
    def scheduled_check():
        logger.debug("Запуск планировщика задач")
        return check_pages(rutracker_api, BOT)
    
    schedule.every(CHECK_INTERVAL).minutes.do(scheduled_check)

    def run_schedule():
        while True:
            schedule.run_pending()
            time.sleep(1)

    schedule_thread = Thread(target=run_schedule)
    schedule_thread.daemon = True
    schedule_thread.start()

    # Запуск бота
    logger.info("Бот запущен")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
