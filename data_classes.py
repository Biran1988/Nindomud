"""
Primary combat class data (Sections 8-9).

Only the levels 1-20 "general ninja training" slice is populated for
now -- elemental/advanced specialization trees are intentionally left
out per Section 48 (systems reserved for later).

Note: primary class no longer determines starting skills (every player
gets the same universal starting kit -- see session.py/data_jutsu.py).
It still governs which jutsu category can be used by bare name (Taijutsu
and Bukijutsu -- both physical, not chakra-incantation techniques) vs
requires 'perform' (Ninjutsu/Genjutsu), even though every player knows
all four active jutsu regardless of their own class.
"""

CLASSES = {
    "taijutsu": {
        "display_name": "Taijutsu",
        "description": (
            "Close-range physical combat: strikes, combinations, and "
            "chakra-enhanced blows."
        ),
        "stat_bonus": {"strength": 4, "dexterity": 4},
    },
    "ninjutsu": {
        "display_name": "Ninjutsu",
        "description": (
            "Non-elemental chakra techniques -- the foundation for "
            "elemental ninjutsu added in a later expansion."
        ),
        "stat_bonus": {"intelligence": 4, "constitution": 4},
    },
    "genjutsu": {
        "display_name": "Genjutsu",
        "description": (
            "Illusion and mental-disruption techniques that confuse and "
            "weaken opponents rather than striking them directly."
        ),
        "stat_bonus": {"intelligence": 4, "wisdom": 4},
    },
    "bukijutsu": {
        "display_name": "Bukijutsu",
        "description": (
            "Weapons and ninja tool arts: swords, shuriken, and other "
            "armaments used with precision rather than raw chakra."
        ),
        "stat_bonus": {"strength": 4, "constitution": 4},
    },
}


def apply_class_stat_bonus(player) -> None:
    """Applies this player's own primary_class stat bonus, per direct
    request/confirmation (Section 123): "add a class bonus for stat
    like genjutsu starts with plus 4 intel and 2 wisdom and do they
    same for other classes" -> confirmed to an even +4/+4 across all
    4 classes (Genjutsu's own initial +4/+2 was corrected to +4/+4 to
    match). Applied ONCE, automatically, at character creation (see
    session._create_player) -- never re-applied later, since a
    player's own primary_class is permanent. Safe no-op if
    primary_class isn't a real, known class."""
    bonus = CLASSES.get(player.primary_class, {}).get("stat_bonus", {})
    for stat_name, amount in bonus.items():
        setattr(player, stat_name, getattr(player, stat_name) + amount)


def class_names_display() -> str:
    # Same colors already used for class tags in the who list
    # (commands.CLASS_WHO_COLOR) -- duplicated rather than imported for
    # the same circular-import reason as village_names_display() above.
    colors = {"taijutsu": "&R", "ninjutsu": "&B", "genjutsu": "&M", "bukijutsu": "&Y"}
    lines = []
    for key, c in CLASSES.items():
        color = colors.get(key, "&W")
        lines.append(f"  {color}{key:10s}&x - {c['description']}")
    return "\n".join(lines)
