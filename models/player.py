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
        name_parts = name.split(" ") if name else ["Unknown"]
        self.data["firstName"] = name_parts[0] if name_parts else "Unknown"
        self.data["lastName"] = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
        self.data["fullName"] = name or "Unknown Player"
        self.data["age"] = age or 0
        self.data["team"] = team or "Unknown Team"
        self.data["league"] = league or "Unknown League"
        self.data["fbrefId"] = fbref_id

    def set_physical_info(self, height, weight, preferred_foot):
        """Fiziksel bilgileri ayarla"""
        self.data["height"] = height or ""
        self.data["weight"] = weight or ""
        self.data["preferredFoot"] = preferred_foot or ""

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
        self.data["similarPlayers"] = similar_players or []

    def set_transfer_history(self, transfers):
        """Transfer geçmişini ayarla"""
        self.data["transferHistory"] = transfers or []

    def update_timestamp(self):
        """Güncelleme zamanını ayarla"""
        self.data["updatedAt"] = datetime.utcnow()

    def to_dict(self):
        """Sözlük formatında döndür"""
        return self.data

    def validate(self):
        """Gelişmiş veri doğrulaması"""
        # Kritik alanlar - bu alanlar mutlaka dolu olmalı
        critical_fields = ["fbrefId", "fullName"]

        for field in critical_fields:
            value = self.data.get(field)
            if not value or (isinstance(value, str) and value.strip() == ""):
                return False, f"Kritik alan eksik veya boş: {field}"

        # Opsiyonel ama önemli alanlar - uyarı ver ama başarısız sayma
        important_fields = ["team", "league"]
        warnings = []

        for field in important_fields:
            value = self.data.get(field)
            if not value or (isinstance(value, str) and value.strip() == ""):
                warnings.append(f"Önemli alan eksik: {field}")

        # FBRef ID formatı kontrolü
        fbref_id = self.data.get("fbrefId", "")
        if fbref_id and not self._is_valid_fbref_id(fbref_id):
            return False, f"Geçersiz FBRef ID formatı: {fbref_id}"

        # Yaş kontrolü
        age = self.data.get("age", 0)
        if age and (age < 15 or age > 50):
            warnings.append(f"Şüpheli yaş değeri: {age}")

        # Uyarıları logla ama başarılı olarak döndür
        if warnings:
            import logging
            for warning in warnings:
                logging.warning(f"Validation warning: {warning}")

        return True, "OK"

    def _is_valid_fbref_id(self, fbref_id):
        """FBRef ID formatını kontrol eder"""
        import re
        # FBRef ID 8 karakterli hexadecimal string olmalı
        pattern = r'^[a-f0-9]{8}$'
        return bool(re.match(pattern, fbref_id))

    def get_summary(self):
        """Oyuncu özetini döndürür"""
        return {
            "name": self.data.get("fullName", "Unknown"),
            "team": self.data.get("team", "Unknown"),
            "league": self.data.get("league", "Unknown"),
            "position": self.data.get("detailedPosition", "Unknown"),
            "age": self.data.get("age", 0),
            "fbrefId": self.data.get("fbrefId", ""),
            "hasStats": bool(self.data.get("seasonStats", {})),
            "hasScouting": bool(self.data.get("scoutingReport", {})),
            "updatedAt": self.data.get("updatedAt")
        }