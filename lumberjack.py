"""Lumberjack profession with overlapping four-tier axe progression.

Copper gathers through Sturdy Oak; Ironbound Oak through Ironwood;
Steel Ironwood through Ancient Heartwood; the finest Heartwood Axe
also unlocks the rare Yew Log at Lumberjack level 95.
"""

import gathering_job

CHOPPABLE_BIOMES = {"forest"}

AXES = {
    "a copper axe": {"required_level": 1, "max_resource_level": 15, "tier": 0},
    "an ironbound oak axe": {"required_level": 15, "max_resource_level": 35, "tier": 1},
    "a steel ironwood axe": {"required_level": 35, "max_resource_level": 85, "tier": 2},
    "a chakra steel heartwood axe": {"required_level": 75, "max_resource_level": 95, "tier": 3},
}

FIND_TABLE = [
    ("a bundle of kindling", 1, 60, 5),
    ("a birch branch", 1, 40, 8),
    ("a sturdy oak log", 15, 25, 25),
    ("an ironwood log", 35, 15, 60),
    ("a masterwork oak log", 60, 6, 150),
    ("an ancient heartwood log", 85, 2, 400),
    ("a yew log", 95, 1, 500),
]

FAIL_CHANCE_BASE = 20
FAIL_CHANCE_FLOOR = 2


def can_chop_here(biome: str) -> bool:
    return gathering_job.can_gather_here(biome, CHOPPABLE_BIOMES)


def tool_required_level(tool_name: str):
    return gathering_job.tool_required_level(tool_name, AXES)


def attempt_chop(job_level: int, tool_name: str) -> dict:
    tool = AXES.get(tool_name.lower())
    if tool is None:
        raise ValueError("Unknown lumber axe")
    return gathering_job.attempt_gather(job_level, FAIL_CHANCE_BASE, FAIL_CHANCE_FLOOR, FIND_TABLE,
                                        max_resource_level=tool["max_resource_level"], tier=tool["tier"])
