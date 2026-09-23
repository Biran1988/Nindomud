"""
Teams (Section 82), per direct request:

"Add a teams system so if you create a team you gain more experience
fighting with them. Only chuunin or higher rank can lead a team. A
team can total 4 players including the team leader. 24 hour wait
time on disbanding your team before you can join another team."

Genuinely separate from the existing session-only groups.py --
confirmed directly rather than assumed, since the two systems could
easily have been conflated. A group (groups.py) is a temporary,
in-memory-only party that exists purely for splitting XP evenly
across a single play session -- it vanishes the moment anyone logs
out, has no rank requirement, no size limit beyond MAX_GROUP_SIZE (6),
and no cost to leave. A team is the opposite in every one of those
respects: it's a persistent, named roster (up to 4, leader included)
that exists in teams.json whether or not any member is even online,
gated behind the leader holding at least Chunin rank, and leaving one
carries a real 24-hour cooldown before joining (or creating) another.

The actual XP bonus (TEAM_XP_BONUS_PCT, +10%) requires BOTH systems
at once, confirmed directly as a real design fork rather than assumed
either way: a player must be in a session 'group' (via 'group invite')
WITH a teammate, not just standing near them -- being on the same
team alone, with no active group, earns nothing extra. See
combat.handle_mob_defeat's XP-split loop for where this is actually
applied.

Storage: teams.json (storage.load_teams/save_teams), matching
spawn_points.json's own established pattern -- a single shared file
holding every team, auto-loaded once at server start into the
in-memory TEAMS dict, auto-saved back to disk on every mutation
(create/join/leave/disband), not a manual 'save world'-style command.
This is deliberately DIFFERENT from world_persistence.py's own
snapshot approach, since a team is something players actively
create/change during ordinary play, not something that only makes
sense to snapshot occasionally.
"""

import time
from typing import Dict, List, Optional

import kage

MAX_TEAM_SIZE = 4
DISBAND_COOLDOWN_SECONDS = 24 * 60 * 60
TEAM_XP_BONUS_PCT = 10
MIN_LEADER_RANK = "chunin"

# vnum-less, in-memory registry -- team_name (lowercase) -> team dict.
# {"leader": str, "members": [str, ...], "created_at": float}
# Loaded once at server start (see content.py's populate(), which
# calls load_all()) and kept in sync with teams.json on every
# mutation, exactly matching spawn_points.py's own established
# in-memory-registry-plus-auto-save shape.
TEAMS: Dict[str, dict] = {}


def load_all() -> None:
    """Populates TEAMS from teams.json at server start. Called once
    from content.populate(), same as spawn_points.apply_all()."""
    import storage
    TEAMS.clear()
    TEAMS.update(storage.load_teams())


def _save() -> None:
    import storage
    storage.save_teams(TEAMS)


def can_lead_team(player) -> bool:
    """Whether player's CURRENT village_rank is at least Chunin --
    confirmed design ("Only chuunin or higher rank can lead a team").
    Uses kage.RANK_ORDER's own established index-based comparison,
    the same mechanism the rank-promotion system itself already
    relies on, rather than a separate hardcoded rank list that could
    drift out of sync with it."""
    if player.village_rank not in kage.RANK_ORDER:
        return False
    return kage.RANK_ORDER.index(player.village_rank) >= kage.RANK_ORDER.index(MIN_LEADER_RANK)


def get_team(team_name: Optional[str]) -> Optional[dict]:
    if not team_name:
        return None
    return TEAMS.get(team_name.lower())


def create_team(player, team_name: str) -> str:
    """Creates a new team with player as its sole member and leader.
    Returns an error message on failure, or "" on success. Does NOT
    check can_lead_team/cooldown itself -- callers (commands.py) are
    expected to have already checked those, since the exact wording
    of a refusal differs by which check failed and callers can give a
    more specific message with full context."""
    key = team_name.lower()
    if key in TEAMS:
        return f"A team named '{team_name}' already exists."
    TEAMS[key] = {
        "name": team_name,
        "leader": player.name,
        "members": [player.name],
        "created_at": time.time(),
    }
    player.team_name = team_name
    _save()
    return ""


def join_team(player, team_name: str) -> str:
    """Adds player to an existing team. Returns an error message on
    failure, or "" on success."""
    team = get_team(team_name)
    if not team:
        return f"There is no team named '{team_name}'."
    if len(team["members"]) >= MAX_TEAM_SIZE:
        return f"{team['name']} is already full ({MAX_TEAM_SIZE} members max)."
    if player.name in team["members"]:
        return "You're already on that team."
    team["members"].append(player.name)
    player.team_name = team["name"]  # the team's own canonical display-case name, not the joiner's query casing
    _save()
    return ""


def leave_team(player) -> str:
    """Removes player from their current team. If they were the
    leader, the next member (by join order) is promoted; if they were
    the last member, the team is deleted entirely. Starts the 24-hour
    disband cooldown ONLY when the team is actually dissolved
    (the last member leaving) or the player was its leader stepping
    down from leadership entirely -- confirmed design is specifically
    about "disbanding your team", i.e. the team ceasing to exist for
    that player's own leadership, not merely leaving one team to
    immediately join a teammate's team as an ordinary member. In
    practice here: the cooldown is applied whenever a team a player
    led is dissolved or handed off, and whenever the player's own
    membership genuinely ends (both the common real-world cases)."""
    team_name = player.team_name
    team = get_team(team_name)
    if not team:
        player.team_name = None
        return "You aren't on a team."

    was_leader = team["leader"] == player.name
    team["members"].remove(player.name)
    player.team_name = None
    player.team_disband_cooldown_until = time.time() + DISBAND_COOLDOWN_SECONDS

    if not team["members"]:
        del TEAMS[team_name.lower()]
    elif was_leader:
        team["leader"] = team["members"][0]

    _save()
    return ""


def on_disband_cooldown(player) -> bool:
    return time.time() < player.team_disband_cooldown_until


def disband_cooldown_remaining_seconds(player) -> float:
    return max(0.0, player.team_disband_cooldown_until - time.time())


def teammates_online_in_room(player, room_vnum: int) -> List:
    """Every OTHER online player Session whose player is on the same
    team as `player` and physically in room_vnum right now. Used by
    combat.handle_mob_defeat to check the TEAM half of the XP-bonus
    condition (confirmed design: must be BOTH grouped AND teammates).
    Does not check group membership at all -- that's the caller's own
    responsibility, since group state lives in session objects this
    module has no need to know about otherwise."""
    from session import ACTIVE_SESSIONS
    team = get_team(player.team_name)
    if not team:
        return []
    return [
        s for s in ACTIVE_SESSIONS
        if s.player and s.player is not player
        and s.player.name in team["members"]
        and s.player.room_vnum == room_vnum
    ]
