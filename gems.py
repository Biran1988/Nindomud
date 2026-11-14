"""Rare bonus gems awarded alongside normal ore on successful Mining.

Every gem here has a matching Gemcutter recipe. Top elemental stones have
identical rarity and weight: fire, water, earth, wind and lightning.
Rough Quartz is NOT part of the normal ore drop table.
"""

import random

# (name, rarity, weight, color) -- weight is relative only to other
# gems in this table, not mixed into mining.ORE_TABLE's own weighting.
# Rarity follows the project's existing common/uncommon/rare/epic/
# legendary tiers (for the standard rarity-colored display), separate
# from each gem's own natural color (used in its description).
GEM_TABLE = [
    ("a rough quartz", "uncommon", 30, "clear"),
    ("a jade", "uncommon", 25, "green"),
    ("an amber", "rare", 15, "golden orange"),
    ("a garnet", "rare", 12, "deep red"),
    ("an amethyst", "epic", 5, "purple"),
    ("a topaz", "epic", 5, "golden yellow"),
    ("a sapphire", "epic", 5, "blue"),
    ("an emerald", "epic", 5, "vivid green"),
    ("a ruby", "epic", 5, "red"),
    ("a diamond", "legendary", 1, "brilliant clear"),
]

# The default chance is still 3% for basic mining. Mining passes a
# tool-specific rate, up to 20% for the top-tier Heartwood pickaxe.
FIND_CHANCE_PERCENT = 3


def roll_bonus_gem(chance_percent: int = FIND_CHANCE_PERCENT):
    """Rolled once per SUCCESSFUL mining attempt (not a failed one --
    see commands.cmd_mine). Returns (name, rarity) if a bonus gem
    turned up this time, or None most of the time. A found gem is an
    EXTRA on top of the normal ore/ingot result, not a replacement
    for it."""
    if random.randint(1, 100) > chance_percent:
        return None
    weights = [entry[2] for entry in GEM_TABLE]
    name, rarity, _, _color = random.choices(GEM_TABLE, weights=weights, k=1)[0]
    return name, rarity
