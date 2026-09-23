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
}


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
        color = colors.get(key, 255)
        lines.append(f"  &[{color}]{key:8s} - {v['village_name']}&x")
    return "\n".join(lines)
