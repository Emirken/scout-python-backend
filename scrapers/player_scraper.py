# scrapers/player_scraper.py
import logging
from .base_scraper import BaseScraper
from .utils import ScrapingUtils
from config.settings import Settings
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
        """Temel bilgileri çeker"""
        try:
            # FBRef ID
            fbref_id = self.utils.extract_fbref_id(player_url)

            # Oyuncu adı
            name_elem = soup.find('h1')
            full_name = self.utils.clean_text(name_elem.text) if name_elem else ""

            # Bio tablosu
            bio_table = soup.find('div', {'id': 'meta'})
            if bio_table:
                bio_items = bio_table.find_all('p')

                age = 0
                team = ""
                position = ""
                contract_end = ""

                for item in bio_items:
                    text = item.text.lower()

                    if 'age' in text:
                        age_match = re.search(r'age (\d+)', text)
                        age = int(age_match.group(1)) if age_match else 0

                    elif 'club' in text or 'team' in text:
                        team_link = item.find('a')
                        team = self.utils.clean_text(team_link.text) if team_link else ""

                    elif 'position' in text:
                        position = self.utils.clean_text(text.replace('position:', '').strip())

                    elif 'contract' in text:
                        contract_match = re.search(r'(\d{4})', text)
                        contract_end = contract_match.group(1) if contract_match else ""

            # Basic info'dan gelen veriler varsa kullan
            if basic_info:
                team = basic_info.get('team', team)
                age = basic_info.get('age', age)
                position = basic_info.get('position', position)

            # Player model'e ayarla
            league = basic_info.get('league', '') if basic_info else ''
            player.set_basic_info(full_name, age, team, league, fbref_id)
            player.data['detailedPosition'] = position
            player.data['contractEnd'] = contract_end

            # Fotoğraf
            photo_elem = soup.find('div', {'class': 'media-item'})
            if photo_elem:
                img = photo_elem.find('img')
                if img and img.get('src'):
                    player.data['photo'] = self.utils.build_full_url(Settings.FBREF_BASE_URL, img['src'])

        except Exception as e:
            logging.error(f"Temel bilgi çekme hatası: {e}")

    def extract_physical_info(self, soup, player):
        """Fiziksel bilgileri çeker"""
        try:
            bio_div = soup.find('div', {'id': 'meta'})
            if not bio_div:
                return

            bio_text = bio_div.text

            # Boy bilgisi
            height_match = re.search(r'(\d+cm|\d+-\d+)', bio_text)
            height = height_match.group(1) if height_match else ""

            # Kilo bilgisi
            weight_match = re.search(r'(\d+kg|\d+lb)', bio_text)
            weight = weight_match.group(1) if weight_match else ""

            # Kullandığı ayak
            foot_match = re.search(r'footed[:\s]*([a-zA-Z]+)', bio_text.lower())
            preferred_foot = foot_match.group(1).title() if foot_match else ""

            # Parse et
            height_clean, weight_clean = self.utils.parse_height_weight(height, weight)

            player.set_physical_info(height_clean, weight_clean, preferred_foot)

        except Exception as e:
            logging.error(f"Fiziksel bilgi çekme hatası: {e}")

    def extract_season_stats(self, soup, player):
        """Sezon istatistiklerini çeker"""
        try:
            stats_dict = {}

            # Standard Stats
            standard_table = soup.find('table', {'id': 'stats_standard'})
            if standard_table:
                stats_dict['standard'] = self.parse_stats_table(standard_table)

            # Shooting Stats
            shooting_table = soup.find('table', {'id': 'stats_shooting'})
            if shooting_table:
                stats_dict['shooting'] = self.parse_stats_table(shooting_table)

            # Passing Stats
            passing_table = soup.find('table', {'id': 'stats_passing'})
            if passing_table:
                stats_dict['passing'] = self.parse_stats_table(passing_table)

            # Pass Types
            pass_types_table = soup.find('table', {'id': 'stats_pass_types'})
            if pass_types_table:
                stats_dict['pass_types'] = self.parse_stats_table(pass_types_table)

            # Goal and Shot Creation
            gsc_table = soup.find('table', {'id': 'stats_gca'})
            if gsc_table:
                stats_dict['gsc'] = self.parse_stats_table(gsc_table)

            # Defensive Actions
            defense_table = soup.find('table', {'id': 'stats_defense'})
            if defense_table:
                stats_dict['defense'] = self.parse_stats_table(defense_table)

            # Possession
            possession_table = soup.find('table', {'id': 'stats_possession'})
            if possession_table:
                stats_dict['possession'] = self.parse_stats_table(possession_table)

            # Miscellaneous
            misc_table = soup.find('table', {'id': 'stats_misc'})
            if misc_table:
                stats_dict['misc'] = self.parse_stats_table(misc_table)

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

            # En son sezon verilerini al (genellikle son satır)
            tbody = table.find('tbody')
            if not tbody:
                return stats

            rows = tbody.find_all('tr')
            if not rows:
                return stats

            # Son satırı al (en güncel sezon)
            last_row = rows[-1]
            cells = last_row.find_all(['td', 'th'])

            for i, cell in enumerate(cells):
                if i < len(headers):
                    header = headers[i]
                    value = self.utils.extract_stat_value(cell.text)
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
                # Alternatif selector
                similar_section = soup.find('div', string=re.compile(r'Similar Players'))
                if similar_section:
                    similar_section = similar_section.find_parent('div')

            if similar_section:
                player_links = similar_section.find_all('a', href=re.compile(r'/players/'))

                for link in player_links[:10]:  # İlk 10 benzer oyuncu
                    similar_name = self.utils.clean_text(link.text)
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
                if len(cells) >= 4:
                    # Stat adı
                    stat_name = self.utils.clean_text(cells[0].text)

                    # Per 90 değeri
                    per90_value = self.utils.extract_stat_value(cells[1].text)

                    # Percentile değeri
                    percentile_value = self.utils.extract_percentile(cells[2].text)

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
                    season = self.utils.clean_text(cells[0].text)

                    # Tarih
                    date = self.utils.clean_text(cells[1].text)

                    # Eski takım
                    from_team = self.utils.clean_text(cells[2].text)

                    # Yeni takım
                    to_team = self.utils.clean_text(cells[3].text)

                    # Transfer ücreti (varsa)
                    fee = ""
                    if len(cells) > 4:
                        fee = self.utils.clean_text(cells[4].text)

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