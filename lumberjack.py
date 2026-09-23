"""
Lumberjack (Section 63b) -- a gathering job on jobs.py's framework.

REDESIGNED per explicit request (same "Minecraft-style" crafting
revamp as mining.py): ONE tool (a copper axe), every material is a
single, non-tiered item -- no more "Common Pine Log" vs. "Uncommon
Pine Log" variants. Progression comes from Lumberjack LEVEL directly
unlocking access to better wood (FIND_TABLE), not a tool tier shifting
a rarity roll.

Requires an axe (bought) and standing in a forest biome.

The actual gather-attempt/fail-chance/tool-lookup logic is shared
with fishing.py/mining.py/farming.py -- see gathering_job.py, factored
out since all four modules had it as an identical copy-paste with
only names/data swapped. Public function names here are kept exactly
as they were before that refactor (can_chop_here, tool_required_level,
attempt_chop) -- commands.py calls these by name directly, so the
public surface intentionally didn't change, only the implementation
behind it.
"""

import gathering_job

CHOPPABLE_BIOMES = {"forest"}

AXES = {
    "a copper axe": {"required_level": 1},
}

FIND_TABLE = [
    ("a bundle of kindling", 1, 60, 5),
    ("a birch branch", 1, 40, 8),
    ("a sturdy oak log", 15, 25, 25),
    ("an ironwood log", 35, 15, 60),
    ("a masterwork oak log", 60, 6, 150),
    ("an ancient heartwood log", 85, 2, 400),
]

FAIL_CHANCE_BASE = 20
FAIL_CHANCE_FLOOR = 2


def can_chop_here(biome: str) -> bool:
    return gathering_job.can_gather_here(biome, CHOPPABLE_BIOMES)


def tool_required_level(tool_name: str):
    return gathering_job.tool_required_level(tool_name, AXES)


def attempt_chop(job_level: int, tool_name: str) -> dict:
    return gathering_job.attempt_gather(job_level, FAIL_CHANCE_BASE, FAIL_CHANCE_FLOOR, FIND_TABLE)
