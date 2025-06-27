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
            # Pozisyona göre scouting report - artık nested object
            "scoutingReport": {
                "positions": {},  # Her pozisyon için ayrı data
                "defaultPosition": "",  # Ana pozisyon
                "lastUpdated": datetime.utcnow()
            },
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

    def set_scouting_report_for_position(self, position, scouting_dict):
        """Belirli bir pozisyon için scouting raporunu ayarla"""
        if not self.data["scoutingReport"]["positions"]:
            self.data["scoutingReport"]["positions"] = {}

        # Pozisyon isimlerini normalize et
        normalized_position = self.normalize_position_name(position)

        self.data["scoutingReport"]["positions"][normalized_position] = {
            "standardStats": scouting_dict.get("standard", {}),
            "shooting": scouting_dict.get("shooting", {}),
            "passing": scouting_dict.get("passing", {}),
            "passTypes": scouting_dict.get("pass_types", {}),
            "goalShotCreation": scouting_dict.get("gsc", {}),
            "defensiveActions": scouting_dict.get("defense", {}),
            "possession": scouting_dict.get("possession", {}),
            "miscellaneous": scouting_dict.get("misc", {}),
            "lastUpdated": datetime.utcnow()
        }

        # İlk pozisyon default pozisyon olsun
        if not self.data["scoutingReport"]["defaultPosition"]:
            self.data["scoutingReport"]["defaultPosition"] = normalized_position

    def set_scouting_report_flat(self, scouting_dict, position=None):
        """Düz scouting verisi için - pozisyon belirtilmemişse default pozisyona ata"""
        if not position:
            # Oyuncunun ana pozisyonunu kullan
            position = self.determine_main_position()

        normalized_position = self.normalize_position_name(position)

        if not self.data["scoutingReport"]["positions"]:
            self.data["scoutingReport"]["positions"] = {}

        self.data["scoutingReport"]["positions"][normalized_position] = scouting_dict

        # Default pozisyon ayarla
        if not self.data["scoutingReport"]["defaultPosition"]:
            self.data["scoutingReport"]["defaultPosition"] = normalized_position

        self.data["scoutingReport"]["lastUpdated"] = datetime.utcnow()

    def normalize_position_name(self, position):
        """Pozisyon isimlerini normalize et"""
        if not position:
            return "Unknown"

        pos_lower = str(position).lower().strip()

        # Pozisyon mapping'i
        position_mappings = {
            # Attackers/Forwards
            'fw': 'Forward',
            'forward': 'Forward',
            'cf': 'Center Forward',
            'st': 'Striker',
            'striker': 'Striker',
            'lw': 'Left Winger',
            'rw': 'Right Winger',
            'winger': 'Winger',
            'left winger': 'Left Winger',
            'right winger': 'Right Winger',

            # Midfielders
            'mf': 'Midfielder',
            'midfielder': 'Midfielder',
            'cm': 'Central Midfielder',
            'cdm': 'Defensive Midfielder',
            'cam': 'Attacking Midfielder',
            'dm': 'Defensive Midfielder',
            'am': 'Attacking Midfielder',
            'lm': 'Left Midfielder',
            'rm': 'Right Midfielder',

            # Defenders
            'df': 'Defender',
            'defender': 'Defender',
            'cb': 'Center Back',
            'lb': 'Left Back',
            'rb': 'Right Back',
            'wb': 'Wing Back',
            'lwb': 'Left Wing Back',
            'rwb': 'Right Wing Back',

            # Goalkeeper
            'gk': 'Goalkeeper',
            'goalkeeper': 'Goalkeeper'
        }

        # Önce tam eşleşme ara
        if pos_lower in position_mappings:
            return position_mappings[pos_lower]

        # Kısmi eşleşme ara
        for key, value in position_mappings.items():
            if key in pos_lower:
                return value

        # Eşleşme bulunamazsa orijinal pozisyonu döndür (capitalize edilmiş)
        return position.title()

    def determine_main_position(self):
        """Oyuncunun ana pozisyonunu belirle"""
        detailed_pos = self.data.get("detailedPosition", "")

        if not detailed_pos:
            return "Unknown"

        # "fw-mf (am-wm" gibi karmaşık pozisyonlardan ana pozisyonu çıkar
        # İlk kısmı al (fw-mf'den fw'yi)
        main_part = detailed_pos.split('(')[0].strip()

        if '-' in main_part:
            # "fw-mf" gibi birleşik pozisyonlarda ilk kısmı al
            primary = main_part.split('-')[0].strip()
        else:
            primary = main_part

        return self.normalize_position_name(primary)

    def get_scouting_for_position(self, position=None):
        """Belirli bir pozisyon için scouting raporunu getir"""
        if not position:
            position = self.data["scoutingReport"].get("defaultPosition", "")

        normalized_position = self.normalize_position_name(position)

        positions_data = self.data["scoutingReport"].get("positions", {})
        return positions_data.get(normalized_position, {})

    def get_all_scouting_positions(self):
        """Mevcut tüm scouting pozisyonlarını getir"""
        return list(self.data["scoutingReport"].get("positions", {}).keys())

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
        positions = self.get_all_scouting_positions()
        return {
            "name": self.data.get("fullName", "Unknown"),
            "team": self.data.get("team", "Unknown"),
            "league": self.data.get("league", "Unknown"),
            "position": self.data.get("detailedPosition", "Unknown"),
            "age": self.data.get("age", 0),
            "fbrefId": self.data.get("fbrefId", ""),
            "hasStats": bool(self.data.get("seasonStats", {})),
            "scoutingPositions": positions,
            "defaultScoutingPosition": self.data["scoutingReport"].get("defaultPosition", ""),
            "updatedAt": self.data.get("updatedAt")
        }