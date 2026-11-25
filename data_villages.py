"""
Village data table (Section 46).

Kept fully data-driven so village behavior (start room, hospital, headband,
Kage title) never needs to be hardcoded into chargen, combat, or defeat
logic -- new villages, or later ally/enemy relationships, are just new
rows here.
"""

VILLAGES = {
    "leaf": {
        "village_id": 1,
        "village_name": "Konohagakure",
        "village_short_name": "Konoha",
        "kage_title": "Hokage",
        "starting_room_vnum": 1,
        "hospital_room_vnum": 1,
        "default_headband_vnum": 9001,
        "default_reputation": 0,
        "ally_villages": [],
        "enemy_villages": [],
        "restricted_areas": [],
    },
    "stone": {
        "village_id": 2,
        "village_name": "Iwagakure",
        "village_short_name": "Iwa",
        "kage_title": "Tsuchikage",
        "starting_room_vnum": 2501,
        "hospital_room_vnum": 2501,
        "default_headband_vnum": 9002,
        "default_reputation": 0,
        "ally_villages": [],
        "enemy_villages": [],
        "restricted_areas": [],
    },
    "water": {
        "village_id": 3,
        "village_name": "Kirigakure",
        "village_short_name": "Kiri",
        "kage_title": "Mizukage",
        "starting_room_vnum": 5001,
        "hospital_room_vnum": 5001,
        "default_headband_vnum": 9003,
        "default_reputation": 0,
        "ally_villages": [],
        "enemy_villages": [],
        "restricted_areas": [],
    },
    "cloud": {
        "village_id": 4,
        "village_name": "Kumogakure",
        "village_short_name": "Kumo",
        "kage_title": "Raikage",
        "starting_room_vnum": 7501,
        "hospital_room_vnum": 7501,
        "default_headband_vnum": 9004,
        "default_reputation": 0,
        "ally_villages": [],
        "enemy_villages": [],
        "restricted_areas": [],
    },
    "sand": {
        "village_id": 5,
        "village_name": "Sunagakure",
        "village_short_name": "Suna",
        "kage_title": "Kazekage",
        "starting_room_vnum": 10001,
        "hospital_room_vnum": 10001,
        "default_headband_vnum": 9005,
        "default_reputation": 0,
        "ally_villages": [],
        "enemy_villages": [],
        "restricted_areas": [],
    },
    "whirlpool": {
        "village_id": 6,
        "village_name": "Uzushiogakure",
        "village_short_name": "Uzushio",
        "kage_title": "Whirlpool Leader",
        "starting_room_vnum": 80001,
        "hospital_room_vnum": 80001,
        "area_end_vnum": 82500,
        "default_headband_vnum": 9006,
        "default_reputation": 0,
        "ally_villages": [],
        "enemy_villages": [],
        "restricted_areas": [],
        "hidden_at_creation": True,
    },
    "grass": {
        "village_id": 7, "village_name": "Kusagakure", "village_short_name": "Kusa",
        "kage_title": "Kusa Village Leader", "starting_room_vnum": 12501,
        "hospital_room_vnum": 12501, "area_end_vnum": 13500, "area_key": "land of grass",
        "default_headband_vnum": 12951, "rank_headband_base": 12952,
        "default_reputation": 0, "ally_villages": [], "enemy_villages": [],
        "restricted_areas": [], "hidden_at_creation": True,
    },
    "rain": {
        "village_id": 8, "village_name": "Amegakure", "village_short_name": "Ame",
        "kage_title": "Ame Village Leader", "starting_room_vnum": 13501,
        "hospital_room_vnum": 13501, "area_end_vnum": 14500, "area_key": "land of rain",
        "default_headband_vnum": 13951, "rank_headband_base": 13952,
        "default_reputation": 0, "ally_villages": [], "enemy_villages": [],
        "restricted_areas": [], "hidden_at_creation": True,
    },
    "waterfall": {
        "village_id": 9, "village_name": "Takigakure", "village_short_name": "Taki",
        "kage_title": "Taki Village Leader", "starting_room_vnum": 16501,
        "hospital_room_vnum": 16501, "area_end_vnum": 17500, "area_key": "land of waterfalls",
        "default_headband_vnum": 16951, "rank_headband_base": 16952,
        "default_reputation": 0, "ally_villages": [], "enemy_villages": [],
        "restricted_areas": [], "hidden_at_creation": True,
    },
    "sound": {
        "village_id": 10, "village_name": "Otogakure", "village_short_name": "Oto",
        "kage_title": "Oto Village Leader", "starting_room_vnum": 17501,
        "hospital_room_vnum": 17501, "area_end_vnum": 18500, "area_key": "land of sound",
        "default_headband_vnum": 17951, "rank_headband_base": 17952,
        "default_reputation": 0, "ally_villages": [], "enemy_villages": [],
        "restricted_areas": [], "hidden_at_creation": True,
    },
    "frost": {
        "village_id": 11, "village_name": "Shimogakure", "village_short_name": "Shimo",
        "kage_title": "Shimo Village Leader", "starting_room_vnum": 18501,
        "hospital_room_vnum": 18501, "area_end_vnum": 19500, "area_key": "land of frost",
        "default_headband_vnum": 18951, "rank_headband_base": 18952,
        "default_reputation": 0, "ally_villages": [], "enemy_villages": [],
        "restricted_areas": [], "hidden_at_creation": True,
    },
    "hotwater": {
        "village_id": 12, "village_name": "Yugakure", "village_short_name": "Yu",
        "kage_title": "Yu Village Leader", "starting_room_vnum": 19501,
        "hospital_room_vnum": 19501, "area_end_vnum": 20500, "area_key": "land of hot water",
        "default_headband_vnum": 19951, "rank_headband_base": 19952,
        "default_reputation": 0, "ally_villages": [], "enemy_villages": [],
        "restricted_areas": [], "hidden_at_creation": True,
    },
    "rock": {
        "village_id": 13, "village_name": "Ishigakure", "village_short_name": "Ishi",
        "kage_title": "Ishi Village Leader", "starting_room_vnum": 82501,
        "hospital_room_vnum": 82501, "area_end_vnum": 85000, "area_key": "rock",
        "default_headband_vnum": 82951, "rank_headband_base": 82952,
        "default_reputation": 0, "ally_villages": [], "enemy_villages": [],
        "restricted_areas": [], "hidden_at_creation": True,
        # Retired selection: retain IDs and saved-character compatibility.
        "retired_at_creation": True,
    },
    "moon": {
        "village_id": 14, "village_name": "Tsukigakure", "village_short_name": "Tsuki",
        "kage_title": "Tsuki Village Leader", "starting_room_vnum": 85001,
        "hospital_room_vnum": 85001, "area_end_vnum": 87500, "area_key": "moon",
        "default_headband_vnum": 85451, "rank_headband_base": 85452,
        "default_reputation": 0, "ally_villages": [], "enemy_villages": [],
        "restricted_areas": [], "hidden_at_creation": True,
    },
}


def resolve_village_key(value: str):
    key = value.strip().casefold()
    if key in VILLAGES:
        return key if not VILLAGES[key].get("retired_at_creation") else None
    return next((name for name, info in VILLAGES.items()
                 if not info.get("retired_at_creation") and key in
                 (info['village_name'].casefold(), info['village_short_name'].casefold())), None)


def village_names_display() -> str:
    # Same xterm-256 color per village already used for village names in
    # the who list (commands.VILLAGE_FULL_NAME_COLORS) and the login
    # banner (ascii_art.VILLAGE_COLORS) -- duplicated here rather than
    # imported, since commands.py already imports FROM this module and
    # importing back would be circular. Just the first of each pair, for
    # a clean solid color here rather than the flashier alternating
    # per-letter effect used in those two other places.
    colors = {"leaf": 34, "cloud": 33, "water": 38, "sand": 214, "stone": 130}
    lines = []
    for key, v in VILLAGES.items():
        if v.get("hidden_at_creation", False):
            continue
        color = colors.get(key, 255)
        lines.append(f"  &[{color}]{key:8s} - {v['village_name']}&x")
    return "\n".join(lines)
