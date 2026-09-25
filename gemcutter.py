"""Gemcutter: cut raw gems from mining with a held Copper Chisel.

Cutting succeeds once the appropriate Gemcutter level and raw gem are
present. Each completed cut uses one charge of the chisel.
"""

CHISELS = {"a copper chisel": {"required_level": 1}}

BONUS_BY_RARITY = {"common": 1, "uncommon": 2, "rare": 3, "epic": 5, "legendary": 8}

# Raw gem -> (cut output, required Gemcutter level, job XP).
RECIPES = {
    "a rough quartz": ("A Cut Quartz", 1, 15),
    "a raw sapphire": ("A Cut Sapphire", 25, 40),
    "a raw ruby": ("A Cut Ruby", 55, 100),
    "a raw diamond": ("A Cut Diamond", 80, 300),
}
