import os
import schedule
import time
import logging
from logging.handlers import RotatingFileHandler
from threading import Thread
import telegram
from telegram.ext import (
    Updater, CommandHandler, CallbackQueryHandler, MessageHandler,
    Filters, ConversationHandler
)
from rutracker_api import RutrackerAPI
import sys

from config import (
    check_required_env_vars, BOT_TOKEN, CHECK_INTERVAL, RUTRACKER_USERNAME, 
    RUTRACKER_PASSWORD, WAITING_URL, LOG_FILE, LOG_FORMAT, LOG_MAX_BYTES, LOG_BACKUP_COUNT, 
    USE_PROXY, HTTP_PROXY, HTTPS_PROXY, TIMEZONE, QBITTORRENT_ENABLED
)
from database import init_db, init_users_db
from utils import check_pages
from handlers import (
    start, add_with_arg, add_start, add_url, cancel_add, list_pages, 
    update_page_cmd, check_now, toggle_subscription, subscription_status,
    list_users, make_admin, remove_admin, add_user_cmd, delete_user_cmd,
    user_help_cmd, button, handle_text, set_dependencies, 
    force_download, clean_files_dir, delete_all_pages
)

# Устанавливаем переменную окружения TZ
os.environ['TZ'] = TIMEZONE
try:
    time.tzset()
except AttributeError:
    # Для Windows, tzset не доступен
    pass

# Глобальные переменные для доступа в других функциях
rutracker_api = None
BOT = None

# Создание директории для лог-файла, если она не существует
log_dir = os.path.dirname(LOG_FILE)
if log_dir and not os.path.exists(log_dir):
    try:
        os.makedirs(log_dir)
        print(f"Создана директория для логов: {log_dir}")
    except Exception as e:
        print(f"ОШИБКА: Невозможно создать директорию для логов {log_dir}: {e}")
        sys.exit(1)

# Настройка логирования
# Сначала удаляем существующие обработчики, если они есть
root_logger = logging.getLogger()
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

# Настраиваем корневой логгер
root_logger.setLevel(logging.DEBUG)

# Создание обработчиков
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT)
file_handler.setLevel(logging.DEBUG)  # Записываем все в файл
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)  # В консоль только INFO и выше
stream_handler.setFormatter(logging.Formatter(LOG_FORMAT))

# Добавляем обработчики к корневому логгеру
root_logger.addHandler(file_handler)
root_logger.addHandler(stream_handler)

# Настраиваем наш логгер
logger = logging.getLogger(__name__)

# Логи запуска
logger.info("========== НАЧАЛО СЕССИИ ==========")
logger.info(f"Файл логов: {LOG_FILE}")
logger.info(f"Формат логов: {LOG_FORMAT}")
logger.info(f"Интервал проверки: {CHECK_INTERVAL} минут")
logger.info(f"Временная зона: {TIMEZONE}")
logger.debug("Настройка логирования завершена успешно")

def run_schedule_wrapper():
    """Обертка для run_schedule с обработкой исключений для логирования"""
    try:
        logger.debug("Запуск потока планировщика задач")
        run_schedule()
    except Exception as e:
        logger.error(f"Ошибка в потоке планировщика: {e}", exc_info=True)

def run_schedule():
    """Функция для выполнения запланированных задач"""
    logger.debug("Функция run_schedule запущена")
    last_run_time = None
    
    while True:
        try:
            now = time.time()
            schedule.run_pending()
            
            # Логируем выполнение задач не чаще чем раз в минуту
            if last_run_time is None or now - last_run_time >= 60:
                logger.debug("Проверка запланированных задач")
                last_run_time = now
                
            time.sleep(1)
        except Exception as e:
            logger.error(f"Ошибка при выполнении запланированных задач: {e}", exc_info=True)
            time.sleep(10)  # Пауза перед повторной попыткой

def scheduled_check():
    """Функция для запланированной проверки страниц"""
    try:
        logger.debug(f"Запуск плановой проверки (интервал: {CHECK_INTERVAL} минут)")
        result = check_pages(rutracker_api, BOT)
        logger.debug(f"Плановая проверка завершена. Результат: {result}")
        return result
    except Exception as e:
        logger.error(f"Ошибка при плановой проверке: {e}", exc_info=True)
        return False

def main() -> None:
    try:
        logger.debug("Запуск main функции")
        
        # Проверка переменных окружения
        logger.debug("Проверка переменных окружения")
        check_required_env_vars()
        
        # Инициализация баз данных
        logger.debug("Инициализация баз данных")
        init_db()
        init_users_db()
        
        # Инициализация RutrackerAPI
        logger.debug("Инициализация RutrackerAPI")
        global rutracker_api
        rutracker_api = RutrackerAPI(RUTRACKER_USERNAME, RUTRACKER_PASSWORD)
        
        # Инициализация бота
        logger.debug("Инициализация бота")
        
        # Настройка прокси
        request_kwargs = None
        if USE_PROXY:
            request_kwargs = {'proxy_url': HTTP_PROXY}
            
        # Создаем Updater без job_queue для избежания ошибок с pytz
        updater = Updater(token=BOT_TOKEN, use_context=True, request_kwargs=request_kwargs)
        dispatcher = updater.dispatcher
        
        global BOT
        BOT = updater.bot
        
        # Передаем зависимости в модуль handlers
        logger.debug("Передача зависимостей в модуль handlers")
        set_dependencies(rutracker_api, BOT)

        # Регистрация обработчиков
        logger.debug("Регистрация обработчиков команд")
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("add", add_with_arg))
        
        add_conversation = ConversationHandler(
            entry_points=[CommandHandler("add", add_start, filters=~Filters.regex(r'^/add\s+\S+'))],
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
        dispatcher.add_handler(CommandHandler("dellall", delete_all_pages))
        dispatcher.add_handler(CallbackQueryHandler(button))
        dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
                
        dispatcher.add_handler(CommandHandler("force", force_download))
        dispatcher.add_handler(CommandHandler("clean", clean_files_dir))
        logger.debug("Все обработчики команд зарегистрированы")

        # Настройка и запуск планировщика задач
        logger.debug(f"Настройка планировщика с интервалом {CHECK_INTERVAL} минут")
        schedule.every(CHECK_INTERVAL).minutes.do(scheduled_check)

        logger.debug("Запуск отдельного потока для планировщика")
        schedule_thread = Thread(target=run_schedule_wrapper)
        schedule_thread.daemon = True
        schedule_thread.start()

        # Запуск бота
        logger.info("Бот запущен и готов к работе")
        updater.start_polling()
        updater.idle()  # Ждем до тех пор, пока бот не остановят
        
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()
