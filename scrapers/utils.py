import re
from urllib.parse import urljoin, urlparse
import logging


class ScrapingUtils:
    @staticmethod
    def extract_fbref_id(url):
        """FBRef URL'sinden oyuncu ID'sini çıkarır"""
        try:
            # URL formatı: https://fbref.com/en/players/e342ad68/Mohamed-Salah
            pattern = r'/players/([a-f0-9]+)/'
            match = re.search(pattern, url)
            return match.group(1) if match else None
        except:
            return None

    @staticmethod
    def clean_text(text):
        """Metin temizleme"""
        if not text:
            return ""
        return re.sub(r'\s+', ' ', text.strip())

    @staticmethod
    def parse_age(age_text):
        """Yaş metnini parse eder (örn: "29-123" -> 29)"""
        try:
            if '-' in age_text:
                return int(age_text.split('-')[0])
            return int(age_text)
        except:
            return 0

    @staticmethod
    def parse_height_weight(height_text, weight_text):
        """Boy ve kilo bilgilerini parse eder"""
        height = ""
        weight = ""

        try:
            if height_text:
                # cm formatında boy (örn: "180cm" veya "5-11")
                if 'cm' in height_text:
                    height = height_text.strip()
                elif '-' in height_text:  # feet-inches formatı
                    parts = height_text.split('-')
                    if len(parts) == 2:
                        feet = int(parts[0])
                        inches = int(parts[1])
                        cm = int((feet * 12 + inches) * 2.54)
                        height = f"{cm}cm"

            if weight_text:
                # kg formatında kilo (örn: "75kg" veya "165lb")
                if 'kg' in weight_text:
                    weight = weight_text.strip()
                elif 'lb' in weight_text:
                    lb = int(re.findall(r'\d+', weight_text)[0])
                    kg = int(lb * 0.453592)
                    weight = f"{kg}kg"
        except:
            pass

        return height, weight

    @staticmethod
    def build_full_url(base_url, relative_url):
        """Tam URL oluşturur"""
        return urljoin(base_url, relative_url)

    @staticmethod
    def extract_stat_value(stat_text):
        """İstatistik değerini çıkarır ve sayıya dönüştürür"""
        try:
            if not stat_text or stat_text.strip() == '':
                return 0

            # Virgülleri kaldır (1,234 -> 1234)
            clean_text = stat_text.replace(',', '')

            # Sadece sayı ve nokta karakterlerini al
            number_match = re.search(r'[\d\.]+', clean_text)
            if number_match:
                value = number_match.group()
                return float(value) if '.' in value else int(value)

            return 0
        except:
            return 0

    @staticmethod
    def extract_percentile(percentile_text):
        """Percentile değerini çıkarır"""
        try:
            if not percentile_text:
                return 0

            # "85th" -> 85 formatında dönüştür
            number = re.findall(r'\d+', percentile_text)
            return int(number[0]) if number else 0
        except:
            return 0

    @staticmethod
    def is_valid_player_url(url):
        """Geçerli oyuncu URL'si kontrolü"""
        return bool(re.search(r'/players/[a-f0-9]+/', url))

    @staticmethod
    def get_season_from_url(url):
        """URL'den sezon bilgisini çıkarır"""
        try:
            # Örnek: /2023-2024/
            season_match = re.search(r'/(\d{4}-\d{4})/', url)
            return season_match.group(1) if season_match else "2024-2025"
        except:
            return "2024-2025"


def setup_logging():
    """Logging konfigürasyonu"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('data/logs/scraper.log'),
            logging.StreamHandler()
        ]
    )