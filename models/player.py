from datetime import datetime
from typing import List, Dict, Optional


class PlayerModel:
    def __init__(self):
        self.data = {
            "fbrefId": "",
            "firstName": "",
            "lastName": "",
            "fullName": "",
            "age": 0,
            "contractEnd": "",
            "preferredFoot": "",
            "team": "",
            "league": "",
            "country": "",
            "height": "",
            "weight": "",
            "detailedPosition": "",
            "photo": "",
            "similarPlayers": [],
            "seasonStats": {},
            "scoutingReport": {},
            "transferHistory": [],
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow()
        }

    def set_basic_info(self, name, age, team, league, fbref_id):
        """Temel bilgileri ayarla"""
        name_parts = name.split(" ")
        self.data["firstName"] = name_parts[0] if name_parts else ""
        self.data["lastName"] = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
        self.data["fullName"] = name
        self.data["age"] = age
        self.data["team"] = team
        self.data["league"] = league
        self.data["fbrefId"] = fbref_id

    def set_physical_info(self, height, weight, preferred_foot):
        """Fiziksel bilgileri ayarla"""
        self.data["height"] = height
        self.data["weight"] = weight
        self.data["preferredFoot"] = preferred_foot

    def set_season_stats(self, stats_dict):
        """Sezon istatistiklerini ayarla"""
        self.data["seasonStats"] = {
            "standardStats": stats_dict.get("standard", {}),
            "shooting": stats_dict.get("shooting", {}),
            "passing": stats_dict.get("passing", {}),
            "passTypes": stats_dict.get("pass_types", {}),
            "goalShotCreation": stats_dict.get("gsc", {}),
            "defensiveActions": stats_dict.get("defense", {}),
            "possession": stats_dict.get("possession", {}),
            "miscellaneous": stats_dict.get("misc", {})
        }

    def set_scouting_report(self, scouting_dict):
        """Scouting raporunu ayarla"""
        self.data["scoutingReport"] = {
            "standardStats": scouting_dict.get("standard", {}),
            "shooting": scouting_dict.get("shooting", {}),
            "passing": scouting_dict.get("passing", {}),
            "passTypes": scouting_dict.get("pass_types", {}),
            "goalShotCreation": scouting_dict.get("gsc", {}),
            "defensiveActions": scouting_dict.get("defense", {}),
            "possession": scouting_dict.get("possession", {}),
            "miscellaneous": scouting_dict.get("misc", {})
        }

    def set_similar_players(self, similar_players):
        """Benzer oyuncuları ayarla"""
        self.data["similarPlayers"] = similar_players

    def set_transfer_history(self, transfers):
        """Transfer geçmişini ayarla"""
        self.data["transferHistory"] = transfers

    def update_timestamp(self):
        """Güncelleme zamanını ayarla"""
        self.data["updatedAt"] = datetime.utcnow()

    def to_dict(self):
        """Sözlük formatında döndür"""
        return self.data

    def validate(self):
        """Veri doğrulaması"""
        required_fields = ["fbrefId", "fullName", "team", "league"]
        for field in required_fields:
            if not self.data.get(field):
                return False, f"Gerekli alan eksik: {field}"
        return True, "OK"