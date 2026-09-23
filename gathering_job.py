"""
Shared gathering-job logic (Section 71) -- factored out of fishing.py,
mining.py, lumberjack.py, and farming.py per direct request ("look for
redundant/dead files" -> confirmed scope: "look for genuine code
duplication/redundancy across files (copy-pasted logic, near-identical
functions) and consolidate it").

All four of those modules were built independently across earlier
sessions but ended up with the exact same shape: a biome-gate check, a
tool-required-level lookup, a fail-chance roll, and a level-gated
weighted find table. Only the actual DATA (which biomes, what the tool
dict is called, what's in the find table) and farming's own fail-chance
formula genuinely differ between them -- everything else was a literal
copy-paste with names swapped.

This module holds that shared logic ONCE. Each job module still keeps
its own public function names exactly as they were (can_fish_here,
attempt_catch, etc.) -- callers throughout commands.py reference those
specific names, so changing the public API would mean touching every
call site for a purely cosmetic win, which isn't worth the added risk.
Instead each job module's own functions become a thin one-line
delegation into this shared implementation.

Not used by cooking.py -- cooking's own shape (a pot tier, a quality
roll, a burn chance) is genuinely different from the other four's
"one tool, weighted level-gated find table" pattern, not just
differently-named the same logic, so it was left as its own file
rather than forced into this shared shape.
"""

import random


def can_gather_here(biome: str, valid_biomes: set) -> bool:
    """Shared body of can_fish_here/can_mine_here/can_chop_here/
    can_farm_here -- true if biome is one this job can be performed
    in."""
    return biome in valid_biomes


def tool_required_level(tool_name: str, tools: dict):
    """Shared body of every job's own tool_required_level -- the
    level needed to use a given tool, or None if tool_name isn't a
    recognized tool for this job at all."""
    tool = tools.get(tool_name)
    return tool["required_level"] if tool else None


def fail_chance(job_level: int, base: int, floor: int, level_divisor: int = 2) -> int:
    """Shared body of every job's own _fail_chance -- decreases with
    job level, weather-adjusted, never below floor. level_divisor
    defaults to 2 (fishing/mining/lumberjack's own convention);
    farming.py is the one real exception, using 4 instead -- a
    genuine behavioral difference preserved here as a parameter
    rather than silently unified away."""
    import weather
    result = base - job_level // level_divisor
    return max(floor, result + weather.gathering_fail_chance_modifier())


def attempt_gather(job_level: int, base: int, floor: int, find_table: list, level_divisor: int = 2) -> dict:
    """Shared body of every job's own attempt_catch/attempt_mine/
    attempt_chop/attempt_farm. A real chance to come up with nothing,
    decreasing with job level but never reaching zero (fail_chance
    above). On a successful attempt, which item you get is a weighted
    random choice among every find_table entry your level has
    unlocked -- find_table entries are (name, required_level, weight,
    xp) tuples, matching every job module's own FIND_TABLE shape
    exactly. Returns {"failed": True} on a failed attempt, or
    {"failed": False, "name", "xp"} on a find."""
    if random.randint(1, 100) <= fail_chance(job_level, base, floor, level_divisor):
        return {"failed": True}
    available = [(name, weight, xp) for name, required, weight, xp in find_table if job_level >= required]
    name, _, xp = random.choices(available, weights=[w for _, w, _ in available], k=1)[0]
    return {"failed": False, "name": name, "xp": xp}
