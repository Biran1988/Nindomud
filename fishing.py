"""
Fishing (Section 61b) -- the first job on jobs.py's framework.

REDESIGNED per explicit request (same "Minecraft-style" crafting
revamp as mining.py/lumberjack.py/farming.py): ONE tool (a kindling
fishing rod), every fish is a single, non-tiered item -- no more
"Common Sardine" vs. "Legendary Sardine" variants of the same
species. Progression comes from Fishing LEVEL directly unlocking
access to better fish species (FIND_TABLE).

Requires a fishing rod (bought) and standing in a water biome.

The actual gather-attempt/fail-chance/tool-lookup logic is shared
with mining.py/lumberjack.py/farming.py -- see gathering_job.py,
factored out since all four modules had it as an identical copy-paste
with only names/data swapped. Public function names here are kept
exactly as they were before that refactor (can_fish_here,
rod_required_level, attempt_catch) -- commands.py calls these by name
directly, so the public surface intentionally didn't change, only the
implementation behind it.
"""

import gathering_job

WATER_BIOMES = {"ocean", "river", "lake", "swamp"}

RODS = {
    "a kindling fishing rod": {"required_level": 1},
}

FIND_TABLE = [
    ("a minnow", 1, 60, 5),
    ("a sardine", 1, 40, 8),
    ("a trout", 15, 25, 20),
    ("a bass", 25, 20, 35),
    ("a salmon", 40, 12, 60),
    ("a swordfish", 55, 8, 100),
    ("a koi", 75, 4, 200),
    ("a leviathan", 90, 1, 500),
]

FAIL_CHANCE_BASE = 20
FAIL_CHANCE_FLOOR = 2


def can_fish_here(biome: str) -> bool:
    return gathering_job.can_gather_here(biome, WATER_BIOMES)


def rod_required_level(rod_name: str):
    return gathering_job.tool_required_level(rod_name, RODS)


def attempt_catch(job_level: int, rod_name: str) -> dict:
    return gathering_job.attempt_gather(job_level, FAIL_CHANCE_BASE, FAIL_CHANCE_FLOOR, FIND_TABLE)
