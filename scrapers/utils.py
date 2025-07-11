import re
import os
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
        except Exception as e:
            logging.error(f"FBRef ID extraction error: {e}")
            return None

    @staticmethod
    def parse_contract_date(date_text):
        """Gelişmiş kontrat tarihi parsing"""
        try:
            if not date_text:
                return ""

            import re
            from datetime import datetime

            date_str = str(date_text).strip().lower()

            # Çeşitli tarih formatları
            date_formats = [
                # "30 June 2025", "June 30, 2025"
                r'(\d{1,2})\s+(\w+)\s+(\d{4})',
                r'(\w+)\s+(\d{1,2}),?\s+(\d{4})',

                # "30/06/2025", "06/30/2025", "2025/06/30"
                r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})',
                r'(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})',

                # "June 2025", "2025"
                r'(\w+)\s+(\d{4})',
                r'^(\d{4})$'
            ]

            month_names = {
                'january': '01', 'february': '02', 'march': '03', 'april': '04',
                'may': '05', 'june': '06', 'july': '07', 'august': '08',
                'september': '09', 'october': '10', 'november': '11', 'december': '12',
                'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
                'jun': '06', 'jul': '07', 'aug': '08', 'sep': '09',
                'oct': '10', 'nov': '11', 'dec': '12'
            }

            for pattern in date_formats:
                match = re.search(pattern, date_str)
                if match:
                    groups = match.groups()

                    if len(groups) == 1:  # Sadece yıl
                        year = int(groups[0])
                        if 2024 <= year <= 2035:
                            return str(year)

                    elif len(groups) == 2:  # Ay ve yıl
                        month_text, year_text = groups
                        try:
                            year = int(year_text)
                            if year < 2024 or year > 2035:
                                continue

                            # Ay ismini kontrol et
                            if month_text in month_names:
                                return str(year)
                            else:
                                # Sayısal ay olabilir
                                month = int(month_text)
                                if 1 <= month <= 12:
                                    return str(year)
                        except ValueError:
                            continue

                    elif len(groups) == 3:  # Tam tarih
                        try:
                            # Hangi format olduğunu belirle
                            if groups[0].isdigit() and groups[2].isdigit():  # Day Month Year
                                day, month_text, year = groups
                                year = int(year)
                                if year < 2024 or year > 2035:
                                    continue
                                return str(year)
                            elif groups[1].isdigit() and groups[2].isdigit():  # Month Day Year
                                month_text, day, year = groups
                                year = int(year)
                                if year < 2024 or year > 2035:
                                    continue
                                return str(year)
                            else:  # Numeric formats
                                # DD/MM/YYYY or MM/DD/YYYY or YYYY/MM/DD
                                parts = [int(g) for g in groups if g.isdigit()]
                                for part in parts:
                                    if 2024 <= part <= 2035:
                                        return str(part)
                        except ValueError:
                            continue

            return ""

        except Exception as e:
            logging.error(f"Contract date parsing error: {e}")
            return ""

    @staticmethod
    def validate_contract_year(year_text):
        """Kontrat yılının geçerliliğini kontrol eder"""
        try:
            if not year_text:
                return False

            year = int(str(year_text).strip())

            # Mevcut yıldan en az 10 yıl sonrasına kadar geçerli
            from datetime import datetime
            current_year = datetime.now().year

            return current_year <= year <= current_year + 10

        except (ValueError, TypeError):
            return False

    @staticmethod
    def extract_contract_keywords(text):
        """Kontrat ile ilgili anahtar kelimeleri bulur"""
        try:
            if not text:
                return []

            text_lower = str(text).lower()

            contract_keywords = [
                'contract until', 'contract expires', 'contract ends',
                'deal until', 'deal expires', 'deal ends',
                'signed until', 'signed through',
                'expires in', 'expires on', 'expires at',
                'until', 'through', 'till'
            ]

            found_keywords = []
            for keyword in contract_keywords:
                if keyword in text_lower:
                    found_keywords.append(keyword)

            return found_keywords

        except Exception as e:
            logging.error(f"Contract keyword extraction error: {e}")
            return []

    @staticmethod
    def smart_contract_extraction(full_text):
        """Akıllı kontrat bilgisi çıkarma"""
        try:
            if not full_text:
                return ""

            text = str(full_text).lower()

            # Önce kontrat ile ilgili cümleleri bul
            sentences = re.split(r'[.!?]+', text)
            contract_sentences = []

            for sentence in sentences:
                if any(keyword in sentence for keyword in ['contract', 'deal', 'expires', 'until', 'signed']):
                    contract_sentences.append(sentence)

            # Her cümlede yıl ara
            for sentence in contract_sentences:
                years = re.findall(r'\b(20\d{2})\b', sentence)
                for year in years:
                    year_int = int(year)
                    if ScrapingUtils.validate_contract_year(year_int):
                        return year

            # Genel arama
            years = re.findall(r'\b(20\d{2})\b', text)
            for year in years:
                year_int = int(year)
                if ScrapingUtils.validate_contract_year(year_int):
                    # Bu yılın kontrat yılı olma olasılığını kontrol et
                    year_context = text[max(0, text.find(year) - 50):text.find(year) + 50]
                    if any(keyword in year_context for keyword in ['contract', 'deal', 'expires', 'until']):
                        return year

            return ""

        except Exception as e:
            logging.error(f"Smart contract extraction error: {e}")
            return ""

    @staticmethod
    def clean_text(text):
        """Gelişmiş metin temizleme"""
        if not text:
            return ""

        # Unicode karakterleri normalize et
        import unicodedata
        text = unicodedata.normalize('NFKD', str(text))

        # HTML entities'leri decode et
        import html
        text = html.unescape(text)

        # Çoklu whitespace'leri tek space'e çevir
        text = re.sub(r'\s+', ' ', text)

        # Satır başı ve sonundaki boşlukları temizle
        text = text.strip()

        # Gereksiz noktalama işaretlerini temizle (ama bazılarını koru)
        # text = re.sub(r'[^\w\s\-\.\,\(\)\'\"]', '', text)

        return text

    @staticmethod
    def parse_age(age_text):
        """Gelişmiş yaş parsing"""
        try:
            if not age_text:
                return 0

            age_str = str(age_text).strip()

            # "29-123" formatından sadece yaşı al (29-123 formatında 29 yaş, 123 gün)
            if '-' in age_str:
                age_part = age_str.split('-')[0]
            else:
                age_part = age_str

            # "(age 32)" formatını handle et
            age_match = re.search(r'\(age\s+(\d+)\)', age_part)
            if age_match:
                age = int(age_match.group(1))
                if 15 <= age <= 50:
                    return age

            # "Age: 32" formatını handle et
            age_match = re.search(r'age[:\s]+(\d+)', age_part.lower())
            if age_match:
                age = int(age_match.group(1))
                if 15 <= age <= 50:
                    return age

            # Sadece sayıları çıkar
            age_match = re.search(r'(\d+)', age_part)
            if age_match:
                age = int(age_match.group(1))
                # Mantıklı yaş aralığı kontrolü
                if 15 <= age <= 50:
                    return age
                # Eğer çok büyük bir sayı ise (doğum yılı olabilir), yaşa çevir
                elif 1970 <= age <= 2010:
                    from datetime import datetime
                    current_year = datetime.now().year
                    calculated_age = current_year - age
                    if 15 <= calculated_age <= 50:
                        return calculated_age

            return 0
        except Exception as e:
            logging.error(f"Age parsing error: {e}")
            return 0

    @staticmethod
    def parse_height_weight(height_text, weight_text):
        """Gelişmiş boy ve kilo parsing"""
        height = ""
        weight = ""

        try:
            # Boy parsing
            if height_text:
                height_text = str(height_text).lower()

                if 'cm' in height_text:
                    # "180cm" formatı
                    cm_match = re.search(r'(\d+)cm', height_text)
                    if cm_match:
                        height = f"{cm_match.group(1)}cm"
                elif re.match(r'\d+-\d+', height_text):
                    # "5-11" feet-inches formatı
                    parts = height_text.split('-')
                    if len(parts) == 2:
                        try:
                            feet = int(parts[0])
                            inches = int(parts[1])
                            cm = int((feet * 12 + inches) * 2.54)
                            height = f"{cm}cm"
                        except ValueError:
                            pass
                elif re.search(r'\d+', height_text):
                    # Sadece sayı varsa cm olarak kabul et
                    height_match = re.search(r'(\d+)', height_text)
                    if height_match:
                        cm_value = int(height_match.group(1))
                        if 150 <= cm_value <= 220:  # Mantıklı boy aralığı
                            height = f"{cm_value}cm"

            # Kilo parsing
            if weight_text:
                weight_text = str(weight_text).lower()

                if 'kg' in weight_text:
                    # "75kg" formatı
                    kg_match = re.search(r'(\d+)kg', weight_text)
                    if kg_match:
                        weight = f"{kg_match.group(1)}kg"
                elif 'lb' in weight_text:
                    # "165lb" formatı
                    lb_match = re.search(r'(\d+)lb', weight_text)
                    if lb_match:
                        lb_value = int(lb_match.group(1))
                        kg_value = int(lb_value * 0.453592)
                        weight = f"{kg_value}kg"
                elif re.search(r'\d+', weight_text):
                    # Sadece sayı varsa kg olarak kabul et
                    weight_match = re.search(r'(\d+)', weight_text)
                    if weight_match:
                        kg_value = int(weight_match.group(1))
                        if 50 <= kg_value <= 150:  # Mantıklı kilo aralığı
                            weight = f"{kg_value}kg"

        except Exception as e:
            logging.error(f"Height/weight parsing error: {e}")

        return height, weight

    @staticmethod
    def build_full_url(base_url, relative_url):
        """Güvenli URL oluşturma"""
        try:
            if not relative_url:
                return base_url
            return urljoin(base_url, relative_url)
        except Exception as e:
            logging.error(f"URL building error: {e}")
            return base_url

    @staticmethod
    def extract_stat_value(stat_text):
        """Gelişmiş istatistik değeri çıkarma"""
        try:
            if not stat_text or str(stat_text).strip() in ['', '-', '—', 'N/A', 'nan']:
                return 0

            # String'e çevir ve temizle
            clean_text = str(stat_text).replace(',', '').replace('%', '').strip()

            # Negatif değerleri handle et
            is_negative = clean_text.startswith('-')
            if is_negative:
                clean_text = clean_text[1:]

            # Sadece sayı ve nokta karakterlerini al
            number_match = re.search(r'[\d\.]+', clean_text)
            if number_match:
                value_str = number_match.group()
                try:
                    if '.' in value_str:
                        value = float(value_str)
                    else:
                        value = int(value_str)

                    return -value if is_negative else value
                except ValueError:
                    return 0

            return 0
        except Exception as e:
            logging.error(f"Stat extraction error: {e}")
            return 0

    @staticmethod
    def extract_percentile(percentile_text):
        """Gelişmiş percentile çıkarma"""
        try:
            if not percentile_text:
                return 0

            # "85th", "85%", "85" formatlarını handle et
            clean_text = str(percentile_text).lower().replace('th', '').replace('%', '').strip()

            number_match = re.search(r'\d+', clean_text)
            if number_match:
                percentile = int(number_match.group())
                # Percentile 0-100 arasında olmalı
                if 0 <= percentile <= 100:
                    return percentile

            return 0
        except Exception as e:
            logging.error(f"Percentile extraction error: {e}")
            return 0

    @staticmethod
    def is_valid_player_url(url):
        """Gelişmiş URL validasyonu"""
        try:
            if not url:
                return False

            # FBRef player URL pattern'i kontrol et
            pattern = r'fbref\.com.*?/players/[a-f0-9]+/'
            return bool(re.search(pattern, url))
        except Exception:
            return False

    @staticmethod
    def get_season_from_url(url):
        """URL'den sezon bilgisini güvenli şekilde çıkar"""
        try:
            # Örnek: /2023-2024/ veya /2024-25/
            season_patterns = [
                r'/(\d{4}-\d{4})/',
                r'/(\d{4}-\d{2})/',
                r'season=(\d{4}-\d{4})',
                r'season=(\d{4}-\d{2})'
            ]

            for pattern in season_patterns:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)

            # Default current season
            return "2024-2025"
        except Exception:
            return "2024-2025"

    @staticmethod
    def safe_find_text(element, default=""):
        """BeautifulSoup element'ten güvenli text çıkarma"""
        try:
            if element and hasattr(element, 'text'):
                return ScrapingUtils.clean_text(element.text)
            return default
        except Exception:
            return default

    @staticmethod
    def safe_get_attribute(element, attribute, default=""):
        """Element attribute'unu güvenli şekilde al"""
        try:
            if element and hasattr(element, 'get'):
                return element.get(attribute, default)
            return default
        except Exception:
            return default


def setup_logging():
    """Gelişmiş logging konfigürasyonu"""
    try:
        # Log dizinini oluştur
        log_dir = 'data/logs'
        os.makedirs(log_dir, exist_ok=True)

        # Log formatı
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

        # Handlers
        handlers = [
            logging.StreamHandler(),  # Console output
        ]

        # File handler (sadece dizin varsa)
        log_file = os.path.join(log_dir, 'scraper.log')
        try:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(logging.Formatter(log_format))
            handlers.append(file_handler)
        except Exception as e:
            print(f"Warning: Could not create log file: {e}")

        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=handlers,
            force=True  # Override existing configuration
        )

        # Set specific loggers to WARNING to reduce noise
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('selenium').setLevel(logging.WARNING)
        logging.getLogger('webdriver_manager').setLevel(logging.WARNING)

    except Exception as e:
        print(f"Logging setup failed: {e}")
        # Fallback to basic console logging
        logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')