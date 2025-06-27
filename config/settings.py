import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # MongoDB ayarları
    MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
    MONGODB_DB_NAME = os.getenv('MONGODB_DB_NAME', 'ScoutDatabase')
    MONGODB_COLLECTION = os.getenv('MONGODB_COLLECTION', 'players')

    # FBRef ayarları
    FBREF_BASE_URL = os.getenv('FBREF_BASE_URL', 'https://fbref.com')

    # Enhanced scraping ayarları
    SCRAPING_DELAY = int(os.getenv('SCRAPING_DELAY', 3))  # Increased delay
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', 30))
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', 3))

    # Rate limiting
    MIN_DELAY = float(os.getenv('MIN_DELAY', 2.0))
    MAX_DELAY = float(os.getenv('MAX_DELAY', 5.0))
    ERROR_DELAY = float(os.getenv('ERROR_DELAY', 10.0))

    # Enhanced headers with more realistic values
    HEADERS = {
        'User-Agent': os.getenv('USER_AGENT',
                                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
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
    }

    # Selenium ayarları
    USE_SELENIUM_FALLBACK = os.getenv('USE_SELENIUM_FALLBACK', 'true').lower() == 'true'
    HEADLESS_BROWSER = False  # Debug için görüntülü mod
    SELENIUM_TIMEOUT = 30

    # Proxy settings (optional)
    PROXY_LIST = os.getenv('PROXY_LIST', '').split(',') if os.getenv('PROXY_LIST') else []
    USE_PROXY_ROTATION = len(PROXY_LIST) > 0

    # Error handling
    MAX_CONSECUTIVE_ERRORS = int(os.getenv('MAX_CONSECUTIVE_ERRORS', 5))
    EXPONENTIAL_BACKOFF = os.getenv('EXPONENTIAL_BACKOFF', 'true').lower() == 'true'

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_TO_FILE = os.getenv('LOG_TO_FILE', 'true').lower() == 'true'

    @classmethod
    def get_random_delay(cls):
        """Get a random delay between min and max delay"""
        import random
        return random.uniform(cls.MIN_DELAY, cls.MAX_DELAY)

    @classmethod
    def get_error_delay(cls, attempt=1):
        """Get exponential backoff delay for errors"""
        if cls.EXPONENTIAL_BACKOFF:
            return cls.ERROR_DELAY * (2 ** (attempt - 1))
        return cls.ERROR_DELAY

    @classmethod
    def get_random_user_agent(cls):
        """Get a random user agent"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        import random
        return random.choice(user_agents)