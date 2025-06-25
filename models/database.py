from pymongo import MongoClient
from config.settings import Settings
import logging


class DatabaseManager:
    def __init__(self):
        self.client = MongoClient(Settings.MONGODB_URI)
        self.db = self.client[Settings.MONGODB_DB_NAME]
        self.collection = self.db[Settings.MONGODB_COLLECTION]

        # Index oluştur
        self.collection.create_index("fbrefId", unique=True)
        self.collection.create_index("name")
        self.collection.create_index("team")
        self.collection.create_index("league")

    def insert_player(self, player_data):
        """Oyuncu verisini ekle veya güncelle"""
        try:
            result = self.collection.update_one(
                {"fbrefId": player_data["fbrefId"]},
                {"$set": player_data},
                upsert=True
            )
            return result
        except Exception as e:
            logging.error(f"Veritabanı hatası: {e}")
            return None

    def get_player(self, fbref_id):
        """Oyuncu verisini getir"""
        return self.collection.find_one({"fbrefId": fbref_id})

    def get_all_players(self, league=None):
        """Tüm oyuncuları getir"""
        filter_dict = {}
        if league:
            filter_dict["league"] = league
        return list(self.collection.find(filter_dict))

    def close(self):
        """Veritabanı bağlantısını kapat"""
        self.client.close()