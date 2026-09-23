"""
Mining (Section 63a) -- the second job on jobs.py's generic leveling
framework.

REDESIGNED per explicit request ("going in a different direction with
crafting ... remove the rarity in jobs items ... 1 item per type ...
make rarity of getting the item based on player level ... for now a
single copper pickaxe/tool is enough to mine and level determines
what you get ... more of a minecraft system"). Previously: 6 tiered
pickaxes and 24 ore/gem species each with their own Common-through-
Legendary rarity ladder (a "which rarity did I roll" system). Now:
ONE tool (a copper pickaxe, no tier progression for now), and every
material is a single, non-tiered item -- no more "Common Iron Ore"
vs. "Uncommon Iron Ore" variants of the same thing, just "An Iron
Ore". Progression instead comes from your Mining LEVEL directly
unlocking access to better materials (FIND_TABLE below), Minecraft-
style, rather than a tool tier shifting the odds of a random rarity
roll on a fixed set of materials.

Requires a pickaxe (bought) and standing in a mountain biome (see
MINEABLE_BIOMES).

Smelting (an iron ore -> an iron ingot, etc.) is unchanged in shape --
still gated by Mining level -- since the ore/ingot naming already
matched the "1 item per type" principle this whole redesign is
built around. Smelting is genuinely mining-specific (no equivalent in
fishing/lumberjack/farming), so it stays in this file rather than
moving into the shared gathering_job.py module below.

The actual gather-attempt/fail-chance/tool-lookup logic (everything
BELOW the smelting section) is shared with fishing.py/lumberjack.py/
farming.py -- see gathering_job.py, factored out since all four
modules had it as an identical copy-paste with only names/data
swapped. Public function names here are kept exactly as they were
before that refactor (can_mine_here, tool_required_level,
attempt_mine) -- commands.py calls these by name directly, so the
public surface intentionally didn't change, only the implementation
behind it.
"""

import gathering_job

MINEABLE_BIOMES = {"mountain"}

# Deliberately just one tool for now, per explicit request -- more
# tiers may return once the broader crafting revamp this is part of
# is further along.
PICKAXES = {
    "a copper pickaxe": {"required_level": 1},
}

# Every material Mining can find, each a single, non-tiered item.
# Mining level directly gates which of these are even reachable at
# all (Minecraft-style progression) -- weight only matters among
# whatever's already unlocked at the player's current level. Ordered
# low to high; xp scales with how hard-won a material is to reach.
FIND_TABLE = [
    ("an iron ore", 1, 60, 15),
    ("a rough quartz", 1, 40, 15),
    ("a steel ore", 20, 30, 40),
    ("a raw sapphire", 25, 20, 40),
    ("a chakra steel ore", 50, 12, 100),
    ("a raw ruby", 55, 8, 100),
    ("a raw diamond", 80, 2, 300),
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
    return gathering_job.attempt_gather(job_level, FAIL_CHANCE_BASE, FAIL_CHANCE_FLOOR, FIND_TABLE)


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
