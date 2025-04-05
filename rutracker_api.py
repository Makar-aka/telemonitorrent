import os
import requests
import re
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class RutrackerAPI:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.base_url = "https://rutracker.org/forum/"
        self.logged_in = False
        self.proxies = self.setup_proxies()

    def setup_proxies(self):
        if os.getenv('USE_PROXY', 'false').lower() == 'true':
            proxies = {
                "http": os.getenv('HTTP_PROXY'),
                "https": os.getenv('HTTPS_PROXY')
            }
            if not all(proxies.values()):
                logger.error("Не настроены прокси-серверы")
                return None
            if not all(self.validate_proxy(proxy) for proxy in proxies.values()):
                logger.error("Некорректные настройки прокси")
                return None
            return proxies
        return None

    def validate_proxy(self, proxy_url):
        try:
            requests.get("http://httpbin.org/ip", proxies={"http": proxy_url}, timeout=5)
            return True
        except Exception as e:
            logger.error(f"Ошибка при проверке прокси {proxy_url}: {e}")
            return False

    def make_request(self, method, endpoint, **kwargs):
        url = self.base_url + endpoint
        return self.session.request(method, url, proxies=self.proxies, **kwargs)

    def login(self):
        if self.logged_in:
            return True

        login_url = self.base_url + "login.php"
        payload = {
            "login_username": self.username,
            "login_password": self.password,
            "login": "вход"
        }
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        try:
            response = self.session.post(login_url, data=payload, headers=headers, proxies=self.proxies)
            self.logged_in = "logged-in" in response.text or "logout" in response.text
            return self.logged_in
        except Exception as e:
            logger.error(f"Ошибка при авторизации: {e}")
            return False

    def get_page_content(self, url):
        if not self.login():
            return None
        response = self.session.get(url, proxies=self.proxies)
        response.raise_for_status()
        return response.text

    def parse_date(self, page_content):
        soup = BeautifulSoup(page_content, 'html.parser')
        date_span = soup.find('span', class_='posted_since hide-for-print')
        if date_span:
            date_text = date_span.text
            match = re.search(r'ред\. (\d{2}-\w{3}-\d{2} \d{2}:\d{2})', date_text)
            if match:
                return match.group(1)
        return None

    def get_page_title(self, url):
        page_content = self.get_page_content(url)
        if page_content:
            soup = BeautifulSoup(page_content, 'html.parser')
            title_tag = soup.find('title')
            if title_tag:
                title_text = title_tag.text.split('/')[0].strip()
                return title_text
        return 'No Title'

    def download_torrent_file(self, url, file_path):
        if not self.login():
            return None
        response = self.session.get(url, proxies=self.proxies)
        response.raise_for_status()
        with open(file_path, 'wb') as file:
            file.write(response.content)
        logger.info(f"Торрент-файл скачан и сохранен в {file_path}")

    def get_edit_date(self, url):
        page_content = self.get_page_content(url)
        return self.parse_date(page_content)

    def download_torrent_by_url(self, page_url, file_path):
        if not self.login():
            return None

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        try:
            response = self.session.get(page_url, headers=headers, proxies=self.proxies)
            if response.status_code != 200:
                logger.error(f"Ошибка при загрузке страницы: {response.status_code}")
                return None

            soup = BeautifulSoup(response.text, "html.parser")
            download_link_element = soup.select_one("a[href*='dl.php?t=']")
            if not download_link_element:
                logger.error("Ссылка на загрузку торрента не найдена")
                return None

            download_url = self.base_url + download_link_element["href"]
            torrent_response = self.session.get(download_url, headers=headers, proxies=self.proxies, stream=True)
            if torrent_response.status_code == 200:
                with open(file_path, 'wb') as file:
                    for chunk in torrent_response.iter_content(chunk_size=8192):
                        file.write(chunk)
                logger.info(f"Торрент-файл скачан и сохранен в {file_path}")
                return file_path
            else:
                logger.error(f"Ошибка при загрузке торрента: {torrent_response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Ошибка при загрузке торрента по ссылке: {e}")
            return None



