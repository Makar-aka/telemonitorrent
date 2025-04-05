import os
import requests
import re
import logging
from bs4 import BeautifulSoup
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class RutrackerAPI:
    """
    Класс для взаимодействия с API RuTracker
    """
    def __init__(self, username, password):
        """
        Инициализирует сессию и параметры для работы с RuTracker
        
        Args:
            username (str): Имя пользователя для авторизации
            password (str): Пароль для авторизации
        """
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.base_url = "https://rutracker.org/forum/"
        self.logged_in = False
        self.proxies = self.setup_proxies()
        
        # Стандартные заголовки для запросов
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def setup_proxies(self):
        """
        Настраивает и проверяет прокси-серверы, если они указаны в переменных окружения
        
        Returns:
            dict or None: Словарь с настройками прокси или None
        """
        if os.getenv('USE_PROXY', 'false').lower() == 'true':
            http_proxy = os.getenv('HTTP_PROXY')
            https_proxy = os.getenv('HTTPS_PROXY')
            
            if not http_proxy or not https_proxy:
                logger.error("Не настроены прокси-серверы")
                return None
                
            proxies = {
                "http": http_proxy,
                "https": https_proxy
            }
            
            if not all(self.validate_proxy(proxy) for proxy in proxies.values()):
                logger.error("Некорректные настройки прокси")
                return None
                
            logger.info("Использование прокси настроено успешно")
            return proxies
            
        return None

    def validate_proxy(self, proxy_url):
        """
        Проверяет работоспособность прокси
        
        Args:
            proxy_url (str): URL прокси-сервера
            
        Returns:
            bool: True если прокси работает, иначе False
        """
        try:
            requests.get("http://httpbin.org/ip", proxies={"http": proxy_url}, timeout=5)
            return True
        except Exception as e:
            logger.error(f"Ошибка при проверке прокси {proxy_url}: {e}")
            return False

    def login(self):
        """
        Выполняет вход на сайт
        
        Returns:
            bool: True если вход выполнен успешно, иначе False
        """
        # Если уже выполнен вход, повторно не логинимся
        if self.logged_in:
            return True

        login_url = self.base_url + "login.php"
        payload = {
            "login_username": self.username,
            "login_password": self.password,
            "login": "вход"
        }

        try:
            response = self.session.post(login_url, data=payload, headers=self.headers, proxies=self.proxies)
            response.raise_for_status()  # Проверяем статус ответа
            
            self.logged_in = "logged-in" in response.text or "logout" in response.text
            
            if self.logged_in:
                logger.info("Успешная авторизация на RuTracker")
            else:
                logger.error("Не удалось авторизоваться на RuTracker")
                
            return self.logged_in
        except Exception as e:
            logger.error(f"Ошибка при авторизации: {e}")
            return False

    def get_page_content(self, url):
        """
        Получает содержимое страницы
        
        Args:
            url (str): URL страницы
            
        Returns:
            str or None: HTML-код страницы или None в случае ошибки
        """
        try:
            if not self.login():
                logger.error("Не удалось получить страницу: не выполнен вход")
                return None
                
            response = self.session.get(url, headers=self.headers, proxies=self.proxies)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Ошибка при получении страницы {url}: {e}")
            return None

    def parse_date(self, page_content):
        """
        Извлекает дату обновления из содержимого страницы
        
        Args:
            page_content (str): HTML-код страницы
            
        Returns:
            str or None: Дата обновления или None, если не найдена
        """
        if not page_content:
            return None
            
        try:
            soup = BeautifulSoup(page_content, 'html.parser')
            date_span = soup.find('span', class_='posted_since hide-for-print')
            if date_span:
                date_text = date_span.text
                match = re.search(r'ред\. (\d{2}-\w{3}-\d{2} \d{2}:\d{2})', date_text)
                if match:
                    return match.group(1)
        except Exception as e:
            logger.error(f"Ошибка при парсинге даты: {e}")
            
        return None

    def get_page_title(self, url):
        """
        Извлекает заголовок страницы
        
        Args:
            url (str): URL страницы
            
        Returns:
            str: Заголовок страницы или 'No Title' в случае ошибки
        """
        try:
            page_content = self.get_page_content(url)
            if page_content:
                soup = BeautifulSoup(page_content, 'html.parser')
                title_tag = soup.find('title')
                if title_tag:
                    title_text = title_tag.text.split('/')[0].strip()
                    return title_text
        except Exception as e:
            logger.error(f"Ошибка при получении заголовка страницы {url}: {e}")
            
        return 'No Title'

    def get_edit_date(self, url):
        """
        Получает дату обновления страницы
        
        Args:
            url (str): URL страницы
            
        Returns:
            str or None: Дата обновления или None
        """
        page_content = self.get_page_content(url)
        return self.parse_date(page_content)

    def download_torrent_by_url(self, page_url, file_path):
        """
        Скачивает торрент-файл по URL страницы
        
        Args:
            page_url (str): URL страницы с торрентом
            file_path (str): Путь для сохранения торрент-файла
            
        Returns:
            str or None: Путь к файлу или None в случае ошибки
        """
        try:
            if not self.login():
                logger.error("Не удалось скачать торрент: не выполнен вход")
                return None

            # Получаем страницу с торрентом
            response = self.session.get(page_url, headers=self.headers, proxies=self.proxies)
            response.raise_for_status()

            # Ищем ссылку на скачивание
            soup = BeautifulSoup(response.text, "html.parser")
            download_link_element = soup.select_one("a[href*='dl.php?t=']")
            if not download_link_element:
                logger.error(f"Ссылка на загрузку торрента не найдена для {page_url}")
                return None

            # Скачиваем торрент-файл
            download_url = self.base_url + download_link_element["href"]
            torrent_response = self.session.get(download_url, headers=self.headers, proxies=self.proxies, stream=True)
            torrent_response.raise_for_status()
            
            # Создаем директорию, если не существует
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            
            # Сохраняем файл
            with open(file_path, 'wb') as file:
                for chunk in torrent_response.iter_content(chunk_size=8192):
                    file.write(chunk)
                    
            logger.info(f"Торрент-файл скачан и сохранен в {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Ошибка при загрузке торрента по ссылке {page_url}: {e}")
            return None
            
    def close(self):
        """
        Закрывает сессию
        """
        try:
            self.session.close()
            logger.debug("Сессия RutrackerAPI закрыта")
        except Exception as e:
            logger.error(f"Ошибка при закрытии сессии: {e}")
            
    def __enter__(self):
        """
        Поддержка контекстного менеджера
        """
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Закрытие ресурсов при выходе из контекстного менеджера
        """
        self.close()
