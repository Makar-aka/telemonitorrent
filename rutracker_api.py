import requests
from bs4 import BeautifulSoup
import re
import logging

logger = logging.getLogger(__name__)

# Настройка прокси
proxies = None

def set_proxies(proxy_settings):
    global proxies
    proxies = proxy_settings

# Функция для получения содержимого страницы
def get_page_content(url):
    response = requests.get(url, proxies=proxies)
    response.raise_for_status()
    return response.text

# Функция для парсинга даты с страницы
def parse_date(page_content):
    soup = BeautifulSoup(page_content, 'html.parser')
    date_span = soup.find('span', class_='posted_since hide-for-print')
    if date_span:
        date_text = date_span.text
        match = re.search(r'ред\. (\d{2}-\w{3}-\d{2} \d{2}:\d{2})', date_text)
        if match:
            return match.group(1)
    return None

# Функция для получения заголовка страницы
def get_page_title(url):
    page_content = get_page_content(url)
    soup = BeautifulSoup(page_content, 'html.parser')
    title_tag = soup.find('title')
    if title_tag:
        title_text = title_tag.text.split('/')[0].strip()
        return title_text
    return 'No Title'

# Функция для скачивания торрент-файла
def download_torrent_file(url, file_path):
    response = requests.get(url, proxies=proxies)
    response.raise_for_status()
    with open(file_path, 'wb') as file:
        file.write(response.content)
    logger.info(f"Торрент-файл скачан и сохранен в {file_path}")

# Функция для получения даты редактирования с страницы
def get_edit_date(url):
    page_content = get_page_content(url)
    return parse_date(page_content)

