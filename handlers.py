from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler
from config import logger, WAITING_URL, CHECK_INTERVAL
from database import (
    get_pages, get_page_by_id, update_page_url, add_page,
    user_exists, add_user, update_user_admin, update_user_sub, delete_user, get_users, delete_page
)
from utils import check_pages, restricted, admin_required

# Определим глобальные переменные, которые будут заполнены в main.py
rutracker_api = None
BOT = None

# Создадим декораторы доступа
restricted_decorator = restricted(user_exists, add_user, get_users)
admin_required_decorator = admin_required(user_exists, add_user, get_users)

# Функция для отображения списка страниц
def display_pages_list(update_or_query):
    keyboard = []
    pages = get_pages()
    
    # Формируем заголовок с информацией о периодичности проверки
    if CHECK_INTERVAL == 1:
        interval_text = "каждую минуту"
    elif CHECK_INTERVAL < 5:
        interval_text = f"каждые {CHECK_INTERVAL} минуты"
    else:
        interval_text = f"каждые {CHECK_INTERVAL} минут"
    
    title_text = f'Страницы для мониторинга (проверка {interval_text}):'
    
    if pages:
        keyboard = []
        for page in pages:
            page_id, title, url, date, last_checked = page
            # Если дата обновления есть, добавляем ее в текст кнопки
            button_text = title
            if date:
                # Сокращаем дату до более компактного формата
                short_date = date.split()[0] if " " in date else date
                button_text = f"{title} [{short_date}]"
            
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"page_{page_id}")])
    
    keyboard.append([InlineKeyboardButton("Добавить", callback_data="add_url_button")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if isinstance(update_or_query, Update):
        update_or_query.message.reply_text(title_text, reply_markup=reply_markup)
    else:
        update_or_query.edit_message_text(text=title_text, reply_markup=reply_markup)
    
    logger.info("Список страниц отображен")

# Обработчики команд
@restricted_decorator
def start(update: Update, context: CallbackContext) -> None:
    welcome_message = ('Привет! Я могу промониторить раздачи на рутрекере, чтобы ты ничего не пропустил! '
                      'Добавь в меня ссылку на сериал, я предупрежу тебя о новых сериях и скачаю его обновления на диск!')
    
    keyboard = [
        [InlineKeyboardButton("Список", callback_data="back_to_list"), 
         InlineKeyboardButton("Добавить", callback_data="add_url_button")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(welcome_message, reply_markup=reply_markup)
    logger.info("Команда /start выполнена")

@restricted_decorator
def add_with_arg(update: Update, context: CallbackContext) -> None:
    url = context.args[0]
    title = rutracker_api.get_page_title(url)
    
    page_id, title, existing_id = add_page(title, url, rutracker_api)
    
    if page_id is None:
        # Страница уже существует
        update.message.reply_text(f'Эта ссылка уже добавлена в мониторинг под названием "{title}" (ID: {existing_id}).')
        logger.info(f"Попытка добавить дубликат URL: {url}")
    else:
        keyboard = [
            [InlineKeyboardButton("Назад к списку", callback_data="back_to_list"),
             InlineKeyboardButton("Добавить еще", callback_data="add_url_button")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(f'Страница {title} добавлена для мониторинга.', reply_markup=reply_markup)
        logger.info(f"Команда /add выполнена для URL: {url}")

@restricted_decorator
def add_start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Пришли мне ссылку для мониторинга:')
    logger.info("Запрос ссылки отправлен")
    return WAITING_URL

@restricted_decorator
def add_url(update: Update, context: CallbackContext) -> int:
    url = update.message.text
    logger.debug(f"Получена ссылка: {url}")
    
    try:
        title = rutracker_api.get_page_title(url)
        logger.debug(f"Получен заголовок: {title}")
        
        page_id, title, existing_id = add_page(title, url, rutracker_api)
        
        keyboard = [
            [InlineKeyboardButton("Назад к списку", callback_data="back_to_list"),
             InlineKeyboardButton("Добавить еще", callback_data="add_url_button")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if page_id is None:
            # Страница уже существует
            update.message.reply_text(
                f'Эта ссылка уже добавлена в мониторинг под названием "{title}" (ID: {existing_id}).',
                reply_markup=reply_markup
            )
            logger.info(f"Попытка добавить дубликат URL: {url}")
        else:
            update.message.reply_text(f'Ссылку поймал и добавил в мониторинг.', reply_markup=reply_markup)
            logger.debug("Отправлено подтверждение добавления")
            logger.info(f"Страница {title} добавлена для мониторинга через сообщение")
    except Exception as e:
        logger.error(f"Ошибка при обработке ссылки: {e}")
        update.message.reply_text(f'Произошла ошибка при обработке ссылки: {str(e)}')
    
    return ConversationHandler.END

@restricted_decorator
def cancel_add(update: Update, context: CallbackContext) -> int:
    chat_id = update.message.chat_id
    waiting_key = f'waiting_url_{chat_id}'
    if context.bot_data.get(waiting_key):
        context.bot_data[waiting_key] = False
        
    keyboard = [[InlineKeyboardButton("Назад к списку", callback_data="back_to_list")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Добавление ссылки отменено.', reply_markup=reply_markup)
    logger.info("Добавление ссылки отменено")
    return ConversationHandler.END

@restricted_decorator
def list_pages(update: Update, context: CallbackContext) -> None:
    pages = get_pages()
    if not pages:
        keyboard = [[InlineKeyboardButton("Добавить", callback_data="add_url_button")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text('Нет страниц для мониторинга.', reply_markup=reply_markup)
        logger.info("Команда /list выполнена: нет страниц для мониторинга")
        return

    display_pages_list(update)

@admin_required_decorator
def update_page_cmd(update: Update, context: CallbackContext) -> None:
    if len(context.args) != 2:
        update.message.reply_text('Использование: /update <ID> <ссылка>')
        logger.warning("Неправильное использование команды /update")
        return

    page_id = int(context.args[0])
    new_url = context.args[1]
    
    success, existing_id, existing_title = update_page_url(page_id, new_url)
    
    if not success:
        update.message.reply_text(
            f'Эта ссылка уже добавлена в мониторинг под названием "{existing_title}" (ID: {existing_id}).'
        )
        logger.info(f"Попытка обновить на дублирующуюся ссылку: {new_url}")
    else:
        keyboard = [
            [InlineKeyboardButton("Назад к списку", callback_data="back_to_list")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(f'Ссылка для страницы с ID {page_id} обновлена.', reply_markup=reply_markup)
        logger.info(f"Команда /update выполнена для страницы с ID {page_id}")

# Команда для запуска проверки вручную
@admin_required_decorator
def check_now(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Запускаю проверку страниц на обновления...')
    
    # Выполняем проверку
    updates_found = check_pages(rutracker_api, BOT)
    
    keyboard = [[InlineKeyboardButton("Назад к списку", callback_data="back_to_list")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if updates_found:
        update.message.reply_text('Проверка завершена. Найдены обновления!', reply_markup=reply_markup)
    else:
        update.message.reply_text('Проверка завершена. Обновлений не найдено.', reply_markup=reply_markup)
    
    logger.info("Запущена ручная проверка страниц")

# Команда для управления подпиской
@restricted_decorator
def toggle_subscription(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    user_data = user_exists(user_id)
    
    if not user_data:
        add_user(user_id)
        update.message.reply_text('Вы подписаны на уведомления об обновлениях.')
        logger.info(f"Пользователь {user_id} подписался на уведомления")
        return
    
    # Меняем статус подписки на противоположный
    current_sub = user_data[2]
    new_sub = 0 if current_sub == 1 else 1
    
    update_user_sub(user_id, new_sub)
    
    if new_sub == 1:
        update.message.reply_text('Вы подписаны на уведомления об обновлениях.')
        logger.info(f"Пользователь {user_id} подписался на уведомления")
    else:
        update.message.reply_text('Вы отписались от уведомлений об обновлениях.')
        logger.info(f"Пользователь {user_id} отписался от уведомлений")

# Команда для отображения статуса подписки
@restricted_decorator
def subscription_status(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    user_data = user_exists(user_id)
    
    if not user_data:
        add_user(user_id)
        update.message.reply_text('Вы подписаны на уведомления об обновлениях.')
        return
    
    is_admin = user_data[1]
    is_subscribed = user_data[2]
    
    status_text = f'Ваш ID: {user_id}\n'
    status_text += f'Статус администратора: {"Да" if is_admin else "Нет"}\n'
    status_text += f'Подписка на уведомления: {"Включена" if is_subscribed else "Отключена"}'
    
    update.message.reply_text(status_text)

# Команды для администраторов
@admin_required_decorator
def list_users(update: Update, context: CallbackContext) -> None:
    users = get_users()
    
    if not users:
        update.message.reply_text('Нет зарегистрированных пользователей.')
        return
    
    users_text = 'Список пользователей:\n\n'
    for user in users:
        user_id, is_admin, is_subscribed = user
        # Попытка получить информацию о пользователе через API
        try:
            user_info = context.bot.get_chat(user_id)
            username = user_info.username or "Нет"
            name = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip() or "Нет"
            user_details = f"@{username}, Имя: {name}"
        except Exception:
            user_details = "Информация недоступна"
        
        users_text += (f'ID: {user_id}, {user_details}\n'
                      f'Админ: {"Да" if is_admin else "Нет"}, '
                      f'Подписка: {"Да" if is_subscribed else "Нет"}\n\n')
    
    update.message.reply_text(users_text)

@admin_required_decorator
def make_admin(update: Update, context: CallbackContext) -> None:
    if len(context.args) != 1:
        update.message.reply_text('Использование: /makeadmin <ID>')
        return
    
    try:
        target_id = int(context.args[0])
        
        user_data = user_exists(target_id)
        if not user_data:
            update.message.reply_text(f'Пользователь с ID {target_id} не найден.')
            return
        
        update_user_admin(target_id, 1)
        update.message.reply_text(f'Пользователю с ID {target_id} предоставлены права администратора.')
        logger.info(f"Пользователю {target_id} предоставлены права администратора")
    except ValueError:
        update.message.reply_text('ID пользователя должен быть числом.')

@admin_required_decorator
def remove_admin(update: Update, context: CallbackContext) -> None:
    if len(context.args) != 1:
        update.message.reply_text('Использование: /removeadmin <ID>')
        return
    
    try:
        target_id = int(context.args[0])
        
        # Проверка, не пытается ли админ удалить сам себя
        if target_id == update.effective_user.id:
            update.message.reply_text('Нельзя удалить права администратора у самого себя.')
            return
        
        user_data = user_exists(target_id)
        if not user_data:
            update.message.reply_text(f'Пользователь с ID {target_id} не найден.')
            return
        
        update_user_admin(target_id, 0)
        update.message.reply_text(f'У пользователя с ID {target_id} удалены права администратора.')
        logger.info(f"У пользователя {target_id} удалены права администратора")
    except ValueError:
        update.message.reply_text('ID пользователя должен быть числом.')

@admin_required_decorator
def add_user_cmd(update: Update, context: CallbackContext) -> None:
    if len(context.args) < 1:
        update.message.reply_text('Использование: /adduser <ID> [is_admin=0] [sub=1]')
        return
    
    try:
        target_id = int(context.args[0])
        is_admin = int(context.args[1]) if len(context.args) > 1 else 0
        sub = int(context.args[2]) if len(context.args) > 2 else 1
        
        # Проверка корректности значений
        if is_admin not in [0, 1]:
            update.message.reply_text('Значение is_admin должно быть 0 или 1')
            return
        
        if sub not in [0, 1]:
            update.message.reply_text('Значение sub должно быть 0 или 1')
            return
        
        # Проверяем, существует ли уже пользователь
        user_data = user_exists(target_id)
        if user_data:
            update.message.reply_text(
                f'Пользователь с ID {target_id} уже существует. '
                f'Права администратора: {"Да" if user_data[1] else "Нет"}, '
                f'Подписка: {"Да" if user_data[2] else "Нет"}'
            )
            return
        
        add_user(target_id, is_admin, sub)
        update.message.reply_text(
            f'Пользователь с ID {target_id} добавлен. '
            f'Права администратора: {"Да" if is_admin else "Нет"}, '
            f'Подписка: {"Да" if sub else "Нет"}'
        )
        logger.info(f"Пользователь {target_id} добавлен с правами: admin={is_admin}, sub={sub}")
    except ValueError:
        update.message.reply_text('ID пользователя должен быть числом.')

@admin_required_decorator
def delete_user_cmd(update: Update, context: CallbackContext) -> None:
    if len(context.args) != 1:
        update.message.reply_text('Использование: /userdel <ID>')
        return
    
    try:
        target_id = int(context.args[0])
        
        # Проверка, не пытается ли админ удалить сам себя
        if target_id == update.effective_user.id:
            update.message.reply_text('Нельзя удалить самого себя.')
            return
        
        user_data = user_exists(target_id)
        if not user_data:
            update.message.reply_text(f'Пользователь с ID {target_id} не найден.')
            return
        
        delete_user(target_id)
        update.message.reply_text(f'Пользователь с ID {target_id} удален.')
        logger.info(f"Пользователь {target_id} удален из базы данных")
    except ValueError:
        update.message.reply_text('ID пользователя должен быть числом.')

@admin_required_decorator
def admin_help_cmd(update: Update, context: CallbackContext) -> None:
    """Показывает список всех доступных команд для администратора"""
    help_text = "<b>Список доступных команд:</b>\n\n"
    
    # Команды для всех пользователей
    help_text += "<b>Общие команды:</b>\n"
    help_text += "/start - Начало работы с ботом\n"
    help_text += "/list - Показать список отслеживаемых страниц\n"
    help_text += "/add [ссылка] - Добавить страницу для мониторинга\n"
    help_text += "/subscribe - Включить/выключить уведомления\n"
    help_text += "/status - Показать ваш статус и настройки\n\n"
    
    # Команды для администраторов
    help_text += "<b>Команды администратора:</b>\n"
    help_text += "/update [ID] [ссылка] - Обновить ссылку для страницы\n"
    help_text += "/check - Запустить проверку обновлений вручную\n"
    help_text += "/users - Показать список всех пользователей\n"
    help_text += "/adduser [ID] [is_admin=0] [sub=1] - Добавить пользователя\n"
    help_text += "/userdel [ID] - Удалить пользователя\n"
    help_text += "/makeadmin [ID] - Сделать пользователя администратором\n"
    help_text += "/removeadmin [ID] - Убрать права администратора\n"
    help_text += "/help - Показать этот список команд\n\n"
    
    help_text += "<b>Параметры:</b>\n"
    help_text += "ID - идентификатор пользователя или страницы\n"
    help_text += "is_admin - права администратора (0 или 1)\n"
    help_text += "sub - подписка на уведомления (0 или 1)"
    
    keyboard = [[InlineKeyboardButton("Назад к списку", callback_data="back_to_list")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode='HTML')
    logger.info("Отображен список команд администратора")

@restricted_decorator
def user_help_cmd(update: Update, context: CallbackContext) -> None:
    """Показывает список доступных команд для обычного пользователя"""
    
    # Проверяем, является ли пользователь администратором
    user_id = update.effective_user.id
    user_data = user_exists(user_id)
    
    if user_data and user_data[1] == 1:  # is_admin = 1
        # Перенаправляем на админскую справку
        return admin_help_cmd(update, context)
    
    help_text = "<b>Список доступных команд:</b>\n\n"
    
    # Команды для всех пользователей
    help_text += "/start - Начало работы с ботом\n"
    help_text += "/list - Показать список отслеживаемых страниц\n"
    help_text += "/add [ссылка] - Добавить страницу для мониторинга\n"
    help_text += "/subscribe - Включить/выключить уведомления\n"
    help_text += "/status - Показать ваш статус и настройки\n"
    help_text += "/help - Показать этот список команд"
    
    keyboard = [[InlineKeyboardButton("Назад к списку", callback_data="back_to_list")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode='HTML')
    logger.info("Отображен список команд пользователя")

# Функция-обработчик кнопок
@restricted_decorator
def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    data = query.data
    logger.debug(f"Обработка callback данных: {data}")

    if data == "back_to_list":
        display_pages_list(query)
        logger.info("Возврат к списку страниц")
        return

    if data == "add_url_button":
        # Отправляем сообщение с запросом URL и кнопкой отмены
        keyboard = [[InlineKeyboardButton("Отмена", callback_data="cancel_add")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        context.bot.send_message(
            chat_id=query.message.chat_id,
            text='Пришли мне ссылку для мониторинга:',
            reply_markup=reply_markup
        )
        logger.info("Отправлен запрос на ссылку после нажатия кнопки")
        context.bot_data[f'waiting_url_{query.message.chat_id}'] = True
        return
        
    if data == "cancel_add":
        # Отмена добавления URL
        chat_id = query.message.chat_id
        waiting_key = f'waiting_url_{chat_id}'
        if context.bot_data.get(waiting_key):
            context.bot_data[waiting_key] = False
        
        # Возвращаемся к списку страниц
        display_pages_list(query)
        logger.info("Добавление ссылки отменено, возврат к списку страниц")
        return

    # Разбираем данные callback
    parts = data.split('_')
    if len(parts) < 2:
        logger.warning(f"Неверный формат данных callback: {data}")
        return
    
    action = parts[0]
    
    if action == 'page':
        page_id = int(parts[1])
        page = get_page_by_id(page_id)
        if page:
            _, _, url, date, last_checked = page
            edit_date = rutracker_api.get_edit_date(url)
            keyboard = [
                [InlineKeyboardButton("Назад к списку", callback_data="back_to_list"),
                 InlineKeyboardButton("Delete", callback_data=f"delete_{page_id}"),
                 InlineKeyboardButton(f"Обновить сейчас ({last_checked})", callback_data=f"refresh_{page_id}"),
                 InlineKeyboardButton("Раздача", url=url)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.edit_message_text(text=f'Дата: {edit_date}', reply_markup=reply_markup)
            logger.info(f"Кнопка страницы с ID {page_id} нажата, дата: {edit_date}")

    elif action == 'delete':
        page_id = int(parts[1])
        delete_page(page_id)
        keyboard = [[InlineKeyboardButton("Назад к списку", callback_data="back_to_list")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text=f'Страница с ID {page_id} удалена', reply_markup=reply_markup)
        logger.info(f"Кнопка удаления для страницы с ID {page_id} нажата")

    elif action == 'refresh':
        page_id = int(parts[1])
        page = get_page_by_id(page_id)
        if page:
            _, _, url, _, _ = page
            edit_date = rutracker_api.get_edit_date(url)
            from database import update_last_checked
            update_last_checked(page_id)
            keyboard = [[InlineKeyboardButton("Назад к списку", callback_data="back_to_list")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.edit_message_text(text=f'Дата: {edit_date}', reply_markup=reply_markup)
            logger.info(f"Кнопка обновления сейчас для страницы с ID {page_id} нажата, дата: {edit_date}")

# Обработчик для текстовых сообщений
@restricted_decorator
def handle_text(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    waiting_key = f'waiting_url_{chat_id}'
    
    if context.bot_data.get(waiting_key):
        url = update.message.text
        logger.debug(f"Получена ссылка: {url}")
        
        try:
            title = rutracker_api.get_page_title(url)
            logger.debug(f"Получен заголовок: {title}")
            
            page_id, title, existing_id = add_page(title, url, rutracker_api)
            
            keyboard = [
                [InlineKeyboardButton("Назад к списку", callback_data="back_to_list"),
                 InlineKeyboardButton("Добавить еще", callback_data="add_url_button")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if page_id is None:
                # Страница уже существует
                update.message.reply_text(
                    f'Эта ссылка уже добавлена в мониторинг под названием "{title}" (ID: {existing_id}).',
                    reply_markup=reply_markup
                )
                logger.info(f"Попытка добавить дубликат URL: {url}")
            else:
                update.message.reply_text(f'Ссылку поймал и добавил в мониторинг.', reply_markup=reply_markup)
                logger.debug("Отправлено подтверждение добавления")
                logger.info(f"Страница {title} добавлена для мониторинга через сообщение")
            
            context.bot_data[waiting_key] = False
            logger.debug(f"Сброшен флаг ожидания URL для чата {chat_id}")
            
        except Exception as e:
            logger.error(f"Ошибка при обработке ссылки: {e}")
            update.message.reply_text(f'Произошла ошибка при обработке ссылки: {str(e)}')
            context.bot_data[waiting_key] = False

# Функция для установки внешних зависимостей
def set_dependencies(api, bot):
    global rutracker_api, BOT
    rutracker_api = api
    BOT = bot