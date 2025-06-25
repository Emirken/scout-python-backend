# scrapers/player_scraper.py
import logging
from .base_scraper import BaseScraper
from .utils import ScrapingUtils
from config.settings import Settings
from config.leagues import LEAGUE_COUNTRIES
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
        """Temel bilgileri çeker - Enhanced league detection"""
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
            contract_end = ""
            league = ""
            country = ""

            # Bio tablosu - meta div'den bilgileri çek
            meta_div = soup.find('div', {'id': 'meta'})
            if meta_div:
                # Paragraflardan bilgi çek
                bio_items = meta_div.find_all('p')

                for item in bio_items:
                    text = item.get_text().lower()

                    if 'age' in text:
                        age_match = re.search(r'age\s*:?\s*(\d+)', text)
                        if not age_match:
                            age_match = re.search(r'(\d+)', text)
                        age = int(age_match.group(1)) if age_match else 0

                    elif any(keyword in text for keyword in ['club', 'team', 'current team']):
                        team_link = item.find('a')
                        if team_link:
                            team = self.utils.clean_text(team_link.text)
                        else:
                            # Link yoksa text'ten çıkar
                            team_text = re.sub(r'(club|team|current team)[:\s]*', '', text, flags=re.IGNORECASE)
                            team = self.utils.clean_text(team_text)

                    elif 'position' in text:
                        position_text = re.sub(r'position[:\s]*', '', text, flags=re.IGNORECASE)
                        position = self.utils.clean_text(position_text)

                    elif 'contract' in text:
                        contract_match = re.search(r'(\d{4})', text)
                        contract_end = contract_match.group(1) if contract_match else ""

                # Takım linkinden lig bilgisini çıkarmaya çalış
                team_links = meta_div.find_all('a', href=re.compile(r'/squads/'))
                for team_link in team_links:
                    team_href = team_link.get('href', '')
                    # Squad URL'sinden lig bilgisini çıkar
                    if '/squads/' in team_href:
                        league = self.extract_league_from_team_url(team_href, soup)
                        if league:
                            break

            # Alternatif: Sayfa içindeki diğer linklerden lig bilgisini bul
            if not league:
                league = self.detect_league_from_page(soup)

            # Basic info'dan gelen veriler varsa kullan (öncelik)
            if basic_info:
                team = basic_info.get('team', team) or team
                age = basic_info.get('age', age) or age
                position = basic_info.get('position', position) or position
                league = basic_info.get('league', league) or league
                country = basic_info.get('country', country) or country

            # Ülke bilgisini lig'den çıkar
            if league and not country:
                country = LEAGUE_COUNTRIES.get(league, '')

            # Lig bilgisi hala yoksa default değer ver
            if not league:
                if team:
                    league = self.guess_league_from_team(team)
                else:
                    league = "Unknown League"

            # Player model'e ayarla
            player.set_basic_info(full_name, age, team, league, fbref_id)
            player.data['detailedPosition'] = position
            player.data['contractEnd'] = contract_end
            player.data['country'] = country

            # Fotoğraf
            self.extract_player_photo(soup, player)

            logging.info(f"Temel bilgiler çıkarıldı: {full_name}, {team}, {league}")

        except Exception as e:
            logging.error(f"Temel bilgi çekme hatası: {e}")

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
        """Sayfa içeriğinden lig bilgisini tespit eder"""
        try:
            # Breadcrumb linklerinden lig bul
            breadcrumb_links = soup.find_all('a', href=re.compile(r'/comps/\d+/'))
            for link in breadcrumb_links:
                link_text = link.get_text().strip()
                league = self.match_league_name(link_text)
                if league:
                    return league

            # Meta bilgilerden lig bul
            meta_tags = soup.find_all('meta')
            for meta in meta_tags:
                content = meta.get('content', '').lower()
                if any(league.lower() in content for league in
                       ['premier league', 'la liga', 'serie a', 'bundesliga', 'ligue 1']):
                    for league_name in ['Premier League', 'La Liga', 'Serie A', 'Bundesliga', 'Ligue 1']:
                        if league_name.lower() in content:
                            return league_name

            # Sayfa başlığından lig bul
            title = soup.find('title')
            if title:
                title_text = title.get_text().lower()
                return self.match_league_name(title_text)

            return None
        except Exception as e:
            logging.error(f"Sayfa'dan lig tespit hatası: {e}")
            return None

    def match_league_name(self, text):
        """Text'den lig ismini eşleştirir"""
        try:
            from config.leagues import LEAGUES
            text_lower = text.lower()

            # Doğrudan eşleşme
            for league_name in LEAGUES.keys():
                if league_name.lower() in text_lower:
                    return league_name

            # Kısmi eşleşmeler
            league_mappings = {
                'premier': 'Premier League',
                'epl': 'Premier League',
                'la liga': 'La Liga',
                'serie a': 'Serie A',
                'bundesliga': 'Bundesliga',
                'ligue 1': 'Ligue 1',
                'süper lig': 'Trendyol Süper Lig',
                'eredivisie': 'Eredivisie',
                'championship': 'Championship',
                'liga portugal': 'Liga Portugal Betclic'
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