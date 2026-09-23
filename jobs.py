"""
Job leveling (Section 61) -- a RuneScape-style progression track
completely separate from ninja level/experience (leveling.py). A
player's ninja level governs jutsu, HP/chakra/stamina, and combat
stats; job levels govern gathering/crafting professions instead, and
advance purely by doing that profession's activity, not by fighting or
completing missions.

Generic across any job name -- Player.job_levels/job_xp (models.py)
are plain dicts keyed by job name, so adding a job needs no new Player
fields, just a new entry in JOB_NAMES and that job's own tool tiers/
loot table in its own module (see fishing.py, the first one, and
mining.py/lumberjack.py, structured identically to it). Weaponsmith/
Armorsmith/Gemcutter are crafting-only jobs -- no gathering command of
their own, just crafting.py recipes consuming what Mining/Lumberjack
produce.

Job level cap matches the ninja level cap (100) for consistency, but
uses its OWN xp curve (job_xp_for_level), tuned independently from
leveling.py's ninja curve -- gathering professions in games like this
are usually meant to feel like a slower, steadier grind than combat
leveling, not an identical curve reused wholesale.
"""

JOB_NAMES = [
    "fishing", "mining", "lumberjack", "weaponsmith", "armorsmith", "gemcutter", "cooking",
    "farming",
]  # future suggestions: seal_crafting, summoning_taming

# Per explicit request ("remove blacksmith and weapon smith or hide
# them for now"): Weaponsmith and Armorsmith have had zero recipes
# since the crafting revamp (see weaponsmith.py/armorsmith.py's own
# docstrings) -- there's currently nothing a player can actually do
# with either. Hidden from player-facing job listings (see
# commands.build_jobs_lines) rather than removed from JOB_NAMES
# outright, so job_levels data and the Max Chakra stat bonus both stay
# fully intact underneath -- easy to reverse once the new crafting
# system gives these jobs something to do again.
HIDDEN_JOBS = {"weaponsmith", "armorsmith"}
# Jobs are crafting/gathering side content -- unlocking materials and
# minor items -- not a parallel track to ninja progression itself;
# keep new jobs in that lane (see Alchemy's removal: potions that
# meaningfully restored health/chakra encroached on ninja resource
# management, which is a step too far for what a job should provide).

MAX_JOB_LEVEL = 100

# xp cost of each incremental level, per level number (level 2 costs
# XP_PER_LEVEL_FACTOR * 1, level 3 costs XP_PER_LEVEL_FACTOR * 2, and so
# on) -- 5x the original 50, per explicit request, making job leveling
# a slower grind than before across the whole curve uniformly.
XP_PER_LEVEL_FACTOR = 250


def job_xp_for_level(level: int) -> int:
    """Total cumulative xp needed to REACH `level` (level 1 = 0 xp).
    A gentler, steadier curve than ninja leveling -- gathering
    professions are meant to be a slow grind, not a race."""
    if level <= 1:
        return 0
    return int(sum(XP_PER_LEVEL_FACTOR * lvl for lvl in range(1, level)))


def get_job_level(player, job: str) -> int:
    return player.job_levels.get(job, 1)


def get_job_xp(player, job: str) -> int:
    return player.job_xp.get(job, 0)


ACTION_STAMINA_COST_MIN = 1
ACTION_STAMINA_COST_MAX = 2


def try_deduct_action_stamina(player) -> bool:
    """Rolls a random 1-2 stamina cost (per explicit request) and
    deducts it if the player has enough -- used by every job action
    (fishing/mining/lumberjack/farming/cooking/crafting) right before
    committing to the action, the same way combat.py deducts a jutsu's
    stamina cost when it's used, not when it resolves. Returns False
    (deducting nothing) if the player doesn't have enough; the caller
    is responsible for refusing the action and telling the player."""
    import random
    cost = random.randint(ACTION_STAMINA_COST_MIN, ACTION_STAMINA_COST_MAX)
    if player.stamina < cost:
        return False
    player.stamina -= cost
    return True


# Per direct request ("make wood cutting and mining increase stamina
# by the same metric farming does, cooking weaponsmith and armorsmith
# both increase chakra"): the exact same stacking mechanism Farming's
# Max Health bonus already used (see add_job_xp below), just applied
# to a different resource pool per job. Maps a job name to
# (maximum_<pool> field, current <pool> field, display label).
JOB_STAT_BONUS = {
    "farming": ("maximum_stamina", "stamina", "Max Stamina", 1),
    "lumberjack": ("maximum_stamina", "stamina", "Max Stamina", 1),
    "mining": ("maximum_stamina", "stamina", "Max Stamina", 1),
    "cooking": ("maximum_chakra", "chakra", "Max Chakra", 1),
    "weaponsmith": ("maximum_chakra", "chakra", "Max Chakra", 1),
    "armorsmith": ("maximum_chakra", "chakra", "Max Chakra", 1),
    "gemcutter": ("maximum_health", "health", "Max Health", 2),
}


def add_job_xp(player, job: str, amount: int) -> list:
    """Adds xp to `job`, handling level-ups (possibly several at once).
    Returns messages to show the player; empty if no level-up occurred."""
    if job not in JOB_NAMES:
        return []

    messages = []
    current_level = get_job_level(player, job)
    if current_level >= MAX_JOB_LEVEL:
        return []

    new_xp = get_job_xp(player, job) + amount
    player.job_xp[job] = new_xp

    new_level = current_level
    stat_gained = 0
    stat_multiplier = JOB_STAT_BONUS[job][3] if job in JOB_STAT_BONUS else 1
    if job in JOB_STAT_BONUS and job not in player.job_levels:
        # Level 1 is an implicit default (get_job_level returns 1 when
        # the key isn't present at all) -- a player is never actually
        # "leveled up" to it via the loop below, so without crediting
        # it here the running total would start from level 2 instead
        # of level 1, undercounting the triangular sum by 1 forever.
        stat_gained += 1 * stat_multiplier
    while new_level < MAX_JOB_LEVEL and new_xp >= job_xp_for_level(new_level + 1):
        new_level += 1
        # Stacks per explicit request: each individual level
        # contributes its own level number, so the running total is
        # the triangular sum (1+2+3+...+N = N*(N+1)/2) -- e.g. level
        # 23 means +276 total, not +23. Tracked per-level here (not as
        # a single lump sum for however many levels this xp gain
        # crosses) since each level contributes a different amount
        # from the last. Multiplied by the job's own rate (Gemcutter
        # runs at 2x every other job's own rate, per explicit request).
        if job in JOB_STAT_BONUS:
            stat_gained += new_level * stat_multiplier

    if new_level > current_level or stat_gained:
        if new_level > current_level:
            player.job_levels[job] = new_level
            messages.append(f"&Y*** Your {job.capitalize()} level increased to {new_level}! ***&x")
        else:
            player.job_levels[job] = new_level  # still records the implicit level-1 baseline explicitly
        if stat_gained:
            max_field, current_field, label, _ = JOB_STAT_BONUS[job]
            setattr(player, max_field, getattr(player, max_field) + stat_gained)
            setattr(player, current_field, getattr(player, current_field) + stat_gained)
            messages.append(f"  &R+{stat_gained} {label}&x")

    return messages
