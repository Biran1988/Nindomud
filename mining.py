"""Mining ores using overlapping copper, iron, steel and chakra-steel tiers.

The primary find table contains only ores. Every gem, including rough
quartz, arrives as a rare additional drop after a successful mine.
"""

import gathering_job

MINEABLE_BIOMES = {"mountain"}

# Deliberately just one tool for now, per explicit request -- more
# tiers may return once the broader crafting revamp this is part of
# is further along.
PICKAXES = {
    "a copper pickaxe": {"required_level": 1, "max_resource_level": 1, "tier": 0},
    "an ironbound oak pickaxe": {"required_level": 15, "max_resource_level": 25, "tier": 1},
    "a steel ironwood pickaxe": {"required_level": 35, "max_resource_level": 55, "tier": 2},
    "a chakra steel heartwood pickaxe": {"required_level": 75, "max_resource_level": 80, "tier": 3},
}

# Every primary Mining material, each a single, non-tiered ore.
# Mining level directly gates which of these are even reachable at
# all (Minecraft-style progression) -- weight only matters among
# whatever's already unlocked at the player's current level. Gems are
# rolled separately by gems.roll_bonus_gem after ore is granted. Ordered
# low to high; xp scales with how hard-won a material is to reach.
FIND_TABLE = [
    ("an iron ore", 1, 60, 15),
    ("a steel ore", 20, 30, 40),
    ("a chakra steel ore", 50, 12, 100),
]

FAIL_CHANCE_BASE = 20   # % chance to fail at Mining level 1, matching fishing/lumberjack's own convention
FAIL_CHANCE_FLOOR = 2   # % chance to fail even at max level -- never guaranteed


def can_mine_here(biome: str) -> bool:
    return gathering_job.can_gather_here(biome, MINEABLE_BIOMES)


def tool_required_level(tool_name: str):
    return gathering_job.tool_required_level(tool_name, PICKAXES)


def attempt_mine(job_level: int, tool_name: str) -> dict:
    """Resolves one mining attempt. A real chance to come up with
    nothing, decreasing with Mining level alone (no tool tiers left to
    factor in) but never reaching zero. On a successful attempt, which
    material you get is determined by your level unlocking access to
    it (FIND_TABLE) -- there's no rarity roll on a single material
    anymore, since each material is just one item now. Returns
    {"failed": True} on a failed attempt, or {"failed": False, "name",
    "xp"} on a find."""
    tool = PICKAXES.get(tool_name.lower())
    if tool is None:
        raise ValueError("Unknown pickaxe")
    return gathering_job.attempt_gather(job_level, FAIL_CHANCE_BASE, FAIL_CHANCE_FLOOR, FIND_TABLE,
                                        max_resource_level=tool["max_resource_level"], tier=tool["tier"])


# Smelting -- converts a raw ore found while mining into the ingot
# every downstream crafting recipe in the game will eventually depend
# on by exact name. Gated by Mining level (matching the ore's own
# FIND_TABLE requirement above). Deliberately always succeeds once the
# level and material checks pass -- the randomness already happened at
# the mining step that produced the ore.
SMELTING_RECIPES = {
    "an iron ore": {"ingot": "an iron ingot", "required_level": 1},
    "a steel ore": {"ingot": "a steel ingot", "required_level": 20},
    "a chakra steel ore": {"ingot": "a chakra steel ingot", "required_level": 50},
}


def smelt_required_level(ore_name: str):
    recipe = SMELTING_RECIPES.get(ore_name.lower())
    return recipe["required_level"] if recipe else None


def smelt_ore(ore_name: str) -> str:
    """Returns the ingot name a given ore smelts into. Raises KeyError
    if ore_name isn't a smeltable ore -- callers are expected to have
    already validated this via SMELTING_RECIPES."""
    return SMELTING_RECIPES[ore_name.lower()]["ingot"]
