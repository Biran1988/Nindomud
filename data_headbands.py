"""Rank-specific village headbands.

Headband bonuses live in item prototypes, while display colors use the
registered rarity. Five ordinary ranks and the appointed Kage rank each
have a headband; promotion replaces the equipped headband and its bonuses.
"""

from typing import Optional

# Same RANK_ORDER as kage.py, duplicated as a plain tuple here rather
# than imported, to avoid a circular import (kage.py doesn't need to
# know anything about headbands to keep working -- see
# apply_rank_headband below, which IS the one place that imports both).
RANK_ORDER = ["student", "genin", "chunin", "special jonin", "jonin", "kage"]

# Progressively larger Armor Class bonus per rank. The starting Student rank stays
# at the existing headband's original 0 bonus (purely cosmetic) so
# nothing about the very first headband a player ever gets changes.
RANK_HEADBAND_AC_BONUS = {
    "student": 0,
    "genin": 2,
    "chunin": 4,
    "special jonin": 6,
    "jonin": 10,
    "kage": 14,
}

# Which of the 5 existing rarity tiers each rank's headband is colored
# as when displayed (rarity_colored_name, already wired in everywhere
# an item name is shown). students and genin share the lowest
# tier, since there's no tier below "common".
RANK_HEADBAND_RARITY = {
    "student": "common",
    "genin": "common",
    "chunin": "uncommon",
    "special jonin": "rare",
    "jonin": "legendary",
    "kage": "legendary",
}

# The rank-specific part of the headband's name -- "" for a
# student, so its name stays exactly "A Konoha Headband" (no rank
# word, no stat suffix, since its bonus is 0).
RANK_HEADBAND_TITLE = {
    "student": "",
    "genin": "Genin Headband",
    "chunin": "Chunin Headband",
    "special jonin": "Special Jonin Headband",
    "jonin": "Jonin Headband",
    "kage": "Kage's Headband",
}


def headband_base_name(village_short_name: str, rank: str) -> str:
    """The stored item name for a village + rank's headband -- e.g.
    'A Konoha Genin Headband'. Deliberately carries no stat text of
    any kind -- the Armor Class bonus lives entirely in the item
    prototype's own stat_bonuses field (set in content.py right after
    this name is registered), per explicit request ("never ever put
    stats in the name of the item or description"). This is what
    actually lives in player.inventory/player.equipment (items are
    plain strings in this project); color is applied only at display
    time via the item's own registered rarity (see this module's own
    docstring)."""
    title = RANK_HEADBAND_TITLE.get(rank, "")
    return f"A {village_short_name} {title}".strip() if title else f"A {village_short_name} Headband"


def apply_rank_headband(player, rank: str) -> Optional[str]:
    """Swaps the player's currently-equipped headband for the one
    matching `rank`, if their village has one registered for it.
    Removes the old headband from equipment entirely (it does NOT go
    back to inventory -- only the current rank's headband applies) and equips the new one directly. Returns the
    new headband's name for the caller to announce, or None if rank
    isn't a recognized headband tier.

    Called from the exam, promotion and Kage appointment paths."""
    import data_villages

    if rank not in RANK_HEADBAND_TITLE:
        return None
    village_data = data_villages.VILLAGES.get(player.village)
    if not village_data:
        return None
    new_headband = headband_base_name(village_data["village_short_name"], rank)
    import commands
    old_headband = player.equipment.get("head")
    if old_headband:
        commands._apply_equipment_stat_bonuses(player, old_headband, sign=-1)
    player.equipment["head"] = new_headband
    commands._apply_equipment_stat_bonuses(player, new_headband, sign=1)
    return new_headband
