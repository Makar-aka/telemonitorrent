# TELEMONITORRENT

Этот проект предтавляет собой Telegram-бота для взаимодействия с Rutracker.
Бот хранит ссылки на страницы и проверяет их на наличие обновлений раздач.
Добавь ссылку на сериал и получай уведомления о новых сериях.
Так же бот сохраняет файлы в локальную папку.\
Пользователи и страницы хранятся в бд sqlite. Первый пользователь бота становится администратором. 

## Установка

1. Клонируйте репозиторий:

git clone https://github.com/Makar-aka/telemonitorrent.git

cd telemonitorrent

pip install -r requirements.txt

4. Создайте файл `.env` в корневом каталоге проекта и добавьте в него следующие строки:

BOT_TOKEN=your_bot_token\
CHECK_INTERVAL=10\
RUTRACKER_USERNAME=your_username\
RUTRACKER_PASSWORD=your_password\
FILE_DIR=files\
USE_PROXY=true\
HTTP_PROXY=http://1.2.3.4:5678\
HTTPS_PROXY=http://1.2.3.4:5678\
LOG_FILE=bot.log\
LOG_FORMAT=%(asctime)s - %(name)s - %(levelname)s - %(message)s\
DB_PATH=database.db\
USERS_DB_PATH=users.db


## Запуск
### Обычный запуск
python3 bot.py

### Запуск как системный сервис
1.	Настройте файл сервиса:\
sudo cp telemon.service /etc/systemd/system/\
Поменяйте директории в файле telemon.service на свои. Для этого выполните команду:\
sudo nano /etc/systemd/system/telemon.service
sudo systemctl daemon-reload\
sudo systemctl enable telemon.service\
sudo systemctl start telemon.service

2.	Установите сервис:\
sudo cp telemon.service /etc/systemd/system/\
sudo systemctl daemon-reload\
sudo systemctl enable telemon.service\
sudo systemctl start telemon.service

3.	Управление сервисом:\
sudo systemctl status telemon.service  # Проверка статуса\
sudo systemctl stop telemon.service    # Остановка\
sudo systemctl restart telemon.service # Перезапуск

## Использование

Бот поддерживает следующие команды:

- `/start` - Начало работы с ботом.
- `/add <url>` - Добавить страницу с аргументом.
- `/add` - Начать диалог для добавления страницы.
- `/list` - Список всех добавленных страниц.
- `/update` - Обновить страницу.
- `/check` - Проверить страницы сейчас.
- `/help` - Показать справку по командам.
- `/subscribe` - Подписаться на обновления.
- `/status` - Показать статус подписки.
- `/users` - Список всех пользователей (административная команда).
- `/makeadmin` - Сделать пользователя администратором (административная команда).
- `/removeadmin` - Удалить пользователя из администраторов (административная команда).
- `/adduser` - Добавить пользователя (административная команда).
- `/userdel` - Удалить пользователя (административная команда).

## Логирование

Логи записываются в файл, указанный в переменной `LOG_FILE` в файле `.env`. Формат логов задается переменной `LOG_FORMAT`.


## Лицензия

Этот проект лицензирован под лицензией Apache-2.0 license. Подробности см. в файле `LICENSE`.
