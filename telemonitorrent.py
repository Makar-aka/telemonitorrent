import os
import sqlite3
import requests
from bs4 import BeautifulSoup
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from dotenv import load_dotenv
import schedule
import time
from threading import Thread

# �������� ���������� ��������� �� ����� .env
load_dotenv()
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 10))
BOT_TOKEN = os.getenv('BOT_TOKEN')

# ���� � ���� ������ SQLite
db_path = 'database.db'

# ������� ��� ������������� ���� ������
def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS pages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT,
                        url TEXT,
                        date TEXT)''')
    conn.commit()
    conn.close()

# ������� ��� ���������� �������� � ���� ������
def add_page(title, url):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO pages (title, url) VALUES (?, ?)", (title, url))
    conn.commit()
    conn.close()

# ������� ��� ��������� ������ ������� �� ���� ������
def get_pages():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, url, date FROM pages")
    pages = cursor.fetchall()
    conn.close()
    return pages

# ������� ��� ���������� ������ �������� � ���� ������
def update_page_url(page_id, new_url):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE pages SET url = ? WHERE id = ?", (new_url, page_id))
    conn.commit()
    conn.close()

# ������� ��� ���������� ���� �������� � ���� ������
def update_page_date(page_id, new_date):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE pages SET date = ? WHERE id = ?", (new_date, page_id))
    conn.commit()
    conn.close()

# ������� ��� ��������� ����������� ��������
def get_page_content(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.text

# ������� ��� �������� ���� � ��������
def parse_date(page_content):
    soup = BeautifulSoup(page_content, 'html.parser')
    date_span = soup.find('span', class_='posted_since hide-for-print')
    if date_span:
        date_text = date_span.text
        match = re.search(r'���\. (\d{2}-\w{3}-\d{2} \d{2}:\d{2})', date_text)
        if match:
            return match.group(1)
    return None

# ������� ��� ���������� �������-�����
def download_torrent_file(url, file_path):
    response = requests.get(url)
    response.raise_for_status()
    with open(file_path, 'wb') as file:
        file.write(response.content)

# ������� ��� �������� ��������� �� ���������
def check_pages():
    pages = get_pages()
    for page in pages:
        page_id, title, url, old_date = page
        page_content = get_page_content(url)
        new_date = parse_date(page_content)
        if new_date and new_date != old_date:
            torrent_url = 'URL_�������_�����'  # �������� �� URL �������-�����
            torrent_file_path = f'torrents/{page_id}.torrent'  # �������� �� ���� � �������-�����
            download_torrent_file(torrent_url, torrent_file_path)
            update_page_date(page_id, new_date)
            print(f"���� ��� �������� {title} ��������� � �������-���� ������.")

# ���������� ������� /start
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('������! ����������� /add <������> ��� ���������� �������� � /list ��� ��������� �������.')

# ���������� ������� /add
def add(update: Update, context: CallbackContext) -> None:
    if len(context.args) != 1:
        update.message.reply_text('�������������: /add <������>')
        return

    url = context.args[0]
    title = 'Title'  # ����� ����� �������� ������ ��� ��������� ��������� ��������
    add_page(title, url)
    update.message.reply_text(f'�������� {title} ��������� ��� �����������.')

# ���������� ������� /list
def list_pages(update: Update, context: CallbackContext) -> None:
    pages = get_pages()
    if not pages:
        update.message.reply_text('��� ������� ��� �����������.')
        return

    keyboard = [[InlineKeyboardButton(page[1], callback_data=str(page[0]))] for page in pages]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('�������� ��� �����������:', reply_markup=reply_markup)

# ���������� ������� �� ������
def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    page_id = int(query.data)
    query.edit_message_text(text=f'�� ������� �������� � ID {page_id}. ����������� /update <������> ��� ����������.')

# ���������� ������� /update
def update_page(update: Update, context: CallbackContext) -> None:
    if len(context.args) != 2:
        update.message.reply_text('�������������: /update <ID> <������>')
        return

    page_id = int(context.args[0])
    new_url = context.args[1]
    update_page_url(page_id, new_url)
    update.message.reply_text(f'������ ��� �������� � ID {page_id} ���������.')

def main() -> None:
    # ������������� ���� ������
    init_db()

    # �������� ������� Updater � �������� ��� ������ ������ ����
    updater = Updater(BOT_TOKEN)

    # ��������� ���������� ��� ����������� ������������
    dispatcher = updater.dispatcher

    # ����������� ������������ ������
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("add", add))
    dispatcher.add_handler(CommandHandler("list", list_pages))
    dispatcher.add_handler(CommandHandler("update", update_page))
    dispatcher.add_handler(CallbackQueryHandler(button))

    # ������ ������������ �����
    schedule.every(CHECK_INTERVAL).minutes.do(check_pages)

    def run_schedule():
        while True:
            schedule.run_pending()
            time.sleep(1)

    # ������ ������������ � ��������� ������
    schedule_thread = Thread(target=run_schedule)
    schedule_thread.start()

    # ������ ����
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
