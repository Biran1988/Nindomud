"""Original Nindo MUD techniques for elemental Kekkei Genkai.

The three tiers share Ice Release's damage, cost and cooldown curve.
Each entry supplies a combat effect and its own fixed hand-sign sequence.
Dust Release is the level-100 Kekkei Tota exception, with higher costs.
"""

ARTS = {
    "wood_release": (
        ("Wood Splinter Barrage", "off_balance", 25, ("Snake", "Ram", "Tiger")),
        ("Wood Binding Roots", "weakened", 45, ("Snake", "Ox", "Ram", "Dog")),
        ("Deep Forest Bloom", "drained", 35, ("Snake", "Ram", "Dragon", "Tiger", "Dog")),
    ),
    "storm_release": (
        ("Laser Current", "drained", 25, ("Ox", "Hare", "Dragon")),
        ("Guiding Lightning", "paralyzed", 45, ("Ox", "Hare", "Monkey", "Dragon")),
        ("Storm Dragon Torrent", "off_balance", 35, ("Ox", "Monkey", "Dragon", "Ram", "Tiger")),
    ),
    "boil_release": (
        ("Scalding Spray", "burning", 25, ("Horse", "Dragon", "Ram")),
        ("Vapor Cloak Burst", "blinded", 45, ("Horse", "Ox", "Snake", "Tiger")),
        ("Corrosive Steam Wave", "weakened", 35, ("Horse", "Dragon", "Ox", "Ram", "Tiger")),
    ),
    "lava_release": (
        ("Molten Pebbles", "burning", 25, ("Snake", "Horse", "Boar")),
        ("Lava Snare", "off_balance", 45, ("Snake", "Boar", "Horse", "Dog")),
        ("Magma Torrent", "burning", 35, ("Snake", "Boar", "Dragon", "Horse", "Tiger")),
    ),
    "scorch_release": (
        ("Heat Needle", "burning", 25, ("Tiger", "Hare", "Horse")),
        ("Scorching Mirage", "blinded", 45, ("Tiger", "Horse", "Ram", "Snake")),
        ("Burning Horizon", "burning", 35, ("Tiger", "Hare", "Horse", "Dragon", "Ram")),
    ),
    "magnet_release": (
        ("Iron Sand Volley", "off_balance", 25, ("Snake", "Ox", "Dog")),
        ("Magnetic Bind", "paralyzed", 45, ("Snake", "Dog", "Ox", "Ram")),
        ("Iron Sand Maelstrom", "blinded", 35, ("Snake", "Ox", "Dog", "Dragon", "Tiger")),
    ),
    "explosion_release": (
        ("Blast Clay Shot", "off_balance", 25, ("Boar", "Tiger", "Horse")),
        ("Detonation Field", "blinded", 45, ("Boar", "Horse", "Snake", "Tiger")),
        ("Blast Cascade", "stunned", 35, ("Boar", "Horse", "Dragon", "Ram", "Tiger")),
    ),
    "flashfire_release": (
        ("Flash Spark", "burning", 25, ("Horse", "Ox", "Hare")),
        ("Blazing Pulse", "blinded", 45, ("Horse", "Ox", "Monkey", "Tiger")),
        ("Flashfire Storm", "burning", 35, ("Horse", "Ox", "Monkey", "Dragon", "Tiger")),
    ),
    "tempest_release": (
        ("Gale Spark", "off_balance", 25, ("Tiger", "Hare", "Ox")),
        ("Thunderhead Bind", "paralyzed", 45, ("Tiger", "Ox", "Monkey", "Dragon")),
        ("Tempest Lance", "blinded", 35, ("Tiger", "Hare", "Ox", "Dragon", "Ram")),
    ),
    "dust_release": (
        ("Particle Spear", "off_balance", 30, ("Snake", "Boar", "Tiger", "Dragon")),
        ("Particle Cage", "paralyzed", 35, ("Snake", "Ram", "Boar", "Tiger", "Dragon")),
        ("Atomic Dissolution", "weakened", 40, ("Snake", "Boar", "Dragon", "Ram", "Tiger", "Ox")),
    ),
}

ICE_TIERS = (
    (25, (30, 48), 24, 5.0, 2),
    (45, (38, 62), 42, 14.0, 3),
    (70, (85, 125), 78, 24.0, 5),
)
DUST_TIERS = (
    (100, (95, 130), 105, 16.0, 5),
    (100, (105, 140), 125, 22.0, 5),
    (100, (115, 150), 150, 28.0, 5),
)


def jutsu_entries() -> dict:
    entries = {}
    for release_id, techniques in ARTS.items():
        tiers = DUST_TIERS if release_id == "dust_release" else ICE_TIERS
        for (name, effect, chance, _signs), (level, damage, cost, cooldown, tier) in zip(techniques, tiers):
            key = name.lower()
            entries[key] = {
                "jutsu_id": release_id + "_" + key.replace(" ", "_"),
                "display_name": name, "class_requirement": "ninjutsu",
                "level_requirement": level, "chakra_cost": cost,
                "stamina_cost": 0, "cooldown": cooldown, "damage": damage,
                "damage_type": "chakra", "effect": effect,
                "effect_chance_pct": chance, "tier": tier,
                "element": "none", "kkg_gate": release_id,
            }
    return entries


def handsigns() -> dict:
    return {name.lower(): list(signs)
            for techniques in ARTS.values()
            for name, _effect, _chance, signs in techniques}
