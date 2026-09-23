"""
Cooking (Section 67) -- a job on jobs.py's framework. Takes a raw
fish (Fishing's own catches) and produces a cooked dish.

REDESIGNED per explicit request (same "Minecraft-style" crafting
revamp as the other 4 jobs): ONE tool (a copper cooking pot), no
quality tiers on the output -- a raw fish always produces the same
cooked dish. The progression axis is now purely that higher-level
fish (which Fishing's own level gating unlocks) produce more valuable
dishes, not a quality roll on the same dish.

Requires a cooking pot held (or standing in own apartment kitchen),
and a raw fish in inventory.
"""

import random

BURN_CHANCE_BASE = 25
BURN_CHANCE_FLOOR = 3

POTS = {
    "a copper cooking pot": {"required_level": 1},
}

# Maps a raw fish name (from fishing.FIND_TABLE) to its cooked dish
# name and base sell cost. Every fish has exactly one dish -- no
# quality tiers anymore.
INGREDIENTS = {
    "a minnow": {"dish": "A Cooked Minnow", "base_cost": 4},
    "a sardine": {"dish": "A Cooked Sardine", "base_cost": 6},
    "a trout": {"dish": "A Cooked Trout", "base_cost": 30},
    "a bass": {"dish": "A Cooked Bass", "base_cost": 36},
    "a salmon": {"dish": "A Cooked Salmon", "base_cost": 200},
    "a swordfish": {"dish": "A Cooked Swordfish", "base_cost": 300},
    "a koi": {"dish": "A Cooked Golden Koi", "base_cost": 2000},
    "a leviathan": {"dish": "A Leviathan Fillet", "base_cost": 20000},
}

# XP from cooking scales with the fish's own level requirement
# (higher-level fish are worth more to cook), matching the pattern
# the gathering jobs use.
COOKING_XP = {
    "a minnow": 10,
    "a sardine": 12,
    "a trout": 25,
    "a bass": 35,
    "a salmon": 60,
    "a swordfish": 100,
    "a koi": 200,
    "a leviathan": 500,
}


def pot_required_level(pot_name: str):
    pot = POTS.get(pot_name.lower() if pot_name else "")
    return pot["required_level"] if pot else None


def _burn_chance(job_level: int) -> int:
    import weather
    return max(BURN_CHANCE_FLOOR, BURN_CHANCE_BASE - job_level // 3 + weather.gathering_fail_chance_modifier())


def attempt_cook(job_level: int, ingredient_name: str, pot_name: str) -> dict:
    """Resolves one cooking attempt. Returns {"burned": True} on a
    burnt attempt, or {"burned": False, "name", "xp"} on success."""
    ingredient = INGREDIENTS.get(ingredient_name.lower())
    if ingredient is None:
        return {"burned": True}
    if random.randint(1, 100) <= _burn_chance(job_level):
        return {"burned": True}
    xp = COOKING_XP.get(ingredient_name.lower(), 10)
    return {"burned": False, "name": ingredient["dish"], "xp": xp}


def price_for_dish(item_name: str):
    """Returns the sell price for a cooked dish, or None if not
    recognized -- lets cmd_sell fall back to flat category pricing."""
    name_lower = item_name.lower()
    for data in INGREDIENTS.values():
        if data["dish"].lower() in name_lower:
            return data["base_cost"]
    return None
