"""
Rank headbands.

Extends the existing village headband (previously a single, purely
cosmetic item per village, granted once at chargen and never touched
again) into a full progression matching kage.RANK_ORDER, per explicit
request: each rank gets its own headband, colored distinctly, with a
progressively larger stat bonus.

Reuses the exact same "(+N Armor Class)" name-suffix mechanism every
other piece of armor in the game already uses (see commands.
craft_stat_bonus_suffix / parse_crafted_bonus) -- no new combat wiring
was needed at all, since commands.equipped_armor_class_bonus() already
sums this bonus across every worn slot, "head" included. "Colored"
reuses the existing 5-tier rarity system (data_rarity.py) the same
way, since that's the one color mechanism already wired into every
place an item's name is displayed (inventory, equipment, sell,
etc.) -- rather than inventing a second, parallel coloring system
that would only work in the one or two places built to know about it.
7 ranks don't map 1:1 onto 5 rarity tiers, so the two lowest and two
highest ranks share a tier with their neighbor (see
RANK_HEADBAND_RARITY below) -- everything in between gets its own.

IMPORTANT CAVEAT, stated plainly: kage.PROMOTIONS_ENABLED is currently
False, so no player can currently be promoted past genin through
normal play -- see kage.py's own comment on why. The chunin-and-above
headbands built here are fully real, functional items (registered,
correctly stat-boosted, correctly colored, and wired into
kage.handle_promotion_request so a promotion swaps the headband
automatically), but nothing in the game currently grants them to a
player, since the promotions that would is switched off. They're
ready the moment that flag flips back on.
"""

from typing import Optional

# Same RANK_ORDER as kage.py, duplicated as a plain tuple here rather
# than imported, to avoid a circular import (kage.py doesn't need to
# know anything about headbands to keep working -- see
# apply_rank_headband below, which IS the one place that imports both).
RANK_ORDER = ["academy student", "genin", "chunin", "special jonin", "jonin", "elite jonin", "village elder", "kage"]

# Progressively larger Armor Class bonus per rank. academy student stays
# at the existing headband's original 0 bonus (purely cosmetic) so
# nothing about the very first headband a player ever gets changes.
RANK_HEADBAND_AC_BONUS = {
    "academy student": 0,
    "genin": 2,
    "chunin": 4,
    "special jonin": 6,
    "jonin": 8,
    "elite jonin": 10,
    "village elder": 12,
    "kage": 14,
}

# Which of the 5 existing rarity tiers each rank's headband is colored
# as when displayed (rarity_colored_name, already wired in everywhere
# an item name is shown). academy student and genin share the lowest
# tier, since there's no tier below "common".
RANK_HEADBAND_RARITY = {
    "academy student": "common",
    "genin": "common",
    "chunin": "uncommon",
    "special jonin": "rare",
    "jonin": "epic",
    "elite jonin": "legendary",
    "village elder": "legendary",
    "kage": "legendary",
}

# The rank-specific part of the headband's name -- "" for academy
# student, so its name stays exactly "A Konoha Headband" (no rank
# word, no stat suffix, since its bonus is 0).
RANK_HEADBAND_TITLE = {
    "academy student": "",
    "genin": "Genin Headband",
    "chunin": "Chunin Headband",
    "special jonin": "Special Jonin Headband",
    "jonin": "Jonin Headband",
    "elite jonin": "Elite Jonin Headband",
    "village elder": "Elder's Headband",
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
    back to inventory -- ranks only ever move forward, so there's
    nothing to preserve) and equips the new one directly. Returns the
    new headband's name for the caller to announce, or None if rank
    isn't a recognized headband tier.

    Called from kage.handle_promotion_request() -- currently
    unreachable in normal play while promotions are disabled, but
    wired in correctly for when they aren't."""
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
