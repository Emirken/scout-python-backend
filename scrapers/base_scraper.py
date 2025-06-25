import requests
from bs4 import BeautifulSoup
import time
import logging
import random
from fake_useragent import UserAgent
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config.settings import Settings


class BaseScraper:
    def __init__(self, use_selenium=False):
        self.session = requests.Session()
        self.ua = UserAgent()
        self.use_selenium = use_selenium
        self.driver = None

        # Enhanced headers to avoid detection
        self.session.headers.update({
            'User-Agent': self.ua.chrome,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        })

        # Configure session to handle cookies and redirects
        self.session.max_redirects = 5

        if use_selenium:
            self.setup_selenium()

    def setup_selenium(self):
        """Enhanced Selenium WebDriver setup with anti-detection"""
        chrome_options = Options()

        # Basic options
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--start-maximized')

        # Anti-detection options
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-images')
        chrome_options.add_argument('--disable-javascript')
        chrome_options.add_argument('--no-first-run')
        chrome_options.add_argument('--no-default-browser-check')
        chrome_options.add_argument('--disable-default-apps')

        # User agent
        chrome_options.add_argument(f'--user-agent={self.ua.chrome}')

        # Additional anti-detection
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # Proxy rotation (optional - uncomment if you have proxies)
        # proxies = ['proxy1:port', 'proxy2:port']
        # proxy = random.choice(proxies)
        # chrome_options.add_argument(f'--proxy-server={proxy}')

        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)

            # Execute script to remove webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        except Exception as e:
            logging.error(f"Selenium setup failed: {e}")
            self.driver = None

    def get_page(self, url, use_selenium=None, max_retries=3):
        """Enhanced page fetching with retry logic"""
        for attempt in range(max_retries):
            try:
                if use_selenium or (use_selenium is None and self.use_selenium):
                    result = self.get_page_selenium(url)
                else:
                    result = self.get_page_requests(url)

                if result:
                    return result

                # If failed, wait before retry
                if attempt < max_retries - 1:
                    wait_time = random.uniform(5, 10) * (attempt + 1)
                    logging.warning(f"Attempt {attempt + 1} failed, waiting {wait_time:.1f}s before retry")
                    time.sleep(wait_time)

            except Exception as e:
                logging.error(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(3, 7))

        return None

    def get_page_requests(self, url):
        """Enhanced requests with better error handling"""
        try:
            # Rotate user agent for each request
            self.session.headers['User-Agent'] = self.ua.chrome

            # Add referer for better legitimacy
            if 'fbref.com' in url:
                self.session.headers['Referer'] = 'https://fbref.com/'

            # Random delay before request
            time.sleep(random.uniform(2, 5))

            response = self.session.get(
                url,
                timeout=Settings.REQUEST_TIMEOUT,
                allow_redirects=True
            )

            # Check for different error codes
            if response.status_code == 403:
                logging.warning(f"403 Forbidden - trying Selenium for: {url}")
                return self.get_page_selenium(url) if not self.use_selenium else None
            elif response.status_code == 429:
                logging.warning(f"Rate limited - waiting longer")
                time.sleep(random.uniform(10, 20))
                return None
            elif response.status_code != 200:
                logging.error(f"HTTP {response.status_code} for: {url}")
                return None

            return BeautifulSoup(response.content, 'html.parser')

        except requests.exceptions.RequestException as e:
            logging.error(f"Request error for {url}: {e}")
            return None

    def get_page_selenium(self, url):
        """Enhanced Selenium page fetching"""
        try:
            if not self.driver:
                self.setup_selenium()
                if not self.driver:
                    return None

            # Navigate to page
            self.driver.get(url)

            # Wait for page to load
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except:
                pass  # Continue even if wait fails

            # Random delay to mimic human behavior
            time.sleep(random.uniform(3, 7))

            # Scroll to simulate reading
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(random.uniform(1, 3))
            self.driver.execute_script("window.scrollTo(0, 0);")

            return BeautifulSoup(self.driver.page_source, 'html.parser')

        except Exception as e:
            logging.error(f"Selenium error for {url}: {e}")
            return None

    def close(self):
        """Clean up resources"""
        try:
            if self.driver:
                self.driver.quit()
            if self.session:
                self.session.close()
        except Exception as e:
            logging.error(f"Error closing resources: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()