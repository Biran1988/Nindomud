"""
Random gem finds (Section 77), per explicit request: gems can
occasionally turn up while Mining any suitable rock, rather than
getting their own full gathering job or progression track. A flat,
deliberately tiny chance (FIND_CHANCE_PERCENT) rolled on top of a
normal, successful mining attempt -- not instead of it, and not
scaled by pickaxe tier or job level the way mining.ORE_TABLE's own
odds are, since "very rare across the board" was the explicit ask,
not "rare until you're a master miner."

Deliberately distinct from mining.ORE_TABLE's own "a rough quartz" /
"a raw sapphire" / "a raw ruby" / "a raw diamond" entries, which still
feed Gemcutter's existing cutting recipes unchanged -- these bonus
gems are standalone, already-finished items (no further processing,
no crafting job consuming them), so the names deliberately don't
collide: "a quartz" here vs. "a rough quartz" from the ore table, "a
sapphire" here vs. "a raw sapphire" there, and so on.
"""

import random

# (name, rarity, weight, color) -- weight is relative only to other
# gems in this table, not mixed into mining.ORE_TABLE's own weighting.
# Rarity follows the project's existing common/uncommon/rare/epic/
# legendary tiers (for the standard rarity-colored display), separate
# from each gem's own natural color (used in its description).
GEM_TABLE = [
    ("a quartz", "uncommon", 30, "clear"),
    ("a jade", "uncommon", 25, "green"),
    ("an amber", "rare", 15, "golden orange"),
    ("a garnet", "rare", 12, "deep red"),
    ("an amethyst", "rare", 10, "purple"),
    ("a topaz", "rare", 8, "golden yellow"),
    ("a sapphire", "epic", 5, "blue"),
    ("an emerald", "epic", 4, "vivid green"),
    ("a ruby", "epic", 3, "red"),
    ("a diamond", "legendary", 1, "brilliant clear"),
]

# Flat and deliberately tiny -- "very rare across the board", the same
# for a level-1 miner with a basic pickaxe as a level-100 miner with a
# chakra steel one. Unlike mining's own fail chance/rarity odds, this
# is NOT adjusted by job level or pickaxe tier at all.
FIND_CHANCE_PERCENT = 3


def roll_bonus_gem():
    """Rolled once per SUCCESSFUL mining attempt (not a failed one --
    see commands.cmd_mine). Returns (name, rarity) if a bonus gem
    turned up this time, or None most of the time. A found gem is an
    EXTRA on top of the normal ore/ingot result, not a replacement
    for it."""
    if random.randint(1, 100) > FIND_CHANCE_PERCENT:
        return None
    weights = [entry[2] for entry in GEM_TABLE]
    name, rarity, _, _color = random.choices(GEM_TABLE, weights=weights, k=1)[0]
    return name, rarity
