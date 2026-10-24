"""One player-chosen combat signature; bonus unlocks at 150% use mastery."""

import math

import data_jutsu


SIGNATURE_CAP = 150
SIGNATURE_BONUS = 1.25

# These attacks use the shared damage/effect resolver. Utility moves below
# have dedicated duration hooks; binary and passive abilities cannot be
# meaningfully made 25% stronger without changing their rules.
ATTACK_TYPES = {"normal", "ambush", "thrown", "fan_art", "blade_strike",
                "sevenfold", "area", "mirror"}
DURATION_TYPES = {"buff", "mist", "disguise", "item_illusion",
                  "item_decoy", "chisei", "room_sleep"}


def eligible(jutsu):
    kind = jutsu.get("jutsu_type", "normal")
    return ((kind in ATTACK_TYPES and jutsu.get("damage") is not None)
            or kind in DURATION_TYPES)


def selected_name(player):
    return getattr(player, "signature_move", "") or ""


def empowered(player, jutsu):
    name = jutsu.get("display_name", "")
    return (eligible(jutsu) and selected_name(player) == name
            and name in player.learned_skills
            and player.skill_proficiencies.get(name, 0) >= SIGNATURE_CAP)


def amount(player, jutsu, amount):
    return max(1, round(amount * SIGNATURE_BONUS)) if empowered(player, jutsu) else amount


def duration(player, jutsu, duration):
    return max(1, math.ceil(duration * SIGNATURE_BONUS)) if empowered(player, jutsu) else duration
