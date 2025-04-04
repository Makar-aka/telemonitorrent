import requests
from bs4 import BeautifulSoup
import re
import logging

logger = logging.getLogger(__name__)

# ��������� ������
proxies = None

def set_proxies(proxy_settings):
    global proxies
    proxies = proxy_settings

# ������� ��� ��������� ����������� ��������
def get_page_content(url):
    response = requests.get(url, proxies=proxies)
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

# ������� ��� ��������� ��������� ��������
def get_page_title(url):
    page_content = get_page_content(url)
    soup = BeautifulSoup(page_content, 'html.parser')
    title_tag = soup.find('title')
    if title_tag:
        title_text = title_tag.text.split('/')[0].strip()
        return title_text
    return 'No Title'

# ������� ��� ���������� �������-�����
def download_torrent_file(url, file_path):
    response = requests.get(url, proxies=proxies)
    response.raise_for_status()
    with open(file_path, 'wb') as file:
        file.write(response.content)
    logger.info(f"�������-���� ������ � �������� � {file_path}")
