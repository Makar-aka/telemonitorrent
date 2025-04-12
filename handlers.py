import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler
from config import logger, WAITING_URL, CHECK_INTERVAL, FILE_DIR
from database import (
    get_pages, get_page_by_id, update_page_url, add_page,
    user_exists, add_user, update_user_admin, update_user_sub, delete_user, get_users, delete_page,
    update_last_checked
)
from utils import check_pages, restricted, admin_required, upload_to_qbittorrent

# Определим глобальные переменные, которые будут заполнены в main.py
rutracker_api = None
BOT = None

# Создадим декораторы доступа
restricted_decorator = restricted(user_exists, add_user, get_users)
admin_required_decorator = admin_required(user_exists, add_user, get_users)

# Общие клавиатуры для повторного использования
BACK_TO_LIST_KEYBOARD = InlineKeyboardMarkup([[
    InlineKeyboardButton("Назад к списку", callback_data="back_to_list")
]])

ADD_MORE_KEYBOARD = InlineKeyboardMarkup([[
    InlineKeyboardButton("Назад к списку", callback_data="back_to_list"),
    InlineKeyboardButton("Добавить еще", callback_data="add_url_button")
]])

# Функция для отображения списка страниц
def display_pages_list(update_or_query):
    logger.debug("Отображение списка страниц начато")
    pages = get_pages()
    page_count = len(pages) if pages else 0
    logger.debug(f"Получено {page_count} страниц из базы данных")
    
    # Формируем заголовок с информацией о периодичности проверки
    if CHECK_INTERVAL == 1:
        interval_text = "каждую минуту"
    elif CHECK_INTERVAL < 5:
        interval_text = f"каждые {CHECK_INTERVAL} минуты"
    else:
        interval_text = f"каждые {CHECK_INTERVAL} минут"
    
    title_text = f'Страницы для мониторинга (проверка {interval_text}):'
    
    keyboard = []
    if pages:
        for page in pages:
            page_id, title, url, date, last_checked = page
            # Если дата обновления есть, добавляем ее в текст кнопки
            button_text = title
            if date:
                # Сокращаем дату до более компактного формата
                short_date = date.split()[0] if " " in date else date
                button_text = f"{title} [{short_date}]"
            
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"page_{page_id}")])
            logger.debug(f"Добавлена кнопка для страницы: {title} (ID: {page_id})")
    
    keyboard.append([InlineKeyboardButton("Добавить", callback_data="add_url_button")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if isinstance(update_or_query, Update):
        update_or_query.message.reply_text(title_text, reply_markup=reply_markup)
        logger.debug("Список страниц отправлен как новое сообщение")
    else:
        update_or_query.edit_message_text(text=title_text, reply_markup=reply_markup)
        logger.debug("Список страниц отправлен как редактирование существующего сообщения")
    
    logger.info("Список страниц отображен")

# Обработчики команд
@restricted_decorator
def start(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    logger.debug(f"Команда /start от пользователя {user_id}")
    
    welcome_message = ('Привет! Я могу промониторить раздачи на рутрекере, чтобы ты ничего не пропустил! '
                      'Добавь в меня ссылку на сериал, я предупрежу тебя о новых сериях и скачаю его обновления на диск! '
                      '\nПодробности в /help')
    
    keyboard = [
        [InlineKeyboardButton("Список", callback_data="back_to_list"), 
         InlineKeyboardButton("Добавить", callback_data="add_url_button")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(welcome_message, reply_markup=reply_markup)
    logger.info(f"Команда /start выполнена для пользователя {user_id}")

@restricted_decorator
def add_with_arg(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    logger.debug(f"Команда /add с аргументами от пользователя {user_id}")
    
    if not context.args:
        update.message.reply_text('Использование: /add <ссылка>')
        logger.warning(f"Команда /add вызвана без аргументов пользователем {user_id}")
        return
    
    url = context.args[0]
    logger.debug(f"Получен URL для добавления от пользователя {user_id}")
    
    try:
        title = rutracker_api.get_page_title(url)
        logger.debug(f"Получен заголовок: {title}")
        
        page_id, title, existing_id = add_page(title, url, rutracker_api)
        
        if page_id is None:
            # Страница уже существует
            update.message.reply_text(
                f'Эта ссылка уже добавлена в мониторинг под названием "{title}" (ID: {existing_id}).',
                reply_markup=ADD_MORE_KEYBOARD
            )
            logger.info(f"Попытка добавить дубликат URL пользователем {user_id}")
        else:
            update.message.reply_text(
                f'Страница {title} добавлена для мониторинга.',
                reply_markup=ADD_MORE_KEYBOARD
            )
            logger.info(f"Команда /add выполнена пользователем {user_id} для страницы {title}")
            
            # Скачиваем торрент-файл
            file_path = os.path.join(FILE_DIR, f"{page_id}.torrent")
            downloaded_file = rutracker_api.download_torrent_by_url(url, file_path)
            
            if downloaded_file:
                # Отправляем торрент-файл в qBittorrent
                qbit_result = upload_to_qbittorrent(downloaded_file)
                
                if qbit_result:
                    update.message.reply_text(f"Торрент-файл скачан и отправлен в qBittorrent: {os.path.basename(downloaded_file)}")
                    logger.info(f"Торрент-файл для страницы {title} отправлен в qBittorrent")
                else:
                    update.message.reply_text(f"Торрент-файл скачан, но не отправлен в qBittorrent: {os.path.basename(downloaded_file)}")
                    logger.warning(f"Не удалось отправить торрент-файл для страницы {title} в qBittorrent")
            else:
                update.message.reply_text("Не удалось скачать торрент-файл.")
                logger.error(f"Ошибка при скачивании торрент-файла для страницы {title}")
    except Exception as e:
        update.message.reply_text(f'Произошла ошибка при обработке ссылки: {str(e)}')
        logger.error(f"Ошибка при обработке ссылки от пользователя {user_id}: {e}")

@restricted_decorator
def add_start(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    logger.debug(f"Команда /add без аргументов от пользователя {user_id}")
    update.message.reply_text('Пришли мне ссылку для мониторинга:')
    logger.info(f"Запрос ссылки отправлен пользователю {user_id}")
    return WAITING_URL

@restricted_decorator
def add_url(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    url = update.message.text
    logger.debug(f"Получена ссылка от пользователя {user_id}")
    
    try:
        # Получаем заголовок страницы
        title = rutracker_api.get_page_title(url)
        logger.debug(f"Получен заголовок: {title}")
        
        # Добавляем страницу в базу данных
        page_id, title, existing_id = add_page(title, url, rutracker_api)
        
        if page_id is None:
            # Если страница уже существует
            update.message.reply_text(
                f'Эта ссылка уже добавлена в мониторинг под названием "{title}" (ID: {existing_id}).',
                reply_markup=ADD_MORE_KEYBOARD
            )
            logger.info(f"Попытка добавить дубликат URL пользователем {user_id}")
        else:
            # Успешное добавление
            update.message.reply_text(
                f'Ссылку поймал и добавил в мониторинг.',
                reply_markup=ADD_MORE_KEYBOARD
            )
            logger.info(f"Страница {title} добавлена для мониторинга пользователем {user_id}")
            
            # Скачиваем торрент-файл
            logger.debug(f"Попытка скачать торрент-файл для ссылки: {url}")
            file_path = os.path.join(FILE_DIR, f"{page_id}.torrent")
            downloaded_file = rutracker_api.download_torrent_by_url(url, file_path)
            
            if downloaded_file:
                # Отправляем торрент-файл в qBittorrent
                qbit_result = upload_to_qbittorrent(downloaded_file)
                
                if qbit_result:
                    update.message.reply_text(f"Торрент-файл скачан и отправлен в qBittorrent: {os.path.basename(downloaded_file)}")
                    logger.info(f"Торрент-файл для страницы {title} отправлен в qBittorrent")
                else:
                    update.message.reply_text(f"Торрент-файл скачан, но не отправлен в qBittorrent: {os.path.basename(downloaded_file)}")
                    logger.warning(f"Не удалось отправить торрент-файл для страницы {title} в qBittorrent")
            else:
                update.message.reply_text("Не удалось скачать торрент-файл.")
                logger.error(f"Ошибка при скачивании торрент-файла для страницы {title}")
    except Exception as e:
        logger.error(f"Ошибка при обработке ссылки от пользователя {user_id}: {e}")
        update.message.reply_text(f'Произошла ошибка при обработке ссылки: {str(e)}')
    
    return ConversationHandler.END

@restricted_decorator
def cancel_add(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    logger.debug(f"Команда /cancel от пользователя {user_id}")
    
    chat_id = update.message.chat_id
    waiting_key = f'waiting_url_{chat_id}'
    if context.bot_data.get(waiting_key):
        context.bot_data[waiting_key] = False
        logger.debug(f"Сброшен флаг ожидания URL для чата {chat_id}")
    
    update.message.reply_text('Добавление ссылки отменено.', reply_markup=BACK_TO_LIST_KEYBOARD)
    logger.info(f"Добавление ссылки отменено пользователем {user_id}")
    return ConversationHandler.END

@restricted_decorator
def list_pages(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    logger.debug(f"Команда /list от пользователя {user_id}")
    
    pages = get_pages()
    if not pages:
        keyboard = [[InlineKeyboardButton("Добавить", callback_data="add_url_button")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text('Нет страниц для мониторинга.', reply_markup=reply_markup)
        logger.info(f"Команда /list выполнена для пользователя {user_id}: нет страниц для мониторинга")
        return

    display_pages_list(update)
    logger.info(f"Команда /list выполнена для пользователя {user_id}")

@admin_required_decorator
def update_page_cmd(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    logger.debug(f"Команда /update от пользователя {user_id}")
    
    if len(context.args) != 2:
        update.message.reply_text('Использование: /update <ID> <ссылка>')
        logger.warning(f"Неправильное использование команды /update пользователем {user_id}")
        return

    try:
        page_id = int(context.args[0])
        new_url = context.args[1]
        logger.debug(f"Обновление страницы с ID {page_id} пользователем {user_id}")
        
        success, existing_id, existing_title = update_page_url(page_id, new_url)
        
        if not success:
            update.message.reply_text(
                f'Эта ссылка уже добавлена в мониторинг под названием "{existing_title}" (ID: {existing_id}).'
            )
            logger.info(f"Попытка обновить на дублирующуюся ссылку пользователем {user_id}")
        else:
            update.message.reply_text(
                f'Ссылка для страницы с ID {page_id} обновлена.',
                reply_markup=BACK_TO_LIST_KEYBOARD
            )
            logger.info(f"Команда /update выполнена для страницы с ID {page_id} пользователем {user_id}")
    except ValueError:
        update.message.reply_text('ID страницы должен быть числом.')
        logger.warning(f"Некорректный ID страницы в команде /update от {user_id}")

# Команда для запуска проверки вручную
@admin_required_decorator
def check_now(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    logger.debug(f"Команда /check от пользователя {user_id}")
    
    update.message.reply_text('Запускаю проверку страниц на обновления...')
    logger.debug("Запуск ручной проверки страниц")
    
    # Выполняем проверку
    updates_found = check_pages(rutracker_api, BOT)
    
    message = 'Проверка завершена. ' + ('Найдены обновления!' if updates_found else 'Обновлений не найдено.')
    update.message.reply_text(message, reply_markup=BACK_TO_LIST_KEYBOARD)
    
    logger.info(f"Завершена ручная проверка страниц пользователем {user_id}. Результат: {updates_found}")

@admin_required_decorator
def force_download(update: Update, context: CallbackContext) -> None:
    """
    Принудительно загружает все отслеживаемые страницы, независимо от даты обновления
    """
    user_id = update.effective_user.id
    logger.debug(f"Команда /force от пользователя {user_id}")
    
    update.message.reply_text('Начинаю принудительную загрузку всех отслеживаемых страниц...')
    logger.debug("Запуск принудительной загрузки всех страниц")
    
    # Получаем все страницы из БД
    pages = get_pages()
    
    if not pages:
        update.message.reply_text('Нет страниц для загрузки.')
        logger.info("Нет страниц для принудительной загрузки")
        return
    
    total_pages = len(pages)
    success_count = 0
    error_count = 0
    
    # Отправляем статусное сообщение
    status_msg = update.message.reply_text(f"Загрузка торрентов: 0/{total_pages}")
    
    for idx, page in enumerate(pages, 1):
        page_id, title, url, _, _ = page
        
        try:
            logger.debug(f"Принудительная загрузка страницы: {title} (ID: {page_id})")
            
            # Скачиваем торрент-файл
            file_path = os.path.join(FILE_DIR, f"{page_id}.torrent")
            torrent_file_path = rutracker_api.download_torrent_by_url(url, file_path)
            
            if torrent_file_path:
                # Отправляем торрент-файл в qBittorrent
                qbit_result = upload_to_qbittorrent(torrent_file_path)
                if qbit_result:
                    logger.info(f"Торрент-файл для страницы {title} загружен и отправлен в qBittorrent")
                    success_count += 1
                else:
                    logger.warning(f"Торрент-файл загружен, но не отправлен в qBittorrent: {title}")
                    error_count += 1
            else:
                logger.error(f"Не удалось загрузить торрент-файл для страницы {title}")
                error_count += 1
                
            # Обновляем время последней проверки
            update_last_checked(page_id)
            
            # Обновляем статусное сообщение каждые несколько страниц или в конце
            if idx % 5 == 0 or idx == total_pages:
                try:
                    context.bot.edit_message_text(
                        chat_id=status_msg.chat_id,
                        message_id=status_msg.message_id,
                        text=f"Загрузка торрентов: {idx}/{total_pages}"
                    )
                except Exception:
                    # Игнорируем ошибки редактирования сообщения
                    pass
                
        except Exception as e:
            logger.error(f"Ошибка при загрузке страницы {title}: {e}")
            error_count += 1
    
    # Отправляем итоговое сообщение
    result_message = (
        f"Принудительная загрузка завершена.\n"
        f"Всего страниц: {total_pages}\n"
        f"Успешно: {success_count}\n"
        f"С ошибками: {error_count}"
    )
    
    update.message.reply_text(result_message)
    logger.info(f"Принудительная загрузка завершена. Успешно: {success_count}, С ошибками: {error_count}")

@admin_required_decorator
def clean_files_dir(update: Update, context: CallbackContext) -> None:
    """
    Очищает директорию с торрент-файлами
    """
    user_id = update.effective_user.id
    logger.debug(f"Команда /clean от пользователя {user_id}")
    
    # Проверка подтверждения
    if len(context.args) == 1 and context.args[0].lower() == "confirm":
        confirmed = True
    else:
        confirmed = False
    
    if not confirmed:
        update.message.reply_text(
            'Эта команда удалит все файлы из папки торрентов.\n'
            'Для подтверждения введите: /clean confirm'
        )
        return
    
    try:
        # Удаляем все файлы .torrent из FILE_DIR
        file_count = 0
        for filename in os.listdir(FILE_DIR):
            if filename.endswith(".torrent"):
                file_path = os.path.join(FILE_DIR, filename)
                try:
                    os.remove(file_path)
                    file_count += 1
                    logger.debug(f"Удален файл: {file_path}")
                except Exception as e:
                    logger.error(f"Не удалось удалить файл {file_path}: {e}")
        
        update.message.reply_text(f'Директория очищена. Удалено файлов: {file_count}')
        logger.info(f"Директория {FILE_DIR} очищена. Удалено {file_count} файлов пользователем {user_id}")
    except Exception as e:
        error_msg = f"Ошибка при очистке директории: {e}"
        update.message.reply_text(error_msg)
        logger.error(error_msg)


# Команда для управления подпиской
@restricted_decorator
def toggle_subscription(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    logger.debug(f"Команда /subscribe от пользователя {user_id}")
    
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
    
    message = 'Вы подписаны на уведомления об обновлениях.' if new_sub == 1 else 'Вы отписались от уведомлений об обновлениях.'
    update.message.reply_text(message)
    
    logger.info(f"Пользователь {user_id} {'подписался на' if new_sub == 1 else 'отписался от'} уведомления")

# Команда для отображения статуса подписки
@restricted_decorator
def subscription_status(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    logger.debug(f"Команда /status от пользователя {user_id}")
    
    user_data = user_exists(user_id)
    
    if not user_data:
        add_user(user_id)
        update.message.reply_text('Вы подписаны на уведомления об обновлениях.')
        logger.info(f"Пользователь {user_id} автоматически подписан при проверке статуса")
        return
    
    is_admin = user_data[1]
    is_subscribed = user_data[2]
    
    status_text = f'Ваш ID: {user_id}\n'
    status_text += f'Статус администратора: {"Да" if is_admin else "Нет"}\n'
    status_text += f'Подписка на уведомления: {"Включена" if is_subscribed else "Отключена"}'
    
    update.message.reply_text(status_text)
    logger.info(f"Статус подписки отображен для пользователя {user_id}")

# Команды для администраторов
@admin_required_decorator
def list_users(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    logger.debug(f"Команда /users от пользователя {user_id}")
    
    users = get_users()
    
    if not users:
        update.message.reply_text('Нет зарегистрированных пользователей.')
        logger.info("Команда /users выполнена: нет зарегистрированных пользователей")
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
            logger.debug(f"Получена информация о пользователе {user_id}")
        except Exception as e:
            user_details = "Информация недоступна"
            logger.debug(f"Не удалось получить информацию о пользователе {user_id}: {e}")
        
        users_text += (f'ID: {user_id}, {user_details}\n'
                      f'Админ: {"Да" if is_admin else "Нет"}, '
                      f'Подписка: {"Да" if is_subscribed else "Нет"}\n\n')
    
    update.message.reply_text(users_text)
    logger.info(f"Список пользователей отображен для администратора {update.effective_user.id}")

@admin_required_decorator
def make_admin(update: Update, context: CallbackContext) -> None:
    admin_id = update.effective_user.id
    logger.debug(f"Команда /makeadmin от пользователя {admin_id}")
    
    if len(context.args) != 1:
        update.message.reply_text('Использование: /makeadmin <ID>')
        logger.warning(f"Неправильное использование команды /makeadmin пользователем {admin_id}")
        return
    
    try:
        target_id = int(context.args[0])
        logger.debug(f"Попытка сделать пользователя {target_id} администратором")
        
        user_data = user_exists(target_id)
        if not user_data:
            update.message.reply_text(f'Пользователь с ID {target_id} не найден.')
            logger.warning(f"Пользователь с ID {target_id} не найден при попытке сделать его администратором")
            return
        
        update_user_admin(target_id, 1)
        update.message.reply_text(f'Пользователю с ID {target_id} предоставлены права администратора.')
        logger.info(f"Пользователю {target_id} предоставлены права администратора администратором {admin_id}")
    except ValueError:
        update.message.reply_text('ID пользователя должен быть числом.')
        logger.warning(f"Некорректный ID пользователя в команде /makeadmin от {admin_id}")

@admin_required_decorator
def remove_admin(update: Update, context: CallbackContext) -> None:
    admin_id = update.effective_user.id
    logger.debug(f"Команда /removeadmin от пользователя {admin_id}")
    
    if len(context.args) != 1:
        update.message.reply_text('Использование: /removeadmin <ID>')
        logger.warning(f"Неправильное использование команды /removeadmin пользователем {admin_id}")
        return
    
    try:
        target_id = int(context.args[0])
        logger.debug(f"Попытка удалить права администратора у пользователя {target_id}")
        
        # Проверка, не пытается ли админ удалить сам себя
        if target_id == admin_id:
            update.message.reply_text('Нельзя удалить права администратора у самого себя.')
            logger.warning(f"Пользователь {admin_id} пытается удалить права администратора у самого себя")
            return
        
        user_data = user_exists(target_id)
        if not user_data:
            update.message.reply_text(f'Пользователь с ID {target_id} не найден.')
            logger.warning(f"Пользователь с ID {target_id} не найден при попытке удалить права администратора")
            return
        
        update_user_admin(target_id, 0)
        update.message.reply_text(f'У пользователя с ID {target_id} удалены права администратора.')
        logger.info(f"У пользователя {target_id} удалены права администратора администратором {admin_id}")
    except ValueError:
        update.message.reply_text('ID пользователя должен быть числом.')
        logger.warning(f"Некорректный ID пользователя в команде /removeadmin от {admin_id}")

@admin_required_decorator
def add_user_cmd(update: Update, context: CallbackContext) -> None:
    admin_id = update.effective_user.id
    logger.debug(f"Команда /adduser от пользователя {admin_id}")
    
    if len(context.args) < 1:
        update.message.reply_text('Использование: /adduser <ID> [is_admin=0] [sub=1]')
        logger.warning(f"Неправильное использование команды /adduser пользователем {admin_id}")
        return
    
    try:
        target_id = int(context.args[0])
        is_admin = int(context.args[1]) if len(context.args) > 1 else 0
        sub = int(context.args[2]) if len(context.args) > 2 else 1
        
        logger.debug(f"Попытка добавить пользователя {target_id} с правами: admin={is_admin}, sub={sub}")
        
        # Проверка корректности значений
        if is_admin not in [0, 1]:
            update.message.reply_text('Значение is_admin должно быть 0 или 1')
            logger.warning(f"Некорректное значение is_admin в команде /adduser от {admin_id}")
            return
        
        if sub not in [0, 1]:
            update.message.reply_text('Значение sub должно быть 0 или 1')
            logger.warning(f"Некорректное значение sub в команде /adduser от {admin_id}")
            return
        
        # Проверяем, существует ли уже пользователь
        user_data = user_exists(target_id)
        if user_data:
            update.message.reply_text(
                f'Пользователь с ID {target_id} уже существует. '
                f'Права администратора: {"Да" if user_data[1] else "Нет"}, '
                f'Подписка: {"Да" if user_data[2] else "Нет"}'
            )
            logger.info(f"Пользователь {target_id} уже существует, не добавлен")
            return
        
        add_user(target_id, is_admin, sub)
        update.message.reply_text(
            f'Пользователь с ID {target_id} добавлен. '
            f'Права администратора: {"Да" if is_admin else "Нет"}, '
            f'Подписка: {"Да" if sub else "Нет"}'
        )
        logger.info(f"Пользователь {target_id} добавлен с правами: admin={is_admin}, sub={sub} администратором {admin_id}")
    except ValueError:
        update.message.reply_text('ID пользователя должен быть числом.')
        logger.warning(f"Некорректный ID пользователя в команде /adduser от {admin_id}")

@admin_required_decorator
def delete_user_cmd(update: Update, context: CallbackContext) -> None:
    admin_id = update.effective_user.id
    logger.debug(f"Команда /userdel от пользователя {admin_id}")
    
    if len(context.args) != 1:
        update.message.reply_text('Использование: /userdel <ID>')
        logger.warning(f"Неправильное использование команды /userdel пользователем {admin_id}")
        return
    
    try:
        target_id = int(context.args[0])
        logger.debug(f"Попытка удалить пользователя {target_id}")
        
        # Проверка, не пытается ли админ удалить сам себя
        if target_id == admin_id:
            update.message.reply_text('Нельзя удалить самого себя.')
            logger.warning(f"Пользователь {admin_id} пытается удалить самого себя")
            return
        
        user_data = user_exists(target_id)
        if not user_data:
            update.message.reply_text(f'Пользователь с ID {target_id} не найден.')
            logger.warning(f"Пользователь с ID {target_id} не найден при попытке удалить")
            return
        
        delete_user(target_id)
        update.message.reply_text(f'Пользователь с ID {target_id} удален.')
        logger.info(f"Пользователь {target_id} удален из базы данных администратором {admin_id}")
    except ValueError:
        update.message.reply_text('ID пользователя должен быть числом.')
        logger.warning(f"Некорректный ID пользователя в команде /userdel от {admin_id}")

@admin_required_decorator
def delete_all_pages(update: Update, context: CallbackContext) -> None:
    """
    Удаляет все отслеживаемые ссылки и соответствующие торрент-файлы
    """
    user_id = update.effective_user.id
    logger.debug(f"Команда /dellall от пользователя {user_id}")
    
    # Проверка подтверждения
    if len(context.args) == 1 and context.args[0].lower() == "confirm":
        confirmed = True
    else:
        confirmed = False
    
    if not confirmed:
        update.message.reply_text(
            'Эта команда удалит ВСЕ отслеживаемые страницы и их торрент-файлы.\n'
            'Действие необратимо! Для подтверждения введите: /dellall confirm'
        )
        return
    
    try:
        # Получаем список всех страниц
        pages = get_pages()
        
        if not pages:
            update.message.reply_text('Нет страниц для удаления.')
            logger.info(f"Нет страниц для удаления по команде пользователя {user_id}")
            return
        
        total_pages = len(pages)
        deleted_pages = 0
        deleted_files = 0
        
        # Удаляем страницы и их файлы
        for page in pages:
            page_id, title, _, _, _ = page
            
            # Удаляем соответствующий торрент-файл, если он существует
            file_path = os.path.join(FILE_DIR, f"{page_id}.torrent")
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    deleted_files += 1
                    logger.debug(f"Удален файл: {file_path}")
                except Exception as e:
                    logger.error(f"Не удалось удалить файл {file_path}: {e}")
            
            # Удаляем страницу из базы данных
            delete_page(page_id)
            deleted_pages += 1
            logger.debug(f"Удалена страница: {title} (ID: {page_id})")
        
        result_message = (
            f"Операция завершена.\n"
            f"Удалено страниц: {deleted_pages} из {total_pages}\n"
            f"Удалено файлов: {deleted_files} из {total_pages}"
        )
        
        update.message.reply_text(result_message)
        logger.info(f"Удаление всех страниц завершено. Удалено страниц: {deleted_pages}, файлов: {deleted_files}")
    except Exception as e:
        error_msg = f"Ошибка при удалении всех страниц: {e}"
        update.message.reply_text(error_msg)
        logger.error(error_msg)

@admin_required_decorator
def admin_help_cmd(update: Update, context: CallbackContext) -> None:
    """Показывает список всех доступных команд для администратора"""
    admin_id = update.effective_user.id
    logger.debug(f"Команда /help от администратора {admin_id}")
    
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
    help_text += "/help - Показать этот список команд\n"
    help_text += "/force - Принудительная загрузка всех страниц\n"
    help_text += "/clean - Очистить директорию с торрент-файлами\n"
    help_text += "/dellall - Удалить ВСЕ отслеживаемые страницы и их файлы\n"

    help_text += "<b>Параметры:</b>\n"
    help_text += "ID - идентификатор пользователя или страницы\n"
    help_text += "is_admin - права администратора (0 или 1)\n"
    help_text += "sub - подписка на уведомления (0 или 1)"
    
    update.message.reply_text(help_text, reply_markup=BACK_TO_LIST_KEYBOARD, parse_mode='HTML')
    logger.info(f"Отображен список команд администратора для пользователя {admin_id}")

@restricted_decorator
def user_help_cmd(update: Update, context: CallbackContext) -> None:
    """Показывает список доступных команд для обычного пользователя"""
    user_id = update.effective_user.id
    logger.debug(f"Команда /help от пользователя {user_id}")
    
    # Проверяем, является ли пользователь администратором
    user_data = user_exists(user_id)
    
    if user_data and user_data[1] == 1:  # is_admin = 1
        # Перенаправляем на админскую справку
        logger.debug(f"Пользователь {user_id} является администратором, перенаправляем на админскую справку")
        return admin_help_cmd(update, context)
    
    help_text = "<b>Список доступных команд:</b>\n\n"
    
    # Команды для всех пользователей
    help_text += "/start - Начало работы с ботом\n"
    help_text += "/list - Показать список отслеживаемых страниц\n"
    help_text += "/add [ссылка] - Добавить страницу для мониторинга\n"
    help_text += "/subscribe - Включить/выключить уведомления\n"
    help_text += "/status - Показать ваш статус и настройки\n"
    help_text += "/help - Показать этот список команд"
    
    update.message.reply_text(help_text, reply_markup=BACK_TO_LIST_KEYBOARD, parse_mode='HTML')
    logger.info(f"Отображен список команд пользователя для пользователя {user_id}")

# Функция-обработчик кнопок
@restricted_decorator
def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    data = query.data
    user_id = query.from_user.id
    logger.debug(f"Обработка callback данных: {data} от пользователя {user_id}")

    if data == "back_to_list":
        display_pages_list(query)
        logger.info(f"Возврат к списку страниц для пользователя {user_id}")
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
        logger.info(f"Отправлен запрос на ссылку после нажатия кнопки пользователем {user_id}")
        context.bot_data[f'waiting_url_{query.message.chat_id}'] = True
        return
        
    if data == "cancel_add":
        # Отмена добавления URL
        chat_id = query.message.chat_id
        waiting_key = f'waiting_url_{chat_id}'
        if context.bot_data.get(waiting_key):
            context.bot_data[waiting_key] = False
            logger.debug(f"Сброшен флаг ожидания URL для чата {chat_id}")
        
        # Возвращаемся к списку страниц
        display_pages_list(query)
        logger.info(f"Добавление ссылки отменено, возврат к списку страниц для пользователя {user_id}")
        return

    # Разбираем данные callback
    parts = data.split('_')
    if len(parts) < 2:
        logger.warning(f"Неверный формат данных callback: {data} от пользователя {user_id}")
        return
    
    action = parts[0]
    
    if action == 'page':
        page_id = int(parts[1])
        logger.debug(f"Запрос информации о странице с ID {page_id} от пользователя {user_id}")
        page = get_page_by_id(page_id)
        if page:
            _, title, url, date, last_checked = page
            edit_date = rutracker_api.get_edit_date(url)
            keyboard = [
                [InlineKeyboardButton("Назад к списку", callback_data="back_to_list"),
                 InlineKeyboardButton("Delete", callback_data=f"delete_{page_id}"),
                 InlineKeyboardButton(f"Обновить сейчас ({last_checked})", callback_data=f"refresh_{page_id}"),
                 InlineKeyboardButton("Раздача", url=url)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.edit_message_text(text=f'Дата: {edit_date}', reply_markup=reply_markup)
            logger.info(f"Кнопка страницы с ID {page_id} нажата пользователем {user_id}, дата: {edit_date}")

    elif action == 'delete':
        page_id = int(parts[1])
        logger.debug(f"Запрос на удаление страницы с ID {page_id} от пользователя {user_id}")
        delete_page(page_id)
        query.edit_message_text(text=f'Страница с ID {page_id} удалена', reply_markup=BACK_TO_LIST_KEYBOARD)
        logger.info(f"Страница с ID {page_id} удалена пользователем {user_id}")

    elif action == 'refresh':
        page_id = int(parts[1])
        logger.debug(f"Запрос на обновление страницы с ID {page_id} от пользователя {user_id}")
        page = get_page_by_id(page_id)
        if page:
            page_id, title, url, _, _ = page
            edit_date = rutracker_api.get_edit_date(url)
            update_last_checked(page_id)
            
            # Скачиваем торрент-файл
            file_path = os.path.join(FILE_DIR, f"{page_id}.torrent")
            downloaded_file = rutracker_api.download_torrent_by_url(url, file_path)
            
            if downloaded_file:
                # Отправляем торрент-файл в qBittorrent
                qbit_result = upload_to_qbittorrent(downloaded_file)
                
                message = f'Дата: {edit_date}\n'
                if qbit_result:
                    message += 'Торрент-файл отправлен в qBittorrent'
                    logger.info(f"Торрент-файл для страницы {title} отправлен в qBittorrent")
                else:
                    message += 'Не удалось отправить торрент-файл в qBittorrent'
                    logger.warning(f"Не удалось отправить торрент-файл для страницы {title} в qBittorrent")
                    
                query.edit_message_text(text=message, reply_markup=BACK_TO_LIST_KEYBOARD)
            else:
                query.edit_message_text(text=f'Дата: {edit_date}\nНе удалось скачать торрент-файл', reply_markup=BACK_TO_LIST_KEYBOARD)
                logger.error(f"Ошибка при скачивании торрент-файла для страницы {page_id}")
            
            logger.info(f"Страница с ID {page_id} обновлена пользователем {user_id}, дата: {edit_date}")

# Обработчик для текстовых сообщений
@restricted_decorator
def handle_text(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    user_id = update.effective_user.id
    waiting_key = f'waiting_url_{chat_id}'
    
    if context.bot_data.get(waiting_key):
        url = update.message.text
        logger.debug(f"Получена ссылка от пользователя {user_id}")
        
        try:
            title = rutracker_api.get_page_title(url)
            logger.debug(f"Получен заголовок: {title}")
            
            page_id, title, existing_id = add_page(title, url, rutracker_api)
            
            if page_id is None:
                # Страница уже существует
                update.message.reply_text(
                    f'Эта ссылка уже добавлена в мониторинг под названием "{title}" (ID: {existing_id}).',
                    reply_markup=ADD_MORE_KEYBOARD
                )
                logger.info(f"Попытка добавить дубликат URL пользователем {user_id}")
            else:
                update.message.reply_text(
                    f'Ссылку поймал и добавил в мониторинг.',
                    reply_markup=ADD_MORE_KEYBOARD
                )
                logger.debug("Отправлено подтверждение добавления")
                logger.info(f"Страница {title} добавлена для мониторинга через сообщение пользователем {user_id}")
                
                # Скачиваем торрент-файл
                file_path = os.path.join(FILE_DIR, f"{page_id}.torrent")
                downloaded_file = rutracker_api.download_torrent_by_url(url, file_path)
                
                if downloaded_file:
                    # Отправляем торрент-файл в qBittorrent
                    qbit_result = upload_to_qbittorrent(downloaded_file)
                    
                    if qbit_result:
                        update.message.reply_text(f"Торрент-файл скачан и отправлен в qBittorrent: {os.path.basename(downloaded_file)}")
                        logger.info(f"Торрент-файл для страницы {title} отправлен в qBittorrent")
                    else:
                        update.message.reply_text(f"Торрент-файл скачан, но не отправлен в qBittorrent: {os.path.basename(downloaded_file)}")
                        logger.warning(f"Не удалось отправить торрент-файл для страницы {title} в qBittorrent")
                else:
                    update.message.reply_text("Не удалось скачать торрент-файл.")
                    logger.error(f"Ошибка при скачивании торрент-файла для страницы {title}")
            
            context.bot_data[waiting_key] = False
            logger.debug(f"Сброшен флаг ожидания URL для чата {chat_id}")
            
        except Exception as e:
            logger.error(f"Ошибка при обработке ссылки от пользователя {user_id}: {e}")
            update.message.reply_text(f'Произошла ошибка при обработке ссылки: {str(e)}')
            context.bot_data[waiting_key] = False

# Функция для установки внешних зависимостей
def set_dependencies(api, bot):
    global rutracker_api, BOT
    rutracker_api = api
    BOT = bot
    logger.debug("Установлены внешние зависимости (rutracker_api и BOT)")
