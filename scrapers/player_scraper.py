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
        """Scouting raporunu çeker"""
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

            scouting_dict = {}

            # Scouting tabloları
            tables = soup.find_all('table', {'class': 'stats_table'})

            for table in tables:
                table_id = table.get('id', '')

                if 'scout_summary' in table_id:
                    scouting_dict['standard'] = self.parse_scouting_table(table)
                elif 'scout_shooting' in table_id:
                    scouting_dict['shooting'] = self.parse_scouting_table(table)
                elif 'scout_passing' in table_id:
                    scouting_dict['passing'] = self.parse_scouting_table(table)
                elif 'scout_pass_types' in table_id:
                    scouting_dict['pass_types'] = self.parse_scouting_table(table)
                elif 'scout_gca' in table_id:
                    scouting_dict['gsc'] = self.parse_scouting_table(table)
                elif 'scout_defense' in table_id:
                    scouting_dict['defense'] = self.parse_scouting_table(table)
                elif 'scout_possession' in table_id:
                    scouting_dict['possession'] = self.parse_scouting_table(table)
                elif 'scout_misc' in table_id:
                    scouting_dict['misc'] = self.parse_scouting_table(table)

            player.set_scouting_report(scouting_dict)

        except Exception as e:
            logging.error(f"Scouting raporu çekme hatası: {e}")

    def parse_scouting_table(self, table):
        """Scouting tablosunu parse eder"""
        try:
            scouting_data = {}

            tbody = table.find('tbody')
            if not tbody:
                return scouting_data

            rows = tbody.find_all('tr')

            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 3:
                    # Stat adı
                    stat_name = self.utils.clean_text(cells[0].get_text())

                    # Per 90 değeri
                    per90_value = self.utils.extract_stat_value(cells[1].get_text())

                    # Percentile değeri
                    percentile_value = self.utils.extract_percentile(cells[2].get_text())

                    if stat_name:
                        scouting_data[stat_name] = {
                            'per90': per90_value,
                            'percentile': percentile_value
                        }

            return scouting_data

        except Exception as e:
            logging.error(f"Scouting tablo parse hatası: {e}")
            return {}

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