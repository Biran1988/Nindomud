"""
Mission system (Sections 18-19).

Two D-Rank missions per village now: the original "kill" type (defeat N
of a village-specific mob template) and a new "gather" type (collect N
of an item via a dedicated action, then deliver them to a specific mob
to turn in) -- e.g. pulling weeds and handing them to a villager.
mission_type distinguishes them ("kill" vs "gather"); a "gather"
mission's own action command (see commands.cmd_pullweeds/cmd_deliver)
drives its progress instead of on_mob_defeated.

Missions are repeatable -- completing one starts a cooldown before it
can be accepted again, tracked per-player in Player.mission_cooldowns.
Each mission can override how long that cooldown is via its own
cooldown_seconds field; missions without one fall back to
config.MISSION_COOLDOWN_SECONDS. completed_missions keeps growing with
each completion (a full history, not a unique-set), so repeat
completions still count toward things like the Kage promotion ladder's
"completed mission count" requirement.
"""

import time
from typing import List

import config
from data_villages import VILLAGES
from models import Player

# village -> list of mission definitions (was a single dict per village;
# restructured to a list once a second mission per village was added).
MISSIONS = {
    "whirlpool": [
        {
            "mission_id": "whirlpool_d1", "rank": "D-Rank", "village": "whirlpool",
            "mission_type": "kill", "title": "Guard the Coast",
            "description": "Defeat 3 wandering bandits near the Uzushio coast.",
            "target_mob_template": 5006, "target_count": 1,
            "reward_xp": 200, "reward_ryo": 40, "reward_mission_points": 1,
        },
        {
            "mission_id": "whirlpool_d2", "rank": "D-Rank", "village": "whirlpool",
            "mission_type": "gather", "title": "Weed the Garden",
            "description": "Deliver 5 bundles of weeds to an Uzushio villager.",
            "target_item": "a bundle of weeds", "target_count": 5,
            "delivery_mob_template": 6055,
            "reward_xp": 80, "reward_ryo": 20, "reward_mission_points": 1,
            "cooldown_seconds": 1200,
        },
    ],
    "leaf": [
        {
            "mission_id": "leaf_d1", "rank": "D-Rank", "village": "leaf",
            "mission_type": "kill",
            "title": "Clear the Outskirts",
            "description": "Defeat 3 wandering bandits near the Konoha outskirts.",
            "target_mob_template": 5001, "target_count": 1,
            "reward_xp": 200, "reward_ryo": 40, "reward_mission_points": 1,
        },
        {
            "mission_id": "leaf_d2", "rank": "D-Rank", "village": "leaf",
            "mission_type": "gather",
            "title": "Weed the Garden",
            "description": "Pull 5 bundles of weeds at a villager's house near "
                            "Konoha, then deliver them to the villager.",
            "target_item": "a bundle of weeds", "target_count": 5,
            "delivery_mob_template": 6005,
            "reward_xp": 80, "reward_ryo": 20, "reward_mission_points": 1,
            "cooldown_seconds": 1200,  # 20 minutes, not the usual 10
        },
    ],
    "stone": [
        {
            "mission_id": "stone_d1", "rank": "D-Rank", "village": "stone",
            "mission_type": "kill",
            "title": "Clear the Outskirts",
            "description": "Defeat 3 wandering bandits near the Iwa outskirts.",
            "target_mob_template": 5002, "target_count": 1,
            "reward_xp": 200, "reward_ryo": 40, "reward_mission_points": 1,
        },
        {
            "mission_id": "stone_d2", "rank": "D-Rank", "village": "stone",
            "mission_type": "gather",
            "title": "Weed the Garden",
            "description": "Pull 5 bundles of weeds at a villager's house near "
                            "Iwa, then deliver them to the villager.",
            "target_item": "a bundle of weeds", "target_count": 5,
            "delivery_mob_template": 6015,
            "reward_xp": 80, "reward_ryo": 20, "reward_mission_points": 1,
            "cooldown_seconds": 1200,
        },
    ],
    "water": [
        {
            "mission_id": "water_d1", "rank": "D-Rank", "village": "water",
            "mission_type": "kill",
            "title": "Clear the Outskirts",
            "description": "Defeat 3 wandering bandits near the Kiri outskirts.",
            "target_mob_template": 5003, "target_count": 1,
            "reward_xp": 200, "reward_ryo": 40, "reward_mission_points": 1,
        },
        {
            "mission_id": "water_d2", "rank": "D-Rank", "village": "water",
            "mission_type": "gather",
            "title": "Weed the Garden",
            "description": "Pull 5 bundles of weeds at a villager's house near "
                            "Kiri, then deliver them to the villager.",
            "target_item": "a bundle of weeds", "target_count": 5,
            "delivery_mob_template": 6025,
            "reward_xp": 80, "reward_ryo": 20, "reward_mission_points": 1,
            "cooldown_seconds": 1200,
        },
    ],
    "cloud": [
        {
            "mission_id": "cloud_d1", "rank": "D-Rank", "village": "cloud",
            "mission_type": "kill",
            "title": "Clear the Outskirts",
            "description": "Defeat 3 wandering bandits near the Kumo outskirts.",
            "target_mob_template": 5004, "target_count": 1,
            "reward_xp": 200, "reward_ryo": 40, "reward_mission_points": 1,
        },
        {
            "mission_id": "cloud_d2", "rank": "D-Rank", "village": "cloud",
            "mission_type": "gather",
            "title": "Weed the Garden",
            "description": "Pull 5 bundles of weeds at a villager's house near "
                            "Kumo, then deliver them to the villager.",
            "target_item": "a bundle of weeds", "target_count": 5,
            "delivery_mob_template": 6035,
            "reward_xp": 80, "reward_ryo": 20, "reward_mission_points": 1,
            "cooldown_seconds": 1200,
        },
    ],
    "sand": [
        {
            "mission_id": "sand_d1", "rank": "D-Rank", "village": "sand",
            "mission_type": "kill",
            "title": "Clear the Outskirts",
            "description": "Defeat 3 wandering bandits near the Suna outskirts.",
            "target_mob_template": 5005, "target_count": 1,
            "reward_xp": 200, "reward_ryo": 40, "reward_mission_points": 1,
        },
        {
            "mission_id": "sand_d2", "rank": "D-Rank", "village": "sand",
            "mission_type": "gather",
            "title": "Weed the Garden",
            "description": "Pull 5 bundles of weeds at a villager's house near "
                            "Suna, then deliver them to the villager.",
            "target_item": "a bundle of weeds", "target_count": 5,
            "delivery_mob_template": 6045,
            "reward_xp": 80, "reward_ryo": 20, "reward_mission_points": 1,
            "cooldown_seconds": 1200,
        },
    ],
}

# Higher mission ranks (Section 69) -- C/B/A/S, one per village, added
# on top of the hand-written D-Rank missions above. C/B/A/S ranks are
# no longer static board postings -- per direct follow-up request
# ("instead of a static board you request what mission difficulty you
# want and it will select from a pool of mobs within your level range
# dependent on what you picked"), a player instead REQUESTS a rank
# (see request_mission below) and one Mission-flagged mob (see
# olc.VALID_MOB_ACT_FLAGS) whose own level falls within that rank's
# level-range window (relative to the player's CURRENT level, not a
# fixed target) is picked at random from the pool. D-Rank is
# deliberately left untouched above -- per direct design confirmation
# ("Keep the low level static missions for players to get started
# with"), it stays exactly as it always was.
#
MISSION_DURATION_SECONDS = 30 * 60  # Real time; keeps counting while offline.

# (rank, id_suffix, min_level, target_count, reward_xp, reward_ryo,
#  reward_mission_points, cooldown_seconds)
_HIGHER_RANK_DEFS = [
    ("D-Rank", "d1", 1, 1, 200, 40, 1, 600),
    ("C-Rank", "c1", 10, 1, 500, 100, 2, 900),
    ("B-Rank", "b1", 25, 1, 1200, 250, 3, 1200),
    ("A-Rank", "a1", 50, 1, 3000, 600, 5, 1800),
    ("S-Rank", "s1", 80, 1, 8000, 1500, 10, 2700),
]
_HIGHER_RANK_BY_NAME = {d[0]: d for d in _HIGHER_RANK_DEFS}

# Each Mission-tagged mob has ONE rank relative to the requesting player.
# These bands deliberately never overlap. As the player levels up,
# the same mob naturally moves S -> A -> B -> C -> D; once it has
# become easier than D's upper boundary, it remains eligible for D.
# A minimum ninja level still applies when requesting each rank.
#
# Rank bands are keyed by (mob_level - player_level):
#     D: <= +5 (including any weaker enemy)
#     C: +6 through +20
#     B: +21 through +40
#     A: +41 through +70
#     S: +71 or higher
# The maximum mob level is 250; levels 1..250 remain classifiable at
# every player level without wrapping top-level enemies into S-rank.
RANK_LEVEL_OFFSETS = {
    "D-Rank": (None, 5),
    "C-Rank": (6, 20),
    "B-Rank": (21, 40),
    "A-Rank": (41, 70),
    "S-Rank": (71, None),
}
MAX_CHARACTER_LEVEL = 250


def level_window_for_rank(player_level: int, rank: str):
    """Inclusive mob-level range for the requested rank.

    A missing lower offset means every weaker mob remains D-rank;
    a missing upper offset means every harder mob is S-rank. Ranges
    may be empty at very high ninja levels, which correctly means
    there are no higher-level Mission-tagged enemies in the world.
    """
    lo_offset, hi_offset = RANK_LEVEL_OFFSETS[rank]
    lo = 1 if lo_offset is None else player_level + lo_offset
    hi = MAX_CHARACTER_LEVEL if hi_offset is None else min(
        MAX_CHARACTER_LEVEL, player_level + hi_offset)
    return lo, hi


def mission_rank_for_levels(player_level: int, mob_level: int):
    """Classify a real mob once, exclusively, relative to a ninja."""
    if not isinstance(mob_level, int) or not 1 <= mob_level <= MAX_CHARACTER_LEVEL:
        return None
    for rank in RANK_LEVEL_OFFSETS:
        lo, hi = level_window_for_rank(player_level, rank)
        if lo <= mob_level <= hi:
            return rank
    return None


def pick_mission_mob(player: Player, rank: str):
    """Choose among globally registered Mission-flagged mobs in ONE band.

    No mob can match two ranks for the same player. A target's rank is
    computed when the mission is assigned; a current active mission
    keeps its chosen target, progress, and rewards if the player levels.
    """
    import random
    import combat

    if rank not in RANK_LEVEL_OFFSETS:
        return None, None
    window_lo, window_hi = level_window_for_rank(player.level, rank)
    candidates = [
        (vnum, t) for vnum, t in combat.MOB_TEMPLATES.items()
        if ("Mission" in t.get("act_flags", [])
            and isinstance(t.get("level"), int)
            and window_lo <= t["level"] <= window_hi
            and 1 <= t["level"] <= MAX_CHARACTER_LEVEL)
    ]
    if not candidates:
        return None, None
    return random.choice(candidates)

def request_mission(player: Player, rank: str) -> str:
    """Requests a dynamic C/B/A/S rank mission (see module docstring
    at the top of this file's C/B/A/S section) -- picks a real
    Mission-flagged mob via pick_mission_mob, builds a fully self-
    contained mission dict (not a static lookup, since there's no
    fixed definition for a dynamically-picked target), and adds it to
    the player's active_missions. Returns a human-readable result,
    same convention as accept_mission for the static D-Rank path."""
    import time as time_module

    rank_input = rank.strip()
    if rank_input.lower().endswith("-rank"):
        rank_letter = rank_input[:-len("-rank")]
    else:
        rank_letter = rank_input
    rank = f"{rank_letter.upper()}-Rank"
    rank_def = _HIGHER_RANK_BY_NAME.get(rank)
    if not rank_def:
        return f"'{rank}' isn't a valid mission rank. Valid: D-Rank, C-Rank, B-Rank, A-Rank, S-Rank."
    _, _, min_level, target_count, reward_xp, reward_ryo, reward_mp, cooldown_seconds = rank_def

    if player.level < min_level:
        return f"You must be at least level {min_level} to request a {rank} mission."

    cooldown_key = f"dynamic_{rank}"
    remaining = cooldown_remaining(player, cooldown_key)
    if remaining > 0:
        return f"You've requested a {rank} mission too recently. You can request another in {_format_duration(remaining)}."
    if any((_resolve_mission(m) or {}).get("rank") == rank
           for m in player.active_missions):
        return f"You already have an active {rank} mission -- finish or abandon it first."

    mob_vnum, mob = pick_mission_mob(player, rank)
    if not mob:
        return f"No {rank} mission is available for your level right now -- try again later, or a different rank."

    mission = {
        "mission_id": f"dynamic_{rank}_{mob_vnum}_{int(time_module.time())}",
        "rank": rank, "dynamic_rank": rank,
        "mission_type": "kill",
        "title": f"Hunt: {mob['short_desc']}",
        "description": (
            f"Defeat {mob['short_desc']} (level {mob.get('level', '?')})."
            if target_count == 1 else
            f"Defeat {target_count} of the following: {mob['short_desc']} (level {mob.get('level', '?')})."
        ),
        "target_mob_template": mob_vnum,
        "target_level": mob.get("level", 1),
        "target_count": target_count,
        "reward_xp": reward_xp, "reward_ryo": reward_ryo, "reward_mission_points": reward_mp,
        "min_level": min_level,
        "cooldown_seconds": cooldown_seconds,
    }

    now = time_module.time()
    player.active_missions.append({"mission_id": mission["mission_id"], "progress": 0,
                                   "dynamic": mission, "expires_at": now + MISSION_DURATION_SECONDS})
    player.mission_cooldowns[cooldown_key] = now + cooldown_seconds
    return (f"Mission requested: {mission['title']} ({rank}) -- {mission['description']}"
            " You have 30 minutes. Use 'mission info' for your target and deadline.")


def missions_for_village(village: str) -> List[dict]:
    return MISSIONS[village]


def mission_cooldown_seconds(mission: dict) -> float:
    return mission.get("cooldown_seconds", config.MISSION_COOLDOWN_SECONDS)


def cooldown_remaining(player: Player, mission_id: str) -> float:
    ready_at = player.mission_cooldowns.get(mission_id, 0)
    return max(0.0, ready_at - time.time())


def _format_duration(seconds: float) -> str:
    total = int(seconds)
    minutes, secs = divmod(total, 60)
    if minutes and secs:
        return f"{minutes}m {secs}s"
    if minutes:
        return f"{minutes}m"
    return f"{secs}s"


def accept_mission(player: Player, village: str, mission_id: str) -> str:
    mission = _find_mission(mission_id)
    if not mission or mission["village"] != village:
        return "There is no such mission here."
    min_level = mission.get("min_level", 1)
    if player.level < min_level:
        return f"You must be at least level {min_level} to accept {mission['title']} ({mission['rank']})."
    if any(m["mission_id"] == mission["mission_id"] for m in player.active_missions):
        return "You have already accepted this mission."
    remaining = cooldown_remaining(player, mission["mission_id"])
    if remaining > 0:
        return f"This mission is on cooldown. You can accept it again in {_format_duration(remaining)}."
    entry = {"mission_id": mission["mission_id"], "progress": 0,
             "expires_at": time.time() + MISSION_DURATION_SECONDS}
    if mission.get("mission_type", "kill") == "kill":
        # Static D-Rank kill templates can refer to Kage NPCs; never
        # assign untagged or level-inappropriate mobs to a hunt.
        vnum, mob = pick_mission_mob(player, "D-Rank")
        if mob is None:
            return "No suitable D-Rank Mission-tagged enemy is available for your level."
        chosen = dict(mission)
        chosen["target_mob_template"] = vnum
        chosen["target_level"] = mob.get("level", 1)
        chosen["title"] = f"Hunt: {mob['short_desc']}"
        chosen["description"] = f"Defeat {mob['short_desc']} (level {mob.get('level', '?')})."
        entry["dynamic"] = chosen
        mission = chosen
    player.active_missions.append(entry)
    result = (f"Mission accepted: {mission['title']} ({mission['rank']}) -- "
              f"{mission['description']} You have 30 minutes.")
    if mission.get("mission_type") == "gather":
        import combat
        delivery_proto = combat.MOB_TEMPLATES.get(mission["delivery_mob_template"])
        delivery_name = delivery_proto["short_desc"] if delivery_proto else "the right NPC"
        result += f"\nOnce you have enough, type 'deliver' at {delivery_name} to turn it in -- gathering the items alone doesn't finish it."
    return result


def expire_missions(player: Player, now=None) -> List[str]:
    """Fail overdue missions on real wall-clock time, including offline time.

    Old active mission entries lacking a deadline get one fresh window on
    upgrade, then that deadline is persisted with the player.
    """
    now = time.time() if now is None else now
    failed = []
    for entry in list(player.active_missions):
        deadline = entry.get("expires_at")
        if deadline is None:
            entry["expires_at"] = now + MISSION_DURATION_SECONDS
            continue
        if now >= deadline:
            player.active_missions.remove(entry)
            mission = _resolve_mission(entry)
            title = mission["title"] if mission else entry.get("mission_id", "Unknown mission")
            failed.append(f"&RMission failed (30-minute time limit): {title}.&x")
    return failed


def fail_mission(player: Player, rank_or_id="") -> str:
    """Abandon the most recent mission or select one by rank/ID/title."""
    if not player.active_missions:
        return "You have no active mission to fail."
    query = rank_or_id.strip().lower()
    matches = []
    for entry in player.active_missions:
        mission = _resolve_mission(entry)
        rank = (mission or {}).get("rank", "").lower()
        title = (mission or {}).get("title", "").lower()
        names = {entry.get("mission_id", "").lower(), title, rank,
                 rank.removesuffix("-rank")}
        if not query or query in names:
            matches.append(entry)
    if not matches:
        return f"No active mission matches {rank_or_id!r}. Use 'mission info'."
    entry = matches[-1]
    mission = _resolve_mission(entry)
    player.active_missions.remove(entry)
    title = mission["title"] if mission else entry.get("mission_id", "Unknown mission")
    return f"&RMission failed: {title}. No rewards were given.&x"


def mission_info(player: Player, now=None) -> str:
    """Show which mob to hunt, mob level/VNUM, progress and the clock."""
    now = time.time() if now is None else now
    if not player.active_missions:
        return "You have no active missions. Use 'mission request <rank>'."
    lines = ["&WActive missions (30-minute deadline):&x"]
    for entry in player.active_missions:
        mission = _resolve_mission(entry)
        if not mission:
            continue
        remaining = max(0, entry.get("expires_at", now + MISSION_DURATION_SECONDS) - now)
        lines.append(f"  &Y{mission['title']}&x ({mission['rank']})")
        if mission.get("mission_type", "kill") == "kill":
            import combat
            template = combat.MOB_TEMPLATES.get(mission["target_mob_template"], {})
            target = template.get("short_desc", mission["title"].removeprefix("Hunt: "))
            level = mission.get("target_level", template.get("level", "?"))
            lines.append(f"    Hunt: {target} (level {level}, mob VNUM {mission['target_mob_template']})")
        else:
            lines.append(f"    Objective: {mission['description']}")
        lines.append(f"    Progress: {entry.get('progress', 0)}/{mission['target_count']}")
        lines.append(f"    Time remaining: {_format_duration(remaining)}")
        lines.append(f"    To abandon: mission fail {mission['rank'].lower().replace('-rank', '')}")
    return "\n".join(lines)


def journal_text(player: Player) -> str:
    if not player.active_missions:
        return "You have no active missions."
    lines = ["Active missions:"]
    for entry in player.active_missions:
        mission = _resolve_mission(entry)
        line = (
            f"  {mission['title']} ({mission['rank']}) - "
            f"{entry['progress']}/{mission['target_count']} complete"
        )
        if mission.get("mission_type") == "gather":
            import combat
            delivery_proto = combat.MOB_TEMPLATES.get(mission["delivery_mob_template"])
            delivery_name = delivery_proto["short_desc"] if delivery_proto else "the right NPC"
            line += f"\n    (reaching the target doesn't finish it by itself -- type 'deliver' at {delivery_name} to turn it in)"
        lines.append(line)
    return "\n".join(lines)


def _find_mission(mission_id: str):
    for village_missions in MISSIONS.values():
        for mission in village_missions:
            if mission["mission_id"] == mission_id:
                return mission
    return None


def _resolve_mission(entry: dict):
    """Resolves an active_missions/completed-mission entry to its full
    mission dict -- checking the entry's own inline "dynamic" data
    first (a self-contained dict generated at request time by
    request_mission, since a dynamically-picked C/B/A/S mission has no
    static definition anywhere to look up by ID), falling back to the
    existing static MISSIONS lookup (_find_mission) for D-Rank and any
    other static mission. Every function that used to call
    _find_mission(entry["mission_id"]) directly now goes through this
    instead, so dynamic missions track and complete correctly too."""
    if isinstance(entry, dict) and entry.get("dynamic"):
        mission = entry["dynamic"]
    else:
        mission_id = entry["mission_id"] if isinstance(entry, dict) else entry
        mission = _find_mission(mission_id)
    # Existing saved hunts may still carry the old multi-kill target count.
    # Normalize at read time so active missions finish after one kill without
    # altering gather/delivery objectives or persisted player data.
    if mission and mission.get("mission_type", "kill") == "kill" and mission.get("target_count") != 1:
        mission = dict(mission, target_count=1)
        template = mission.get("target_mob_template")
        import combat
        name = combat.MOB_TEMPLATES.get(template, {}).get("short_desc")
        if name:
            mission["description"] = f"Defeat {name} (level {mission.get('target_level', '?')})."
    return mission


def completed_counts_by_rank(player: Player) -> dict:
    """Tally completed_missions (a full history, duplicates included) by
    rank, e.g. {'D-Rank': 7, 'C-Rank': 2}. Preserves a sensible rank order
    even for ranks the player hasn't completed yet, so the score sheet can
    show a stable line order as more ranks are added later. A dynamic
    C/B/A/S mission has no static definition to look back up after
    completion (its self-contained data lived only in the now-removed
    active_missions entry) -- its rank is parsed directly out of its own
    ID instead, which deliberately embeds it (f"dynamic_{rank}_...") for
    exactly this reason."""
    counts = {rank: 0 for rank in ["D-Rank", "C-Rank", "B-Rank", "A-Rank", "S-Rank"]}
    for mission_id in player.completed_missions:
        if mission_id.startswith("dynamic_"):
            rank = mission_id.split("_", 2)[1]
            counts[rank] = counts.get(rank, 0) + 1
            continue
        mission = _find_mission(mission_id)
        if not mission:
            continue
        rank = mission["rank"]
        counts[rank] = counts.get(rank, 0) + 1
    return counts


def _complete_mission(player: Player, mission: dict, entry: dict) -> List[str]:
    """Shared reward-granting tail for completing ANY mission type --
    xp/ryo/mission points/reputation/village perks, plus the cooldown
    (using this mission's OWN cooldown_seconds if it set one, e.g. the
    gather mission's 20 minutes vs the usual 10). Both on_mob_defeated
    (kill-type) and on_weeds_delivered (gather-type) call this once
    their own type-specific progress check is satisfied."""
    lines = []
    player.active_missions.remove(entry)
    player.completed_missions.append(mission["mission_id"])
    cooldown = mission_cooldown_seconds(mission)
    player.mission_cooldowns[mission["mission_id"]] = time.time() + cooldown
    import village_perks
    ryo_mult = village_perks.ryo_multiplier(player.village)
    ryo_reward = int(mission["reward_ryo"] * ryo_mult)
    player.ryo += ryo_reward
    player.mission_points += mission["reward_mission_points"]
    player.mission_points_earned_total += mission["reward_mission_points"]
    player.village_reputation[player.village] = (
        player.village_reputation.get(player.village, 0) + 5
    )
    xp_mult = village_perks.xp_multiplier(player.village)
    xp_reward = int(mission["reward_xp"] * xp_mult)
    import leveling
    experience_before = player.experience
    xp_messages = leveling.grant_experience(player, xp_reward)
    earned_xp = max(0, player.experience - experience_before)
    perk_notes = []
    if xp_mult != 1.0 and earned_xp:
        perk_notes.append(f"x{xp_mult:g} exp")
    if ryo_mult != 1.0:
        perk_notes.append(f"x{ryo_mult:g} ryo")
    perk_suffix = f" &Y({', '.join(perk_notes)} village perk)&x" if perk_notes else ""
    cap_note = (" &Y(Rank cap: no experience awarded.)&x"
                if not earned_xp and player.level >= leveling.rank_level_cap(player) else "")
    lines.append(
        f"&GMission complete: {mission['title']}!&x\n"
        f"You receive {earned_xp} experience, {ryo_reward} ryo, "
        f"and {mission['reward_mission_points']} mission point(s)."
        + perk_suffix + cap_note + "\n"
        f"This mission can be accepted again in {_format_duration(cooldown)}."
    )
    lines.extend(xp_messages)
    return lines


def on_mob_defeated(player: Player, template_vnum: int) -> List[str]:
    """Update mission progress after a mob kill; auto turn-in on
    completion. Only "kill"-type missions respond to this -- a
    "gather"-type mission's progress comes from commands.cmd_deliver
    instead (see on_weeds_delivered below)."""
    lines = expire_missions(player)
    for entry in list(player.active_missions):
        mission = _resolve_mission(entry)
        if not mission:
            continue
        if mission.get("mission_type", "kill") != "kill" or mission["target_mob_template"] != template_vnum:
            continue
        entry["progress"] += 1
        lines.append(f"Mission progress: {mission['title']} ({entry['progress']}/{mission['target_count']})")
        if entry["progress"] >= mission["target_count"]:
            lines.extend(_complete_mission(player, mission, entry))
    return lines


def on_weeds_delivered(player: Player, delivery_mob_template: int, delivered_count: int) -> List[str]:
    """Update mission progress after delivering gathered items (e.g.
    'deliver' handing weeds to a villager mob); auto turn-in on
    completion. Only "gather"-type missions respond to this. Progress
    increments by however many were actually delivered in one go
    (commands.cmd_deliver hands over everything the player is
    carrying at once, not one at a time), capped at the mission's
    target_count so over-delivering doesn't overshoot."""
    lines = expire_missions(player)
    for entry in list(player.active_missions):
        mission = _resolve_mission(entry)
        if not mission:
            continue
        if mission.get("mission_type") != "gather" or mission["delivery_mob_template"] != delivery_mob_template:
            continue
        entry["progress"] = min(mission["target_count"], entry["progress"] + delivered_count)
        lines.append(f"Mission progress: {mission['title']} ({entry['progress']}/{mission['target_count']})")
        if entry["progress"] >= mission["target_count"]:
            lines.extend(_complete_mission(player, mission, entry))
    return lines
