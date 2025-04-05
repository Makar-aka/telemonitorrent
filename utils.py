import os
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from config import logger, NOTIFICATIONS_ENABLED, FILE_DIR
from database import get_users, update_page_date, update_last_checked, get_pages

# Функция для проверки доступа пользователя
def check_user_access(update: Update, user_exists_func, add_user_func, get_users_func) -> bool:
    """
    Проверяет, имеет ли пользователь доступ к боту
    
    Args:
        update: Объект Update из Telegram
        user_exists_func: Функция для проверки существования пользователя
        add_user_func: Функция для добавления пользователя
        get_users_func: Функция для получения списка пользователей
        
    Returns:
        bool: True если пользователь имеет доступ, False в противном случае
    """
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

# Функция для проверки изменений на страницах
def check_pages(rutracker_api, BOT):
    """
    Проверяет страницы на наличие обновлений
    
    Args:
        rutracker_api: Экземпляр API RuTracker
        BOT: Экземпляр бота Telegram
        
    Returns:
        bool: True если найдены обновления, False в противном случае
    """
    logger.info("Начата проверка страниц на обновления")
    
    try:
        pages = get_pages()
        
        if not pages:
            logger.info("Нет страниц для проверки")
            return False
            
        updates_found = False
        
        for page in pages:
            page_id, title, url, old_date, _ = page
            logger.debug(f"Проверка страницы: {title} (ID: {page_id})")
            
            try:
                page_content = rutracker_api.get_page_content(url)
                if not page_content:
                    logger.error(f"Не удалось получить содержимое страницы {title} (ID: {page_id})")
                    continue
                    
                new_date = rutracker_api.parse_date(page_content)
                if not new_date:
                    logger.warning(f"Не удалось определить дату для страницы {title} (ID: {page_id})")
                
                if new_date and new_date != old_date:
                    updates_found = True
                    torrent_file_path = os.path.join(FILE_DIR, f'{page_id}.torrent')
                    
                    # Скачиваем торрент-файл
                    if rutracker_api.download_torrent_by_url(url, torrent_file_path):
                        # Обновляем дату в базе данных
                        update_page_date(page_id, new_date)
                        logger.info(f"Дата для страницы {title} обновлена ({old_date or 'Не задана'} -> {new_date})")
                        logger.info(f"Торрент-файл скачан в {torrent_file_path}")
                        
                        # Формируем сообщение об обновлении
                        notification_message = (
                            f"<b>🆕 Найдено обновление!</b>\n\n"
                            f"<b>Название:</b> {title}\n"
                            f"<b>Новая дата:</b> {new_date}\n"
                            f"<b>Предыдущая дата:</b> {old_date or 'Не задана'}\n"
                            f"<b>ID:</b> {page_id}"
                        )
                        
                        keyboard = [
                            [InlineKeyboardButton("Открыть раздачу", url=url)],
                            [InlineKeyboardButton("Посмотреть список", callback_data="back_to_list")]
                        ]
                        
                        # Отправляем уведомление подписчикам
                        send_notification_to_subscribers(BOT, notification_message, keyboard)
                    else:
                        logger.error(f"Не удалось скачать торрент-файл для страницы {title} (ID: {page_id})")
            except Exception as e:
                logger.error(f"Ошибка при проверке страницы {title} (ID: {page_id}): {e}")
            finally:
                # Обновляем время последней проверки в любом случае
                update_last_checked(page_id)
        
        if not updates_found:
            logger.info("Обновлений не найдено")
        
        return updates_found
            
    except Exception as e:
        logger.error(f"Ошибка при проверке страниц: {e}")
        return False

# Декораторы доступа
def restricted(user_exists_func, add_user_func, get_users_func):
    """
    Декоратор для ограничения доступа к функциям бота
    
    Args:
        user_exists_func: Функция для проверки существования пользователя
        add_user_func: Функция для добавления пользователя
        get_users_func: Функция для получения списка пользователей
        
    Returns:
        Декоратор, который проверяет доступ пользователя
    """
    def decorator(func):
        def wrapped(update, context, *args, **kwargs):
            if not check_user_access(update, user_exists_func, add_user_func, get_users_func):
                return
            return func(update, context, *args, **kwargs)
        return wrapped
    return decorator

def admin_required(user_exists_func, add_user_func, get_users_func):
    """
    Декоратор для ограничения доступа к административным функциям бота
    
    Args:
        user_exists_func: Функция для проверки существования пользователя
        add_user_func: Функция для добавления пользователя
        get_users_func: Функция для получения списка пользователей
        
    Returns:
        Декоратор, который проверяет права администратора
    """
    def decorator(func):
        def wrapped(update, context, *args, **kwargs):
            if not check_user_access(update, user_exists_func, add_user_func, get_users_func):
                return
            if not check_admin_access(update, user_exists_func):
                return
            return func(update, context, *args, **kwargs)
        return wrapped
    return decorator
