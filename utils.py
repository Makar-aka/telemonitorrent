import os
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from config import logger, NOTIFICATIONS_ENABLED, FILE_DIR
from database import get_users, update_page_date, update_last_checked, get_pages


# Функция для проверки доступа пользователя
def check_user_access(update: Update, user_exists_func, add_user_func, get_users_func) -> bool:
   
    user_id = update.effective_user.id
    user_data = user_exists_func(user_id)
    
    if user_data:
        logger.debug(f"Пользователь {user_id} имеет доступ")
        return True
    
    # Если пользователя нет в базе
    username = update.effective_user.username or "Не указано"
    first_name = update.effective_user.first_name or "Не указано"
    last_name = update.effective_user.last_name or "Не указано"
    
    # Проверяем, пуста ли база (для первого администратора)
    if len(get_users_func()) == 0:
        add_user_func(user_id, is_admin=1)
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
    try:
        update.message.reply_text(
            'Извините, у вас нет доступа к этому боту. '
            'Пожалуйста, свяжитесь с администратором, чтобы получить доступ.'
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения об отсутствии доступа: {e}")
        
    return False

# Функция для проверки прав администратора
def check_admin_access(update: Update, user_exists_func) -> bool:
    """
    Проверяет, имеет ли пользователь права администратора
    
    Args:
        update: Объект Update из Telegram
        user_exists_func: Функция для проверки существования пользователя
        
    Returns:
        bool: True если пользователь имеет права администратора, False в противном случае
    """
    user_id = update.effective_user.id
    user_data = user_exists_func(user_id)
    
    if user_data and user_data[1] == 1:  # is_admin = 1
        logger.debug(f"Пользователь {user_id} имеет права администратора")
        return True
    
    logger.warning(f"Пользователь {user_id} не имеет прав администратора")
    
    try:
        update.message.reply_text(
            'У вас нет прав администратора для выполнения этой команды.'
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения об отсутствии прав администратора: {e}")
        
    return False

# Функция для отправки уведомлений всем пользователям с подпиской
def send_notification_to_subscribers(bot, message, keyboard=None):
    """
    Отправляет уведомление всем подписанным пользователям
    
    Args:
        bot: Экземпляр бота Telegram
        message: Текст сообщения
        keyboard: Опциональная клавиатура
    """
    if not NOTIFICATIONS_ENABLED:
        logger.info("Уведомления отключены в настройках")
        return

    reply_markup = None
    if keyboard:
        reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        users = get_users()
        subscribers = [user[0] for user in users if user[2] == 1]  # id где sub = 1
        
        if not subscribers:
            logger.info("Нет подписанных пользователей для отправки уведомлений")
            return
            
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
                logger.debug(f"Уведомление отправлено пользователю {user_id}")
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")
        
        logger.info(f"Отправлено уведомлений: {success_count} из {len(subscribers)}")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений: {e}")
def check_qbittorrent_auth():
    """
    Проверяет авторизацию в qBittorrent API используя библиотеку python-qbittorrent.
    
    Returns:
        bool: True если авторизация успешна, иначе False
    """
    from qbittorrent import Client
    from config import (
        QBITTORRENT_ENABLED, QBITTORRENT_URL, QBITTORRENT_USERNAME, 
        QBITTORRENT_PASSWORD, logger
    )
    
    if not QBITTORRENT_ENABLED:
        return True
    
    if not QBITTORRENT_URL:
        logger.error("Не указан URL qBittorrent")
        return False
    
    # Сохраняем оригинальные значения прокси
    original_http_proxy = os.environ.get('HTTP_PROXY')
    original_https_proxy = os.environ.get('HTTPS_PROXY')
    
    try:
        # Временно удаляем переменные окружения прокси
        if 'HTTP_PROXY' in os.environ:
            del os.environ['HTTP_PROXY']
        if 'HTTPS_PROXY' in os.environ:
            del os.environ['HTTPS_PROXY']
        if 'http_proxy' in os.environ:
            del os.environ['http_proxy']
        if 'https_proxy' in os.environ:
            del os.environ['https_proxy']
            
        logger.debug(f"Проверка подключения к qBittorrent: {QBITTORRENT_URL}")
        
        # Создаем клиент qBittorrent
        qbt_client = Client(QBITTORRENT_URL)
        
        # Авторизуемся
        qbt_client.login(
            QBITTORRENT_USERNAME or "admin",
            QBITTORRENT_PASSWORD or "adminadmin"
        )
        
        # Если мы дошли до этой точки без исключений, авторизация успешна
        # Проверим версию, чтобы убедиться, что соединение работает
        # В библиотеке python-qbittorrent используется метод qb_api_version() вместо app_version()
        try:
            api_version = qbt_client.qbittorrent_version
            logger.info(f"Подключение к qBittorrent успешно. Версия клиента: {api_version}")
        except:
            # Если атрибут qbittorrent_version не доступен, попробуем получить любую другую информацию
            # для подтверждения соединения
            torrents = qbt_client.torrents()
            logger.info(f"Подключение к qBittorrent успешно. Текущее количество торрентов: {len(torrents)}")
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при подключении к qBittorrent: {e}")
        return False
    finally:
        # Восстанавливаем прокси-настройки
        if original_http_proxy:
            os.environ['HTTP_PROXY'] = original_http_proxy
        if original_https_proxy:
            os.environ['HTTPS_PROXY'] = original_https_proxy


def upload_to_qbittorrent(file_path):
    """
    Отправляет торрент-файл в qBittorrent через библиотеку python-qbittorrent
    
    Args:
        file_path (str): Путь к торрент-файлу
        
    Returns:
        bool: True если отправка успешна, иначе False
    """
    from qbittorrent import Client
    from config import (
        QBITTORRENT_ENABLED, QBITTORRENT_URL, QBITTORRENT_USERNAME, 
        QBITTORRENT_PASSWORD, QBITTORRENT_CATEGORY, QBITTORRENT_SAVE_PATH,
        logger
    )
    
    if not QBITTORRENT_ENABLED:
        logger.debug("Загрузка в qBittorrent отключена в настройках")
        return False
    
    # Сохраняем оригинальные значения прокси
    original_http_proxy = os.environ.get('HTTP_PROXY')
    original_https_proxy = os.environ.get('HTTPS_PROXY')
    
    try:
        # Временно удаляем переменные окружения прокси
        if 'HTTP_PROXY' in os.environ:
            del os.environ['HTTP_PROXY']
        if 'HTTPS_PROXY' in os.environ:
            del os.environ['HTTPS_PROXY']
        if 'http_proxy' in os.environ:
            del os.environ['http_proxy']
        if 'https_proxy' in os.environ:
            del os.environ['https_proxy']
        
        logger.debug(f"Подключение к qBittorrent для загрузки файла: {file_path}")
        
        # Создаем клиент qBittorrent
        qbt_client = Client(QBITTORRENT_URL)
        
        # Авторизуемся
        qbt_client.login(QBITTORRENT_USERNAME, QBITTORRENT_PASSWORD)
        
        # Подготавливаем параметры для загрузки торрента
        options = {}
        
        if QBITTORRENT_CATEGORY:
            options['category'] = QBITTORRENT_CATEGORY
            
        if QBITTORRENT_SAVE_PATH:
            options['savepath'] = QBITTORRENT_SAVE_PATH
            
        # Добавляем торрент
        with open(file_path, 'rb') as torrent_file:
            torrent_data = torrent_file.read()
            qbt_client.download_from_file(torrent_data, **options)
            
        logger.info(f"Торрент-файл {os.path.basename(file_path)} успешно добавлен в qBittorrent")
        
        # Посчитаем количество торрентов (без вызова несуществующих методов)
        try:
            torrents_count = len(qbt_client.torrents())
            logger.debug(f"Всего торрентов в qBittorrent: {torrents_count}")
        except:
            pass
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке торрента в qBittorrent: {e}")
        return False
    finally:
        # Восстанавливаем прокси-настройки
        if original_http_proxy:
            os.environ['HTTP_PROXY'] = original_http_proxy
        if original_https_proxy:
            os.environ['HTTPS_PROXY'] = original_https_proxy


def get_qbittorrent_client():
    """
    Создает и настраивает клиент qBittorrent с управлением прокси
    
    Returns:
        Client: Настроенный и авторизованный клиент qBittorrent или None при ошибке
    """
    from qbittorrent import Client
    from config import (
        QBITTORRENT_ENABLED, QBITTORRENT_URL, QBITTORRENT_USERNAME, 
        QBITTORRENT_PASSWORD, logger
    )
    
    if not QBITTORRENT_ENABLED or not QBITTORRENT_URL:
        return None
    
    # Сохраняем оригинальные значения прокси
    original_http_proxy = os.environ.get('HTTP_PROXY')
    original_https_proxy = os.environ.get('HTTPS_PROXY')
    
    try:
        # Временно удаляем переменные окружения прокси
        if 'HTTP_PROXY' in os.environ:
            del os.environ['HTTP_PROXY']
        if 'HTTPS_PROXY' in os.environ:
            del os.environ['HTTPS_PROXY']
        if 'http_proxy' in os.environ:
            del os.environ['http_proxy']
        if 'https_proxy' in os.environ:
            del os.environ['https_proxy']
        
        # Создаем и настраиваем клиент
        client = Client(QBITTORRENT_URL)
        client.login(QBITTORRENT_USERNAME, QBITTORRENT_PASSWORD)
        
        return client
    except Exception as e:
        logger.error(f"Не удалось создать клиент qBittorrent: {e}")
        return None
    finally:
        # Восстанавливаем прокси-настройки
        if original_http_proxy:
            os.environ['HTTP_PROXY'] = original_http_proxy
        if original_https_proxy:
            os.environ['HTTPS_PROXY'] = original_https_proxy


# Функция для проверки изменений на страницах
def check_pages(rutracker_api, BOT, specific_url=None):
    
    logger.info("Начата проверка страниц на обновления")
    
    try:
        # Получаем список страниц
        pages = get_pages()
        
        if not pages:
            logger.info("Нет страниц для проверки")
            return False
        
        updates_found = False
        
        for page in pages:
            page_id, title, url, old_date, last_checked = page
            
            # Если указан specific_url, пропускаем остальные страницы
            if specific_url and url != specific_url:
                continue
            
            logger.debug(f"Проверка страницы: {title} (ID: {page_id})")
            
            try:
                # Получаем содержимое страницы
                page_content = rutracker_api.get_page_content(url)
                if not page_content:
                    logger.error(f"Не удалось получить содержимое страницы {title} (ID: {page_id})")
                    continue
                
                # Получаем новую дату обновления
                new_date = rutracker_api.parse_date(page_content)
                
                # Если дата обновления изменилась
                if new_date and new_date != old_date:
                    updates_found = True
                    logger.info(f"Обнаружено обновление страницы: {title} (ID: {page_id})")
                    logger.info(f"Старая дата: {old_date}, Новая дата: {new_date}")
                    
                    # Обновляем дату в базе данных
                    update_page_date(page_id, new_date)
                    
                    # Скачиваем торрент-файл
                    file_path = os.path.join(FILE_DIR, f"{page_id}.torrent")
                    torrent_file_path = rutracker_api.download_torrent_by_url(url, file_path)
                    
                    if torrent_file_path:
                        logger.info(f"Торрент-файл скачан и сохранен в {torrent_file_path}")
                        
                        # Отправляем торрент-файл в qBittorrent
                        qbit_result = upload_to_qbittorrent(torrent_file_path)
                        if qbit_result:
                            logger.info(f"Торрент-файл для страницы {title} отправлен в qBittorrent")
                        else:
                            logger.warning(f"Не удалось отправить торрент-файл для страницы {title} в qBittorrent")
                        
                        # Отправляем уведомление подписчикам
                        message = (
                            f"<b>Обновление!</b>\n"
                            f"Раздача: {title}\n"
                            f"Дата обновления: {new_date}\n"
                            f"<a href='{url}'>Ссылка на страницу</a>"
                        )
                        keyboard = [[
                            InlineKeyboardButton("Открыть в браузере", url=url)
                        ]]
                        send_notification_to_subscribers(BOT, message, keyboard)
                    else:
                        logger.error(f"Не удалось скачать торрент-файл для {title} (ID: {page_id})")
            except Exception as e:
                logger.error(f"Ошибка при проверке страницы {title} (ID: {page_id}): {e}")
            finally:
                # Обновляем время последней проверки
                update_last_checked(page_id)
        
        if not updates_found:
            logger.info("Обновлений не найдено")
        
        return updates_found
    except Exception as e:
        logger.error(f"Ошибка при проверке страниц: {e}")
        return False

# Декораторы доступа
def restricted(user_exists_func, add_user_func, get_users_func):
   
    def decorator(func):
        def wrapped(update, context, *args, **kwargs):
            if not check_user_access(update, user_exists_func, add_user_func, get_users_func):
                return
            return func(update, context, *args, **kwargs)
        return wrapped
    return decorator

def admin_required(user_exists_func, add_user_func, get_users_func):
    
    def decorator(func):
        def wrapped(update, context, *args, **kwargs):
            if not check_user_access(update, user_exists_func, add_user_func, get_users_func):
                return
            if not check_admin_access(update, user_exists_func):
                return
            return func(update, context, *args, **kwargs)
        return wrapped
    return decorator

def upload_to_qbittorrent(file_path):
    """
    Отправляет торрент-файл в qBittorrent через веб-интерфейс
    
    Args:
        file_path (str): Путь к торрент-файлу
        
    Returns:
        bool: True если отправка успешна, иначе False
    """
    import requests
    from config import (
        QBITTORRENT_ENABLED, QBITTORRENT_URL, QBITTORRENT_USERNAME, 
        QBITTORRENT_PASSWORD, QBITTORRENT_CATEGORY, QBITTORRENT_SAVE_PATH,
        logger
    )
    
    if not QBITTORRENT_ENABLED:
        logger.debug("Загрузка в qBittorrent отключена в настройках")
        return False
    
    # Сохраняем оригинальные значения прокси
    original_http_proxy = os.environ.get('HTTP_PROXY')
    original_https_proxy = os.environ.get('HTTPS_PROXY')
    
    try:
        # Временно удаляем переменные окружения прокси
        if 'HTTP_PROXY' in os.environ:
            del os.environ['HTTP_PROXY']
        if 'HTTPS_PROXY' in os.environ:
            del os.environ['HTTPS_PROXY']
        if 'http_proxy' in os.environ:
            del os.environ['http_proxy']
        if 'https_proxy' in os.environ:
            del os.environ['https_proxy']
            
        # Создаем сессию
        session = requests.Session()
        # Явно отключаем прокси для qBittorrent
        session.proxies = {'http': None, 'https': None}
        
        # Авторизуемся
        login_url = f"{QBITTORRENT_URL}/api/v2/auth/login"
        login_data = {
            "username": QBITTORRENT_USERNAME,
            "password": QBITTORRENT_PASSWORD
        }
        login_response = session.post(login_url, data=login_data)
        
        if login_response.status_code != 200:
            logger.error(f"Ошибка авторизации в qBittorrent: {login_response.status_code}")
            return False
            
        # Загружаем торрент-файл
        upload_url = f"{QBITTORRENT_URL}/api/v2/torrents/add"
        
        # Подготавливаем данные для загрузки
        upload_data = {}
        if QBITTORRENT_CATEGORY:
            upload_data["category"] = QBITTORRENT_CATEGORY
        if QBITTORRENT_SAVE_PATH:
            upload_data["savepath"] = QBITTORRENT_SAVE_PATH
            
        # Открываем файл для отправки
        with open(file_path, 'rb') as torrent_file:
            files = {'torrents': torrent_file}
            upload_response = session.post(upload_url, data=upload_data, files=files)
        
        if upload_response.status_code == 200:
            logger.info(f"Торрент-файл {file_path} успешно добавлен в qBittorrent")
            return True
        else:
            logger.error(f"Ошибка при загрузке торрента в qBittorrent: {upload_response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка при отправке торрент-файла в qBittorrent: {e}")
        return False
    finally:
        # Восстанавливаем прокси-настройки
        if original_http_proxy:
            os.environ['HTTP_PROXY'] = original_http_proxy
        if original_https_proxy:
            os.environ['HTTPS_PROXY'] = original_https_proxy

def get_torrent_status(torrent_hash=None):
    """
    Получает информацию о статусе торрента или всех торрентов в qBittorrent
    
    Args:
        torrent_hash (str, optional): Хеш торрента для получения информации
        
    Returns:
        dict/list: Информация о торренте или список всех торрентов
    """
    client = get_qbittorrent_client()
    
    if not client:
        return None
    
    try:
        if torrent_hash:
            # Получаем список всех торрентов
            all_torrents = client.torrents()
            
            # Находим нужный торрент по хешу
            for torrent in all_torrents:
                if torrent.get('hash', '').lower() == torrent_hash.lower():
                    return torrent
            return None
        else:
            # Возвращаем информацию обо всех торрентах
            return client.torrents()
    except Exception as e:
        logger.error(f"Ошибка при получении информации о торрентах: {e}")
        return None