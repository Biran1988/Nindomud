"""
Natural regeneration (Sections 11-12's resources, tied into the pulse
architecture from Section 16).

Regen ticks on a slower cadence than the combat pulse (see
config.REGEN_INTERVAL_SECONDS) and only for players who are NOT
currently fighting (server.py's pulse loop only calls tick_player() for
sessions with no combat_target). Rate scales with the player's rest
position (standing/resting/sleeping) and is further multiplied in any
room carrying the 'accelerated_healing' room flag -- set on every
village hospital by content.py, and toggleable elsewhere by staff via
`rset flags accelerated_healing`.

This is deliberately NOT a combat stance system (Section 16 rules that
out) -- resting/sleeping only ever affect out-of-combat regen rate. Hospital rooms provide a
stronger treatment bonus while retaining the normal regen tick schedule.
"""

from typing import Optional

import world

ACCELERATED_HEALING_FLAG = "accelerated_healing"

# Regen per tick as a percentage of the relevant maximum, capped at a
# flat per-tick maximum too (see _regen_amount) -- job actions and
# jutsu both cost a flat amount regardless of the player's own
# maximum (job actions: 1-2 stamina; jutsu: a handful of chakra), so
# regen must never be allowed to scale past what a flat drain can
# outpace, no matter how large a stat-bonus-inflated maximum grows.
# Set to 1/4 of the original rates (0.02/0.03/0.04) per explicit request.
BASE_REGEN_PERCENT = {
    "health": 0.005,
    "chakra": 0.0075,
    "stamina": 0.01,
}

# Flat per-tick cap per resource, per direct follow-up bug report
# ("one character is regen faster then suing the stamina") -- verified
# live that a Lumberjack-25 character (425 maximum_stamina) already
# regens faster (4/10s) than continuous gathering can drain (2.5/10s,
# from the flat 1-2 stamina cost every 6s -- see jobs.
# try_deduct_action_stamina). Stamina's cap (2) is deliberately set
# BELOW that 2.5 drain rate so it can never be outrun, no matter how
# large a stat-bonus-inflated maximum_stamina grows. Chakra (jutsu
# spam drains at 33+/10s minimum, see data_jutsu.py) and health (even
# a weak early mob deals ~14/10s in combat) both have real drain rates
# far above any cap that would still let their own regen mean
# anything, so their caps are generous headroom, not a tight fix --
# stamina is the one resource where a small flat action cost is
# actually at risk of being outrun by a large enough maximum. Health's
# cap specifically needs to stay well above 25 -- an existing test
# deliberately inflates maximum_health to 1000 so the position-
# multiplier differences (standing/resting/sleeping/hospital) stay
# visibly distinct above the regen floor, and the hospital case alone
# needs 25+ of headroom to remain detectable.
REGEN_FLAT_CAP = {
    "health": 50,
    "chakra": 10,
    "stamina": 2,
}

POSITION_MULTIPLIER = {
    "standing": 1.0,
    "resting": 1.75,
    "sleeping": 3.0,
}

HOSPITAL_MULTIPLIER = 10.0
# Hospital healing bypasses ordinary per-tick caps. Resource maximums still apply.


CHAKRA_CONTROL_REGEN_BONUS_PER_POINT = 0.5  # confirmed directly: same real rate as the other new resource formulas (Section 130)


def chakra_control_regen_bonus(chakra_control: int) -> int:
    """The real, uncapped extra chakra restored per regen tick from
    Chakra Control -- per direct request/confirmation (Section 131):
    "makes you regen chakra more often," confirmed to mean MORE
    chakra per existing tick (not a faster tick), and confirmed
    directly to be allowed to exceed REGEN_FLAT_CAP["chakra"] (10),
    since a maxed Chakra Control genuinely deserves noticeably faster
    regen than that cap currently allows. +0.5 per point above the
    baseline of 10, no ceiling of its own."""
    if chakra_control <= 10:
        return 0
    return round((chakra_control - 10) * CHAKRA_CONTROL_REGEN_BONUS_PER_POINT)


def _regen_amount(maximum: int, resource: str, multiplier: float, *, hospital: bool = False) -> int:
    """Calculate out-of-combat recovery.

    Standing uses the familiar flat normal caps so activity costs still
    exceed ordinary regen at high stats. Sleeping triples the *actual*
    standing recovery, even when ordinary regen has hit that cap.
    Hospitals bypass flat caps completely and restore at least 10x the
    standing recovery; sleeping in hospital triples the hospital rate.
    All final resources are still clamped to the character maximum.
    """
    if maximum <= 0:
        return 0
    normal = max(1, min(int(maximum * BASE_REGEN_PERCENT[resource]),
                        REGEN_FLAT_CAP[resource]))
    if hospital:
        # multiplier is 10x while standing or 30x while sleeping.
        # Scale both the uncapped percentage and the standing recovery
        # floor, ensuring 10x/30x even for small resource pools.
        return max(int(maximum * BASE_REGEN_PERCENT[resource] * multiplier),
                   int(normal * multiplier))
    return max(1, int(normal * multiplier))


def tick_sharingan_idle(player) -> list:
    """Charge idle Sharingan upkeep on its own 10-second timer."""
    messages = []
    if player.sharingan_active:
        import commands
        import upkeep_reports
        if player.chakra < commands.SHARINGAN_IDLE_CHAKRA_UPKEEP:
            player.sharingan_active = False
            messages.extend(upkeep_reports.flush(player, "Sharingan"))
            messages.append("&RYour chakra gives out -- your Sharingan fades back to black.&x")
        else:
            player.chakra -= commands.SHARINGAN_IDLE_CHAKRA_UPKEEP
            messages.extend(upkeep_reports.record(player, "Sharingan", commands.SHARINGAN_IDLE_CHAKRA_UPKEEP))
            import combat
            messages.extend(combat.tick_sharingan_mastery_gain(player))

    return messages


def tick_player(player) -> list:
    """Apply a natural regeneration tick silently outside combat."""
    if player.health <= 0:
        return []

    multiplier = POSITION_MULTIPLIER.get(player.position, 1.0)
    room = world.WORLD.get(player.room_vnum)
    hospital = bool(room and ACCELERATED_HEALING_FLAG in room.flags)
    if hospital:
        multiplier *= HOSPITAL_MULTIPLIER

    player.health = min(player.maximum_health,
                        player.health + _regen_amount(player.maximum_health, "health", multiplier, hospital=hospital))
    player.chakra = min(player.maximum_chakra,
                         player.chakra + _regen_amount(player.maximum_chakra, "chakra", multiplier, hospital=hospital) + chakra_control_regen_bonus(player.chakra_control))
    player.stamina = min(player.maximum_stamina,
                          player.stamina + _regen_amount(player.maximum_stamina, "stamina", multiplier, hospital=hospital))

    return []
