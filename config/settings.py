import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # MongoDB ayarları
    MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
    MONGODB_DB_NAME = os.getenv('MONGODB_DB_NAME', 'football_database')
    MONGODB_COLLECTION = os.getenv('MONGODB_COLLECTION', 'players')

    # FBRef ayarları
    FBREF_BASE_URL = os.getenv('FBREF_BASE_URL', 'https://fbref.com')

    # Scraping ayarları
    SCRAPING_DELAY = int(os.getenv('SCRAPING_DELAY', 2))
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', 30))

    # Headers
    HEADERS = {
        'User-Agent': os.getenv('USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }