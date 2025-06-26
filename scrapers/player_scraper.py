# scrapers/player_scraper.py
import logging
from .base_scraper import BaseScraper
from .utils import ScrapingUtils
from config.settings import Settings
from config.leagues import LEAGUE_COUNTRIES, LEAGUES
from models.player import PlayerModel
import re
from urllib.parse import urljoin


class PlayerScraper(BaseScraper):
    def __init__(self):
        super().__init__(use_selenium=False)
        self.utils = ScrapingUtils()

    def scrape_player_details(self, player_url, basic_info=None):
        """Oyuncu detay sayfasından tüm bilgileri çeker"""
        logging.info(f"Oyuncu detayları çekiliyor: {player_url}")

        # PlayerModel oluştur
        player = PlayerModel()

        # Temel sayfa
        soup = self.get_page(player_url)
        if not soup:
            logging.error(f"Oyuncu sayfası getirilemedi: {player_url}")
            return None

        try:
            # Temel bilgileri çek
            self.extract_basic_info(soup, player, player_url, basic_info)

            # Fiziksel bilgileri çek
            self.extract_physical_info(soup, player)

            # Sezon istatistiklerini çek
            self.extract_season_stats(soup, player)

            # Benzer oyuncuları çek
            self.extract_similar_players(soup, player, player_url)

            # Scouting raporunu çek
            self.extract_scouting_report(player, player_url)

            # Transfer geçmişini çek
            self.extract_transfer_history(soup, player)

            # Zaman damgasını güncelle
            player.update_timestamp()

            # Doğrulama
            is_valid, message = player.validate()
            if not is_valid:
                logging.error(f"Oyuncu verisi geçersiz: {message}")
                return None

            return player.to_dict()

        except Exception as e:
            logging.error(f"Oyuncu detay çekme hatası: {e}")
            return None

    def extract_basic_info(self, soup, player, player_url, basic_info=None):
        """Temel bilgileri çeker - Enhanced contract extraction with full dates"""
        try:
            # FBRef ID
            fbref_id = self.utils.extract_fbref_id(player_url)

            # Oyuncu adı
            name_elem = soup.find('h1')
            full_name = self.utils.clean_text(name_elem.text) if name_elem else ""

            # Initialize variables
            age = 0
            team = ""
            position = ""
            league = ""
            country = ""

            # Enhanced contract end extraction with full date
            contract_end = self.extract_contract_end(soup)

            # Bio tablosu - meta div'den bilgileri çek
            meta_div = soup.find('div', {'id': 'meta'})
            if meta_div:
                # Paragraflardan bilgi çek
                bio_items = meta_div.find_all('p')

                for item in bio_items:
                    text = item.get_text().strip()
                    text_lower = text.lower()

                    # Yaş parsing - daha doğru regex ile
                    if 'born:' in text_lower or 'age:' in text_lower:
                        # "Born: June 15, 1992 (age 32)" formatı
                        age_match = re.search(r'\(age\s+(\d+)\)', text)
                        if not age_match:
                            # "Age: 32" formatı
                            age_match = re.search(r'age[:\s]+(\d+)', text_lower)
                        if not age_match:
                            # Sadece sayı varsa ve mantıklı aralıkta
                            numbers = re.findall(r'\b(\d+)\b', text)
                            for num in numbers:
                                num_int = int(num)
                                if 15 <= num_int <= 45:  # Futbolcu yaş aralığı
                                    age = num_int
                                    break
                        else:
                            age_val = int(age_match.group(1))
                            if 15 <= age_val <= 45:
                                age = age_val

                    # Takım bilgisi - daha geniş arama
                    elif any(keyword in text_lower for keyword in ['club:', 'team:', 'current club:', 'plays for:']):
                        team_link = item.find('a')
                        if team_link:
                            team = self.utils.clean_text(team_link.text)
                        else:
                            # Link yoksa text'ten çıkar
                            team_patterns = [
                                r'club[:\s]+([^,\n]+)',
                                r'team[:\s]+([^,\n]+)',
                                r'plays for[:\s]+([^,\n]+)'
                            ]
                            for pattern in team_patterns:
                                team_match = re.search(pattern, text_lower)
                                if team_match:
                                    team = self.utils.clean_text(team_match.group(1))
                                    break

                    # Pozisyon bilgisi - daha temiz parsing
                    elif 'position:' in text_lower:
                        position_match = re.search(r'position[:\s]+([^,\n]+)', text_lower)
                        if position_match:
                            position_raw = position_match.group(1)
                            # "fw-mf (am-wm, right) footed left" gibi karmaşık metni temizle
                            position = re.sub(r'\s+footed\s+\w+', '', position_raw).strip()
                            position = self.utils.clean_text(position)

            # Takım linkinden lig bilgisini çıkarmaya çalış
            if meta_div:
                team_links = meta_div.find_all('a', href=re.compile(r'/squads/'))
                for team_link in team_links:
                    team_href = team_link.get('href', '')
                    if '/squads/' in team_href:
                        # Takım adını da burada al eğer henüz yoksa
                        if not team:
                            team = self.utils.clean_text(team_link.text)

                        # Lig bilgisini çıkar
                        league = self.extract_league_from_team_url(team_href, soup)
                        if league:
                            break

            # Alternatif: Sayfa içindeki diğer linklerden lig bilgisini bul
            if not league:
                league = self.detect_league_from_page(soup)

            # Basic info'dan gelen veriler varsa kullan (öncelik)
            if basic_info:
                # Sadece boşsa basic_info'dan al
                team = team or basic_info.get('team', '')
                age = age or basic_info.get('age', 0)
                position = position or basic_info.get('position', '')
                league = league or basic_info.get('league', '')
                country = country or basic_info.get('country', '')

            # Ülke bilgisini lig'den çıkar
            if league and not country:
                country = LEAGUE_COUNTRIES.get(league, '')

            # Lig bilgisi hala yoksa takımdan tahmin et
            if not league and team:
                league = self.guess_league_from_team(team)

            # Son kontrollar ve default değerler
            if not league:
                league = "Unknown League"
            if not team:
                team = "Unknown Team"
            if age == 0:
                # Yaş hala 0 ise alternatif yöntemlerle bul
                age = self.extract_age_from_birth_date(soup)

            # Player model'e ayarla
            player.set_basic_info(full_name, age, team, league, fbref_id)
            player.data['detailedPosition'] = position
            player.data['contractEnd'] = contract_end
            player.data['country'] = country

            # Fotoğraf
            self.extract_player_photo(soup, player)

            logging.info(
                f"Temel bilgiler çıkarıldı: {full_name}, {team}, {league}, Yaş: {age}, Kontrat: {contract_end}")

        except Exception as e:
            logging.error(f"Temel bilgi çekme hatası: {e}")

    def extract_contract_end(self, soup):
        """Enhanced contract end extraction with full date format"""
        try:
            contract_end = ""

            # Method 1: Meta div'den kontrat bilgisi - tam tarih formatı
            meta_div = soup.find('div', {'id': 'meta'})
            if meta_div:
                meta_text = meta_div.get_text().lower()

                # Önce tam tarih formatlarını ara
                full_date_patterns = [
                    r'contract\s+until[:\s]+(\w+\s+\d{1,2},?\s+\d{4})',  # "Contract until June 30, 2027"
                    r'expires[:\s]+(\w+\s+\d{1,2},?\s+\d{4})',  # "Expires: June 30, 2027"
                    r'until[:\s]+(\w+\s+\d{1,2},?\s+\d{4})',  # "Until June 30, 2027"
                    r'(\d{1,2}\s+\w+\s+\d{4})',  # "30 June 2027"
                    r'(\w+\s+\d{4})',  # "June 2027"
                ]

                for pattern in full_date_patterns:
                    date_match = re.search(pattern, meta_text)
                    if date_match:
                        date_str = date_match.group(1)
                        formatted_date = self.format_contract_date(date_str)
                        if formatted_date:
                            contract_end = formatted_date
                            break

                # Eğer tam tarih bulunamazsa, sadece yıl ara
                if not contract_end:
                    year_patterns = [
                        r'contract\s+until[:\s]+.*?(\d{4})',
                        r'expires[:\s]+.*?(\d{4})',
                        r'until[:\s]+.*?(\d{4})',
                        r'contract[:\s]+.*?(\d{4})',
                        r'expires\s+in\s+(\d{4})',
                        r'contract\s+ends[:\s]+.*?(\d{4})',
                        r'deal\s+until[:\s]+.*?(\d{4})',
                        r'signed\s+until[:\s]+.*?(\d{4})',
                        r'under\s+contract\s+until[:\s]+.*?(\d{4})'
                    ]

                    for pattern in year_patterns:
                        contract_match = re.search(pattern, meta_text)
                        if contract_match:
                            year = int(contract_match.group(1))
                            if 2024 <= year <= 2035:  # Mantıklı yıl aralığı
                                # Default olarak sezon sonu (30 Haziran) yap
                                contract_end = f"June 30, {year}"
                                break

            # Method 2: Bio paragraflarından detaylı arama
            if not contract_end and meta_div:
                bio_items = meta_div.find_all('p')
                for item in bio_items:
                    item_text = item.get_text().lower()

                    # Daha spesifik arama
                    if any(keyword in item_text for keyword in ['contract', 'expires', 'until', 'deal']):
                        # Tam tarih formatları
                        full_date_patterns = [
                            r'(\w+\s+\d{1,2},?\s+\d{4})',  # "June 30, 2025"
                            r'(\d{1,2}\s+\w+\s+\d{4})',  # "30 June 2025"
                            r'(\w+\s+\d{4})',  # "June 2025"
                        ]

                        for pattern in full_date_patterns:
                            date_match = re.search(pattern, item_text)
                            if date_match:
                                date_str = date_match.group(1)
                                formatted_date = self.format_contract_date(date_str)
                                if formatted_date:
                                    contract_end = formatted_date
                                    break

                        if contract_end:
                            break

                        # Eğer tam tarih bulunamazsa yıl ara
                        year_patterns = [
                            r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})',  # "30/6/2025"
                            r'(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})',  # "2025-06-30"
                            r'(\d{4})'  # Sadece yıl
                        ]

                        for pattern in year_patterns:
                            date_match = re.search(pattern, item_text)
                            if date_match:
                                groups = date_match.groups()
                                if len(groups) == 1:  # Sadece yıl
                                    year = int(groups[0])
                                    if 2024 <= year <= 2035:
                                        contract_end = f"June 30, {year}"
                                        break
                                elif len(groups) == 3:  # Tam tarih
                                    # Format'a göre yıl belirle
                                    if len(groups[0]) == 4:  # YYYY-MM-DD
                                        year = int(groups[0])
                                        month = int(groups[1])
                                        day = int(groups[2])
                                    else:  # DD/MM/YYYY
                                        day = int(groups[0])
                                        month = int(groups[1])
                                        year = int(groups[2])

                                    if 2024 <= year <= 2035:
                                        month_name = self.get_month_name(month)
                                        contract_end = f"{month_name} {day}, {year}"
                                        break

                        if contract_end:
                            break

            # Method 3: Tablo verilerinden kontrat bilgisi
            if not contract_end:
                tables = soup.find_all('table')
                for table in tables:
                    rows = table.find_all('tr')
                    for row in rows:
                        row_text = row.get_text().lower()
                        if 'contract' in row_text or 'expires' in row_text:
                            # Tam tarih ara
                            date_patterns = [
                                r'(\w+\s+\d{1,2},?\s+\d{4})',
                                r'(\d{1,2}\s+\w+\s+\d{4})',
                                r'(\d{4})'
                            ]

                            for pattern in date_patterns:
                                date_match = re.search(pattern, row_text)
                                if date_match:
                                    date_str = date_match.group(1)
                                    if date_str.isdigit():  # Sadece yıl
                                        year = int(date_str)
                                        if 2024 <= year <= 2035:
                                            contract_end = f"June 30, {year}"
                                            break
                                    else:  # Tam tarih
                                        formatted_date = self.format_contract_date(date_str)
                                        if formatted_date:
                                            contract_end = formatted_date
                                            break

                            if contract_end:
                                break
                    if contract_end:
                        break

            # Method 4: Smart contract extraction using utils
            if not contract_end:
                all_text = soup.get_text()
                year_only = self.utils.smart_contract_extraction(all_text)
                if year_only:
                    contract_end = f"June 30, {year_only}"

            # Method 5: Son çare - yaş ve takıma göre tahmin
            if not contract_end:
                try:
                    # Yaş bilgisini al
                    age = self.extract_age_from_birth_date(soup)
                    if age == 0:
                        # Yaş bilgisini meta'dan al
                        meta_div = soup.find('div', {'id': 'meta'})
                        if meta_div:
                            age_match = re.search(r'age\s+(\d+)', meta_div.get_text().lower())
                            if age_match:
                                age = int(age_match.group(1))

                    # Yaşa göre muhtemel kontrat sonu tahmini
                    if age > 0:
                        from datetime import datetime
                        current_year = datetime.now().year

                        if age < 25:  # Genç oyuncu
                            contract_end = f"June 30, {current_year + 3}"  # 3 yıllık kontrat
                        elif age < 30:  # Olgun oyuncu
                            contract_end = f"June 30, {current_year + 2}"  # 2 yıllık kontrat
                        elif age < 35:  # Deneyimli oyuncu
                            contract_end = f"June 30, {current_year + 1}"  # 1 yıllık kontrat
                        else:  # Veteran
                            contract_end = f"June 30, {current_year + 1}"  # Kısa vadeli

                except Exception as e:
                    logging.error(f"Kontrat tahmini hatası: {e}")

            return contract_end

        except Exception as e:
            logging.error(f"Kontrat çıkarma hatası: {e}")
            return ""

    def format_contract_date(self, date_str):
        """Kontrat tarihini standart formata çevirir"""
        try:
            import re
            from datetime import datetime

            date_str = str(date_str).strip()

            # Ay isimlerini sayıya çevir
            month_names = {
                'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
                'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6, 'jul': 7,
                'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }

            month_num_to_name = {
                1: 'January', 2: 'February', 3: 'March', 4: 'April', 5: 'May', 6: 'June',
                7: 'July', 8: 'August', 9: 'September', 10: 'October', 11: 'November', 12: 'December'
            }

            # Farklı formatları parse et
            patterns = [
                r'(\w+)\s+(\d{1,2}),?\s+(\d{4})',  # "June 30, 2027" or "June 30 2027"
                r'(\d{1,2})\s+(\w+)\s+(\d{4})',  # "30 June 2027"
                r'(\w+)\s+(\d{4})',  # "June 2027"
                r'^(\d{4})$'  # "2027"
            ]

            for pattern in patterns:
                match = re.search(pattern, date_str.lower())
                if match:
                    groups = match.groups()

                    if len(groups) == 1:  # Sadece yıl
                        year = int(groups[0])
                        if 2024 <= year <= 2035:
                            return f"June 30, {year}"  # Default: sezon sonu

                    elif len(groups) == 2:  # Ay ve yıl
                        month_text, year_text = groups
                        year = int(year_text)
                        if 2024 <= year <= 2035:
                            if month_text in month_names:
                                month_name = month_text.capitalize()
                                return f"{month_name} 30, {year}"  # Default: ayın 30'u

                    elif len(groups) == 3:  # Tam tarih
                        if groups[0].isdigit():  # "30 June 2027"
                            day, month_text, year = groups
                            day = int(day)
                            year = int(year)
                            if month_text in month_names and 2024 <= year <= 2035:
                                month_name = month_text.capitalize()
                                return f"{month_name} {day}, {year}"
                        else:  # "June 30, 2027"
                            month_text, day, year = groups
                            day = int(day)
                            year = int(year)
                            if month_text in month_names and 2024 <= year <= 2035:
                                month_name = month_text.capitalize()
                                return f"{month_name} {day}, {year}"

            return ""

        except Exception as e:
            logging.error(f"Tarih formatı hatası: {e}")
            return ""

    def get_month_name(self, month_num):
        """Ay numarasını ay ismine çevirir"""
        try:
            month_names = {
                1: 'January', 2: 'February', 3: 'March', 4: 'April', 5: 'May', 6: 'June',
                7: 'July', 8: 'August', 9: 'September', 10: 'October', 11: 'November', 12: 'December'
            }
            return month_names.get(month_num, 'June')  # Default: June
        except:
            return 'June'

    def extract_age_from_birth_date(self, soup):
        """Doğum tarihinden yaş hesaplar"""
        try:
            from datetime import datetime

            # Doğum tarihi bilgisini ara
            meta_div = soup.find('div', {'id': 'meta'})
            if not meta_div:
                return 0

            text = meta_div.get_text()

            # Çeşitli doğum tarihi formatları
            birth_patterns = [
                r'born[:\s]+\w+\s+(\d{1,2}),\s+(\d{4})',  # "Born: June 15, 1992"
                r'(\d{1,2})\s+\w+\s+(\d{4})',  # "15 June 1992"
                r'(\d{4})-(\d{1,2})-(\d{1,2})',  # "1992-06-15"
            ]

            current_year = datetime.now().year

            for pattern in birth_patterns:
                matches = re.findall(pattern, text.lower())
                for match in matches:
                    try:
                        if len(match) == 2:  # month day, year format
                            birth_year = int(match[1])
                        elif len(match) == 3:  # year-month-day format
                            birth_year = int(match[0])
                        else:
                            continue

                        age = current_year - birth_year
                        if 15 <= age <= 45:  # Mantıklı yaş aralığı
                            return age
                    except (ValueError, IndexError):
                        continue

            return 0
        except Exception as e:
            logging.error(f"Doğum tarihinden yaş hesaplama hatası: {e}")
            return 0

    def extract_league_from_team_url(self, team_href, soup):
        """Takım URL'sinden lig bilgisini çıkarır"""
        try:
            # URL'de lig bilgisi varsa çıkar
            # Örnek: /en/squads/18bb7c10/2024-2025/Liverpool-Stats
            if '/squads/' in team_href:
                # Tam takım sayfasını al
                team_url = self.utils.build_full_url(Settings.FBREF_BASE_URL, team_href)
                team_soup = self.get_page(team_url)

                if team_soup:
                    # Takım sayfasındaki lig linklerini bul
                    comp_links = team_soup.find_all('a', href=re.compile(r'/comps/\d+/'))
                    for link in comp_links:
                        link_text = link.get_text().strip()
                        # Bilinen lig isimlerini kontrol et
                        from config.leagues import LEAGUES
                        for league_name in LEAGUES.keys():
                            if league_name.lower() in link_text.lower() or link_text.lower() in league_name.lower():
                                return league_name

            return None
        except Exception as e:
            logging.error(f"Takım URL'sinden lig çıkarma hatası: {e}")
            return None

    def detect_league_from_page(self, soup):
        """Sayfa içeriğinden lig bilgisini tespit eder - Enhanced"""
        try:
            # 1. Breadcrumb linklerinden lig bul
            breadcrumb_selectors = [
                'div.breadcrumb a',
                'nav a',
                '.nav-bar a',
                'a[href*="/comps/"]'
            ]

            for selector in breadcrumb_selectors:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href', '')
                    if '/comps/' in href:
                        link_text = link.get_text().strip()
                        league = self.match_league_name(link_text)
                        if league:
                            return league

            # 2. Takım sayfası linklerinden lig bilgisi çıkar
            team_links = soup.find_all('a', href=re.compile(r'/squads/'))
            for link in team_links:
                # Takım sayfasına git ve lig bilgisini al
                team_href = link.get('href')
                if team_href:
                    league = self.extract_league_from_team_url(team_href, soup)
                    if league:
                        return league

            # 3. Meta tags'den lig bul
            meta_tags = soup.find_all('meta')
            for meta in meta_tags:
                content = meta.get('content', '').lower()
                description = meta.get('name', '').lower()

                if 'description' in description or 'keywords' in description:
                    league = self.match_league_name(content)
                    if league:
                        return league

            # 4. Sayfa başlığından lig bul
            title = soup.find('title')
            if title:
                title_text = title.get_text()
                league = self.match_league_name(title_text)
                if league:
                    return league

            # 5. Sayfa içindeki tüm metinden lig ismi ara
            page_text = soup.get_text().lower()
            for league_name in LEAGUES.keys():
                if league_name.lower() in page_text:
                    return league_name

            return None
        except Exception as e:
            logging.error(f"Sayfa'dan lig tespit hatası: {e}")
            return None

    def match_league_name(self, text):
        """Text'den lig ismini eşleştirir - Enhanced"""
        try:
            if not text:
                return None

            from config.leagues import LEAGUES
            text_lower = text.lower()

            # Doğrudan eşleşme
            for league_name in LEAGUES.keys():
                if league_name.lower() in text_lower:
                    return league_name

            # Gelişmiş kısmi eşleşmeler
            league_mappings = {
                'premier league': 'Premier League',
                'epl': 'Premier League',
                'english premier': 'Premier League',
                'la liga': 'La Liga',
                'primera division': 'La Liga',
                'serie a': 'Serie A',
                'italian serie a': 'Serie A',
                'bundesliga': 'Bundesliga',
                'german bundesliga': 'Bundesliga',
                'ligue 1': 'Ligue 1',
                'french ligue 1': 'Ligue 1',
                'süper lig': 'Trendyol Süper Lig',
                'super lig': 'Trendyol Süper Lig',
                'turkish super': 'Trendyol Süper Lig',
                'eredivisie': 'Eredivisie',
                'dutch eredivisie': 'Eredivisie',
                'championship': 'Championship',
                'english championship': 'Championship',
                'liga portugal': 'Liga Portugal Betclic',
                'portuguese liga': 'Liga Portugal Betclic',
                'primeira liga': 'Liga Portugal Betclic',
                'mls': 'MLS',
                'major league soccer': 'MLS',
                'saudi pro': 'Saudi Pro League',
                'saudi professional': 'Saudi Pro League'
            }

            for keyword, league_name in league_mappings.items():
                if keyword in text_lower:
                    return league_name

            return None
        except Exception:
            return None

    def guess_league_from_team(self, team_name):
        """Takım isminden lig tahmini yapar"""
        try:
            team_lower = team_name.lower()

            # Premier League takımları
            pl_teams = ['liverpool', 'manchester', 'arsenal', 'chelsea', 'tottenham', 'newcastle', 'west ham',
                        'brighton']
            if any(team in team_lower for team in pl_teams):
                return 'Premier League'

            # La Liga takımları
            la_liga_teams = ['barcelona', 'real madrid', 'atletico', 'valencia', 'sevilla', 'athletic', 'real sociedad']
            if any(team in team_lower for team in la_liga_teams):
                return 'La Liga'

            # Serie A takımları
            serie_a_teams = ['juventus', 'milan', 'inter', 'napoli', 'roma', 'lazio', 'atalanta', 'fiorentina']
            if any(team in team_lower for team in serie_a_teams):
                return 'Serie A'

            # Bundesliga takımları
            bundesliga_teams = ['bayern', 'dortmund', 'leipzig', 'leverkusen', 'frankfurt', 'wolfsburg']
            if any(team in team_lower for team in bundesliga_teams):
                return 'Bundesliga'

            # Ligue 1 takımları
            ligue1_teams = ['psg', 'marseille', 'lyon', 'monaco', 'lille', 'rennes']
            if any(team in team_lower for team in ligue1_teams):
                return 'Ligue 1'

            return 'Unknown League'
        except Exception:
            return 'Unknown League'

    def extract_player_photo(self, soup, player):
        """Oyuncu fotoğrafını çıkarır"""
        try:
            # Ana fotoğraf
            photo_elem = soup.find('div', {'class': 'media-item'})
            if photo_elem:
                img = photo_elem.find('img')
                if img and img.get('src'):
                    player.data['photo'] = self.utils.build_full_url(Settings.FBREF_BASE_URL, img['src'])
                    return

            # Alternatif selectors
            img_selectors = [
                'img.media-object',
                'img[src*="headshots"]',
                '.player-photo img',
                '#meta img'
            ]

            for selector in img_selectors:
                img = soup.select_one(selector)
                if img and img.get('src'):
                    src = img['src']
                    if 'headshot' in src or 'photo' in src:
                        player.data['photo'] = self.utils.build_full_url(Settings.FBREF_BASE_URL, src)
                        return

        except Exception as e:
            logging.error(f"Fotoğraf çekme hatası: {e}")

    def extract_physical_info(self, soup, player):
        """Fiziksel bilgileri çeker"""
        try:
            bio_div = soup.find('div', {'id': 'meta'})
            if not bio_div:
                return

            bio_text = bio_div.get_text()

            # Boy bilgisi - çeşitli formatları handle et
            height_patterns = [
                r'(\d{3})cm',  # 180cm
                r'(\d)-(\d{1,2})',  # 5-11 (feet-inches)
                r'height[:\s]*(\d{3})cm',
                r'height[:\s]*(\d)-(\d{1,2})'
            ]

            height = ""
            for pattern in height_patterns:
                height_match = re.search(pattern, bio_text)
                if height_match:
                    if len(height_match.groups()) == 1:
                        height = f"{height_match.group(1)}cm"
                    else:
                        # feet-inches to cm conversion
                        feet, inches = int(height_match.group(1)), int(height_match.group(2))
                        cm = int((feet * 12 + inches) * 2.54)
                        height = f"{cm}cm"
                    break

            # Kilo bilgisi
            weight_patterns = [
                r'(\d{2,3})kg',
                r'(\d{3})lb',
                r'weight[:\s]*(\d{2,3})kg',
                r'weight[:\s]*(\d{3})lb'
            ]

            weight = ""
            for pattern in weight_patterns:
                weight_match = re.search(pattern, bio_text)
                if weight_match:
                    weight_val = int(weight_match.group(1))
                    if 'lb' in pattern:
                        weight_val = int(weight_val * 0.453592)
                        weight = f"{weight_val}kg"
                    else:
                        weight = f"{weight_val}kg"
                    break

            # Kullandığı ayak
            foot_patterns = [
                r'footed[:\s]*([a-zA-Z]+)',
                r'foot[:\s]*([a-zA-Z]+)',
                r'([a-zA-Z]+)[\s-]*footed'
            ]

            preferred_foot = ""
            for pattern in foot_patterns:
                foot_match = re.search(pattern, bio_text.lower())
                if foot_match:
                    foot_text = foot_match.group(1).strip()
                    if foot_text in ['left', 'right', 'both']:
                        preferred_foot = foot_text.title()
                        break

            player.set_physical_info(height, weight, preferred_foot)

        except Exception as e:
            logging.error(f"Fiziksel bilgi çekme hatası: {e}")

    def extract_season_stats(self, soup, player):
        """Sezon istatistiklerini çeker"""
        try:
            stats_dict = {}

            # İstatistik tablolarını bul ve parse et
            table_mappings = {
                'stats_standard': 'standard',
                'stats_shooting': 'shooting',
                'stats_passing': 'passing',
                'stats_pass_types': 'pass_types',
                'stats_gca': 'gsc',
                'stats_defense': 'defense',
                'stats_possession': 'possession',
                'stats_misc': 'misc'
            }

            for table_id, stats_key in table_mappings.items():
                table = soup.find('table', {'id': table_id})
                if table:
                    stats_dict[stats_key] = self.parse_stats_table(table)

            player.set_season_stats(stats_dict)

        except Exception as e:
            logging.error(f"Sezon istatistikleri çekme hatası: {e}")

    def parse_stats_table(self, table):
        """İstatistik tablosunu parse eder"""
        try:
            stats = {}

            # Tablo başlıklarını al
            thead = table.find('thead')
            if not thead:
                return stats

            headers = []
            header_row = thead.find('tr')
            if header_row:
                for th in header_row.find_all(['th', 'td']):
                    data_stat = th.get('data-stat', '')
                    if data_stat:
                        headers.append(data_stat)

            # Son sezon verilerini al
            tbody = table.find('tbody')
            if not tbody:
                return stats

            rows = tbody.find_all('tr')
            if not rows:
                return stats

            # En güncel sezon için son satırı al
            last_row = rows[-1]
            cells = last_row.find_all(['td', 'th'])

            for i, cell in enumerate(cells):
                if i < len(headers):
                    header = headers[i]
                    value = self.utils.extract_stat_value(cell.get_text())
                    stats[header] = value

            return stats

        except Exception as e:
            logging.error(f"Tablo parse hatası: {e}")
            return {}

    def extract_similar_players(self, soup, player, player_url):
        """Benzer oyuncuları çeker"""
        try:
            similar_players = []

            # Similar Players bölümünü bul
            similar_section = soup.find('div', {'id': 'all_similar'})
            if not similar_section:
                # Alternatif selectors
                for text_pattern in ['Similar Players', 'similar', 'comparison']:
                    similar_section = soup.find(string=re.compile(text_pattern, re.IGNORECASE))
                    if similar_section:
                        similar_section = similar_section.find_parent('div')
                        break

            if similar_section:
                player_links = similar_section.find_all('a', href=re.compile(r'/players/'))

                for link in player_links[:10]:  # İlk 10 benzer oyuncu
                    similar_name = self.utils.clean_text(link.get_text())
                    similar_url = self.utils.build_full_url(Settings.FBREF_BASE_URL, link.get('href'))
                    similar_id = self.utils.extract_fbref_id(similar_url)

                    if similar_id and similar_name:
                        similar_players.append({
                            'name': similar_name,
                            'fbrefId': similar_id,
                            'url': similar_url
                        })

            player.set_similar_players(similar_players)

        except Exception as e:
            logging.error(f"Benzer oyuncular çekme hatası: {e}")

    def extract_scouting_report(self, player, player_url):
        """Scouting raporunu çeker - Sadece geçerli istatistikleri toplar"""
        try:
            # Scouting report URL'si oluştur
            fbref_id = self.utils.extract_fbref_id(player_url)
            if not fbref_id:
                return

            player_name = player.data.get('fullName', '').replace(' ', '-')
            scouting_url = f"{Settings.FBREF_BASE_URL}/en/players/{fbref_id}/scout/365_m1/{player_name}-Scouting-Report"

            soup = self.get_page(scouting_url)
            if not soup:
                logging.warning(f"Scouting raporu getirilemedi: {scouting_url}")
                return

            scouting_data = {}

            # Tüm tabloları bul
            tables = soup.find_all('table')

            for table in tables:
                # Her tablodaki istatistikleri çıkar
                table_data = self.parse_scouting_table(table)

                # Çıkarılan istatistikleri ana scouting_data'ya ekle
                for stat_name, stat_values in table_data.items():
                    # Sadece geçerli istatistik isimlerini kabul et
                    if self.is_valid_stat_name(stat_name):
                        scouting_data[stat_name] = stat_values

            # PlayerModel'e scouting verilerini set et
            player.data['scoutingReport'] = scouting_data

            if scouting_data:
                logging.info(f"Scouting raporu tamamlandı: {len(scouting_data)} geçerli stat")
            else:
                logging.warning("Hiç scouting verisi çekilemedi")

        except Exception as e:
            logging.error(f"Scouting raporu çekme hatası: {e}")

    def is_valid_stat_name(self, stat_name):
                """İstatistik isminin geçerli olup olmadığını kontrol eder"""
                try:
                    if not stat_name or not isinstance(stat_name, str):
                        return False

                    stat_name_clean = stat_name.strip()

                    # Boş string kontrolü
                    if not stat_name_clean:
                        return False

                    # Sadece sayı olanları reddet
                    if stat_name_clean.isdigit():
                        return False

                    # Takım isimlerini reddet (büyük harfle başlayan ve birden fazla kelime içeren)
                    team_indicators = [
                        'Liverpool', 'Arsenal', 'Manchester', 'Chelsea', 'Barcelona', 'Real Madrid',
                        'Bayern Munich', 'Paris Saint-Germain', 'Juventus', 'Milan', 'Inter',
                        'Atletico', 'Napoli', 'Roma', 'Lazio', 'Dortmund', 'Leipzig',
                        'Marseille', 'Monaco', 'Lyon', 'United', 'City', 'FC', 'Union',
                        'Whitecaps', 'Pride', 'Wave', 'Spirit', 'Current', 'Cincinnati'
                    ]

                    # Takım ismi kontrolü
                    for team_indicator in team_indicators:
                        if team_indicator.lower() in stat_name_clean.lower():
                            return False

                    # Geçerli istatistik kelimelerini kontrol et
                    valid_stat_keywords = [
                        'goals', 'assists', 'shots', 'passes', 'tackles', 'interceptions',
                        'blocks', 'clearances', 'touches', 'carries', 'take-ons', 'aerials',
                        'fouls', 'cards', 'xg', 'xa', 'npxg', 'sca', 'gca', 'progressive',
                        'completion', 'distance', 'penalty', 'crosses', 'corners', 'through',
                        'live-ball', 'dead-ball', 'switches', 'final third', 'area',
                        'challenged', 'won', 'lost', 'attempted', 'successful', 'percentage',
                        'miscontrols', 'dispossessed', 'recoveries', 'offsides', 'errors'
                    ]

                    # En az bir geçerli kelime içermeli
                    stat_lower = stat_name_clean.lower()
                    has_valid_keyword = any(keyword in stat_lower for keyword in valid_stat_keywords)

                    # Özel durumlar: kısa ama geçerli istatistikler
                    short_valid_stats = ['%', 'per90', 'percentile']
                    is_short_valid = any(short_stat in stat_lower for short_stat in short_valid_stats)

                    return has_valid_keyword or is_short_valid

                except Exception as e:
                    logging.error(f"Stat name validation error: {e}")
                    return False

    def determine_scouting_category(self, table, table_id):
        """Tablodan scouting kategorisini belirler"""
        try:
            # Önce table ID'sinden çıkarmaya çalış
            if 'standard' in table_id.lower() or 'summary' in table_id.lower():
                return 'standard'
            elif 'shooting' in table_id.lower():
                return 'shooting'
            elif 'passing' in table_id.lower() and 'types' not in table_id.lower():
                return 'passing'
            elif 'pass_types' in table_id.lower() or 'passtypes' in table_id.lower():
                return 'pass_types'
            elif 'gca' in table_id.lower() or 'creation' in table_id.lower():
                return 'gsc'
            elif 'defense' in table_id.lower() or 'defensive' in table_id.lower():
                return 'defense'
            elif 'possession' in table_id.lower():
                return 'possession'
            elif 'misc' in table_id.lower() or 'miscellaneous' in table_id.lower():
                return 'misc'

            # Table ID'sinden bulamazsa, tablo başlığına bak
            caption = table.find('caption')
            if caption:
                caption_text = caption.get_text().lower()

                if 'standard' in caption_text or 'summary' in caption_text:
                    return 'standard'
                elif 'shooting' in caption_text:
                    return 'shooting'
                elif 'passing' in caption_text and 'types' not in caption_text:
                    return 'passing'
                elif 'pass types' in caption_text:
                    return 'pass_types'
                elif 'goal' in caption_text and 'creation' in caption_text:
                    return 'gsc'
                elif 'defensive' in caption_text or 'defense' in caption_text:
                    return 'defense'
                elif 'possession' in caption_text:
                    return 'possession'
                elif 'misc' in caption_text:
                    return 'misc'

            # Tablonun üstündeki başlığa bak
            prev_sibling = table.find_previous_sibling()
            if prev_sibling and prev_sibling.name in ['h2', 'h3', 'h4']:
                header_text = prev_sibling.get_text().lower()

                if 'shooting' in header_text:
                    return 'shooting'
                elif 'passing' in header_text and 'types' not in header_text:
                    return 'passing'
                elif 'pass types' in header_text:
                    return 'pass_types'
                elif 'goal' in header_text and 'creation' in header_text:
                    return 'gsc'
                elif 'defensive' in header_text or 'defense' in header_text:
                    return 'defense'
                elif 'possession' in header_text:
                    return 'possession'
                elif 'misc' in header_text:
                    return 'misc'

            # Tablodaki stat isimlerinden kategoriyi tahmin et
            first_few_stats = []
            tbody = table.find('tbody')
            if tbody:
                rows = tbody.find_all('tr')[:5]  # İlk 5 satıra bak
                for row in rows:
                    first_cell = row.find(['td', 'th'])
                    if first_cell:
                        stat_name = first_cell.get_text().lower()
                        first_few_stats.append(stat_name)

            # Stat isimlerinden kategori tahmin et
            stats_text = ' '.join(first_few_stats)

            if any(word in stats_text for word in ['shots', 'goals', 'shooting']):
                return 'shooting'
            elif any(word in stats_text for word in ['passes completed', 'pass completion', 'progressive passes']):
                return 'passing'
            elif any(word in stats_text for word in ['live-ball', 'dead-ball', 'through balls', 'crosses']):
                return 'pass_types'
            elif any(word in stats_text for word in ['shot-creating', 'goal-creating']):
                return 'gsc'
            elif any(word in stats_text for word in ['tackles', 'interceptions', 'blocks']):
                return 'defense'
            elif any(word in stats_text for word in ['touches', 'take-ons', 'carries']):
                return 'possession'
            elif any(word in stats_text for word in ['yellow cards', 'fouls', 'aerials']):
                return 'misc'

            return None

        except Exception as e:
            logging.error(f"Kategori belirleme hatası: {e}")
            return None

    def extract_scouting_alternative(self, soup):
        """Alternatif scouting çıkarma yöntemi"""
        try:
            scouting_dict = {
                'standard': {},
                'shooting': {},
                'passing': {},
                'pass_types': {},
                'gsc': {},
                'defense': {},
                'possession': {},
                'misc': {}
            }

            # Tüm veri satırlarını bul (percentile sütunu olan)
            all_rows = soup.find_all('tr')

            for row in all_rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 3:
                    # Üçüncü sütunda percentile var mı kontrol et
                    third_cell = cells[2].get_text().strip()
                    if third_cell.isdigit() or '%' in third_cell:
                        # Bu bir stat satırı
                        stat_name = self.utils.clean_text(cells[0].get_text())
                        per90_value = self.utils.extract_stat_value(cells[1].get_text())
                        percentile_value = self.utils.extract_percentile(third_cell)

                        if stat_name and per90_value is not None:
                            # Stat'ı uygun kategoriye yerleştir
                            category = self.categorize_stat_by_name(stat_name)

                            if category:
                                scouting_dict[category][stat_name] = {
                                    'per90': per90_value,
                                    'percentile': percentile_value
                                }

            # Boş kategorileri temizle
            scouting_dict = {k: v for k, v in scouting_dict.items() if v}

            return scouting_dict

        except Exception as e:
            logging.error(f"Alternatif scouting çıkarma hatası: {e}")
            return {}

    def categorize_stat_by_name(self, stat_name):
        """Stat isminden kategorisini belirler"""
        try:
            stat_lower = stat_name.lower()

            # Shooting stats
            if any(word in stat_lower for word in ['shots', 'goals', 'xg', 'shooting', 'penalty']):
                return 'shooting'

            # Passing stats
            elif any(word in stat_lower for word in
                     ['passes', 'assists', 'xag', 'key passes', 'final third', 'penalty area']):
                return 'passing'

            # Pass types
            elif any(word in stat_lower for word in
                     ['live-ball', 'dead-ball', 'through balls', 'crosses', 'corner', 'switches']):
                return 'pass_types'

            # Goal and shot creation
            elif any(word in stat_lower for word in ['shot-creating', 'goal-creating', 'sca', 'gca']):
                return 'gsc'

            # Defense
            elif any(word in stat_lower for word in ['tackles', 'interceptions', 'blocks', 'clearances', 'challenges']):
                return 'defense'

            # Possession
            elif any(word in stat_lower for word in
                     ['touches', 'take-ons', 'carries', 'dribbles', 'progressive carries']):
                return 'possession'

            # Miscellaneous
            elif any(word in stat_lower for word in ['cards', 'fouls', 'offsides', 'aerials', 'recoveries']):
                return 'misc'

            # Default to standard if unclear
            else:
                return 'standard'

        except Exception:
            return 'standard'

    def parse_scouting_table(self, table):
        """Scouting tablosunu parse eder - Gelişmiş filtreleme ile"""
        try:
            scouting_data = {}

            tbody = table.find('tbody')
            if not tbody:
                return scouting_data

            rows = tbody.find_all('tr')

            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 3:
                    # İstatistik ismi
                    stat_cell = cells[0]
                    stat_name = self.utils.clean_text(stat_cell.get_text())

                    # Per 90 değeri
                    per90_text = cells[1].get_text().strip()
                    per90_value = self.utils.extract_stat_value(per90_text)

                    # Percentile değeri
                    percentile_text = cells[2].get_text().strip()
                    percentile_value = self.utils.extract_percentile(percentile_text)

                    # Sadece geçerli veriler için işlem yap
                    if (stat_name and
                            self.is_valid_stat_name(stat_name) and
                            per90_text not in ['', '-', '—'] and
                            percentile_text not in ['', '-', '—']):
                        scouting_data[stat_name] = {
                            'per90': per90_value,
                            'percentile': percentile_value
                        }

            return scouting_data

        except Exception as e:
            logging.error(f"Scouting tablo parse hatası: {e}")
            return {}

    def get_full_stat_name(self, data_stat, visible_text):
        """Data-stat attribute'undan tam stat ismini döndürür"""

        # Scouting report'taki stat isimlerinin mapping'i
        stat_mappings = {
            # Standard Stats
            'goals_per90': 'Goals',
            'assists_per90': 'Assists',
            'goals_assists_per90': 'Goals + Assists',
            'goals_pens_per90': 'Non-Penalty Goals',
            'pens_made_per90': 'Penalty Kicks Made',
            'pens_att_per90': 'Penalty Kicks Attempted',
            'cards_yellow_per90': 'Yellow Cards',
            'cards_red_per90': 'Red Cards',
            'xg_per90': 'xG: Expected Goals',
            'npxg_per90': 'npxG: Non-Penalty xG',
            'xg_assist_per90': 'xAG: Exp. Assisted Goals',
            'npxg_xg_assist_per90': 'npxG + xAG',
            'progressive_carries_per90': 'Progressive Carries',
            'progressive_passes_per90': 'Progressive Passes',
            'progressive_passes_received_per90': 'Progressive Passes Rec',
            'touches_att_pen_area_per90': 'Touches (Att Pen)',
            'sca_per90': 'Shot-Creating Actions',
            'passes_per90': 'Passes Attempted',
            'passes_pct': 'Pass Completion %',
            'take_ons_won_per90': 'Successful Take-Ons',
            'tackles_per90': 'Tackles',
            'interceptions_per90': 'Interceptions',
            'blocks_per90': 'Blocks',
            'clearances_per90': 'Clearances',
            'aerials_won_per90': 'Aerials Won',

            # Shooting Stats
            'shots_per90': 'Shots Total',
            'shots_on_target_per90': 'Shots on Target',
            'shots_on_target_pct': 'Shots on Target %',
            'goals_per_shot': 'Goals/Shot',
            'goals_per_shot_on_target': 'Goals/Shot on Target',
            'average_shot_distance': 'Average Shot Distance',
            'shots_free_kicks_per90': 'Shots from Free Kicks',
            'npxg_per_shot': 'npxG/Shot',
            'goals_minus_xg_per90': 'Goals - xG',
            'np_goals_minus_npxg_per90': 'Non-Penalty Goals - npxG',

            # Passing Stats
            'passes_completed_per90': 'Passes Completed',
            'passes_per90': 'Passes Attempted',
            'passes_pct': 'Pass Completion %',
            'passes_total_distance': 'Total Passing Distance',
            'passes_progressive_distance': 'Progressive Passing Distance',
            'passes_completed_short_per90': 'Passes Completed (Short)',
            'passes_short_per90': 'Passes Attempted (Short)',
            'passes_pct_short': 'Pass Completion % (Short)',
            'passes_completed_medium_per90': 'Passes Completed (Medium)',
            'passes_medium_per90': 'Passes Attempted (Medium)',
            'passes_pct_medium': 'Pass Completion % (Medium)',
            'passes_completed_long_per90': 'Passes Completed (Long)',
            'passes_long_per90': 'Passes Attempted (Long)',
            'passes_pct_long': 'Pass Completion % (Long)',
            'assists_per90': 'Assists',
            'xg_assist_per90': 'xAG: Exp. Assisted Goals',
            'xa_per90': 'xA: Expected Assists',
            'key_passes_per90': 'Key Passes',
            'passes_into_final_third_per90': 'Passes into Final Third',
            'passes_into_penalty_area_per90': 'Passes into Penalty Area',
            'crosses_into_penalty_area_per90': 'Crosses into Penalty Area',
            'progressive_passes_per90': 'Progressive Passes',

            # Pass Types
            'passes_live_per90': 'Live-ball Passes',
            'passes_dead_per90': 'Dead-ball Passes',
            'passes_free_kicks_per90': 'Passes from Free Kicks',
            'through_balls_per90': 'Through Balls',
            'passes_switches_per90': 'Switches',
            'crosses_per90': 'Crosses',
            'throw_ins_per90': 'Throw-ins Taken',
            'corner_kicks_per90': 'Corner Kicks',
            'corner_kicks_in_per90': 'Inswinging Corner Kicks',
            'corner_kicks_out_per90': 'Outswinging Corner Kicks',
            'corner_kicks_straight_per90': 'Straight Corner Kicks',
            'passes_completed_per90': 'Passes Completed',
            'passes_offsides_per90': 'Passes Offside',
            'passes_blocked_per90': 'Passes Blocked',

            # Goal and Shot Creation
            'sca_per90': 'Shot-Creating Actions',
            'sca_passes_live_per90': 'SCA (Live-ball Pass)',
            'sca_passes_dead_per90': 'SCA (Dead-ball Pass)',
            'sca_take_ons_per90': 'SCA (Take-On)',
            'sca_shots_per90': 'SCA (Shot)',
            'sca_fouled_per90': 'SCA (Fouls Drawn)',
            'sca_defense_per90': 'SCA (Defensive Action)',
            'gca_per90': 'Goal-Creating Actions',
            'gca_passes_live_per90': 'GCA (Live-ball Pass)',
            'gca_passes_dead_per90': 'GCA (Dead-ball Pass)',
            'gca_take_ons_per90': 'GCA (Take-On)',
            'gca_shots_per90': 'GCA (Shot)',
            'gca_fouled_per90': 'GCA (Fouls Drawn)',
            'gca_defense_per90': 'GCA (Defensive Action)',

            # Defense
            'tackles_per90': 'Tackles',
            'tackles_won_per90': 'Tackles Won',
            'tackles_def_3rd_per90': 'Tackles (Def 3rd)',
            'tackles_mid_3rd_per90': 'Tackles (Mid 3rd)',
            'tackles_att_3rd_per90': 'Tackles (Att 3rd)',
            'challenge_tackles_per90': 'Dribblers Tackled',
            'challenges_per90': 'Dribbles Challenged',
            'challenge_tackles_pct': '% of Dribblers Tackled',
            'challenges_lost_per90': 'Challenges Lost',
            'blocks_per90': 'Blocks',
            'blocked_shots_per90': 'Shots Blocked',
            'blocked_passes_per90': 'Passes Blocked',
            'interceptions_per90': 'Interceptions',
            'tackles_interceptions_per90': 'Tkl+Int',
            'clearances_per90': 'Clearances',
            'errors_per90': 'Errors',

            # Possession
            'touches_per90': 'Touches',
            'touches_def_pen_area_per90': 'Touches (Def Pen)',
            'touches_def_3rd_per90': 'Touches (Def 3rd)',
            'touches_mid_3rd_per90': 'Touches (Mid 3rd)',
            'touches_att_3rd_per90': 'Touches (Att 3rd)',
            'touches_att_pen_area_per90': 'Touches (Att Pen)',
            'touches_live_ball_per90': 'Touches (Live-Ball)',
            'take_ons_per90': 'Take-Ons Attempted',
            'take_ons_won_per90': 'Successful Take-Ons',
            'take_ons_won_pct': 'Successful Take-On %',
            'take_ons_tackled_per90': 'Times Tackled During Take-On',
            'take_ons_tackled_pct': 'Tackled During Take-On Percentage',
            'carries_per90': 'Carries',
            'carries_distance_per90': 'Total Carrying Distance',
            'carries_progressive_distance_per90': 'Progressive Carrying Distance',
            'progressive_carries_per90': 'Progressive Carries',
            'carries_into_final_third_per90': 'Carries into Final Third',
            'carries_into_penalty_area_per90': 'Carries into Penalty Area',
            'miscontrols_per90': 'Miscontrols',
            'dispossessed_per90': 'Dispossessed',
            'passes_received_per90': 'Passes Received',
            'progressive_passes_received_per90': 'Progressive Passes Rec',

            # Miscellaneous
            'cards_yellow_per90': 'Yellow Cards',
            'cards_red_per90': 'Red Cards',
            'cards_yellow_red_per90': 'Second Yellow Card',
            'fouls_per90': 'Fouls Committed',
            'fouled_per90': 'Fouls Drawn',
            'offsides_per90': 'Offsides',
            'crosses_per90': 'Crosses',
            'interceptions_per90': 'Interceptions',
            'tackles_won_per90': 'Tackles Won',
            'pens_won_per90': 'Penalty Kicks Won',
            'pens_conceded_per90': 'Penalty Kicks Conceded',
            'own_goals_per90': 'Own Goals',
            'ball_recoveries_per90': 'Ball Recoveries',
            'aerials_won_per90': 'Aerials Won',
            'aerials_lost_per90': 'Aerials Lost',
            'aerials_won_pct': '% of Aerials Won'
        }

        # Eğer mapping'de varsa onu kullan, yoksa görünen metni kullan
        return stat_mappings.get(data_stat, visible_text)

    def extract_transfer_history(self, soup, player):
        """Transfer geçmişini çeker"""
        try:
            transfers = []

            # Transfer tablosu
            transfer_table = soup.find('table', {'id': 'transfers'})
            if not transfer_table:
                return

            tbody = transfer_table.find('tbody')
            if not tbody:
                return

            rows = tbody.find_all('tr')

            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 4:
                    # Sezon
                    season = self.utils.clean_text(cells[0].get_text())

                    # Tarih
                    date = self.utils.clean_text(cells[1].get_text())

                    # Eski takım
                    from_team = self.utils.clean_text(cells[2].get_text())

                    # Yeni takım
                    to_team = self.utils.clean_text(cells[3].get_text())

                    # Transfer ücreti (varsa)
                    fee = ""
                    if len(cells) > 4:
                        fee = self.utils.clean_text(cells[4].get_text())

                    transfers.append({
                        'season': season,
                        'date': date,
                        'fromTeam': from_team,
                        'toTeam': to_team,
                        'fee': fee
                    })

            player.set_transfer_history(transfers)

        except Exception as e:
            logging.error(f"Transfer geçmişi çekme hatası: {e}")

    def update_existing_player_contract(self, fbref_id):
        """Mevcut oyuncunun kontrat bilgisini günceller"""
        try:
            player_url = f"https://fbref.com/en/players/{fbref_id}/"
            soup = self.get_page(player_url)

            if soup:
                contract_end = self.extract_contract_end(soup)
                return contract_end

            return ""
        except Exception as e:
            logging.error(f"Kontrat güncelleme hatası: {e}")
            return ""