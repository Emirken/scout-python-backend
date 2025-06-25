import logging
from .base_scraper import BaseScraper
from .utils import ScrapingUtils
from config.settings import Settings
from config.leagues import LEAGUES, LEAGUE_COUNTRIES
import re


class LeagueScraper(BaseScraper):
    def __init__(self):
        super().__init__(use_selenium=False)
        self.utils = ScrapingUtils()

    def get_league_players(self, league_name):
        """Belirli bir ligdeki tüm oyuncuları getirir"""
        if league_name not in LEAGUES:
            logging.error(f"Bilinmeyen lig: {league_name}")
            return []

        league_url = LEAGUES[league_name]
        logging.info(f"Lig scraping başlatılıyor: {league_name}")

        soup = self.get_page(league_url)
        if not soup:
            logging.error(f"Lig sayfası getirilemedi: {league_url}")
            return []

        players = []

        # Ana istatistik tablosunu bul
        stats_table = soup.find('table', {'id': 'stats_standard'})
        if not stats_table:
            logging.warning(f"İstatistik tablosu bulunamadı: {league_name}")
            return []

        tbody = stats_table.find('tbody')
        if not tbody:
            return []

        rows = tbody.find_all('tr')

        for row in rows:
            try:
                player_data = self.extract_player_from_row(row, league_name)
                if player_data:
                    players.append(player_data)

            except Exception as e:
                logging.error(f"Oyuncu verisi çıkarılırken hata: {e}")
                continue

        logging.info(f"{league_name} liginden {len(players)} oyuncu bulundu")
        return players

    def extract_player_from_row(self, row, league_name):
        """Tablo satırından oyuncu bilgilerini çıkarır"""
        try:
            # Oyuncu adı ve URL'si
            player_cell = row.find('td', {'data-stat': 'player'})
            if not player_cell:
                return None

            player_link = player_cell.find('a')
            if not player_link:
                return None

            player_name = self.utils.clean_text(player_link.text)
            player_url = self.utils.build_full_url(Settings.FBREF_BASE_URL, player_link.get('href'))
            fbref_id = self.utils.extract_fbref_id(player_url)

            if not fbref_id:
                return None

            # Takım bilgisi
            team_cell = row.find('td', {'data-stat': 'team'})
            team_name = self.utils.clean_text(team_cell.text) if team_cell else ""

            # Yaş bilgisi
            age_cell = row.find('td', {'data-stat': 'age'})
            age = self.utils.parse_age(age_cell.text) if age_cell else 0

            # Pozisyon bilgisi
            position_cell = row.find('td', {'data-stat': 'position'})
            position = self.utils.clean_text(position_cell.text) if position_cell else ""

            # Temel istatistikler
            matches_cell = row.find('td', {'data-stat': 'matches'})
            matches = self.utils.extract_stat_value(matches_cell.text) if matches_cell else 0

            starts_cell = row.find('td', {'data-stat': 'starts'})
            starts = self.utils.extract_stat_value(starts_cell.text) if starts_cell else 0

            minutes_cell = row.find('td', {'data-stat': 'minutes'})
            minutes = self.utils.extract_stat_value(minutes_cell.text) if minutes_cell else 0

            goals_cell = row.find('td', {'data-stat': 'goals'})
            goals = self.utils.extract_stat_value(goals_cell.text) if goals_cell else 0

            assists_cell = row.find('td', {'data-stat': 'assists'})
            assists = self.utils.extract_stat_value(assists_cell.text) if assists_cell else 0

            return {
                'name': player_name,
                'fbref_id': fbref_id,
                'player_url': player_url,
                'team': team_name,
                'league': league_name,
                'country': LEAGUE_COUNTRIES.get(league_name, ''),
                'age': age,
                'position': position,
                'basic_stats': {
                    'matches': matches,
                    'starts': starts,
                    'minutes': minutes,
                    'goals': goals,
                    'assists': assists
                }
            }

        except Exception as e:
            logging.error(f"Satır verisi çıkarılırken hata: {e}")
            return None

    def get_all_leagues_players(self, league_list=None):
        """Tüm liglerden oyuncuları getirir"""
        if league_list is None:
            league_list = list(LEAGUES.keys())

        all_players = []

        for league_name in league_list:
            try:
                league_players = self.get_league_players(league_name)
                all_players.extend(league_players)

                # Ligler arası bekleme
                import time
                time.sleep(5)

            except Exception as e:
                logging.error(f"Lig scraping hatası ({league_name}): {e}")
                continue

        logging.info(f"Toplam {len(all_players)} oyuncu bulundu")
        return all_players

    def get_team_squad(self, team_url):
        """Takım kadrosunu getirir"""
        soup = self.get_page(team_url)
        if not soup:
            return []

        players = []

        # Kadro tablosunu bul
        squad_table = soup.find('table', {'id': 'stats_standard'})
        if not squad_table:
            return []

        tbody = squad_table.find('tbody')
        if not tbody:
            return []