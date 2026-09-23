"""
Farming (Section 70) -- a gathering job on jobs.py's framework.

REDESIGNED per explicit request (same "Minecraft-style" crafting
revamp as mining.py/lumberjack.py): ONE tool (a copper hoe), every
crop is a single, non-tiered item. Progression comes from Farming
LEVEL directly unlocking access to better crops (FIND_TABLE).

Requires a hoe (bought) and standing in a plains biome.

The actual gather-attempt/fail-chance/tool-lookup logic is shared
with fishing.py/mining.py/lumberjack.py -- see gathering_job.py,
factored out since those three modules had it as an identical
copy-paste with only names/data swapped. Farming's own fail-chance
formula genuinely differs from the other three (job_level // 4 here,
not // 2, and a floor of 3 rather than 2) -- gathering_job.fail_chance
takes both as explicit parameters specifically so this real
difference stays intact rather than getting silently unified away.
Public function names here are kept exactly as they were before that
refactor (can_farm_here, tool_required_level, attempt_farm) --
commands.py calls these by name directly, so the public surface
intentionally didn't change, only the implementation behind it.
"""

import gathering_job

FARMABLE_BIOMES = {"plains"}

HOES = {
    "a copper hoe": {"required_level": 1},
}

FIND_TABLE = [
    ("a carrot", 1, 50, 5),
    ("a potato", 1, 50, 5),
    ("a tomato", 10, 30, 15),
    ("an onion", 10, 30, 15),
    ("a pumpkin", 30, 15, 40),
    ("a watermelon", 30, 15, 40),
    ("a corn", 55, 8, 100),
    ("a pepper", 80, 3, 300),
]

FAIL_CHANCE_BASE = 20
FAIL_CHANCE_FLOOR = 3
FAIL_CHANCE_LEVEL_DIVISOR = 4  # genuinely different from fishing/mining/lumberjack's own 2 -- preserved exactly


def can_farm_here(biome: str) -> bool:
    return gathering_job.can_gather_here(biome, FARMABLE_BIOMES)


def tool_required_level(tool_name: str):
    return gathering_job.tool_required_level(tool_name, HOES)


def attempt_farm(job_level: int, tool_name: str) -> dict:
    return gathering_job.attempt_gather(
        job_level, FAIL_CHANCE_BASE, FAIL_CHANCE_FLOOR, FIND_TABLE,
        level_divisor=FAIL_CHANCE_LEVEL_DIVISOR,
    )
