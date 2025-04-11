# TELEMONITORRENT

Этот проект предтавляет собой Telegram-бота для взаимодействия с Rutracker.
Бот хранит ссылки на страницы и проверяет их на наличие обновлений раздач.\
Добавь ссылку на сериал и получай уведомления о новых сериях.\
Так же бот сохраняет файлы в локальную папку.\
Пользователи и страницы хранятся в бд sqlite. Первый пользователь бота становится администратором. 

## Требования
- Python 3.x
- Библиотеки, указанные в `requirements.txt`

## Установка

1. Клонируйте репозиторий:

git clone https://github.com/Makar-aka/telemonitorrent.git

cd telemonitorrent\
sudo apt update\
sudo apt install python3 python3-pip\
pip install -r requirements.txt

4. Создайте файл `.env` в корневом каталоге проекта и добавьте в него следующие строки:

BOT_TOKEN=your_bot_token\
CHECK_INTERVAL=10\
RUTRACKER_USERNAME=your_username\
RUTRACKER_PASSWORD=your_password\
FILE_DIR=files\
USE_PROXY=false\
HTTP_PROXY=\
HTTPS_PROXY=\
LOG_FILE=bot.log\
LOG_LEVEL=INFO\
LOG_FORMAT=%(asctime)s - %(name)s - %(levelname)s - %(message)s\
DB_PATH=database.db\
USERS_DB_PATH=users.db

LOG_MAX_BYTES=5120  # 5 MB
LOG_BACKUP_COUNT=5

## Запуск
### Обычный запуск
python3 bot.py

------
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
------

### Запуск в docker compose
Создайте м заполние .env

создайте файлы базы и логов в папке с проектом:
```bash
touch database.db
touch users.db
touch bot.log
```
Создайте файл docker-compose.yml в корневом каталоге проекта и добавьте в него следующие строки:

```yaml
services:
  bot:
    build: https://github.com/Makar-aka/telemonitorrent.git
    container_name: telemonitorrent
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
      - RUTRACKER_USERNAME=${RUTRACKER_USERNAME}
      - RUTRACKER_PASSWORD=${RUTRACKER_PASSWORD}
      - CHECK_INTERVAL=${CHECK_INTERVAL}
      - FILE_DIR=${FILE_DIR}
      - DB_PATH=${DB_PATH}
      - USERS_DB_PATH=${USERS_DB_PATH}
      - LOG_FILE=${LOG_FILE}
      - LOG_LEVEL=${LOG_LEVEL}
      - LOG_FORMAT=${LOG_FORMAT}
      - TZ=Europe/Moscow
    volumes:
      - ./files:/files
      - ./users.db:/app/users.db
      - ./database.db:/app/database.db
      - ./bot.log:/app/bot.log
    user: "1000:1000"
    restart: always
```
Запустите docker-compose:
```bash 
docker-compose up -d
```
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
