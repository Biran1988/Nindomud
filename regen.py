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
out) -- resting/sleeping only ever affect out-of-combat regen rate and
are auto-cancelled the moment a player moves or enters combat.
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
    "sleeping": 2.5,
}

HOSPITAL_MULTIPLIER = 2.0


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


def _regen_amount(maximum: int, resource: str, multiplier: float) -> int:
    if maximum <= 0:
        return 0
    raw = int(maximum * BASE_REGEN_PERCENT[resource] * multiplier)
    return max(1, min(raw, REGEN_FLAT_CAP[resource]))


def tick_player(player) -> list:
    """Apply one regen tick to a non-fighting player, plus the
    Sharingan's idle upkeep if it's active (per direct request "make
    sharingan cost upkeep at all times" -- this function already only
    runs for a player with no combat_target/pvp_target, see server.py's
    caller, so hooking the idle drain in here is what makes it apply
    "at all times, including outside combat" without a third, separate
    always-on loop). Returns a list of messages (possibly empty) --
    the one-time 'fully recovered' message the moment all three
    resources cap out, and/or the Sharingan-fading message if idle
    upkeep just turned it off -- rather than the single Optional[str]
    this used to return, matching the for-message-in-tick_x pattern
    already used throughout combat.py for the same kind of multi-
    source per-tick messaging."""
    messages = []
    if player.sharingan_active:
        import commands
        if player.chakra < commands.SHARINGAN_IDLE_CHAKRA_UPKEEP:
            player.sharingan_active = False
            messages.append("&RYour chakra gives out -- your Sharingan fades back to black.&x")
        else:
            player.chakra -= commands.SHARINGAN_IDLE_CHAKRA_UPKEEP

    if player.health <= 0:
        return messages

    was_full = (
        player.health >= player.maximum_health
        and player.chakra >= player.maximum_chakra
        and player.stamina >= player.maximum_stamina
    )
    if was_full:
        return messages

    multiplier = POSITION_MULTIPLIER.get(player.position, 1.0)
    room = world.WORLD.get(player.room_vnum)
    if room and ACCELERATED_HEALING_FLAG in room.flags:
        multiplier *= HOSPITAL_MULTIPLIER

    player.health = min(player.maximum_health,
                        player.health + _regen_amount(player.maximum_health, "health", multiplier))
    player.chakra = min(player.maximum_chakra,
                         player.chakra + _regen_amount(player.maximum_chakra, "chakra", multiplier) + chakra_control_regen_bonus(player.chakra_control))
    player.stamina = min(player.maximum_stamina,
                          player.stamina + _regen_amount(player.maximum_stamina, "stamina", multiplier))

    now_full = (
        player.health >= player.maximum_health
        and player.chakra >= player.maximum_chakra
        and player.stamina >= player.maximum_stamina
    )
    if now_full:
        messages.append("&GYou feel fully recovered.&x")
    return messages
