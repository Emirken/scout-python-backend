import requests
from bs4 import BeautifulSoup
import time
import logging
from fake_useragent import UserAgent
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from config.settings import Settings


class BaseScraper:
    def __init__(self, use_selenium=False):
        self.session = requests.Session()
        self.ua = UserAgent()
        self.use_selenium = use_selenium
        self.driver = None

        # Requests için headers ayarla
        self.session.headers.update(Settings.HEADERS)

        if use_selenium:
            self.setup_selenium()

    def setup_selenium(self):
        """Selenium WebDriver'ı kurar"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument(f'--user-agent={self.ua.random}')

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)

    def get_page(self, url, use_selenium=None):
        """Sayfa içeriğini getirir"""
        if use_selenium or (use_selenium is None and self.use_selenium):
            return self.get_page_selenium(url)
        else:
            return self.get_page_requests(url)

    def get_page_requests(self, url):
        """Requests ile sayfa getirir"""
        try:
            # User-Agent'ı rastgele değiştir
            self.session.headers['User-Agent'] = self.ua.random

            response = self.session.get(url, timeout=Settings.REQUEST_TIMEOUT)
            response.raise_for_status()

            # Bekleme süresi
            time.sleep(Settings.SCRAPING_DELAY)

            return BeautifulSoup(response.content, 'html.parser')

        except requests.RequestException as e:
            logging.error(f"Sayfa getirme hatası ({url}): {e}")
            return None

    def get_page_selenium(self, url):
        """Selenium ile sayfa getirir"""
        try:
            if not self.driver:
                self.setup_selenium()

            self.driver.get(url)
            time.sleep(Settings.SCRAPING_DELAY)

            return BeautifulSoup(self.driver.page_source, 'html.parser')

        except Exception as e:
            logging.error(f"Selenium sayfa getirme hatası ({url}): {e}")
            return None

    def close(self):
        """Kaynakları temizler"""
        if self.driver:
            self.driver.quit()
        self.session.close()