import os
from telegram import InlineKeyboardMarkup, Update
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
    update.message.reply_text(
        'Извините, у вас нет доступа к этому боту. '
        'Пожалуйста, свяжитесь с администратором, чтобы получить доступ.'
    )
    return False

# Функция для проверки прав администратора
def check_admin_access(update: Update, user_exists_func) -> bool:
    user_id = update.effective_user.id
    user_data = user_exists_func(user_id)
    
    if user_data and user_data[1] == 1:  # is_admin = 1
        logger.debug(f"Пользователь {user_id} имеет права администратора")
        return True
    
    logger.warning(f"Пользователь {user_id} не имеет прав администратора")
    update.message.reply_text(
        'У вас нет прав администратора для выполнения этой команды.'
    )
    return False

# Функция для отправки уведомлений всем пользователям с подпиской
def send_notification_to_subscribers(bot, message, keyboard=None):
    if not NOTIFICATIONS_ENABLED:
        logger.info("Уведомления отключены в настройках")
        return

    reply_markup = None
    if keyboard:
        reply_markup = InlineKeyboardMarkup(keyboard)

    users = get_users()
    subscribers = [user[0] for user in users if user[2] == 1]  # id где sub = 1
    
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

# Функция для проверки изменений на страницах
def check_pages(rutracker_api, BOT):
    logger.info("Начата проверка страниц на обновления")
    pages = get_pages()
    updates_found = False
    
    for page in pages:
        page_id, title, url, old_date, _ = page
        logger.debug(f"Проверка страницы: {title} (ID: {page_id})")
        page_content = rutracker_api.get_page_content(url)
        new_date = rutracker_api.parse_date(page_content)
        
        if new_date and new_date != old_date:
            updates_found = True
            torrent_file_path = os.path.join(FILE_DIR, f'{page_id}.torrent')
            rutracker_api.download_torrent_by_url(url, torrent_file_path)
            update_page_date(page_id, new_date)
            logger.info(f"Дата для страницы {title} обновлена и торрент-файл скачан в {torrent_file_path}")
            
            # Отправляем уведомление о найденном обновлении
            from telegram import InlineKeyboardButton
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
            
        update_last_checked(page_id)
    
    if not updates_found:
        logger.info("Обновлений не найдено")
    
    return updates_found

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

