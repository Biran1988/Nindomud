"""Gemcutter: cut every bonus-mining gem and legacy raw gem.

A held Copper Chisel and the Gemcutter job level are required.
The five elemental gems all unlock at level 60 for equal access.
"""
import gem_inlays

CHISELS = {"a copper chisel": {"required_level": 1}}
BONUS_BY_RARITY = {"common": 1, "uncommon": 2, "rare": 3, "epic": 5, "legendary": 8}

# Input gem -> (cut result, Gemcutter minimum job level, job XP).
RECIPES = {
    "a rough quartz": ("A Cut Quartz", 1, 15),
    "a quartz": ("A Cut Quartz", 1, 15),  # legacy bonus-mining quartz
    "a jade": ("A Cut Jade", 10, 25),
    "an amber": ("A Cut Amber", 20, 40),
    "a garnet": ("A Cut Garnet", 30, 55),
    "an amethyst": ("A Cut Amethyst", 60, 110),
    "a topaz": ("A Cut Topaz", 60, 110),
    "a sapphire": ("A Cut Sapphire", 60, 110),
    "an emerald": ("A Cut Emerald", 60, 110),
    "a ruby": ("A Cut Ruby", 60, 110),
    "a diamond": ("A Cut Diamond", 80, 300),
    # Backward-compatible main-table drops created by older releases.
    "a raw sapphire": ("A Cut Sapphire", 60, 110),
    "a raw ruby": ("A Cut Ruby", 60, 110),
    "a raw diamond": ("A Cut Diamond", 80, 300),
}
