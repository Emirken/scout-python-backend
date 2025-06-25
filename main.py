# main.py
import logging
import sys
import os
import time
from datetime import datetime

# Proje modüllerini import et
from models.database import DatabaseManager
from scrapers.league_scraper import LeagueScraper
from scrapers.player_scraper import PlayerScraper
from scrapers.utils import setup_logging
from config.leagues import LEAGUES


class FBRefScraper:
    def __init__(self):
        # Logging'i başlat
        setup_logging()
        self.logger = logging.getLogger(__name__)

        # Scraper'ları başlat
        self.league_scraper = LeagueScraper()
        self.player_scraper = PlayerScraper()

        # Veritabanını başlat
        try:
            self.db = DatabaseManager()
            self.logger.info("Veritabanı bağlantısı başarılı")
        except Exception as e:
            self.logger.error(f"Veritabanı bağlantı hatası: {e}")
            sys.exit(1)

    def scrape_all_leagues(self, league_list=None):
        """Tüm ligleri scrape eder"""
        start_time = datetime.now()
        self.logger.info("Tüm ligler için scraping başlatılıyor...")

        if league_list is None:
            league_list = list(LEAGUES.keys())

        total_players = 0
        successful_players = 0

        for league_name in league_list:
            try:
                self.logger.info(f"Lig scraping başlıyor: {league_name}")

                # Ligdeki oyuncuları al
                league_players = self.league_scraper.get_league_players(league_name)

                if not league_players:
                    self.logger.warning(f"Lig için oyuncu bulunamadı: {league_name}")
                    continue

                self.logger.info(f"{league_name}: {len(league_players)} oyuncu bulundu")
                total_players += len(league_players)

                # Her oyuncu için detaylı scraping
                for i, basic_player in enumerate(league_players, 1):
                    try:
                        player_url = basic_player['player_url']
                        fbref_id = basic_player['fbref_id']

                        # Veritabanında zaten varsa atla
                        existing_player = self.db.get_player(fbref_id)
                        if existing_player:
                            self.logger.info(f"Oyuncu zaten mevcut, atlanıyor: {basic_player['name']}")
                            continue

                        self.logger.info(
                            f"Oyuncu detayları çekiliyor ({i}/{len(league_players)}): {basic_player['name']}")

                        # Detaylı oyuncu bilgilerini çek
                        detailed_player = self.player_scraper.scrape_player_details(
                            player_url,
                            basic_player
                        )

                        if detailed_player:
                            # Veritabanına kaydet
                            result = self.db.insert_player(detailed_player)
                            if result:
                                successful_players += 1
                                self.logger.info(f"Oyuncu kaydedildi: {detailed_player['fullName']}")
                            else:
                                self.logger.error(f"Oyuncu kaydedilemedi: {detailed_player['fullName']}")
                        else:
                            self.logger.error(f"Oyuncu detayları çekilemedi: {basic_player['name']}")

                        # Her 10 oyuncuda bir progress raporu
                        if i % 10 == 0:
                            elapsed = datetime.now() - start_time
                            self.logger.info(
                                f"Progress: {successful_players}/{total_players} oyuncu başarılı - Geçen süre: {elapsed}")

                        # Rate limiting
                        time.sleep(3)

                    except Exception as e:
                        self.logger.error(f"Oyuncu scraping hatası ({basic_player.get('name', 'Unknown')}): {e}")
                        continue

                self.logger.info(f"Lig tamamlandı: {league_name}")

                # Ligler arası bekleme
                time.sleep(10)

            except Exception as e:
                self.logger.error(f"Lig scraping hatası ({league_name}): {e}")
                continue

        # Sonuç raporu
        end_time = datetime.now()
        total_time = end_time - start_time

        self.logger.info("=" * 50)
        self.logger.info("SCRAPING TAMAMLANDI")
        self.logger.info(f"Toplam süre: {total_time}")
        self.logger.info(f"Toplam oyuncu bulundu: {total_players}")
        self.logger.info(f"Başarıyla kaydedilen: {successful_players}")
        self.logger.info(f"Başarı oranı: {(successful_players / total_players) * 100:.1f}%")
        self.logger.info("=" * 50)

    def scrape_single_league(self, league_name):
        """Tek bir ligi scrape eder"""
        if league_name not in LEAGUES:
            self.logger.error(f"Bilinmeyen lig: {league_name}")
            return

        self.scrape_all_leagues([league_name])

    def scrape_single_player(self, player_url):
        """Tek bir oyuncuyu scrape eder"""
        try:
            self.logger.info(f"Tek oyuncu scraping: {player_url}")

            detailed_player = self.player_scraper.scrape_player_details(player_url)

            if detailed_player:
                result = self.db.insert_player(detailed_player)
                if result:
                    self.logger.info(f"Oyuncu başarıyla kaydedildi: {detailed_player['fullName']}")
                    return detailed_player
                else:
                    self.logger.error("Oyuncu kaydedilemedi")
            else:
                self.logger.error("Oyuncu detayları çekilemedi")

            return None

        except Exception as e:
            self.logger.error(f"Tek oyuncu scraping hatası: {e}")
            return None

    def update_existing_players(self):
        """Mevcut oyuncuları günceller"""
        try:
            self.logger.info("Mevcut oyuncular güncelleniyor...")

            all_players = self.db.get_all_players()
            self.logger.info(f"Güncellenecek oyuncu sayısı: {len(all_players)}")

            updated_count = 0

            for player in all_players:
                try:
                    fbref_id = player['fbref_id']
                    player_url = f"https://fbref.com/en/players/{fbref_id}/"

                    self.logger.info(f"Güncelleniyor: {player['fullName']}")

                    # Güncel verileri çek
                    updated_data = self.player_scraper.scrape_player_details(player_url)

                    if updated_data:
                        result = self.db.insert_player(updated_data)  # upsert
                        if result:
                            updated_count += 1
                            self.logger.info(f"Güncellendi: {updated_data['fullName']}")

                    time.sleep(2)  # Rate limiting

                except Exception as e:
                    self.logger.error(f"Oyuncu güncelleme hatası: {e}")
                    continue

            self.logger.info(f"Güncelleme tamamlandı. {updated_count} oyuncu güncellendi.")

        except Exception as e:
            self.logger.error(f"Toplu güncelleme hatası: {e}")

    def get_database_stats(self):
        """Veritabanı istatistiklerini gösterir"""
        try:
            all_players = self.db.get_all_players()

            # Genel istatistikler
            total_players = len(all_players)

            # Lig bazında sayılar
            league_counts = {}
            for player in all_players:
                league = player.get('league', 'Unknown')
                league_counts[league] = league_counts.get(league, 0) + 1

            # Rapor
            print("=" * 50)
            print("VERİTABANI İSTATİSTİKLERİ")
            print("=" * 50)
            print(f"Toplam oyuncu sayısı: {total_players}")
            print("\nLig bazında dağılım:")
            for league, count in sorted(league_counts.items()):
                print(f"  {league}: {count} oyuncu")
            print("=" * 50)

        except Exception as e:
            self.logger.error(f"İstatistik alma hatası: {e}")

    def cleanup(self):
        """Kaynakları temizler"""
        try:
            self.league_scraper.close()
            self.player_scraper.close()
            self.db.close()
            self.logger.info("Kaynaklar temizlendi")
        except Exception as e:
            self.logger.error(f"Temizleme hatası: {e}")


def main():
    """Ana fonksiyon"""
    scraper = None

    try:
        scraper = FBRefScraper()

        if len(sys.argv) > 1:
            command = sys.argv[1].lower()

            if command == "all":
                # Tüm ligleri scrape et
                scraper.scrape_all_leagues()

            elif command == "league" and len(sys.argv) > 2:
                # Belirli bir ligi scrape et
                league_name = sys.argv[2]
                scraper.scrape_single_league(league_name)

            elif command == "player" and len(sys.argv) > 2:
                # Belirli bir oyuncuyu scrape et
                player_url = sys.argv[2]
                scraper.scrape_single_player(player_url)

            elif command == "update":
                # Mevcut oyuncuları güncelle
                scraper.update_existing_players()

            elif command == "stats":
                # Veritabanı istatistikleri
                scraper.get_database_stats()

            elif command == "test":
                # Test modunda sadece birkaç oyuncu
                test_leagues = ["Premier League", "La Liga"]
                scraper.scrape_all_leagues(test_leagues)

            else:
                print("Geçersiz komut!")
                print_usage()

        else:
            print_usage()

    except KeyboardInterrupt:
        print("\nScraping durduruldu...")

    except Exception as e:
        logging.error(f"Ana program hatası: {e}")

    finally:
        if scraper:
            scraper.cleanup()


def print_usage():
    """Kullanım bilgilerini yazdırır"""
    print("\nFBRef Web Scraper")
    print("=" * 30)
    print("Kullanım:")
    print("  python main.py all                    # Tüm ligleri scrape et")
    print("  python main.py league 'Premier League' # Belirli ligi scrape et")
    print("  python main.py player <URL>           # Belirli oyuncuyu scrape et")
    print("  python main.py update                 # Mevcut oyuncuları güncelle")
    print("  python main.py stats                  # Veritabanı istatistikleri")
    print("  python main.py test                   # Test modu")
    print("\nÖrnekler:")
    print("  python main.py league 'Trendyol Süper Lig'")
    print("  python main.py player 'https://fbref.com/en/players/e342ad68/Mohamed-Salah'")


if __name__ == "__main__":
    main()