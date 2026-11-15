"""Original Naruto-compatible techniques inspired by popular anime action styles.

These are ordinary class jutsu, not a separate spell engine: unlock by class
and level, cross-class via the existing scroll mechanism, and reuse the same
PvE/PvP combat, cooldown, mastery, chakra/stamina and status systems.
Names, descriptions and mechanics are original Nindo_mud implementations.
"""

# (name, class, level, base chakra, base stamina, cooldown, element, effect,
#  effect chance %, accuracy bonus, required weapon types, inspiration, flavor)
_ARTS = [
    [
        "Dragonfire Pulse",
        "ninjutsu",
        25,
        34,
        0,
        7,
        "fire",
        "burning",
        30,
        0,
        [],
        "Fairy Tail dragon magic",
        "A narrow dragon-shaped burst of fire that leaves lingering flames."
    ],
    [
        "Spirit Cannon",
        "ninjutsu",
        50,
        49,
        0,
        9,
        "none",
        "drained",
        30,
        1,
        [],
        "Dragon Ball focused ki",
        "Condenses raw chakra into a piercing blast that saps the target's reserves."
    ],
    [
        "Lightning Dragon Cascade",
        "ninjutsu",
        75,
        74,
        0,
        12,
        "lightning",
        "paralyzed",
        22,
        0,
        [],
        "Fairy Tail lightning magic",
        "Successive lightning arcs lash the target, threatening brief paralysis."
    ],
    [
        "Celestial Nova Sphere",
        "ninjutsu",
        100,
        110,
        0,
        17,
        "none",
        "off_balance",
        35,
        0,
        [],
        "Dragon Ball energy blasts",
        "A dense chakra sphere detonates on impact and disrupts the enemy's footing."
    ],
    [
        "Flashstep Palm",
        "taijutsu",
        25,
        0,
        18,
        6,
        "none",
        "off_balance",
        35,
        5,
        [],
        "Bleach high-speed movement",
        "An explosive footwork burst ends in an unarmed palm strike."
    ],
    [
        "Breathing Rhythm Rush",
        "taijutsu",
        50,
        0,
        32,
        8,
        "none",
        "bleeding",
        30,
        2,
        [],
        "Demon Slayer rhythmic breathing",
        "A breath-timed rush of unarmed blows that can leave the target bleeding."
    ],
    [
        "Titanbreaker Fist",
        "taijutsu",
        75,
        0,
        52,
        12,
        "none",
        "weakened",
        35,
        0,
        [],
        "Attack on Titan and One Punch Man heavy impacts",
        "A crushing body-powered punch breaks the target's momentum."
    ],
    [
        "Meteor Drive Combo",
        "taijutsu",
        100,
        0,
        76,
        17,
        "none",
        "stunned",
        20,
        1,
        [],
        "My Hero Academia impact combinations",
        "A decisive sequence of fast blows that may briefly stun the opponent."
    ],
    [
        "Phantom Floor Maze",
        "genjutsu",
        25,
        30,
        0,
        7,
        "none",
        "disoriented",
        60,
        0,
        [],
        "Sword Art Online dungeon floors",
        "The foe sees an endless maze of shifting corridors and loses orientation."
    ],
    [
        "Mirrored Guild Hall",
        "genjutsu",
        50,
        47,
        0,
        10,
        "none",
        "confused",
        55,
        0,
        [],
        "Fairy Tail illusion magic",
        "Dozens of reflected allies mislead the foe's senses and timing."
    ],
    [
        "Endless Void Stage",
        "genjutsu",
        75,
        76,
        0,
        14,
        "none",
        "blinded",
        45,
        0,
        [],
        "Jujutsu Kaisen domain illusions",
        "A false boundless stage overloads vision and perception."
    ],
    [
        "Refracted Memory Prison",
        "genjutsu",
        100,
        112,
        0,
        19,
        "none",
        "frightened",
        55,
        0,
        [],
        "Bleach hypnotic perception",
        "The target relives contradictory memories and is shaken by false certainty."
    ],
    [
        "Starstream Sword Dance",
        "bukijutsu",
        25,
        0,
        21,
        7,
        "none",
        "bleeding",
        30,
        2,
        [
            "sword"
        ],
        "Sword Art Online rapid sword combos",
        "A flowing series of cuts with a wielded sword."
    ],
    [
        "Moonfang Draw",
        "bukijutsu",
        50,
        0,
        37,
        9,
        "none",
        "off_balance",
        35,
        4,
        [
            "sword",
            "exotic"
        ],
        "Bleach sword drawing attacks",
        "A single sudden weapon draw catches the enemy off guard."
    ],
    [
        "Ember Breathing Cut",
        "bukijutsu",
        75,
        0,
        54,
        12,
        "none",
        "burning",
        32,
        1,
        [
            "sword"
        ],
        "Demon Slayer breathing sword forms",
        "A heat-trailing sword cut that can kindle a brief burn."
    ],
    [
        "Comet Blade Finale",
        "bukijutsu",
        100,
        0,
        79,
        18,
        "none",
        "stunned",
        22,
        0,
        [
            "sword",
            "exotic"
        ],
        "Sword Art Online high-speed sword finishers",
        "A final accelerated blade strike intended to stagger the opponent."
    ]
]

def jutsu_entries():
    """Return new mutable data entries for the shared jutsu registry."""
    entries = {}
    for (name, school, level, chakra, stamina, cooldown, element, effect,
         chance, accuracy, weapons, _inspiration, _flavor) in _ARTS:
        key = name.lower()
        art = {
            "jutsu_id": "anime_" + school + "_" + key.replace(" ", "_"),
            "display_name": name,
            "class_requirement": school,
            "level_requirement": level,
            "chakra_cost": chakra,
            "stamina_cost": stamina,
            "cooldown": float(cooldown),
            # The shared damage ladder scales this starter range by level;
            # these figures are not separate damage rules or huge multipliers.
            "damage": (20, 32),
            "damage_type": ("mental" if school == "genjutsu" else
                            "physical" if school in ("taijutsu", "bukijutsu")
                            else "chakra"),
            "effect": effect, "effect_chance_pct": chance,
            "accuracy_bonus": accuracy,
            "jutsu_type": "attack",
            "tier": 2 if level <= 25 else 3 if level <= 75 else 4,
            "element": element,
        }
        if weapons:
            art["required_weapon_types"] = tuple(weapons)
        entries[key] = art
    return entries


def help_pages(jutsu):
    """Build synchronized in-game help pages from the ACTUAL scaled jutsu."""
    pages = []
    for (name, school, level, _chakra, _stamina, cooldown, element, effect,
         chance, _accuracy, weapons, _inspiration, flavor) in _ARTS:
        key = name.lower()
        art = jutsu[key]
        syntax = ("" if school in ("bukijutsu", "taijutsu") else "perform ") + key + " <target>"
        resource = "Stamina" if school in ("bukijutsu", "taijutsu") else "Chakra"
        base_cost = art["stamina_cost"] if resource == "Stamina" else art["chakra_cost"]
        requirements = []
        if element != "none":
            requirements.append("Requires your own " + element.capitalize() + " chakra nature.")
        if weapons:
            requirements.append("Requires a wielded " + " or ".join(weapons) + ".")
        requirements.append("The displayed base cost increases with level under standard jutsu scaling.")
        body = (
            "Syntax: " + syntax + "\n\n" + flavor + "\n\n"
            + school.capitalize() + " art. Automatically learned at level " + str(level)
            + " by " + school.capitalize() + " characters; other classes may learn it"
            + " from a legitimate technique scroll under the normal scroll rules. "
            + "Returning eligible characters receive it on login. "
            + "Practice it with a class teacher once before first use.\n\n"
            + "Base " + resource + " cost: " + str(base_cost) + ". Cooldown: "
            + str(cooldown) + " seconds. Scaled base damage: "
            + str(art["damage"][0]) + "-" + str(art["damage"][1])
            + ". " + str(chance) + "% chance to inflict " + effect.replace("_", " ")
            + " on a successful hit. "
            + " ".join(requirements)
            + "\n\nOmit <target> during combat to attack your current opponent."
        )
        pages.append({
            "primary_keyword": key, "keywords": [key],
            "title": name, "body": body,
            "created_by": "System", "updated_by": "System", "updated_at": 0.0,
        })
    summary = [
        "Syntax: help anime arts",
        "",
        "Sixteen original anime-inspired combat arts. Your primary class"
        " learns its four at levels 25, 50, 75 and 100; scrolls can teach"
        " another class's ordinary techniques under existing rules.",
        "All attacks use the standard combat engine. Ninjutsu and Genjutsu"
        " use PERFORM; Taijutsu and Bukijutsu use bare technique names.",
        "First practice with a teacher unless a scroll expressly grants the art.",
        "Each move has its own help topic and cooldown.",
    ]
    for school in ("ninjutsu", "taijutsu", "genjutsu", "bukijutsu"):
        summary += ["", school.capitalize() + ":"]
        summary += ["  Level " + str(lvl) + " - " + name
                    for name, cls, lvl, *_rest in _ARTS if cls == school]
    pages.append({
        "primary_keyword": "anime arts",
        "keywords": ["anime arts", "new jutsu", "anime jutsu"],
        "title": "Anime-Inspired Combat Arts",
        "body": "\n".join(summary),
        "created_by": "System", "updated_by": "System", "updated_at": 0.0,
    })
    return pages
