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
    Проверяет авторизацию в qBittorrent API.
    
    Returns:
        bool: True если авторизация успешна, иначе False
    """
    import requests
    import urllib.parse
    from config import (
        QBITTORRENT_ENABLED, QBITTORRENT_URL, QBITTORRENT_USERNAME, 
        QBITTORRENT_PASSWORD, logger
    )
    
    if not QBITTORRENT_ENABLED:
        return True
    
    if not QBITTORRENT_URL:
        logger.error("Не указан URL qBittorrent")
        return False
    
    try:
        # Создаем сессию
        session = requests.Session()
        
        # Проверяем сначала доступность API без авторизации
        try:
            logger.debug(f"Проверка доступности qBittorrent API: {QBITTORRENT_URL}")
            api_version_url = f"{QBITTORRENT_URL}/api/v2/app/version"
            api_version_response = session.get(api_version_url, timeout=10)
            
            if api_version_response.status_code == 200:
                logger.info(f"qBittorrent доступен, версия: {api_version_response.text}")
            else:
                logger.warning(f"qBittorrent API недоступен. Код: {api_version_response.status_code}")
                return False
        except Exception as e:
            logger.warning(f"Ошибка при проверке API qBittorrent: {e}")
            return False
        
        # Авторизуемся
        login_url = f"{QBITTORRENT_URL}/api/v2/auth/login"
        
        # Подготовка данных авторизации
        form_data = {
            "username": QBITTORRENT_USERNAME or "admin",
            "password": QBITTORRENT_PASSWORD or "adminadmin"
        }
        
        # Пробуем различные способы отправки данных для поддержки разных версий qBittorrent
        
        # Способ 1: Стандартный для большинства новых версий
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        encoded_data = urllib.parse.urlencode(form_data)
        
        logger.debug(f"Попытка авторизации в qBittorrent (способ 1)")
        login_response = session.post(
            login_url, 
            data=encoded_data,
            headers=headers,
            timeout=10
        )
        
        if login_response.status_code == 200:
            logger.debug("Авторизация в qBittorrent успешна (способ 1)")
        else:
            logger.debug(f"Авторизация не удалась (способ 1). Код: {login_response.status_code}")
            
            # Способ 2: Прямая передача данных формы
            logger.debug(f"Попытка авторизации в qBittorrent (способ 2)")
            login_response = session.post(
                login_url,
                data=form_data,
                timeout=10
            )
            
            if login_response.status_code != 200:
                logger.debug(f"Авторизация не удалась (способ 2). Код: {login_response.status_code}")
                
                # Способ 3: Пробуем через другой путь API (для старых версий)
                alt_login_url = f"{QBITTORRENT_URL}/login"
                logger.debug(f"Попытка авторизации в qBittorrent (способ 3): {alt_login_url}")
                login_response = session.post(
                    alt_login_url,
                    data=form_data,
                    timeout=10
                )
                
                if login_response.status_code != 200:
                    logger.error("Все попытки авторизации не удались")
                    return False
                else:
                    logger.debug("Авторизация в qBittorrent успешна (способ 3)")
            else:
                logger.debug("Авторизация в qBittorrent успешна (способ 2)")
        
        # Проверяем авторизацию, запросив информацию о клиенте
        check_url = f"{QBITTORRENT_URL}/api/v2/app/version"
        check_response = session.get(check_url, timeout=10)
        
        if check_response.status_code == 200:
            logger.info(f"Авторизация в qBittorrent подтверждена, версия: {check_response.text}")
            return True
        else:
            logger.error(f"Ошибка проверки авторизации в qBittorrent. Код: {check_response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        logger.error(f"Не удалось подключиться к qBittorrent по адресу {QBITTORRENT_URL}")
        return False
    except requests.exceptions.Timeout:
        logger.error("Таймаут подключения к qBittorrent")
        return False
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при авторизации в qBittorrent: {e}")
        return False
# Функция для проверки изменений на страницах
def check_pages(rutracker_api, BOT, specific_url=None):
    """
    Проверяет все страницы (или конкретную страницу) на наличие обновлений
    
    Args:
        rutracker_api: Экземпляр API Rutracker
        BOT: Экземпляр бота Telegram
        specific_url: Конкретный URL для проверки (опционально)
        
    Returns:
        bool: True если найдены обновления, иначе False
    """
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
    
    import requests
    from config import (
        QBITTORRENT_ENABLED, QBITTORRENT_URL, QBITTORRENT_USERNAME, 
        QBITTORRENT_PASSWORD, QBITTORRENT_CATEGORY, QBITTORRENT_SAVE_PATH,
        logger
    )
    
    if not QBITTORRENT_ENABLED:
        logger.debug("Загрузка в qBittorrent отключена в настройках")
        return False
    
    try:
        # Создаем сессию
        session = requests.Session()
        
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
